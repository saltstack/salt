# -*- coding: utf-8 -*-
'''
Manage VMware ESXi Clusters.

Dependencies
============

- pyVmomi Python Module


pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against.
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import traceback

# Import Salt Libs
import salt.exceptions
from salt.utils.dictdiffer import recursive_diff
from salt.utils.listdiffer import list_diff
from salt.config.schemas.esxcluster import ESXClusterConfigSchema
from salt.utils import dictupdate

# External libraries
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    return HAS_JSONSCHEMA


def mod_init(low):
    '''
    Retrieves and adapt the login credentials from the proxy connection module
    '''
    return True


def cluster_configured(name, cluster_config):
    '''
    Configures a cluster. Creates a new cluster, if it doesn't exist on the
    vCenter or reconfigures it if configured differently

    Supported proxies: esxdatacenter, esxcluster

    name
        Name of the state. If the state is run in by an ``esxdatacenter``
        proxy, it will be the name of the cluster.

    cluster_config
        Configuration applied to the cluster.
        Complex datastructure following the ESXClusterConfigSchema.
        Valid example is:

.. code-block::yaml

        drs:
            default_vm_behavior: fullyAutomated
            enabled: true
            vmotion_rate: 3
        ha:
            admission_control
            _enabled: false
            default_vm_settings:
                isolation_response: powerOff
                restart_priority: medium
            enabled: true
            hb_ds_candidate_policy: userSelectedDs
            host_monitoring: enabled
            options:
                - key: das.ignoreinsufficienthbdatastore
                  value: 'true'
            vm_monitoring: vmMonitoringDisabled
        vm_swap_placement: vmDirectory
        vsan:
            auto_claim_storage: false
            compression_enabled: true
            dedup_enabled: true
            enabled: true

    '''
    proxy_type = __salt__['vsphere.get_proxy_type']()
    if proxy_type == 'esxdatacenter':
        cluster_name, datacenter_name = \
                name, __salt__['esxdatacenter.get_details']()['datacenter']
    elif proxy_type == 'esxcluster':
        cluster_name, datacenter_name = \
                __salt__['esxcluster.get_details']()['cluster'], \
                __salt__['esxcluster.get_details']()['datacenter']
    else:
        raise salt.exceptions.CommandExecutionError('Unsupported proxy {0}'
                                                    ''.format(proxy_type))
    log.info('Running {0} for cluster \'{1}\' in datacenter '
             '\'{2}\''.format(name, cluster_name, datacenter_name))
    cluster_dict = cluster_config
    log.trace('cluster_dict =  {0}'.format(cluster_dict))
    changes_required = False
    ret = {'name': name,
           'changes': {}, 'result': None, 'comment': 'Default'}
    comments = []
    changes = {}
    changes_required = False

    try:
        log.debug('Validating cluster_configured state input')
        schema = ESXClusterConfigSchema.serialize()
        log.trace('schema = {0}'.format(schema))
        try:
            jsonschema.validate(cluster_dict, schema)
        except jsonschema.exceptions.ValidationError as exc:
            raise salt.exceptions.InvalidESXClusterPayloadError(exc)
        current = None
        si = __salt__['vsphere.get_service_instance_via_proxy']()
        try:
            current = __salt__['vsphere.list_cluster'](datacenter_name,
                                                       cluster_name,
                                                       service_instance=si)
        except salt.exceptions.VMwareObjectRetrievalError:
            changes_required = True
            if __opts__['test']:
                comments.append('State {0} will create cluster '
                                '\'{1}\' in datacenter \'{2}\'.'
                                ''.format(name, cluster_name, datacenter_name))
                log.info(comments[-1])
                __salt__['vsphere.disconnect'](si)
                ret.update({'result': None,
                            'comment': '\n'.join(comments)})
                return ret
            log.debug ('Creating cluster \'{0}\' in datacenter \'{1}\'. '
                       ''.format(cluster_name, datacenter_name))
            __salt__['vsphere.create_cluster'](cluster_dict,
                                               datacenter_name,
                                               cluster_name,
                                               service_instance=si)
            comments.append('Created cluster \'{0}\' in datacenter \'{1}\''
                            ''.format(cluster_name, datacenter_name))
            log.info(comments[-1])
            changes.update({'new': cluster_dict})
        if current:
            # Cluster already exists
            # We need to handle lists sepparately
            ldiff = None
            if 'ha' in cluster_dict and 'options' in cluster_dict['ha']:
                ldiff = list_diff(current.get('ha', {}).get('options', []),
                                  cluster_dict.get('ha', {}).get('options', []),
                                  'key')
                log.trace('options diffs = {0}'.format(ldiff.diffs))
                # Remove options if exist
                del cluster_dict['ha']['options']
                if 'ha' in current and 'options' in current['ha']:
                    del current['ha']['options']
            diff = recursive_diff(current, cluster_dict)
            log.trace('diffs = {0}'.format(diff.diffs))
            if not (diff.diffs or (ldiff and ldiff.diffs)):
                # No differences
                comments.append('Cluster \'{0}\' in datacenter \'{1}\' is up '
                                'to date. Nothing to be done.'
                                ''.format(cluster_name, datacenter_name))
                log.info(comments[-1])
            else:
                changes_required = True
                changes_str = ''
                if diff.diffs:
                    changes_str = '{0}{1}'.format(changes_str,
                                                  diff.changes_str)
                if ldiff and ldiff.diffs:
                    changes_str = '{0}\nha:\n  options:\n{1}'.format(
                        changes_str,
                        '\n'.join(['  {0}'.format(l) for l in
                                   ldiff.changes_str2.split('\n')]))
                # Apply the changes
                if __opts__['test']:
                    comments.append(
                        'State {0} will update cluster \'{1}\' '
                        'in datacenter \'{2}\':\n{3}'
                        ''.format(name, cluster_name,
                                  datacenter_name, changes_str))
                else:
                    new_values = diff.new_values
                    old_values = diff.old_values
                    if ldiff and ldiff.new_values:
                        dictupdate.update(
                            new_values, {'ha': {'options': ldiff.new_values}})
                    if ldiff and ldiff.old_values:
                        dictupdate.update(
                            old_values, {'ha': {'options': ldiff.old_values}})
                    log.trace('new_values = {0}'.format(new_values))
                    __salt__['vsphere.update_cluster'](new_values,
                                                       datacenter_name,
                                                       cluster_name,
                                                       service_instance=si)
                    comments.append('Updated cluster \'{0}\' in datacenter '
                                    '\'{1}\''.format(cluster_name,
                                                     datacenter_name))
                    log.info(comments[-1])
                    changes.update({'new': new_values,
                                    'old': old_values})
        __salt__['vsphere.disconnect'](si)
        ret_status = True
        if __opts__['test'] and changes_required:
            ret_status = None
        ret.update({'result': ret_status,
                    'comment': '\n'.join(comments),
                    'changes': changes})
        return ret
    except salt.exceptions.CommandExecutionError as exc:
        log.error('Error: {0}\n{1}'.format(exc, traceback.format_exc()))
        if si:
            __salt__['vsphere.disconnect'](si)
        ret.update({
            'result': False,
            'comment': str(exc)})
        return ret
