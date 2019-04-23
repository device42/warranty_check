#!/usr/bin/env python
import sys

from Files.shared import Config, Device42rest
from Files.warranty_dell import Dell
from Files.warranty_hp import Hp
from Files.warranty_ibm_lenovo import IbmLenovo


def get_hardware_by_vendor(name):
    # Getting the hardware models, so we specifically target the manufacturer systems registered
    hardware_models = d42_rest.get_hardware_models()
    models = []
    if hardware_models:
        for model in hardware_models['models']:
            manufacturer = model.get('manufacturer')
            if manufacturer and name not in manufacturer.lower():
                continue

            model_name = model.get('name')
            if model_name and model_name not in models:
                models.append(model_name)

    return ','.join(models)


def get_vendor_api(name):

    current_cfg = cfg.get_config(name)
    api = None

    if vendor == 'dell':
        dell_params = {
            'url': current_cfg['url'],
            'api_key': current_cfg['api_key'],
            'd42_rest': d42_rest
        }
        api = Dell(dell_params)

    elif vendor == 'hp':
        hp_params = {
            'url': current_cfg['url'],
            'api_key': current_cfg['api_key'],
            'api_secret': current_cfg['api_secret'],
            'd42_rest': d42_rest
        }
        api = Hp(hp_params)

    elif vendor == 'ibm' or vendor == 'lenovo':
        ibm_lenovo_params = {
            'url': current_cfg['url'],
            'url2': current_cfg['url2'],
            'd42_rest': d42_rest
        }
        api = IbmLenovo(vendor, ibm_lenovo_params)

    return api


def loader(name, api, d42):
    global ordernos

    # Locate the devices involved, based on the hardware models found, add offset with recursion
    offset = 0
    previous_batch = None
    while True:
        serials = []
        current_hardware_models = get_hardware_by_vendor(name)
        current_devices_batch = d42.get_devices(offset, current_hardware_models)

        # If previous batch the same as current we finish
        if previous_batch is not None:
            if previous_batch == current_devices_batch:
                print '\n[!] Finished'
                break

        previous_batch = current_devices_batch
        if current_devices_batch and 'Devices' in current_devices_batch and len(current_devices_batch['Devices']) > 0:
            items = [[x['device_id'], x['serial_no'], x['manufacturer']] for x in
                     current_devices_batch['Devices'] if x['serial_no'] and x['manufacturer']]
            for item in items:
                try:
                    d42_id, d42_serial, d42_vendor = item
                    if name in d42_vendor.lower():
                        print '[+] %s serial #: %s' % (name.title(), d42_serial)
                        serials.append(d42_serial)
                except ValueError as e:
                    print '\n[!] Error in item: "%s", msg : "%s"' % (item, e)

            inline_serials = ','.join(serials)

            if len(serials) > 0:
                result = vendor_api.run_warranty_check(inline_serials)

                if result is not None:
                    api.process_result(result, purchases, ordernos)

            offset += 50
        else:
            print '\n[!] Finished'
            break

if __name__ == '__main__':

    # get settings from config file
    cfg = Config()
    d42_cfg = cfg.get_config('d42')
    discover = cfg.get_config('discover')
    other = cfg.get_config('other')

    # init
    d42_params = {
        'username': d42_cfg['username'],
        'password': d42_cfg['password'],
        'url': d42_cfg['url']
    }
    d42_rest = Device42rest(d42_params)

    DEBUG =  bool(other['debug'])
    DOQL =  bool(other['doql'])
    #forcedupdate = bool(discover['forcedupdate'])
    if other['debug'].lower() == 'false': DEBUG=bool('')
    if other['doql'].lower()  == 'false': DOQL=bool('')
    #if discover['forcedupdate'].lower()  == 'false': forcedupdate=bool('')

    # get purchases data from Device42
    purchases = {}
    global ordernos
    ordernos  = {}

    if DOQL:
        #orders = d42_rest.get_doqldata('select purchaselineitem_pk,order_no,line_no,contract_id,contract_type_name,service_type_name,li.start_date,li.end_date,LIDEV.device_name,DEV.serial_no,li.cc_code from view_purchase_v1 PUR LEFT JOIN view_purchaselineitem_v1 LI ON PUR.purchase_pk=LI.purchase_fk LEFT JOIN view_purchaselineitems_to_devices_v1 LIDEV on (LI.purchaselineitem_pk=LIDEV.purchaselineitem_fk) LEFT JOIN view_device_v1 DEV on (LIDEV.device_fk=DEV.device_pk) WHERE order_no=\'104050847\' AND purchaselineitem_pk=23554 limit 5')
        orders = d42_rest.get_doqldata('select purchaselineitem_pk,order_no,line_no,contract_id,contract_type_name,service_type_name,li.start_date,li.end_date,LIDEV.device_name,DEV.serial_no,li.cc_code from view_purchase_v1 PUR LEFT JOIN view_purchaselineitem_v1 LI ON PUR.purchase_pk=LI.purchase_fk LEFT JOIN view_purchaselineitems_to_devices_v1 LIDEV on (LI.purchaselineitem_pk=LIDEV.purchaselineitem_fk) LEFT JOIN view_device_v1 DEV on (LIDEV.device_fk=DEV.device_pk)' )
        # 23554,104050847,4299,732-22780,Warranty,ProSupport for DataCenter/ProSup,2015-07-26,2016-11-01,prod-trid-mssql-001_1474535852.74,123456
        #if DEBUG:
        #    print orders
        orders = orders.splitlines()
        for order in orders:
            if order.split(',')[1]:
                #Check if there is a lineitem for the order. If so register the lineitem in the array
                purchase_id     = order.split(',')[0]
                order_no        = order.split(',')[1]
                line_no         = order.split(',')[2]
                contractid      = order.split(',')[3]
                contracttype    = order.split(',')[4]
                servicetype     = order.split(',')[5]
                start           = order.split(',')[6]
                end             = order.split(',')[7]
                devices         = order.split(',')[8]
                serial          = order.split(',')[9]

                # Build dictionary to compensate for Dell removing order_nos from the api output
                ordernos[serial.split('_')[0].lower()] = order_no

                if start and end and devices and contractid and serial:
                    hasher = serial.split('_')[0].lower() + contractid + start + end
                    if hasher not in purchases:
                        purchases[hasher] = [purchase_id, order_no, line_no, contractid, start, end, discover['forcedupdate']]
    else:
        orders = d42_rest.get_purchases()
        if orders and 'purchases' in orders:
            for order in orders['purchases']:
                if 'line_items' in order:
                    purchase_id = order.get('purchase_id')
                    order_no = order.get('order_no')

                    for line_item in order['line_items']:
                        line_no = line_item.get('line_no')
                        devices = line_item.get('devices')
                        contractid = line_item.get('line_notes')
                        start = line_item.get('line_start_date')
                        end = line_item.get('line_end_date')

                        if start and end and devices and contractid:
                            for device in devices:
                                if 'serial_no' in device:
                                    serial = device['serial_no']
                                    hasher = serial + contractid + start + end
                                    if hasher not in purchases:
                                        purchases[hasher] = [purchase_id, order_no, line_no, contractid, start, end, discover['forcedupdate']]

    APPS_ROW = []
    if discover['dell']:
        APPS_ROW.append('dell')
    if discover['hp']:
        APPS_ROW.append('hp')
    if discover['ibm']:
        APPS_ROW.append('ibm')
    if discover['lenovo']:
        APPS_ROW.append('lenovo')

    for vendor in APPS_ROW:
        print '\n[+] %s section' % vendor
        vendor_api = get_vendor_api(vendor)
        loader(vendor, vendor_api, d42_rest)

    sys.exit()
