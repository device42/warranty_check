
import re
import sys
import requests
import shared as config
from uploader import Device42
from xml.sax import saxutils as su
from BeautifulSoup import BeautifulSoup as BS

try:
    requests.packages.urllib3.disable_warnings()
except:
    pass


class IBM():
    def __init__(self, ibm_url, debug, retry, order_no_type):
        self.url    = ibm_url
        self.debug  = debug
        self.retry  = retry
        self.o_type = order_no_type
        self.data   = {}


    def run_warranty_check(self, dev_type, serial):
        if self.debug:
            print '\t[+] Checking warranty info for IBM "%s"' % serial
        for x in range(self.retry):
            try:
                url     = self.url + '?type=%s&serial=%s' % (dev_type, serial)
                resp    = requests.get(url)
                result  = resp.text
                data    = self.process_result(result, serial)
                return data
            except requests.RequestException as e:
                msg     = str(e)
                print '\n[!] HTTP error. Message was: %s' % msg


    def process_result(self, result, serial):
        soup      = BS(su.unescape(result))
        ibm_data  = {}
        try:
            table = soup.find('table', {'class':'ibm-data-table'})
            rows  = table.findAll('tr')
            data  = [[td.findChildren(text=True) for td in tr.findAll('td')] for tr in rows]

            desc            = data[1]
            modelno         = desc[0][0]
            modeltype       = desc[1][0]
            modelserial     = desc[2][0]
            warr            = data[3]
            warr_msg        = ((warr[0][0]).replace('\n', '')).replace('\n', '') # warranty message
            line_end_date   = warr[1][0]

            ibm_data.update({'vendor':'IBM'})
            ibm_data.update({'line_type':'contract'})
            ibm_data.update({'line_item_type':'device'})
            ibm_data.update({'line_device_serial_nos':serial})
            ibm_data.update({'expiration_date':line_end_date.strip()})


            if self.debug:
                print '\n------------------------'
                print '[+] Model: %s %s '   % (modeltype, modelno)
                print '\t[!] Serial: %s'    % modelserial
                print '\t[!] Status: %s'    % warr_msg.strip()
                print '\t[!] Expiration date: %s' % line_end_date

            return ibm_data

        except AttributeError:
            for rec in (result).split('\n'):
                if 'Error message' in rec:
                    rec = rec.replace('&nbsp;', ' ')
                    msg = re.sub('<[^>]*>', '', rec)
                    print '[!] Exception: Message was: '
                    print '\t%s' % msg

        except Exception as e:
            print '[!] Exception. Message was: %s' % str(e)
            pass

def main():
    # get settings from config file
    d42_username, d42_password, d42_url,\
           ibm_url, debug, retry, order_no_type = config.get_config('ibm')

    if not ibm_url.startswith('https'):
        print '[!] Error in config file. IBM URL must start with HTTPS.\n\tExiting...'
        sys.exit()
    # init
    d42  = Device42(d42_username, d42_password, d42_url, debug, retry)
    ibm = IBM(ibm_url, debug, retry, order_no_type)
    #ibm.run_warranty_check('8852','0645455')

    # get data from Device42
    orders = d42.get_purchases()
    already_there = []
    dates   = {}
    for order in orders:
        line_items =  order['line_items']
        for line_item in line_items:
            end   = line_item['line_end_date']
            start = line_item['line_start_date']
            devices = line_item['devices']
            for device in devices:
                serial = device['serial_no']
                dates.update({serial:[start,end]})
                if serial not in already_there:
                    already_there.append(serial)

    devices = d42.get_serials()
    items = [[x['device_id'],x['serial_no'],x['manufacturer']] for x in devices['Devices'] if x['serial_no'] and  x['manufacturer']]
    for item in items:
        d42_id, serial, vendor = item
        print '\t[+] IBM serial #: %s' % serial
        """
        if 'ibm' in vendor.lower():
            #if len(serial) <= 7: # testing only original DELL...remove this
            warranty = ibm.run_warranty_check(dev_type, serial)
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
        print '[!] IBM warranty check is not implemented yet.'

