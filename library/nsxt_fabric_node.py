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
    from com.vmware.nsx.fabric.nodes_client import Status
    from com.vmware.nsx.fabric_client import Nodes
    from com.vmware.nsx.model_client import Node
    from com.vmware.nsx.model_client import HostNodeLoginCredential
    from com.vmware.nsx.model_client import HostNode
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


def listNodes(module, stub_config):
    try:
        fabricnodes_svc = Nodes(stub_config)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error listing nodes: %s'%(api_error.error_message))
    return fabricnodes_svc.list()


def createNode(module, stub_config):
    if module.params['os_type'] == "ESXI":
        os_type=HostNode.OS_TYPE_ESXI
    elif module.params['os_type'] == "RHEL":
        os_type=HostNode.OS_TYPE_RHELKVM
    elif module.params['os_type'] == "UBUNTU":
        os_type=HostNode.OS_TYPE_UBUNTUKVM

    ip_addr = []
    ip_addr.append(module.params['ip_address'])
    fnodes_svc = Nodes(stub_config)
    newNode = HostNode(
	display_name=module.params['display_name'],
	ip_addresses=ip_addr,
	os_type=os_type,
	os_version=module.params['os_version'],
	host_credential=HostNodeLoginCredential(
            username=module.params['node_username'], 
            password=module.params['node_passwd'], 
            thumbprint=module.params['thumbprint']
        )
    )
    try:
        fnodes_svc.create(newNode)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error creating node: %s'%(api_error.error_message))
    time.sleep(20)
    resultNode = getNodeByName(module, stub_config)
    status_svc = Status(stub_config)
    while True:
        fn_status = status_svc.get(resultNode.id)
        if fn_status.host_node_deployment_status == "INSTALL_IN_PROGRESS":
            time.sleep(10)
        elif fn_status.host_node_deployment_status == "INSTALL_SUCCESSFUL":
            time.sleep(5)
            return resultNode
        else:
            module.fail_json(msg='Error in Node status: %s'%(str(fn_status)))


def deleteNode(module, node, stub_config):
    fnodes_svc = Nodes(stub_config)
    node_id = node.id
    node_name = node.display_name
    try:
        fnodes_svc.delete(node_id)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.exit_json(changed=False, object_id=node_id, object_name=node_name, message=api_error)

        module.fail_json(msg='API Error Deleting node: %s'%(api_error.error_message))
    status_svc = Status(stub_config)
    while True:
        try:
            fn_status = status_svc.get(node_id)
            time.sleep(10)
        except Error as ex:
            module.exit_json(changed=True, object_id=node_id, object_name=node_name)


def getNodeByName(module, stub_config):
    result = listNodes(module, stub_config)
    for vs in result.results:
        fn = vs.convert_to(Node)
        if fn.display_name == module.params['display_name']:
            return fn
    return None

def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            ip_address=dict(required=True, type='str'),
            node_username=dict(required=False, type='str'),
            node_passwd=dict(required=False, type='str', no_log=True),
            thumbprint=dict(required=False, type='str', no_log=True),
            os_type=dict(required=True, type='str', choices=['ESXI', 'RHEL', 'UBUNTU']),
            os_version=dict(required=True, type='str', choices=['6.5.0', '7.4', '16.04']),
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
    if module.params['state'] == "present":
        node = getNodeByName(module, stub_config)
        if node is None:
            if module.check_mode:
                module.exit_json(changed=True, debug_out="Fabric node will be created", id="1111")

            result = createNode(module, stub_config)
            module.exit_json(changed=True, id=result.id, object_name=module.params['display_name'], body=str(result))
        else:
            module.exit_json(changed=False, id=node.id, object_name=module.params['display_name'], message="Node with name %s already exists!"%(module.params['display_name']))

    elif module.params['state'] == "absent":
        node = getNodeByName(module, stub_config)
        if node is None:
            module.exit_json(changed=False, object_name=module.params['display_name'], message="No Node with name %s"%(module.params['display_name']))
        else:
            if module.check_mode:
                module.exit_json(changed=True, debug_out="Fabric Node with name %s will be deleted" % (module.params['display_name']))

            deleteNode(module, node, stub_config)
            module.exit_json(changed=True, object_name=module.params['display_name'], message="Node with name %s deleted"%(module.params['display_name']))




from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
