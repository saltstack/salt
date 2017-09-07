# -*- coding: utf-8 -*-
'''
Work with virtual machines managed by vagrant

    .. versionadded:: Oxygen
'''


# Import python libs
from __future__ import absolute_import
import os
import re
import sys
import shutil
import subprocess
import string  # pylint: disable=deprecated-module
import logging
import time
import datetime

# Import third party libs
import yaml
import jinja2
import jinja2.exceptions
from salt.ext import six
from salt.ext.six.moves import StringIO as _StringIO  # pylint: disable=import-error

# Import salt libs
import salt.utils
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.validate.net
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

# Set up template environment
JINJA = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, 'virt')
    )
)

__virtualname__ = 'varant'


def __virtual__():
    '''
    run Vagrant commands if possible
    '''
    if salt.utils.path.which('vagrant') is None:
        return (False, 'The vagrant module could not be loaded: vagrant command not found')
    return __virtualname__


def __get_conn():
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.
    '''
    # This has only been tested on kvm and xen, it needs to be expanded to
    # support all vm layers supported by libvirt


    hypervisor = __salt__['config.get']('libvirt:hypervisor', 'qemu')

    try:
        conn = conn_func = NotImplemented # conn_func[hypervisor][0](*conn_func[hypervisor][1])
    except Exception:
        raise CommandExecutionError(
            'Sorry, {0} failed to open a connection to the hypervisor '
            'software at {1}'.format(
                __grains__['fqdn'],
                conn_func[hypervisor][1][0]
            )
        )
    return conn


def _get_domain(*vms, **kwargs):
    '''
    Return a domain object for the named VM or return domain object for all VMs.
    '''
    ret = list()
    lookup_vms = list()
    conn = __get_conn()

    all_vms = list_domains()
    if not all_vms:
        raise CommandExecutionError('No virtual machines found.')

    if vms:
        for vm in vms:
            if vm not in all_vms:
                raise CommandExecutionError('The VM "{name}" is not present'.format(name=vm))
            else:
                lookup_vms.append(vm)
    else:
        lookup_vms = list(all_vms)

    for vm in lookup_vms:
        ret.append(conn.lookupByName(vm))

    return len(ret) == 1 and not kwargs.get('iterable') and ret[0] or ret



def init(name,
         cwd='',      # path to find Vagrantfile
         machine='',  # name of machine in Vagrantfile
         runas=None,  # defaults to SUDO_USER
         start=True,  # pylint: disable=redefined-outer-name
         # saltenv='base',
         # seed=True,
         install=True,
         # pub_key=None,
         # priv_key=None,
         # seed_cmd='seed.apply',
         **kwargs):
    '''
    Initialize a new Vagrant vm

    CLI Example:

    .. code-block:: bash

        salt 'hypervisor' vagrant.init salt_id /path/to/Vagrantfile machine_name
        salt my_laptop vagrant.init x1 /projects/bevy_master q1

    '''

    # if False:
    #             # Seed only if there is an image specified
    #             if seed and disk_image:
    #                 log.debug('Seed command is {0}'.format(seed_cmd))
    #                 __salt__[seed_cmd](
    #                     img_dest,
    #                     id_=name,
    #                     config=kwargs.get('config'),
    #                     install=install,
    #                     pub_key=pub_key,
    #                     priv_key=priv_key,


    # log.debug('Generating VM XML')
    # kwargs['enable_vnc'] = enable_vnc
    # xml = _gen_xml(name, cpu, mem, diskp, nicp, hypervisor, **kwargs)
    # try:
    #     define_xml_str(xml)
    # except libvirtError as err:
    #     # check if failure is due to this domain already existing
    #     if "domain '{}' already exists".format(name) in str(err):
    #         # continue on to seeding
    #         log.warning(err)
    #     else:
    #         raise err  # a real error we should report upwards

    if start:
        log.debug('Starting VM {0}'.format(name))
        _get_domain(name).create()

    return True


def list_domains():
    '''
    Return a list of available domains.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_domains
    '''
    vms = []
    vms.extend(list_active_vms())
    vms.extend(list_inactive_vms())
    return vms


def list_active_vms():
    '''
    Return a list of names for active virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_active_vms
    '''
    conn = __get_conn()
    vms = []
    for id_ in conn.listDomainsID():
        vms.append(conn.lookupByID(id_).name())
    return vms


def list_inactive_vms():
    '''
    Return a list of names for inactive virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms
    '''
    conn = __get_conn()
    vms = []
    for id_ in conn.listDefinedDomains():
        vms.append(id_)
    return vms



def vm_state(vm_=None):
    '''
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_state <domain>
    '''
    def _info(vm_):
        state = ''
        dom = _get_domain(vm_)
        raw = dom.info()
        state = NotImplemented #.get(raw[0], 'unknown')
        return state
    info = {}
    if vm_:
        info[vm_] = _info(vm_)
    else:
        for vm_ in list_domains():
            info[vm_] = _info(vm_)
    return info




def shutdown(vm_):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <domain>
    '''
    dom = _get_domain(vm_)
    return dom.shutdown() == 0


def pause(vm_):
    '''
    Pause the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pause <domain>
    '''
    dom = _get_domain(vm_)
    return dom.suspend() == 0


def resume(vm_):
    '''
    Resume the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.resume <domain>
    '''
    dom = _get_domain(vm_)
    return dom.resume() == 0


def start(name):
    '''
    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <domain>
    '''
    return _get_domain(name).create() == 0


def stop(name):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the power.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.stop <domain>
    '''
    return _get_domain(name).destroy() == 0


def reboot(name):
    '''
    Reboot a domain via ACPI request

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <domain>
    '''
    return _get_domain(name).reboot(NotImplemented) == 0


def reset(vm_):
    '''
    Reset a VM by emulating the reset button on a physical machine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reset <domain>
    '''
    dom = _get_domain(vm_)

    # reset takes a flag, like reboot, but it is not yet used
    # so we just pass in 0
    # see: http://libvirt.org/html/libvirt-libvirt.html#virDomainReset
    return dom.reset(0) == 0



def undefine(vm_):
    '''
    Remove a defined vm, this does not purge the virtual machine image, and
    this only works if the vm is powered down

    CLI Example:

    .. code-block:: bash

        salt '*' virt.undefine <domain>
    '''
    dom = _get_domain(vm_)
    return dom.undefine() == 0


def purge(vm_, dirs=False):
    '''
    Recursively destroy and delete a virtual machine, pass True for dir's to
    also delete the directories containing the virtual machine disk images -
    USE WITH EXTREME CAUTION!

    CLI Example:

    .. code-block:: bash

        salt '*' virt.purge <domain>
    '''

    directories = set()
    dirs = NotImplemented

    if dirs:
        for dir_ in directories:
            shutil.rmtree(dir_)
    undefine(vm_)
    return True

