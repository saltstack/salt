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
import salt.ext.six as six
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress

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
        vm_ = {}
        log.error('Trouble reading Salt cache for vagrant[%s]', name)
    try:
        _ = vm_['machine']
    except KeyError:
        raise ValueError, 'No Vagrant machine defined for Salt-id {}'.format(name)
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


def _vagrant_ssh_config(vm_):
    '''
    get the information for ssh communication from the new VM
    :param vm_: the VM's info as we have it now
    :return: dictionary of ssh stuff
    '''
    machine = vm_['machine']
    ret = {}
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
    return ssh_config


def version():
    '''
    Return the version of Vagrant on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.version
    '''
    cmd = 'vagrant -v'
    try:
        output = subprocess.check_output([cmd], shell=True)
    except subprocess.CalledProcessError:
        return 'Error: subprocess error calling ' + cmd
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


def start(name, vm_={}):
    '''
    Start (vagrant up) a defined virtual machine by salt_id name.
    The machine must have been previously defined using "vagrant.init".

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.start <salt_id>
    '''
    return _start(name, vm_)


def _start(name, vm_, opts=None):  # internal call name, because "start" is a keyword argument to vagrant.init
    fudged_opts = defaultdict(lambda: None)
    if opts is None:
        fudged_opts.update(__opts__)
        fudged_opts.update(_get_cached_opts(name))
        fudged_opts.setdefault('profiles', defaultdict(lambda: ''))
        fudged_opts.setdefault('providers', {})
        fudged_opts.setdefault('deploy_scripts_search_path', vm_.get('deploy_scripts_search_path', []))

    if not vm_:
        vm_ = _get_cached_vm(name)

    try:
        machine = vm_['machine']
    except KeyError:
        raise ValueError, 'No Vagrant machine defined for Salt-id {}'.format(name)

    vagrant_provider = vm_.get('vagrant_provider', '')
    provider_ = '--provider={}'.format(vagrant_provider) if vagrant_provider else ''
    cmd = _runas_sudo(vm_, 'vagrant up {} {}'.format(machine, provider_))
    log.info('Executing command "%s"', cmd)
    ret = subprocess.call(
            [cmd],
            shell=True,
            cwd=vm_.get('cwd', None)
            )

    return ret == 0



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
    return ret == 0


def get_ssh_config(name, network_mask='', get_private_key=False):
    '''
    Retrieve hints of how you might connect to a Vagrant VM.

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.get_ssh_config <salt_id>
        salt my_laptop vagrant.get_ssh_config quail1 network_mask=10.0.0.0/8 get_private_key=True

    returns a dictionary containing:

    - key_filename:  the name of the private key file on the VM host computer
    - ssh_username:  the username to be used to log in to the VM
    - ssh_host:  the IP address used to log in to the VM.  (This will usually be `127.0.0.1`)
    - ssh_port:  the TCP port used to log in to the VM.  (This will often be `2222`)
    - \[ip_address:\]  (if `network_mask` is defined. see below)
    - \[private_key:\]  (if `get_private_key` is True) the private key for ssh_username

    About `network_mask`:

    Vagrant usually uses a redirected TCP port on its host computer to log in to a VM using ssh.
    This makes it impossible for a third machine (such as a salt-cloud master) to contact the VM
    unless the VM has another network interface defined.  You will usually want a bridged network
    defined by having a `config.vm.network "public_network"` statement in your `Vagrantfile`.

    The IP address of the bridged adapter will typically be assigned by DHCP and unknown to you,
    but you should be able to determine what IP network the address will be chosen from.
    If you enter a CIDR network mask, the module will attempt to find the VM's address for you.
    It will send an `ifconfig` command to the VM (using ssh to `ssh_host`:`ssh_port`) and scan the
    result, returning the IP address of the first interface it can find which matches your mask.
    '''
    vm_ = _get_cached_vm(name)

    ssh_config = _vagrant_ssh_config(vm_)

    ans = { 'key_filename': ssh_config['IdentityFile'],
            'ssh_username': ssh_config['User'],
            'ssh_host': ssh_config['HostName'],
            'ssh_port': ssh_config['Port'],
            }

    if network_mask:
        #  ask the new VM to report its network address
        command = 'ssh -i {IdentityFile} -p {Port} ' \
                  '-oStrictHostKeyChecking={StrictHostKeyChecking} ' \
                  '-oUserKnownHostsFile={UserKnownHostsFile} ' \
                  '-oControlPath=none ' \
                  '{User}@{HostName} ifconfig'.format(**ssh_config)

        log.info('Trying ssh -p {Port} {User}@{HostName} ifconfig'.format(**ssh_config))
        try:
            ret = subprocess.check_output([command], shell=True)
        except subprocess.CalledProcessError as e:
            raise CommandExecutionError, 'Error trying ssh to %s: %s'.format(name, e)
        reply = salt.utils.stringutils.to_str(ret)
        log.info(reply)

        ## TODO: move this code to salt-cloud driver
        ## target_network = config.get_cloud_config_value(
        ##    'target_network', vm_, __opts__, default=None)
        target_network_range = ipaddress.ip_network(network_mask, strict=False)

        for line in reply.split('\n'):
            try:   # try to find a bridged network address
                # the lines we are looking for appear like:
                #    "inet addr:10.124.31.185  Bcast:10.124.31.255  Mask:255.255.248.0"
                # or "inet6 addr: fe80::a00:27ff:fe04:7aac/64 Scope:Link"
                tokens = line.replace('addr:','',1).split()  # remove "addr:" if it exists, then split
                found_address = None
                if "inet" in tokens:
                    nxt = tokens.index("inet") + 1
                    found_address = ipaddress.ip_address(tokens[nxt])
                elif "inet6" in tokens:
                    nxt = tokens.index("inet6") + 1
                    found_address = ipaddress.ip_address(tokens[nxt].split('/')[0])
                if found_address in target_network_range:
                    ans['ip_address'] = str(found_address)
                    break  # we have located a good matching address
            except (IndexError, AttributeError, TypeError):
                pass  # all syntax and type errors loop here
            # falling out if the loop leaves us remembering the last candidate
        log.info('Network IP address in %s detected as: %s',
                 target_network_range, ans.get('ip_address', '(not found)'))

    if get_private_key:
        # retrieve the Vagrant private key from the host
        try:
            with open(ssh_config['IdentityFile']) as pks:
                ans['private_key'] = pks.read()
        except (OSError, IOError) as e:
            raise CommandExecutionError, "Error processing Vagrant private key file: {}".format(e)
    return ans
