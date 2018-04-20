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
    from com.vmware.nsx_client import LogicalRouterPorts
    from com.vmware.nsx.model_client import LogicalRouterPort
    from com.vmware.nsx.model_client import LogicalRouterUpLinkPort
    from com.vmware.nsx.model_client import ResourceReference
    from com.vmware.nsx.model_client import EdgeCluster
    from com.vmware.nsx.model_client import EdgeClusterMember
    from com.vmware.nsx_client import EdgeClusters
    from com.vmware.nsx.model_client import TransportNode
    from com.vmware.nsx_client import TransportNodes
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
        if fn.display_name == module.params['edge_cluster_member']:
            return fn
    return None

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

def listLogicalRouterPorts(module, stub_config, lrid):
    lr_list = []
    try:
        lr_svc = LogicalRouterPorts(stub_config)
        lr_list = lr_svc.list(resource_type='LogicalRouterUpLinkPort', logical_router_id=lrid)
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error listing Logical Routers: %s'%(api_error.error_message))
    return lr_list

def getLogicalRouterPortByName(module, stub_config, lrid):
    result = listLogicalRouterPorts(module, stub_config, lrid)
    for vs in result.results:
        lr = vs.convert_to(LogicalRouterUpLinkPort)
        if lr.display_name == module.params['display_name']:
            return lr
    return None


def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            description=dict(required=False, type='str', default=None),
            edge_cluster_member=dict(required=True, type='str'),
            ip_address=dict(required=True, type='str'),
            t0_router=dict(required=True, type='str'),
            logical_switch_port_id=dict(required=True, type='str'),
            urpf=dict(required=False, type='str', default='NONE', choices=['NONE', 'STRICT']),
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
    lr_svc = LogicalRouters(stub_config)
    lr = getLogicalRouterByName(module, stub_config)
    ec_svc = EdgeClusters(stub_config)
    edgeCluster = ec_svc.get(lr.edge_cluster_id)

    tn = getTransportNodeByName(module, stub_config)
    member_index = []
    for member in edgeCluster.members:
        if member.transport_node_id == tn.id:
            member_index.append(int(member.member_index))


    subnet_list = []
    subnet = module.params['ip_address'].split('/')
    new_subnet = IPSubnet(ip_addresses=[subnet[0]], prefix_length=int(subnet[1]))
    subnet_list.append(new_subnet)
    lrp_svc = LogicalRouterPorts(stub_config)
    lrp = getLogicalRouterPortByName(module, stub_config, lr.id)
    if module.params['state'] == 'present':
        if lrp is None:
            new_lrp = LogicalRouterUpLinkPort(
                display_name=module.params['display_name'],
                description=module.params['description'],
                edge_cluster_member_index=member_index,
                linked_logical_switch_port_id=ResourceReference(target_id=module.params['logical_switch_port_id']),
                subnets=subnet_list,
                urpf_mode=module.params['urpf'],
                logical_router_id=lr.id,
                tags=tags
            )
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(new_lrp), id="1111")
            try:
                lrp_temp = lrp_svc.create(new_lrp)
                new_lrp = lrp_temp.convert_to(LogicalRouterUpLinkPort)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=new_lrp.id, message="Logical Router Port with name %s created!"%(module.params['display_name']))
            except Error as ex:
                api_error = ex.data.convert_to(ApiError)
                module.fail_json(msg='API Error creating Logical Router Uplink: %s'%(str(api_error.error_message)))
        elif lrp:
            changed = False
            if lrp.linked_logical_switch_port_id.target_id != module.params['logical_switch_port_id']:
                changed = True
                lrp.linked_logical_switch_port_id=ResourceReference(target_id=module.params['logical_switch_port_id'])
            if tags != lrp.tags:
                changed = True
                lrp.tags=tags
            if subnet_list != lrp.subnets:
                changed = True
                lrp.subnets=subnet_list
            if member_index != lrp.edge_cluster_member_index:
                changed = True
                lrp.edge_cluster_member_index=member_index
            if changed:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(lrp), id=lrp.id)
                new_lr = lrp_svc.update(lrp.id, lrp)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=lrp.id, message="Logical Router Uplink with name %s has been changed!"%(module.params['display_name']))
            module.exit_json(changed=False, object_name=module.params['display_name'], id=lrp.id, message="Logical Router Uplink with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":

        if lrp:
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(lrp), id=lrp.id)
            try:
                lrp_svc.delete(lrp.id, force=True)
            except Error as ex:
                api_error = ex.date.convert_to(ApiError)
                module.fail_json(msg='API Error deleting Logical Router Ports: %s'%(api_error.error_message))

            module.exit_json(changed=True, object_name=module.params['display_name'], message="Logical Router Port with name %s deleted!"%(module.params['display_name']))
        module.exit_json(changed=False, object_name=module.params['display_name'], message="Logical Router Port with name %s does not exist!"%(module.params['display_name']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
