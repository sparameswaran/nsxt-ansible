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
    from com.vmware.nsx.fabric_client import ComputeManagers
    from com.vmware.nsx.model_client import ComputeManager
    from com.vmware.nsx.fabric_client import ComputeCollectionFabricTemplates
    from com.vmware.nsx.fabric_client import ComputeCollections
    from com.vmware.nsx_client import ComputeCollectionTransportNodeTemplates

    from com.vmware.nsx.model_client import ComputeCollectionFabricTemplate
    from com.vmware.nsx.model_client import ComputeCollection
    from com.vmware.nsx.model_client import ComputeCollectionTransportNodeTemplate
    from com.vmware.nsx.model_client import StandardHostSwitchSpec
    from com.vmware.nsx.model_client import StandardHostSwitch
    from com.vmware.nsx.model_client import Tag
    from com.vmware.nsx.model_client import IpAssignmentSpec
    from com.vmware.nsx.model_client import StaticIpPoolSpec
    from com.vmware.nsx.model_client import AssignedByDhcp

    from com.vmware.nsx.transport_nodes_client import State
    from com.vmware.nsx_client import TransportNodes
    from com.vmware.nsx_client import TransportZones
    from com.vmware.nsx_client import HostSwitchProfiles
    from com.vmware.nsx.model_client import TransportZone
    from com.vmware.nsx.model_client import TransportZoneEndPoint
    from com.vmware.nsx.model_client import TransportNode
    from com.vmware.nsx.model_client import HostSwitchSpec
    from com.vmware.nsx.model_client import HostSwitch
    from com.vmware.nsx.model_client import HostSwitchProfileTypeIdEntry
    from com.vmware.nsx.model_client import UplinkHostSwitchProfile
    from com.vmware.nsx.model_client import Pnic

    from com.vmware.nsx.fabric_client import Nodes
    from com.vmware.nsx.model_client import Node
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


def listComputeManagers(module, stub_config):
    cm_list = []
    try:
        cm_svc = ComputeManagers(stub_config)
        cm_list = cm_svc.list()
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error listing Compute Managers: %s'%(api_error.error_message))
    return cm_list

def getCMByName(module, stub_config):
    result = listComputeManagers(module, stub_config)
    for vs in result.results:
        cm = vs.convert_to(ComputeManager)
        if cm.display_name == module.params['cm_name']:
            return cm
    module.fail_json(msg='No Compute Manager %s is found, please specift the right cm_name value!' % (module.params['cm_name']))
    return None

def listCMClusters(module, stub_config):
    cm = getCMByName(module, stub_config)
    cc_list = []
    try:
        cc_svc = ComputeCollections(stub_config)
        cc_list = cc_svc.list(origin_id=cm.id)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error listing Compute Managers: %s'%(api_error.error_message))
    return cc_list

def getClusterByName(module, stub_config):
    result = listCMClusters(module, stub_config)
    for vs in result.results:
        cc = vs.convert_to(ComputeCollection)
        if cc.display_name == module.params['display_name']:
            return cc
    module.fail_json(msg='No Cluster with name %s found in Compute Manager %s' % (module.params['display_name'], module.params['cm_name']))
    return None

def getFabricTemplates(module, stub_config, cc):
    cc_list = []
    try:
        cc_svc = ComputeCollectionFabricTemplates(stub_config)
        cc_list = cc_svc.list(compute_collection_id=cc.external_id)
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg='API Error listing Compute Managers: %s'%(api_error.error_message))
    return cc_list




def getTransportZoneEndPoint(module, stub_config):
    tz_endpoints = []
    transportzones_svc = TransportZones(stub_config)
    try:
        tzs = transportzones_svc.list()
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.exit_json(changed=False, message="Error listing Transport Zones: "%(api_error))

    for tz_name in module.params['transport_zone_endpoints']:
        for vs in tzs.results:
            fn = vs.convert_to(TransportZone)
            if fn.display_name == tz_name:
                ep=TransportZoneEndPoint(transport_zone_id=fn.id)
                tz_endpoints.append(ep)
    return tz_endpoints

def getUplinkProfileId(module, stub_config, prof_name):
    hsp_svc = HostSwitchProfiles(stub_config)
    try:
        hsps = hsp_svc.list()
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.exit_json(changed=False, message="Error listing Transport Zones: "%(api_error))

    for vs in hsps.results:
        fn = vs.convert_to(UplinkHostSwitchProfile)
        if fn.display_name == prof_name:
            return fn.id


def createHostSwitchList(module, stub_config):
    hs_list= []
    for hostswitch in module.params['host_switch']:
        pnic_list = []
        uplink_profile_id=getUplinkProfileId(module, stub_config, hostswitch['uplink_profile'])
        hsprof_list = []

        hsptie=HostSwitchProfileTypeIdEntry(
            key=HostSwitchProfileTypeIdEntry.KEY_UPLINKHOSTSWITCHPROFILE,
            value=uplink_profile_id
        )
        hsprof_list.append(hsptie)
        for key, value in hostswitch["pnics"].items():
            pnic=Pnic(device_name=value, uplink_name=key)
            pnic_list.append(pnic)

        ipAssignmentSpec = None
        if 'static_ip_pool_id' in hostswitch:
            ipAssignmentSpec = StaticIpPoolSpec(
                 ip_pool_id = hostswitch["static_ip_pool_id"]
            )
        else:
            ipAssignmentSpec = AssignedByDhcp()

        hs=StandardHostSwitch(
            cpu_config=None,
            host_switch_name=hostswitch["name"],
            host_switch_profile_ids=hsprof_list,
            pnics=pnic_list,
            ip_assignment_spec=ipAssignmentSpec
        )

        hs_list.append(hs)
    return hs_list

def createTransportNodeTemplate(module, stub_config, cc):
    tz_endpoints=getTransportZoneEndPoint(module, stub_config)
    hs_list = createHostSwitchList(module, stub_config)
    cctnt_svc = ComputeCollectionTransportNodeTemplates(stub_config)


    transport_node_temp=ComputeCollectionTransportNodeTemplate(
        display_name='cctnt-%s' % (module.params['display_name']),
        compute_collection_ids=[cc.external_id],
        host_switch_spec=StandardHostSwitchSpec(host_switches=hs_list),
        transport_zone_endpoints=tz_endpoints
    )
#    module.exit_json(changed=False, msg=str(transport_node_temp))
    try:
        rs = cctnt_svc.create(transport_node_temp)
        return rs
    except Error as ex:
        api_error = ex.data.convert_to(ApiError)
        module.fail_json(msg="API Error creating Transport Node: %s "%(api_error))
    return 1

def createTnTemplate(module, stub_config, cc):
    cctnt_svc = ComputeCollectionTransportNodeTemplates(stub_config)
    changed = False
    try:
        cctnt_list = cctnt_svc.list(compute_collection_id=cc.external_id)
        desiredTZs = getTransportZoneEndPoint(module, stub_config)
        if cctnt_list.results[0].transport_zone_endpoints != desiredTZs:
            cctnt_list.results[0].transport_zone_endpoints = desiredTZs
            changed = True
        hs_list = createHostSwitchList(module, stub_config)
        hs_spec = StandardHostSwitchSpec(host_switches=hs_list)
        tmp_hs_spec = cctnt_list.results[0].host_switch_spec
        real_hs_spec = tmp_hs_spec.convert_to(StandardHostSwitchSpec)
        ip_assign = real_hs_spec.host_switches[0].ip_assignment_spec
        assigment = ip_assign.convert_to(IpAssignmentSpec)
        if assigment.resource_type != hs_spec.host_switches[0].ip_assignment_spec.resource_type:
            changed = True
            real_hs_spec.host_switches[0].ip_assignment_spec = hs_spec.host_switches[0].ip_assignment_spec
        if real_hs_spec.host_switches[0].host_switch_name != hs_spec.host_switches[0].host_switch_name:
            real_hs_spec.host_switches[0].host_switch_name = hs_spec.host_switches[0].host_switch_name
            changed = True
        if real_hs_spec.host_switches[0].host_switch_profile_ids != hs_spec.host_switches[0].host_switch_profile_ids:
            real_hs_spec.host_switches[0].host_switch_profile_ids = hs_spec.host_switches[0].host_switch_profile_ids
            changed = True
        if real_hs_spec.host_switches[0].pnics != hs_spec.host_switches[0].pnics:
            real_hs_spec.host_switches[0].pnics = hs_spec.host_switches[0].pnics
            changed = True
        if changed:
            if module.check_mode:
                module.exit_json(changed=True, msg="Cluster auto config will be updated", id="1111")

            cctnt_list.results[0].host_switch_spec = real_hs_spec
            cctnt_svc.update(cctnt_list.results[0].id, cctnt_list.results[0])
            module.exit_json(changed=True, msg=str(cctnt_list), id=cctnt_list.results[0].id)
    except AttributeError:
        createTransportNodeTemplate(module, stub_config, cc)
        changed = True
    return changed

def main():
    module = AnsibleModule(
        argument_spec=dict(
            display_name=dict(required=True, type='str'),
            cm_name=dict(required=False, type='str', default=None),
            auto_install_nsx=dict(required=False, type='bool', default=True),
            create_transport_node=dict(required=False, type='bool', default=True),
            host_switch=dict(required=True, type='list'),
            transport_zone_endpoints=dict(required=False, type='list'),
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
    ccft_svc = ComputeCollectionFabricTemplates(stub_config)
    cc = getClusterByName(module, stub_config)
    ft_list = getFabricTemplates(module, stub_config, cc)

    cctnt_svc = ComputeCollectionTransportNodeTemplates(stub_config)


    if module.params['state'] == 'present':
        if ft_list.result_count == 1:
            changed = False
            if ft_list.results[0].auto_install_nsx != module.params['auto_install_nsx']:
                ft_list.results[0].auto_install_nsx = module.params['auto_install_nsx']
                if module.check_mode:
                    module.exit_json(changed=True, msg="Cluster auto config will be updated", id="1111")
                ccft_svc.update(ft_list.results[0].id, ft_list.results[0])
                changed = True
            if not module.params['create_transport_node']:
                try:
                    cctnt_list = cctnt_svc.list(compute_collection_id=cc.external_id)
                    if module.check_mode:
                        module.exit_json(changed=True, msg="Cluster auto config will be updated", id="1111")
                    cctnt_svc.delete(cctnt_list.results[0].id)
                    module.exit_json(changed=True, msg="Automatic Transport Node Creation is disabled")

                except AttributeError:
                    module.exit_json(changed=False, msg="TN Template is already disabling")
            if module.params['create_transport_node']:
                changed = createTnTemplate(module, stub_config, cc)
            if changed:
                module.exit_json(changed=True, msg='Template for cluster %s has been updated!' % (module.params['display_name']))
            module.exit_json(changed=False, msg='Template for cluster %s already exists!' % (module.params['display_name']))

        elif ft_list.result_count == 0:
            ccft = ComputeCollectionFabricTemplate(
                display_name = 'ccFabTempl-%s' % (module.params['display_name']),
                description=None,
                auto_install_nsx=module.params['auto_install_nsx'],
                compute_collection_id=cc.external_id,
                tags=tags
            )
            if module.check_mode:
                module.exit_json(changed=True, msg="Cluster auto config will be crated", id="1111")

            new_ccft = ccft_svc.create(ccft)
            if module.params['create_transport_node']:
                changed = createTnTemplate(module, stub_config, cc)
            module.exit_json(changed=True, object_name=str(new_ccft), id=new_ccft.id, msg='Template for cluster %s created!' % (module.params['display_name']))

    elif module.params['state'] == "absent":
        if ft_list.result_count == 1:
            if module.check_mode:
                module.exit_json(changed=True, msg="Cluster auto config will be deleted", id="1111")

            try:
                cctnt_list = cctnt_svc.list(compute_collection_id=cc.external_id)
                cctnt_svc.delete(cctnt_list.results[0].id)
            except AttributeError:
                pass
            ccft_svc.delete(ft_list.results[0].id)
            module.exit_json(changed=True, object_out=str(ft_list.results[0]), msg='Template for cluster %s deleted!' % (module.params['display_name']))
        elif ft_list.result_count == 0:
            module.exit_json(changed=False, msg='No Template Configuration for Cluster %s found!' % (module.params['display_name']))


from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
