# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]",
#     "zeep",
#     "requests",
#     "pydantic>=2.0",
# ]
# ///

import os
import requests
import sys
from typing import List, Optional, Annotated, Any
from mcp.server.fastmcp import FastMCP
from zeep import Client, Settings
from zeep.transports import Transport
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator

# ==============================================================================
# 0. 核心工具
# ==============================================================================
def ensure_list_validator(v: Any) -> Any:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]

SmartList = Annotated[List, BeforeValidator(ensure_list_validator)]

# ==============================================================================
# 1. 設定區 (Configuration) - 包含 Binding Name
# ==============================================================================
class SAPConfig:
    HOST = "vhivcqasci.sap.inventec.com:44300"
    CLIENT = "100"
    PROTOCOL = "https"
    NAMESPACE = "urn:sap-com:document:sap:rfc:functions" # SAP 標準 Namespace

    # [設定結構]
    # path: 網址路徑 (不含 host)
    # binding: WSDL 內的 Binding 名稱 (通常對應 URL 最後一段的大寫)
    SERVICES = {
        "SO": {
            "path": "zws_bapi_salesorder_create/{client}/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding",
            "binding": "ZWS_BAPI_SALESORDER_CREATE_BINDING"
        },
        "STO": {
            "path": "zsd_sto_create/{client}/zsd_sto_create_svr/zsd_sto_create_binding",
            "binding": "ZSD_STO_CREATE_BINDING"
        },
        "DN": {
            "path": "zws_bapi_outb_delivery_create/{client}/zws_bapi_outb_delivery_create/bind_dn_create",
            "binding": "BIND_DN_CREATE"
        },
        "MAT": {
            "path": "zws_bapi_material_savedata/{client}/zws_bapi_material_savedata/bind_material",
            "binding": "BIND_MATERIAL"
        },
        "SRC": {
            "path": "zsd_source_list_maintain/{client}/zsd_source_list_maintain_svr/zsd_source_list_maintain_binding",
            "binding": "ZSD_SOURCE_LIST_MAINTAIN_BINDING"
        },
        "INF": {
            "path": "zws_info_record_maintain/{client}/zws_info_record_maintain_svr/zws_info_record_maintain_binding",
            "binding": "ZWS_INFO_RECORD_MAINTAIN_BINDING"
        }
    }

    @classmethod
    def get_info(cls, key: str):
        if key not in cls.SERVICES:
            raise ValueError(f"Unknown SAP Service Key: {key}")

        cfg = cls.SERVICES[key]
        path = cfg["path"].format(client=cls.CLIENT)

        # 1. WSDL URL (下載定義用)
        wsdl_url = f"{cls.PROTOCOL}://{cls.HOST}/sap/bc/srt/rfc/sap/{path}?wsdl"

        # 2. Service Address (實際呼叫用，通常就是不含 ?wsdl 的網址)
        address = f"{cls.PROTOCOL}://{cls.HOST}/sap/bc/srt/rfc/sap/{path}"

        # 3. Binding QName (告訴 zeep 綁定哪一個 port)
        # 格式: {Namespace}BindingName
        binding_name = f"{{{cls.NAMESPACE}}}{cfg['binding']}"

        return wsdl_url, address, binding_name

# ==============================================================================
# 2. 核心連線功能
# ==============================================================================
mcp = FastMCP("SAP All-in-One Service")

def get_service_proxy(key: str):
    """
    建立 SAP 連線並強制綁定到正確的 Service/Port
    解決 'No default service defined' 錯誤
    """
    SAP_USER = os.environ.get("SAP_USER")
    SAP_PASSWORD = os.environ.get("SAP_PASSWORD")

    if not SAP_USER or not SAP_PASSWORD:
        raise ValueError("Error: SAP_USER or SAP_PASSWORD environment variables are not set.")

    # 1. 取得連線資訊
    wsdl_url, address, binding_name = SAPConfig.get_info(key)

    # 2. 建立 Session
    session = requests.Session()
    session.auth = (SAP_USER, SAP_PASSWORD)
    session.verify = False
    transport = Transport(session=session)
    settings = Settings(strict=False, xml_huge_tree=True)

    try:
        # 3. 下載 WSDL
        client = Client(wsdl=wsdl_url, transport=transport, settings=settings)

        # 4. 強制建立 Service Proxy
        service = client.create_service(binding_name, address)

        return service
    except Exception as e:
        raise ConnectionError(f"Failed to create service for {key}. WSDL: {wsdl_url}. Error: {e}")

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
    SO_ITEM: Annotated[List[SOItem], BeforeValidator(ensure_list_validator)] = Field(..., description="Items")
) -> str:
    """Create Sales Order (ZBAPI_SALESORDER_CREATE)"""
    try:
        service = get_service_proxy("SO")

        items = [x.model_dump(exclude_none=True) for x in SO_ITEM]
        res = service.ZBAPI_SALESORDER_CREATE(
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
    PR_ITEMS: Annotated[List[PRItem], BeforeValidator(ensure_list_validator)] = Field(..., description="PR Items"),
    LGORT: Optional[str] = Field(None, description="Storage Loc")
) -> str:
    """Create STO PO from PR (ZSD_STO_CREATE)"""
    try:
        service = get_service_proxy("STO")
        pr_payload = [{'ITEM_NO': item.ITEM_NO} for item in PR_ITEMS]
        res = service.ZSD_STO_CREATE(
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
    PO_ITEM: Annotated[List[DNItem], BeforeValidator(ensure_list_validator)] = Field(..., description="Items"),
    DUE_DATE: Optional[str] = Field(None, description="Due Date")
) -> str:
    """Create Delivery (ZWS_BAPI_OUTB_DELIVERY_CREATE)"""
    try:
        service = get_service_proxy("DN")
        items = [x.model_dump() for x in PO_ITEM]

        if hasattr(service, 'ZBAPI_OUTB_DELIVERY_CREATE_STO'):
             res = service.ZBAPI_OUTB_DELIVERY_CREATE_STO(
                SHIP_POINT=SHIP_POINT, PO_ITEM={'item': items}, DUE_DATE=DUE_DATE
            )
        else:
            res = service.ZWS_BAPI_OUTB_DELIVERY_CREATE(
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
        service = get_service_proxy("MAT")
        res = service.ZWS_BAPI_MATERIAL_SAVEDATA(
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
        service = get_service_proxy("SRC")
        res = service.ZSD_SOURCE_LIST_MAINTAIN(
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
        service = get_service_proxy("INF")
        res = service.ZWS_INFO_RECORD_MAINTAIN(
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
    mcp.run()