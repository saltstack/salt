'''
Work with vitual machines managed by libvirt
'''
# Special Thanks to Michael Dehann, many of the concepts, and a few structures
# of his in the virt func module have been used


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
            vms.append(name)
    return vms

def info():
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
        dom = dom = conn.lookupByName(vm)
        raw = dom.info()
        info[vm] = {
                'state': VIRT_STATE_NAME_MAP.get(raw[0], 'unknown'),
                'maxMem': int(raw[1]),
                'mem': int(raw[2]),
                'cpu': raw[3],
                'cputime': int(data[4]),
                }
    return info



