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
    from com.vmware.nsx.model_client import LogicalRouterLinkPortOnTIER1
    from com.vmware.nsx.model_client import LogicalRouterLinkPortOnTIER0
    from com.vmware.nsx.model_client import ResourceReference
    from com.vmware.nsx_client import LogicalRouterPorts
    from com.vmware.nsx.model_client import LogicalRouterPort
    from com.vmware.nsx.model_client import AdvertisementConfig
    from com.vmware.nsx.logical_routers.routing_client import Advertisement

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
        if lr.display_name == module.params['display_name']:
            return lr
    return None



def connectT0(t1, module, stub_config):
    t0port = None
    lrp_svc = LogicalRouterPorts(stub_config)

    t0_lrp=LogicalRouterLinkPortOnTIER0(
        display_name="t0-downlink-to_%s"%(t1.display_name), 
        logical_router_id=module.params['connected_t0_id'], 
        description=t1.id
    )
    try:
        port = lrp_svc.create(t0_lrp)
        t0port = port.convert_to(LogicalRouterLinkPortOnTIER0)
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error creating T0 port: %s'%(api_error.error_message))

    t1_lrp=LogicalRouterLinkPortOnTIER1(
        display_name="%s-uplinklink-to_t0"%(t1.display_name), 
        description=module.params['connected_t0_id'], 
        logical_router_id=t1.id,
        linked_logical_router_port_id=ResourceReference(target_id=t0port.id)
    )
    try:
        t1port = lrp_svc.create(t1_lrp)
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error creating T1 port: %s'%(api_error.error_message))

    return True

def deleteAllPortsOnRouter(lr, module, stub_config):
    lrp_svc = LogicalRouterPorts(stub_config)
    lrpList = lrp_svc.list(logical_router_id=lr.id)
    if lrpList.results:
        for vs in lrpList.results:
            lrp = vs.convert_to(LogicalRouterPort)
            lrp_svc.delete(lrp.id, force=True)

def compareLrpT0T1(lr, module, stub_config):
    changed = False
    t0id = None
    lrp_svc = LogicalRouterPorts(stub_config)
    lrpList = lrp_svc.list(logical_router_id=lr.id, resource_type='LogicalRouterLinkPortOnTIER1')
    if lrpList.results:
        lrp = lrpList.results[0].convert_to(LogicalRouterLinkPortOnTIER1)
        t0port_id = lrp.linked_logical_router_port_id.target_id
        t1port_id = lrp.id
        t0tmp = lrp_svc.get(t0port_id)
        t0lrp = t0tmp.convert_to(LogicalRouterLinkPortOnTIER0)
        t0id = t0lrp.logical_router_id
    if t0id:
        if t0id != module.params['connected_t0_id']:
            changed = True
            if t1port_id:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out="Connection to T0 will be deleted")
                lrp_svc.delete(t1port_id, force=True)
                lrp_svc.delete(t0port_id, force=True)
            if module.params['connected_t0_id']:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out="T1 will be connected to T0")
                changed = connectT0(lr, module, stub_config)
    elif not t0id:
        if t0id != module.params['connected_t0_id']:
            changed = True
            if module.params['connected_t0_id']:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out="T1 will be connected to T0")
                changed = connectT0(lr, module, stub_config)

    return changed

def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            description=dict(required=False, type='str', default=None),
            failover_mode=dict(required=False, type='str', default=None, choices=['NON_PREEMPTIVE', 'PREEMPTIVE']),
            edge_cluster_id=dict(required=False, type='str', default=None),
            connected_t0_id=dict(required=False, type='str', default=None),
            high_availability_mode=dict(required=False, type='str', default='ACTIVE_STANDBY', choices=['ACTIVE_STANDBY', 'ACTIVE_ACTIVE']),
            advertise=dict(required=False, type='dict', default=None),
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
    desired_adv_config = AdvertisementConfig()
    if module.params['advertise']:
        if 'enabled' in module.params['advertise']:
            desired_adv_config.enabled = module.params['advertise']['enabled']
        else:
            desired_adv_config.enabled = True
        if 'advertise_lb_snat_ip' in module.params['advertise'] and module.params['advertise']['advertise_lb_snat_ip']:
            desired_adv_config.advertise_lb_snat_ip = module.params['advertise']['advertise_lb_snat_ip']
        if 'advertise_lb_vip' in module.params['advertise'] and module.params['advertise']['advertise_lb_vip']:
            desired_adv_config.advertise_lb_vip = module.params['advertise']['advertise_lb_vip']
        if 'advertise_nat_routes' in module.params['advertise'] and module.params['advertise']['advertise_nat_routes']:
            desired_adv_config.advertise_nat_routes = module.params['advertise']['advertise_nat_routes']
        if 'advertise_nsx_connected_routes' in module.params['advertise'] and module.params['advertise']['advertise_nsx_connected_routes']:
            desired_adv_config.advertise_nsx_connected_routes = module.params['advertise']['advertise_nsx_connected_routes']
        if 'advertise_static_routes' in module.params['advertise'] and module.params['advertise']['advertise_static_routes']:
            desired_adv_config.advertise_static_routes = module.params['advertise']['advertise_static_routes']

    tags=None
    if module.params['tags'] is not None:
        tags = []
        for key, value in module.params['tags'].items():
            tag=Tag(scope=key, tag=value)
            tags.append(tag)
    lr_svc = LogicalRouters(stub_config)
    lr = getLogicalRouterByName(module, stub_config)
    if module.params['state'] == 'present':
        if lr is None:
            new_lr = LogicalRouter(
                display_name=module.params['display_name'],
                description=module.params['description'],
                failover_mode=module.params['failover_mode'],
                edge_cluster_id=module.params['edge_cluster_id'],
                router_type='TIER1',
                high_availability_mode=module.params['high_availability_mode'],
                tags=tags
            )
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(new_lr), id="1111")
            try:
                new_lr = lr_svc.create(new_lr)
                mylr = getLogicalRouterByName(module, stub_config)
                if module.params['connected_t0_id']:
                    connectT0(mylr, module, stub_config)
                if module.params['advertise']:
                    adv_svc = Advertisement(stub_config)
                    adv_config = adv_svc.get(mylr.id)
                    adv_config.enabled = desired_adv_config.enabled
                    adv_config.advertise_lb_snat_ip = desired_adv_config.advertise_lb_snat_ip
                    adv_config.advertise_lb_vip = desired_adv_config.advertise_lb_vip
                    adv_config.advertise_nat_routes = desired_adv_config.advertise_nat_routes
                    adv_config.advertise_nsx_connected_routes = desired_adv_config.advertise_nsx_connected_routes
                    adv_config.advertise_static_routes = desired_adv_config.advertise_static_routes
                    adv_svc.update(mylr.id, adv_config)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=mylr.id, message="Logical Router with name %s created!"%(module.params['display_name']))
            except Error as ex:
                module.fail_json(msg='API Error listing Logical Routers: %s'%(str(ex)))
        elif lr:
            adv_svc = Advertisement(stub_config)
            adv_config = adv_svc.get(lr.id)
            changed = False
            if tags != lr.tags:
                changed = True
                lr.tags=tags
            if module.params['edge_cluster_id'] != lr.edge_cluster_id:
                lr.edge_cluster_id=module.params['edge_cluster_id']
                changed = True
            if changed:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(lr), id=lr.id)
                new_lr = lr_svc.update(lr.id, lr)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=new_lr.id, message="Logical Router with name %s has been modified!"%(module.params['display_name']))
            if compareLrpT0T1(lr, module, stub_config):
                module.exit_json(changed=True, object_name=module.params['display_name'], id=lr.id, message="Logical Router uplink on T1 with name %s has been modified!"%(module.params['display_name']))
            if module.params['advertise']:
                changed = False
                if ('enabled' not in module.params['advertise']):
                    changed = False
                elif module.params['advertise']['enabled'] != adv_config.enabled:
                    adv_config.enabled = desired_adv_config.enabled
                    changed = True
                if ('advertise_lb_snat_ip' not in module.params['advertise']):
                    if adv_config.advertise_lb_snat_ip:
                        adv_config.advertise_lb_snat_ip = None
                        changed = True
                elif module.params['advertise']['advertise_lb_snat_ip'] != adv_config.advertise_lb_snat_ip:
                    adv_config.advertise_lb_snat_ip = desired_adv_config.advertise_lb_snat_ip
                    changed = True

                if ('advertise_lb_vip' not in module.params['advertise']):
                    if adv_config.advertise_lb_vip:
                        adv_config.advertise_lb_vip = None
                        changed = True
                elif module.params['advertise']['advertise_lb_vip'] != adv_config.advertise_lb_vip:
                    adv_config.advertise_lb_vip = desired_adv_config.advertise_lb_vip
                    changed = True
 
                if ('advertise_nat_routes' not in module.params['advertise']):
                    if adv_config.advertise_nat_routes:
                        adv_config.advertise_nat_routes = None
                        changed = True
                elif module.params['advertise']['advertise_nat_routes'] != adv_config.advertise_nat_routes:
                    adv_config.advertise_nat_routes = desired_adv_config.advertise_nat_routes
                    changed = True

                if ('advertise_nsx_connected_routes' not in module.params['advertise']):
                    if adv_config.advertise_nsx_connected_routes:
                        adv_config.advertise_nsx_connected_routes = None
                        changed = True
                elif module.params['advertise']['advertise_nsx_connected_routes'] != adv_config.advertise_nsx_connected_routes:
                    adv_config.advertise_nsx_connected_routes = desired_adv_config.advertise_nsx_connected_routes
                    changed = True

                if ('advertise_static_routes' not in module.params['advertise']):
                    if adv_config.advertise_static_routes:
                        adv_config.advertise_static_routes = None
                        changed = True
                elif module.params['advertise']['advertise_static_routes'] != adv_config.advertise_static_routes:
                    adv_config.advertise_static_routes = desired_adv_config.advertise_static_routes
                    changed = True

                if changed:
                    if module.check_mode:
                        module.exit_json(changed=True, debug_out=str(adv_config), id=lr.id)
                    adv_svc.update(lr.id, adv_config)
                    module.exit_json(changed=True, object_name=module.params['display_name'], id=lr.id, message="Logical Router advertisement config on T1 with name %s has been modified!"%(module.params['display_name']))

            module.exit_json(changed=False, object_name=module.params['display_name'], id=lr.id, message="Logical Router with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":
        if lr:
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(lr), id=lr.id)
            try:
                deleteAllPortsOnRouter(lr, module, stub_config)
                lr_svc.delete(lr.id)
            except Error as ex:
                api_error = ex.date.convert_to(ApiError)
                module.fail_json(msg='API Error deleting Logical Routers: %s'%(api_error.error_message))


            module.exit_json(changed=True, object_name=module.params['display_name'], message="Logical Router with name %s deleted!"%(module.params['display_name']))
        module.exit_json(changed=False, object_name=module.params['display_name'], message="Logical Router with name %s does not exist!"%(module.params['display_name']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
