#!/usr/bin/env python
# coding=utf-8
#
# Copyright © 2018 VMware, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions
# of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
# TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

__author__ = 'yasensim'


import requests, time
try:
    from com.vmware.nsx.transport_nodes_client import State
    from com.vmware.nsx_client import TransportNodes
    from com.vmware.nsx_client import TransportZones
    from com.vmware.nsx_client import HostSwitchProfiles
    from com.vmware.nsx.model_client import TransportZone
    from com.vmware.nsx.model_client import TransportZoneEndPoint
    from com.vmware.nsx.model_client import TransportNode
    from com.vmware.nsx.model_client import HostSwitchSpec
    from com.vmware.nsx.model_client import HostSwitch
    from com.vmware.nsx.model_client import HostSwitchProfileTypeIdEntry
    from com.vmware.nsx.model_client import UplinkHostSwitchProfile
    from com.vmware.nsx.model_client import Pnic

    from com.vmware.vapi.std.errors_client import NotFound
    from vmware.vapi.lib import connect
    from vmware.vapi.security.user_password import \
        create_user_password_security_context
    from vmware.vapi.stdlib.client.factories import StubConfigurationFactory
    from com.vmware.nsx.model_client import ApiError
    from com.vmware.vapi.std.errors_client import Error
    HAS_PYNSXT = True
except ImportError:
    HAS_PYNSXT = False


def getTransportZoneEndPoint(module, stub_config):
    tz_endpoints = []
    transportzones_svc = TransportZones(stub_config)
    try:
        tzs = transportzones_svc.list()
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.exit_json(changed=False, message="Error listing Transport Zones: "%(api_error))

    for tz_name in module.params['transport_zone_endpoints']:
        for vs in tzs.results:
            fn = vs.convert_to(TransportZone)
            if fn.display_name == tz_name:
                ep=TransportZoneEndPoint(transport_zone_id=fn.id)
                tz_endpoints.append(ep)
    return tz_endpoints

def getUplinkProfileId(module, stub_config):
    hsp_svc = HostSwitchProfiles(stub_config)
    try:
        hsps = hsp_svc.list()
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.exit_json(changed=False, message="Error listing Transport Zones: "%(api_error))

    for vs in hsps.results:
        fn = vs.convert_to(UplinkHostSwitchProfile)
        if fn.display_name == module.params['uplink_profile']:
            return fn.id

def createTransportNode(module, stub_config):
    tz_endpoints=getTransportZoneEndPoint(module, stub_config)
    uplink_profile_id=getUplinkProfileId(module, stub_config)
    hsptie=HostSwitchProfileTypeIdEntry(
        key=HostSwitchProfileTypeIdEntry.KEY_UPLINKHOSTSWITCHPROFILE,
        value=uplink_profile_id
    )
    hsprof_list = []
    hsprof_list.append(hsptie)

    pnic_list = []
    for key, value in module.params["pnics"].items():
        pnic=Pnic(device_name=value, uplink_name=key)
        pnic_list.append(pnic)

    hs=HostSwitch(
        host_switch_name=module.params["host_switch_name"],
        host_switch_profile_ids=hsprof_list,
        pnics=pnic_list,
        static_ip_pool_id=module.params["static_ip_pool_id"]
    )
    hs_list= []
    hs_list.append(hs)
    tn_svc = TransportNodes(stub_config)
    transport_node=TransportNode(
        display_name=module.params['display_name'],
        host_switches=hs_list,
        node_id=module.params['node_id'],
        transport_zone_endpoints=tz_endpoints
    )
    try:
        rs = tn_svc.create(transport_node)
        tnode_status = checkTnodeStatus(rs, stub_config)
        if tnode_status == "UP":
            return rs
        elif tnode_status == "DOWN":
            module.fail_json(msg='Transport Node %s Status is Down!'%(module.params["display_name"]))
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg="API Error creating Transport Node: %s "%(api_error))
    return rs


def updateTransportNode(module, stub_config):
    changed = False
    node = getTransportNodeByName(module, stub_config)

    pnic_list = []
    for key, value in module.params["pnics"].items():
        pnic=Pnic(device_name=value, uplink_name=key)
        pnic_list.append(pnic)

    if pnic_list != node.host_switches[0].pnics:
        changed = True

    tz_endpoints=getTransportZoneEndPoint(module, stub_config)
    if len(tz_endpoints) != len(node.transport_zone_endpoints):
        changed = True
    isThere = False
    uplink_profile_id=getUplinkProfileId(module, stub_config)
    for prof_id in node.host_switches[0].host_switch_profile_ids:
        if uplink_profile_id == prof_id.value:
            isThere = True
    if not isThere:
        changed = True
    if node.host_switches[0].static_ip_pool_id != module.params["static_ip_pool_id"]:
        changed = True
    if changed:
        hsptie=HostSwitchProfileTypeIdEntry(
            key=HostSwitchProfileTypeIdEntry.KEY_UPLINKHOSTSWITCHPROFILE,
            value=uplink_profile_id
        )
        hsprof_list = []
        hsprof_list.append(hsptie)

        hs=HostSwitch(
            host_switch_name=module.params["host_switch_name"],
            host_switch_profile_ids=hsprof_list,
            pnics=pnic_list,
            static_ip_pool_id=module.params["static_ip_pool_id"]
        )
        hs_list= []
        hs_list.append(hs)
        tn_svc = TransportNodes(stub_config)
        node.host_switches=hs_list
        node.transport_zone_endpoints=tz_endpoints
        try:
            rs = tn_svc.update(node.id, node)
        except Error as ex:
            api_error = ex.data.convert_to(ApiError)
            module.fail_json(msg="API Error updating Transport Node: %s "%(api_error))
    return changed


def checkTnodeStatus(tnode, stub_config):
    time.sleep(5)
    state_svc = State(stub_config)
    counter = 10
    while (state_svc.get(tnode.id)).state != "success":
        counter=counter-1
        time.sleep(5)
        if counter == 0:
            return "DOWN"
    return "UP"


def listTransportNodes(module, stub_config):
    try:
        fabricnodes_svc = TransportNodes(stub_config)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error listing nodes: %s'%(api_error.error_message))
    return fabricnodes_svc.list()


def getTransportNodeByName(module, stub_config):
    result = listTransportNodes(module, stub_config)
    for vs in result.results:
        fn = vs.convert_to(TransportNode)
        if fn.display_name == module.params['display_name']:
            return fn
    return None

def deleteTransportNode(module, node, stub_config):
    fnodes_svc = TransportNodes(stub_config)
    node_id = node.id
    node_name = node.display_name
    try:
        fnodes_svc.delete(node_id)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error Deleting node: %s'%(api_error.error_message))
    time.sleep(5)
    module.exit_json(changed=True, id=node.id, object_name=node_name)

#def updateMaintenanceMode(desired, node, stub_config):
#    action = TransportNode.MAINTENANCE_MODE_DISABLED
#    if desired.upper() == "ENABLED":
#        action = TransportNode.MAINTENANCE_MODE_ENABLED
#    elif desired.upper() == "FORCE_ENABLED":
#        action = TransportNode.MAINTENANCE_MODE_FORCE_ENABLED
#    action="ENABLED"
#    tn_svc = TransportNodes(stub_config)
#    tn_svc.updatemaintenancemode(node.id, action)



def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            node_id=dict(required=True, type='str'),
            maintenance_mode=dict(required=False, type='str', choices=['DISABLED', 'ENABLED', 'FORCE_ENABLED']),
            static_ip_pool_id=dict(required=True, type='str'),
            host_switch_name=dict(required=False, type='str'),
            transport_zone_endpoints=dict(required=False, type='list'),
            pnics=dict(required=False, type='dict'),
            uplink_profile=dict(required=False, type='str'),
            state=dict(required=False, type='str', default="present", choices=['present', 'absent']),
            nsx_manager=dict(required=True, type='str'),
            nsx_username=dict(required=True, type='str'),
            nsx_passwd=dict(required=True, type='str', no_log=True)
        ),
        supports_check_mode=False
    )

    if not HAS_PYNSXT:
        module.fail_json(msg='pynsxt is required for this module')
    session = requests.session()
    session.verify = False
    nsx_url = 'https://%s:%s' % (module.params['nsx_manager'], 443)
    connector = connect.get_requests_connector(
        session=session, msg_protocol='rest', url=nsx_url)
    stub_config = StubConfigurationFactory.new_std_configuration(connector)
    security_context = create_user_password_security_context(module.params["nsx_username"], module.params["nsx_passwd"])
    connector.set_security_context(security_context)
    requests.packages.urllib3.disable_warnings()

    if module.params['state'] == "present":
        node = getTransportNodeByName(module, stub_config)
        if node is None:
            result = createTransportNode(module, stub_config)
            module.exit_json(changed=True, object_name=module.params['display_name'], id=result.id, body=str(result))
        else:
            changed = False
#            if module.params["maintenance_mode"]:
#                if module.params["maintenance_mode"].upper() != node.maintenance_mode:
#                    changed = True
#                    updateMaintenanceMode(module.params["maintenance_mode"], node, stub_config)
#
            changed=updateTransportNode(module, stub_config)
            if changed:
                module.exit_json(changed=True, object_name=module.params['display_name'], id=node.id, message="Transport Node with name %s has been modified!"%(module.params['display_name']))
            module.exit_json(changed=False, object_name=module.params['display_name'], id=node.id, message="Transport Node with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":
        node = getTransportNodeByName(module, stub_config)
        if node is None:
            module.exit_json(changed=False, object_name=module.params['display_name'], message="No Transport Node with name %s"%(module.params['display_name']))
        else:
            deleteTransportNode(module, node, stub_config)



from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
