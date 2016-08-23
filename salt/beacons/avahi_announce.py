# -*- coding: utf-8 -*-
'''
 Beacon to announce via avahi (zeroconf)

'''
# Import Python libs
from __future__ import absolute_import
import logging

# Import 3rd Party libs
try:
    import avahi
    HAS_PYAVAHI = True
except ImportError:
    HAS_PYAVAHI = False
import dbus

log = logging.getLogger(__name__)

__virtualname__ = 'avahi_announce'

LAST_GRAINS = {}
BUS = dbus.SystemBus()
SERVER = dbus.Interface(BUS.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER),
                        avahi.DBUS_INTERFACE_SERVER)
GROUP = dbus.Interface(BUS.get_object(avahi.DBUS_NAME, SERVER.EntryGroupNew()),
                       avahi.DBUS_INTERFACE_ENTRY_GROUP)


def __virtual__():
    if HAS_PYAVAHI:
        return __virtualname__
    return False


def __validate__(config):
    '''
    Validate the beacon configuration
    '''
    if not isinstance(config, dict):
        return False, ('Configuration for avahi_announcement '
                       'beacon must be a dictionary')
    elif not all(x in list(config.keys()) for x in ('servicetype', 'port', 'txt')):
        return False, ('Configuration for avahi_announce beacon '
                       'must contain servicetype, port and txt items')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Broadcast values via zeroconf

    If the announced values are static, it is adviced to set run_once: True
    (do not poll) on the beacon configuration. Grains can be used to define
    txt values using the syntax: grains.<grain_name>

    The default servicename its the hostname grain value.

    Example Config

    .. code-block:: yaml

       beacons:
          avahi_announce:
             run_once: True
             servicetype: _demo._tcp
             txt:
                ProdName: grains.productname
                SerialNo: grains.serialnumber
                Comments: 'this is a test'
    '''
    ret = []
    changes = {}
    txt = {}

    global LAST_GRAINS

    _validate = validate(config)
    if not _validate[0]:
        log.warning('Beacon {0} configuration invalid, '
                    'not adding. {1}'.format(__virtualname__, _validate[1]))
        return ret

    if 'servicename' in config:
        servicename = config['servicename']
    else:
        servicename = __grains__['host']

    for item in config['txt']:
        if config['txt'][item].startswith('grains.'):
            grain = config['txt'][item][7:]
            txt[item] = __grains__[grain]
            if LAST_GRAINS and (LAST_GRAINS[grain] != __grains__[grain]):
                changes[str('txt.' + item)] = txt[item]
        else:
            txt[item] = config['txt'][item]

        if not LAST_GRAINS:
            changes[str('txt.' + item)] = txt[item]

    if changes:
        if not LAST_GRAINS:
            changes['servicename'] = servicename
            changes['servicetype'] = config['servicetype']
            changes['port'] = config['port']
        else:
            GROUP.Reset()
        GROUP.AddService(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                         servicename, config['servicetype'], '', '',
                         dbus.UInt16(config['port']), avahi.dict_to_txt_array(txt))
        GROUP.Commit()

        ret.append({'tag': 'result', 'changes': changes})

    LAST_GRAINS = __grains__

    return ret
