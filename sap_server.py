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
from typing import List, Optional, Union, Any, Dict
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# ==============================================================================
# 1. 設定區 (Templates)
# ==============================================================================
class SAPConfig:
    HOST = "vhivcqasci.sap.inventec.com:44300"
    # 根據文件，不需要 Client 變數，因為 URL 已經包含 /100/

    # https://www.merriam-webster.com/dictionary/define
    URLS = {
        "SO": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_salesorder_create/100/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding",
        "STO": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zsd_sto_create/100/zsd_sto_create_svr/zsd_sto_create_binding",
        "DN": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_outb_delivery_create/100/zws_bapi_outb_delivery_create/bind_dn_create",
        "MAT": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_material_savedata/100/zws_bapi_material_savedata/bind_material",
        "SRC": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zsd_source_list_maintain/100/zsd_source_list_maintain_svr/zsd_source_list_maintain_binding",
        "INF": "https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_info_record_maintain/100/zws_info_record_maintain_svr/zws_info_record_maintain_binding"
    }

# ==============================================================================
# 2. 核心連線功能 (Raw SOAP Caller)
# ==============================================================================
mcp = FastMCP("SAP Automation Agent")

class SAPClient:
    def __init__(self, key: str):
        self.url = SAPConfig.URLS[key]
        self.user = os.environ.get("SAP_USER")
        self.password = os.environ.get("SAP_PASSWORD")
        if not self.user or not self.password:
            raise ValueError("Environment variables SAP_USER / SAP_PASSWORD not set.")

    def post_soap(self, body_content: str, action: str = "") -> str:
        """發送標準 SOAP Envelope"""
        envelope = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:sap-com:document:sap:rfc:functions"><soapenv:Header/><soapenv:Body>{body_content}</soapenv:Body></soapenv:Envelope>"""

        headers = {
            'Content-Type': 'text/xml',
            'Accept': 'text/xml',
            'Authorization': f'Basic REMOVED_IN_LOG', # 實際發送時 requests 會處理 auth
        }

        try:
            response = requests.post(
                self.url,
                data=envelope.encode('utf-8'),
                auth=(self.user, self.password),
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                verify=False
            )

            # 解析回傳結果
            if response.status_code == 200:
                try:
                    # 嘗試轉成 JSON 格式回傳，方便閱讀
                    parsed = xmltodict.parse(response.text)
                    body = parsed.get('soap-env:Envelope', {}).get('soap-env:Body', {})
                    return str(body) # 回傳 Dictionary 字串
                except:
                    return response.text # 解析失敗就回傳原始 XML
            else:
                return f"HTTP Error {response.status_code}: {response.text}"

        except Exception as e:
            return f"Connection Error: {str(e)}"

# ==============================================================================
# 3. 工具定義 (Tools) - 依照文件模板實作
# ==============================================================================

# --- [1] Create Sales Order (SO) ---
@mcp.tool()
def create_sales_order(
    CUST_PO: str,
    CUST_PO_DATE: str,
    MATERIAL: str,
    QTY: float,
    UUID: str = "",
    # 以下參數提供預設值
    ORDER_TYPE: str = "ZIES",
    SALES_ORG: str = "TW01",
    SALES_CHANNEL: str = "03",
    SALES_DIVISION: str = "01",
    SOLD_TO_PARTY: str = "HRCTO-IMX",
    SHIP_TO_PARTY: str = "HRCTO-MX",
    PLANT: str = "TP01",
    SHIPPING_POINT: str = "TW01"
) -> str:
    """Step 1: Create Sales Order (ZBAPI_SALESORDER_CREATE)"""
    # 注意: 文件中 Item 包在 <IT_SO_ITEM><item>...</item></IT_SO_ITEM>
    xml_body = f"""
    <urn:ZBAPI_SALESORDER_CREATE>
        <UUID>{UUID}</UUID>
        <CUST_PO>{CUST_PO}</CUST_PO>
        <CUST_PO_DATE>{CUST_PO_DATE}</CUST_PO_DATE>
        <IT_SO_ITEM>
            <item>
                <MATERIAL_NO>000010</MATERIAL_NO>
                <MATERIAL>{MATERIAL}</MATERIAL>
                <UNIT>PCE</UNIT>
                <QTY>{QTY}</QTY>
                <PLANT>{PLANT}</PLANT>
                <SHIPPING_POINT>{SHIPPING_POINT}</SHIPPING_POINT>
                <DELIVERY_DATE>{CUST_PO_DATE}</DELIVERY_DATE>
            </item>
        </IT_SO_ITEM>
        <ORDER_TYPE>{ORDER_TYPE}</ORDER_TYPE>
        <SALES_CHANNEL>{SALES_CHANNEL}</SALES_CHANNEL>
        <SALES_DIVISION>{SALES_DIVISION}</SALES_DIVISION>
        <SALES_ORG>{SALES_ORG}</SALES_ORG>
        <SHIP_TO_PARTY>{SHIP_TO_PARTY}</SHIP_TO_PARTY>
        <SOLD_TO_PARTY>{SOLD_TO_PARTY}</SOLD_TO_PARTY>
    </urn:ZBAPI_SALESORDER_CREATE>
    """
    return SAPClient("SO").post_soap(xml_body)

# --- [2] Create STO (PO) ---
@mcp.tool()
def create_sto_po(
    PR_NUMBER: str,
    PR_ITEM: str, # 這是 PR Item No (文件 Source 72 <BNFPO>)
    UUID: str = "",
    # 預設值
    PUR_GROUP: str = "999",
    PUR_ORG: str = "TW10",
    PUR_PLANT: str = "TP01",
    VENDOR: str = "ICC-CP60",
    DOC_TYPE: str = "NB"
) -> str:
    """Step 2: Create STO PO (ZSD_STO_CREATE)"""
    # 注意: 這裡用 <PUR_ITEM><item><BNFPO>...</BNFPO></item></PUR_ITEM>
    xml_body = f"""
    <urn:ZSD_STO_CREATE>
        <UUID>{UUID}</UUID>
        <DOC_TYPE>{DOC_TYPE}</DOC_TYPE>
        <LGORT/>
        <PR_NUMBER>{PR_NUMBER}</PR_NUMBER>
        <PUR_GROUP>{PUR_GROUP}</PUR_GROUP>
        <PUR_ITEM>
            <item>
                <BNFPO>{PR_ITEM}</BNFPO>
            </item>
        </PUR_ITEM>
        <PUR_ORG>{PUR_ORG}</PUR_ORG>
        <PUR_PLANT>{PUR_PLANT}</PUR_PLANT>
        <VENDOR>{VENDOR}</VENDOR>
    </urn:ZSD_STO_CREATE>
    """
    return SAPClient("STO").post_soap(xml_body)

# --- [3] Create Outbound Delivery (DN) ---
@mcp.tool()
def create_outbound_delivery(
    PO_NUMBER: str,
    ITEM_NO: str,
    QUANTITY: float,
    SHIPPING_POINT: str,
    UUID: str = ""
) -> str:
    """Step 3: Create Outbound Delivery (ZBAPI_OUTB_DELIVERY_CREATE_STO)"""
    # 注意: <PO_ITEM><item><REF_DOC>...
    xml_body = f"""
    <urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>
        <UUID>{UUID}</UUID>
        <PO_ITEM>
            <item>
                <REF_DOC>{PO_NUMBER}</REF_DOC>
                <REF_ITEM>{ITEM_NO}</REF_ITEM>
                <DLV_QTY>{QUANTITY}</DLV_QTY>
                <SALES_UNIT>EA</SALES_UNIT>
            </item>
        </PO_ITEM>
        <SHIP_POINT>{SHIPPING_POINT}</SHIP_POINT>
    </urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>
    """
    return SAPClient("DN").post_soap(xml_body)

# --- [4] Remediation: Info Record ---
@mcp.tool()
def maintain_info_record(
    MATERIAL: str,
    UUID: str = "",
    # 預設補救值
    PRICE: str = "999",
    VENDOR: str = "ICC-CP60",
    PLANT: str = "TP01",
    PUR_ORG: str = "TW10"
) -> str:
    """Remediation: Info Record (ZSD_INFO_RECORD_MAINTAIN)"""
    xml_body = f"""
    <urn:ZSD_INFO_RECORD_MAINTAIN>
        <UUID>{UUID}</UUID>
        <CURRENCY>USD</CURRENCY>
        <MATERIAL>{MATERIAL}</MATERIAL>
        <PLANT>{PLANT}</PLANT>
        <PRICE>{PRICE}</PRICE>
        <PRICE_UNIT>1</PRICE_UNIT>
        <PUR_ORG>{PUR_ORG}</PUR_ORG>
        <VENDOR>{VENDOR}</VENDOR>
    </urn:ZSD_INFO_RECORD_MAINTAIN>
    """
    return SAPClient("INF").post_soap(xml_body)

# --- [5] Remediation: Material View (Sales) ---
@mcp.tool()
def maintain_sales_view(
    MATERIAL: str,
    SALES_ORG: str,
    DISTR_CHAN: str,
    UUID: str = "",
    PLANT: str = "TP01",      # Default based on rule
    DELYG_PLNT: str = "TP01"  # Default based on rule
) -> str:
    """Remediation: Maintain Sales View"""
    # 邏輯判斷: 若 Org=CN60/03 -> Plant=CP60; 若 TW01/03 -> TP01
    if SALES_ORG == "CN60" and DISTR_CHAN == "03":
        PLANT = "CP60"
        DELYG_PLNT = "CP60"
    elif SALES_ORG == "TW01" and DISTR_CHAN == "03":
        PLANT = "TP01"
        DELYG_PLNT = "TP01"

    xml_body = f"""
    <urn:ZBAPI_MATERIAL_SAVEDATA>
        <UUID>{UUID}</UUID>
        <HEADDATA>
            <MATERIAL>{MATERIAL}</MATERIAL>
            <SALES_VIEW>X</SALES_VIEW>
            <STORAGE_VIEW></STORAGE_VIEW>
            <WAREHOUSE_VIEW></WAREHOUSE_VIEW>
        </HEADDATA>
        <PLANTDATA>
            <PLANT>{PLANT}</PLANT>
        </PLANTDATA>
        <SALESDATA>
            <SALES_ORG>{SALES_ORG}</SALES_ORG>
            <DISTR_CHAN>{DISTR_CHAN}</DISTR_CHAN>
            <DELYG_PLNT>{DELYG_PLNT}</DELYG_PLNT>
        </SALESDATA>
    </urn:ZBAPI_MATERIAL_SAVEDATA>
    """
    return SAPClient("MAT").post_soap(xml_body)

# --- [6] Remediation: Material View (Warehouse) ---
@mcp.tool()
def maintain_warehouse_view(
    MATERIAL: str,
    UUID: str = "",
    WHSE_NO: str = "WH1"
) -> str:
    """Remediation: Maintain Warehouse View"""
    xml_body = f"""
    <urn:ZBAPI_MATERIAL_SAVEDATA>
        <UUID>{UUID}</UUID>
        <HEADDATA>
            <MATERIAL>{MATERIAL}</MATERIAL>
            <SALES_VIEW></SALES_VIEW>
            <STORAGE_VIEW></STORAGE_VIEW>
            <WAREHOUSE_VIEW>X</WAREHOUSE_VIEW>
        </HEADDATA>
        <WAREHOUSENUMBERDATA>
            <WHSE_NO>{WHSE_NO}</WHSE_NO>
        </WAREHOUSENUMBERDATA>
    </urn:ZBAPI_MATERIAL_SAVEDATA>
    """
    return SAPClient("MAT").post_soap(xml_body)

# --- [7] Remediation: Source List ---
@mcp.tool()
def maintain_source_list(
    MATERIAL: str,
    VALID_FROM: str, # Format YYYY-MM-DD (e.g. CUST_PO_DATE)
    UUID: str = "",
    PLANT: str = "TP01",
    VENDOR: str = "ICC-CP60"
) -> str:
    """Remediation: Source List (ZSD_SOURCE_LIST_MAINTAIN)"""
    xml_body = f"""
    <urn:ZSD_SOURCE_LIST_MAINTAIN>
        <UUID>{UUID}</UUID>
        <MATERIAL>{MATERIAL}</MATERIAL>
        <PLANT>{PLANT}</PLANT>
        <VENDOR>{VENDOR}</VENDOR>
        <VALID_FROM>{VALID_FROM}</VALID_FROM>
        <VALID_TO>9999-12-31</VALID_TO>
    </urn:ZSD_SOURCE_LIST_MAINTAIN>
    """
    return SAPClient("SRC").post_soap(xml_body)

# ==============================================================================
# 4. 啟動
# ==============================================================================
if __name__ == "__main__":
    mcp.run()