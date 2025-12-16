import os
import requests
import uvicorn
from mcp.server.fastmcp import FastMCP
from zeep import Client, Settings
from zeep.transports import Transport
from pydantic import BaseModel, Field
from typing import List, Optional

# 1. 初始化 MCP Server
mcp = FastMCP("SAP Sales Order BAPI")

# 2. 設定 (建議使用環境變數，或在此暫時填入測試)
SAP_USER = os.environ.get("SAP_USER", "您的帳號")
SAP_PASSWORD = os.environ.get("SAP_PASSWORD", "您的密碼")
WSDL_FILENAME = "zws_bapi_salesorder_create_binding.xml"
# 取得 WSDL 的絕對路徑
WSDL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), WSDL_FILENAME))

# 3. 定義資料結構 (Pydantic Model)
class SalesOrderItem(BaseModel):
    MATERIAL: str = Field(..., description="Material Number (e.g. 'MZ-FG-M100')")
    QTY: float = Field(..., description="Quantity")
    UNIT: str = Field(..., description="Unit (e.g. 'PC')")
    PLANT: str = Field(..., description="Plant Code (e.g. '1000')")
    DELIVERY_DATE: str = Field(..., description="YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$")
    MATERIAL_NO: Optional[str] = Field(None, description="Numeric Material ID")
    CUST_MATERIAL: Optional[str] = Field(None, description="Customer Material Number")
    SHIPPING_POINT: Optional[str] = Field(None, description="Shipping Point")

# 4. 定義工具 (Tool)
@mcp.tool()
def create_sales_order(
    ORDER_TYPE: str = Field(..., description="Order Type (e.g. 'OR')"),
    SALES_ORG: str = Field(..., description="Sales Org (e.g. '1000')"),
    SOLD_TO_PARTY: str = Field(..., description="Customer No."),
    IT_SO_ITEM: List[SalesOrderItem] = Field(..., description="Items"),
    CUST_PO: str = Field("", description="PO Number"),
    CUST_PO_DATE: Optional[str] = Field(None, description="PO Date YYYY-MM-DD"),
    SALES_CHANNEL: str = Field("01", description="Dist. Channel"),
    SALES_DIVISION: str = Field("01", description="Division"),
    SHIP_TO_PARTY: Optional[str] = Field(None, description="Ship-To Party")
) -> str:
    """Create a SAP Sales Order via ZBAPI_SALESORDER_CREATE"""
    
    if "您的帳號" in SAP_USER:
        return "錯誤：請設定 SAP_USER 環境變數或修改程式碼中的帳號。"

    session = requests.Session()
    session.auth = (SAP_USER, SAP_PASSWORD)
    session.verify = False # 忽略內網 SSL 憑證警告
    
    settings = Settings(strict=False, xml_huge_tree=True)

    try:
        transport = Transport(session=session)
        client = Client(wsdl=WSDL_PATH, transport=transport, settings=settings)
        
        # 建立 Service Proxy (網址來自 WSDL，若需覆寫請在此修改)
        service = client.create_service(
            '{urn:sap-com:document:sap:rfc:functions}ZWS_BAPI_SALESORDER_CREATE_BINDING',
            'https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_salesorder_create/100/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding'
        )

        items_payload = [item.model_dump(exclude_none=True) for item in IT_SO_ITEM]

        response = service.ZBAPI_SALESORDER_CREATE(
            ORDER_TYPE=ORDER_TYPE,
            SALES_ORG=SALES_ORG,
            SALES_CHANNEL=SALES_CHANNEL,
            SALES_DIVISION=SALES_DIVISION,
            SOLD_TO_PARTY=SOLD_TO_PARTY,
            SHIP_TO_PARTY=SHIP_TO_PARTY if SHIP_TO_PARTY else SOLD_TO_PARTY,
            CUST_PO=CUST_PO,
            CUST_PO_DATE=CUST_PO_DATE,
            IT_SO_ITEM={'item': items_payload}
        )

        sales_no = response.get('SALES_NO')
        detail_msg = response.get('DETAIL_MESSAGE', {}).get('item', [])
        
        # 簡單格式化回傳
        msg_str = " | ".join([f"{m.get('TYPE')}: {m.get('MESSAGE')}" for m in detail_msg if m.get('TYPE') in ['E', 'A', 'S']])
        if sales_no:
             return f"成功！訂單號碼: {sales_no}\n訊息: {msg_str}"
        return f"失敗或無單號。\n訊息: {msg_str}"

    except Exception as e:
        return f"系統錯誤: {str(e)}"

# 5. 啟動 Web Server (SSE 模式)
if __name__ == "__main__":
    print("正在啟動 SAP MCP Server (SSE 模式)...")
    print("網址: http://localhost:8000/sse")
    # 這行指令會啟動網頁伺服器
    mcp.run(transport="sse")