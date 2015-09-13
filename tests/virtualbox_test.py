# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide
from vboxapi import VirtualBoxManager

# This code initializes VirtualBox manager with default style
# and parameters
virtualBoxManager = VirtualBoxManager(None, None)

vbox = virtualBoxManager.vbox

for machine in virtualBoxManager.getArray(vbox, "Machines"):
    print "Machine '%s' logs in '%s'" %(machine.name, machine.logFolder)
