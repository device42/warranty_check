# Warranty check

## About Device42
[Device42](http://www.device42.com) is a comprehensive data center inventory management and IP Address management software that integrates centralized password management, impact charts and applications mappings with IT asset management.

## Intro
This script checks warranty status for Dell, HP, IBM, Lenovo and Meraki manufactured devices stored in Device42.

## Prerequisites
In order for this script to check warranty status of the device, the device must have hardware model and serial number entered in Device42. Dell Warranty Status API key must be acquired as well.
- Device42 Hardware model must have "Cisco", "Dell", "Hewlett Packard", "IBM", "LENOVO" or "Meraki" in it's manufacturer data.
- Device42 Serial number must be set to "Cisco", "Dell", "Hewlett Packard", "IBM", "LENOVO" or "Meraki" device serial number.
- Cisco's client id and client secret can be obtained by completing their on-boarding form. Please follow the instructions from here: https://www.cisco.com/c/en/us/support/docs/services/sntc/onboarding_guide.html instructions for enabling the Cisco support APIs can be found here: https://apiconsole.cisco.com/documentation
- Dell's client id and client secret can be obtained by filling the on-boarding form. New and existing API users will need to register an account with TechDirect. Please check: http://en.community.dell.com/dell-groups/supportapisgroup/
- HP's API key can be obtained by filling the on-boarding form. Please, follow the instructions from here: https://developers.hp.com/css-enroll
- Merakis API key can be obtained by going to the organization > settings page on the Meraki dashboard. Ensure that the enable access to API checkbox is selected then go to your profile to generate the API key. Please check https://developer.cisco.com/meraki/api/#/rest/getting-started/what-can-the-api-be-used-for
## Plans
- Include life_cycle event to register the purchase date. Unfortunately it can’t can done now, as I can’t easily compare purchases with the information found at dell. The life_cycle event doesn’t give back the serial, only the devicename. It would be nice if the serial_no could be added to the output of GET /api/1.0/lifecycle_event/

## Gotchas
- If either hardware model or serial # is missing, warranty status won't be checked for device.
- IBM script points to warranty info not related to the SKU, serial given
- If a Meraki product has a licence with a renewal required state, the expiration date will be set to the current date

## Usage
- Set required parameters in warranty.cfg file and run starter.py script:

## Linux Usage
- Install pip depend on your distro.
- Run `pip install requests`
- Run `python starter.py`

## Windows Usage
- Download the pip installer: [https://bootstrap.pypa.io/get-pip.py](https://bootstrap.pypa.io/get-pip.py)
- Open a console in the download folder as Admin and run `get-pip.py`.
- Add the path to your environment : "%PythonFolder%\Scripts"
- Run `pip install requests`
- Run `python starter.py`

## Compatibility
* requests module required
* Script runs on Linux and Windows
* Python 2.7

## Updates
10/10/19 - Updated Dell warranty sync to use version 5 of their API (OAuth2.0), Version 4 EOL is scheduled for 12/15/19, Please update before this date