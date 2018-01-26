# -*- coding: utf-8 -*-
'''
This module (mostly) uses the XenAPI to manage Xen virtual machines.

Big fat warning: the XenAPI used in this file is the one bundled with
Xen Source, NOT XenServer nor Xen Cloud Platform. As a matter of fact it
*will* fail under those platforms. From what I've read, little work is needed
to adapt this code to XS/XCP, mostly playing with XenAPI version, but as
XCP is not taking precedence on Xen Source on many platforms, please keep
compatibility in mind.

Useful documentation:

. http://downloads.xen.org/Wiki/XenAPI/xenapi-1.0.6.pdf
. http://docs.vmd.citrix.com/XenServer/6.0.0/1.0/en_gb/api/
. https://github.com/xapi-project/xen-api/tree/master/scripts/examples/python
. http://xenbits.xen.org/gitweb/?p=xen.git;a=tree;f=tools/python/xen/xm;hb=HEAD
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import sys
import contextlib
import os
from salt.ext.six.moves import range
from salt.ext.six.moves import map

try:
    import importlib  # pylint: disable=minimum-python-version
    HAS_IMPORTLIB = True
except ImportError:
    # Python < 2.7 does not have importlib
    HAS_IMPORTLIB = False

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.modules.cmdmod
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'virt'

# This module has only been tested on Debian GNU/Linux and NetBSD, it
# probably needs more path appending for other distributions.
# The path to append is the path to python Xen libraries, where resides
# XenAPI.


def _check_xenapi():
    if __grains__['os'] == 'Debian':
        debian_xen_version = '/usr/lib/xen-common/bin/xen-version'
        if os.path.isfile(debian_xen_version):
            # __salt__ is not available in __virtual__
            xenversion = salt.modules.cmdmod._run_quiet(debian_xen_version)
            xapipath = '/usr/lib/xen-{0}/lib/python'.format(xenversion)
            if os.path.isdir(xapipath):
                sys.path.append(xapipath)

    try:
        if HAS_IMPORTLIB:
            return importlib.import_module('xen.xm.XenAPI')
        return __import__('xen.xm.XenAPI').xm.XenAPI
    except (ImportError, AttributeError):
        return False


def __virtual__():
    if _check_xenapi() is not False:
        return __virtualname__
    return (False, "Module xapi: xenapi check failed")


@contextlib.contextmanager
def _get_xapi_session():
    '''
    Get a session to XenAPI. By default, use the local UNIX socket.
    '''
    _xenapi = _check_xenapi()

    xapi_uri = __salt__['config.option']('xapi.uri')
    xapi_login = __salt__['config.option']('xapi.login')
    xapi_password = __salt__['config.option']('xapi.password')

    if not xapi_uri:
        # xend local UNIX socket
        xapi_uri = 'httpu:///var/run/xend/xen-api.sock'
    if not xapi_login:
        xapi_login = ''
    if not xapi_password:
        xapi_password = ''

    try:
        session = _xenapi.Session(xapi_uri)
        session.xenapi.login_with_password(xapi_login, xapi_password)

        yield session.xenapi
    except Exception:
        raise CommandExecutionError('Failed to connect to XenAPI socket.')
    finally:
        session.xenapi.session.logout()


# Used rectypes (Record types):
#
# host
# host_cpu
# VM
# VIF
# VBD


def _get_xtool():
    '''
    Internal, returns xl or xm command line path
    '''
    for xtool in ['xl', 'xm']:
        path = salt.utils.path.which(xtool)
        if path is not None:
            return path


def _get_all(xapi, rectype):
    '''
    Internal, returns all members of rectype
    '''
    return getattr(xapi, rectype).get_all()


def _get_label_uuid(xapi, rectype, label):
    '''
    Internal, returns label's uuid
    '''
    try:
        return getattr(xapi, rectype).get_by_name_label(label)[0]
    except Exception:
        return False


def _get_record(xapi, rectype, uuid):
    '''
    Internal, returns a full record for uuid
    '''
    return getattr(xapi, rectype).get_record(uuid)


def _get_record_by_label(xapi, rectype, label):
    '''
    Internal, returns a full record for uuid
    '''
    uuid = _get_label_uuid(xapi, rectype, label)
    if uuid is False:
        return False
    return getattr(xapi, rectype).get_record(uuid)


def _get_metrics_record(xapi, rectype, record):
    '''
    Internal, returns metrics record for a rectype
    '''
    metrics_id = record['metrics']
    return getattr(xapi, '{0}_metrics'.format(rectype)).get_record(metrics_id)


def _get_val(record, keys):
    '''
    Internal, get value from record
    '''
    data = record
    for key in keys:
        if key in data:
            data = data[key]
        else:
            return None
    return data


def list_domains():
    '''
    Return a list of virtual machine names on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_domains
    '''
    with _get_xapi_session() as xapi:
        hosts = xapi.VM.get_all()
        ret = []

        for _host in hosts:
            if xapi.VM.get_record(_host)['is_control_domain'] is False:
                ret.append(xapi.VM.get_name_label(_host))

        return ret


def vm_info(vm_=None):
    '''
    Return detailed information about the vms.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_info
    '''
    with _get_xapi_session() as xapi:

        def _info(vm_):
            vm_rec = _get_record_by_label(xapi, 'VM', vm_)
            if vm_rec is False:
                return False
            vm_metrics_rec = _get_metrics_record(xapi, 'VM', vm_rec)

            return {'cpu': vm_metrics_rec['VCPUs_number'],
                    'maxCPU': _get_val(vm_rec, ['VCPUs_max']),
                    'cputime': vm_metrics_rec['VCPUs_utilisation'],
                    'disks': get_disks(vm_),
                    'nics': get_nics(vm_),
                    'maxMem': int(_get_val(vm_rec, ['memory_dynamic_max'])),
                    'mem': int(vm_metrics_rec['memory_actual']),
                    'state': _get_val(vm_rec, ['power_state'])
                    }
        info = {}
        if vm_:
            ret = _info(vm_)
            if ret is not None:
                info[vm_] = ret
        else:
            for vm_ in list_domains():
                ret = _info(vm_)
                if ret is not None:
                    info[vm_] = _info(vm_)
        return info


def vm_state(vm_=None):
    '''
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_state <vm name>
    '''
    with _get_xapi_session() as xapi:
        info = {}

        if vm_:
            info[vm_] = _get_record_by_label(xapi, 'VM', vm_)['power_state']
            return info

        for vm_ in list_domains():
            info[vm_] = _get_record_by_label(xapi, 'VM', vm_)['power_state']
        return info


def node_info():
    '''
    Return a dict with information about this node

    CLI Example:

    .. code-block:: bash

        salt '*' virt.node_info
    '''
    with _get_xapi_session() as xapi:
        # get node uuid
        host_rec = _get_record(xapi, 'host', _get_all(xapi, 'host')[0])
        # get first CPU (likely to be a core) uuid
        host_cpu_rec = _get_record(xapi, 'host_cpu', host_rec['host_CPUs'][0])
        # get related metrics
        host_metrics_rec = _get_metrics_record(xapi, 'host', host_rec)

        # adapted / cleaned up from Xen's xm
        def getCpuMhz():
            cpu_speeds = [int(host_cpu_rec["speed"])
                          for host_cpu_it in host_cpu_rec
                          if "speed" in host_cpu_it]
            if cpu_speeds:
                return sum(cpu_speeds) / len(cpu_speeds)
            else:
                return 0

        def getCpuFeatures():
            if host_cpu_rec:
                return host_cpu_rec['features']

        def getFreeCpuCount():
            cnt = 0
            for host_cpu_it in host_cpu_rec:
                if len(host_cpu_rec['cpu_pool']) == 0:
                    cnt += 1
            return cnt

        info = {
                'cpucores': _get_val(host_rec,
                                    ["cpu_configuration", "nr_cpus"]),
                'cpufeatures': getCpuFeatures(),
                'cpumhz': getCpuMhz(),
                'cpuarch': _get_val(host_rec,
                                    ["software_version", "machine"]),
                'cputhreads': _get_val(host_rec,
                                    ["cpu_configuration", "threads_per_core"]),
                'phymemory': int(host_metrics_rec["memory_total"]) / 1024 / 1024,
                'cores_per_sockets': _get_val(host_rec,
                                    ["cpu_configuration", "cores_per_socket"]),
                'free_cpus': getFreeCpuCount(),
                'free_memory': int(host_metrics_rec["memory_free"]) / 1024 / 1024,
                'xen_major': _get_val(host_rec,
                                    ["software_version", "xen_major"]),
                'xen_minor': _get_val(host_rec,
                                    ["software_version", "xen_minor"]),
                'xen_extra': _get_val(host_rec,
                                    ["software_version", "xen_extra"]),
                'xen_caps': " ".join(_get_val(host_rec, ["capabilities"])),
                'xen_scheduler': _get_val(host_rec,
                                    ["sched_policy"]),
                'xen_pagesize': _get_val(host_rec,
                                    ["other_config", "xen_pagesize"]),
                'platform_params': _get_val(host_rec,
                                    ["other_config", "platform_params"]),
                'xen_commandline': _get_val(host_rec,
                                    ["other_config", "xen_commandline"]),
                'xen_changeset': _get_val(host_rec,
                                    ["software_version", "xen_changeset"]),
                'cc_compiler': _get_val(host_rec,
                                    ["software_version", "cc_compiler"]),
                'cc_compile_by': _get_val(host_rec,
                                    ["software_version", "cc_compile_by"]),
                'cc_compile_domain': _get_val(host_rec,
                                    ["software_version", "cc_compile_domain"]),
                'cc_compile_date': _get_val(host_rec,
                                    ["software_version", "cc_compile_date"]),
                'xend_config_format': _get_val(host_rec,
                                    ["software_version", "xend_config_format"])
                }

        return info


def get_nics(vm_):
    '''
    Return info about the network interfaces of a named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_nics <vm name>
    '''
    with _get_xapi_session() as xapi:
        nic = {}

        vm_rec = _get_record_by_label(xapi, 'VM', vm_)
        if vm_rec is False:
            return False
        for vif in vm_rec['VIFs']:
            vif_rec = _get_record(xapi, 'VIF', vif)
            nic[vif_rec['MAC']] = {
                'mac': vif_rec['MAC'],
                'device': vif_rec['device'],
                'mtu': vif_rec['MTU']
            }

        return nic


def get_macs(vm_):
    '''
    Return a list off MAC addresses from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_macs <vm name>
    '''
    macs = []
    nics = get_nics(vm_)
    if nics is None:
        return None
    for nic in nics:
        macs.append(nic)

    return macs


def get_disks(vm_):
    '''
    Return the disks of a named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_disks <vm name>
    '''
    with _get_xapi_session() as xapi:

        disk = {}

        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        for vbd in xapi.VM.get_VBDs(vm_uuid):
            dev = xapi.VBD.get_device(vbd)
            if not dev:
                continue
            prop = xapi.VBD.get_runtime_properties(vbd)
            disk[dev] = {
                'backend': prop['backend'],
                'type': prop['device-type'],
                'protocol': prop['protocol']
            }

        return disk


def setmem(vm_, memory):
    '''
    Changes the amount of memory allocated to VM.

    Memory is to be specified in MB

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem myvm 768
    '''
    with _get_xapi_session() as xapi:
        mem_target = int(memory) * 1024 * 1024

        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.set_memory_dynamic_max_live(vm_uuid, mem_target)
            xapi.VM.set_memory_dynamic_min_live(vm_uuid, mem_target)
            return True
        except Exception:
            return False


def setvcpus(vm_, vcpus):
    '''
    Changes the amount of vcpus allocated to VM.

    vcpus is an int representing the number to be assigned

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setvcpus myvm 2
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.set_VCPUs_number_live(vm_uuid, vcpus)
            return True
        except Exception:
            return False


def vcpu_pin(vm_, vcpu, cpus):
    '''
    Set which CPUs a VCPU can use.

    CLI Example:

    .. code-block:: bash

        salt 'foo' virt.vcpu_pin domU-id 2 1
        salt 'foo' virt.vcpu_pin domU-id 2 2-6
    '''
    with _get_xapi_session() as xapi:

        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False

        # from xm's main
        def cpu_make_map(cpulist):
            cpus = []
            for c in cpulist.split(','):
                if c == '':
                    continue
                if '-' in c:
                    (x, y) = c.split('-')
                    for i in range(int(x), int(y) + 1):
                        cpus.append(int(i))
                else:
                    # remove this element from the list
                    if c[0] == '^':
                        cpus = [x for x in cpus if x != int(c[1:])]
                    else:
                        cpus.append(int(c))
            cpus.sort()
            return ','.join(map(str, cpus))

        if cpus == 'all':
            cpumap = cpu_make_map('0-63')
        else:
            cpumap = cpu_make_map('{0}'.format(cpus))

        try:
            xapi.VM.add_to_VCPUs_params_live(vm_uuid,
                                             'cpumap{0}'.format(vcpu), cpumap)
            return True
        # VM.add_to_VCPUs_params_live() implementation in xend 4.1+ has
        # a bug which makes the client call fail.
        # That code is accurate for all others XenAPI implementations, but
        # for that particular one, fallback to xm / xl instead.
        except Exception:
            return __salt__['cmd.run'](
                    '{0} vcpu-pin {1} {2} {3}'.format(_get_xtool(), vm_, vcpu, cpus),
                    python_shell=False)


def freemem():
    '''
    Return an int representing the amount of memory that has not been given
    to virtual machines on this node

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freemem
    '''
    return node_info()['free_memory']


def freecpu():
    '''
    Return an int representing the number of unallocated cpus on this
    hypervisor

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freecpu
    '''
    return node_info()['free_cpus']


def full_info():
    '''
    Return the node_info, vm_info and freemem

    CLI Example:

    .. code-block:: bash

        salt '*' virt.full_info
    '''
    return {'node_info': node_info(), 'vm_info': vm_info()}


def shutdown(vm_):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <vm name>
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.clean_shutdown(vm_uuid)
            return True
        except Exception:
            return False


def pause(vm_):
    '''
    Pause the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pause <vm name>
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.pause(vm_uuid)
            return True
        except Exception:
            return False


def resume(vm_):
    '''
    Resume the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.resume <vm name>
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.unpause(vm_uuid)
            return True
        except Exception:
            return False


def start(config_):
    '''
    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <path to Xen cfg file>
    '''
    # FIXME / TODO
    # This function does NOT use the XenAPI. Instead, it use good old xm / xl.
    # On Xen Source, creating a virtual machine using XenAPI is really painful.
    # XCP / XS make it really easy using xapi.Async.VM.start instead. Anyone?
    return __salt__['cmd.run']('{0} create {1}'.format(_get_xtool(), config_), python_shell=False)


def reboot(vm_):
    '''
    Reboot a domain via ACPI request

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <vm name>
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.clean_reboot(vm_uuid)
            return True
        except Exception:
            return False


def reset(vm_):
    '''
    Reset a VM by emulating the reset button on a physical machine

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reset <vm name>
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.hard_reboot(vm_uuid)
            return True
        except Exception:
            return False


def migrate(vm_, target,
            live=1, port=0, node=-1, ssl=None, change_home_server=0):
    '''
    Migrates the virtual machine to another hypervisor

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate <vm name> <target hypervisor> [live] [port] [node] [ssl] [change_home_server]

    Optional values:

    live
        Use live migration
    port
        Use a specified port
    node
        Use specified NUMA node on target
    ssl
        use ssl connection for migration
    change_home_server
        change home server for managed domains
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        other_config = {
            'port': port,
            'node': node,
            'ssl': ssl,
            'change_home_server': change_home_server
        }
        try:
            xapi.VM.migrate(vm_uuid, target, bool(live), other_config)
            return True
        except Exception:
            return False


def stop(vm_):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the
    power

    CLI Example:

    .. code-block:: bash

        salt '*' virt.stop <vm name>
    '''
    with _get_xapi_session() as xapi:
        vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
        if vm_uuid is False:
            return False
        try:
            xapi.VM.hard_shutdown(vm_uuid)
            return True
        except Exception:
            return False


def is_hyper():
    '''
    Returns a bool whether or not this node is a hypervisor of any kind

    CLI Example:

    .. code-block:: bash

        salt '*' virt.is_hyper
    '''
    try:
        if __grains__['virtual_subtype'] != 'Xen Dom0':
            return False
    except KeyError:
        # virtual_subtype isn't set everywhere.
        return False
    try:
        with salt.utils.files.fopen('/proc/modules') as fp_:
            if 'xen_' not in salt.utils.stringutils.to_unicode(fp_.read()):
                return False
    except (OSError, IOError):
        return False
    # there must be a smarter way...
    return 'xenstore' in __salt__['cmd.run'](__grains__['ps'])


def vm_cputime(vm_=None):
    '''
    Return cputime used by the vms on this hyper in a
    list of dicts:

    .. code-block:: python

        [
            'your-vm': {
                'cputime' <int>
                'cputime_percent' <int>
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_cputime
    '''
    with _get_xapi_session() as xapi:
        def _info(vm_):
            host_rec = _get_record_by_label(xapi, 'VM', vm_)
            host_cpus = len(host_rec['host_CPUs'])
            if host_rec is False:
                return False
            host_metrics = _get_metrics_record(xapi, 'VM', host_rec)
            vcpus = int(host_metrics['VCPUs_number'])
            cputime = int(host_metrics['VCPUs_utilisation']['0'])
            cputime_percent = 0
            if cputime:
                # Divide by vcpus to always return a number between 0 and 100
                cputime_percent = (1.0e-7 * cputime / host_cpus) / vcpus
            return {'cputime': int(cputime),
                    'cputime_percent': int('{0:.0f}'.format(cputime_percent))}
        info = {}
        if vm_:
            info[vm_] = _info(vm_)
            return info

        for vm_ in list_domains():
            info[vm_] = _info(vm_)

        return info


def vm_netstats(vm_=None):
    '''
    Return combined network counters used by the vms on this hyper in a
    list of dicts:

    .. code-block:: python

        [
            'your-vm': {
                'io_read_kbs'           : 0,
                'io_total_read_kbs'     : 0,
                'io_total_write_kbs'    : 0,
                'io_write_kbs'          : 0
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_netstats
    '''
    with _get_xapi_session() as xapi:
        def _info(vm_):
            ret = {}
            vm_rec = _get_record_by_label(xapi, 'VM', vm_)
            if vm_rec is False:
                return False
            for vif in vm_rec['VIFs']:
                vif_rec = _get_record(xapi, 'VIF', vif)
                ret[vif_rec['device']] = _get_metrics_record(xapi, 'VIF',
                                                             vif_rec)
                del ret[vif_rec['device']]['last_updated']

            return ret

        info = {}
        if vm_:
            info[vm_] = _info(vm_)
        else:
            for vm_ in list_domains():
                info[vm_] = _info(vm_)
        return info


def vm_diskstats(vm_=None):
    '''
    Return disk usage counters used by the vms on this hyper in a
    list of dicts:

    .. code-block:: python

        [
            'your-vm': {
                'io_read_kbs'   : 0,
                'io_write_kbs'  : 0
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_diskstats
    '''
    with _get_xapi_session() as xapi:
        def _info(vm_):
            ret = {}
            vm_uuid = _get_label_uuid(xapi, 'VM', vm_)
            if vm_uuid is False:
                return False
            for vbd in xapi.VM.get_VBDs(vm_uuid):
                vbd_rec = _get_record(xapi, 'VBD', vbd)
                ret[vbd_rec['device']] = _get_metrics_record(xapi, 'VBD',
                                                             vbd_rec)
                del ret[vbd_rec['device']]['last_updated']

            return ret

        info = {}
        if vm_:
            info[vm_] = _info(vm_)
        else:
            for vm_ in list_domains():
                info[vm_] = _info(vm_)
        return info
