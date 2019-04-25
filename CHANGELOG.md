## 25.04.2019
- ordernumbers: Added shipdate option in warranty.cfg for dell systems. This due to dell removing the orderno from the api output
- if an existing registration exists, make use of that order number to compare/register
- ordernumbers: instead of vendor set common as default. Though might want to set descrete as default, or skipdate. Device42 doesn't show more than 1000 lines in the webbgui overview of an order.
- Defaulting to Dell API production url
- Debug output shows proper serials, not including the \_epoch
- Using DOQL for getting existing purchases to speed up script execution
- added boolean for DOQL and DEBUG (debug existed, but now also works in starter.py)
- bugfix: corrected hasher comparison
- bugfix: corrected working of the booleans (true/false actually works now)
- Dell API: increased api retry to 60secs
- bugfix: If no purchaselines are returned the script will stop (can be forced to go on with boolean forcedupdate in warranty.cfg). Reason for doing: noticed sometimes the query didn't give purchaselines, just ordernumbers. In that case the script would continue and make double entries.


## 30.04.2017
- service type field has been extended in version 13.1.0.
- Added an option to force updating the line items. Needed as the Service Type does not get updated otherwise as the contents of the field can't be checked via the api to see if it needs a change.
- Using offset per 50 requests instead of 100. The Dell API seems to limit response to 80 serials. For every 100 requests no info came back for the last 20 serials.

## Previous changes
- Moved from just showing last date to showing all warranties and services found in the api call
- Comparison on existence of registration per purchase/support info (per line on the order) based on serial, line contract id and contract end date
- Moved from querying ALL devices to just querying the devices from the vendor itself (so skipping virtual machines and other manufacturers)
- Using offset per 100 requests instead of doing a full request of all devices
- Brief pause per api call to prevent blockage at the api request site (1 second pause per api call)
- Making a remark if the session for the api call is unauthorized (http code 401)
- Added section to also update systems which have had their serials numbers changed due to a life_cycle event.
- Added a service_level_group for dell equipment as that also has warranty contracts
