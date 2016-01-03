"""
Utilities to help make requests to virtualbox


This code assumes vboxapi.py from VirtualBox distribution
being in PYTHONPATH, or installed system-wide
"""

# Import python libs
import logging
import re

log = logging.getLogger(__name__)

# Import virtualbox libs
HAS_LIBS = False
try:
    from vboxapi import VirtualBoxManager

    HAS_LIBS = True

except ImportError:
    VirtualBoxManager = None
    log.error("Couldn't import VirtualBox API")

_virtualboxManager = None

"""
Attributes we expect to have when converting an XPCOM object to a dict
"""
XPCOM_ATTRIBUTES = {
    "IMachine": [
        "id",
        "name",
        "accessible",
        "description",
        "groups",
        "memorySize",
        "OSTypeId",
        "state",
    ]
}

"""
Dict of states {
    <number>: ( <name>, <description> )
}
"""
MACHINE_STATES = dict(enumerate([
    ("Null", "Null value (never used by the API)"),
    ("PoweredOff", "The machine is not running and has no saved execution state; "
                   "it has either never been started or been shut down successfully."),
    ("Saved", "The machine is not currently running, but the execution state of the machine has been "
              "saved to an external file when it was running, from where it can be resumed."),
    ("Teleported", "The machine was teleported to a different host (or process) and then powered off. "
                   "Take care when powering it on again may corrupt resources it shares with the teleportation "
                   "target (e.g. disk and network)."),
    ("Aborted", "The process running the machine has terminated abnormally. This may indicate a "
                "crash of the VM process in host execution context, or the VM process has been terminated "
                "externally."),
    ("Running", "The machine is currently being executed."),
    ("Paused", "Execution of the machine has been paused."),
    ("Stuck", "Execution of the machine has reached the \"Guru Meditation\" condition. This indicates a "
              "severe error in the hypervisor itself."),
    ("Teleporting", "The machine is about to be teleported to a different host or process. It is possible "
                    "to pause a machine in this state, but it will go to the TeleportingPausedVM state and it "
                    "will not be possible to resume it again unless the teleportation fails."),
    ("LiveSnapshotting", "A live snapshot is being taken. The machine is running normally, but some "
                         "of the runtime configuration options are inaccessible. "
                         "Also, if paused while in this state it will transition to OnlineSnapshotting "
                         "and it will not be resume the execution until the snapshot operation has completed."),
    ("Starting", "Machine is being started after powering it on from a zero execution state."),
    ("Stopping", "Machine is being normally stopped powering it off, or after the guest OS has initiated "
                 "a shutdown sequence."),
    ("Saving", "Machine is saving its execution state to a file."),
    ("Restoring", "Execution state of the machine is being restored from a file after powering it on from "
                  "the saved execution state."),
    ("TeleportingPausedVM", "The machine is being teleported to another host or process, but it is not "
                            "running. This is the paused variant of the Teleporting state."),
    ("TeleportingIn", "Teleporting the machine state in from another host or process."),
    ("FaultTolerantSyncing", "The machine is being synced with a fault tolerant VM running else-where."),
    ("DeletingSnapshotOnline", "Like DeletingSnapshot , but the merging of media is ongoing in the "
                               "background while the machine is running."),
    ("DeletingSnapshotPaused", "Like DeletingSnapshotOnline , but the machine was paused when "
                               "the merging of differencing media was started."),
    ("OnlineSnapshotting", "Like LiveSnapshotting , but the machine was paused when the merging "
                           "of differencing media was started."),
    ("RestoringSnapshot", "A machine snapshot is being restored; this typically does not take long."),
    ("DeletingSnapshot", "A machine snapshot is being deleted; this can take a long time since this may "
                         "require merging differencing media. This value indicates that the machine is not running "
                         "while the snapshot is being deleted."),
    ("SettingUp", "Lengthy setup operation is in progress."),
    ("Snapshotting", "Taking an (offline) snapshot."),
    ("FirstOnline", "Pseudo-state: first online state (for use in relational expressions)."),
    ("LastOnline", "Pseudo-state: last online state (for use in relational expressions)."),
    ("FirstTransient", "Pseudo-state: first transient state (for use in relational expressions)."),
    ("LastTransient", "Pseudo-state: last transient state (for use in relational expressions)."),
]))


def vb_get_manager():
    # This code initializes VirtualBox manager with default style
    # and parameters
    global _virtualboxManager
    if _virtualboxManager is None:
        _virtualboxManager = VirtualBoxManager(None, None)

    return _virtualboxManager


def vb_get_box():
    vb_get_manager()
    vbox = _virtualboxManager.vbox
    return vbox


def vb_list_machines(**kwargs):
    manager = vb_get_manager()
    machines = manager.getArray(vb_get_box(), "machines")
    return [
        vb_xpcom_to_attribute_dict(machine, "IMachine", **kwargs)
        for machine in machines
        ]


def vb_create_machine(name=None):
    vbox = vb_get_box()
    log.info("Create virtualbox machine %s " % (name,))
    groups = None
    os_type_id = "Other"
    new_machine = vbox.createMachine(
        None,  # Settings file
        name,
        groups,
        os_type_id,
        None  # flags
    )
    vbox.registerMachine(new_machine)
    log.info("Finished creating %s" % name)


def vb_clone_vm(
    name=None,
    clone_from=None,
    timeout=10000,
    **kwargs
):
    """
    Tells virtualbox to create a VM

    @return dict of resulting VM
    """
    vbox = vb_get_box()
    log.info("Clone virtualbox machine %s from %s" % (name, clone_from))

    source_machine = vbox.findMachine(clone_from)

    groups = None
    osTypeId = "Other"
    new_machine = vbox.createMachine(
        None,  # Settings file
        name,
        groups,
        osTypeId,
        None  # flags
    )

    progress = source_machine.cloneTo(
        new_machine,
        0,  # CloneMode
        None  # CloneOptions : None = Full?
    )

    progress.waitForCompletion(timeout)
    log.info("Finished cloning %s from %s" % (name, clone_from))

    vbox.registerMachine(new_machine)

    return vb_xpcom_to_attribute_dict(new_machine, "IMachine")


def vb_start_vm(name=None, timeout=10000, **kwargs):
    """
    Tells Virtualbox to start up a VM.
    Blocking function!

    @return dict of started VM, contains IP addresses and what not
    """
    # TODO handle errors
    vbox = vb_get_box()
    log.info("Starting machine %s" % name)
    machine = vbox.findMachine(name)

    session = _virtualboxManager.getSessionObject(vbox)
    progress = machine.launchVMProcess(session, "", "")

    progress.waitForCompletion(timeout)
    log.info("Started machine %s" % name)

    _virtualboxManager.closeMachineSession(session)

    return vb_xpcom_to_attribute_dict(machine, "IMachine")


def vb_stop_vm(name=None, timeout=10000, **kwargs):
    # TODO handle errors
    vbox = vb_get_box()
    machine = vbox.findMachine(name)
    log.info("Stopping machine %s" % name)
    session = _virtualboxManager.openMachineSession(machine)
    console = session.console
    progress = console.powerDown()
    progress.waitForCompletion(timeout)
    _virtualboxManager.closeMachineSession(session)
    log.info("Stopped machine %s" % name)
    return vb_xpcom_to_attribute_dict(machine, "IMachine")


def vb_destroy_machine(name=None, timeout=10000):
    """

    @param timeout int timeout in milliseconds
    """
    vbox = vb_get_box()
    log.info("Destroying machine %s" % name)
    machine = vbox.findMachine(name)
    files = machine.unregister(2)
    progress = machine.deleteConfig(files)
    progress.waitForCompletion(timeout)
    log.info("Finished destroying machine %s" % name)


def vb_xpcom_to_attribute_dict(xpcom
                               , interface_name=None
                               , attributes=None
                               , excluded_attributes=None
                               , extra_attributes=None
                               ):
    """
    Attempts to build a dict from an XPCOM object.
    Attributes that don't exist in the object return an empty string.

    attribute_list = list of str or tuple(str,<a class>)

    e.g attributes=[("bad_attribute", list)] --> { "bad_attribute": [] }

    @param xpcom:
    @type xpcom:
    @param interface_name: Which interface we will be converting from.
                           Without this it's best to specify the list of attributes you want
    @type interface_name: str
    @param attributes: Overrides the attributes used from XPCOM_ATTRIBUTES
    @type attributes: attribute_list
    @param excluded_attributes: Which should be excluded in the returned dict.
                                !!These take precedence over extra_attributes!!
    @type excluded_attributes: attribute_list
    @param extra_attributes: Which should be retrieved in addition those already being retrieved
    @type extra_attributes: attribute_list
    @return:
    @rtype: dict
    """
    # Check the interface
    if interface_name:
        m = re.search(r"XPCOM.+implementing %s" % interface_name, str(xpcom))
        if not m:
            # TODO maybe raise error here?
            log.warn("Interface %s is unknown and cannot be converted to dict" % interface_name)
            return dict()

    interface_attributes = set(attributes or XPCOM_ATTRIBUTES.get(interface_name, []))
    if extra_attributes:
        interface_attributes = interface_attributes.union(extra_attributes)
    if excluded_attributes:
        interface_attributes = interface_attributes.difference(excluded_attributes)

    attribute_tuples = []
    for attribute in interface_attributes:
        if isinstance(attribute, tuple):
            attribute_name = attribute[0]
            attribute_class = attribute[1]
            value = (attribute_name, getattr(xpcom, attribute_name, attribute_class()))
        else:
            value = (attribute, getattr(xpcom, attribute, ""))
        attribute_tuples.append(value)

    return dict(attribute_tuples)


def vb_machinestate_to_str(machinestate):
    """

    @param machinestate: from the machine state enum from XPCOM
    @type machinestate: int
    @return:
    @rtype:
    """

    return MACHINE_STATES.get(machinestate, ("Unknown", "This state is unknown to us. Might be new?"))


def machine_get_machinestate(machinedict):
    return vb_machinestate_to_str(machinedict.get("state"))


def vb_machine_exists(name):
    try:
        vbox = vb_get_box()
        vbox.findMachine(name)
        return True
    except Exception as e:
        if isinstance(e.message, str):
            message = e.message
        elif isinstance(e.msg, str):
            message = e.msg
        else:
            message = ""
        if 0 > message.find("Could not find a registered machine named"):
            log.error(message)

        return False
