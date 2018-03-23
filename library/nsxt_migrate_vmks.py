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
    from com.vmware.nsx.model_client import HostNode
    from com.vmware.nsx_client import TransportNodes
    from com.vmware.nsx_client import TransportZones
    from com.vmware.nsx.model_client import TransportZone
    from com.vmware.nsx.model_client import TransportNode
    from com.vmware.nsx.model_client import Pnic
    from com.vmware.nsx_client import LogicalSwitches
    from com.vmware.nsx.model_client import LogicalSwitch

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


def migrateVmks(module, stub_config):
    node = getTransportNodeByName(module, stub_config)
    ls_list = module.params["vlan_logical_switches"].split(',')
    ls_ids=""
    for ls in ls_list:
        ls_ids+=(getLogicalSwitchIdByName(module, ls, stub_config)).strip()+","
    ls_ids = ls_ids[:-1]
    tn_svc = TransportNodes(stub_config)

    try:
        rs = tn_svc.update(node.id, node, ls_ids, module.params["vmks"])
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error migratin VMKs on Trnaport Node: %s'%(api_error.error_message))
    if module.params["pnics"]:
        pnic_list = []
        for key, value in module.params["pnics"].items():
            pnic=Pnic(device_name=value, uplink_name=key)
            pnic_list.append(pnic)
        migrated_node = getTransportNodeByName(module, stub_config)
        migrated_node.host_switches[0].pnics=pnic_list
        time.sleep(10)

        try:
            rs = tn_svc.update(migrated_node.id, migrated_node)
        except Error as ex:
            api_error = ex.data.convert_to(ApiError)
            module.fail_json(msg='API Error updating Trnaport Node: %s'%(api_error.error_message))
        module.exit_json(changed=True, id=node.id, name=node.display_name, pnics="updated",message="%s migrated to %s"%(module.params["vmks"], module.params["vlan_logical_switches"]))

    module.exit_json(changed=True, id=node.id, name=node.display_name, pnics="not updated",message="%s migrated to %s"%(module.params["vmks"], module.params["vlan_logical_switches"]))


def listLogicalSwitches(module, stub_config):
    ls_list = []
    try:
        logicalswitches_svc = LogicalSwitches(stub_config)
        ls_list = logicalswitches_svc.list()
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error listing Logical Switchess: %s'%(api_error.error_message))
    return ls_list


def getLogicalSwitchIdByName(module, ls_name, stub_config):
    result = listLogicalSwitches(module, stub_config)
    lsid = ""
    for vs in result.results:
        fn = vs.convert_to(LogicalSwitch)
        if fn.display_name == ls_name:
            lsid = fn.id
    if len(lsid) < 5:
        module.fail_json(msg='No Logical Switch with name %s found!'%(ls_name))
    return lsid

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


def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            vlan_logical_switches=dict(required=True, type='str'),
            vmks=dict(required=True, type='str'),
            pnics=dict(required=False, type='dict'),
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

    migrateVmks(module, stub_config)



from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
