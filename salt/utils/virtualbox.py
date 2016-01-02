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
        "OSTypeId",
    ]
}


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


def vb_start_vm(**kwargs):
    """
    Tells Virtualbox to start up a VM.
    Blocking function!

    @return dict of started VM, contains IP addresses and what not
    """
    pass


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

    @param xpcom:
    @type xpcom:
    @param interface_name: Which interface we will be converting from.
                           Without this it's best to specify the list of attributes you want
    @type interface_name: str
    @param attributes: Overrides the attributes used from XPCOM_ATTRIBUTES
    @type attributes: list
    @param excluded_attributes: Which should be excluded in the returned dict.
                                !!These take precedence over extra_attributes!!
    @type excluded_attributes: list
    @param extra_attributes: Which should be retrieved in addition those already being retrieved
    @type extra_attributes: list
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

    attribute_tuples = [
        (attribute, getattr(xpcom, attribute, ""))
        for attribute in interface_attributes
        ]

    return dict(attribute_tuples)


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
