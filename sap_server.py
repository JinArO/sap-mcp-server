# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]",
#     "requests",
#     "pydantic>=2.0",
#     "xmltodict",
# ]
# ///

import os
import requests
import xmltodict
from typing import List, Optional
from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

# ==============================================================================
# 設定 (Configuration)
# ==============================================================================
class SAPConfig:
    SERVICES = {
        "SO": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_salesorder_create/100/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZWS_BAPI_SALESORDER_CREATE:ZBAPI_SALESORDER_CREATERequest"'
        },
        "STO": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zsd_sto_create/100/zsd_sto_create_svr/zsd_sto_create_binding",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZSD_STO_CREATE:ZSD_STO_CREATERequest"'
        },
        "DN": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_outb_delivery_create/100/zws_bapi_outb_delivery_create/bind_dn_create",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZWS_BAPI_OUTB_DELIVERY_CREATE_STO:ZBAPI_OUTB_DELIVERY_CREATE_STORequest"'
        },
        "MAT": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_material_savedata/100/zws_bapi_material_savedata/bind_material",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZWS_BAPI_MATERIAL_SAVEDATA:ZBAPI_MATERIAL_SAVEDATARequest"'
        },
        "SRC": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zsd_source_list_maintain/100/zsd_source_list_maintain_svr/zsd_source_list_maintain_binding",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZSD_SOURCE_LIST_MAINTAIN:ZSD_SOURCE_LIST_MAINTAINRequest"'
        },
        "INF": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_info_record_maintain/100/zws_info_record_maintain_svr/zws_info_record_maintain_binding",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZWS_INFO_RECORD_MAINTAIN:ZSD_INFO_RECORD_MAINTAINRequest"'
        },
        "QTY": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zsd_kitting_flow_change/100/zsd_kitting_flow_change_svr/zsd_kitting_flow_change_bind",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZSD_KITTING_FLOW_CHANGE:ZSD_KITTING_FLOW_CHANGERequest"'
        },
        "STATUS": {
            "url": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/wsdl/flv_10002A111AD1/bndg_url/sap/bc/srt/rfc/sap/zai_flow_status/100/zai_flow_status_svr/zai_flow_status_svr_bind?sap-client=100",
            "action": '"urn:sap-com:document:sap:rfc:functions:ZAI_FLOW_STATUS:ZAI_FLOW_STATUSRequest"'
        }
    }

# ==============================================================================
# 工作階段管理 (Session Management)
# ==============================================================================
class SessionCredentialStore:
    """儲存不同 MCP 工作階段 (Session) 的 SAP 憑證"""
    def __init__(self):
        # 使用字典儲存：session_id -> {user, password}
        self._credentials = {}

        # 如果有環境變數，將其作為預設憑證
        default_user = os.environ.get("SAP_USER")
        default_password = os.environ.get("SAP_PASSWORD")
        if default_user and default_password:
            self._default_credentials = {
                "user": default_user,
                "password": default_password
            }
        else:
            self._default_credentials = None

    def set_credentials(self, session_id: str, user: str, password: str):
        """為指定工作階段設定憑證"""
        self._credentials[session_id] = {
            "user": user,
            "password": password
        }

    def get_credentials(self, session_id: str):
        """獲取指定工作階段的憑證"""
        # 優先使用該工作階段特定的憑證
        if session_id in self._credentials:
            return self._credentials[session_id]

        # 如果沒有，嘗試使用預設憑證
        if self._default_credentials:
            return self._default_credentials

        raise ValueError(f"未找到工作階段 {session_id} 的憑證，且未設定預設憑證。請先呼叫 set_sap_credentials 設定憑證。")

    def has_credentials(self, session_id: str) -> bool:
        """檢查是否有憑證"""
        return session_id in self._credentials or self._default_credentials is not None

    def clear_credentials(self, session_id: str):
        """清除指定工作階段的憑證"""
        if session_id in self._credentials:
            del self._credentials[session_id]

# 全域憑證儲存區
credential_store = SessionCredentialStore()

# ==============================================================================
# 核心客戶端 (Core Client)
# ==============================================================================
mcp = FastMCP("SAP Automation Agent")

class SAPClient:
    def __init__(self, key: str, session_id: str):
        cfg = SAPConfig.SERVICES[key]
        self.url = cfg["url"]
        self.action = cfg["action"]

        # 從憑證儲存區中獲取此工作階段的憑證
        creds = credential_store.get_credentials(session_id)
        self.user = creds["user"]
        self.password = creds["password"]

    def post_soap(self, body_content: str) -> str:
        # 標準 SOAP Envelope (不含 XML 宣告)
        envelope = f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:sap-com:document:sap:rfc:functions"><soapenv:Header/><soapenv:Body>{body_content}</soapenv:Body></soapenv:Envelope>'

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'Accept': 'text/xml',
            'SOAPAction': self.action,
        }

        try:
            response = requests.post(
                self.url,
                data=envelope.encode('utf-8'),
                auth=(self.user, self.password),
                headers=headers,
                verify=False
            )

            if response.status_code == 200:
                try:
                    parsed = xmltodict.parse(response.text)
                    # 嘗試提取 Body 內容
                    env = parsed.get('soap-env:Envelope') or parsed.get('soapenv:Envelope') or parsed.get('SOAP-ENV:Envelope')
                    if env:
                        body = env.get('soap-env:Body') or env.get('soapenv:Body') or env.get('SOAP-ENV:Body')
                        return str(body) if body else response.text
                    return response.text
                except:
                    return response.text
            else:
                return f"HTTP 錯誤 {response.status_code}: {response.text}"

        except Exception as e:
            return f"連線錯誤: {str(e)}"

# ==============================================================================
# 工作階段管理工具 (Session Management Tools)
# ==============================================================================

@mcp.tool()
def set_sap_credentials(
    username: str,
    password: str,
    ctx: Context = None
) -> str:
    """設定目前工作階段的 SAP 憑證

    參數:
        username: SAP 使用者名稱
        password: SAP 密碼

    回傳:
        設定結果訊息
    """
    if ctx and hasattr(ctx, 'request_context'):
        # 使用 request_id 作為 session 識別
        session_id = getattr(ctx.request_context, 'request_id', 'default')
        # 更好的做法是使用 session 資訊，但這裡用 client_params 模擬
        if hasattr(ctx, 'session') and hasattr(ctx.session, 'client_params'):
            client_info = str(ctx.session.client_params)
            session_id = hash(client_info) if client_info else 'default'
        session_id = str(session_id)
    else:
        session_id = 'default'

    credential_store.set_credentials(session_id, username, password)
    return f"已為工作階段 {session_id} 設定 SAP 憑證（使用者：{username}）"

@mcp.tool()
def check_session_credentials(ctx: Context = None) -> str:
    """檢查目前工作階段是否已設定憑證

    回傳:
        憑證狀態資訊
    """
    if ctx and hasattr(ctx, 'request_context'):
        session_id = getattr(ctx.request_context, 'request_id', 'default')
        if hasattr(ctx, 'session') and hasattr(ctx.session, 'client_params'):
            client_info = str(ctx.session.client_params)
            session_id = hash(client_info) if client_info else 'default'
        session_id = str(session_id)
    else:
        session_id = 'default'

    if credential_store.has_credentials(session_id):
        creds = credential_store.get_credentials(session_id)
        return f"工作階段 {session_id} 已設定憑證（使用者：{creds['user']}）"
    else:
        return f"工作階段 {session_id} 未設定憑證"

def _get_session_id(ctx: Context = None) -> str:
    """從 Context 中提取 session ID"""
    if ctx and hasattr(ctx, 'request_context'):
        session_id = getattr(ctx.request_context, 'request_id', 'default')
        if hasattr(ctx, 'session') and hasattr(ctx.session, 'client_params'):
            client_info = str(ctx.session.client_params)
            session_id = hash(client_info) if client_info else 'default'
        return str(session_id)
    return 'default'

# ==============================================================================
# SAP 操作工具 (SAP Operation Tools)
# ==============================================================================

@mcp.tool()
def create_sales_order(
    CUST_PO: str,
    CUST_PO_DATE: str,
    MATERIAL: str,
    QTY: float,
    UUID: str = "",
    ORDER_TYPE: str = "ZIES",
    SALES_ORG: str = "TW01",
    SALES_CHANNEL: str = "03",
    SALES_DIVISION: str = "01",
    SOLD_TO_PARTY: str = "HRCTO-IMX",
    SHIP_TO_PARTY: str = "HRCTO-MX",
    PLANT: str = "TP01",
    SHIPPING_POINT: str = "TW01",
    ctx: Context = None
) -> str:
    """步驟 1: 建立銷售訂單 (Sales Order)"""

    # 獲取目前工作階段的 session ID
    session_id = _get_session_id(ctx)

    # 強制使用預設值以防止「缺少必要的抬頭欄位」錯誤
    order_type_val = ORDER_TYPE if ORDER_TYPE else "ZIES"
    sales_org_val = SALES_ORG if SALES_ORG else "TW01"
    sales_channel_val = SALES_CHANNEL if SALES_CHANNEL else "03"
    sales_division_val = SALES_DIVISION if SALES_DIVISION else "01"
    sold_to_val = SOLD_TO_PARTY if SOLD_TO_PARTY else "HRCTO-IMX"
    ship_to_val = SHIP_TO_PARTY if SHIP_TO_PARTY else "HRCTO-MX"
    plant_val = PLANT if PLANT else "TP01"
    shipping_pt_val = SHIPPING_POINT if SHIPPING_POINT else "TW01"

    cust_po_val = CUST_PO if CUST_PO else "TEST_PO"
    cust_po_date_val = CUST_PO_DATE if CUST_PO_DATE else "2025-01-01"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    # 嚴格遵循文件結構：UUID -> CUST -> ITEM TABLE -> HEADER FIELDS
    xml_body = f'<urn:ZBAPI_SALESORDER_CREATE>{uuid_tag}<CUST_PO>{cust_po_val}</CUST_PO><CUST_PO_DATE>{cust_po_date_val}</CUST_PO_DATE><IT_SO_ITEM><item><MATERIAL_NO>000010</MATERIAL_NO><MATERIAL>{MATERIAL}</MATERIAL><UNIT>PCE</UNIT><QTY>{QTY}</QTY><PLANT>{plant_val}</PLANT><SHIPPING_POINT>{shipping_pt_val}</SHIPPING_POINT><DELIVERY_DATE>{cust_po_date_val}</DELIVERY_DATE></item></IT_SO_ITEM><ORDER_TYPE>{order_type_val}</ORDER_TYPE><SALES_CHANNEL>{sales_channel_val}</SALES_CHANNEL><SALES_DIVISION>{sales_division_val}</SALES_DIVISION><SALES_ORG>{sales_org_val}</SALES_ORG><SHIP_TO_PARTY>{ship_to_val}</SHIP_TO_PARTY><SOLD_TO_PARTY>{sold_to_val}</SOLD_TO_PARTY></urn:ZBAPI_SALESORDER_CREATE>'

    return SAPClient("SO", session_id).post_soap(xml_body)

@mcp.tool()
def create_sto_po(
    PR_NUMBER: str,
    PR_ITEM: str,
    UUID: str = "",
    PUR_GROUP: str = "999",
    PUR_ORG: str = "TW10",
    PUR_PLANT: str = "TP01",
    VENDOR: str = "ICC-CP60",
    DOC_TYPE: str = "NB",
    ctx: Context = None
) -> str:
    """步驟 2: 建立 STO 採購訂單 (PO)"""

    session_id = _get_session_id(ctx)

    pur_group_val = PUR_GROUP if PUR_GROUP else "999"
    pur_org_val = PUR_ORG if PUR_ORG else "TW10"
    pur_plant_val = PUR_PLANT if PUR_PLANT else "TP01"
    vendor_val = VENDOR if VENDOR else "ICC-CP60"
    doc_type_val = DOC_TYPE if DOC_TYPE else "NB"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_STO_CREATE>{uuid_tag}<DOC_TYPE>{doc_type_val}</DOC_TYPE><LGORT/><PR_NUMBER>{PR_NUMBER}</PR_NUMBER><PUR_GROUP>{pur_group_val}</PUR_GROUP><PUR_ITEM><item><BNFPO>{PR_ITEM}</BNFPO></item></PUR_ITEM><PUR_ORG>{pur_org_val}</PUR_ORG><PUR_PLANT>{pur_plant_val}</PUR_PLANT><VENDOR>{vendor_val}</VENDOR></urn:ZSD_STO_CREATE>'

    return SAPClient("STO", session_id).post_soap(xml_body)

@mcp.tool()
def create_outbound_delivery(
    PO_NUMBER: str,
    ITEM_NO: str,
    QUANTITY: float,
    UUID: str = "",
    ctx: Context = None
) -> str:
    """步驟 3: 建立外向交貨單 (Outbound Delivery)"""

    session_id = _get_session_id(ctx)

    ship_point_val = "CN60"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>{uuid_tag}<PO_ITEM><item><REF_DOC>{PO_NUMBER}</REF_DOC><REF_ITEM>{ITEM_NO}</REF_ITEM><DLV_QTY>{QUANTITY}</DLV_QTY><SALES_UNIT>EA</SALES_UNIT></item></PO_ITEM><SHIP_POINT>{ship_point_val}</SHIP_POINT></urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>'

    return SAPClient("DN", session_id).post_soap(xml_body)

@mcp.tool()
def maintain_info_record(
    MATERIAL: str,
    UUID: str = "",
    PRICE: str = "999",
    VENDOR: str = "ICC-CP60",
    PLANT: str = "TP01",
    PUR_ORG: str = "TW10",
    ctx: Context = None
) -> str:
    """補救操作: 維護資訊記錄 (Info Record)"""

    session_id = _get_session_id(ctx)

    price_val = PRICE if PRICE else "999"
    vendor_val = VENDOR if VENDOR else "ICC-CP60"
    plant_val = PLANT if PLANT else "TP01"
    pur_org_val = PUR_ORG if PUR_ORG else "TW10"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_INFO_RECORD_MAINTAIN>{uuid_tag}<CURRENCY>USD</CURRENCY><MATERIAL>{MATERIAL}</MATERIAL><PLANT>{plant_val}</PLANT><PRICE>{price_val}</PRICE><PRICE_UNIT>1</PRICE_UNIT><PUR_ORG>{pur_org_val}</PUR_ORG><VENDOR>{vendor_val}</VENDOR></urn:ZSD_INFO_RECORD_MAINTAIN>'

    return SAPClient("INF", session_id).post_soap(xml_body)

@mcp.tool()
def maintain_sales_view(
    MATERIAL: str,
    SALES_ORG: str,
    DISTR_CHAN: str,
    UUID: str = "",
    PLANT: str = "TP01",
    DELYG_PLNT: str = "TP01",
    ctx: Context = None
) -> str:
    """補救操作: 維護銷售視圖 (Sales View)"""

    session_id = _get_session_id(ctx)

    # 邏輯參照 Word 文件
    plant_val = PLANT
    delyg_plnt_val = DELYG_PLNT

    if SALES_ORG == "CN60" and DISTR_CHAN == "03":
        plant_val = "CP60"
        delyg_plnt_val = "CP60"
    elif SALES_ORG == "TW01" and DISTR_CHAN == "03":
        plant_val = "TP01"
        delyg_plnt_val = "TP01"

    plant_val = plant_val if plant_val else "TP01"
    delyg_plnt_val = delyg_plnt_val if delyg_plnt_val else "TP01"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_MATERIAL_SAVEDATA>{uuid_tag}<HEADDATA><MATERIAL>{MATERIAL}</MATERIAL><SALES_VIEW>X</SALES_VIEW><STORAGE_VIEW></STORAGE_VIEW><WAREHOUSE_VIEW></WAREHOUSE_VIEW></HEADDATA><PLANTDATA><PLANT>{plant_val}</PLANT></PLANTDATA><SALESDATA><SALES_ORG>{SALES_ORG}</SALES_ORG><DISTR_CHAN>{DISTR_CHAN}</DISTR_CHAN><DELYG_PLNT>{delyg_plnt_val}</DELYG_PLNT></SALESDATA></urn:ZBAPI_MATERIAL_SAVEDATA>'

    return SAPClient("MAT", session_id).post_soap(xml_body)

@mcp.tool()
def maintain_warehouse_view(
    MATERIAL: str,
    UUID: str = "",
    WHSE_NO: str = "WH1",
    ctx: Context = None
) -> str:
    """補救操作: 維護倉庫視圖 (Warehouse View)"""

    session_id = _get_session_id(ctx)

    whse_no_val = WHSE_NO if WHSE_NO else "WH1"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_MATERIAL_SAVEDATA>{uuid_tag}<HEADDATA><MATERIAL>{MATERIAL}</MATERIAL><SALES_VIEW></SALES_VIEW><STORAGE_VIEW></STORAGE_VIEW><WAREHOUSE_VIEW>X</WAREHOUSE_VIEW></HEADDATA><WAREHOUSENUMBERDATA><WHSE_NO>{whse_no_val}</WHSE_NO></WAREHOUSENUMBERDATA></urn:ZBAPI_MATERIAL_SAVEDATA>'

    return SAPClient("MAT", session_id).post_soap(xml_body)

@mcp.tool()
def maintain_source_list(
    MATERIAL: str,
    VALID_FROM: str,
    UUID: str = "",
    PLANT: str = "TP01",
    VENDOR: str = "ICC-CP60",
    ctx: Context = None
) -> str:
    """補救操作: 維護貨源清單 (Source List)"""

    session_id = _get_session_id(ctx)

    plant_val = PLANT if PLANT else "TP01"
    vendor_val = VENDOR if VENDOR else "ICC-CP60"
    valid_from_val = VALID_FROM if VALID_FROM else "2025-01-01"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_SOURCE_LIST_MAINTAIN>{uuid_tag}<MATERIAL>{MATERIAL}</MATERIAL><PLANT>{plant_val}</PLANT><VENDOR>{vendor_val}</VENDOR><VALID_FROM>{valid_from_val}</VALID_FROM><VALID_TO>9999-12-31</VALID_TO></urn:ZSD_SOURCE_LIST_MAINTAIN>'

    return SAPClient("SRC", session_id).post_soap(xml_body)

@mcp.tool()
def change_kitting_qty(
    KITTING_PO: str,
    PO_ITEM: str,
    QUANTITY: float,
    UUID: str = "",
    ctx: Context = None
) -> str:
    """補救操作: 更改 Kitting PO 數量"""

    session_id = _get_session_id(ctx)

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_KITTING_FLOW_CHANGE>{uuid_tag}<KITTING_PO>{KITTING_PO}</KITTING_PO><PR_ITEM><item><EBELP>{PO_ITEM}</EBELP><MENGE>{QUANTITY}</MENGE></item></PR_ITEM></urn:ZSD_KITTING_FLOW_CHANGE>'

    return SAPClient("QTY", session_id).post_soap(xml_body)

@mcp.tool()
def check_kitting_status(
    BATCH_ID: str,
    ctx: Context = None
) -> str:
    """查詢 Kitting 流程狀態"""
    
    session_id = _get_session_id(ctx)

    # Ensure BATCH_ID is 16 chars, zero-padded to match SAP format
    batch_id_val = BATCH_ID.strip().zfill(16)

    xml_body = f'<urn:ZAI_FLOW_STATUS><BATCH_ID><item><BATCH_ID>{batch_id_val}</BATCH_ID></item></BATCH_ID></urn:ZAI_FLOW_STATUS>'
    
    return SAPClient("STATUS", session_id).post_soap(xml_body)

if __name__ == "__main__":
    mcp.run()