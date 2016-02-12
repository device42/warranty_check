import requests
import base64

class Device42():
    def __init__(self, d42_username, d42_password, d42_url, debug, retry):
        self.username = d42_username
        self.password = d42_password
        self.url      = d42_url
        self.debug    = debug
        self.retry    = retry

    def upload_data(self, data):
        path = '/api/1.0/purchases/'
        url = self.url + path
        payload = data
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r = requests.post(url, data=payload, headers=headers, verify=False)

        if self.debug:
            print '[+] Posting data: %s'  % str(payload)
            print '\t[*] Status code: %d' % r.status_code
            print '\t[*] Response: %s'    % str(r.text)
        return r.json()

    def get_data(self, path):
        url  = self.url + path
        for x in range(self.retry):
            try:
                r       = requests.get(url, auth=(self.username, self.password), verify=False)
                return r.json()
            except requests.RequestException as e:
                msg     = str(e)
                print '\n[!] HTTP error. Message was: %s' % msg

    def get_serials(self):
        print '\n[!] Fetching serials from Device42'
        api_path = "api/1.0/devices/all"
        cols     = "?include_cols=serial_no,device_id,manufacturer"
        path     = api_path + cols
        response = self.get_data(path)
        return response

    def get_purchases(self):
        print '\n[!] Fetching order numbers from Device42'
        path     = '/api/1.0/purchases/'
        response = self.get_data(path)
        return response
