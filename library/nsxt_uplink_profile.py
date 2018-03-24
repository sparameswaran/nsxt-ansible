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
    from com.vmware.nsx.model_client import IpPoolSubnet
    from com.vmware.nsx.model_client import IpPoolRange
    from com.vmware.nsx.model_client import IpPool
    from com.vmware.nsx.pools_client import IpPools
    from com.vmware.nsx.model_client import Tag

    from com.vmware.nsx_client import HostSwitchProfiles
    from com.vmware.nsx.model_client import UplinkHostSwitchProfile
    from com.vmware.nsx.model_client import TeamingPolicy
    from com.vmware.nsx.model_client import Uplink

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

def listProfiles(module, stub_config):
    prof_list = []
    try:
        hs_profile_svc = HostSwitchProfiles(stub_config)
        prof_list = hs_profile_svc.list()
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error listing Hostswitch Profiles: %s'%(api_error.error_message))
    return prof_list

def getProfileByName(module, stub_config):
    result = listProfiles(module, stub_config)
    for vs in result.results:
        prof = vs.convert_to(UplinkHostSwitchProfile)
        if prof.display_name == module.params['display_name']:
            return prof
    return None

def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            description=dict(required=False, type='str', default=None),
            mtu=dict(required=False, type='int', default=1600),
            lags=dict(required=False, type='list', default=None),
            active_list=dict(required=True, type='list'),
            standby_list=dict(required=False, type='list', default=None),
            policy=dict(required=True, type='str', choices=['FAILOVER_ORDER', 'LOADBALANCE_SRCID']),
            transport_vlan=dict(required=True, type='int'),
            tags=dict(required=False, type='dict', default=None),
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
    tags=None
    if module.params['tags'] is not None:
        tags = []
        for key, value in module.params['tags'].items():
            tag=Tag(scope=key, tag=value)
            tags.append(tag)

    uplink_type=Uplink.UPLINK_TYPE_PNIC
    if module.params['lags']:
        uplink_type=Uplink.UPLINK_TYPE_LAG

    active_list = []
    for active_uplink in module.params['active_list']:
        uplink = Uplink(active_uplink, uplink_type)
        active_list.append(uplink)

    standby_list = []
    for standby_uplink in module.params['standby_list']:
        uplink = Uplink(standby_uplink, uplink_type)
        standby_list.append(uplink)

    teaming=TeamingPolicy(active_list, module.params['policy'], standby_list)

    hs_profile_svc = HostSwitchProfiles(stub_config)
    prof = getProfileByName(module, stub_config)
    if module.params['state'] == 'present':
        if prof is None:
            new_prof = UplinkHostSwitchProfile(
                display_name=module.params['display_name'],
                description=module.params['description'],
                lags=module.params['lags'],
                mtu=module.params['mtu'],
                teaming=teaming,
                transport_vlan=module.params['transport_vlan'],
                tags=tags
            )
            new_prof = hs_profile_svc.create(new_prof)
            created_prof = getProfileByName(module, stub_config)
            module.exit_json(changed=True, object_name=module.params['display_name'], id=created_prof.id, message="Uplink Profile with name %s created!"%(module.params['display_name']))
        elif prof:
            changed = False
            if tags != prof.tags:
                changed = True
                prof.tags=tags
            if prof.teaming != teaming:
                prof.teaming = teaming
                changed = True
            if prof.mtu != module.params['mtu']:
                prof.mtu = module.params['mtu']
                changed = True
            if prof.transport_vlan != module.params['transport_vlan']:
                prof.transport_vlan = module.params['transport_vlan']
                changed = True
            if changed:
                new_prof = hs_profile_svc.update(prof.id, prof)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=prof.id, msg="Uplink Profile has been changed")
            module.exit_json(changed=False, object_name=module.params['display_name'], id=prof.id, message="Uplink Profile with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":
        hs_profile_svc.delete(prof.id)
        module.exit_json(changed=True, object_name=module.params['display_name'], message="Uplink Profile with name %s deleted!"%(module.params['display_name']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
