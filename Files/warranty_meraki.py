import copy
from datetime import datetime, timedelta
import sys
import time
import random
import json
import requests

from shared import DEBUG, RETRY, ORDER_NO_TYPE, left
from warranty_abstract import WarrantyBase

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class Meraki(WarrantyBase, object):

    def __init__(self, params):
        super(Meraki, self).__init__()
        self.url = params['url']
        self.api_key = params['api_key']
        self.debug = DEBUG
        self.retry = RETRY
        self.order_no = ORDER_NO_TYPE
        self.d42_rest = params['d42_rest']
        self.common = None

        if self.order_no == 'common':
            self.common = self.generate_random_order_no()

        # API Endpoints
        self.organization_endpoint = "/organizations"
        self.networks_endpoint = "/networks"
        self.devices_endpoint = "/devices"
        self.license_state_endpoint = "/licenseState"

        # API Call Throttler
        self.API_call_limit = 1
        self.API_execution_delay = 5
        self.API_requests_made = 1
        self.last_api_call = None

    def run_warranty_check(self, inline_serials, retry=True):
        # Every Time we run a warranty check task preprocess data so that remainder of warranty check is done locally
        licence_states, organization_devices, all_devices = self.pre_process_meraki_data()

        # if any of these values are None then stop warranty check because there was an error somewhere
        if licence_states is None or organization_devices is None or all_devices is None:
            return None

        # making sure the warranty also gets updated if the serial has been changed by decom lifecycle process
        global full_serials
        full_serials = {}

        inline_serials = inline_serials.split(',')

        if self.debug is True:
            print '\t[+] Checking warranty info for "%s"' % inline_serials

        result = {'inline_serials': inline_serials, 'license': licence_states,
                  'devices_by_organization': organization_devices, 'all_devices': all_devices}

        return result

    def process_result(self, result, purchases):
        if self.debug is True:
            print '\t[+] Processing Results for Meraki Warranty Check'

        all_data = []
        inline_serials = result['inline_serials']
        license = result['license']
        # organization_devices = result['devices_by_organization']  realize that this is only useful for logging
        all_devices = result['all_devices']

        # only taking actions on devices that are populated in D42
        for serial_number in inline_serials:
            if serial_number in all_devices:
                organization_id = all_devices[serial_number]
                license_expiration = license[organization_id]

                data = {}

                if self.order_no == 'common':
                    order_no = self.common
                else:
                    order_no = self.generate_random_order_no()

                data.update({'order_no': order_no})
                data.update({'completed': 'yes'})
                data.update({'vendor': 'Meraki'})
                data.update({'line_device_serial_nos': serial_number})
                data.update({'line_type': 'contract'})
                data.update({'line_item_type': 'device'})
                data.update({'line_completed': 'yes'})

                # warranty - Note: Meraki product warranties are a combined average so there is no way of knowing start
                # date for a particular device
                data.update({'line_contract_type': 'Warranty'})
                data.update({'line_start_date': '2006-01-01'})
                data.update({'line_end_date': license_expiration})

                all_data.append(copy.deepcopy(data))

                # Easter Egg: start date in hash is the year meraki was founded
                hasher = serial_number + "2006-01-01" + license_expiration

                try:
                    d_purchase_id, d_order_no, d_line_no, d_contractid, d_start, d_end, forcedupdate = purchases[hasher]

                    if forcedupdate:
                        data['purchase_id'] = d_purchase_id
                        data.pop('order_no')
                        raise KeyError

                    # check for duplicate state
                    if d_start == "2006-01-01" and d_end == license_expiration:
                        print '\t[!] Duplicate found. Purchase ' \
                              'for SKU "%s" with end date "%s" ' \
                              'is already uploaded' % (serial_number, license_expiration)
                except KeyError:
                    self.d42_rest.upload_data(data)
                    data.clear()

        # Debug
        """
        test_data = {}
        test_data.update({'order_no': self.generate_random_order_no()})
        test_data.update({'completed': 'yes'})
        test_data.update({'vendor': 'Meraki'})
        test_data.update({'line_device_serial_nos': 'FOC1252W6EW'})
        test_data.update({'line_type': 'contract'})
        test_data.update({'line_contract_type': 'Warranty'})
        test_data.update({'line_item_type': 'device'})
        test_data.update({'line_completed': 'yes'})

        # warranty
        test_data.update({'line_start_date': '2006-01-01'})
        test_data.update({'line_end_date': '2019-08-28'})
        all_data.append(copy.deepcopy(test_data))

        if self.debug is True:
            print
            print 'Test Data'
            print test_data
            print

            # Easter Egg: start date in hash is the year meraki was founded
            hasher = "FOC1252W6EW" + "2006-01-01" + "2019-08-28"

            try:
                d_purchase_id, d_order_no, d_line_no, d_contractid, d_start, d_end, forcedupdate = purchases[hasher]

                if forcedupdate:
                    test_data['purchase_id'] = d_purchase_id
                    test_data.pop('order_no')
                    raise KeyError

                # check for duplicate state
                if d_start == "2006-01-01" and d_end == license_expiration:
                    print '\t[!] Duplicate found. Purchase ' \
                          'for SKU "%s" with end date "%s" ' \
                          'is already uploaded' % (serial_number, license_expiration)
            except KeyError:
                self.d42_rest.upload_data(test_data)
                test_data.clear()
        """

    # keeps track of the last time api call was made to ensure we dont get a 'too many requests' status code
    # also keeps track of the number of requests being made because the api allows 5 requests a second
    def meraki_request_throttler(self):

        if self.last_api_call is not None:
            if(datetime.utcnow() - self.last_api_call).total_seconds() < self.API_call_limit:
                if self.API_requests_made % 5 == 0:
                    if self.debug is True:
                        print "Meraki request throttler delaying requests for 5 seconds"
                    time.sleep(self.API_execution_delay)

        # record the new last request time and increment the number of requests made by one
        self.last_api_call = datetime.utcnow()
        self.API_requests_made += 1

    # Pre process uses Cisco Meraki API to gather license information contained within Meraki. Since licence
    # information is associated with an organization and not a device we work backwards by getting all the organizations
    # associated with an API key. We then obtain the networks associated with each organization and then finally the
    # devices associated with each network. With the constructed data we can cross reference devices in d42 and update
    # them accordingly with information regarding the license state of the organization they are a part of
    def pre_process_meraki_data(self, retry=True, timeout=15):
        # gets a combined list of all the organization ids associated with the meraki access token
        all_organization_ids = self.get_all_organizations(retry, timeout)
        if all_organization_ids is None:
            return None

        # gets license for all organizations and adds it to a dictionary
        # {organization id: days_remaining}
        all_licence_states = self.get_license_state_all_organizations(all_organization_ids, retry, timeout)

        if all_licence_states is None:
            return None

        # gets all the devices in each organization and creates a dictionary to find what organization each device is a
        # part of --> all_devices = all_organization_devices{serial_number: organization_id, serial_number: ...}
        # all organizations --> {organization_id: serial_number, serial_number, sserial_number}
        all_organization_devices, all_devices = self.get_all_device_serial_numbers(all_organization_ids, retry, timeout)

        if all_organization_devices is None:
            return None

        if self.debug is True:
            print
            print 'Organization IDs: ' + str(all_organization_ids)
            print 'License Days Remaining: ' + str(all_licence_states)
            print 'Organization Devices: ' + str(all_organization_devices)
            print 'All Devices: ' + str(all_devices)
            if len(all_devices) == 0:
                print
                print "[!] There are no Cisco Meraki devices associated with the given access key"
                print "[!] No purchase order will be created or updated"
            print

        return all_licence_states, all_organization_devices, all_devices

    def get_license_state_all_organizations(self, all_organization_ids, retry, timeout):
        all_license_states = {}

        headers = {
            'X-Cisco-Meraki-API-Key': self.api_key
        }

        if self.debug is True:
            print '\t\t[+] Getting license states for all organizations '

        for organization_id in all_organization_ids:
            try:
                resp = requests.get(self.url + self.organization_endpoint + '/' + organization_id +
                                    self.license_state_endpoint, headers=headers, timeout=timeout)
                result = self.process_get_response(resp, retry)
            except requests.RequestException as e:
                self.error_msg(e)
                return None

            if result is None:
                return None

            # Checks to see if expiration date field is valid and converts it to days remaining, adds it to a dictionary
            # with key organization_id and value days remaining on licence
            if 'expirationDate' in result:
                if result['expirationDate'] == "N/A":
                    days_remaining = datetime.utcnow().strftime("%Y-%m-%d")
                else:
                    days_remaining = self.meraki_date_parser(result['expirationDate'])  # TODO make sure this works

                all_license_states[organization_id] = days_remaining

        return all_license_states

    def get_all_organizations(self, retry, timeout):
        all_organization_ids = []

        headers = {
            'X-Cisco-Meraki-API-Key': self.api_key
        }

        if self.debug is True:
            print '\t\t[+] Getting all organization IDs '

        try:
            resp = requests.get(self.url + self.organization_endpoint, headers=headers, timeout=timeout)
            result = self.process_get_response(resp, retry)
        except requests.RequestException as e:
            self.error_msg(e)
            return None

        if result is None:
            return None

        # adds all the organization ids retrieved from the request to a combined list
        for organization in result:
            if 'id' in organization:
                all_organization_ids.append(organization['id'])

        return all_organization_ids

    def get_all_device_serial_numbers(self, all_organization_ids, retry, timeout):
        all_organizations = {}
        devices_in_network = []

        all_devices = {}

        headers = {
            'X-Cisco-Meraki-API-Key': self.api_key
        }

        if self.debug is True:
            print '\t\t[+] Getting all device serial numbers '

        for organization_id in all_organization_ids:
            try:
                resp = requests.get(self.url + self.organization_endpoint + '/' + organization_id + '/' +
                                    self.devices_endpoint, headers=headers, timeout=timeout)
                result = self.process_get_response(resp, retry)
            except requests.RequestException as e:
                self.error_msg(e)
                continue

            if result is None:
                return None

            # adds all the devices retrieved from the request to a dictionary with key serial number, value organization
            for device in result:
                if 'serial' in device:
                    all_devices[device['serial']] = organization_id  # add device to all devices dictionary for later

            # adds a list of all the devices in an organization to a dictionary
            all_organizations[organization_id] = result

        return all_organizations, all_devices

    """
    Status Codes
    400: Bad Request- You did something wrong, e.g. a malformed request or missing parameter.
    403: Forbidden- You don't have permission to do that.
    404: Not found- No such URL, or you don't have access to the API or organization at all. 
    429: Too Many Requests- You submitted more than 5 calls in 1 second to an Organization, triggering rate limiting. 
    """
    def process_get_response(self, resp, retry):

        self.meraki_request_throttler()

        msg = 'Status code: %s' % str(resp.status_code)

        if str(resp.status_code) == '429' or str(resp.status_code) == '404':
            print 'HTTP error. Message was: %s' % msg
            print 'waiting for 10 seconds to let the api server calm down'
            # suspecting blockage due to to many api calls or missing organization privileges
            # wait 10 seconds and continue
            time.sleep(10)
            if retry:
                print 'Retrying...'
                self.pre_process_meraki_data(False)
            else:
                return None
        elif str(resp.status_code) == '400' or str(resp.status_code) == '403':
            # bad request or incorrect API key
            print 'HTTP error. Message was: %s' % msg
            print 'Malformed request or incorrect API Key'
            return None
        else:
            result = resp.json()
            return result

    @staticmethod
    def meraki_date_parser(meraki_date):
        meraki_date.replace(',', '')
        date_items = meraki_date.split(' ')

        month = date_items[0]
        day = date_items[1]
        year = date_items[2]

        d42_date_format = year + '-' + month + '-' + day

        return d42_date_format

