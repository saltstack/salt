r"""
Manage Vagrant VMs
==================

Manange execution of Vagrant virtual machines on Salt minions.

Vagrant_ is a tool for building and managing virtual machine environments.
It can use various providers, such as VirtualBox_, Docker_, or VMware_, to run its VMs.
Vagrant provides some of the functionality of a light-weight hypervisor.
The combination of Salt modules, Vagrant running on the host, and a
virtual machine provider, gives hypervisor-like functionality for
developers who use Vagrant to quickly define their virtual environments.

.. _Vagrant: http://www.vagrantup.com/
.. _VirtualBox: https://www.virtualbox.org/
.. _Docker: https://www.docker.io/
.. _VMWare: https://www.vmware.com/

    .. versionadded:: 2018.3.0

The configuration of each virtual machine is defined in a file named
``Vagrantfile`` which must exist on the VM host machine.
The essential parameters which must be defined to start a Vagrant VM
are the directory where the ``Vagrantfile`` is located \(argument ``cwd:``\),
and the username which will own the ``Vagrant box`` created for the VM \(
argument ``vagrant_runas:``\).

A single ``Vagrantfile`` may define one or more virtual machines.
Use the ``machine`` argument to chose among them. The default (blank)
value will select the ``primary`` (or only) machine in the Vagrantfile.

\[NOTE:\] Each virtual machine host must have the following:

- a working salt-minion
- a Salt sdb database configured for ``vagrant_sdb_data``.
- Vagrant installed and the ``vagrant`` command working
- a suitable VM provider

.. code-block:: yaml

    # EXAMPLE:
    # file /etc/salt/minion.d/vagrant_sdb.conf on the host computer
    #  -- this sdb database is required by the Vagrant module --
    vagrant_sdb_data:  # The sdb database must have this name.
      driver: sqlite3  # Let's use SQLite to store the data ...
      database: /var/cache/salt/vagrant.sqlite  # ... in this file ...
      table: sdb  # ... using this table name.
      create_table: True  # if not present

"""

import fnmatch

import salt.utils.args
from salt.exceptions import CommandExecutionError, SaltInvocationError

__virtualname__ = "vagrant"


def __virtual__():
    """
    Only if vagrant module is available.

    :return:
    """
    if "vagrant.version" in __salt__:
        return __virtualname__
    return (False, "vagrant module could not be loaded")


def _vagrant_call(node, function, section, comment, status_when_done=None, **kwargs):
    """
    Helper to call the vagrant functions. Wildcards supported.

    :param node: The Salt-id or wildcard
    :param function: the vagrant submodule to call
    :param section: the name for the state call.
    :param comment: what the state reply should say
    :param status_when_done: the Vagrant status expected for this state
    :return:  the dictionary for the state reply
    """
    ret = {"name": node, "changes": {}, "result": True, "comment": ""}

    targeted_nodes = []
    if isinstance(node, str):
        try:  # use shortcut if a single node name
            if __salt__["vagrant.get_vm_info"](node):
                targeted_nodes = [node]
        except SaltInvocationError:
            pass

    if not targeted_nodes:  # the shortcut failed, do this the hard way
        all_domains = __salt__["vagrant.list_domains"]()
        targeted_nodes = fnmatch.filter(all_domains, node)
    changed_nodes = []
    ignored_nodes = []
    for node in targeted_nodes:
        if status_when_done:
            try:
                present_state = __salt__["vagrant.vm_state"](node)[0]
                if present_state["state"] == status_when_done:
                    continue  # no change is needed
            except (IndexError, SaltInvocationError, CommandExecutionError):
                pass
        try:
            response = __salt__["vagrant.{}".format(function)](node, **kwargs)
            if isinstance(response, dict):
                response = response["name"]
            changed_nodes.append({"node": node, function: response})
        except (SaltInvocationError, CommandExecutionError) as err:
            ignored_nodes.append({"node": node, "issue": str(err)})
    if not changed_nodes:
        ret["result"] = True
        ret["comment"] = "No changes seen"
        if ignored_nodes:
            ret["changes"] = {"ignored": ignored_nodes}
    else:
        ret["changes"] = {section: changed_nodes}
        ret["comment"] = comment

    return ret


def running(name, **kwargs):
    r"""
    Defines and starts a new VM with specified arguments, or restart a
    VM (or group of VMs). (Runs ``vagrant up``.)

    :param name: the Salt_id node name you wish your VM to have.

    If ``name`` contains a "?" or "*"  then it will re-start a group of VMs
    which have been paused or stopped.

    Each machine must be initially started individually using this function
    or the vagrant.init execution module call.

    \[NOTE:\] Keyword arguments are silently ignored when re-starting an existing VM.

    Possible keyword arguments:

    - cwd: The directory (path) containing the Vagrantfile
    - machine: ('') the name of the machine (in the Vagrantfile) if not default
    - vagrant_runas: ('root') the username who owns the vagrantbox file
    - vagrant_provider: the provider to run the VM (usually 'virtualbox')
    - vm: ({}) a dictionary containing these or other keyword arguments

    .. code-block:: yaml

        node_name:
          vagrant.running

    .. code-block:: yaml

        node_name:
          vagrant.running:
            - cwd: /projects/my_project
            - vagrant_runas: my_username
            - machine: machine1

    """
    if "*" in name or "?" in name:

        return _vagrant_call(
            name, "start", "restarted", "Machine has been restarted", "running"
        )

    else:

        ret = {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "{} is already running".format(name),
        }

        try:
            info = __salt__["vagrant.vm_state"](name)
            if info[0]["state"] != "running":
                __salt__["vagrant.start"](name)
                ret["changes"][name] = "Machine started"
                ret["comment"] = "Node {} started".format(name)
        except (SaltInvocationError, CommandExecutionError):
            #  there was no viable existing machine to start
            ret, kwargs = _find_init_change(name, ret, **kwargs)
            kwargs["start"] = True
            __salt__["vagrant.init"](name, **kwargs)
            ret["changes"][name] = "Node defined and started"
            ret["comment"] = "Node {} defined and started".format(name)

        return ret


def _find_init_change(name, ret, **kwargs):
    """
    look for changes from any previous init of machine.

    :return: modified ret and kwargs
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    if "vm" in kwargs:
        kwargs.update(kwargs.pop("vm"))
    # the state processing eats 'runas' so we rename
    kwargs["runas"] = kwargs.pop("vagrant_runas", "")
    try:
        vm_ = __salt__["vagrant.get_vm_info"](name)
    except SaltInvocationError:
        vm_ = {}
        for key, value in kwargs.items():
            ret["changes"][key] = {"old": None, "new": value}
    if vm_:  # test for changed values
        for key in vm_:
            value = vm_[key] or ""  # supply a blank if value is None
            if key != "name":  # will be missing in kwargs
                new = kwargs.get(key, "")
                if new != value:
                    if key == "machine" and new == "":
                        continue  # we don't know the default machine name
                    ret["changes"][key] = {"old": value, "new": new}
    return ret, kwargs


def initialized(name, **kwargs):
    r"""
    Defines a new VM with specified arguments, but does not start it.

    :param name: the Salt_id node name you wish your VM to have.

    Each machine must be initialized individually using this function
    or the "vagrant.running" function, or the vagrant.init execution module call.

    This command will not change the state of a running or paused machine.

    Possible keyword arguments:

    - cwd: The directory (path) containing the Vagrantfile
    - machine: ('') the name of the machine (in the Vagrantfile) if not default
    - vagrant_runas: ('root') the username who owns the vagrantbox file
    - vagrant_provider: the provider to run the VM (usually 'virtualbox')
    - vm: ({}) a dictionary containing these or other keyword arguments

    .. code-block:: yaml

        node_name1:
          vagrant.initialized
            - cwd: /projects/my_project
            - vagrant_runas: my_username
            - machine: machine1

        node_name2:
          vagrant.initialized
            - cwd: /projects/my_project
            - vagrant_runas: my_username
            - machine: machine2

        start_nodes:
          vagrant.start:
            - name: node_name?
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "The VM is already correctly defined",
    }

    # define a machine to start later
    ret, kwargs = _find_init_change(name, ret, **kwargs)

    if ret["changes"] == {}:
        return ret

    kwargs["start"] = False
    __salt__["vagrant.init"](name, **kwargs)
    ret["changes"][name] = "Node initialized"
    ret["comment"] = "Node {} defined but not started.".format(name)

    return ret


def stopped(name):
    """
    Stops a VM (or VMs) by shutting it (them) down nicely. (Runs ``vagrant halt``)

    :param name: May be a Salt_id node, or a POSIX-style wildcard string.

    .. code-block:: yaml

        node_name:
          vagrant.stopped
    """

    return _vagrant_call(
        name, "shutdown", "stopped", "Machine has been shut down", "poweroff"
    )


def powered_off(name):
    """
    Stops a VM (or VMs) by power off.  (Runs ``vagrant halt``.)

    This method is provided for compatibility with other VM-control
    state modules. For Vagrant, the action is identical with ``stopped``.

    :param name: May be a Salt_id node or a POSIX-style wildcard string.

    .. code-block:: yaml

        node_name:
          vagrant.unpowered
    """

    return _vagrant_call(
        name, "stop", "unpowered", "Machine has been powered off", "poweroff"
    )


def destroyed(name):
    """
    Stops a VM (or VMs) and removes all references to it (them). (Runs ``vagrant destroy``.)

    Subsequent re-use of the same machine will requere another operation of ``vagrant.running``
    or a call to the ``vagrant.init`` execution module.

    :param name: May be a Salt_id node or a POSIX-style wildcard string.

    .. code-block:: yaml

        node_name:
          vagrant.destroyed
    """

    return _vagrant_call(name, "destroy", "destroyed", "Machine has been removed")


def paused(name):
    """
    Stores the state of a VM (or VMs) for fast restart. (Runs ``vagrant suspend``.)

    :param name: May be a Salt_id node or a POSIX-style wildcard string.

    .. code-block:: yaml

        node_name:
          vagrant.paused
    """

    return _vagrant_call(name, "pause", "paused", "Machine has been suspended", "saved")


def rebooted(name):
    """
    Reboots a running, paused, or stopped VM (or VMs). (Runs ``vagrant reload``.)

    The  will re-run the provisioning

    :param name: May be a Salt_id node or a POSIX-style wildcard string.

    .. code-block:: yaml

        node_name:
          vagrant.reloaded
    """

    return _vagrant_call(name, "reboot", "rebooted", "Machine has been reloaded")
