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
import salt.utils.versions
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


def _virt_call(domain, function, section, comment,
               connection=None, username=None, password=None, **kwargs):
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
            response = __salt__['virt.{0}'.format(function)](targeted_domain,
                                                             connection=connection,
                                                             username=username,
                                                             password=password,
                                                             **kwargs)
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


def stopped(name, connection=None, username=None, password=None):
    '''
    Stops a VM by shutting it down nicely.

    .. versionadded:: 2016.3.0

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'shutdown', 'stopped', "Machine has been shut down",
                      connection=connection, username=username, password=password)


def powered_off(name, connection=None, username=None, password=None):
    '''
    Stops a VM by power off.

    .. versionadded:: 2016.3.0

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'stop', 'unpowered', 'Machine has been powered off',
                      connection=connection, username=username, password=password)


def running(name,
            cpu=None,
            mem=None,
            image=None,
            vm_type=None,
            disk_profile=None,
            disks=None,
            nic_profile=None,
            interfaces=None,
            graphics=None,
            loader=None,
            seed=True,
            install=True,
            pub_key=None,
            priv_key=None,
            update=False,
            connection=None,
            username=None,
            password=None,
            os_type=None,
            arch=None):
    '''
    Starts an existing guest, or defines and starts a new VM with specified arguments.

    .. versionadded:: 2016.3.0

    :param name: name of the virtual machine to run
    :param cpu: number of CPUs for the virtual machine to create
    :param mem: amount of memory in MiB for the new virtual machine
    :param image: disk image to use for the first disk of the new VM

        .. deprecated:: 2019.2.0
    :param vm_type: force virtual machine type for the new VM. The default value is taken from
        the host capabilities. This could be useful for example to use ``'qemu'`` type instead
        of the ``'kvm'`` one.

        .. versionadded:: 2019.2.0
    :param disk_profile:
        Name of the disk profile to use for the new virtual machine

        .. versionadded:: 2019.2.0
    :param disks:
        List of disk to create for the new virtual machine.
        See the **Disk Definitions** section of the :py:func:`virt.init
        <salt.modules.virt.init>` function for more details on the items on
        this list.

        .. versionadded:: 2019.2.0
    :param nic_profile:
        Name of the network interfaces profile to use for the new virtual machine

        .. versionadded:: 2019.2.0
    :param interfaces:
        List of network interfaces to create for the new virtual machine.
        See the **Network Interface Definitions** section of the
        :py:func:`virt.init <salt.modules.virt.init>` function for more details
        on the items on this list.

        .. versionadded:: 2019.2.0
    :param graphics:
        Graphics device to create for the new virtual machine.
        See the **Graphics Definition** section of the :py:func:`virt.init
        <salt.modules.virt.init>` function for more details on this dictionary.

        .. versionadded:: 2019.2.0
    :param loader:
        Firmware loader for the new virtual machine.
        See the **Loader Definition** section of the :py:func:`virt.init
        <salt.modules.virt.init>` function for more details on this dictionary.

        .. versionadded:: 2019.2.0
    :param saltenv:
        Fileserver environment (Default: ``'base'``).
        See :mod:`cp module for more details <salt.modules.cp>`

        .. versionadded:: 2019.2.0
    :param seed: ``True`` to seed the disk image. Only used when the ``image`` parameter is provided.
                 (Default: ``True``)

        .. versionadded:: 2019.2.0
    :param install: install salt minion if absent (Default: ``True``)

        .. versionadded:: 2019.2.0
    :param pub_key: public key to seed with (Default: ``None``)

        .. versionadded:: 2019.2.0
    :param priv_key: public key to seed with (Default: ``None``)

        .. versionadded:: 2019.2.0
    :param seed_cmd: Salt command to execute to seed the image. (Default: ``'seed.apply'``)

        .. versionadded:: 2019.2.0
    :param update: set to ``True`` to update a defined module. (Default: ``False``)

        .. versionadded:: 2019.2.0
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param os_type:
        type of virtualization as found in the ``//os/type`` element of the libvirt definition.
        The default value is taken from the host capabilities, with a preference for ``hvm``.
        Only used when creating a new virtual machine.

        .. versionadded:: Neon
    :param arch:
        architecture of the virtual machine. The default value is taken from the host capabilities,
        but ``x86_64`` is prefed over ``i686``. Only used when creating a new virtual machine.

        .. versionadded:: Neon

    .. rubric:: Example States

    Make sure an already-defined virtual machine called ``domain_name`` is running:

    .. code-block:: yaml

        domain_name:
          virt.running

    Do the same, but define the virtual machine if needed:

    .. code-block:: yaml

        domain_name:
          virt.running:
            - cpu: 2
            - mem: 2048
            - disk_profile: prod
            - disks:
              - name: system
                size: 8192
                overlay_image: True
                pool: default
                image: /path/to/image.qcow2
              - name: data
                size: 16834
            - nic_profile: prod
            - interfaces:
              - name: eth0
                mac: 01:23:45:67:89:AB
              - name: eth1
                type: network
                source: admin
            - graphics:
              - type: spice
                listen:
                  - type: address
                    address: 192.168.0.125

    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': '{0} is running'.format(name)
           }

    try:
        try:
            __salt__['virt.vm_state'](name)
            if __salt__['virt.vm_state'](name) != 'running':
                action_msg = 'started'
                if update:
                    status = __salt__['virt.update'](name,
                                                     cpu=cpu,
                                                     mem=mem,
                                                     disk_profile=disk_profile,
                                                     disks=disks,
                                                     nic_profile=nic_profile,
                                                     interfaces=interfaces,
                                                     graphics=graphics,
                                                     live=False,
                                                     connection=connection,
                                                     username=username,
                                                     password=password)
                    if status['definition']:
                        action_msg = 'updated and started'
                __salt__['virt.start'](name)
                ret['changes'][name] = 'Domain {0}'.format(action_msg)
                ret['comment'] = 'Domain {0} {1}'.format(name, action_msg)
            else:
                if update:
                    status = __salt__['virt.update'](name,
                                                     cpu=cpu,
                                                     mem=mem,
                                                     disk_profile=disk_profile,
                                                     disks=disks,
                                                     nic_profile=nic_profile,
                                                     interfaces=interfaces,
                                                     graphics=graphics,
                                                     connection=connection,
                                                     username=username,
                                                     password=password)
                    ret['changes'][name] = status
                    if status.get('errors', None):
                        ret['comment'] = 'Domain {0} updated, but some live update(s) failed'.format(name)
                    elif not status['definition']:
                        ret['comment'] = 'Domain {0} exists and is running'.format(name)
                    else:
                        ret['comment'] = 'Domain {0} updated, restart to fully apply the changes'.format(name)
                else:
                    ret['comment'] = 'Domain {0} exists and is running'.format(name)
        except CommandExecutionError:
            if image:
                salt.utils.versions.warn_until(
                    'Sodium',
                    '\'image\' parameter has been deprecated. Rather use the \'disks\' parameter '
                    'to override or define the image. \'image\' will be removed in {version}.'
                )
            __salt__['virt.init'](name,
                                  cpu=cpu,
                                  mem=mem,
                                  os_type=os_type,
                                  arch=arch,
                                  image=image,
                                  hypervisor=vm_type,
                                  disk=disk_profile,
                                  disks=disks,
                                  nic=nic_profile,
                                  interfaces=interfaces,
                                  graphics=graphics,
                                  loader=loader,
                                  seed=seed,
                                  install=install,
                                  pub_key=pub_key,
                                  priv_key=priv_key,
                                  connection=connection,
                                  username=username,
                                  password=password)
            ret['changes'][name] = 'Domain defined and started'
            ret['comment'] = 'Domain {0} defined and started'.format(name)
    except libvirt.libvirtError as err:
        # Something bad happened when starting / updating the VM, report it
        ret['comment'] = six.text_type(err)
        ret['result'] = False

    return ret


def snapshot(name, suffix=None, connection=None, username=None, password=None):
    '''
    Takes a snapshot of a particular VM or by a UNIX-style wildcard.

    .. versionadded:: 2016.3.0

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: yaml

        domain_name:
          virt.snapshot:
            - suffix: periodic

        domain*:
          virt.snapshot:
            - suffix: periodic
    '''

    return _virt_call(name, 'snapshot', 'saved', 'Snapshot has been taken', suffix=suffix,
                      connection=connection, username=username, password=password)


# Deprecated states
def rebooted(name, connection=None, username=None, password=None):
    '''
    Reboots VMs

    .. versionadded:: 2016.3.0

    :param name:

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    '''

    return _virt_call(name, 'reboot', 'rebooted', "Machine has been rebooted",
                      connection=connection, username=username, password=password)


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


def network_running(name,
                    bridge,
                    forward,
                    vport=None,
                    tag=None,
                    autostart=True,
                    connection=None,
                    username=None,
                    password=None):
    '''
    Defines and starts a new network with specified arguments.

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

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

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''
           }

    try:
        info = __salt__['virt.network_info'](name, connection=connection, username=username, password=password)
        if info:
            if info['active']:
                ret['comment'] = 'Network {0} exists and is running'.format(name)
            else:
                __salt__['virt.network_start'](name, connection=connection, username=username, password=password)
                ret['changes'][name] = 'Network started'
                ret['comment'] = 'Network {0} started'.format(name)
        else:
            __salt__['virt.network_define'](name,
                                            bridge,
                                            forward,
                                            vport,
                                            tag=tag,
                                            autostart=autostart,
                                            start=True,
                                            connection=connection,
                                            username=username,
                                            password=password)
            ret['changes'][name] = 'Network defined and started'
            ret['comment'] = 'Network {0} defined and started'.format(name)
    except libvirt.libvirtError as err:
        ret['result'] = False
        ret['comment'] = err.get_error_message()

    return ret


def pool_running(name,
                 ptype=None,
                 target=None,
                 permissions=None,
                 source=None,
                 transient=False,
                 autostart=True,
                 connection=None,
                 username=None,
                 password=None):
    '''
    Defines and starts a new pool with specified arguments.

    .. versionadded:: 2019.2.0

    :param ptype: libvirt pool type
    :param target: full path to the target device or folder. (Default: ``None``)
    :param permissions: target permissions. See the **Permissions definition**
        section of the :py:func:`virt.pool_define
        <salt.module.virt.pool_define>` documentation for more details on this
        structure.
    :param source:
        dictionary containing keys matching the ``source_*`` parameters in function
        :py:func:`virt.pool_define <salt.modules.virt.pool_define>`.
    :param transient:
        when set to ``True``, the pool will be automatically undefined after
        being stopped. (Default: ``False``)
    :param autostart:
        Whether to start the pool when booting the host. (Default: ``True``)
    :param start:
        When ``True``, define and start the pool, otherwise the pool will be
        left stopped.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. code-block:: yaml

        pool_name:
          virt.pool_define

    .. code-block:: yaml

        pool_name:
          virt.pool_define:
            - ptype: netfs
            - target: /mnt/cifs
            - permissions:
                - mode: 0770
                - owner: 1000
                - group: 100
            - source:
                - dir: samba_share
                - hosts:
                   one.example.com
                   two.example.com
                - format: cifs
            - autostart: True

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''
           }

    try:
        info = __salt__['virt.pool_info'](name, connection=connection, username=username, password=password)
        if info:
            if info['state'] == 'running':
                ret['comment'] = 'Pool {0} exists and is running'.format(name)
            else:
                __salt__['virt.pool_start'](name, connection=connection, username=username, password=password)
                ret['changes'][name] = 'Pool started'
                ret['comment'] = 'Pool {0} started'.format(name)
        else:
            __salt__['virt.pool_define'](name,
                                         ptype=ptype,
                                         target=target,
                                         permissions=permissions,
                                         source_devices=(source or {}).get('devices', None),
                                         source_dir=(source or {}).get('dir', None),
                                         source_adapter=(source or {}).get('adapter', None),
                                         source_hosts=(source or {}).get('hosts', None),
                                         source_auth=(source or {}).get('auth', None),
                                         source_name=(source or {}).get('name', None),
                                         source_format=(source or {}).get('format', None),
                                         transient=transient,
                                         start=False,
                                         connection=connection,
                                         username=username,
                                         password=password)
            if autostart:
                __salt__['virt.pool_set_autostart'](name,
                                                    state='on' if autostart else 'off',
                                                    connection=connection,
                                                    username=username,
                                                    password=password)

            __salt__['virt.pool_build'](name,
                                        connection=connection,
                                        username=username,
                                        password=password)
            ret['changes'][name] = 'Pool defined and started'
            ret['comment'] = 'Pool {0} defined and started'.format(name)
    except libvirt.libvirtError as err:
        ret['comment'] = err.get_error_message()
        ret['result'] = False

    return ret
