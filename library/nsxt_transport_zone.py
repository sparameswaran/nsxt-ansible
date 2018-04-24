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
    from com.vmware.nsx.model_client import TransportZone
    from com.vmware.nsx.model_client import Tag
    from com.vmware.nsx_client import TransportZones

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

def listTransportZones(module, stub_config):
    tz_list = []
    try:
        tz_svc = TransportZones(stub_config)
        tz_list = tz_svc.list()
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error listing Transport Zones: %s'%(api_error.error_message))
    return tz_list

def getTransportZoneByName(module, stub_config):
    result = listTransportZones(module, stub_config)
    for vs in result.results:
        tz = vs.convert_to(TransportZone)
        if tz.display_name == module.params['display_name']:
            return tz
    return None

def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            description=dict(required=False, type='str', default=None),
            host_switch_mode=dict(required=False, type='str', default='STANDARD', choices=['STANDARD', 'ENS']),
            host_switch_name=dict(required=True, type='str'),
            nested_nsx=dict(required=False, type='bool', default=False),
            transport_type=dict(required=False, type='str', default='OVERLAY', choices=['OVERLAY', 'VLAN']),
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
    transportzones_svc = TransportZones(stub_config)
    tz = getTransportZoneByName(module, stub_config)
    if module.params['state'] == 'present':
        if tz is None:
            new_tz = TransportZone(
                transport_type=module.params['transport_type'],
                display_name=module.params['display_name'],
                description=module.params['description'],
                host_switch_name=module.params['host_switch_name'],
                host_switch_mode=module.params['host_switch_mode'],
                nested_nsx=module.params['nested_nsx'],
                tags=tags
            )
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(new_tz), id="1111")
            new_tz = transportzones_svc.create(new_tz)
            module.exit_json(changed=True, object_name=module.params['display_name'], id=new_tz.id, message="Transport Zone with name %s created!"%(module.params['display_name']))
        elif tz:
            if tags != tz.tags:
                tz.tags=tags
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(tz), id=tz.id)
                new_tz = transportzones_svc.update(tz.id, tz)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=new_tz.id, message="Transport Zone with name %s has changed tags!"%(module.params['display_name']))
            module.exit_json(changed=False, object_name=module.params['display_name'], id=tz.id, message="Transport Zone with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":
        if tz:
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(tz), id=tz.id)
            transportzones_svc.delete(tz.id)
            module.exit_json(changed=True, object_name=module.params['display_name'], message="Transport Zone with name %s deleted!"%(module.params['display_name']))
        module.exit_json(changed=False, object_name=module.params['display_name'], message="Transport Zone with name %s doe not exist!"%(module.params['display_name']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
