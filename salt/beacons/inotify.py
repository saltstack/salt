# -*- coding: utf-8 -*-
'''
Watch files and translate the changes into salt events
'''
# Import python libs
import collections

# Import third party libs
try:
    import pyinotify
    HAS_PYINOTIFY = True
    DEFAULT_MASK = pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_MODIFY
except ImportError:
    HAS_PYINOTIFY = False
    DEFAULT_MASK = None

__virtualname__ = 'inotify'


def __virtual__():
    if HAS_PYINOTIFY:
        return __virtualname__
    return False


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


def beacon(config):
    '''
    Watch the configured files
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
            rec = config[path].get('rec', False)
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
