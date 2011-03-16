'''
Work with vitual machines managed by libvirt
'''
# Import Python Libs
import os
import sub_process
import libvirt
import subprocess
import StringIO
from xml.dom import minidom

# Import libvirt
import libvirt

VIRT_STATE_NAME_MAP = {
   0 : "running",
   1 : "running",
   2 : "running",
   3 : "paused",
   4 : "shutdown",
   5 : "shutdown",
   6 : "crashed"
}

def __get_conn():
    '''
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.
    '''
    # This only supports kvm right now, it needs to be expanded to support
    # all vm layers supported by libvirt
    return libvirt.open("qemu:///system")

def list_vms():
    '''
    Return a list of virtual machine names on the minion
    '''
    conn = __get_con()
    vms = []
    names = conn.listDefinedDomains()
        for name in names:
            vm = conn.lookupByName(name)
            vms.append(vm)
    return vms

def _info():
    '''
    Return detailed information about the vms on this hyper in a dict:
    [{'cpus': <int>,
     'MaxMem': <int>,
     'Mem': <int>,
     'state': '<state>',}, ...]
    '''
    info = {}
    conn = __get_conn()
    for vm in list_vms():
        raw = vm.info()



