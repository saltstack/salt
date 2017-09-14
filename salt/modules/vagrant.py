# -*- coding: utf-8 -*-
'''
Work with virtual machines managed by vagrant

    .. versionadded:: Oxygen
'''


# Import python libs
from __future__ import absolute_import, print_function
import subprocess
import logging
from collections import defaultdict

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
        return False, 'The vagrant module could not be loaded: vagrant command not found'
    return __virtualname__


def _update_cache(name, vm_, opts=None):
    vm_cache = salt.cache.Cache(__opts__, expire=13140000)  # keep data for ten years
    vm_cache.store('vagrant', name, vm_)
    if opts:
        vm_cache.store('vagrant_opts', name, opts)


def _get_cached_vm(name):
    vm_cache = salt.cache.Cache(__opts__)
    try:
        vm_ = vm_cache.fetch('vagrant', name)
    except SaltCacheError:
        vm_ = {'name': name, 'machine': '', 'cwd': '.'}
        log.warn('Trouble reading Salt cache for vagrant[%s]', name)
    return vm_


def _get_cached_opts(name):
    vm_cache = salt.cache.Cache(__opts__)
    try:
        opts = vm_cache.fetch('vagrant_opts', name)
    except SaltCacheError:
        log.warn('Trouble reading Salt opts cache for vagrant[%s]', name)
        return None
    return opts


def _erase_cache(name):
    vm_cache = salt.cache.Cache(__opts__)
    try:
        vm_cache.flush('vagrant', name)
    except SaltCacheError:
        pass
    try:
        vm_cache.flush('vagrant_opts', name)
    except SaltCacheError:
        pass


def version():
    '''
    Return the version of Vagrant on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.version
    '''
    cmd = 'vagrant -v'
    output = subprocess.check_output([cmd], shell=True)
    reply = salt.utils.stringutils.to_str(output)
    return reply.strip()


def list_domains():
    '''
    Return a cached list of all available Vagrant VMs on host.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.list_domains
    '''
    vms = []
    cmd = 'vagrant global-status {}'
    log.info('Executing command "%s"', cmd)
    try:
        output = subprocess.check_output([cmd], shell=True)
    except subprocess.CalledProcessError:
        return []
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        try:
            _ = int(tokens[0], 16)  # valid id numbers are hexadecimal
            vms.append(' '.join(tokens))
        except (ValueError, IndexError):
            pass  # skip other lines
    return vms


def list_active_vms(cwd=None):
    '''
    Return a list of names for active virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.list_active_vms  cwd=/projects/project_1
    '''
    vms = []
    cmd = 'vagrant status'
    log.info('Executing command "%s"', cmd)
    try:
        output = subprocess.check_output(
            [cmd],
            shell=True,
            cwd=cwd)
    except subprocess.CalledProcessError:
        return []
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        if len(tokens) > 1:
            if tokens[1] == 'running':
                vms.append(tokens[0])
    return vms


def list_inactive_vms(cwd=None):
    '''
    Return a list of names for inactive virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms cwd=/projects/project_1
    '''
    vms = []
    cmd = 'vagrant status'
    log.info('Executing command "%s"', cmd)
    try:
        output = subprocess.check_output(
            [cmd],
            shell=True,
            cwd=cwd)
    except subprocess.CalledProcessError:
        return []
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        if len(tokens) > 1 and tokens[-1].endswith(')'):
            if tokens[1] != 'running':
                vms.append(tokens[0])
    return vms


def vm_state(name='', cwd=None):
    '''
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.vm_state <name>  cwd=/projects/project_1
    '''
    info = {}
    cmd = 'vagrant status {}'.format(name)
    log.info('Executing command "%s"', cmd)
    try:
        output = subprocess.check_output(
            [cmd],
            shell=True,
            cwd=cwd)
    except subprocess.CalledProcessError:
        return {}
    reply = salt.utils.stringutils.to_str(output)
    for line in reply.split('\n'):  # build a list of the text reply
        print(line)
        tokens = line.strip().split()
        if len(tokens) > 1 and tokens[-1].endswith(')') :
            try:
                info[tokens[0]] = {'state': ' '.join(tokens[1:-1])}
                info[tokens[0]]['provider'] = tokens[-1].lstrip('(').rstrip(')')
            except IndexError:
                pass
    return info


def init(name,  # Salt_id for created VM
         cwd,   # path to find Vagrantfile
         machine='',  # name of machine in Vagrantfile
         runas=None,  # username who owns Vagrant box
         start=True,  # start the machine when initialized
         deploy=None,  # load Salt onto the virtual machine, default=True
         vagrant_provider='', # vagrant provider engine name
         vm={},  # a dictionary of VM configuration settings
         opts=None, # a dictionary of master configuration settings
         ):
    '''
    Initialize a new Vagrant vm

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.init <salt_id> /path/to/Vagrantfile
        salt my_laptop vagrant.init x1 /projects/bevy_master machine=quail1
    '''
    vm_ = vm.copy()  #  passed configuration data
    vm_['name'] = name
    vm_['cwd'] = cwd
    #  passed-in keyword arguments overwrite vm dictionary values
    vm_['machine'] = machine or vm_.get('machine', machine)
    vm_['runas'] = runas or vm_.get('runas', runas)
    vm_['deploy'] = deploy if deploy is not None else vm_.get('deploy', True)
    vm_['vagrant_provider'] = vagrant_provider or vm_.get('vagrant_provider', '')
    _update_cache(name, vm_, opts)

    if start:
        log.debug('Starting VM {0}'.format(name))
        ret = _start(name, vm_, opts)
    else:
        ret = True
    return ret


def _runas_sudo(vm_, command):
    '''
    prepend "sudo -u <runas> " if _vm['runas'] is defined
    :param vm_: the virtual machine configuration dictionary
    :param command: the command line which will be sent
    :return: "sudo -u <runas> command" or "command" as needed
    '''
    runas = vm_.get('runas', False)
    if runas:
        return 'sudo -u {} {}'.format(runas, command)
    return command


def start(name, vm_=None, opts=None):
    '''
    Start (vagrant up) a defined virtual machine by salt_id name.
    The machine must have been previously defined using "vagrant.init".

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.start <salt_id>
    '''
    ret = _start(name, vm_, opts)


def _start(name, vm_, opts):  # internal call name, because "start" is a keyword argument to vagrant.init
    fudged_opts = defaultdict(lambda: None)
    if opts is None:
        fudged_opts.update(__opts__)
        fudged_opts.update(_get_cached_opts(name))
        fudged_opts.setdefault('profiles', defaultdict(lambda: ''))
        fudged_opts.setdefault('providers', {})
        fudged_opts.setdefault('deploy_scripts_search_path', vm_.get('deploy_scripts_search_path', []))

    if vm_ is None:
        vm_ = _get_cached_vm(name)

    machine = vm_['machine']

    vagrant_provider = vm_.get('vagrant_provider', '')
    provider_ = '--provider={}'.format(vagrant_provider) if vagrant_provider else ''
    cmd = _runas_sudo(vm_, 'vagrant up {} {}'.format(machine, provider_))
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
    if 'ssh_host' not in vm_:
        log.info('requesting vagrant ssh-config for %s', machine or 'Vagrant default')
        output = subprocess.check_output(
            [_runas_sudo(vm_, 'vagrant ssh-config {}'.format(machine))],
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

    vm_.setdefault('driver', 'vagrant.start')  # provide a dummy value needed in get_cloud_config_value
    vm_.setdefault('provider', '')  # provide a dummy value needed in get_cloud_config_value
    vm_.setdefault('profile', '')  # provide a dummy value needed in get_cloud_config_value
    log.info('Provisioning machine %s as node %s using ssh %s',
             machine, vm_['name'], vm_['ssh_host'])
    ret = __utils__['cloud.bootstrap'](vm_, fudged_opts)

    return ret



def shutdown(name):
    '''
    Send a soft shutdown signal to the named vm.
    ( for Vagrant, alternate name for vagrant.stop )

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.shutdown <salt_id>
    '''
    return stop(name)


def stop(name):
    '''
    Hard shutdown the virtual machine.
    ( Vagrant will attempt a soft shutdown first. )

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.stop <salt_id>
    '''
    vm_ = _get_cached_vm(name)
    machine = vm_['machine']

    cmd = _runas_sudo(vm_, 'vagrant halt {}'.format(machine))
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
        [cmd],
        shell=True,
        cwd=vm_.get('cwd', None)
        )
    return ret


def pause(name):
    '''
    Pause (suspend) the named vm

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.pause <salt_id>
    '''
    vm_ = _get_cached_vm(name)
    machine = vm_['machine']

    cmd = _runas_sudo(vm_, 'vagrant suspend {}'.format(machine))
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

        salt <host> vagrant.reboot <salt_id>
    '''
    vm_ = _get_cached_vm(name)
    machine = vm_['machine']

    cmd = _runas_sudo(vm_, 'vagrant reload {}'.format(machine))
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

        salt <host> vagrant.destroy <salt_id>
    '''

    vm_ = _get_cached_vm(name)
    machine = vm_['machine']

    cmd = _runas_sudo(vm_, 'vagrant destroy -f {}'.format(machine))
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
        [cmd],
        shell=True,
        cwd=vm_.get('cwd', None)
        )
    _erase_cache(name)
    return ret
