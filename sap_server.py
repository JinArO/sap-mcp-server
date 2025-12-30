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
# 1. 設定區 (Templates & Headers)
# ==============================================================================
class SAPConfig:
    HOST = "vhivcqasci.sap.inventec.com:44300"

    # [API 定義]
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
        }
    }

# ==============================================================================
# 2. 核心連線功能 (Raw SOAP Caller)
# ==============================================================================
mcp = FastMCP("SAP Automation Agent")

class SAPClient:
    def __init__(self, key: str):
        cfg = SAPConfig.SERVICES[key]
        self.url = cfg["url"]
        self.action = cfg["action"]
        self.user = os.environ.get("SAP_USER")
        self.password = os.environ.get("SAP_PASSWORD")
        if not self.user or not self.password:
            raise ValueError("Environment variables SAP_USER / SAP_PASSWORD not set.")

    def post_soap(self, body_content: str) -> str:
        """發送標準 SOAP Envelope"""
        # 嚴格的單行 XML 封裝
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
                    env = parsed.get('soap-env:Envelope') or parsed.get('soapenv:Envelope') or parsed.get('SOAP-ENV:Envelope')
                    if env:
                        body = env.get('soap-env:Body') or env.get('soapenv:Body') or env.get('SOAP-ENV:Body')
                        return str(body) if body else response.text
                    return response.text
                except:
                    return response.text
            else:
                return f"HTTP Error {response.status_code}: {response.text}"

        except Exception as e:
            return f"Connection Error: {str(e)}"

# ==============================================================================
# 3. 工具定義 (Tools)
# ==============================================================================

# --- [1] Create Sales Order (SO) ---
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
    SHIPPING_POINT: str = "TW01"
) -> str:
    [cite_start]"""Step 1: Create Sales Order (ZBAPI_SALESORDER_CREATE) [cite: 38-52]"""

    ORDER_TYPE = ORDER_TYPE or "ZIES"
    SALES_ORG = SALES_ORG or "TW01"
    SALES_CHANNEL = SALES_CHANNEL or "03"
    SALES_DIVISION = SALES_DIVISION or "01"
    SOLD_TO_PARTY = SOLD_TO_PARTY or "HRCTO-IMX"
    SHIP_TO_PARTY = SHIP_TO_PARTY or "HRCTO-MX"
    PLANT = PLANT or "TP01"
    SHIPPING_POINT = SHIPPING_POINT or "TW01"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_SALESORDER_CREATE>{uuid_tag}<CUST_PO>{CUST_PO}</CUST_PO><CUST_PO_DATE>{CUST_PO_DATE}</CUST_PO_DATE><IT_SO_ITEM><item><MATERIAL_NO>000010</MATERIAL_NO><MATERIAL>{MATERIAL}</MATERIAL><UNIT>PCE</UNIT><QTY>{QTY}</QTY><PLANT>{PLANT}</PLANT><SHIPPING_POINT>{SHIPPING_POINT}</SHIPPING_POINT><DELIVERY_DATE>{CUST_PO_DATE}</DELIVERY_DATE></item></IT_SO_ITEM><ORDER_TYPE>{ORDER_TYPE}</ORDER_TYPE><SALES_CHANNEL>{SALES_CHANNEL}</SALES_CHANNEL><SALES_DIVISION>{SALES_DIVISION}</SALES_DIVISION><SALES_ORG>{SALES_ORG}</SALES_ORG><SHIP_TO_PARTY>{SHIP_TO_PARTY}</SHIP_TO_PARTY><SOLD_TO_PARTY>{SOLD_TO_PARTY}</SOLD_TO_PARTY></urn:ZBAPI_SALESORDER_CREATE>'

    return SAPClient("SO").post_soap(xml_body)

# --- [2] Create STO (PO) ---
@mcp.tool()
def create_sto_po(
    PR_NUMBER: str,
    PR_ITEM: str,
    UUID: str = "",
    PUR_GROUP: str = "999",
    PUR_ORG: str = "TW10",
    PUR_PLANT: str = "TP01",
    VENDOR: str = "ICC-CP60",
    DOC_TYPE: str = "NB"
) -> str:
    [cite_start]"""Step 2: Create STO PO (ZSD_STO_CREATE) [cite: 66-78]"""

    PUR_GROUP = PUR_GROUP or "999"
    PUR_ORG = PUR_ORG or "TW10"
    PUR_PLANT = PUR_PLANT or "TP01"
    VENDOR = VENDOR or "ICC-CP60"
    DOC_TYPE = DOC_TYPE or "NB"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_STO_CREATE>{uuid_tag}<DOC_TYPE>{DOC_TYPE}</DOC_TYPE><LGORT/><PR_NUMBER>{PR_NUMBER}</PR_NUMBER><PUR_GROUP>{PUR_GROUP}</PUR_GROUP><PUR_ITEM><item><BNFPO>{PR_ITEM}</BNFPO></item></PUR_ITEM><PUR_ORG>{PUR_ORG}</PUR_ORG><PUR_PLANT>{PUR_PLANT}</PUR_PLANT><VENDOR>{VENDOR}</VENDOR></urn:ZSD_STO_CREATE>'

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
    [cite_start]"""Step 3: Create Outbound Delivery (ZBAPI_OUTB_DELIVERY_CREATE_STO) [cite: 93]"""

    SHIPPING_POINT = SHIPPING_POINT or "TW01"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>{uuid_tag}<PO_ITEM><item><REF_DOC>{PO_NUMBER}</REF_DOC><REF_ITEM>{ITEM_NO}</REF_ITEM><DLV_QTY>{QUANTITY}</DLV_QTY><SALES_UNIT>EA</SALES_UNIT></item></PO_ITEM><SHIP_POINT>{SHIPPING_POINT}</SHIP_POINT></urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>'

    return SAPClient("DN").post_soap(xml_body)

# --- [4] Remediation: Info Record ---
@mcp.tool()
def maintain_info_record(
    MATERIAL: str,
    UUID: str = "",
    PRICE: str = "999",
    VENDOR: str = "ICC-CP60",
    PLANT: str = "TP01",
    PUR_ORG: str = "TW10"
) -> str:
    [cite_start]"""Remediation: Info Record [cite: 147-155]"""

    PRICE = PRICE or "999"
    VENDOR = VENDOR or "ICC-CP60"
    PLANT = PLANT or "TP01"
    PUR_ORG = PUR_ORG or "TW10"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_INFO_RECORD_MAINTAIN>{uuid_tag}<CURRENCY>USD</CURRENCY><MATERIAL>{MATERIAL}</MATERIAL><PLANT>{PLANT}</PLANT><PRICE>{PRICE}</PRICE><PRICE_UNIT>1</PRICE_UNIT><PUR_ORG>{PUR_ORG}</PUR_ORG><VENDOR>{VENDOR}</VENDOR></urn:ZSD_INFO_RECORD_MAINTAIN>'

    return SAPClient("INF").post_soap(xml_body)

# --- [5] Remediation: Sales View ---
@mcp.tool()
def maintain_sales_view(
    MATERIAL: str,
    SALES_ORG: str,
    DISTR_CHAN: str,
    UUID: str = "",
    PLANT: str = "TP01",
    DELYG_PLNT: str = "TP01"
) -> str:
    [cite_start]"""Remediation: Maintain Sales View [cite: 171-187]"""

    if SALES_ORG == "CN60" and DISTR_CHAN == "03":
        PLANT = "CP60"
        DELYG_PLNT = "CP60"
    elif SALES_ORG == "TW01" and DISTR_CHAN == "03":
        PLANT = "TP01"
        DELYG_PLNT = "TP01"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_MATERIAL_SAVEDATA>{uuid_tag}<HEADDATA><MATERIAL>{MATERIAL}</MATERIAL><SALES_VIEW>X</SALES_VIEW><STORAGE_VIEW></STORAGE_VIEW><WAREHOUSE_VIEW></WAREHOUSE_VIEW></HEADDATA><PLANTDATA><PLANT>{PLANT}</PLANT></PLANTDATA><SALESDATA><SALES_ORG>{SALES_ORG}</SALES_ORG><DISTR_CHAN>{DISTR_CHAN}</DISTR_CHAN><DELYG_PLNT>{DELYG_PLNT}</DELYG_PLNT></SALESDATA></urn:ZBAPI_MATERIAL_SAVEDATA>'

    return SAPClient("MAT").post_soap(xml_body)

# --- [6] Remediation: Warehouse View ---
@mcp.tool()
def maintain_warehouse_view(
    MATERIAL: str,
    UUID: str = "",
    WHSE_NO: str = "WH1"
) -> str:
    [cite_start]"""Remediation: Maintain Warehouse View [cite: 206-217]"""

    WHSE_NO = WHSE_NO or "WH1"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_MATERIAL_SAVEDATA>{uuid_tag}<HEADDATA><MATERIAL>{MATERIAL}</MATERIAL><SALES_VIEW></SALES_VIEW><STORAGE_VIEW></STORAGE_VIEW><WAREHOUSE_VIEW>X</WAREHOUSE_VIEW></HEADDATA><WAREHOUSENUMBERDATA><WHSE_NO>{WHSE_NO}</WHSE_NO></WAREHOUSENUMBERDATA></urn:ZBAPI_MATERIAL_SAVEDATA>'

    return SAPClient("MAT").post_soap(xml_body)

# --- [7] Remediation: Source List ---
@mcp.tool()
def maintain_source_list(
    MATERIAL: str,
    VALID_FROM: str,
    UUID: str = "",
    PLANT: str = "TP01",
    VENDOR: str = "ICC-CP60"
) -> str:
    [cite_start]"""Remediation: Source List [cite: 257]"""

    PLANT = PLANT or "TP01"
    VENDOR = VENDOR or "ICC-CP60"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_SOURCE_LIST_MAINTAIN>{uuid_tag}<MATERIAL>{MATERIAL}</MATERIAL><PLANT>{PLANT}</PLANT><VENDOR>{VENDOR}</VENDOR><VALID_FROM>{VALID_FROM}</VALID_FROM><VALID_TO>9999-12-31</VALID_TO></urn:ZSD_SOURCE_LIST_MAINTAIN>'

    return SAPClient("SRC").post_soap(xml_body)

# ==============================================================================
# 4. 啟動
# ==============================================================================
if __name__ == "__main__":
    mcp.run()