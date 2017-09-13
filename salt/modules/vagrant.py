# -*- coding: utf-8 -*-
'''
Work with virtual machines managed by vagrant

    .. versionadded:: Oxygen
'''


# Import python libs
from __future__ import absolute_import, print_function
import subprocess
import logging

# Import salt libs
import salt.cache
import salt.utils
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltCacheError

log = logging.getLogger(__name__)

__virtualname__ = 'vagrant'


def __virtual__():
    '''
    run Vagrant commands if possible
    '''
    if salt.utils.path.which('vagrant') is None:
        return (False, 'The vagrant module could not be loaded: vagrant command not found')
    return __virtualname__


def _user(vm_):
    '''
    prepend "sudo -u username " if _vm['runas'] is defined
    :param vm_: the virtual machine configuration dictionary
    :return: "sudo -u <username> " or "" as needed
    '''
    try:
        return 'sudo -u {} '.format(vm_['runas'])
    except KeyError:
        return ''


def _update_cache(name, vm_):
    vm_cache = salt.cache.Cache(__opts__, expire=13140000)  # keep data for ten years
    vm_cache.store('vagrant', name, vm_)


def _get_cache(name):
    vm_cache = salt.cache.Cache(__opts__)
    try:
        vm_ = vm_cache.fetch('vagrant', name)
    except SaltCacheError:
        vm_ = {'name': name, 'machine': '', 'cwd': '.'}
        log.warn('Trouble reading Salt cache for vagrant[%S]', name)
    return vm_


def init(name,  # Salt id for created VM
         cwd,   # path to find Vagrantfile
         **kwargs): # other keyword arguments
    '''
    Initialize a new Vagrant vm

    CLI Example:

    .. code-block:: bash

        salt 'hypervisor' vagrant.init salt_id /path/to/Vagrantfile
        salt my_laptop vagrant.init x1 /projects/bevy_master machine=q1

        optional keyword arguments:
         machine='',  # name of machine in Vagrantfile
         runas=None,  # defaults to SUDO_USER
         start=True,  # start the machine when initialized
         deploy=True, # load Salt on the machine
         vm={},  # a dictionary of configuration settings
    '''
    vm_ = kwargs.copy()  # any keyword arguments are stored as configuration data
    if 'vm' in kwargs:   # allow caller to pass in a dictionary
        vm_.update(kwargs.pop('vm'))
    vm_.update(name=name, cwd=cwd)

    _update_cache(name, vm_)

    if start:
        log.debug('Starting VM {0}'.format(name))
        ret = start(name, vm_)
    else:
        ret = True
    return ret


def list_domains():
    '''
    Return a list of available domains.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.list_domains
    '''
    vms = []
    cmd = 'vagrant global-status {}'
    log.info('Executing command "%s"', cmd)
    output = subprocess.check_output(
        [cmd],
        shell=True,
        )
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        try:
            _ = int(tokens[0], 16)  # valid id numbers are hexadecimal
            vms.append(tokens)
        except (ValueError, IndexError):
            pass
    return vms


def list_active_vms():
    '''
    Return a list of names for active virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.list_active_vms  cwd=/projects/project_1
    '''
    vms = []
    cmd = 'vagrant status'
    log.info('Executing command "%s"', cmd)
    output = subprocess.check_output(
        [cmd],
        shell=True,
        )
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        if len(tokens) > 1:
            if tokens[1] == 'running':
                vms.append(tokens[0])
    return vms


def list_inactive_vms():
    '''
    Return a list of names for inactive virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms cwd=/projects/project_1
    '''
    vms = []
    cmd = 'vagrant status'
    log.info('Executing command "%s"', cmd)
    output = subprocess.check_output(
        [cmd],
        shell=True,
        )
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        if len(tokens) > 1:
            if tokens[1] != 'running':
                vms.append(tokens[0])
    return vms


def vm_state(name=''):
    '''
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.vm_state <name>  cwd='/projects/project_1'
    '''
    info = {}
    cmd = 'vagrant status {}'.format(name)
    log.info('Executing command "%s"', cmd)
    output = subprocess.check_output(
        [cmd],
        shell=True,
    )
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        if tokens[-1].endswith(')') :
            try:
                info[tokens[0]]['state'] = tokens[1]
                info[tokens[0]]['provider'] = tokens[2] - '(' - ')'
            except IndexError:
                pass
    return info


def shutdown(name):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.shutdown <name>
    '''
    return stop(name)


def pause(name):
    '''
    Pause (suspend) the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.pause <name>
    '''
    vm_ = _get_cache(name)
    machine = vm_['machine']

    cmd = '{}vagrant suspend {}'.format(_user(vm_), machine)
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
        [cmd],
        shell=True,
        cwd=vm_.get('cwd', None)
        )
    return ret



def start(name, vm_=None):
    '''
    Start a defined virtual machine.  The machine must have been previously defined
    using "vagrant.init".

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.start <domain>
    '''
    fudged_opts = __opts__.copy()  # make a mock of cloud configuration info
    fudged_opts['profiles'] = {}
    fudged_opts['providers'] = {}

    if vm_ is None:
        vm_ = _get_cache(name)

    machine = vm_['machine']

    cmd = '{}vagrant up {}'.format(_user(vm_), machine)
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
            [cmd],
            shell=True,
            cwd=vm_.get('cwd', None)
            )
    if ret:
        raise CommandExecutionError('Error starting Vagrant machine')

    # the ssh address and port are not known until after the machine boots.
    # so we must detect it and record it then
    if not vm_['ssh_host']:
        log.info('requesting vagrant ssh-config for %s', machine or 'Vagrant default')
        output = subprocess.check_output(
            ['{}vagrant ssh-config {}'.format(_user(vm_), machine)],
            shell=True,
            cwd=vm_.get('cwd', None)
        )
        reply = salt.utils.stringutils.to_str(output)
        ssh_config = {}
        for line in reply.split('\n'):  # build a dictionary of the text reply
            tokens = line.strip().split()
            if len(tokens) == 2:  # each two-token line becomes a key:value pair
                ssh_config[tokens[0]] = tokens[1]
        log.debug('ssh_config=%s', repr(ssh_config))


        vm_.setdefault('key_filename', ssh_config['IdentityFile'])
        vm_.setdefault('ssh_username', ssh_config['User'])
        vm_['ssh_host'] = ssh_config['HostName']
        vm_.setdefault('ssh_port', ssh_config['Port'])
        _update_cache(name, vm_)

    log.info('Provisioning machine %s as node %s using ssh %s',
             machine, vm_['name'], vm_['ssh_host'])
    ret = __utils__['cloud.bootstrap'](vm_, fudged_opts)

    return ret


def stop(name):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the power.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.stop <name>
    '''
    vm_ = _get_cache(name)
    machine = vm_['machine']

    cmd = '{}vagrant halt {}'.format(_user(vm_), machine)
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
        [cmd],
        shell=True,
        cwd=vm_.get('cwd', None)
        )
    return ret


def reboot(name):
    '''
    Reboot a VM

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.reboot <name>
    '''
    vm_ = _get_cache(name)
    machine = vm_['machine']

    cmd = '{}vagrant reload {}'.format(_user(vm_), machine)
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
        [cmd],
        shell=True,
        cwd=vm_.get('cwd', None)
        )
    return ret


def destroy(name):
    '''
    Destroy and delete a virtual machine.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.destroy <name>
    '''

    vm_ = _get_cache(name)
    machine = vm_['machine']

    cmd = '{}vagrant destroy -f {}'.format(_user(vm_), machine)
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
        [cmd],
        shell=True,
        cwd=vm_.get('cwd', None)
        )
    return ret
