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
    from com.vmware.nsx.model_client import LogicalRouter
    from com.vmware.nsx_client import LogicalRouters

    from com.vmware.nsx.logical_routers.routing_client import StaticRoutes
    from com.vmware.nsx.model_client import StaticRouteNextHop
    from com.vmware.nsx.model_client import StaticRoute

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
        if lr.display_name == module.params['router_name']:
            return lr
    return None

def listStaticRoutes(module, stub_config, lrid):
    lr_list = []
    try:
        lr_svc = StaticRoutes(stub_config)
        lr_list = lr_svc.list(logical_router_id=lrid)
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error listing Logical Routers: %s'%(api_error.error_message))
    return lr_list

def getStaticRouteByNetwork(module, stub_config, lrid):
    result = listStaticRoutes(module, stub_config, lrid)
    for vs in result.results:
        lr = vs.convert_to(StaticRoute)
        if lr.network == module.params['network']:
            return lr
    return None

def simplifyNextHopList(nextHopList):
    ipList = []
    for member in nextHopList:
        ipList.append(member.ip_address)
    return ipList


def main():
    module = AnsibleModule(
        argument_spec=dict(
            network=dict(required=True, type='str'),
            description=dict(required=False, type='str', default=None),
            next_hops=dict(required=True, type='list', default=None),
            admin_distance=dict(required=False, type='int', default=1),
            router_name=dict(required=False, type='str', default=None),
            router_id=dict(required=False, type='str', default=None),
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
    lrid = ""
    if module.params['router_id']:
        lrid = module.params['router_id']
    elif module.params['router_name']:
        lr_svc = LogicalRouters(stub_config)
        lr = getLogicalRouterByName(module, stub_config)
        lrid = lr.id
    sroute = getStaticRouteByNetwork(module, stub_config, lrid)
    next_hop_list = []
    for next_hop in module.params['next_hops']:
        staticRouteNextHop = StaticRouteNextHop(
            administrative_distance=module.params['admin_distance'],
            ip_address = next_hop,
            logical_router_port_id=None
        )
        next_hop_list.append(staticRouteNextHop)
    sr_svc = StaticRoutes(stub_config)
    if module.params['state'] == 'present':
        if sroute is None:
            new_static_route = StaticRoute(
                display_name=None,
                network=module.params['network'],
                next_hops=next_hop_list,
                description=module.params['description'],
                tags=tags
            )
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(new_static_route), id="1111")
            try:
                new_static_route = sr_svc.create(lrid, new_static_route)
                module.exit_json(changed=True, object_name=module.params['network'], id=new_static_route.id, 
                                 message="Static Route with for %s with id %s was created on router with id %s!"%(module.params['network'], new_static_route.id, lrid))
            except Error as ex:
                module.fail_json(msg='API Error creating Static Route: %s'%(str(ex)))
        elif sroute:
            changed = False
            if tags != sroute.tags:
                sroute.tags=tags
                changed = True
            nhopList1 = simplifyNextHopList(sroute.next_hops)
            nhopList2 = simplifyNextHopList(next_hop_list)
            if nhopList1 != nhopList2:
                sroute.next_hops=next_hop_list
                changed = True
            if changed:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(sroute), id=lrid)
                new_static_route = sr_svc.update(lrid, sroute.id, sroute)
                module.exit_json(changed=True, object_name=module.params['network'], id=new_static_route.id, 
                                 message="Static Route for %s has changed tags!"%(module.params['network']))
            module.exit_json(changed=False, object_name=module.params['network'], id=sroute.id, router_id=lrid, 
                             message="Static Route for %s already exists!"%(module.params['network']))

    elif module.params['state'] == "absent":
        if sroute:
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(sroute), id=lrid)
            try:
                sr_svc.delete(lrid, sroute.id)
                module.exit_json(changed=True, object_name=module.params['network'], message="Static Route for %s deleted!"%(module.params['network']))
            except Error as ex:
                api_error = ex.date.convert_to(ApiError)
                module.fail_json(msg='API Error deleting Logical Routers: %s'%(api_error.error_message))
        module.exit_json(changed=False, object_name=module.params['network'], message="Static Route for %s does not exist!"%(module.params['network']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
