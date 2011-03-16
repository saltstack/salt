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

    CLI Example:
    salt '*' libvirt.list_vms
    '''
    conn = __get_con()
    vms = []
    names = conn.listDefinedDomains()
        for name in names:
            vms.append(name)
    return vms

def vm_info():
    '''
    Return detailed information about the vms on this hyper in a dict:

    {'cpu': <int>,
     'maxMem': <int>,
     'mem': <int>,
     'state': '<state>',
     'cputime' <int>}

    CLI Example:
    salt '*' libvirt.vm_info
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

def node_info():
    '''
    Return a dict with information about this node
    '''
    conn = __get_conn()
    info = {}
    raw = conn.getInfo()
    info = {
            'cpumodel'     : str(raw[0]),
            'phymemory'    : raw[1],
            'cpus'         : raw[2],
            'cpumhz'       : raw[3],
            'numanodes'    : raw[4],
            'sockets'      : raw[5],
            'cpucores'     : raw[6],
            'cputhreads'   : raw[7]
            }
    return info

def freemem():
    '''
    Return an int representing the amount of memory that has not been given
    to virtual machines on this node

    CLI Example:
    salt '*' libvirt.freemem
    '''
    conn = __get_conn()
    mem = conn.getInfo()[1]
    # Take off just enough to sustain the hypervisor
    mem -= 256
    for vm in list_vms():
        dom = conn.lookupByName(vm)
        if dom.ID() > 0:
            mem -= vm.info()[2]/1024
    return mem

def shutdown(self, vm):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:
    salt '*' libvirt.shutdown <vm name>
    '''
    conn = __get_conn()
    conn.shutdown(vm)
    return True

def pause(self, vm):
    '''
    Pause the named vm

    CLI Example:
    salt '*' libvirt.pause <vm name>
    '''
    conn = __get_conn()
    conn.suspend(vm)
    return True

def unpause(self, vm):
    '''
    Unpause the named vm

    CLI Example:
    salt '*' libvirt.unpause <vm name>
    '''
    conn = __get_conn()
    conn.resume(vm)
    return True

def create(self, vm):
    '''
    Start a defined domain

    CLI Example:
    salt '*' libvirt.create <vm name>
    '''
    conn = __get_conn()
    conn.create(vm)
    return True
# Crate more "create" functions to wrap the libvirt api better

def destroy(self, vm):
    '''
    Hard power down the virtual machine, this is equivelent to pulling the
    power

    CLI Example:
    salt '*' libvirt.destroy <vm name>
    '''
    conn = __get_conn()
    conn.destroy(vm)
    return True

