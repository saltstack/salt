# -*- coding: utf-8 -*-
'''
Manage virt
===========

For the key certificate this state uses the external pillar in the master to call
for the generation and signing of certificates for systems running libvirt:

.. code-block:: yaml

    libvirt_keys:
      virt.keys
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import fnmatch
import os

try:
    import libvirt  # pylint: disable=import-error
    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False

# Import Salt libs
import salt.utils.args
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

__virtualname__ = 'virt'


def __virtual__():
    '''
    Only if virt module is available.

    :return:
    '''

    if 'virt.node_info' in __salt__:
        return __virtualname__
    return False


def keys(name, basepath='/etc/pki', **kwargs):
    '''
    Manage libvirt keys.

    name
        The name variable used to track the execution

    basepath
        Defaults to ``/etc/pki``, this is the root location used for libvirt
        keys on the hypervisor

    The following parameters are optional:

        country
            The country that the certificate should use.  Defaults to US.

        .. versionadded:: 2018.3.0

        state
            The state that the certificate should use.  Defaults to Utah.

        .. versionadded:: 2018.3.0

        locality
            The locality that the certificate should use.
            Defaults to Salt Lake City.

        .. versionadded:: 2018.3.0

        organization
            The organization that the certificate should use.
            Defaults to Salted.

        .. versionadded:: 2018.3.0

        expiration_days
            The number of days that the certificate should be valid for.
            Defaults to 365 days (1 year)

        .. versionadded:: 2018.3.0

    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    # Grab all kwargs to make them available as pillar values
    # rename them to something hopefully unique to avoid
    # overriding anything existing
    pillar_kwargs = {}
    for key, value in six.iteritems(kwargs):
        pillar_kwargs['ext_pillar_virt.{0}'.format(key)] = value

    pillar = __salt__['pillar.ext']({'libvirt': '_'}, pillar_kwargs)
    paths = {
        'serverkey': os.path.join(basepath, 'libvirt',
                                  'private', 'serverkey.pem'),
        'servercert': os.path.join(basepath, 'libvirt',
                                   'servercert.pem'),
        'clientkey': os.path.join(basepath, 'libvirt',
                                  'private', 'clientkey.pem'),
        'clientcert': os.path.join(basepath, 'libvirt',
                                   'clientcert.pem'),
        'cacert': os.path.join(basepath, 'CA', 'cacert.pem')
    }

    for key in paths:
        p_key = 'libvirt.{0}.pem'.format(key)
        if p_key not in pillar:
            continue
        if not os.path.exists(os.path.dirname(paths[key])):
            os.makedirs(os.path.dirname(paths[key]))
        if os.path.isfile(paths[key]):
            with salt.utils.files.fopen(paths[key], 'r') as fp_:
                if salt.utils.stringutils.to_unicode(fp_.read()) != pillar[p_key]:
                    ret['changes'][key] = 'update'
        else:
            ret['changes'][key] = 'new'

    if not ret['changes']:
        ret['comment'] = 'All keys are correct'
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Libvirt keys are set to be updated'
        ret['changes'] = {}
    else:
        for key in ret['changes']:
            with salt.utils.files.fopen(paths[key], 'w+') as fp_:
                fp_.write(
                    salt.utils.stringutils.to_str(
                        pillar['libvirt.{0}.pem'.format(key)]
                    )
                )

        ret['comment'] = 'Updated libvirt certs and keys'

    return ret


def _virt_call(domain, function, section, comment, **kwargs):
    '''
    Helper to call the virt functions. Wildcards supported.

    :param domain:
    :param function:
    :param section:
    :param comment:
    :return:
    '''
    ret = {'name': domain, 'changes': {}, 'result': True, 'comment': ''}
    targeted_domains = fnmatch.filter(__salt__['virt.list_domains'](), domain)
    changed_domains = list()
    ignored_domains = list()
    for targeted_domain in targeted_domains:
        try:
            response = __salt__['virt.{0}'.format(function)](targeted_domain, **kwargs)
            if isinstance(response, dict):
                response = response['name']
            changed_domains.append({'domain': targeted_domain, function: response})
        except libvirt.libvirtError as err:
            ignored_domains.append({'domain': targeted_domain, 'issue': six.text_type(err)})
    if not changed_domains:
        ret['result'] = False
        ret['comment'] = 'No changes had happened'
        if ignored_domains:
            ret['changes'] = {'ignored': ignored_domains}
    else:
        ret['changes'] = {section: changed_domains}
        ret['comment'] = comment

    return ret


def stopped(name):
    '''
    Stops a VM by shutting it down nicely.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'shutdown', 'stopped', "Machine has been shut down")


def powered_off(name):
    '''
    Stops a VM by power off.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'stop', 'unpowered', 'Machine has been powered off')


def running(name, **kwargs):
    '''
    Starts an existing guest, or defines and starts a new VM with specified arguments.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.running

    .. code-block:: yaml

        domain_name:
          virt.running:
            - cpu: 2
            - mem: 2048
            - eth0_mac: 00:00:6a:53:00:e3

    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': '{0} is running'.format(name)
           }

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    cpu = kwargs.pop('cpu', False)
    mem = kwargs.pop('mem', False)
    image = kwargs.pop('image', False)

    try:
        try:
            __salt__['virt.vm_state'](name)
            if __salt__['virt.vm_state'](name) != 'running':
                __salt__['virt.start'](name)
                ret['changes'][name] = 'Domain started'
                ret['comment'] = 'Domain {0} started'.format(name)
            else:
                ret['comment'] = 'Domain {0} exists and is running'.format(name)
        except CommandExecutionError:
            kwargs = salt.utils.args.clean_kwargs(**kwargs)
            __salt__['virt.init'](name, cpu=cpu, mem=mem, image=image, **kwargs)
            ret['changes'][name] = 'Domain defined and started'
            ret['comment'] = 'Domain {0} defined and started'.format(name)
    except libvirt.libvirtError as err:
        # Something bad happened when starting the VM, report it
        ret['comment'] = six.text_type(err)
        ret['result'] = False

    return ret


def snapshot(name, suffix=None):
    '''
    Takes a snapshot of a particular VM or by a UNIX-style wildcard.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.snapshot:
            - suffix: periodic

        domain*:
          virt.snapshot:
            - suffix: periodic
    '''

    return _virt_call(name, 'snapshot', 'saved', 'Snapshot has been taken', suffix=suffix)


# Deprecated states
def rebooted(name):
    '''
    Reboots VMs

    .. versionadded:: 2016.3.0

    :param name:
    :return:
    '''

    return _virt_call(name, 'reboot', 'rebooted', "Machine has been rebooted")


def unpowered(name):
    '''
    .. deprecated:: 2016.3.0
       Use :py:func:`~salt.modules.virt.powered_off` instead.

    Stops a VM by power off.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'stop', 'unpowered', 'Machine has been powered off')


def saved(name, suffix=None):
    '''
    .. deprecated:: 2016.3.0
       Use :py:func:`~salt.modules.virt.snapshot` instead.

    Takes a snapshot of a particular VM or by a UNIX-style wildcard.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.saved:
            - suffix: periodic

        domain*:
          virt.saved:
            - suffix: periodic
    '''

    return _virt_call(name, 'snapshot', 'saved', 'Snapshots has been taken', suffix=suffix)


def reverted(name, snapshot=None, cleanup=False):  # pylint: disable=redefined-outer-name
    '''
    .. deprecated:: 2016.3.0

    Reverts to the particular snapshot.

    .. versionadded:: 2016.3.0

    .. code-block:: yaml

        domain_name:
          virt.reverted:
            - cleanup: True

        domain_name_1:
          virt.reverted:
            - snapshot: snapshot_name
            - cleanup: False
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    try:
        domains = fnmatch.filter(__salt__['virt.list_domains'](), name)
        if not domains:
            ret['comment'] = 'No domains found for criteria "{0}"'.format(name)
        else:
            ignored_domains = list()
            if len(domains) > 1:
                ret['changes'] = {'reverted': list()}
            for domain in domains:
                result = {}
                try:
                    result = __salt__['virt.revert_snapshot'](domain, snapshot=snapshot, cleanup=cleanup)
                    result = {'domain': domain, 'current': result['reverted'], 'deleted': result['deleted']}
                except CommandExecutionError as err:
                    if len(domains) > 1:
                        ignored_domains.append({'domain': domain, 'issue': six.text_type(err)})
                if len(domains) > 1:
                    if result:
                        ret['changes']['reverted'].append(result)
                else:
                    ret['changes'] = result
                    break

            ret['result'] = len(domains) != len(ignored_domains)
            if ret['result']:
                ret['comment'] = 'Domain{0} has been reverted'.format(len(domains) > 1 and "s" or "")
            if ignored_domains:
                ret['changes']['ignored'] = ignored_domains
            if not ret['changes']['reverted']:
                ret['changes'].pop('reverted')
    except libvirt.libvirtError as err:
        ret['comment'] = six.text_type(err)
    except CommandExecutionError as err:
        ret['comment'] = six.text_type(err)

    return ret


def network_define(name, bridge, forward, **kwargs):
    '''
    Defines and starts a new network with specified arguments.

    .. code-block:: yaml

        domain_name:
          virt.network_define

    .. code-block:: yaml

        network_name:
          virt.network_define:
            - bridge: main
            - forward: bridge
            - vport: openvswitch
            - tag: 180
            - autostart: True
            - start: True

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''
           }

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    vport = kwargs.pop('vport', None)
    tag = kwargs.pop('tag', None)
    autostart = kwargs.pop('autostart', True)
    start = kwargs.pop('start', True)

    try:
        result = __salt__['virt.net_define'](name, bridge, forward, vport, tag=tag, autostart=autostart, start=start)
        if result:
            ret['changes'][name] = 'Network {0} has been created'.format(name)
            ret['result'] = True
        else:
            ret['comment'] = 'Network {0} created fail'.format(name)
    except libvirt.libvirtError as err:
        if err.get_error_code() == libvirt.VIR_ERR_NETWORK_EXIST or libvirt.VIR_ERR_OPERATION_FAILED:
            ret['result'] = True
            ret['comment'] = 'The network already exist'
        else:
            ret['comment'] = err.get_error_message()

    return ret


def pool_define(name, **kwargs):
    '''
    Defines and starts a new pool with specified arguments.

    .. code-block:: yaml

        pool_name:
          virt.pool_define

    .. code-block:: yaml

        pool_name:
          virt.pool_define:
            - ptype: logical
            - target: pool
            - source: sda1
            - autostart: True
            - start: True

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''
           }

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    ptype = kwargs.pop('ptype', None)
    target = kwargs.pop('target', None)
    source = kwargs.pop('source', None)
    autostart = kwargs.pop('autostart', True)
    start = kwargs.pop('start', True)

    try:
        result = __salt__['virt.pool_define_build'](name, ptype=ptype, target=target,
                                                    source=source, autostart=autostart, start=start)
        if result:
            if 'Pool exist' in result:
                if 'Pool update' in result:
                    ret['changes'][name] = 'Pool {0} has been updated'.format(name)
                else:
                    ret['comment'] = 'Pool {0} already exist'.format(name)
            else:
                ret['changes'][name] = 'Pool {0} has been created'.format(name)
            ret['result'] = True
        else:
            ret['comment'] = 'Pool {0} created fail'.format(name)
    except libvirt.libvirtError as err:
        if err.get_error_code() == libvirt.VIR_ERR_STORAGE_POOL_BUILT or libvirt.VIR_ERR_OPERATION_FAILED:
            ret['result'] = True
            ret['comment'] = 'The pool already exist'
        ret['comment'] = err.get_error_message()

    return ret
