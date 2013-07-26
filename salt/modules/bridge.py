'''
Module for gathering and managing bridging informations
'''

import sys
import re
import salt.utils


__func_alias__ = {
    'list_': 'list'
}

def __virtual__():
    '''
    Confirm this module is supported by the OS and the system has
    required tools
    '''
    supported_os = {
        'Linux': 'brctl',
        'NetBSD': 'brconfig'
    }
    cur_os = __grains__['kernel']
    for _os in supported_os:
        if cur_os == _os and salt.utils.which(supported_os[cur_os]):
            return 'bridge'
    return False


def _tool_path(ostool):
    '''
    Internal, returns tools path
    '''
    return salt.utils.which(ostool)


def _linux_brshow(br=None):
    '''
    Internal, returns bridges and enslaved interfaces (GNU/Linux - brctl)
    '''
    brctl = _tool_path('brctl')

    if br:
        cmd = '{0} show {1}'.format(brctl, br)
    else:
        cmd = '{0} show'.format(brctl)

    brs = {}

    for line in __salt__['cmd.run'](cmd).splitlines():
        # get rid of first line
        if line.startswith('bridge name'):
            continue
        # get rid of ^\n's
        vals = line.split()
        if not vals:
            continue

        # bridge name bridge id       STP enabled interfaces
        # br0       8000.e4115bac8ddc   no      eth0
        #                                       foo0
        # br1       8000.e4115bac8ddc   no      eth1
        if len(vals) > 1:
            brname = vals[0]

            brs[brname] = {
                'id': vals[1],
                'stp': vals[2],
            }
            if len(vals) > 3:
                brs[brname]['interfaces'] = [vals[3]]

        if len(vals) == 1 and brname:
            brs[brname]['interfaces'].append(vals[0])

    if br:
        try:
            return brs[br]
        except KeyError, ke :
            return None
    return brs


def _linux_bradd(br):
    '''
    Internal, creates the bridge
    '''
    brctl = _tool_path('brctl')
    return __salt__['cmd.run']('{0} addbr {1}'.format(brctl, br))


def _linux_brdel(br):
    '''
    Internal, deletes the bridge
    '''
    brctl = _tool_path('brctl')
    return __salt__['cmd.run']('{0} delbr {1}'.format(brctl, br))


def _linux_addif(br, iface):
    '''
    Internal, adds an interface to a bridge
    '''
    brctl = _tool_path('brctl')
    return __salt__['cmd.run']('{0} addif {1} {2}'.format(brctl, br, iface))


def _linux_delif(br, iface):
    '''
    Internal, removes an interface from a bridge
    '''
    brctl = _tool_path('brctl')
    return __salt__['cmd.run']('{0} delif {1} {2}'.format(brctl, br, iface))


def _linux_stp(br, state):
    '''
    Internal, sets STP state
    '''
    brctl = _tool_path('brctl')
    return __salt__['cmd.run']('{0} stp {1} {2}'.format(brctl, br, state))


def _netbsd_brshow(br=None):
    '''
    Internal, returns bridges and enslaved interfaces (NetBSD - brconfig)
    '''
    brconfig = _tool_path('brconfig')

    if br:
        cmd = '{0} {1}'.format(brconfig, br)
    else:
        cmd = '{0} -a'.format(brconfig)

    brs = {}
    start_int = False

    for line in __salt__['cmd.run'](cmd).splitlines():
        if line.startswith('bridge'):
            start_int = False
            brname = line.split(':')[0] # on NetBSD, always ^bridge[0-9]:
            brs[brname] = {
                'interfaces': [],
                'stp': 'no'
            }
        if 'Interfaces:' in line:
            start_int = True
            continue
        if start_int and brname:
            m = re.match(r'\s*([a-z0-9]+)\s.*<.*>', line)
            if m:
                brs[brname]['interfaces'].append(m.group(1))
                if 'STP' in line:
                    brs[brname]['stp'] = 'yes'

    if br:
        try:
            return brs[br]
        except KeyError, ke :
            return None
    return brs


def _netbsd_bradd(br):
    '''
    Internal, creates the bridge
    '''
    brconfig = _tool_path('brconfig')
    ifconfig = _tool_path('ifconfig')
    if not br or not ifconfig:
        return False
    if __salt__['cmd.retcode']('{0} {1} create'.format(ifconfig, br)) != 0:
        return False
    if __salt__['cmd.retcode']('{0} {1} up'.format(brconfig, br)) != 0:
        return False
    return True


def _netbsd_brdel(br):
    '''
    Internal, deletes the bridge
    '''
    ifconfig = _tool_path('ifconfig')
    if not br or not ifconfig:
        return False
    return __salt__['cmd.run']('{0} {1} destroy'.format(ifconfig, br))


def _netbsd_addif(br, iface):
    '''
    Internal, adds an interface to a bridge
    '''
    brconfig = _tool_path('brconfig')
    return __salt__['cmd.run']('{0} {1} add {2}'.format(brconfig, br, iface))


def _netbsd_delif(br, iface):
    '''
    Internal, removes an interface from a bridge
    '''
    brconfig = _tool_path('brconfig')
    return __salt__['cmd.run']('{0} {1} delete {2}'.format(brconfig, br, iface))


def _netbsd_stp(br, state, iface):
    '''
    Internal, sets STP state. On NetBSD, it is required to specify the
    STP physical interface
    '''
    brconfig = _tool_path('brconfig')
    if not br or not iface:
        return False
    return __salt__['cmd.run']('{0} {1} {2} {3}'.
                                format(brconfig, br, state, iface))


def _os_dispatch(func, *args, **kwargs):
    '''
    Internal, dispatches functions by operating system
    '''
    _os_func = getattr(sys.modules[__name__], '_{0}_{1}'.
                            format(__grains__['kernel'].lower(), func))
    if callable(_os_func):
        return _os_func(*args, **kwargs)


# End of internal functions


def show(br=None):
    '''
    Returns bridges interfaces along with enslaved physical interfaces. If
    no interface is given, all bridges are shown, else only the specified
    bridge values are returned.

    CLI Example::

        salt '*' bridge.show
        salt '*' bridge.show br0
    '''
    return _os_dispatch('brshow', br)


def list_():
    '''
    Returns the machine's bridges list

    CLI Example::

        salt '*' bridge.list
    '''
    brs = _os_dispatch('brshow')
    if not brs:
        return None
    brlist = []
    for br in brs:
        brlist.append(br)

    return brlist


def interfaces(br=None):
    '''
    Returns interfaces attached to a bridge

    CLI Example::

        salt '*' bridge.interfaces br0
    '''
    if not br:
        return None

    br_ret = _os_dispatch('brshow', br)
    if br_ret:
        return br_ret['interfaces']


def find_interfaces(*args):
    '''
    Returns the bridge to which the interfaces are bond to

    CLI Example::

        salt '*' bridge.find_interfaces eth0 [eth1...]
    '''
    brs = _os_dispatch('brshow')
    if not brs:
        return None

    iflist = {}

    for iface in args:
        for br in brs:
            try: # a bridge may not contain interfaces
                if iface in brs[br]['interfaces']:
                    iflist[iface] = br
            except Exception:
                pass

    return iflist


def add(br=None):
    '''
    Creates a bridge

    CLI Example::

        salt '*' bridge.add br0
    '''
    return _os_dispatch('bradd', br)


def delete(br=None):
    '''
    Deletes a bridge

    CLI Example::

        salt '*' bridge.delete br0
    '''
    return _os_dispatch('brdel', br)


def addif(br=None, iface=None):
    '''
    Adds an interface to a bridge

    CLI Example::

        salt '*' bridge.addif br0 eth0
    '''
    return _os_dispatch('addif', br, iface)


def delif(br=None, iface=None):
    '''
    Removes an interface from a bridge

    CLI Example::

        salt '*' bridge.delif br0 eth0
    '''
    return _os_dispatch('delif', br, iface)


def stp(br=None, state='disable', iface=None):
    '''
    Sets Spanning Tree Protocol state for a bridge

    CLI Example::

        salt '*' bridge.stp br0 enable
        salt '*' bridge.stp br0 disable

    For the NetBSD operating system, it is required to add the interface on
    which to enable the STP.

    CLI Example::

        salt '*' bridge.stp bridge0 enable fxp0
        salt '*' bridge.stp bridge0 disable fxp0
    '''
    if __grains__['kernel'] == 'Linux':
        states = {'enable': 'on', 'disable': 'off'}
        return _os_dispatch('stp', br, states[state])
    elif __grains__['kernel'] == 'NetBSD':
        states = {'enable': 'stp', 'disable': '-stp'}
        return _os_dispatch('stp', br, states[state], iface)


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
