'''
The actual saltkey functional code
'''

# Import python modules
import os
import shutil
import sys
import logging
import glob
import fnmatch
# Import salt modules
import salt.crypt
import salt.utils
import salt.utils.event

log = logging.getLogger(__name__)


class Key(object):
    '''
    The object that encapsulates saltkey actions
    '''
    def __init__(self, opts):
        self.opts = opts
        self.event = salt.utils.event.MasterEvent(opts['sock_dir'])

    def _check_minions_directories(self):
        '''
        Return the minion keys directory paths
        '''
        minions_accepted = os.path.join(self.opts['pki_dir'], 'minions')
        minions_pre = os.path.join(self.opts['pki_dir'], 'minions_pre')
        minions_rejected = os.path.join(self.opts['pki_dir'],
                                        'minions_rejected')
        return minions_accepted, minions_pre, minions_rejected

    def check_master(self):
        '''
        Log if the master is not running
        '''
        if not os.path.exists(
                os.path.join(
                    self.opts['sock_dir'],
                    'publish_pull.ipc'
                    )
                ):
            return False
        return True

    def name_match(self, match, full=False):
        '''
        Accept a glob which to match the of a key and return the key's location
        '''
        if full:
            matches = self.list_all()
        else:
            matches = self.list_keys()
        ret = {}
        for status, keys in matches:
            for key in keys:
                if fnmatch(key, match):
                    if not status in ret:
                        ret[status] = []
                    ret[status].append(key)
        return ret

    def local_keys(self):
        '''
        Return a dict of local keys
        '''
        ret = {'local': []}
        for fn_ in os.listdir(self.opts['pki_dir']):
            if fn_.endswith('.pub') or fn_.endswith('.pem'):
                path = os.path.join(self.opts['pki_dir'], fn_)
                if os.path.isfile(path):
                    ret['local'].append(fn_)
        return ret

    def list_keys(self):
        '''
        Return a dict of managed keys and what the key status are
        '''
        acc, pre, rej = _check_minions_directories()
        ret = {}
        for dir_ in acc, pre, rej:
            ret[os.path.basename(dir_)] = []
            for fn_ in os.listdir(dir_):
                ret[os.path.basename(dir_)].append(fn_)
        return ret

    def all_keys(self):
        '''
        Merge managed keys with local keys
        '''
        return self.list_keys().update(self.local_keys())

    def key_str(self, match):
        '''
        Return the specified public key or keys based on a glob
        '''
        ret = {}
        for status, keys in self.name_match(match):
            ret[status] = {}
            for key in keys:
                path = os.path.join(self.opts['pki_dir'], status, key)
                with open(path, 'r') as fp_:
                    ret[status][key] = fp_.read()
        return ret

    def key_str_all(self):
        '''
        Return all managed key strings
        '''
        ret = {}
        for status, keys in self.list_keys():
            ret[status] = {}
            for key in keys:
                path = os.path.join(self.opts['pki_dir'], status, key)
                with open(path, 'r') as fp_:
                    ret[status][key] = fp_.read()
        return ret

    def accept(self, match):
        '''
        Accept a specified host's public key based on name or keys based on
        glob
        '''
        matches = self.name_match(match)
        if 'minions_pre' in matches:
            for key in matches['minions_pre']:
                try:
                    shutil.move(
                            os.path.join(
                                self.opts['pki_dir'],
                                'minions_pre',
                                key),
                            os.path.join(
                                self.opts['pki_dir'],
                                'minions',
                                key)
                            )
                    eload = {'result': True,
                             'act': 'accept',
                             'id': key}
                    self.event.fire_event(eload, 'key')
                except (IOError, OSError):
                    pass
        return self.name_match(match)

    def accept_all(self):
        '''
        Accept all keys in pre
        '''
        keys = self.list_keys()
        for key in keys['minions_pre']:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            'minions_pre',
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            'minions',
                            key)
                        )
                eload = {'result': True,
                         'act': 'accept',
                         'id': key}
                self.event.fire_event(eload, 'key')
            except (IOError, OSError):
                pass
        return self.list_keys()

    def delete_key(self, match):
        '''
        Delete a single key or keys by glob
        '''
        for status, keys in self.name_match(match):
            for key in keys:
                try:
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                except (OSError, IOError):
                    pass
        return self.list_keys()

    def delete_all(self):
        '''
        Delete all keys
        '''
        for status, keys in self.list_keys():
            for key in keys:
                try:
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                except (OSError, IOError):
                    pass
        return self.list_keys()

    def reject(self, match):
        '''
        Reject a specified host's public key or keys based on a glob
        '''
        matches = self.name_match(match)
        if 'minions_pre' in matches:
            for key in matches['minions_pre']:
                try:
                    shutil.move(
                            os.path.join(
                                self.opts['pki_dir'],
                                'minions_pre',
                                key),
                            os.path.join(
                                self.opts['pki_dir'],
                                'minions_rejected',
                                key)
                            )
                    eload = {'result': True,
                             'act': 'reject',
                             'id': key}
                    self.event.fire_event(eload, 'key')
                except (IOError, OSError):
                    pass
        return self.name_match(match)

    def reject_all(self):
        '''
        Reject all keys in pre
        '''
        keys = self.list_keys()
        for key in keys['minions_pre']:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            'minions_pre',
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            'minions_rejected',
                            key)
                        )
                eload = {'result': True,
                         'act': 'reject',
                         'id': key}
                self.event.fire_event(eload, 'key')
            except (IOError, OSError):
                pass
        return self.list_keys()

    def finger(self, match):
        '''
        Return the fingerprint for a specified key
        '''
        matches = self.name_match(match, True)
        ret = {}
        for status, keys in matches.items():
            ret[status] = {}
            for key in keys:
                ret[status][key] = salt.utils.pem_finger(key)
        return ret

    def finger_all(self):
        '''
        Return fingerprins for all keys
        '''
        ret = {}
        for status, keys in self.list_keys():
            ret[status] = {}
            for key in keys:
                ret[status][key] = salt.utils.pem_finger(key)
        return ret
