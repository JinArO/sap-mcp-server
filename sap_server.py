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
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# ==============================================================================
# Configuration
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
        }
    }

# ==============================================================================
# Core Client
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
        # Standard SOAP Envelope without XML declaration
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
                    # Try to extract Body content
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
# Tools
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
    SHIPPING_POINT: str = "TW01"
) -> str:
    """Step 1: Create Sales Order"""

    # Enforce defaults to prevent 'Mandatory header fields missing'
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

    # Structure strictly following Word doc: UUID -> CUST -> ITEM TABLE -> HEADER FIELDS
    xml_body = f'<urn:ZBAPI_SALESORDER_CREATE>{uuid_tag}<CUST_PO>{cust_po_val}</CUST_PO><CUST_PO_DATE>{cust_po_date_val}</CUST_PO_DATE><IT_SO_ITEM><item><MATERIAL_NO>000010</MATERIAL_NO><MATERIAL>{MATERIAL}</MATERIAL><UNIT>PCE</UNIT><QTY>{QTY}</QTY><PLANT>{plant_val}</PLANT><SHIPPING_POINT>{shipping_pt_val}</SHIPPING_POINT><DELIVERY_DATE>{cust_po_date_val}</DELIVERY_DATE></item></IT_SO_ITEM><ORDER_TYPE>{order_type_val}</ORDER_TYPE><SALES_CHANNEL>{sales_channel_val}</SALES_CHANNEL><SALES_DIVISION>{sales_division_val}</SALES_DIVISION><SALES_ORG>{sales_org_val}</SALES_ORG><SHIP_TO_PARTY>{ship_to_val}</SHIP_TO_PARTY><SOLD_TO_PARTY>{sold_to_val}</SOLD_TO_PARTY></urn:ZBAPI_SALESORDER_CREATE>'

    return SAPClient("SO").post_soap(xml_body)

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
    """Step 2: Create STO PO"""

    pur_group_val = PUR_GROUP if PUR_GROUP else "999"
    pur_org_val = PUR_ORG if PUR_ORG else "TW10"
    pur_plant_val = PUR_PLANT if PUR_PLANT else "TP01"
    vendor_val = VENDOR if VENDOR else "ICC-CP60"
    doc_type_val = DOC_TYPE if DOC_TYPE else "NB"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_STO_CREATE>{uuid_tag}<DOC_TYPE>{doc_type_val}</DOC_TYPE><LGORT/><PR_NUMBER>{PR_NUMBER}</PR_NUMBER><PUR_GROUP>{pur_group_val}</PUR_GROUP><PUR_ITEM><item><BNFPO>{PR_ITEM}</BNFPO></item></PUR_ITEM><PUR_ORG>{pur_org_val}</PUR_ORG><PUR_PLANT>{pur_plant_val}</PUR_PLANT><VENDOR>{vendor_val}</VENDOR></urn:ZSD_STO_CREATE>'

    return SAPClient("STO").post_soap(xml_body)

@mcp.tool()
def create_outbound_delivery(
    PO_NUMBER: str,
    ITEM_NO: str,
    QUANTITY: float,
    SHIPPING_POINT: str,
    UUID: str = ""
) -> str:
    """Step 3: Create Outbound Delivery"""

    ship_point_val = SHIPPING_POINT if SHIPPING_POINT else "TW01"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>{uuid_tag}<PO_ITEM><item><REF_DOC>{PO_NUMBER}</REF_DOC><REF_ITEM>{ITEM_NO}</REF_ITEM><DLV_QTY>{QUANTITY}</DLV_QTY><SALES_UNIT>EA</SALES_UNIT></item></PO_ITEM><SHIP_POINT>{ship_point_val}</SHIP_POINT></urn:ZBAPI_OUTB_DELIVERY_CREATE_STO>'

    return SAPClient("DN").post_soap(xml_body)

@mcp.tool()
def maintain_info_record(
    MATERIAL: str,
    UUID: str = "",
    PRICE: str = "999",
    VENDOR: str = "ICC-CP60",
    PLANT: str = "TP01",
    PUR_ORG: str = "TW10"
) -> str:
    """Remediation: Info Record"""

    price_val = PRICE if PRICE else "999"
    vendor_val = VENDOR if VENDOR else "ICC-CP60"
    plant_val = PLANT if PLANT else "TP01"
    pur_org_val = PUR_ORG if PUR_ORG else "TW10"

    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_INFO_RECORD_MAINTAIN>{uuid_tag}<CURRENCY>USD</CURRENCY><MATERIAL>{MATERIAL}</MATERIAL><PLANT>{plant_val}</PLANT><PRICE>{price_val}</PRICE><PRICE_UNIT>1</PRICE_UNIT><PUR_ORG>{pur_org_val}</PUR_ORG><VENDOR>{vendor_val}</VENDOR></urn:ZSD_INFO_RECORD_MAINTAIN>'

    return SAPClient("INF").post_soap(xml_body)

@mcp.tool()
def maintain_sales_view(
    MATERIAL: str,
    SALES_ORG: str,
    DISTR_CHAN: str,
    UUID: str = "",
    PLANT: str = "TP01",
    DELYG_PLNT: str = "TP01"
) -> str:
    """Remediation: Maintain Sales View"""

    # Logic from Word Doc
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

    return SAPClient("MAT").post_soap(xml_body)

@mcp.tool()
def maintain_warehouse_view(
    MATERIAL: str,
    UUID: str = "",
    WHSE_NO: str = "WH1"
) -> str:
    """Remediation: Maintain Warehouse View"""

    whse_no_val = WHSE_NO if WHSE_NO else "WH1"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZBAPI_MATERIAL_SAVEDATA>{uuid_tag}<HEADDATA><MATERIAL>{MATERIAL}</MATERIAL><SALES_VIEW></SALES_VIEW><STORAGE_VIEW></STORAGE_VIEW><WAREHOUSE_VIEW>X</WAREHOUSE_VIEW></HEADDATA><WAREHOUSENUMBERDATA><WHSE_NO>{whse_no_val}</WHSE_NO></WAREHOUSENUMBERDATA></urn:ZBAPI_MATERIAL_SAVEDATA>'

    return SAPClient("MAT").post_soap(xml_body)

@mcp.tool()
def maintain_source_list(
    MATERIAL: str,
    VALID_FROM: str,
    UUID: str = "",
    PLANT: str = "TP01",
    VENDOR: str = "ICC-CP60"
) -> str:
    """Remediation: Source List"""

    plant_val = PLANT if PLANT else "TP01"
    vendor_val = VENDOR if VENDOR else "ICC-CP60"
    valid_from_val = VALID_FROM if VALID_FROM else "2025-01-01"
    uuid_tag = f"<UUID>{UUID}</UUID>" if UUID else ""

    xml_body = f'<urn:ZSD_SOURCE_LIST_MAINTAIN>{uuid_tag}<MATERIAL>{MATERIAL}</MATERIAL><PLANT>{plant_val}</PLANT><VENDOR>{vendor_val}</VENDOR><VALID_FROM>{valid_from_val}</VALID_FROM><VALID_TO>9999-12-31</VALID_TO></urn:ZSD_SOURCE_LIST_MAINTAIN>'

    return SAPClient("SRC").post_soap(xml_body)

if __name__ == "__main__":
    mcp.run()