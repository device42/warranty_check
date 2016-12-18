import sys
import time
from BeautifulSoup import BeautifulSoup as BS
from xml.sax import saxutils as su

import requests

import shared as config
from uploader import Device42

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class HP:
    def __init__(self, hp_url, debug, retry, order_no_type):
        self.url = hp_url
        self.debug = debug
        self.retry = retry
        self.o_type = order_no_type
        self.token = None
        self.gdid = None
        self.data = {}
        self.devices = []

    def register(self, serial_number):
        soap_payload = """
            <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:iseeReg="http://www.hp.com/isee/webservices/">
            <SOAP-ENV:Body>
            <iseeReg:RegisterClient2>
            <iseeReg:request>
            <![CDATA[<isee:ISEE-Registration xmlns:isee="http://www.hp.com/schemas/isee/5.00/event" schemaVersion="5.00">
            <RegistrationSource>
            <HP_OOSIdentifiers>
            <OSID>
            <Section name="SYSTEM_IDENTIFIERS">
            <Property name="TimestampGenerated" value="%s"/>
            </Section>
            </OSID>
            <CSID>
            <Section name="SYSTEM_IDENTIFIERS">
            <Property name="CollectorType" value="MC3"/>
            <Property name="CollectorVersion" value="T05.80.1 build 1"/>
            <Property name="AutoDetectedSystemSerialNumber" value="%s"/>
            <Property name="SystemModel" value="HP ProLiant"/>
            <Property name="TimestampGenerated" value="%s"/>
            </Section>
            </CSID>
            </HP_OOSIdentifiers>
            <PRS_Address>
            <AddressType>0</AddressType>
            <Address1/>
            <Address2/>
            <Address3/>
            <Address4/>
            <City/>
            <Region/>
            <PostalCode/>
            <TimeZone/>
            <Country/>
            </PRS_Address>
            </RegistrationSource>
            <HP_ISEECustomer>
            <Business/>
            <Name/>
            </HP_ISEECustomer>
            <HP_ISEEPerson>
            <CommunicationMode>255</CommunicationMode>
            <ContactType/>
            <FirstName/>
            <LastName/>
            <Salutation/>
            <Title/>
            <EmailAddress/>
            <TelephoneNumber/>
            <PreferredLanguage/>
            <Availability/>
            </HP_ISEEPerson>
            </isee:ISEE-Registration>]]>
            </iseeReg:request>
            </iseeReg:RegisterClient2>
            </SOAP-ENV:Body>
            </SOAP-ENV:Envelope>
        """

        timestamp = get_timestamp()
        message = (soap_payload % (timestamp, serial_number, timestamp)).encode('utf-8')

        headers = {
            "SOAPAction": "http://www.hp.com/isee/webservices/RegisterClient2",
            "Content-Type": "text/xml; charset=UTF-8",
            "Content-Length": len(message)
        }

        for x in range(self.retry):
            r = requests.post(
                url="https://services.isee.hp.com/ClientRegistration/ClientRegistrationService.asmx",
                headers=headers,
                data=message,
                verify=False
            )

            soup = BS(r.text)
            gdid_raw = soup.findAll('gdid')

            try:
                self.gdid = gdid_raw[0].text
                rtoken_raw = soup.findAll('registrationtoken')
                self.rtoken = rtoken_raw[0].text
                if self.debug:
                    print '\n[!] Registration successful. GDID acquired: %s' % self.gdid
                return True
            except IndexError:
                try:
                    msg_raw = soup.findAll('message')
                    msg = msg_raw[0].text
                    print '[!] Exception: %s' % msg
                    if "failed to get gdid" in msg.lower():
                        url = 'http://h20564.www2.hp.com/hpsc/doc/public/display?docId=emr_na-c03062621'
                        print '\tThis is a server side error. Please take a look at: \n\t%s' % url
                        if x < self.retry-1:
                            print '\n[!] Retrying...'
                            time.sleep(1)
                        else:
                            return False
                except Exception as e:
                    print '[!] Exception! Message was: %s' % str(e)
                    return False
            except Exception as e:
                print '[!] Exception! Message was: %s' % str(e)
                return False

    def run_warranty_check(self, serial, product_number=None):
        if self.debug:
            print '\t[+] Checking warranty info for HP "%s"' % serial
        soap_payload = """
            <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:isee="http://www.hp.com/isee/webservices/">
              <SOAP-ENV:Header>
                <isee:IseeWebServicesHeader>
                  <isee:GDID>%s</isee:GDID>
                  <isee:registrationToken>%s</isee:registrationToken>
                  <isee:OSID/>
                  <isee:CSID/>
                </isee:IseeWebServicesHeader>
              </SOAP-ENV:Header>
              <SOAP-ENV:Body>
                <isee:GetOOSEntitlementList2>
                  <isee:request>
                    <![CDATA[<isee:ISEE-GetOOSEntitlementInfoRequest xmlns:isee="http://www.hp.com/schemas/isee/5.00/entitlement" schemaVersion="5.00">
                      <HP_ISEEEntitlementParameters>
                        <CountryCode>US</CountryCode>
                        <SerialNumber>%s</SerialNumber>
                        <ProductNumber>%s</ProductNumber>
                        <EntitlementType></EntitlementType>
                        <EntitlementId></EntitlementId>
                        <ObligationId></ObligationId>
                      </HP_ISEEEntitlementParameters>
                    </isee:ISEE-GetOOSEntitlementInfoRequest>]]>
                  </isee:request>
                </isee:GetOOSEntitlementList2>
              </SOAP-ENV:Body>
            </SOAP-ENV:Envelope>
        """

        message = (soap_payload % (self.gdid, self.rtoken, serial, product_number)).encode('utf-8')
        headers = {
            "SOAPAction": "http://www.hp.com/isee/webservices/GetOOSEntitlementList2",
            "Content-Type": "text/xml; charset=UTF-8",
            "Content-Length": len(message)
        }

        for x in range(self.retry):
            try:
                resp = requests.post(url=self.url, headers=headers, data=message, verify=False)
                result = resp.text
                data = self.process_result(result, serial, product_number)
                return data
            except requests.RequestException as e:
                msg = str(e)
                print '\n[!] HTTP error. Message was: %s' % msg

    def process_result(self, result, serial, product_number):
        soup = BS(su.unescape(result))
        print soup.prettify()
        time.sleep(1)

        if self.debug:
            print '[+] Manufacturer: HP'
            print '\tSerial: %s \t Part number: %s' % (serial, product_number)
        self.data.update({'manufacturer': 'HP'})
        self.data.update({'serial_no': serial})
        self.data.update({'product_no': product_number})
        try:
            product = soup.find('productdescription').text
            self.data.update({'description': product})
            if self.debug:
                print '\tProduct: %s\n' % product.replace('\n', '').strip()

            for offer in soup.findAll('offer'):
                device = {}
                service = offer.find('offerdescription').text
                scode = offer.find('status').text
                status = 'Unknown'

                if scode.lower() == 'a':
                    status = 'Active'
                elif scode.lower() == 'x':
                    status = 'Expired'

                start_date = offer.find('startdate').text
                end_date = offer.find('enddate').text

                device.update({'service': service})
                device.update({'status': status})
                device.update({'start_date': start_date})
                device.update({'end_date': end_date})
                self.devices.append(device)

                if self.debug:
                    print '\t[*] Service: %s' % service
                    print '\t\tStatus: %s' % status
                    print '\t\tStart date: %s' % start_date
                    print '\t\tEnd date: %s' % end_date
            self.data.update({'items': self.devices})
            return self.data

        except:
            try:
                errorx = soup.findAll('errortext')
                error = errorx[0].text
                print '[!] Error. Message was: %s' % error
            except Exception,  e:
                print '[!] Exception. Message was: %s' % str(e)


def get_timestamp():
    y = str(time.localtime()[0])
    mon = str(time.localtime()[1])
    d = str(time.localtime()[2])
    h = str(time.localtime()[3])
    minutes = str(time.localtime()[4])
    s = str(time.localtime()[5])
    zone = 'EST'
    timestamp = y+'/'+mon+'/'+d+' '+h+':'+minutes+':'+s+' '+zone
    return timestamp


def main():
    # get settings from config file
    d42_username, d42_password, d42_url,\
           hp_url, debug, retry, order_no_type = config.get_config('hp')

    # init
    d42 = Device42(d42_username, d42_password, d42_url, debug, retry)

    # get data from Device42
    orders = d42.get_purchases()
    already_there = []
    dates = {}
    if orders:
        for order in orders:
            line_items = order['line_items']
            for line_item in line_items:
                end = line_item['line_end_date']
                start = line_item['line_start_date']
                devices = line_item['devices']
                for device in devices:
                    serial = device['serial_no']
                    dates.update({serial: [start, end]})
                    if serial not in already_there:
                        already_there.append(serial)

    devices = d42.get_serials()
    items = [[x['device_id'], x['serial_no'], x['manufacturer']] for x in
             devices['Devices'] if x['serial_no'] and x['manufacturer']]

    for item in items:
        d42_id, serial, vendor = item
        print '\t[+] HP serial #: %s' % serial
        """
        if 'hp' in vendor.lower():
            #if len(serial) <= 7: # testing only original DELL...remove this
            warranty = hp.run_warranty_check(serial, product_number)
            if warranty:
                wend   = warranty['line_end_date']
                wstart = warranty['line_start_date']

                # update or duplicate? Compare warranty dates by serial
                if serial in already_there:
                    dstart, dend = dates[serial]
                    if dstart == wstart and dend == wend: # duplicate
                        print '[!] Duplicate found. Purchase for SKU "%s" is already uploaded' % serial
                    else:
                        # add new line_item
                        d42.upload_data(warranty)
                else:
                    # upload new warranty and add it's serial to 'already_there'
                    d42.upload_data(warranty)
                    already_there.append(serial)
        """
    print '[!] HP warranty check is not implemented yet.'


if __name__ == '__main__':
    main()
    sys.exit()
