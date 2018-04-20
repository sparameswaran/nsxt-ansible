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
    from com.vmware.nsx.model_client import Tag
    from com.vmware.nsx.model_client import LogicalRouterDownLinkPort
    from com.vmware.nsx_client import LogicalRouterPorts
    from com.vmware.nsx.model_client import ResourceReference
    from com.vmware.nsx.model_client import IPSubnet

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

def listLogicalRouterPorts(module, stub_config):
    lrp_list = []
    try:
        lrp_svc = LogicalRouterPorts(stub_config)
        lrp_list = lrp_svc.list(logical_router_id=module.params['logical_router_id'], resource_type='LogicalRouterDownLinkPort')
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error listing Logical Router Ports: %s'%(api_error.error_message))
    return lrp_list

def getLogicalRouterPortByName(module, stub_config):
    result = listLogicalRouterPorts(module, stub_config)
    for vs in result.results:
        lrp = vs.convert_to(LogicalRouterDownLinkPort)
        if lrp.display_name == module.params['display_name']:
            return lrp
    return None

def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            description=dict(required=False, type='str', default=None),
            logical_router_id=dict(required=True, type='str'),
            service_bindings=dict(required=False, type='str', default=None),
            linked_logical_switch_port_id=dict(required=True, type='str'),
            subnets=dict(required=True, type='list'),
            urpf_mode=dict(required=False, type='str', default='NONE', choices=['NONE', 'STRICT']),
            tags=dict(required=False, type='dict', default=None),
            state=dict(required=False, type='str', default="present", choices=['present', 'absent']),
            nsx_manager=dict(required=True, type='str'),
            nsx_username=dict(required=True, type='str'),
            nsx_passwd=dict(required=True, type='str', no_log=True)
        ),
        supports_check_mode=True
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
    tags=None
    if module.params['tags'] is not None:
        tags = []
        for key, value in module.params['tags'].items():
            tag=Tag(scope=key, tag=value)
            tags.append(tag)
    subnet_list = []
    for subnet in module.params['subnets']:
        new_subnet = IPSubnet(ip_addresses=subnet['ip_addresses'], prefix_length=int(subnet['prefix_length']))
        subnet_list.append(new_subnet)

    lrp_svc = LogicalRouterPorts(stub_config)
    lrp = getLogicalRouterPortByName(module, stub_config)
    if module.params['state'] == 'present':
        if lrp is None:
            new_lrp = LogicalRouterDownLinkPort(
                display_name=module.params['display_name'],
                description=module.params['description'],
                subnets=subnet_list,
                linked_logical_switch_port_id=ResourceReference(target_id=module.params['linked_logical_switch_port_id']),
                logical_router_id=module.params['logical_router_id'],
                service_bindings=None,
                urpf_mode=module.params['urpf_mode'],
                tags=tags
            )
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(new_lrp), id="1111")
            new_lrp_temp = lrp_svc.create(new_lrp)
            new_lrp = new_lrp_temp.convert_to(LogicalRouterDownLinkPort)
            module.exit_json(changed=True, object_name=module.params['display_name'], id=new_lrp.id, message="Logical Router Port with name %s created!"%(module.params['display_name']))
        elif lrp:
            changed = False
            if tags != lrp.tags:
                changed = True
                lrp.tags=tags
            if subnet_list != lrp.subnets:
                changed = True
                lrp.subnets=subnet_list
            if changed:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(lrp), id=lrp.id)
                new_lrp = lrp_svc.update(lrp.id, lrp)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=lrp.id, message="Logical Router Port with name %s has changed tags!"%(module.params['display_name']))
            module.exit_json(changed=False, object_name=module.params['display_name'], id=lrp.id, message="Logical Router Port with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":
        if lrp:
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(lrp), id=lrp.id)
            lrp_svc.delete(lrp.id)
            module.exit_json(changed=True, object_name=module.params['display_name'], message="Logical Router Port with name %s deleted!"%(module.params['display_name']))
        module.exit_json(changed=False, object_name=module.params['display_name'], message="Logical Router Port with name %s does not exist!"%(module.params['display_name']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
