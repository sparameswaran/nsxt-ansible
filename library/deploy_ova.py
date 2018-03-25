#!/usr/bin/env python
# coding=utf-8
#
# Copyright © 2015 VMware, Inc. All Rights Reserved.
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

__author__ = 'yfauser'

import requests
import ssl

from pyVim.connect import SmartConnect
from pyVmomi import vim, vmodl


def find_virtual_machine(content, searched_vm_name):
    virtual_machines = get_all_objs(content, [vim.VirtualMachine])
    for vm in virtual_machines:
        if vm.name == searched_vm_name:
            return vm
    return None


def get_all_objs(content, vimtype):
    obj = {}
    container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    return obj


def connect_to_api(vchost, vc_user, vc_pwd):
    try:
        service_instance = SmartConnect(host=vchost, user=vc_user, pwd=vc_pwd)
    except (requests.ConnectionError, ssl.SSLError):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            context.verify_mode = ssl.CERT_NONE
            service_instance = SmartConnect(host=vchost, user=vc_user, pwd=vc_pwd, sslContext=context)
        except Exception as e:
            raise Exception(e)
    return service_instance.RetrieveContent()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            ovftool_path=dict(required=True, type='str'),
            datacenter=dict(required=True, type='str'),
            datastore=dict(required=True, type='str'),
            portgroup=dict(required=True, type='str'),
            portgroup_ext=dict(type='str'),
            portgroup_transport=dict(type='str'),
            cluster=dict(required=True, type='str'),
            vmname=dict(required=True, type='str'),
            hostname=dict(required=True, type='str'),
            dns_server=dict(required=True, type='str'),
            ntp_server=dict(required=True, type='str'),
            dns_domain=dict(required=True, type='str'),
            gateway=dict(required=True, type='str'),
            ip_address=dict(required=True, type='str'),
            netmask=dict(required=True, type='str'),
            admin_password=dict(required=True, type='str', no_log=True),
            cli_password=dict(required=True, type='str', no_log=True),
            ssh_enabled=dict(default=False),
            allow_ssh_root_login=dict(default=False),
            path_to_ova=dict(required=True, type='str'),
            ova_file=dict(required=True, type='str'),
            disk_mode=dict(default='thin'),
            vcenter=dict(required=True, type='str'),
            vcenter_user=dict(required=True, type='str'),
            vcenter_passwd=dict(required=True, type='str', no_log=True)
        ),
        supports_check_mode=True,
        required_together=[['portgroup_ext', 'portgroup_transport']]
    )

    try:
        content = connect_to_api(module.params['vcenter'], module.params['vcenter_user'],
                                 module.params['vcenter_passwd'])
    except vim.fault.InvalidLogin:
        module.fail_json(msg='exception while connecting to vCenter, login failure, check username and password')
    except requests.exceptions.ConnectionError:
        module.fail_json(msg='exception while connecting to vCenter, check hostname, FQDN or IP')

    nsx_manager_vm = find_virtual_machine(content, module.params['vmname'])

    if nsx_manager_vm:
        module.exit_json(changed=False, msg='A VM with the name {} was already present'.format(module.params['vmname']))

    ovftool_exec = '{}/ovftool'.format(module.params['ovftool_path'])
    ovf_command = [ovftool_exec]

    ovf_base_options = ['--acceptAllEulas', '--skipManifestCheck', '--X:injectOvfEnv', '--powerOn', '--noSSLVerify',
                        '--allowExtraConfig', '--diskMode={}'.format(module.params['disk_mode']),
                        '--datastore={}'.format(module.params['datastore']),
                        '--name={}'.format(module.params['vmname'])]
    if module.params['portgroup_ext']:
        ovf_base_options.extend(['--net:Network 0={}'.format(module.params['portgroup']),
                                 '--net:Network 1={}'.format(module.params['portgroup_ext']),
                                 '--net:Network 2={}'.format(module.params['portgroup_transport'])])
    else:
        ovf_base_options.extend(['--network={}'.format(module.params['portgroup'])])
    ovf_command.extend(ovf_base_options)

    ovf_ext_prop = ['--prop:nsx_hostname={}'.format(module.params['hostname']),
                   '--prop:nsx_dns1_0={}'.format(module.params['dns_server']),
                   '--prop:nsx_domain_0={}'.format(module.params['dns_domain']),
                   '--prop:nsx_ntp_0={}'.format(module.params['ntp_server']),
                   '--prop:nsx_gateway_0={}'.format(module.params['gateway']),
                   '--prop:nsx_ip_0={}'.format(module.params['ip_address']),
                   '--prop:nsx_netmask_0={}'.format(module.params['netmask']),
                   '--prop:nsx_passwd_0={}'.format(module.params['admin_password']),
                   '--prop:nsx_cli_passwd_0={}'.format(module.params['cli_password']),
                   '--prop:nsx_isSSHEnabled={}'.format(module.params['ssh_enabled']),
                   '--prop:nsx_allowSSHRootLogin={}'.format(module.params['allow_ssh_root_login'])]
    ovf_command.extend(ovf_ext_prop)

    ova_file = '{}/{}'.format(module.params['path_to_ova'], module.params['ova_file'])
    ovf_command.append(ova_file)

    vi_string = 'vi://{}:{}@{}/{}/host/{}/'.format(module.params['vcenter_user'],
                                                   module.params['vcenter_passwd'], module.params['vcenter'],
                                                   module.params['datacenter'], module.params['cluster'])
    ovf_command.append(vi_string)

    if module.check_mode:
        module.exit_json(changed=True, debug_out=ovf_command)

    ova_tool_result = module.run_command(ovf_command)

    if ova_tool_result[0] != 0:
        module.fail_json(msg='Failed to deploy OVA, error message from ovftool is: {}, the comand was {}'.format(ova_tool_result[1], ovf_command))

    module.exit_json(changed=True, ova_tool_result=ova_tool_result)

from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
