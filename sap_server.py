# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]",
#     "zeep",
#     "requests",
#     "pydantic",
#     "uvicorn"
# ]
# ///

import os
import requests
import uvicorn
import sys
from mcp.server.fastmcp import FastMCP
from zeep import Client, Settings
from zeep.transports import Transport
from pydantic import BaseModel, Field
from typing import List, Optional

# ==============================================================================
# 1. 設定區 (Configuration) - 優雅管理版
# ==============================================================================
class SAPConfig:
    # 基礎設定 (日後若要切換 QA/PRD 或 Client，只要改這裡)
    HOST = "vhivcqasci.sap.inventec.com:44300"
    CLIENT = "100"
    PROTOCOL = "https"

    # 服務路徑清單 (自動填入 {client})
    # 這是根據您提供的真實網址提取出的路徑結構
    SERVICES = {
        # Create Sales Order
        "SO": "zws_bapi_salesorder_create/{client}/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding",

        # Create STO (Stock Transport Order)
        "STO": "zsd_sto_create/{client}/zsd_sto_create_svr/zsd_sto_create_binding",

        # Create Delivery Note
        "DN": "zws_bapi_outb_delivery_create/{client}/zws_bapi_outb_delivery_create/bind_dn_create",

        # Material Master View (Basic, Sales, Storage, Warehouse)
        "MAT": "zws_bapi_material_savedata/{client}/zws_bapi_material_savedata/bind_material",

        # Maintain Source List
        "SRC": "zsd_source_list_maintain/{client}/zsd_source_list_maintain_svr/zsd_source_list_maintain_binding",

        # Maintain Info Record
        "INF": "zws_info_record_maintain/{client}/zws_info_record_maintain_svr/zws_info_record_maintain_binding"
    }

    @classmethod
    def get_url(cls, key: str) -> str:
        """自動組裝完整的 WSDL URL"""
        if key not in cls.SERVICES:
            raise ValueError(f"Unknown SAP Service Key: {key}")

        # 1. 取出路徑並填入 Client ID
        path = cls.SERVICES[key].format(client=cls.CLIENT)

        # 2. 組合完整網址 (加上 ?wsdl)
        return f"{cls.PROTOCOL}://{cls.HOST}/sap/bc/srt/rfc/sap/{path}?wsdl"

# ==============================================================================
# 2. 核心連線功能
# ==============================================================================
mcp = FastMCP("SAP All-in-One Service")

def get_client(wsdl_url: str):
    """建立 SAP 連線 Client"""
    SAP_USER = os.environ.get("SAP_USER")
    SAP_PASSWORD = os.environ.get("SAP_PASSWORD")

    if not SAP_USER or not SAP_PASSWORD:
        raise ValueError("Error: SAP_USER or SAP_PASSWORD environment variables are not set.")

    session = requests.Session()
    session.auth = (SAP_USER, SAP_PASSWORD)
    session.verify = False  # 忽略 SSL 憑證檢查 (內部系統常用)

    transport = Transport(session=session)
    settings = Settings(strict=False, xml_huge_tree=True)

    try:
        return Client(wsdl=wsdl_url, transport=transport, settings=settings)
    except Exception as e:
        raise ConnectionError(f"Failed to connect to WSDL: {wsdl_url}. Error: {e}")

# ==============================================================================
# 3. 工具定義 (Tools)
# ==============================================================================

# --- [1] Create Sales Order (SO) ---
class SOItem(BaseModel):
    MATERIAL_NO: str = Field(..., description="Item Number (e.g. '000010')")
    MATERIAL: str = Field(..., description="Material Number (e.g. '1510B3693501')")
    QTY: float = Field(..., description="Quantity")
    UNIT: str = Field(..., description="Unit (e.g. 'PCE')")
    PLANT: str = Field(..., description="Plant (e.g. 'TP01')")
    SHIPPING_POINT: str = Field(..., description="Shipping Point (e.g. 'TW01')")
    DELIVERY_DATE: str = Field(..., description="Delivery Date YYYY-MM-DD")
    CUST_MATERIAL: Optional[str] = Field(None, description="Customer Material Number")

@mcp.tool()
def create_sales_order(
    ORDER_TYPE: str = Field(..., description="Order Type (e.g. ZIES)"),
    SALES_ORG: str = Field(..., description="Sales Org (e.g. TW01)"),
    SALES_CHANNEL: str = Field(..., description="Channel (e.g. 03)"),
    SALES_DIVISION: str = Field(..., description="Division (e.g. 01)"),
    CUST_PO: str = Field(..., description="Customer PO Number"),
    CUST_PO_DATE: str = Field(..., description="Customer PO Date YYYY-MM-DD"),
    SOLD_TO_PARTY: str = Field(..., description="Sold-To Party"),
    SHIP_TO_PARTY: str = Field(..., description="Ship-To Party"),
    SO_ITEM: List[SOItem] = Field(..., description="List of Items")
) -> str:
    """Create Sales Order (ZBAPI_SALESORDER_CREATE)"""
    try:
        client = get_client(SAPConfig.get_url("SO"))
        items_payload = [item.model_dump(exclude_none=True) for item in SO_ITEM]

        res = client.service.ZBAPI_SALESORDER_CREATE(
            ORDER_TYPE=ORDER_TYPE,
            SALES_ORG=SALES_ORG,
            SALES_CHANNEL=SALES_CHANNEL,
            SALES_DIVISION=SALES_DIVISION,
            CUST_PO=CUST_PO,
            CUST_PO_DATE=CUST_PO_DATE,
            SOLD_TO_PARTY=SOLD_TO_PARTY,
            SHIP_TO_PARTY=SHIP_TO_PARTY,
            SO_ITEM={'item': items_payload}
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error creating SO: {str(e)}"


# --- [2] Create STO / Purchase Order ---
class PRItem(BaseModel):
    ITEM_NO: str = Field(..., description="PR Item Number (e.g. '00010')")

@mcp.tool()
def create_sto_po(
    PR_NUMBER: str = Field(..., description="Purchase Requisition Number"),
    PUR_GROUP: str = Field(..., description="Purchasing Group (e.g. '999')"),
    PUR_ORG: str = Field(..., description="Purchasing Org (e.g. 'TW10')"),
    PUR_PLANT: str = Field(..., description="Plant (e.g. 'TP01')"),
    VENDOR: str = Field(..., description="Vendor Code"),
    DOC_TYPE: str = Field("NB", description="Order Type (Default: NB)"),
    PR_ITEMS: List[PRItem] = Field(..., description="List of PR items"),
    LGORT: Optional[str] = Field(None, description="Storage Location (Optional)")
) -> str:
    """Create STO PO from PR (ZSD_STO_CREATE)"""
    try:
        client = get_client(SAPConfig.get_url("STO"))
        pr_payload = [{'ITEM_NO': item.ITEM_NO} for item in PR_ITEMS]

        # 這裡呼叫 ZSD_STO_CREATE (若名稱有變請調整)
        res = client.service.ZSD_STO_CREATE(
            PR_NUMBER=PR_NUMBER,
            PR_ITEM={'item': pr_payload},
            PUR_GROUP=PUR_GROUP,
            PUR_ORG=PUR_ORG,
            PUR_PLANT=PUR_PLANT,
            VENDOR=VENDOR,
            DOC_TYPE=DOC_TYPE,
            LGORT=LGORT
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error creating STO: {str(e)}"


# --- [3] Create Delivery Note (DN) ---
class DNItem(BaseModel):
    REF_DOC: str = Field(..., description="Reference PO Number")
    REF_ITEM: str = Field(..., description="Reference PO Item (e.g. '000010')")
    DLV_QTY: float = Field(..., description="Delivery Quantity")
    SALES_UNIT: str = Field(..., description="Sales Unit (e.g. 'EA')")

@mcp.tool()
def create_outbound_delivery(
    SHIP_POINT: str = Field(..., description="Shipping Point"),
    PO_ITEM: List[DNItem] = Field(..., description="Items to Deliver"),
    DUE_DATE: Optional[str] = Field(None, description="Due Date YYYY-MM-DD")
) -> str:
    """Create Outbound Delivery (ZWS_BAPI_OUTB_DELIVERY_CREATE)"""
    try:
        client = get_client(SAPConfig.get_url("DN"))
        items_payload = [item.model_dump() for item in PO_ITEM]

        # 嘗試呼叫 ZWS 包裹的 Function，或者內部的 ZBAPI_OUTB_DELIVERY_CREATE_STO
        # 根據您的 CSV 結構，核心邏輯是 STO
        if hasattr(client.service, 'ZBAPI_OUTB_DELIVERY_CREATE_STO'):
             res = client.service.ZBAPI_OUTB_DELIVERY_CREATE_STO(
                SHIP_POINT=SHIP_POINT,
                PO_ITEM={'item': items_payload},
                DUE_DATE=DUE_DATE
            )
        else:
            # Fallback (根據 Service Name)
            res = client.service.ZWS_BAPI_OUTB_DELIVERY_CREATE(
                SHIP_POINT=SHIP_POINT,
                PO_ITEM={'item': items_payload},
                DUE_DATE=DUE_DATE
            )
        return f"Result: {res}"
    except Exception as e:
        return f"Error creating DN: {str(e)}"


# --- [4] Material View (Material / Warehouse / Storage) ---
@mcp.tool()
def create_material_view(
    MATERIAL: str = Field(..., description="Material Number"),
    SALES_VIEW: bool = Field(False, description="Create Sales View"),
    STORAGE_VIEW: bool = Field(False, description="Create Storage View"),
    WAREHOUSE_VIEW: bool = Field(False, description="Create Warehouse View")
) -> str:
    """Maintain Material Master Views (ZWS_BAPI_MATERIAL_SAVEDATA)"""
    try:
        client = get_client(SAPConfig.get_url("MAT"))
        headdata = {'MATERIAL': MATERIAL}

        res = client.service.ZWS_BAPI_MATERIAL_SAVEDATA(
            HEADDATA=headdata,
            SALES_VIEW='X' if SALES_VIEW else '',
            STORAGE_VIEW='X' if STORAGE_VIEW else '',
            WAREHOUSE_VIEW='X' if WAREHOUSE_VIEW else ''
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error maintaining Material: {str(e)}"


# --- [5] Maintain Source List ---
@mcp.tool()
def maintain_source_list(
    PLANT: str = Field(..., description="Plant Code"),
    MATERIAL: str = Field(..., description="Material Number"),
    VENDOR: str = Field(..., description="Vendor Code"),
    VALID_FROM: str = Field(..., description="Valid From YYYY-MM-DD"),
    VALID_TO: str = Field(..., description="Valid To YYYY-MM-DD")
) -> str:
    """Maintain Source List (ZSD_SOURCE_LIST_MAINTAIN)"""
    try:
        client = get_client(SAPConfig.get_url("SRC"))
        res = client.service.ZSD_SOURCE_LIST_MAINTAIN(
            PLANT=PLANT,
            MATERIAL=MATERIAL,
            VENDOR=VENDOR,
            VALID_FROM=VALID_FROM,
            VALID_TO=VALID_TO
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error maintaining Source List: {str(e)}"


# --- [6] Maintain Info Record ---
@mcp.tool()
def maintain_info_record(
    VENDOR: str = Field(..., description="Vendor Code"),
    MATERIAL: str = Field(..., description="Material Number"),
    PUR_ORG: str = Field(..., description="Purchasing Org"),
    PLANT: str = Field(..., description="Plant"),
    PRICE: float = Field(..., description="Net Price"),
    PRICE_UNIT: int = Field(..., description="Price Unit (e.g. 1)"),
    CURRENCY: str = Field(..., description="Currency (e.g. USD)")
) -> str:
    """Maintain Info Record (ZWS_INFO_RECORD_MAINTAIN)"""
    try:
        client = get_client(SAPConfig.get_url("INF"))
        res = client.service.ZWS_INFO_RECORD_MAINTAIN(
            VENDOR=VENDOR,
            MATERIAL=MATERIAL,
            PUR_ORG=PUR_ORG,
            PLANT=PLANT,
            PRICE=PRICE,
            PRICE_UNIT=PRICE_UNIT,
            CURRENCY=CURRENCY
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error maintaining Info Record: {str(e)}"


# ==============================================================================
# 4. 啟動伺服器 (Web/SSE 模式) - 適用於 EMCP 平台
# ==============================================================================
if __name__ == "__main__":
    mcp.run()