# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]",
#     "zeep",
#     "requests",
#     "pydantic",
# ]
# ///

import os
import requests
import sys
from mcp.server.fastmcp import FastMCP
from zeep import Client, Settings
from zeep.transports import Transport
from pydantic import BaseModel, Field
from typing import List, Optional

# ==============================================================================
# 1. 設定區 (Configuration)
# ==============================================================================
class SAPConfig:
    HOST = "vhivcqasci.sap.inventec.com:44300"
    CLIENT = "100"
    PROTOCOL = "https"

    # 服務路徑清單
    SERVICES = {
        "SO": "zws_bapi_salesorder_create/{client}/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding",
        "STO": "zsd_sto_create/{client}/zsd_sto_create_svr/zsd_sto_create_binding",
        "DN": "zws_bapi_outb_delivery_create/{client}/zws_bapi_outb_delivery_create/bind_dn_create",
        "MAT": "zws_bapi_material_savedata/{client}/zws_bapi_material_savedata/bind_material",
        "SRC": "zsd_source_list_maintain/{client}/zsd_source_list_maintain_svr/zsd_source_list_maintain_binding",
        "INF": "zws_info_record_maintain/{client}/zws_info_record_maintain_svr/zws_info_record_maintain_binding"
    }

    @classmethod
    def get_url(cls, key: str) -> str:
        if key not in cls.SERVICES:
            raise ValueError(f"Unknown SAP Service Key: {key}")
        path = cls.SERVICES[key].format(client=cls.CLIENT)
        return f"{cls.PROTOCOL}://{cls.HOST}/sap/bc/srt/rfc/sap/{path}?wsdl"

# ==============================================================================
# 2. 核心連線功能
# ==============================================================================
mcp = FastMCP("SAP All-in-One Service")

def get_client(wsdl_url: str):
    SAP_USER = os.environ.get("SAP_USER")
    SAP_PASSWORD = os.environ.get("SAP_PASSWORD")

    if not SAP_USER or not SAP_PASSWORD:
        raise ValueError("Error: SAP_USER or SAP_PASSWORD environment variables are not set.")

    session = requests.Session()
    session.auth = (SAP_USER, SAP_PASSWORD)
    session.verify = False

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
    MATERIAL_NO: str = Field(..., description="Item No e.g. '000010'")
    MATERIAL: str = Field(..., description="Material e.g. '1510B3693501'")
    QTY: float = Field(..., description="Quantity")
    UNIT: str = Field(..., description="Unit e.g. 'PCE'")
    PLANT: str = Field(..., description="Plant e.g. 'TP01'")
    SHIPPING_POINT: str = Field(..., description="Shipping Point e.g. 'TW01'")
    DELIVERY_DATE: str = Field(..., description="Date YYYY-MM-DD")
    CUST_MATERIAL: Optional[str] = Field(None, description="Customer Material")

@mcp.tool()
def create_sales_order(
    ORDER_TYPE: str = Field(..., description="Order Type (e.g. ZIES)"),
    SALES_ORG: str = Field(..., description="Sales Org (e.g. TW01)"),
    SALES_CHANNEL: str = Field(..., description="Channel (e.g. 03)"),
    SALES_DIVISION: str = Field(..., description="Division (e.g. 01)"),
    CUST_PO: str = Field(..., description="Customer PO No"),
    CUST_PO_DATE: str = Field(..., description="Customer PO Date YYYY-MM-DD"),
    SOLD_TO_PARTY: str = Field(..., description="Sold-To Party"),
    SHIP_TO_PARTY: str = Field(..., description="Ship-To Party"),
    SO_ITEM: List[SOItem] = Field(..., description="Items")
) -> str:
    """Create Sales Order (ZBAPI_SALESORDER_CREATE)"""
    try:
        client = get_client(SAPConfig.get_url("SO"))
        items = [x.model_dump(exclude_none=True) for x in SO_ITEM]
        res = client.service.ZBAPI_SALESORDER_CREATE(
            ORDER_TYPE=ORDER_TYPE, SALES_ORG=SALES_ORG,
            SALES_CHANNEL=SALES_CHANNEL, SALES_DIVISION=SALES_DIVISION,
            CUST_PO=CUST_PO, CUST_PO_DATE=CUST_PO_DATE,
            SOLD_TO_PARTY=SOLD_TO_PARTY, SHIP_TO_PARTY=SHIP_TO_PARTY,
            SO_ITEM={'item': items}
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (SO): {str(e)}"

# --- [2] Create STO PO ---
class PRItem(BaseModel):
    ITEM_NO: str = Field(..., description="PR Item Number (e.g. '00010')")

@mcp.tool()
def create_sto_po(
    PR_NUMBER: str = Field(..., description="PR Number"),
    PUR_GROUP: str = Field(..., description="Purch Group"),
    PUR_ORG: str = Field(..., description="Purch Org"),
    PUR_PLANT: str = Field(..., description="Plant"),
    VENDOR: str = Field(..., description="Vendor"),
    DOC_TYPE: str = Field("NB", description="Doc Type"),
    PR_ITEMS: List[PRItem] = Field(..., description="PR Items"),
    LGORT: Optional[str] = Field(None, description="Storage Loc")
) -> str:
    """Create STO PO from PR (ZSD_STO_CREATE)"""
    try:
        client = get_client(SAPConfig.get_url("STO"))
        pr_payload = [{'ITEM_NO': item.ITEM_NO} for item in PR_ITEMS]
        res = client.service.ZSD_STO_CREATE(
            PR_NUMBER=PR_NUMBER, PR_ITEM={'item': pr_payload},
            PUR_GROUP=PUR_GROUP, PUR_ORG=PUR_ORG,
            PUR_PLANT=PUR_PLANT, VENDOR=VENDOR,
            DOC_TYPE=DOC_TYPE, LGORT=LGORT
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (STO): {str(e)}"

# --- [3] Create DN ---
class DNItem(BaseModel):
    REF_DOC: str = Field(..., description="PO Number")
    REF_ITEM: str = Field(..., description="PO Item No (e.g. '000010')")
    DLV_QTY: float = Field(..., description="Qty")
    SALES_UNIT: str = Field(..., description="Unit (e.g. 'EA')")

@mcp.tool()
def create_outbound_delivery(
    SHIP_POINT: str = Field(..., description="Shipping Point"),
    PO_ITEM: List[DNItem] = Field(..., description="Items"),
    DUE_DATE: Optional[str] = Field(None, description="Due Date")
) -> str:
    """Create Delivery (ZWS_BAPI_OUTB_DELIVERY_CREATE)"""
    try:
        client = get_client(SAPConfig.get_url("DN"))
        items = [x.model_dump() for x in PO_ITEM]

        # 嘗試呼叫 ZBAPI_OUTB_DELIVERY_CREATE_STO
        # 這是根據您提供的 CSV 與 網址綜合判斷的正確 Function Name
        if hasattr(client.service, 'ZBAPI_OUTB_DELIVERY_CREATE_STO'):
             res = client.service.ZBAPI_OUTB_DELIVERY_CREATE_STO(
                SHIP_POINT=SHIP_POINT, PO_ITEM={'item': items}, DUE_DATE=DUE_DATE
            )
        else:
            # Fallback
            res = client.service.ZWS_BAPI_OUTB_DELIVERY_CREATE(
                SHIP_POINT=SHIP_POINT, PO_ITEM={'item': items}, DUE_DATE=DUE_DATE
            )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (DN): {str(e)}"

# --- [4] Material View ---
@mcp.tool()
def create_material_view(
    MATERIAL: str = Field(..., description="Material No"),
    SALES_VIEW: bool = Field(False, description="Flag"),
    STORAGE_VIEW: bool = Field(False, description="Flag"),
    WAREHOUSE_VIEW: bool = Field(False, description="Flag")
) -> str:
    """Maintain Material Views"""
    try:
        client = get_client(SAPConfig.get_url("MAT"))
        res = client.service.ZWS_BAPI_MATERIAL_SAVEDATA(
            HEADDATA={'MATERIAL': MATERIAL},
            SALES_VIEW='X' if SALES_VIEW else '',
            STORAGE_VIEW='X' if STORAGE_VIEW else '',
            WAREHOUSE_VIEW='X' if WAREHOUSE_VIEW else ''
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (Material): {str(e)}"

# --- [5] Source List ---
@mcp.tool()
def maintain_source_list(
    PLANT: str, MATERIAL: str, VENDOR: str, VALID_FROM: str, VALID_TO: str
) -> str:
    """Maintain Source List"""
    try:
        client = get_client(SAPConfig.get_url("SRC"))
        res = client.service.ZSD_SOURCE_LIST_MAINTAIN(
            PLANT=PLANT, MATERIAL=MATERIAL, VENDOR=VENDOR,
            VALID_FROM=VALID_FROM, VALID_TO=VALID_TO
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (SourceList): {str(e)}"

# --- [6] Info Record ---
@mcp.tool()
def maintain_info_record(
    VENDOR: str, MATERIAL: str, PUR_ORG: str, PLANT: str,
    PRICE: float, PRICE_UNIT: int, CURRENCY: str
) -> str:
    """Maintain Info Record"""
    try:
        client = get_client(SAPConfig.get_url("INF"))
        res = client.service.ZWS_INFO_RECORD_MAINTAIN(
            VENDOR=VENDOR, MATERIAL=MATERIAL, PUR_ORG=PUR_ORG,
            PLANT=PLANT, PRICE=PRICE, PRICE_UNIT=PRICE_UNIT, CURRENCY=CURRENCY
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (InfoRecord): {str(e)}"

# ==============================================================================
# 4. 啟動 (Stdio Mode)
# ==============================================================================
if __name__ == "__main__":
    # 這裡改回了 mcp.run()，這樣您的 EMCP 平台就能正確讀取了
    mcp.run()