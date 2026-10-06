"""
Work with virtual machines managed by Vagrant.

.. versionadded:: 2018.3.0

Mapping between a Salt node id and the Vagrant machine name
(and the path to the Vagrantfile where it is defined)
is stored in a Salt sdb database on the Vagrant host (minion) machine.
In order to use this module, sdb must be configured. An SQLite
database is the recommended storage method.  The URI used for
the sdb lookup is "sdb://vagrant_sdb_data".

requirements:
   - the VM host machine must have salt-minion, Vagrant and a vm provider installed.
   - the VM host must have a valid definition for `sdb://vagrant_sdb_data`

    Configuration example:

    .. code-block:: yaml

        # file /etc/salt/minion.d/vagrant_sdb.conf
        vagrant_sdb_data:
          driver: sqlite3
          database: /var/cache/salt/vagrant.sqlite
          table: sdb
          create_table: True

"""

import logging
import os

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "vagrant"

VAGRANT_SDB_URL = "sdb://vagrant_sdb_data/"


def __virtual__():
    """
    run Vagrant commands if possible
    """
    if salt.utils.path.which("vagrant") is None:
        return (
            False,
            "The vagrant module could not be loaded: vagrant command not found",
        )
    return __virtualname__


def _build_sdb_uri(key):
    """
    returns string used to fetch data for "key" from the sdb store.

    Salt node id's are used as the key for vm_ dicts.

    """
    return f"{VAGRANT_SDB_URL}{key}"


def _build_machine_uri(machine, cwd):
    """
    returns string used to fetch id names from the sdb store.

    the cwd and machine name are concatenated with '?' which should
    never collide with a Salt node id -- which is important since we
    will be storing both in the same table.
    """
    key = f"{machine}?{os.path.abspath(cwd)}"
    return _build_sdb_uri(key)


def _update_vm_info(name, vm_):
    """store the vm_ information keyed by name"""
    __utils__["sdb.sdb_set"](_build_sdb_uri(name), vm_, __opts__)

    # store machine-to-name mapping, too
    if vm_["machine"]:
        __utils__["sdb.sdb_set"](
            _build_machine_uri(vm_["machine"], vm_.get("cwd", ".")), name, __opts__
        )


def get_vm_info(name):
    """
    get the information for a VM.

    :param name: salt_id name
    :return: dictionary of {'machine': x, 'cwd': y, ...}.
    """
    try:
        vm_ = __utils__["sdb.sdb_get"](_build_sdb_uri(name), __opts__)
    except KeyError:
        raise SaltInvocationError(
            "Probable sdb driver not found. Check your configuration."
        )
    if vm_ is None or "machine" not in vm_:
        raise SaltInvocationError(f"No Vagrant machine defined for Salt_id {name}")
    return vm_


def get_machine_id(machine, cwd):
    """
    returns the salt_id name of the Vagrant VM

    :param machine: the Vagrant machine name
    :param cwd: the path to Vagrantfile
    :return: salt_id name
    """
    name = __utils__["sdb.sdb_get"](_build_machine_uri(machine, cwd), __opts__)
    return name


def _erase_vm_info(name):
    """
    erase the information for a VM the we are destroying.

    some sdb drivers (such as the SQLite driver we expect to use)
    do not have a `delete` method, so if the delete fails, we have
    to replace the with a blank entry.
    """
    try:
        # delete the machine record
        vm_ = get_vm_info(name)
        if vm_["machine"]:
            key = _build_machine_uri(vm_["machine"], vm_.get("cwd", "."))
            try:
                __utils__["sdb.sdb_delete"](key, __opts__)
            except KeyError:
                # no delete method found -- load a blank value
                __utils__["sdb.sdb_set"](key, None, __opts__)
    except Exception:  # pylint: disable=broad-except
        pass

    uri = _build_sdb_uri(name)
    try:
        # delete the name record
        __utils__["sdb.sdb_delete"](uri, __opts__)
    except KeyError:
        # no delete method found -- load an empty dictionary
        __utils__["sdb.sdb_set"](uri, {}, __opts__)
    except Exception:  # pylint: disable=broad-except
        pass


def _vagrant_ssh_config(vm_):
    """
    get the information for ssh communication from the new VM

    :param vm_: the VM's info as we have it now
    :return: dictionary of ssh stuff
    """
    machine = vm_["machine"]
    log.info("requesting vagrant ssh-config for VM %s", machine or "(default)")
    cmd = f"vagrant ssh-config {machine}"
    reply = __salt__["cmd.shell"](
        cmd, runas=vm_.get("runas"), cwd=vm_.get("cwd"), ignore_retcode=True
    )
    ssh_config = {}
    for line in reply.split("\n"):  # build a dictionary of the text reply
        tokens = line.strip().split()
        if len(tokens) == 2:  # each two-token line becomes a key:value pair
            ssh_config[tokens[0]] = tokens[1]
    log.debug("ssh_config=%s", repr(ssh_config))
    return ssh_config


def version():
    """
    Return the version of Vagrant on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.version
    """
    cmd = "vagrant -v"
    return __salt__["cmd.shell"](cmd)


def list_domains():
    """
    Return a list of the salt_id names of all available Vagrant VMs on
    this host without regard to the path where they are defined.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.list_domains --log-level=info

    The log shows information about all known Vagrant environments
    on this machine. This data is cached and may not be completely
    up-to-date.
    """
    vms = []
    cmd = "vagrant global-status"
    reply = __salt__["cmd.shell"](cmd)
    log.debug("--->\n%s", reply)
    for line in reply.split("\n"):  # build a list of the text reply
        tokens = line.strip().split()
        try:
            _ = int(tokens[0], 16)  # valid id numbers are hexadecimal
        except (ValueError, IndexError):
            continue  # skip lines without valid id numbers
        machine = tokens[1]
        cwd = tokens[-1]
        name = get_machine_id(machine, cwd)
        if name:
            vms.append(name)
    return vms


def list_active_vms(cwd=None):
    """
    Return a list of machine names for active virtual machine on the host,
    which are defined in the Vagrantfile at the indicated path.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.list_active_vms  cwd=/projects/project_1
    """
    vms = []
    cmd = "vagrant status"
    reply = __salt__["cmd.shell"](cmd, cwd=cwd)
    log.info("--->\n%s", reply)
    for line in reply.split("\n"):  # build a list of the text reply
        tokens = line.strip().split()
        if len(tokens) > 1:
            if tokens[1] == "running":
                vms.append(tokens[0])
    return vms


def list_inactive_vms(cwd=None):
    """
    Return a list of machine names for inactive virtual machine on the host,
    which are defined in the Vagrantfile at the indicated path.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms cwd=/projects/project_1
    """
    vms = []
    cmd = "vagrant status"
    reply = __salt__["cmd.shell"](cmd, cwd=cwd)
    log.info("--->\n%s", reply)
    for line in reply.split("\n"):  # build a list of the text reply
        tokens = line.strip().split()
        if len(tokens) > 1 and tokens[-1].endswith(")"):
            if tokens[1] != "running":
                vms.append(tokens[0])
    return vms


def vm_state(name="", cwd=None):
    """
    Return list of information for all the vms indicating their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs defined by
    the Vagrantfile in the `cwd` directory.

    CLI Example:

    .. code-block:: bash

        salt '*' vagrant.vm_state <name>  cwd=/projects/project_1

    returns a list of dictionaries with machine name, state, provider,
    and salt_id name.

    .. code-block:: python

        datum = {'machine': _, # Vagrant machine name,
                 'state': _, # string indicating machine state, like 'running'
                 'provider': _, # the Vagrant VM provider
                 'name': _} # salt_id name

    Known bug: if there are multiple machines in your Vagrantfile, and you request
    the status of the ``primary`` machine, which you defined by leaving the ``machine``
    parameter blank, then you may receive the status of all of them.
    Please specify the actual machine name for each VM if there are more than one.

    """

    if name:
        vm_ = get_vm_info(name)
        machine = vm_["machine"]
        cwd = vm_["cwd"] or cwd  # usually ignore passed-in cwd
    else:
        if not cwd:
            raise SaltInvocationError(
                f"Path to Vagranfile must be defined, but cwd={cwd}"
            )
        machine = ""

    info = []
    cmd = f"vagrant status {machine}"
    reply = __salt__["cmd.shell"](cmd, cwd)
    log.info("--->\n%s", reply)
    for line in reply.split("\n"):  # build a list of the text reply
        tokens = line.strip().split()
        if len(tokens) > 1 and tokens[-1].endswith(")"):
            try:
                datum = {
                    "machine": tokens[0],
                    "state": " ".join(tokens[1:-1]),
                    "provider": tokens[-1].lstrip("(").rstrip(")"),
                    "name": get_machine_id(tokens[0], cwd),
                }
                info.append(datum)
            except IndexError:
                pass
    return info


def init(
    name,  # Salt_id for created VM
    cwd=None,  # path to find Vagrantfile
    machine="",  # name of machine in Vagrantfile
    runas=None,  # username who owns Vagrant box
    start=False,  # start the machine when initialized
    vagrant_provider="",  # vagrant provider (default=virtualbox)
    vm=None,  # a dictionary of VM configuration settings
):
    """
    Initialize a new Vagrant VM.

    This inputs all the information needed to start a Vagrant VM.  These settings are stored in
    a Salt sdb database on the Vagrant host minion and used to start, control, and query the
    guest VMs. The salt_id assigned here is the key field for that database and must be unique.

    :param name: The salt_id name you will use to control this VM
    :param cwd: The path to the directory where the Vagrantfile is located
    :param machine: The machine name in the Vagrantfile. If blank, the primary machine will be used.
    :param runas: The username on the host who owns the Vagrant work files.
    :param start: (default: False) Start the virtual machine now.
    :param vagrant_provider: The name of a Vagrant VM provider (if not the default).
    :param vm: Optionally, all the above information may be supplied in this dictionary.
    :return: A string indicating success, or False.

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.init <salt_id> /path/to/Vagrantfile
        salt my_laptop vagrant.init x1 /projects/bevy_master machine=quail1
    """
    vm_ = {} if vm is None else vm.copy()  # passed configuration data
    vm_["name"] = name
    # passed-in keyword arguments overwrite vm dictionary values
    vm_["cwd"] = cwd or vm_.get("cwd")
    if not vm_["cwd"]:
        raise SaltInvocationError(
            'Path to Vagrantfile must be defined by "cwd" argument'
        )
    vm_["machine"] = machine or vm_.get("machine", machine)
    vm_["runas"] = runas or vm_.get("runas", runas)
    vm_["vagrant_provider"] = vagrant_provider or vm_.get("vagrant_provider", "")
    _update_vm_info(name, vm_)

    if start:
        log.debug("Starting VM %s", name)
        ret = _start(name, vm_)
    else:
        ret = "Name {} defined using VM {}".format(name, vm_["machine"] or "(default)")
    return ret


def start(name):
    """
    Start (vagrant up) a virtual machine defined by salt_id name.
    The machine must have been previously defined using "vagrant.init".

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.start <salt_id>
    """
    vm_ = get_vm_info(name)
    return _start(name, vm_)


def _start(
    name, vm_
):  # internal call name, because "start" is a keyword argument to vagrant.init

    try:
        machine = vm_["machine"]
    except KeyError:
        raise SaltInvocationError(f"No Vagrant machine defined for Salt_id {name}")

    vagrant_provider = vm_.get("vagrant_provider", "")
    provider_ = f"--provider={vagrant_provider}" if vagrant_provider else ""
    cmd = f"vagrant up {machine} {provider_}"
    ret = __salt__["cmd.run_all"](
        cmd, runas=vm_.get("runas"), cwd=vm_.get("cwd"), output_loglevel="info"
    )

    if machine == "":  # we were called using the default machine
        for line in ret["stdout"].split("\n"):  # find its actual Vagrant name
            if line.startswith("==>"):
                machine = line.split()[1].rstrip(":")
                vm_["machine"] = machine
                _update_vm_info(name, vm_)  # and remember the true name
                break

    if ret["retcode"] == 0:
        return f'Started "{name}" using Vagrant machine "{machine}".'
    return False


def shutdown(name):
    """
    Send a soft shutdown (vagrant halt) signal to the named vm.

    This does the same thing as vagrant.stop. Other-VM control
    modules use "stop" and "shutdown" to differentiate between
    hard and soft shutdowns.

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.shutdown <salt_id>
    """
    return stop(name)


def stop(name):
    """
    Hard shutdown the virtual machine. (vagrant halt)

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.stop <salt_id>
    """
    vm_ = get_vm_info(name)
    machine = vm_["machine"]

    cmd = f"vagrant halt {machine}"
    ret = __salt__["cmd.retcode"](cmd, runas=vm_.get("runas"), cwd=vm_.get("cwd"))
    return ret == 0


def pause(name):
    """
    Pause (vagrant suspend) the named VM.

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.pause <salt_id>
    """
    vm_ = get_vm_info(name)
    machine = vm_["machine"]

    cmd = f"vagrant suspend {machine}"
    ret = __salt__["cmd.retcode"](cmd, runas=vm_.get("runas"), cwd=vm_.get("cwd"))
    return ret == 0


def reboot(name, provision=False):
    """
    Reboot a VM. (vagrant reload)

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.reboot <salt_id> provision=True

    :param name: The salt_id name you will use to control this VM
    :param provision: (False) also re-run the Vagrant provisioning scripts.
    """
    vm_ = get_vm_info(name)
    machine = vm_["machine"]
    prov = "--provision" if provision else ""

    cmd = f"vagrant reload {machine} {prov}"
    ret = __salt__["cmd.retcode"](cmd, runas=vm_.get("runas"), cwd=vm_.get("cwd"))
    return ret == 0


def destroy(name):
    """
    Destroy and delete a virtual machine. (vagrant destroy -f)

    This also removes the salt_id name defined by vagrant.init.

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.destroy <salt_id>
    """
    vm_ = get_vm_info(name)
    machine = vm_["machine"]

    cmd = f"vagrant destroy -f {machine}"

    ret = __salt__["cmd.run_all"](
        cmd, runas=vm_.get("runas"), cwd=vm_.get("cwd"), output_loglevel="info"
    )
    if ret["retcode"] == 0:
        _erase_vm_info(name)
        return f"Destroyed VM {name}"
    return False


def get_ssh_config(name, network_mask="", get_private_key=False):
    r"""
    Retrieve hints of how you might connect to a Vagrant VM.

    :param name: the salt_id of the machine
    :param network_mask: a CIDR mask to search for the VM's address
    :param get_private_key: (default: False) return the key used for ssh login
    :return: a dict of ssh login information for the VM

    CLI Example:

    .. code-block:: bash

        salt <host> vagrant.get_ssh_config <salt_id>
        salt my_laptop vagrant.get_ssh_config quail1 network_mask=10.0.0.0/8 get_private_key=True

    The returned dictionary contains:

    - key_filename:  the name of the private key file on the VM host computer
    - ssh_username:  the username to be used to log in to the VM
    - ssh_host:  the IP address used to log in to the VM.  (This will usually be `127.0.0.1`)
    - ssh_port:  the TCP port used to log in to the VM.  (This will often be `2222`)
    - \[ip_address:\]  (if `network_mask` is defined. see below)
    - \[private_key:\]  (if `get_private_key` is True) the private key for ssh_username

    About `network_mask`:

    Vagrant usually uses a redirected TCP port on its host computer to log in to a VM using ssh.
    This redirected port and its IP address are "ssh_port" and "ssh_host".  The ssh_host is
    usually the localhost (127.0.0.1).
    This makes it impossible for a third machine (such as a salt-cloud master) to contact the VM
    unless the VM has another network interface defined.  You will usually want a bridged network
    defined by having a `config.vm.network "public_network"` statement in your `Vagrantfile`.

    The IP address of the bridged adapter will typically be assigned by DHCP and unknown to you,
    but you should be able to determine what IP network the address will be chosen from.
    If you enter a CIDR network mask, Salt will attempt to find the VM's address for you.
    The host machine will send an "ip link show" or "ifconfig" command to the VM
    (using ssh to `ssh_host`:`ssh_port`) and return the IP address of the first interface it
    can find which matches your mask.
    """
    vm_ = get_vm_info(name)

    ssh_config = _vagrant_ssh_config(vm_)

    try:
        ans = {
            "key_filename": ssh_config["IdentityFile"],
            "ssh_username": ssh_config["User"],
            "ssh_host": ssh_config["HostName"],
            "ssh_port": ssh_config["Port"],
        }

    except KeyError:
        raise CommandExecutionError(
            "Insufficient SSH information to contact VM {}. Is it running?".format(
                vm_.get("machine", "(default)")
            )
        )

    if network_mask:
        #  ask the new VM to report its network address
        command = (
            "ssh -i {IdentityFile} -p {Port} "
            "-oStrictHostKeyChecking={StrictHostKeyChecking} "
            "-oUserKnownHostsFile={UserKnownHostsFile} "
            "-oControlPath=none "
            "{User}@{HostName} ip link show".format(**ssh_config)
        )

        log.info(
            "Trying ssh -p %(Port)s %(User)s@%(HostName)s ip link show", ssh_config
        )
        reply = __salt__["cmd.shell"](command)
        log.info("--->\n%s", reply)
        target_network_range = ipaddress.ip_network(network_mask, strict=False)

        found_address = None
        for line in reply.split("\n"):
            try:  # try to find a bridged network address
                # the lines we are looking for appear like:
                # ip addr show
                #    inet 192.168.0.107/24 brd 192.168.0.255 scope global dynamic noprefixroute enx3c18a040229d
                #    inet 10.16.119.90/32 scope global gpd0
                #    inet 127.0.0.1/8 scope host lo
                #    inet 192.168.0.116/24 brd 192.168.0.255 scope global dynamic noprefixroute enp0s3
                #    inet6 fe80::df56:869b:f0d5:f77c/64 scope link noprefixroute
                # ifconfig
                #    "inet addr:10.124.31.185  Bcast:10.124.31.255  Mask:255.255.248.0"
                # or "inet6 addr: fe80::a00:27ff:fe04:7aac/64 Scope:Link"
                tokens = line.replace(
                    "addr:", "", 1
                ).split()  # remove "addr:" if it exists, then split
                if "inet" in tokens:
                    nxt = tokens.index("inet") + 1
                    found_address = ipaddress.ip_address(tokens[nxt])
                elif "inet6" in tokens:
                    nxt = tokens.index("inet6") + 1
                    found_address = ipaddress.ip_address(tokens[nxt].split("/")[0])
                if found_address in target_network_range:
                    ans["ip_address"] = str(found_address)
                    break  # we have located a good matching address
            except (IndexError, AttributeError, TypeError):
                pass  # all syntax and type errors loop here
                # falling out if the loop leaves us remembering the last candidate
        log.info(
            "Network IP address in %s detected as: %s",
            target_network_range,
            ans.get("ip_address", "(not found using ip addr show)"),
        )

        if found_address is None:
            # attempt to get ip address using ifconfig
            command = (
                "ssh -i {IdentityFile} -p {Port} "
                "-oStrictHostKeyChecking={StrictHostKeyChecking} "
                "-oUserKnownHostsFile={UserKnownHostsFile} "
                "-oControlPath=none "
                "{User}@{HostName} ifconfig".format(**ssh_config)
            )

            log.info(
                "Trying ssh -p %(Port)s %(User)s@%(HostName)s ifconfig", ssh_config
            )
            reply = __salt__["cmd.shell"](command)
            log.info("ifconfig returned:\n%s", reply)
            target_network_range = ipaddress.ip_network(network_mask, strict=False)

            for line in reply.split("\n"):
                try:  # try to find a bridged network address
                    # the lines we are looking for appear like:
                    #    "inet addr:10.124.31.185  Bcast:10.124.31.255  Mask:255.255.248.0"
                    # or "inet6 addr: fe80::a00:27ff:fe04:7aac/64 Scope:Link"
                    tokens = line.replace(
                        "addr:", "", 1
                    ).split()  # remove "addr:" if it exists, then split
                    found_address = None
                    if "inet" in tokens:
                        nxt = tokens.index("inet") + 1
                        found_address = ipaddress.ip_address(tokens[nxt])
                    elif "inet6" in tokens:
                        nxt = tokens.index("inet6") + 1
                        found_address = ipaddress.ip_address(tokens[nxt].split("/")[0])
                    if found_address in target_network_range:
                        ans["ip_address"] = str(found_address)
                        break  # we have located a good matching address
                except (IndexError, AttributeError, TypeError):
                    pass  # all syntax and type errors loop here
                    # falling out if the loop leaves us remembering the last candidate
            log.info(
                "Network IP address in %s detected as: %s",
                target_network_range,
                ans.get("ip_address", "(not found using ifconfig)"),
            )

    if get_private_key:
        # retrieve the Vagrant private key from the host
        try:
            with salt.utils.files.fopen(ssh_config["IdentityFile"]) as pks:
                ans["private_key"] = salt.utils.stringutils.to_unicode(pks.read())
        except OSError as e:
            raise CommandExecutionError(
                f"Error processing Vagrant private key file: {e}"
            )
    return ans
