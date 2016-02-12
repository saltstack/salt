# -*- coding: utf-8 -*-
'''
Watch files and translate the changes into salt events

:depends:   - pyinotify Python module >= 0.9.5

:Caution:   Using generic mask options like open, access, ignored, and
            closed_nowrite with reactors can easily cause the reactor
            to loop on itself. To mitigate this behavior, consider
            setting the `disable_during_state_run` flag to `True` in
            the beacon configuration.

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
    __context__['inotify.queue'].append(revent)


def _get_notifier():
    '''
    Check the context for the notifier and construct it if not present
    '''
    if 'inotify.notifier' not in __context__:
        __context__['inotify.queue'] = collections.deque()
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
    log.debug('config {0}'.format(config))
    if not isinstance(config, dict):
        return False, 'Configuration for inotify beacon must be a dictionary.'
    else:
        for config_item in config:
            if not isinstance(config[config_item], dict):
                return False, ('Configuration for inotify beacon must '
                               'be a dictionary of dictionaries.')
            else:
                if not any(j in ['mask', 'recurse', 'auto_add'] for j in config[config_item]):
                    return False, ('Configuration for inotify beacon '
                                   'must contain mask, recurse or auto_add items.')

            if 'auto_add' in config[config_item]:
                if not isinstance(config[config_item]['auto_add'], bool):
                    return False, ('Configuration for inotify beacon '
                                   'auto_add must be boolean.')

            if 'recurse' in config[config_item]:
                if not isinstance(config[config_item]['recurse'], bool):
                    return False, ('Configuration for inotify beacon '
                                   ' recurse must be boolean.')

            if 'mask' in config[config_item]:
                if not isinstance(config[config_item]['mask'], list):
                    return False, ('Configuration for inotify beacon '
                                   ' mask must be list.')

                for mask in config[config_item]['mask']:
                    if mask not in VALID_MASK:
                        return False, ('Configuration for inotify beacon '
                                       'invalid mask option {0}.'.format(mask))
    return True, 'Valid beacon configuration'


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

    The mask list can contain the following events (the default mask is create,
    delete, and modify):

    * access            File accessed
    * attrib            File metadata changed
    * close_nowrite     Unwritable file closed
    * close_write       Writable file closed
    * create            File created in watched directory
    * delete            File deleted from watched directory
    * delete_self       Watched file or directory deleted
    * modify            File modified
    * moved_from        File moved out of watched directory
    * moved_to          File moved into watched directory
    * move_self         Watched file moved
    * open              File opened

    The mask can also contain the following options:

    * dont_follow       Don't dereference symbolic links
    * excl_unlink       Omit events for children after they have been unlinked
    * oneshot           Remove watch after one event
    * onlydir           Operate only if name is directory

    recurse:
      Recursively watch files in the directory
    auto_add:
      Automatically start watching files that are created in the watched directory
    '''
    ret = []
    notifier = _get_notifier()
    wm = notifier._watch_manager

    # Read in existing events
    if notifier.check_events(1):
        notifier.read_events()
        notifier.process_events()
        queue = __context__['inotify.queue']
        while queue:
            event = queue.popleft()
            sub = {'tag': event.path,
                   'path': event.pathname,
                   'change': event.maskname}
            ret.append(sub)

    # Get paths currently being watched
    current = set()
    for wd in wm.watches:
        current.add(wm.watches[wd].path)

    # Update existing watches and add new ones
    # TODO: make the config handle more options
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

        if path in current:
            for wd in wm.watches:
                if path == wm.watches[wd].path:
                    update = False
                    if wm.watches[wd].mask != mask:
                        update = True
                    if wm.watches[wd].auto_add != auto_add:
                        update = True
                    if update:
                        wm.update_watch(wd, mask=mask, rec=rec, auto_add=auto_add)
        else:
            wm.add_watch(path, mask, rec=rec, auto_add=auto_add)

    # Return event data
    return ret
