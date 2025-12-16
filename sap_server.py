# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]",
#     "zeep",
#     "requests",
#     "uvicorn",
#     "pydantic",
# ]
# ///

import os
import requests
import uvicorn
import tempfile
from mcp.server.fastmcp import FastMCP
from zeep import Client, Settings
from zeep.transports import Transport
from pydantic import BaseModel, Field
from typing import List, Optional

# ==============================================================================
# 1. 內嵌 WSDL 定義 (注意：這裡加了 r""" 代表原始字串，解決 \d 報錯問題)
# ==============================================================================
WSDL_CONTENT = r"""<?xml version="1.0" encoding="utf-8"?><wsdl:definitions targetNamespace="urn:sap-com:document:sap:rfc:functions" xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/" xmlns:wsoap12="http://schemas.xmlsoap.org/wsdl/soap12/" xmlns:http="http://schemas.xmlsoap.org/wsdl/http/" xmlns:mime="http://schemas.xmlsoap.org/wsdl/mime/" xmlns:tns="urn:sap-com:document:sap:rfc:functions" xmlns:wsp="http://schemas.xmlsoap.org/ws/2004/09/policy" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"><wsdl:documentation><sidl:sidl xmlns:sidl="http://www.sap.com/2007/03/sidl"/></wsdl:documentation><wsp:UsingPolicy wsdl:required="true"/><wsp:Policy wsu:Id="BN__ZWS_BAPI_SALESORDER_CREATE_BINDING"><wsp:ExactlyOne><wsp:All><sapattahnd:Enabled xmlns:sapattahnd="http://www.sap.com/710/features/attachment/">false</sapattahnd:Enabled><saptrnbnd:OptimizedMimeSerialization xmlns:saptrnbnd="http://schemas.xmlsoap.org/ws/2004/09/policy/optimizedmimeserialization" wsp:Optional="true"/><wsaw:UsingAddressing xmlns:wsaw="http://www.w3.org/2006/05/addressing/wsdl" wsp:Optional="true"/><wsp:All xmlns:wsp="http://schemas.xmlsoap.org/ws/2004/09/policy"><sp:TransportBinding xmlns:sp="http://docs.oasis-open.org/ws-sx/ws-securitypolicy/200702" xmlns:sapsp="http://www.sap.com/webas/630/soap/features/security/policy" xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:wst="http://docs.oasis-open.org/ws-sx/ws-trust/200512" xmlns:wsu="http://schemas.xmlsoap.org/ws/2002/07/utility" xmlns:wsx="http://schemas.xmlsoap.org/ws/2004/09/mex"><wsp:Policy><sp:TransportToken><wsp:Policy><sp:HttpsToken><wsp:Policy><sp:HttpBasicAuthentication/></wsp:Policy></sp:HttpsToken></wsp:Policy></sp:TransportToken><sp:AlgorithmSuite><wsp:Policy><sp:Basic128Rsa15/></wsp:Policy></sp:AlgorithmSuite><sp:Layout><wsp:Policy><sp:Strict/></wsp:Policy></sp:Layout></wsp:Policy></sp:TransportBinding></wsp:All></wsp:All><wsp:All><sapattahnd:Enabled xmlns:sapattahnd="http://www.sap.com/710/features/attachment/">false</sapattahnd:Enabled><saptrnbnd:OptimizedXMLTransfer uri="http://xml.sap.com/2006/11/esi/esp/binxml" xmlns:saptrnbnd="http://www.sap.com/webas/710/soap/features/transportbinding/" wsp:Optional="true"/><wsaw:UsingAddressing xmlns:wsaw="http://www.w3.org/2006/05/addressing/wsdl" wsp:Optional="true"/><wsp:All xmlns:wsp="http://schemas.xmlsoap.org/ws/2004/09/policy"><sp:TransportBinding xmlns:sp="http://docs.oasis-open.org/ws-sx/ws-securitypolicy/200702" xmlns:sapsp="http://www.sap.com/webas/630/soap/features/security/policy" xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:wst="http://docs.oasis-open.org/ws-sx/ws-trust/200512" xmlns:wsu="http://schemas.xmlsoap.org/ws/2002/07/utility" xmlns:wsx="http://schemas.xmlsoap.org/ws/2004/09/mex"><wsp:Policy><sp:TransportToken><wsp:Policy><sp:HttpsToken><wsp:Policy><sp:HttpBasicAuthentication/></wsp:Policy></sp:HttpsToken></wsp:Policy></sp:TransportToken><sp:AlgorithmSuite><wsp:Policy><sp:Basic128Rsa15/></wsp:Policy></sp:AlgorithmSuite><sp:Layout><wsp:Policy><sp:Strict/></wsp:Policy></sp:Layout></wsp:Policy></sp:TransportBinding></wsp:All></wsp:All></wsp:ExactlyOne></wsp:Policy><wsp:Policy wsu:Id="BN__ZWS_BAPI_SALESORDER_CREATE_BINDING_soap12"><wsp:ExactlyOne><wsp:All><sapattahnd:Enabled xmlns:sapattahnd="http://www.sap.com/710/features/attachment/">false</sapattahnd:Enabled><saptrnbnd:OptimizedMimeSerialization xmlns:saptrnbnd="http://schemas.xmlsoap.org/ws/2004/09/policy/optimizedmimeserialization" wsp:Optional="true"/><wsaw:UsingAddressing xmlns:wsaw="http://www.w3.org/2006/05/addressing/wsdl" wsp:Optional="true"/><wsp:All xmlns:wsp="http://schemas.xmlsoap.org/ws/2004/09/policy"><sp:TransportBinding xmlns:sp="http://docs.oasis-open.org/ws-sx/ws-securitypolicy/200702" xmlns:sapsp="http://www.sap.com/webas/630/soap/features/security/policy" xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:wst="http://docs.oasis-open.org/ws-sx/ws-trust/200512" xmlns:wsu="http://schemas.xmlsoap.org/ws/2002/07/utility" xmlns:wsx="http://schemas.xmlsoap.org/ws/2004/09/mex"><wsp:Policy><sp:TransportToken><wsp:Policy><sp:HttpsToken><wsp:Policy><sp:HttpBasicAuthentication/></wsp:Policy></sp:HttpsToken></wsp:Policy></sp:TransportToken><sp:AlgorithmSuite><wsp:Policy><sp:Basic128Rsa15/></wsp:Policy></sp:AlgorithmSuite><sp:Layout><wsp:Policy><sp:Strict/></wsp:Policy></sp:Layout></wsp:Policy></sp:TransportBinding></wsp:All></wsp:All><wsp:All><sapattahnd:Enabled xmlns:sapattahnd="http://www.sap.com/710/features/attachment/">false</sapattahnd:Enabled><saptrnbnd:OptimizedXMLTransfer uri="http://xml.sap.com/2006/11/esi/esp/binxml" xmlns:saptrnbnd="http://www.sap.com/webas/710/soap/features/transportbinding/" wsp:Optional="true"/><wsaw:UsingAddressing xmlns:wsaw="http://www.w3.org/2006/05/addressing/wsdl" wsp:Optional="true"/><wsp:All xmlns:wsp="http://schemas.xmlsoap.org/ws/2004/09/policy"><sp:TransportBinding xmlns:sp="http://docs.oasis-open.org/ws-sx/ws-securitypolicy/200702" xmlns:sapsp="http://www.sap.com/webas/630/soap/features/security/policy" xmlns:wsa="http://www.w3.org/2005/08/addressing" xmlns:wst="http://docs.oasis-open.org/ws-sx/ws-trust/200512" xmlns:wsu="http://schemas.xmlsoap.org/ws/2002/07/utility" xmlns:wsx="http://schemas.xmlsoap.org/ws/2004/09/mex"><wsp:Policy><sp:TransportToken><wsp:Policy><sp:HttpsToken><wsp:Policy><sp:HttpBasicAuthentication/></wsp:Policy></sp:HttpsToken></wsp:Policy></sp:TransportToken><sp:AlgorithmSuite><wsp:Policy><sp:Basic128Rsa15/></wsp:Policy></sp:AlgorithmSuite><sp:Layout><wsp:Policy><sp:Strict/></wsp:Policy></sp:Layout></wsp:Policy></sp:TransportBinding></wsp:All></wsp:All></wsp:ExactlyOne></wsp:Policy><wsp:Policy wsu:Id="IF__ZWS_BAPI_SALESORDER_CREATE"><wsp:ExactlyOne><wsp:All><sapsession:Session xmlns:sapsession="http://www.sap.com/webas/630/soap/features/session/"><sapsession:enableSession>false</sapsession:enableSession></sapsession:Session><sapcentraladmin:CentralAdministration xmlns:sapcentraladmin="http://www.sap.com/webas/700/soap/features/CentralAdministration/" wsp:Optional="true"><sapcentraladmin:BusinessApplicationID>8BEEAC4D35E71FE08AC70E02EE41BB21</sapcentraladmin:BusinessApplicationID></sapcentraladmin:CentralAdministration></wsp:All></wsp:ExactlyOne></wsp:Policy><wsp:Policy wsu:Id="OP__ZBAPI_SALESORDER_CREATE"><wsp:ExactlyOne><wsp:All><saptrhnw05:required xmlns:saptrhnw05="http://www.sap.com/NW05/soap/features/transaction/">no</saptrhnw05:required><sapcomhnd:enableCommit xmlns:sapcomhnd="http://www.sap.com/NW05/soap/features/commit/">false</sapcomhnd:enableCommit><sapblock:enableBlocking xmlns:sapblock="http://www.sap.com/NW05/soap/features/blocking/">true</sapblock:enableBlocking><saprmnw05:enableWSRM xmlns:saprmnw05="http://www.sap.com/NW05/soap/features/wsrm/">false</saprmnw05:enableWSRM></wsp:All></wsp:ExactlyOne></wsp:Policy><wsdl:types><xsd:schema attributeFormDefault="qualified" targetNamespace="urn:sap-com:document:sap:rfc:functions"><xsd:simpleType name="char1"><xsd:restriction base="xsd:string"><xsd:maxLength value="1"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char10"><xsd:restriction base="xsd:string"><xsd:maxLength value="10"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char2"><xsd:restriction base="xsd:string"><xsd:maxLength value="2"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char20"><xsd:restriction base="xsd:string"><xsd:maxLength value="20"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char30"><xsd:restriction base="xsd:string"><xsd:maxLength value="30"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char32"><xsd:restriction base="xsd:string"><xsd:maxLength value="32"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char35"><xsd:restriction base="xsd:string"><xsd:maxLength value="35"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char4"><xsd:restriction base="xsd:string"><xsd:maxLength value="4"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="char40"><xsd:restriction base="xsd:string"><xsd:maxLength value="40"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="cuky5"><xsd:restriction base="xsd:string"><xsd:maxLength value="5"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="curr11.2"><xsd:restriction base="xsd:decimal"><xsd:totalDigits value="11"/><xsd:fractionDigits value="2"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="date10"><xsd:restriction base="xsd:string"><xsd:maxLength value="10"/><xsd:pattern value="\d\d\d\d-\d\d-\d\d"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="decimal5.0"><xsd:restriction base="xsd:decimal"><xsd:totalDigits value="5"/><xsd:fractionDigits value="0"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="numeric3"><xsd:restriction base="xsd:string"><xsd:maxLength value="3"/><xsd:pattern value="\d*"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="numeric6"><xsd:restriction base="xsd:string"><xsd:maxLength value="6"/><xsd:pattern value="\d*"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="quantum15.3"><xsd:restriction base="xsd:decimal"><xsd:totalDigits value="15"/><xsd:fractionDigits value="3"/></xsd:restriction></xsd:simpleType><xsd:simpleType name="string"><xsd:restriction base="xsd:string"/></xsd:simpleType><xsd:simpleType name="unit3"><xsd:restriction base="xsd:string"><xsd:maxLength value="3"/></xsd:restriction></xsd:simpleType><xsd:complexType name="ZAIAGENTS_BAPISOITEM_S"><xsd:sequence><xsd:element name="MATERIAL_NO" type="tns:numeric6"/><xsd:element name="MATERIAL" type="tns:char40"/><xsd:element name="UNIT" type="tns:unit3"/><xsd:element name="QTY" type="tns:quantum15.3"/><xsd:element name="CUST_MATERIAL" type="tns:char35"/><xsd:element name="PLANT" type="tns:char4"/><xsd:element name="SHIPPING_POINT" type="tns:char4"/><xsd:element name="DELIVERY_DATE" type="tns:date10"/></xsd:sequence></xsd:complexType><xsd:complexType name="ZBAPIRET"><xsd:sequence><xsd:element name="TYPE" type="tns:char1"/><xsd:element name="ID" type="tns:char20"/><xsd:element name="NUMBER" type="tns:numeric3"/><xsd:element name="MESSAGE" type="tns:string"/><xsd:element name="MESSAGE_LONG" type="tns:string"/><xsd:element name="LOG_NO" type="tns:char20"/><xsd:element name="LOG_MSG_NO" type="tns:numeric6"/><xsd:element name="PARAMETER" type="tns:char32"/><xsd:element name="ROW" type="xsd:int"/><xsd:element name="FIELD" type="tns:char30"/><xsd:element name="SYSTEM" type="tns:char10"/></xsd:sequence></xsd:complexType><xsd:complexType name="ZAIAGENTS_PR_INFO"><xsd:sequence><xsd:element name="PR_NUMBER" type="tns:char10"/><xsd:element name="PR_ITEM" type="tns:numeric6"/><xsd:element name="VENDOR" type="tns:char10"/><xsd:element name="PUR_ORG" type="tns:char4"/><xsd:element name="PLANT" type="tns:char4"/><xsd:element name="PRICE" type="tns:curr11.2"/><xsd:element name="PRICE_UNIT" type="tns:decimal5.0"/><xsd:element name="CURRENCY" type="tns:cuky5"/></xsd:sequence></xsd:complexType><xsd:complexType name="ZAIAGENTS_BAPISOITEM"><xsd:sequence><xsd:element name="item" type="tns:ZAIAGENTS_BAPISOITEM_S" minOccurs="0" maxOccurs="unbounded"/></xsd:sequence></xsd:complexType><xsd:complexType name="ZBAPIRET_T"><xsd:sequence><xsd:element name="item" type="tns:ZBAPIRET" minOccurs="0" maxOccurs="unbounded"/></xsd:sequence></xsd:complexType><xsd:complexType name="ZAIAGENTS_PR_INFO_T"><xsd:sequence><xsd:element name="item" type="tns:ZAIAGENTS_PR_INFO" minOccurs="0" maxOccurs="unbounded"/></xsd:sequence></xsd:complexType><xsd:element name="ZBAPI_SALESORDER_CREATE"><xsd:complexType><xsd:sequence><xsd:element name="CUST_PO" type="tns:char35"/><xsd:element name="CUST_PO_DATE" type="tns:date10"/><xsd:element name="IT_SO_ITEM" type="tns:ZAIAGENTS_BAPISOITEM"/><xsd:element name="ORDER_TYPE" type="tns:char4"/><xsd:element name="SALES_CHANNEL" type="tns:char2"/><xsd:element name="SALES_DIVISION" type="tns:char2"/><xsd:element name="SALES_ORG" type="tns:char4"/><xsd:element name="SHIP_TO_PARTY" type="tns:char10"/><xsd:element name="SOLD_TO_PARTY" type="tns:char10"/></xsd:sequence></xsd:complexType></xsd:element><xsd:element name="ZBAPI_SALESORDER_CREATEResponse"><xsd:complexType><xsd:sequence><xsd:element name="DETAIL_MESSAGE" type="tns:ZBAPIRET_T"/><xsd:element name="PR_ITEM" type="tns:ZAIAGENTS_PR_INFO_T"/><xsd:element name="SALES_NO" type="tns:char10"/></xsd:sequence></xsd:complexType></xsd:element></xsd:schema></wsdl:types><wsdl:message name="ZBAPI_SALESORDER_CREATE"><wsdl:part name="parameters" element="tns:ZBAPI_SALESORDER_CREATE"/></wsdl:message><wsdl:message name="ZBAPI_SALESORDER_CREATEResponse"><wsdl:part name="parameter" element="tns:ZBAPI_SALESORDER_CREATEResponse"/></wsdl:message><wsdl:portType name="ZWS_BAPI_SALESORDER_CREATE"><wsp:Policy><wsp:PolicyReference URI="#IF__ZWS_BAPI_SALESORDER_CREATE"/></wsp:Policy><wsdl:operation name="ZBAPI_SALESORDER_CREATE"><wsp:Policy><wsp:PolicyReference URI="#OP__ZBAPI_SALESORDER_CREATE"/></wsp:Policy><wsdl:input message="tns:ZBAPI_SALESORDER_CREATE"/><wsdl:output message="tns:ZBAPI_SALESORDER_CREATEResponse"/></wsdl:operation></wsdl:portType><wsdl:binding name="ZWS_BAPI_SALESORDER_CREATE_BINDING" type="tns:ZWS_BAPI_SALESORDER_CREATE"><wsp:Policy><wsp:PolicyReference URI="#BN__ZWS_BAPI_SALESORDER_CREATE_BINDING"/></wsp:Policy><soap:binding transport="http://schemas.xmlsoap.org/soap/http" style="document"/><wsdl:operation name="ZBAPI_SALESORDER_CREATE"><soap:operation soapAction="urn:sap-com:document:sap:rfc:functions:ZWS_BAPI_SALESORDER_CREATE:ZBAPI_SALESORDER_CREATERequest" style="document"/><wsdl:input><soap:body use="literal"/></wsdl:input><wsdl:output><soap:body use="literal"/></wsdl:output></wsdl:operation></wsdl:binding><wsdl:binding name="ZWS_BAPI_SALESORDER_CREATE_BINDING_soap12" type="tns:ZWS_BAPI_SALESORDER_CREATE"><wsp:Policy><wsp:PolicyReference URI="#BN__ZWS_BAPI_SALESORDER_CREATE_BINDING_soap12"/></wsp:Policy><wsoap12:binding transport="http://schemas.xmlsoap.org/soap/http" style="document"/><wsdl:operation name="ZBAPI_SALESORDER_CREATE"><wsoap12:operation soapAction="urn:sap-com:document:sap:rfc:functions:ZWS_BAPI_SALESORDER_CREATE:ZBAPI_SALESORDER_CREATERequest" style="document"/><wsdl:input><wsoap12:body use="literal"/></wsdl:input><wsdl:output><wsoap12:body use="literal"/></wsdl:output></wsdl:operation></wsdl:binding><wsdl:service name="ZWS_BAPI_SALESORDER_CREATE_SEV"><wsdl:port name="ZWS_BAPI_SALESORDER_CREATE_BINDING" binding="tns:ZWS_BAPI_SALESORDER_CREATE_BINDING"><soap:address location="https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_salesorder_create/100/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding"/></wsdl:port><wsdl:port name="ZWS_BAPI_SALESORDER_CREATE_BINDING_soap12" binding="tns:ZWS_BAPI_SALESORDER_CREATE_BINDING_soap12"><wsoap12:address location="https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_salesorder_create/100/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding"/></wsdl:port></wsdl:service></wsdl:definitions>"""

# 自動生成臨時 WSDL 檔案
temp_wsdl = tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8")
temp_wsdl.write(WSDL_CONTENT)
temp_wsdl.close()
WSDL_PATH = temp_wsdl.name

# ==============================================================================
# 2. 初始化 MCP Server
# ==============================================================================
mcp = FastMCP("SAP Sales Order BAPI")

SAP_USER = os.environ.get("SAP_USER")
SAP_PASSWORD = os.environ.get("SAP_PASSWORD")

# ==============================================================================
# 3. 定義資料模型 (Pydantic)
# ==============================================================================
class SalesOrderItem(BaseModel):
    MATERIAL: str = Field(..., description="Material Number (e.g. 'MZ-FG-M100')")
    QTY: float = Field(..., description="Quantity")
    UNIT: str = Field(..., description="Unit (e.g. 'PC')")
    PLANT: str = Field(..., description="Plant Code (e.g. '1000')")
    DELIVERY_DATE: str = Field(..., description="YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$")
    MATERIAL_NO: Optional[str] = Field(None, description="Numeric Material ID")
    CUST_MATERIAL: Optional[str] = Field(None, description="Customer Material Number")
    SHIPPING_POINT: Optional[str] = Field(None, description="Shipping Point")

# ==============================================================================
# 4. 定義工具邏輯 (Tool)
# ==============================================================================
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

    if not SAP_USER or not SAP_PASSWORD:
        return "Error: SAP_USER or SAP_PASSWORD not set."

    session = requests.Session()
    session.auth = (SAP_USER, SAP_PASSWORD)
    session.verify = False

    settings = Settings(strict=False, xml_huge_tree=True)

    try:
        transport = Transport(session=session)
        client = Client(wsdl=WSDL_PATH, transport=transport, settings=settings)

        # 綁定 Service
        service = client.create_service(
            '{urn:sap-com:document:sap:rfc:functions}ZWS_BAPI_SALESORDER_CREATE_BINDING',
            'https://vhivcqasci.sap.inventec.com:44300/sap/bc/srt/rfc/sap/zws_bapi_salesorder_create/100/zws_bapi_salesorder_create_sev/zws_bapi_salesorder_create_binding'
        )

        items_payload = [item.model_dump(exclude_none=True) for item in IT_SO_ITEM]

        # 呼叫 SAP
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

        msg_str = " | ".join([f"{m.get('TYPE')}: {m.get('MESSAGE')}" for m in detail_msg if m.get('TYPE') in ['E', 'A', 'S']])

        if sales_no:
             return f"Success! Sales Order: {sales_no}\n{msg_str}"
        return f"Failed.\n{msg_str}"

    except Exception as e:
        return f"System Error: {str(e)}"

# ==============================================================================
# 5. 啟動伺服器
# ==============================================================================
if __name__ == "__main__":
    print("Starting FastMCP Server via UVX...")
    # 修正重點：請將 _sse_app 改為 sse_app (去掉前面的底線)
    uvicorn.run(mcp.sse_app, host="0.0.0.0", port=8000)