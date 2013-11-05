# -*- coding: utf-8 -*-
'''
The Salt Key backend API and interface used by the CLI. The Key class can be
used to manage salt keys directly without interfacing with the CLI.
'''

# Import python libs
import os
import shutil
import fnmatch

# Import salt libs
import salt.crypt
import salt.utils
import salt.utils.event
from salt.utils.event import tagify


class KeyCLI(object):
    '''
    Manage key CLI operations
    '''
    def __init__(self, opts):
        self.opts = opts
        self.key = Key(opts)

    def list_status(self, status):
        '''
        Print out the keys under a named status
        '''
        keys = self.key.list_keys()
        if status.startswith('acc'):
            salt.output.display_output(
                {'minions': keys['minions']},
                'key',
                self.opts
            )
        elif status.startswith('pre') or status.startswith('un'):
            salt.output.display_output(
                {'minions_pre': keys['minions_pre']},
                'key',
                self.opts
            )
        elif status.startswith('rej'):
            salt.output.display_output(
                {'minions_rejected': keys['minions_rejected']},
                'key',
                self.opts
            )

    def list_all(self):
        '''
        Print out all keys
        '''
        salt.output.display_output(
                self.key.list_keys(),
                'key',
                self.opts)

    def accept(self, match, include_rejected=False):
        '''
        Accept the keys matched
        '''
        def _print_accepted(matches, after_match):
            if 'minions' in after_match:
                accepted = sorted(
                    set(after_match['minions']).difference(
                        set(matches.get('minions', []))
                    )
                )
                for key in accepted:
                    print('Key for minion {0} accepted.'.format(key))

        matches = self.key.name_match(match)
        keys = {}
        if 'minions_pre' in matches:
            keys['minions_pre'] = matches['minions_pre']
        if include_rejected and bool(matches.get('minions_rejected')):
            keys['minions_rejected'] = matches['minions_rejected']
        if not keys:
            msg = (
                'The key glob {0!r} does not match any unaccepted {1}keys.'
                .format(match, 'or rejected ' if include_rejected else '')
            )
            print(msg)
            return
        if not self.opts.get('yes', False):
            print('The following keys are going to be accepted:')
            salt.output.display_output(
                    keys,
                    'key',
                    self.opts)
            try:
                veri = raw_input('Proceed? [n/Y] ')
            except KeyboardInterrupt:
                raise SystemExit("\nExiting on CTRL-c")
            if not veri or veri.lower().startswith('y'):
                _print_accepted(
                    matches,
                    self.key.accept(
                        match_dict=keys,
                        include_rejected=include_rejected
                    )
                )
        else:
            print('The following keys are going to be accepted:')
            salt.output.display_output(
                    keys,
                    'key',
                    self.opts)
            _print_accepted(
                matches,
                self.key.accept(
                    match_dict=keys,
                    include_rejected=include_rejected
                )
            )

    def accept_all(self, include_rejected=False):
        '''
        Accept all keys
        '''
        self.accept('*', include_rejected=include_rejected)

    def delete(self, match):
        '''
        Delete the matched keys
        '''
        def _print_deleted(matches, after_match):
            deleted = []
            for keydir in ('minions', 'minions_pre', 'minions_rejected'):
                deleted.extend(list(
                    set(matches.get(keydir, [])).difference(
                        set(after_match.get(keydir, []))
                    )
                ))
            for key in sorted(deleted):
                print('Key for minion {0} deleted.'.format(key))

        matches = self.key.name_match(match)
        if not matches:
            print(
                'The key glob {0!r} does not match any accepted, unaccepted '
                'or rejected keys.'.format(match)
            )
            return
        if not self.opts.get('yes', False):
            print('The following keys are going to be deleted:')
            salt.output.display_output(
                    matches,
                    'key',
                    self.opts)
            try:
                veri = raw_input('Proceed? [N/y] ')
            except KeyboardInterrupt:
                raise SystemExit("\nExiting on CTRL-c")
            if veri.lower().startswith('y'):
                _print_deleted(
                    matches,
                    self.key.delete_key(match_dict=matches)
                )
        else:
            print('Deleting the following keys:')
            salt.output.display_output(
                    matches,
                    'key',
                    self.opts)
            _print_deleted(
                matches,
                self.key.delete_key(match_dict=matches)
            )

    def delete_all(self):
        '''
        Delete all keys
        '''
        self.delete('*')

    def reject(self, match, include_accepted=False):
        '''
        Reject the matched keys
        '''
        def _print_rejected(matches, after_match):
            if 'minions_rejected' in after_match:
                rejected = sorted(
                    set(after_match['minions_rejected']).difference(
                        set(matches.get('minions_rejected', []))
                    )
                )
                for key in rejected:
                    print('Key for minion {0} rejected.'.format(key))

        matches = self.key.name_match(match)
        keys = {}
        if 'minions_pre' in matches:
            keys['minions_pre'] = matches['minions_pre']
        if include_accepted and bool(matches.get('minions')):
            keys['minions'] = matches['minions']
        if not keys:
            msg = 'The key glob {0!r} does not match any {1} keys.'.format(
                match,
                'accepted or unaccepted' if include_accepted else 'unaccepted'
            )
            print(msg)
            return
        if not self.opts.get('yes', False):
            print('The following keys are going to be rejected:')
            salt.output.display_output(
                    keys,
                    'key',
                    self.opts)
            veri = raw_input('Proceed? [n/Y] ')
            if veri.lower().startswith('n'):
                return
        _print_rejected(
            matches,
            self.key.reject(
                match_dict=matches,
                include_accepted=include_accepted
            )
        )

    def reject_all(self, include_accepted=False):
        '''
        Reject all keys
        '''
        self.reject('*', include_accepted=include_accepted)

    def print_key(self, match):
        '''
        Print out a single key
        '''
        matches = self.key.key_str(match)
        salt.output.display_output(
                matches,
                'key',
                self.opts)

    def print_all(self):
        '''
        Print out all managed keys
        '''
        self.print_key('*')

    def finger(self, match):
        '''
        Print out the fingerprints for the matched keys
        '''
        matches = self.key.finger(match)
        salt.output.display_output(
                matches,
                'key',
                self.opts)

    def finger_all(self):
        '''
        Print out all fingerprints
        '''
        matches = self.key.finger('*')
        salt.output.display_output(
                matches,
                'key',
                self.opts)

    def run(self):
        '''
        Run the logic for saltkey
        '''
        if self.opts['gen_keys']:
            salt.crypt.gen_keys(
                    self.opts['gen_keys_dir'],
                    self.opts['gen_keys'],
                    self.opts['keysize'])
            return
        if self.opts['list']:
            self.list_status(self.opts['list'])
        elif self.opts['list_all']:
            self.list_all()
        elif self.opts['print']:
            self.print_key(self.opts['print'])
        elif self.opts['print_all']:
            self.print_all()
        elif self.opts['accept']:
            self.accept(
                self.opts['accept'],
                include_rejected=self.opts['include_all']
            )
        elif self.opts['accept_all']:
            self.accept_all(include_rejected=self.opts['include_all'])
        elif self.opts['reject']:
            self.reject(
                self.opts['reject'],
                include_accepted=self.opts['include_all']
            )
        elif self.opts['reject_all']:
            self.reject_all(include_accepted=self.opts['include_all'])
        elif self.opts['delete']:
            self.delete(self.opts['delete'])
        elif self.opts['delete_all']:
            self.delete_all()
        elif self.opts['finger']:
            self.finger(self.opts['finger'])
        elif self.opts['finger_all']:
            self.finger_all()
        else:
            self.list_all()


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

    def check_minion_cache(self):
        '''
        Check the minion cache to make sure that old minion data is cleared
        '''
        m_cache = os.path.join(self.opts['cachedir'], 'minions')
        if not os.path.isdir(m_cache):
            return
        keys = self.list_keys()
        for minion in os.listdir(m_cache):
            if minion not in keys['minions']:
                shutil.rmtree(os.path.join(m_cache, minion))

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
            matches = self.all_keys()
        else:
            matches = self.list_keys()
        ret = {}
        for status, keys in matches.items():
            for key in salt.utils.isorted(keys):
                if fnmatch.fnmatch(key, match):
                    if status not in ret:
                        ret[status] = []
                    ret[status].append(key)
        return ret

    def dict_match(self, match_dict):
        '''
        Accept a dictionary of keys and return the current state of the
        specified keys
        '''
        ret = {}
        cur_keys = self.list_keys()
        for status, keys in match_dict.items():
            for key in salt.utils.isorted(keys):
                for keydir in ('minions', 'minions_pre', 'minions_rejected'):
                    if fnmatch.filter(cur_keys.get(keydir, []), key):
                        ret.setdefault(keydir, []).append(key)
        return ret

    def local_keys(self):
        '''
        Return a dict of local keys
        '''
        ret = {'local': []}
        for fn_ in salt.utils.isorted(os.listdir(self.opts['pki_dir'])):
            if fn_.endswith('.pub') or fn_.endswith('.pem'):
                path = os.path.join(self.opts['pki_dir'], fn_)
                if os.path.isfile(path):
                    ret['local'].append(fn_)
        return ret

    def list_keys(self):
        '''
        Return a dict of managed keys and what the key status are
        '''
        acc, pre, rej = self._check_minions_directories()
        ret = {}
        for dir_ in acc, pre, rej:
            ret[os.path.basename(dir_)] = []
            for fn_ in salt.utils.isorted(os.listdir(dir_)):
                if os.path.isfile(os.path.join(dir_, fn_)):
                    ret[os.path.basename(dir_)].append(fn_)
        return ret

    def all_keys(self):
        '''
        Merge managed keys with local keys
        '''
        keys = self.list_keys()
        keys.update(self.local_keys())
        return keys

    def list_status(self, match):
        '''
        Return a dict of managed keys under a named status
        '''
        acc, pre, rej = self._check_minions_directories()
        ret = {}
        if match.startswith('acc'):
            ret[os.path.basename(acc)] = []
            for fn_ in salt.utils.isorted(os.listdir(acc)):
                if os.path.isfile(os.path.join(acc, fn_)):
                    ret[os.path.basename(acc)].append(fn_)
        elif match.startswith('pre') or match.startswith('un'):
            ret[os.path.basename(pre)] = []
            for fn_ in salt.utils.isorted(os.listdir(pre)):
                if os.path.isfile(os.path.join(pre, fn_)):
                    ret[os.path.basename(pre)].append(fn_)
        elif match.startswith('rej'):
            ret[os.path.basename(rej)] = []
            for fn_ in salt.utils.isorted(os.listdir(rej)):
                if os.path.isfile(os.path.join(rej, fn_)):
                    ret[os.path.basename(rej)].append(fn_)
        elif match.startswith('all'):
            return self.all_keys()
        return ret

    def key_str(self, match):
        '''
        Return the specified public key or keys based on a glob
        '''
        ret = {}
        for status, keys in self.name_match(match).items():
            ret[status] = {}
            for key in salt.utils.isorted(keys):
                path = os.path.join(self.opts['pki_dir'], status, key)
                with salt.utils.fopen(path, 'r') as fp_:
                    ret[status][key] = fp_.read()
        return ret

    def key_str_all(self):
        '''
        Return all managed key strings
        '''
        ret = {}
        for status, keys in self.list_keys().items():
            ret[status] = {}
            for key in salt.utils.isorted(keys):
                path = os.path.join(self.opts['pki_dir'], status, key)
                with salt.utils.fopen(path, 'r') as fp_:
                    ret[status][key] = fp_.read()
        return ret

    def accept(self, match=None, match_dict=None, include_rejected=False):
        '''
        Accept public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".
        '''
        if match is not None:
            matches = self.name_match(match)
        elif match_dict is not None and isinstance(match_dict, dict):
            matches = match_dict
        else:
            matches = {}
        keydirs = ['minions_pre']
        if include_rejected:
            keydirs.append('minions_rejected')
        for keydir in keydirs:
            for key in matches.get(keydir, []):
                try:
                    shutil.move(
                            os.path.join(
                                self.opts['pki_dir'],
                                keydir,
                                key),
                            os.path.join(
                                self.opts['pki_dir'],
                                'minions',
                                key)
                            )
                    eload = {'result': True,
                             'act': 'accept',
                             'id': key}
                    self.event.fire_event(eload, tagify(prefix='key'))
                except (IOError, OSError):
                    pass
        return (
            self.name_match(match) if match is not None
            else self.dict_match(matches)
        )

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
                self.event.fire_event(eload, tagify(prefix='key'))
            except (IOError, OSError):
                pass
        return self.list_keys()

    def delete_key(self, match=None, match_dict=None):
        '''
        Delete public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".
        '''
        if match is not None:
            matches = self.name_match(match)
        elif match_dict is not None and isinstance(match_dict, dict):
            matches = match_dict
        else:
            matches = {}
        for status, keys in matches.items():
            for key in keys:
                try:
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                    eload = {'result': True,
                             'act': 'delete',
                             'id': key}
                    self.event.fire_event(eload, tagify(prefix='key'))
                except (OSError, IOError):
                    pass
        self.check_minion_cache()
        salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'])
        return (
            self.name_match(match) if match is not None
            else self.dict_match(matches)
        )

    def delete_all(self):
        '''
        Delete all keys
        '''
        for status, keys in self.list_keys().items():
            for key in keys:
                try:
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                    eload = {'result': True,
                             'act': 'delete',
                             'id': key}
                    self.event.fire_event(eload, tagify(prefix='key'))
                except (OSError, IOError):
                    pass
        self.check_minion_cache()
        salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'])
        return self.list_keys()

    def reject(self, match=None, match_dict=None, include_accepted=False):
        '''
        Reject public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".
        '''
        if match is not None:
            matches = self.name_match(match)
        elif match_dict is not None and isinstance(match_dict, dict):
            matches = match_dict
        else:
            matches = {}
        keydirs = ['minions_pre']
        if include_accepted:
            keydirs.append('minions')
        for keydir in keydirs:
            for key in matches.get(keydir, []):
                try:
                    shutil.move(
                            os.path.join(
                                self.opts['pki_dir'],
                                keydir,
                                key),
                            os.path.join(
                                self.opts['pki_dir'],
                                'minions_rejected',
                                key)
                            )
                    eload = {'result': True,
                            'act': 'reject',
                            'id': key}
                    self.event.fire_event(eload, tagify(prefix='key'))
                except (IOError, OSError):
                    pass
        self.check_minion_cache()
        salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'])
        return (
            self.name_match(match) if match is not None
            else self.dict_match(matches)
        )

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
                self.event.fire_event(eload, tagify(prefix='key'))
            except (IOError, OSError):
                pass
        self.check_minion_cache()
        salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'])
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
                if status == 'local':
                    path = os.path.join(self.opts['pki_dir'], key)
                else:
                    path = os.path.join(self.opts['pki_dir'], status, key)
                ret[status][key] = salt.utils.pem_finger(path)
        return ret

    def finger_all(self):
        '''
        Return fingerprins for all keys
        '''
        ret = {}
        for status, keys in self.list_keys().items():
            ret[status] = {}
            for key in keys:
                if status == 'local':
                    path = os.path.join(self.opts['pki_dir'], key)
                else:
                    path = os.path.join(self.opts['pki_dir'], status, key)
                ret[status][key] = salt.utils.pem_finger(path)
        return ret
