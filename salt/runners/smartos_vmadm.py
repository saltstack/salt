# -*- coding: utf-8 -*-
'''
Runner for SmartOS minions control vmadm
'''
# Import python libs
from __future__ import absolute_import
from __future__ import print_function

# Import salt libs
import salt.client
from salt.exceptions import SaltClientError
from salt.utils.odict import OrderedDict

# Import 3rd party libs
import salt.ext.six as six

# Function aliases
__func_alias__ = {
    'list_vms': 'list'
}

# Define the module's virtual name
__virtualname__ = 'vmadm'


def __virtual__():
    '''
    Provides vmadm runner
    '''
    # NOTE: always load vmadm runner
    #       we could check using test.ping + a grain
    #       match, but doing this on master startup is
    #       not acceptable
    return __virtualname__


def _action(action='get', search=None, one=True, force=False):
    '''
    Multi action helper for start, stop, get, ...
    '''
    vms = {}
    matched_vms = []
    client = salt.client.get_local_client(__opts__['conf_file'])

    ## lookup vms
    try:
        vmadm_args = {}
        vmadm_args['order'] = 'uuid,alias,hostname,state'
        if '=' in search:
            vmadm_args['search'] = search
        for cn in client.cmd_iter('G@virtual:physical and G@os:smartos',
                                  'vmadm.list', kwarg=vmadm_args,
                                  tgt_type='compound'):
            if not cn:
                continue
            node = next(six.iterkeys(cn))
            if not isinstance(cn[node], dict) or \
                    'ret' not in cn[node] or \
                    not isinstance(cn[node]['ret'], dict):
                continue
            for vm in cn[node]['ret']:
                vmcfg = cn[node]['ret'][vm]
                vmcfg['node'] = node
                vms[vm] = vmcfg
    except SaltClientError as client_error:
        pass

    ## check if we have vms
    if len(vms) == 0:
        return {'Error': 'No vms found.'}

    ## simple search
    if '=' not in search:
        loop_pass = 0
        while loop_pass < 3:
            ## each pass will try a different field
            if loop_pass == 0:
                field = 'uuid'
            elif loop_pass == 1:
                field = 'hostname'
            else:
                field = 'alias'

            ## loop vms and try to match
            for vm in vms:
                if field == 'uuid' and vm == search:
                    matched_vms.append(vm)
                    break  # exit for on uuid match (max = 1)
                elif field in vms[vm] and vms[vm][field] == search:
                    matched_vms.append(vm)

            ## exit on match(es) or try again
            if len(matched_vms) > 0:
                break
            else:
                loop_pass += 1
    else:
        for vm in vms:
            matched_vms.append(vm)

    ## check if we have vms
    if len(matched_vms) == 0:
        return {'Error': 'No vms matched.'}

    ## multiple allowed?
    if one and len(matched_vms) > 1:
        return {
            'Error': 'Matched {0} vms, only one allowed!'.format(len(matched_vms)),
            'Matches': matched_vms
        }

    ## perform action
    ret = {}
    if action in ['start', 'stop', 'reboot', 'get']:
        for vm in matched_vms:
            vmadm_args = {
                'key': 'uuid',
                'vm': vm
            }
            try:
                for vmadm_res in client.cmd_iter(vms[vm]['node'], 'vmadm.{0}'.format(action), kwarg=vmadm_args):
                    if not vmadm_res:
                        continue
                    if vms[vm]['node'] in vmadm_res:
                        ret[vm] = vmadm_res[vms[vm]['node']]['ret']
            except SaltClientError as client_error:
                ret[vm] = False
    elif action in ['is_running']:
        ret = True
        for vm in matched_vms:
            if vms[vm]['state'] != 'running':
                ret = False
                break
    return ret


def nodes(verbose=False):
    '''
    List all compute nodes

    verbose : boolean
        print additional information about the node
        e.g. platform version, hvm capable, ...

    CLI Example:

    .. code-block:: bash

        salt-run vmadm.nodes
        salt-run vmadm.nodes verbose=True
    '''
    ret = {} if verbose else []
    client = salt.client.get_local_client(__opts__['conf_file'])

    ## get list of nodes
    try:
        for cn in client.cmd_iter('G@virtual:physical and G@os:smartos',
                                  'grains.items', tgt_type='compound'):
            if not cn:
                continue
            node = next(six.iterkeys(cn))
            if not isinstance(cn[node], dict) or \
                    'ret' not in cn[node] or \
                    not isinstance(cn[node]['ret'], dict):
                continue
            if verbose:
                ret[node] = {}
                ret[node]['version'] = {}
                ret[node]['version']['platform'] = cn[node]['ret']['osrelease']
                if 'computenode_sdc_version' in cn[node]['ret']:
                    ret[node]['version']['sdc'] = cn[node]['ret']['computenode_sdc_version']
                ret[node]['vms'] = {}
                if 'computenode_vm_capable' in cn[node]['ret'] and \
                        cn[node]['ret']['computenode_vm_capable'] and \
                        'computenode_vm_hw_virt' in cn[node]['ret']:
                    ret[node]['vms']['hw_cap'] = cn[node]['ret']['computenode_vm_hw_virt']
                else:
                    ret[node]['vms']['hw_cap'] = False
                if 'computenode_vms_running' in cn[node]['ret']:
                    ret[node]['vms']['running'] = cn[node]['ret']['computenode_vms_running']
            else:
                ret.append(node)
    except SaltClientError as client_error:
        return "{0}".format(client_error)

    if not verbose:
        ret.sort()
    return ret


def list_vms(search=None, verbose=False):
    '''
    List all vms

    search : string
        filter vms, see the execution module
    verbose : boolean
        print additional information about the vm

    CLI Example:

    .. code-block:: bash

        salt-run vmadm.list
        salt-run vmadm.list search='type=KVM'
        salt-run vmadm.list verbose=True
    '''
    ret = OrderedDict() if verbose else []
    client = salt.client.get_local_client(__opts__['conf_file'])
    try:
        vmadm_args = {}
        vmadm_args['order'] = 'uuid,alias,hostname,state,type,cpu_cap,vcpus,ram'
        if search:
            vmadm_args['search'] = search
        for cn in client.cmd_iter('G@virtual:physical and G@os:smartos',
                                  'vmadm.list', kwarg=vmadm_args,
                                  tgt_type='compound'):
            if not cn:
                continue
            node = next(six.iterkeys(cn))
            if not isinstance(cn[node], dict) or \
                    'ret' not in cn[node] or \
                    not isinstance(cn[node]['ret'], dict):
                continue
            for vm in cn[node]['ret']:
                vmcfg = cn[node]['ret'][vm]
                if verbose:
                    ret[vm] = OrderedDict()
                    ret[vm]['hostname'] = vmcfg['hostname']
                    ret[vm]['alias'] = vmcfg['alias']
                    ret[vm]['computenode'] = node
                    ret[vm]['state'] = vmcfg['state']
                    ret[vm]['resources'] = OrderedDict()
                    ret[vm]['resources']['memory'] = vmcfg['ram']
                    if vmcfg['type'] == 'KVM':
                        ret[vm]['resources']['cpu'] = "{0:.2f}".format(int(vmcfg['vcpus']))
                    else:
                        if vmcfg['cpu_cap'] != '':
                            ret[vm]['resources']['cpu'] = "{0:.2f}".format(int(vmcfg['cpu_cap'])/100)
                else:
                    ret.append(vm)
    except SaltClientError as client_error:
        return "{0}".format(client_error)

    if not verbose:
        ret = sorted(ret)

    return ret


def start(search, one=True):
    '''
    Start one or more vms

    search : string
        filter vms, see the execution module.
    one : boolean
        start only one vm

    .. note::
        If the search parameter does not contain an equal (=) symbol it will be
        assumed it will be tried as uuid, hostname, and alias.

    CLI Example:

    .. code-block:: bash

        salt-run vmadm.start 91244bba-1146-e4ec-c07e-e825e0223aa9
        salt-run vmadm.start search='alias=jiska'
        salt-run vmadm.start search='type=KVM' one=False
    '''
    return _action('start', search, one)


def stop(search, one=True):
    '''
    Stop one or more vms

    search : string
        filter vms, see the execution module.
    one : boolean
        stop only one vm

    .. note::
        If the search parameter does not contain an equal (=) symbol it will be
        assumed it will be tried as uuid, hostname, and alias.

    CLI Example:

    .. code-block:: bash

        salt-run vmadm.stop 91244bba-1146-e4ec-c07e-e825e0223aa9
        salt-run vmadm.stop search='alias=jody'
        salt-run vmadm.stop search='type=KVM' one=False
    '''
    return _action('stop', search, one)


def reboot(search, one=True, force=False):
    '''
    Reboot one or more vms

    search : string
        filter vms, see the execution module.
    one : boolean
        reboot only one vm
    force : boolean
        force reboot, faster but no graceful shutdown

    .. note::
        If the search parameter does not contain an equal (=) symbol it will be
        assumed it will be tried as uuid, hostname, and alias.

    CLI Example:

    .. code-block:: bash

        salt-run vmadm.reboot 91244bba-1146-e4ec-c07e-e825e0223aa9
        salt-run vmadm.reboot search='alias=marije'
        salt-run vmadm.reboot search='type=KVM' one=False
    '''
    return _action('reboot', search, one, force)


def get(search, one=True):
    '''
    Return information for vms

    search : string
        filter vms, see the execution module.
    one : boolean
        return only one vm

    .. note::
        If the search parameter does not contain an equal (=) symbol it will be
        assumed it will be tried as uuid, hostname, and alias.

    CLI Example:

    .. code-block:: bash

        salt-run vmadm.get 91244bba-1146-e4ec-c07e-e825e0223aa9
        salt-run vmadm.get search='alias=saskia'
    '''
    return _action('get', search, one)


def is_running(search):
    '''
    Return true if vm is running

    search : string
        filter vms, see the execution module.

    .. note::
        If the search parameter does not contain an equal (=) symbol it will be
        assumed it will be tried as uuid, hostname, and alias.

    .. note::
        If multiple vms are matched, the result will be true of ALL vms are running

    CLI Example:

    .. code-block:: bash

        salt-run vmadm.is_running 91244bba-1146-e4ec-c07e-e825e0223aa9
        salt-run vmadm.is_running search='alias=julia'
    '''
    return _action('is_running', search, False)


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
