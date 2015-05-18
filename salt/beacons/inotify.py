# -*- coding: utf-8 -*-
'''
Watch files and translate the changes into salt events

:depends:   - pyinotify Python module >= 0.9.5

:Caution:   Using generic mask options like open, access, ignored, and
:           closed_nowrite with reactors can easily cause the reactor
:           to loop on itself.

'''
# Import Python libs
from __future__ import absolute_import
import collections

# Import salt libs
import salt.ext.six

# Import third party libs
try:
    import pyinotify
    HAS_PYINOTIFY = True
    DEFAULT_MASK = pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_MODIFY
    MASKS = {}
    for var in dir(pyinotify):
        if var.startswith('IN_'):
            key = var[3:].lower()
            MASKS[key] = getattr(pyinotify, var)
except ImportError:
    HAS_PYINOTIFY = False
    DEFAULT_MASK = None

__virtualname__ = 'inotify'

import logging
log = logging.getLogger(__name__)


def __virtual__():
    if HAS_PYINOTIFY:
        return __virtualname__
    return False


def _get_mask(mask):
    '''
    Return the int that represents the mask
    '''
    return MASKS.get(mask, 0)


def _enqueue(revent):
    '''
    Enqueue the event
    '''
    __context__['inotify.que'].append(revent)


def _get_notifier():
    '''
    Check the context for the notifier and construct it if not present
    '''
    if 'inotify.notifier' in __context__:
        return __context__['inotify.notifier']
    __context__['inotify.que'] = collections.deque()
    wm = pyinotify.WatchManager()
    __context__['inotify.notifier'] = pyinotify.Notifier(wm, _enqueue)
    return __context__['inotify.notifier']


def validate(config):
    '''
    Validate the beacon configuration
    '''

    VALID_MASK = [
        'access',
        'attrib',
        'close_nowrite',
        'close_write',
        'create',
        'delete',
        'delete_self',
        'excl_unlink',
        'ignored',
        'modify',
        'moved_from',
        'moved_to',
        'move_self',
        'oneshot',
        'onlydir',
        'open',
        'unmount'
    ]

    # Configuration for diskusage beacon should be a list of dicts
    if not isinstance(config, dict):
        log.info('Configuration for inotify beacon must be a dictionary.')
        return False
    else:
        for config_item in config:
            if not isinstance(config[config_item], dict):
                log.info('Configuration for inotify beacon must '
                         'be a dictionary of dictionaries.')
                return False
            else:
                if not any(j in ['mask', 'recurse', 'auto_add'] for j in config[config_item]):
                    log.info('Configuration for inotify beacon must '
                             'contain mask, recurse or auto_add items.')
                    return False

            if 'auto_add' in config[config_item]:
                if not isinstance(config[config_item]['auto_add'], bool):
                    log.info('Configuration for inotify beacon '
                             'auto_add must be boolean.')
                    return False

            if 'recurse' in config[config_item]:
                if not isinstance(config[config_item]['recurse'], bool):
                    log.info('Configuration for inotify beacon '
                             'recurse must be boolean.')
                    return False

            if 'mask' in config[config_item]:
                if not isinstance(config[config_item]['mask'], list):
                    log.info('Configuration for inotify beacon '
                             'mask must be list.')
                    return False
                for mask in config[config_item]['mask']:
                    if mask not in VALID_MASK:
                        log.info('Configuration for inotify beacon '
                                 'invalid mask option {0}.'.format(mask))
                        return False
    return True


def beacon(config):
    '''
    Watch the configured files

    Example Config

    .. code-block:: yaml

        beacons:
          inotify:
            /path/to/file/or/dir:
              mask:
                - open
                - create
                - close_write
              recurse: True
              auto_add: True

    The mask list can contain options:
        * access            File was accessed
        * attrib            Metadata changed
        * close_nowrite     Unwrittable file closed
        * close_write       Writtable file was closed
        * create            File created
        * delete            File deleted
        * delete_self       Named file or directory deleted
        * excl_unlink
        * ignored
        * modify            File was modified
        * moved_from        File being watched was moved
        * moved_to          File moved into watched area
        * move_self         Named file was moved
        * oneshot
        * onlydir           Operate only if name is directory
        * open              File was opened
        * unmount           Backing fs was unmounted
    recurse:
      Tell the beacon to recursively watch files in the directory
    auto_add:
      Automatically start adding files that are created in the watched directory
    '''
    ret = []
    notifier = _get_notifier()
    wm = notifier._watch_manager
    # Read in existing events
    # remove watcher files that are not in the config
    # update all existing files with watcher settings
    # return original data
    if notifier.check_events(1):
        notifier.read_events()
        notifier.process_events()
        while __context__['inotify.que']:
            sub = {}
            event = __context__['inotify.que'].popleft()
            sub['tag'] = event.path
            sub['path'] = event.pathname
            sub['change'] = event.maskname
            ret.append(sub)

    current = set()
    for wd in wm.watches:
        current.add(wm.watches[wd].path)
    need = set(config)
    for path in current.difference(need):
        # These need to be removed
        for wd in wm.watches:
            if path == wm.watches[wd].path:
                wm.rm_watch(wd)
    for path in config:
        if isinstance(config[path], dict):
            mask = config[path].get('mask', DEFAULT_MASK)
            if isinstance(mask, list):
                r_mask = 0
                for sub in mask:
                    r_mask |= _get_mask(sub)
            elif isinstance(mask, salt.ext.six.binary_type):
                r_mask = _get_mask(mask)
            else:
                r_mask = mask
            mask = r_mask
            rec = config[path].get('recurse', False)
            auto_add = config[path].get('auto_add', False)
        else:
            mask = DEFAULT_MASK
            rec = False
            auto_add = False
        # TODO: make the config handle more options
        if path not in current:
            wm.add_watch(
                path,
                mask,
                rec=rec,
                auto_add=auto_add)
        else:
            for wd in wm.watches:
                if path == wm.watches[wd].path:
                    update = False
                    if wm.watches[wd].mask != mask:
                        update = True
                    if wm.watches[wd].auto_add != auto_add:
                        update = True
                    if update:
                        wm.update_watch(
                            wd,
                            mask=mask,
                            rec=rec,
                            auto_add=auto_add)
    return ret
