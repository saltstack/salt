# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide
from vboxapi import VirtualBoxManager
import logging
import time

# This code initializes VirtualBox manager with default style
# and parameters
virtualBoxManager = VirtualBoxManager(None, None)
vbox = virtualBoxManager.vbox

log = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.DEBUG)
log.addHandler(log_handler)
log.setLevel(logging.DEBUG)
info = log.info

def list_machines():

    for machine in virtualBoxManager.getArray(vbox, "Machines"):

        print "Machine '%s' logs in '%s'" %(machine.name, machine.logFolder)

def create_machine(name, from_machine_name=None, groups=None, osTypeId="Other"):
    info("Create machine %s" % name)
    new_machine = vbox.createMachine(
        None # Settings file
        ,name
        ,groups
        ,osTypeId
        ,None # flags
    )
    if(from_machine_name):
        info("Cloning from %s" % from_machine_name)
        clone_machine(from_machine_name, new_machine)

    vbox.registerMachine(new_machine)

def clone_machine(source_machine_name, new_machine, timeout=10000):
    """

    @param timeout int timeout in milliseconds
    """
    machine = vbox.findMachine(source_machine_name)

    progress = machine.cloneTo(
        new_machine
        , 0 # CloneMode
        , None # CloneOptions : None = Full?
    )

    progress.waitForCompletion(timeout)
    info("Finished for clone of %s" % source_machine_name)

def destroy_machine(name, timeout=10000):
    """

    @param timeout int timeout in milliseconds
    """
    info("Destroying machine %s" % name)
    machine = vbox.findMachine(name)
    files = machine.unregister(2)
    progress = machine.deleteConfig(files)
    progress.waitForCompletion(timeout)
    info("Finished destroying machine %s" % name)

def start_machine(name):
    vb = virtualBoxManager.getVirtualBox()
    pass


def test_create_machine():
    create_machine(
        "ToDestroy"
    )

def test_create_machine_from_clone():
    create_machine("ToDestroy2", from_machine_name="ToDestroy")


if __name__ == '__main__':
    test_create_machine()
    time.sleep(1)
    test_create_machine_from_clone()
    time.sleep(1)
    destroy_machine("ToDestroy")
    time.sleep(1)
    destroy_machine("ToDestroy2")
