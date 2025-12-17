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
from mcp.server.fastmcp import FastMCP
from zeep import Client, Settings
from zeep.transports import Transport
from pydantic import BaseModel, Field
from typing import List, Optional

# ==============================================================================
# 1. 設定區 (Configuration) - 這是控制台！
# ==============================================================================
# 您的 SAP 主機位置
SAP_HOST = "vhivcqasci.sap.inventec.com:44300"
CLIENT = "100" # SAP Client ID

# Helper: 自動組裝 SAP WSDL URL
# 規則: https://<HOST>/sap/bc/srt/rfc/sap/<FUNC>/<CLIENT>/<FUNC>/<BINDING>?wsdl
def make_sap_url(func_name: str) -> str:
    func = func_name.lower()
    return f"https://{SAP_HOST}/sap/bc/srt/rfc/sap/{func}/{CLIENT}/{func}/{func}?wsdl"

# --- [API 網址定義] (如果猜錯名稱，請改這裡！) ---
URL_SO = make_sap_url("ZWS_BAPI_SALESORDER_CREATE")   # 1. Create SO (已知)
URL_PO = make_sap_url("ZSD_PR_TO_PO")                 # 2. Create PO (已知)
URL_DN = make_sap_url("ZSD_CREATE_DN")                # 3. Create DN (推測: 交貨單通常在 SD 模組)
URL_MAT = make_sap_url("ZMM_MATERIAL_GET_DETAIL")     # 4. Material View (推測: 讀取物料詳情)
URL_SRC = make_sap_url("ZMM_MAINTAIN_SOURCE_LIST")    # 5. Source List (推測: 維護貨源清單)
URL_INF = make_sap_url("ZMM_MAINTAIN_INFO_RECORD")    # 6. Info Record (推測: 維護資訊記錄)

# ==============================================================================
# 2. 核心功能 (Setup)
# ==============================================================================
mcp = FastMCP("SAP All-in-One Service")

def get_client(wsdl_url: str):
    """建立 SAP 連線 Client"""
    SAP_USER = os.environ.get("SAP_USER")
    SAP_PASSWORD = os.environ.get("SAP_PASSWORD")

    if not SAP_USER or not SAP_PASSWORD:
        raise ValueError("請確認環境變數 SAP_USER 和 SAP_PASSWORD 已設定")

    session = requests.Session()
    session.auth = (SAP_USER, SAP_PASSWORD)
    session.verify = False # 略過 SSL 驗證 (內部主機常用)

    transport = Transport(session=session)
    settings = Settings(strict=False, xml_huge_tree=True)

    # 直接連網址抓 WSDL
    try:
        return Client(wsdl=wsdl_url, transport=transport, settings=settings)
    except Exception as e:
        raise ConnectionError(f"無法連線到 SAP WSDL: {wsdl_url}. 錯誤: {e}")

# ==============================================================================
# 3. 工具定義 (Tools)
# ==============================================================================

# --- [1] Create Sales Order (SO) ---
class SOItem(BaseModel):
    MATERIAL: str
    QTY: float
    UNIT: str
    PLANT: str
    DELIVERY_DATE: str

@mcp.tool()
def create_sales_order(
    ORDER_TYPE: str, SALES_ORG: str, SOLD_TO_PARTY: str, IT_SO_ITEM: List[SOItem],
    SALES_CHANNEL: str = "01", SALES_DIVISION: str = "01"
) -> str:
    """[SO] Create Sales Order"""
    try:
        client = get_client(URL_SO)
        items = [item.model_dump() for item in IT_SO_ITEM]
        res = client.service.ZBAPI_SALESORDER_CREATE(
            ORDER_TYPE=ORDER_TYPE, SALES_ORG=SALES_ORG,
            SALES_CHANNEL=SALES_CHANNEL, SALES_DIVISION=SALES_DIVISION,
            SOLD_TO_PARTY=SOLD_TO_PARTY, IT_SO_ITEM={'item': items}
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (SO): {str(e)}"

# --- [2] Create Purchase Order (PO) ---
class PRItem(BaseModel):
    ITEM_NO: str = Field(..., description="PR Item Number e.g. '00010'")

@mcp.tool()
def create_purchase_order(
    PR_NUMBER: str, PR_ITEMS: List[PRItem], VENDOR: str,
    PUR_ORG: str, PUR_PLANT: str, PUR_GROUP: str, DOC_TYPE: str = "NB"
) -> str:
    """[PO] Create PO from PR (ZSD_PR_TO_PO)"""
    try:
        client = get_client(URL_PO)
        pr_items = [{'ITEM_NO': x.ITEM_NO} for x in PR_ITEMS]

        # 呼叫 ZSD_PR_TO_PO (請確認 API.csv 裡的 Function 名稱是否完全一致)
        res = client.service.ZSD_PR_TO_PO(
            PR_NUMBER=PR_NUMBER, PR_ITEM={'item': pr_items},
            VENDOR=VENDOR, PUR_ORG=PUR_ORG, PUR_PLANT=PUR_PLANT,
            PUR_GROUP=PUR_GROUP, DOC_TYPE=DOC_TYPE
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (PO): {str(e)}"

# --- [3] Create Delivery Note (DN) ---
@mcp.tool()
def create_outbound_delivery(
    REF_SO_NO: str = Field(..., description="Sales Order Number"),
    SHIPPING_POINT: str = Field(..., description="Shipping Point (e.g. 1000)"),
    DUE_DATE: str = Field(..., description="YYYY-MM-DD")
) -> str:
    """[DN] Create Outbound Delivery"""
    try:
        client = get_client(URL_DN)
        # 假設是標準 BAPI 參數，若是客製 ZSD_CREATE_DN 請依實際參數調整
        res = client.service.ZSD_CREATE_DN(
            SALES_ORDER=REF_SO_NO,
            SHIPPING_POINT=SHIPPING_POINT,
            DUE_DATE=DUE_DATE
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (DN): {str(e)}"

# --- [4] Material View ---
@mcp.tool()
def get_material_info(
    MATERIAL: str, PLANT: Optional[str] = None
) -> str:
    """[Material] Get Material Details"""
    try:
        client = get_client(URL_MAT)
        res = client.service.ZMM_MATERIAL_GET_DETAIL(
            MATERIAL=MATERIAL, PLANT=PLANT
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (Material): {str(e)}"

# --- [5] Maintain Source List ---
class SourceItem(BaseModel):
    VENDOR: str
    VALID_FROM: str
    VALID_TO: str
    PPLANT: str

@mcp.tool()
def maintain_source_list(
    MATERIAL: str, RECORDS: List[SourceItem]
) -> str:
    """[Source List] Maintain Purchase Source List"""
    try:
        client = get_client(URL_SRC)
        items = [x.model_dump() for x in RECORDS]
        res = client.service.ZMM_MAINTAIN_SOURCE_LIST(
            MATERIAL=MATERIAL, SOURCE_DATA={'item': items}
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (Source List): {str(e)}"

# --- [6] Maintain Info Record ---
@mcp.tool()
def maintain_info_record(
    VENDOR: str, MATERIAL: str, PURCH_ORG: str,
    PLANT: str, NET_PRICE: float
) -> str:
    """[Info Record] Maintain Info Record"""
    try:
        client = get_client(URL_INF)
        res = client.service.ZMM_MAINTAIN_INFO_RECORD(
            VENDOR=VENDOR, MATERIAL=MATERIAL,
            PURCH_ORG=PURCH_ORG, PLANT=PLANT, NET_PRICE=NET_PRICE
        )
        return f"Result: {res}"
    except Exception as e:
        return f"Error (Info Record): {str(e)}"

# ==============================================================================
# 4. 啟動 (Stdio Mode)
# ==============================================================================
if __name__ == "__main__":
    mcp.run()