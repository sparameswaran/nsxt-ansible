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
    from com.vmware.nsx.model_client import LogicalRouter
    from com.vmware.nsx_client import LogicalRouters
    from com.vmware.nsx.model_client import HaVipConfig
    from com.vmware.nsx.model_client import VIPSubnet
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


def listLogicalRouters(module, stub_config):
    lr_list = []
    try:
        lr_svc = LogicalRouters(stub_config)
        lr_list = lr_svc.list()
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error listing Logical Routers: %s'%(api_error.error_message))
    return lr_list

def getLogicalRouterByName(module, stub_config):
    result = listLogicalRouters(module, stub_config)
    for vs in result.results:
        lr = vs.convert_to(LogicalRouter)
        if lr.display_name == module.params['t0_router']:
            return lr
    return None



def main():
    module = AnsibleModule(
        argument_spec=dict(
            vip_address=dict(required=True, type='str'),
            enabled=dict(required=False, type='bool', default=True),
            t0_router=dict(required=True, type='str'),
            redundant_uplink_port_ids=dict(required=True, type='list'),
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

    lr_svc = LogicalRouters(stub_config)
    lr = getLogicalRouterByName(module, stub_config)
    subnet_list = []
    subnet = module.params['vip_address'].split('/')
    new_subnet = VIPSubnet(active_vip_addresses=[subnet[0]], prefix_length=int(subnet[1]))
    subnet_list.append(new_subnet)

    haVipConfig = [HaVipConfig(
			enabled=module.params['enabled'], 
			ha_vip_subnets=subnet_list, 
			redundant_uplink_port_ids=module.params['redundant_uplink_port_ids']
		)]


    if module.params['state'] == 'present':
        if lr.advanced_config.ha_vip_configs is None:
            lr.advanced_config.ha_vip_configs=haVipConfig
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(lr), id="1111")
            try:
                new_lr = lr_svc.update(lr.id, lr)
                module.exit_json(changed=True, object_name=module.params['vip_address'], id=lr.id, message="VIP for Logical Router with name %s was created!"%(lr.display_name))
            except Error as ex:
                api_error = ex.data.convert_to(ApiError)
                module.fail_json(msg='API Error creating VIP: %s'%(str(api_error.error_message)))
        elif lr.advanced_config.ha_vip_configs != haVipConfig:
                lr.advanced_config.ha_vip_configs=haVipConfig
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(lr), id=lr.id)
                new_lr = lr_svc.update(lr.id, lr)
                module.exit_json(changed=True, object_name=module.params['vip_address'], id=lr.id, message="VIP for Logical Router with name %s has been changed!"%(lr.display_name))
        module.exit_json(changed=False, object_name=module.params['vip_address'], id=lr.id, message="VIP Logical Router with name %s already exists!"%(lr.display_name))

    elif module.params['state'] == "absent":

        if lr.advanced_config.ha_vip_configs:
            try:
                lr.advanced_config.ha_vip_configs=None
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(lr), id=lr.id)
                new_lr = lr_svc.update(lr.id, lr)
                module.exit_json(changed=True, object_name=module.params['vip_address'], id=lr.id, message="VIP for Logical Router with name %s was deleted!"%(lr.display_name))

            except Error as ex:
                api_error = ex.date.convert_to(ApiError)
                module.fail_json(msg='API Error deleting Logical Router VIP: %s'%(api_error.error_message))

        module.exit_json(changed=False, object_name=module.params['vip_address'], message="Logical Router VIP  %s does not exist!"%(module.params['vip_address']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
