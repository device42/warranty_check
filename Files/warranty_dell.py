import sys
import time
import random
import requests

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class Dell(WarrantyBase, object):
    def __init__(self, params):
        super(Dell, self).__init__()
        self.url = params['url']
        self.api_key = params['api_key']
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

    def run_warranty_check(self, inline_serials, retry=True):
        global full_serials
        full_serials = {}

        # making sure the warranty also gets updated if the serial has been changed by decom lifecycle process
        incoming_serials = inline_serials.split(',')
        inline_serials = []

        for d42_serial in incoming_serials:
            d42_serial = d42_serial.upper()
            if '_' in d42_serial:
                full_serials.update({d42_serial.split('_')[0]: d42_serial})
                d42_serial = d42_serial.split('_')[0]
            elif '(' in d42_serial:
                full_serials.update({d42_serial.split('(')[0]: d42_serial})
                d42_serial = d42_serial.split('(')[0]
            else:
                full_serials.update({d42_serial: d42_serial})
            inline_serials.append(d42_serial)
        inline_serials = ','.join(inline_serials)

        if self.debug:
            print '\t[+] Checking warranty info for "%s"' % inline_serials
        timeout = 30

        payload = {'id': inline_serials, 'apikey': self.api_key, 'accept': 'Application/json'}

        try:
            resp = requests.get(self.url, params=payload, verify=True, timeout=timeout)
            msg = 'Status code: %s' % str(resp.status_code)
            if str(resp.status_code) != '200':
                print '\t[!] HTTP error. Message was: %s' % msg
                if str(resp.status_code) == '401':
                    print '\t[!] API call unauthorized. Wrong/expired key? Wrong endpoint?'
                if str(resp.status_code) == '404':
                    print '\t[!] 404: Information not found?'
                # suspecting blockage due to to many api calls. Put in a pause and go on
                print '\t[!] waiting for 60 seconds to let the api server calm down'
                time.sleep(60)
                if retry:
                    print '\n[!] Retry'
                    self.run_warranty_check(inline_serials, False)
                else:
                    return None
            else:
                result = resp.json()
                return result
        except requests.RequestException as e:
            self.error_msg(e)
            return None

    def process_result(self, result, purchases, ordernos):
        global full_serials
        data = {}

        if 'AssetWarrantyResponse' in result:
            for item in result['AssetWarrantyResponse']:
                try:
                    warranties = item['AssetEntitlementData']
                    asset = item['AssetHeaderData']
                    product = item['ProductHeaderData']
                except IndexError:
                    if self.debug:
                        try:
                            msg = str(result['InvalidFormatAssets']['BadAssets'])
                            if msg:
                                print '\t\t[-] Error: Bad asset: %s' % msg
                        except Exception as e:
                            print e

                else:
                    if self.order_no == 'vendor':
                        order_no = asset['OrderNumber']
                    elif self.order_no == 'common':
                        order_no = self.common
                    elif self.order_no == 'shipdate':
                        if self.debug:
                            print '[!] WORKING ON: \n',item
                        try:
                            #some systems have no shipping date mentioned
                            #or the service_tag is incorrect. Confirm via iDrac and support.dell.com
                            order_no = asset['ShipDate'].split('T')[0]
                        except:
                            order_no = '0000-00-00'
                    else:
                        order_no = self.generate_random_order_no()

                    try:
                        #If an existing registration with ordernumber exists, make use of that one.
                        order_no = ordernos[asset['ServiceTag'].lower()]
                    except Exception as e:
                        print e

                    serial = asset['ServiceTag']
                    customernumber = asset['CustomerNumber']
                    country = asset['CountryLookupCode']

                    '''
                    For future implementation of registering the purchase date as a lifecycle event
                    Add a lifecycle event for the system
                    data.update({'date':ship_date})
                    data.update({'type':'Purchased'})
                    data.update({'serial_no':serial})
                    d42.upload_lifecycle(data)
                    data.clear()
                    '''

                    # We need check per warranty service item
                    for sub_item in warranties:
                        data.clear()
                        ship_date = asset['ShipDate'].split('T')[0]
                        try:
                            product_id = product['ProductId']
                        except:
                            product_id = 'notspecified'

                        data.update({'order_no': order_no})
                        if ship_date:
                            data.update({'po_date': ship_date})
                        data.update({'completed': 'yes'})

                        data.update({'vendor': 'Dell Inc.'})
                        data.update({'line_device_serial_nos': full_serials[serial]})
                        data.update({'line_type': 'contract'})
                        data.update({'line_item_type': 'device'})
                        data.update({'line_completed': 'yes'})

                        line_contract_id = sub_item['ItemNumber']
                        data.update({'line_notes': line_contract_id})
                        data.update({'line_contract_id': line_contract_id})

                        # Using notes as well as the Device42 API doesn't give back the line_contract_id,
                        # so notes is now used for identification
                        # Mention this to device42

                        service_level_group = sub_item['ServiceLevelGroup']
                        if service_level_group == -1 or service_level_group == 5 or service_level_group == 8 or service_level_group == 99999:
                            contract_type = 'Warranty'
                        elif service_level_group == 8 and 'compellent' in product_id:
                            contract_type = 'Service'
                        elif service_level_group == 11 and 'compellent' in product_id:
                            contract_type = 'Warranty'
                        else:
                            contract_type = 'Service'
                        data.update({'line_contract_type': contract_type})
                        if contract_type == 'Service':
                            # Skipping the services, only want the warranties
                            continue

                        try:
                            # There's a max 64 character limit on the line service type field in Device42 (version 13.1.0)
                            service_level_description = left(sub_item['ServiceLevelDescription'], 64)
                            data.update({'line_service_type': service_level_description})
                        except:
                            pass

                        start_date = sub_item['StartDate'].split('T')[0]
                        end_date = sub_item['EndDate'].split('T')[0]

                        data.update({'line_start_date': start_date})
                        data.update({'line_end_date': end_date})

                        # update or duplicate? Compare warranty dates by serial, contract_id, start date and end date
                        hasher = serial.lower() + line_contract_id + start_date + end_date
                        try:
                            d_purchase_id, d_order_no, d_line_no, d_contractid, d_start, d_end, forcedupdate = purchases[hasher]

                            if forcedupdate:
                                data.update({'order_no': start_date})
                                data.update({'purchase_id': d_purchase_id})
                                data.update({'line_no': d_line_no})
                                raise KeyError

                            # check for duplicate state
                            if d_contractid == line_contract_id and d_start == start_date and d_end == end_date:
                                print '\t[!] Duplicate found. Purchase ' \
                                      'for SKU "%s" and "%s" with end date "%s" ' \
                                      'order_id: %s and line_no: %s' % (serial, line_contract_id, end_date, d_purchase_id, d_line_no)

                        except KeyError:
                            self.d42_rest.upload_data(data)
                            data.clear()
