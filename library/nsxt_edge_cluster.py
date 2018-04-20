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
    from com.vmware.nsx.model_client import EdgeCluster
    from com.vmware.nsx.model_client import EdgeClusterMember
    from com.vmware.nsx_client import TransportNodes
    from com.vmware.nsx.model_client import TransportNode
    from com.vmware.nsx_client import EdgeClusters

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

def listEdgeClusters(module, stub_config):
    ec_list = []
    try:
        ec_svc = EdgeClusters(stub_config)
        ec_list = ec_svc.list()
    except Error as ex:
        api_error = ex.date.convert_to(ApiError)
        module.fail_json(msg='API Error listing Edge Clusters: %s'%(api_error.error_message))
    return ec_list

def getEdgeClusterByName(module, stub_config):
    result = listEdgeClusters(module, stub_config)
    for vs in result.results:
        ec = vs.convert_to(EdgeCluster)
        if ec.display_name == module.params['display_name']:
            return ec
    return None

def listTransportNodes(module, stub_config):
    try:
        fabricnodes_svc = TransportNodes(stub_config)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error listing nodes: %s'%(api_error.error_message))
    return fabricnodes_svc.list()

def getTransportNodeByName(name, module, stub_config):
    result = listTransportNodes(module, stub_config)
    for vs in result.results:
        fn = vs.convert_to(TransportNode)
        if fn.display_name == name:
            return fn
    return None

def simplifyClusterMembersList(memberList):
    idList = []
    for member in memberList:
        idList.append(member.transport_node_id)
    return idList


def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            description=dict(required=False, type='str', default=None),
            members=dict(required=False, type='list', default=None),
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

    member_list = []
    if module.params['members']:
        for tnode_name in module.params['members']:
            member = getTransportNodeByName(tnode_name, module, stub_config)
            edgeClusterMember = EdgeClusterMember(transport_node_id=member.id)
            member_list.append(edgeClusterMember)
    elif module.params['members'] is None:
        member_list = None
    ec_svc = EdgeClusters(stub_config)
    ec = getEdgeClusterByName(module, stub_config)
    if module.params['state'] == 'present':
        if ec is None:
            new_ec = EdgeCluster(
                display_name=module.params['display_name'],
                description=module.params['description'],
                members=member_list,
                tags=tags
            )
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(new_ec), id="1111")
            new_ec = ec_svc.create(new_ec)
            module.exit_json(changed=True, object_name=module.params['display_name'], id=new_ec.id, message="Edge Cluster with name %s created!"%(module.params['display_name']))
        elif ec:
            changed = False
            if tags != ec.tags:
                ec.tags=tags
                changed = True
            desiredList = []
            realisedList = []
            if module.params['members']:
                desiredList = simplifyClusterMembersList(member_list)
            if ec.members:
                realisedList = simplifyClusterMembersList(ec.members)
            if desiredList != realisedList:
                ec.members=member_list
                changed = True
            if changed:
                if module.check_mode:
                    module.exit_json(changed=True, debug_out=str(ec), id=ec.id)
                new_ec = ec_svc.update(ec.id, ec)
                module.exit_json(changed=True, object_name=module.params['display_name'], id=new_ec.id, message="Edge Cluster with name %s has changed tags!"%(module.params['display_name']))

            module.exit_json(changed=False, object_name=module.params['display_name'], id=ec.id, message="Edge Cluster with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":
        if ec:
            if module.check_mode:
                module.exit_json(changed=True, debug_out=str(ec))

            ec_svc.delete(ec.id)
            module.exit_json(changed=True, object_name=module.params['display_name'], message="Edge Cluster with name %s deleted!"%(module.params['display_name']))
        if module.check_mode:
            module.exit_json(changed=False, debug_out="no Edge Cluster with name %s" % (module.params['display_name']))

        module.exit_json(changed=False, object_name=module.params['display_name'], message="Edge Cluster with name %s does not exist!"%(module.params['display_name']))

from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
