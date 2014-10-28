# -*- coding: utf-8 -*-
'''
The Salt Key backend API and interface used by the CLI. The Key class can be
used to manage salt keys directly without interfacing with the CLI.
'''

# Import python libs
from __future__ import print_function
import os
import stat
import shutil
import fnmatch
import hashlib
import json
import logging

# Import salt libs
import salt.crypt
import salt.utils
import salt.utils.event
import salt.daemons.masterapi
from salt.utils.event import tagify

# Import third party libs
try:
    import msgpack
except ImportError:
    pass

log = logging.getLogger(__name__)


class KeyCLI(object):
    '''
    Manage key CLI operations
    '''
    def __init__(self, opts):
        self.opts = opts
        if self.opts['transport'] == 'zeromq':
            self.key = Key(opts)
            self.acc = 'minions'
            self.pend = 'minions_pre'
            self.rej = 'minions_rejected'
        else:
            self.key = RaetKey(opts)
            self.acc = 'accepted'
            self.pend = 'pending'
            self.rej = 'rejected'

    def list_status(self, status):
        '''
        Print out the keys under a named status

        :param str status: A string indicating which set of keys to return
        '''
        keys = self.key.list_keys()
        if status.startswith('acc'):
            salt.output.display_output(
                {'minions': keys[self.acc]},
                'key',
                self.opts
            )
        elif status.startswith(('pre', 'un')):
            salt.output.display_output(
                {'minions_pre': keys[self.pend]},
                'key',
                self.opts
            )
        elif status.startswith('rej'):
            salt.output.display_output(
                {'minions_rejected': keys[self.rej]},
                'key',
                self.opts
            )
        elif status.startswith('all'):
            self.list_all()

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

        :param str match: A string to match against. i.e. 'web*'
        :param bool include_rejected: Whether or not to accept a matched key that was formerly rejected
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
        if self.pend in matches:
            keys[self.pend] = matches[self.pend]
        if include_rejected and bool(matches.get(self.rej)):
            keys[self.rej] = matches[self.rej]
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

        :param bool include_rejected: Whether or not to accept a matched key that was formely rejected
        '''
        self.accept('*', include_rejected=include_rejected)

    def delete(self, match):
        '''
        Delete the matched keys

        :param str match: A string to match against. i.e. 'web*'
        '''
        def _print_deleted(matches, after_match):
            deleted = []
            for keydir in (self.acc, self.pend, self.rej):
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

        :param str match: A string to match against. i.e. 'web*'
        :param bool include_accepted: Whether or not to accept a matched key that was formerly accepted
        '''
        def _print_rejected(matches, after_match):
            if self.rej in after_match:
                rejected = sorted(
                    set(after_match[self.rej]).difference(
                        set(matches.get(self.rej, []))
                    )
                )
                for key in rejected:
                    print('Key for minion {0} rejected.'.format(key))

        matches = self.key.name_match(match)
        keys = {}
        if self.pend in matches:
            keys[self.pend] = matches[self.pend]
        if include_accepted and bool(matches.get(self.acc)):
            keys[self.acc] = matches[self.acc]
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

        :param bool include_accepted: Whether or not to accept a matched key that was formerly accepted
        '''
        self.reject('*', include_accepted=include_accepted)

    def print_key(self, match):
        '''
        Print out a single key

        :param str match: A string to match against. i.e. 'web*'
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

        :param str match: A string to match against. i.e. 'web*'
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

    def prep_signature(self):
        '''
        Searches for usable keys to create the
        master public-key signature
        '''
        self.privkey = None
        self.pubkey = None

        # check given pub-key
        if self.opts['pub']:
            if not os.path.isfile(self.opts['pub']):
                print('Public-key {0} does not exist'.format(self.opts['pub']))
                return
            self.pubkey = self.opts['pub']

        # default to master.pub
        else:
            mpub = self.opts['pki_dir'] + '/' + 'master.pub'
            if os.path.isfile(mpub):
                self.pubkey = mpub

        # check given priv-key
        if self.opts['priv']:
            if not os.path.isfile(self.opts['priv']):
                print('Private-key {0} does not exist'.format(self.opts['priv']))
                return
            self.privkey = self.opts['priv']

        # default to master_sign.pem
        else:
            mpriv = self.opts['pki_dir'] + '/' + 'master_sign.pem'
            if os.path.isfile(mpriv):
                self.privkey = mpriv

        if not self.privkey:
            if self.opts['auto_create']:
                print('Generating new signing key-pair {0}.* in {1}'
                      ''.format(self.opts['master_sign_key_name'],
                                self.opts['pki_dir']))
                salt.crypt.gen_keys(self.opts['pki_dir'],
                                    self.opts['master_sign_key_name'],
                                    self.opts['keysize'],
                                    self.opts.get('user'))

                self.privkey = self.opts['pki_dir'] + '/' + self.opts['master_sign_key_name'] + '.pem'
            else:
                print('No usable private-key found')
                return

        if not self.pubkey:
            print('No usable public-key found')
            return

        print('Using public-key {0}'.format(self.pubkey))
        print('Using private-key {0}'.format(self.privkey))

        if self.opts['signature_path']:
            if not os.path.isdir(self.opts['signature_path']):
                print('target directory {0} does not exist'
                      ''.format(self.opts['signature_path']))
        else:
            self.opts['signature_path'] = self.opts['pki_dir']

        sign_path = self.opts['signature_path'] + '/' + self.opts['master_pubkey_signature']

        self.key.gen_signature(self.privkey,
                               self.pubkey,
                               sign_path)

    def run(self):
        '''
        Run the logic for saltkey
        '''
        if self.opts['gen_keys']:
            self.key.gen_keys()
            return
        elif self.opts['gen_signature']:
            self.prep_signature()
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
        kind = self.opts.get('__role', '')
        if not kind:
            emsg = "Missing application kind via opts['__role']"
            log.error(emsg + '\n')
            raise ValueError(emsg)
        self.event = salt.utils.event.get_event(
                kind,
                opts['sock_dir'],
                opts['transport'],
                opts=opts,
                listen=False)

    def _check_minions_directories(self):
        '''
        Return the minion keys directory paths
        '''
        minions_accepted = os.path.join(self.opts['pki_dir'], 'minions')
        minions_pre = os.path.join(self.opts['pki_dir'], 'minions_pre')
        minions_rejected = os.path.join(self.opts['pki_dir'],
                                        'minions_rejected')
        return minions_accepted, minions_pre, minions_rejected

    def gen_keys(self):
        '''
        Generate minion RSA public keypair
        '''
        salt.crypt.gen_keys(
                self.opts['gen_keys_dir'],
                self.opts['gen_keys'],
                self.opts['keysize'])
        return

    def gen_signature(self, privkey, pubkey, sig_path):
        '''
        Generate master public-key-signature
        '''
        return salt.crypt.gen_signature(privkey,
                                        pubkey,
                                        sig_path)

    def check_minion_cache(self):
        '''
        Check the minion cache to make sure that old minion data is cleared
        '''
        m_cache = os.path.join(self.opts['cachedir'], 'minions')
        if not os.path.isdir(m_cache):
            return
        keys = self.list_keys()
        minions = []
        for key, val in keys.items():
            minions.extend(val)
        if self.opts.get('preserve_minion_cache', False):
            for minion in os.listdir(m_cache):
                if minion not in minions:
                    shutil.rmtree(os.path.join(m_cache, minion))

    def check_master(self):
        '''
        Log if the master is not running

        :rtype: bool
        :return: Whether or not the master is running
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
            try:
                for fn_ in salt.utils.isorted(os.listdir(dir_)):
                    if os.path.isfile(os.path.join(dir_, fn_)):
                        ret[os.path.basename(dir_)].append(fn_)
            except (OSError, IOError):
                # key dir kind is not created yet, just skip
                continue
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
        if self.opts.get('rotate_aes_key'):
            salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'], self.opts['sock_dir'])
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
        if self.opts.get('rotate_aes_key'):
            salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'], self.opts['sock_dir'])
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
        if self.opts.get('rotate_aes_key'):
            salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'], self.opts['sock_dir'])
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
        if self.opts.get('rotate_aes_key'):
            salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'], self.opts['sock_dir'])
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


class RaetKey(Key):
    '''
    Manage keys from the raet backend
    '''
    def __init__(self, opts):
        Key.__init__(self, opts)
        self.auto_key = salt.daemons.masterapi.AutoKey(self.opts)
        self.serial = salt.payload.Serial(self.opts)

    def _check_minions_directories(self):
        '''
        Return the minion keys directory paths
        '''
        accepted = os.path.join(self.opts['pki_dir'], 'accepted')
        pre = os.path.join(self.opts['pki_dir'], 'pending')
        rejected = os.path.join(self.opts['pki_dir'], 'rejected')
        return accepted, pre, rejected

    def check_minion_cache(self):
        '''
        Check the minion cache to make sure that old minion data is cleared
        '''
        keys = self.list_keys()
        minions = []
        for key, val in keys.items():
            minions.extend(val)

        m_cache = os.path.join(self.opts['cachedir'], 'minions')
        if os.path.isdir(m_cache):
            for minion in os.listdir(m_cache):
                if minion not in minions:
                    shutil.rmtree(os.path.join(m_cache, minion))

        road_cache = os.path.join(self.opts['cachedir'],
                                  'raet',
                                  self.opts.get('id', 'master'),
                                  'remote')
        if os.path.isdir(road_cache):
            for road in os.listdir(road_cache):
                root, ext = os.path.splitext(road)
                if ext not in ['.json', '.msgpack']:
                    continue
                prefix, sep, name = root.partition('.')
                if not name or prefix != 'estate':
                    continue
                path = os.path.join(road_cache, road)
                with salt.utils.fopen(path, 'rb') as fp_:
                    if ext == '.json':
                        data = json.load(fp_)
                    elif ext == '.msgpack':
                        data = msgpack.load(fp_)
                    if data['role'] not in minions:
                        os.remove(path)

    def gen_keys(self):
        '''
        Use libnacl to generate and safely save a private key
        '''
        import libnacl.public
        d_key = libnacl.dual.DualSecret()
        path = '{0}.key'.format(os.path.join(
            self.opts['gen_keys_dir'],
            self.opts['gen_keys']))
        d_key.save(path, 'msgpack')

    def check_master(self):
        '''
        Log if the master is not running
        NOT YET IMPLEMENTED
        '''
        return True

    def local_keys(self):
        '''
        Return a dict of local keys
        '''
        ret = {'local': []}
        fn_ = os.path.join(self.opts['pki_dir'], 'local.key')
        if os.path.isfile(fn_):
            ret['local'].append(fn_)
        return ret

    def status(self, minion_id, pub, verify):
        '''
        Accepts the minion id, device id, curve public and verify keys.
        If the key is not present, put it in pending and return "pending",
        If the key has been accepted return "accepted"
        if the key should be rejected, return "rejected"
        '''
        acc, pre, rej = self._check_minions_directories()
        acc_path = os.path.join(acc, minion_id)
        pre_path = os.path.join(pre, minion_id)
        rej_path = os.path.join(rej, minion_id)
        # open mode is turned on, force accept the key
        keydata = {
                'minion_id': minion_id,
                'pub': pub,
                'verify': verify}
        if self.opts['open_mode']:  # always accept and overwrite
            with salt.utils.fopen(acc_path, 'w+b') as fp_:
                fp_.write(self.serial.dumps(keydata))
                return 'accepted'
        if os.path.isfile(rej_path):
            return 'rejected'
        elif os.path.isfile(acc_path):
            # The minion id has been accepted, verify the key strings
            with salt.utils.fopen(acc_path, 'rb') as fp_:
                keydata = self.serial.loads(fp_.read())
            if keydata['pub'] == pub and keydata['verify'] == verify:
                return 'accepted'
            else:
                return 'rejected'
        elif os.path.isfile(pre_path):
            auto_reject = self.auto_key.check_autoreject(minion_id)
            auto_sign = self.auto_key.check_autosign(minion_id)
            with salt.utils.fopen(pre_path, 'rb') as fp_:
                keydata = self.serial.loads(fp_.read())
            if keydata['pub'] == pub and keydata['verify'] == verify:
                if auto_reject:
                    self.reject(minion_id)
                    return 'rejected'
                elif auto_sign:
                    self.accept(minion_id)
                    return 'accepted'
                return 'pending'
            else:
                return 'rejected'
        # This is a new key, evaluate auto accept/reject files and place
        # accordingly
        auto_reject = self.auto_key.check_autoreject(minion_id)
        auto_sign = self.auto_key.check_autosign(minion_id)
        if self.opts['auto_accept']:
            w_path = acc_path
            ret = 'accepted'
        elif auto_sign:
            w_path = acc_path
            ret = 'accepted'
        elif auto_reject:
            w_path = rej_path
            ret = 'rejected'
        else:
            w_path = pre_path
            ret = 'pending'
        with salt.utils.fopen(w_path, 'w+b') as fp_:
            fp_.write(self.serial.dumps(keydata))
            return ret

    def _get_key_str(self, minion_id, status):
        '''
        Return the key string in the form of:

        pub: <pub>
        verify: <verify>
        '''
        path = os.path.join(self.opts['pki_dir'], status, minion_id)
        with salt.utils.fopen(path, 'r') as fp_:
            keydata = self.serial.loads(fp_.read())
            return 'pub: {0}\nverify: {1}'.format(
                    keydata['pub'],
                    keydata['verify'])

    def _get_key_finger(self, path):
        '''
        Return a sha256 kingerprint for the key
        '''
        with salt.utils.fopen(path, 'r') as fp_:
            keydata = self.serial.loads(fp_.read())
            key = 'pub: {0}\nverify: {1}'.format(
                    keydata['pub'],
                    keydata['verify'])
        return hashlib.sha256(key).hexdigest()

    def key_str(self, match):
        '''
        Return the specified public key or keys based on a glob
        '''
        ret = {}
        for status, keys in self.name_match(match).items():
            ret[status] = {}
            for key in salt.utils.isorted(keys):
                ret[status][key] = self._get_key_str(key, status)
        return ret

    def key_str_all(self):
        '''
        Return all managed key strings
        '''
        ret = {}
        for status, keys in self.list_keys().items():
            ret[status] = {}
            for key in salt.utils.isorted(keys):
                ret[status][key] = self._get_key_str(key, status)
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
        keydirs = ['pending']
        if include_rejected:
            keydirs.append('rejected')
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
                                'accepted',
                                key)
                            )
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
        for key in keys['pending']:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            'pending',
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            'accepted',
                            key)
                        )
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
                except (OSError, IOError):
                    pass
        self.check_minion_cache()
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
                except (OSError, IOError):
                    pass
        self.check_minion_cache()
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
        keydirs = ['pending']
        if include_accepted:
            keydirs.append('accepted')
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
                                'rejected',
                                key)
                            )
                except (IOError, OSError):
                    pass
        self.check_minion_cache()
        return (
            self.name_match(match) if match is not None
            else self.dict_match(matches)
        )

    def reject_all(self):
        '''
        Reject all keys in pre
        '''
        keys = self.list_keys()
        for key in keys['pending']:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            'pending',
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            'rejected',
                            key)
                        )
            except (IOError, OSError):
                pass
        self.check_minion_cache()
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
                ret[status][key] = self._get_key_finger(path)
        return ret

    def finger_all(self):
        '''
        Return fingerprints for all keys
        '''
        ret = {}
        for status, keys in self.list_keys().items():
            ret[status] = {}
            for key in keys:
                if status == 'local':
                    path = os.path.join(self.opts['pki_dir'], key)
                else:
                    path = os.path.join(self.opts['pki_dir'], status, key)
                ret[status][key] = self._get_key_finger(path)
        return ret

    def read_all_remote(self):
        '''
        Return a dict of all remote key data
        '''
        data = {}
        for status, mids in self.list_keys().items():
            for mid in mids:
                keydata = self.read_remote(mid, status)
                if keydata:
                    keydata['acceptance'] = status
                    data[mid] = keydata

        return data

    def read_remote(self, minion_id, status='accepted'):
        '''
        Read in a remote key of status
        '''
        path = os.path.join(self.opts['pki_dir'], status, minion_id)
        if not os.path.isfile(path):
            return {}
        with salt.utils.fopen(path, 'rb') as fp_:
            return self.serial.loads(fp_.read())

    def read_local(self):
        '''
        Read in the local private keys, return an empy dict if the keys do not
        exist
        '''
        path = os.path.join(self.opts['pki_dir'], 'local.key')
        if not os.path.isfile(path):
            return {}
        with salt.utils.fopen(path, 'rb') as fp_:
            return self.serial.loads(fp_.read())

    def write_local(self, priv, sign):
        '''
        Write the private key and the signing key to a file on disk
        '''
        keydata = {'priv': priv,
                   'sign': sign}
        path = os.path.join(self.opts['pki_dir'], 'local.key')
        c_umask = os.umask(191)
        if os.path.exists(path):
            #mode = os.stat(path).st_mode
            os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
        with salt.utils.fopen(path, 'w+') as fp_:
            fp_.write(self.serial.dumps(keydata))
            os.chmod(path, stat.S_IRUSR)
        os.umask(c_umask)

    def delete_local(self):
        '''
        Delete the local private key file
        '''
        path = os.path.join(self.opts['pki_dir'], 'local.key')
        if os.path.isfile(path):
            os.remove(path)

    def delete_pki_dir(self):
        '''
        Delete the private key directory
        '''
        path = self.opts['pki_dir']
        if os.path.exists(path):
            #os.rmdir(path)
            shutil.rmtree(path)
