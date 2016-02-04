# -*- coding: utf-8 -*-
'''
The Salt Key backend API and interface used by the CLI. The Key class can be
used to manage salt keys directly without interfacing with the CLI.
'''

# Import python libs
from __future__ import absolute_import, print_function
import os
import copy
import json
import stat
import shutil
import fnmatch
import hashlib
import logging

# Import salt libs
import salt.crypt
import salt.utils
import salt.client
import salt.exceptions
import salt.utils.event
import salt.daemons.masterapi
from salt.utils import kinds
from salt.utils.event import tagify

# Import third party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six as six
from salt.ext.six.moves import input
# pylint: enable=import-error,no-name-in-module,redefined-builtin
try:
    import msgpack
except ImportError:
    pass

log = logging.getLogger(__name__)


def get_key(opts):
    if opts['transport'] in ('zeromq', 'tcp'):
        return Key(opts)
    else:
        return RaetKey(opts)


class KeyCLI(object):
    '''
    Manage key CLI operations
    '''
    def __init__(self, opts):
        self.opts = opts
        if self.opts['transport'] in ('zeromq', 'tcp'):
            self.key = Key(opts)
        else:
            self.key = RaetKey(opts)

    def list_status(self, status):
        '''
        Print out the keys under a named status

        :param str status: A string indicating which set of keys to return
        '''
        keys = self.key.list_keys()
        if status.startswith('acc'):
            salt.output.display_output(
                {self.key.ACC: keys[self.key.ACC]},
                'key',
                self.opts
            )
        elif status.startswith(('pre', 'un')):
            salt.output.display_output(
                {self.key.PEND: keys[self.key.PEND]},
                'key',
                self.opts
            )
        elif status.startswith('rej'):
            salt.output.display_output(
                {self.key.REJ: keys[self.key.REJ]},
                'key',
                self.opts
            )
        elif status.startswith('den'):
            if self.key.DEN:
                salt.output.display_output(
                    {self.key.DEN: keys[self.key.DEN]},
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

    def accept(self, match, include_rejected=False, include_denied=False):
        '''
        Accept the keys matched

        :param str match: A string to match against. i.e. 'web*'
        :param bool include_rejected: Whether or not to accept a matched key that was formerly rejected
        :param bool include_denied: Whether or not to accept a matched key that was formerly denied
        '''
        def _print_accepted(matches, after_match):
            if self.key.ACC in after_match:
                accepted = sorted(
                    set(after_match[self.key.ACC]).difference(
                        set(matches.get(self.key.ACC, []))
                    )
                )
                for key in accepted:
                    print('Key for minion {0} accepted.'.format(key))

        matches = self.key.name_match(match)
        keys = {}
        if self.key.PEND in matches:
            keys[self.key.PEND] = matches[self.key.PEND]
        if include_rejected and bool(matches.get(self.key.REJ)):
            keys[self.key.REJ] = matches[self.key.REJ]
        if include_denied and bool(matches.get(self.key.DEN)):
            keys[self.key.DEN] = matches[self.key.DEN]
        if not keys:
            msg = (
                'The key glob \'{0}\' does not match any unaccepted{1} keys.'
                .format(match, (('', ' or denied'),
                                (' or rejected', ', rejected or denied')
                               )[include_rejected][include_denied])
            )
            print(msg)
            raise salt.exceptions.SaltSystemExit(code=1)
        if not self.opts.get('yes', False):
            print('The following keys are going to be accepted:')
            salt.output.display_output(
                    keys,
                    'key',
                    self.opts)
            try:
                veri = input('Proceed? [n/Y] ')
            except KeyboardInterrupt:
                raise SystemExit("\nExiting on CTRL-c")
            if not veri or veri.lower().startswith('y'):
                _print_accepted(
                    matches,
                    self.key.accept(
                        match_dict=keys,
                        include_rejected=include_rejected,
                        include_denied=include_denied
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
                    include_rejected=include_rejected,
                    include_denied=include_denied
                )
            )

    def accept_all(self, include_rejected=False, include_denied=False):
        '''
        Accept all keys

        :param bool include_rejected: Whether or not to accept a matched key that was formerly rejected
        :param bool include_denied: Whether or not to accept a matched key that was formerly denied
        '''
        self.accept('*', include_rejected=include_rejected, include_denied=include_denied)

    def delete(self, match):
        '''
        Delete the matched keys

        :param str match: A string to match against. i.e. 'web*'
        '''
        def _print_deleted(matches, after_match):
            deleted = []
            for keydir in (self.key.ACC, self.key.PEND, self.key.REJ):
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
                'The key glob \'{0}\' does not match any accepted, unaccepted '
                'or rejected keys.'.format(match)
            )
            raise salt.exceptions.SaltSystemExit(code=1)
        if not self.opts.get('yes', False):
            print('The following keys are going to be deleted:')
            salt.output.display_output(
                    matches,
                    'key',
                    self.opts)
            try:
                veri = input('Proceed? [N/y] ')
            except KeyboardInterrupt:
                raise SystemExit("\nExiting on CTRL-c")
            if veri.lower().startswith('y'):
                _print_deleted(
                    matches,
                    self.key.delete_key(match_dict=matches, revoke_auth=True)
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

    def reject(self, match, include_accepted=False, include_denied=False):
        '''
        Reject the matched keys

        :param str match: A string to match against. i.e. 'web*'
        :param bool include_accepted: Whether or not to reject a matched key
        that was formerly accepted
        :param bool include_denied: Whether or not to reject a matched key
        that was formerly denied
        '''
        def _print_rejected(matches, after_match):
            if self.key.REJ in after_match:
                rejected = sorted(
                    set(after_match[self.key.REJ]).difference(
                        set(matches.get(self.key.REJ, []))
                    )
                )
                for key in rejected:
                    print('Key for minion {0} rejected.'.format(key))

        matches = self.key.name_match(match)
        keys = {}
        if self.key.PEND in matches:
            keys[self.key.PEND] = matches[self.key.PEND]
        if include_accepted and bool(matches.get(self.key.ACC)):
            keys[self.key.ACC] = matches[self.key.ACC]
        if include_denied and bool(matches.get(self.key.DEN)):
            keys[self.key.DEN] = matches[self.key.DEN]
        if not keys:
            msg = 'The key glob \'{0}\' does not match any {1} keys.'.format(
                match,
                (('unaccepted', 'unaccepted or denied'),
                 ('accepted or unaccepted', 'accepted, unaccepted or denied')
                )[include_accepted][include_denied]
            )
            print(msg)
            return
        if not self.opts.get('yes', False):
            print('The following keys are going to be rejected:')
            salt.output.display_output(
                    keys,
                    'key',
                    self.opts)
            veri = input('Proceed? [n/Y] ')
            if veri.lower().startswith('n'):
                return
        _print_rejected(
            matches,
            self.key.reject(
                match_dict=matches,
                include_accepted=include_accepted,
                include_denied=include_denied
            )
        )

    def reject_all(self, include_accepted=False, include_denied=False):
        '''
        Reject all keys

        :param bool include_accepted: Whether or not to reject a matched key that was formerly accepted
        :param bool include_denied: Whether or not to reject a matched key that was formerly denied
        '''
        self.reject('*', include_accepted=include_accepted, include_denied=include_denied)

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
                include_rejected=self.opts['include_all'] or self.opts['include_rejected'],
                include_denied=self.opts['include_denied']
            )
        elif self.opts['accept_all']:
            self.accept_all(
                include_rejected=self.opts['include_all'] or self.opts['include_rejected'],
                include_denied=self.opts['include_denied']
            )
        elif self.opts['reject']:
            self.reject(
                self.opts['reject'],
                include_accepted=self.opts['include_all'] or self.opts['include_accepted'],
                include_denied=self.opts['include_denied']
            )
        elif self.opts['reject_all']:
            self.reject_all(
                include_accepted=self.opts['include_all'] or self.opts['include_accepted'],
                include_denied=self.opts['include_denied']
            )
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


class MultiKeyCLI(KeyCLI):
    '''
    Manage multiple key backends from the CLI
    '''
    def __init__(self, opts):
        opts['__multi_key'] = True
        super(MultiKeyCLI, self).__init__(opts)
        # Remove the key attribute set in KeyCLI.__init__
        delattr(self, 'key')
        zopts = copy.copy(opts)
        ropts = copy.copy(opts)
        self.keys = {}
        zopts['transport'] = 'zeromq'
        self.keys['ZMQ Keys'] = KeyCLI(zopts)
        ropts['transport'] = 'raet'
        self.keys['RAET Keys'] = KeyCLI(ropts)

    def _call_all(self, fun, *args):
        '''
        Call the given function on all backend keys
        '''
        for kback in self.keys:
            print(kback)
            getattr(self.keys[kback], fun)(*args)

    def list_status(self, status):
        self._call_all('list_status', status)

    def list_all(self):
        self._call_all('list_all')

    def accept(self, match, include_rejected=False, include_denied=False):
        self._call_all('accept', match, include_rejected, include_denied)

    def accept_all(self, include_rejected=False, include_denied=False):
        self._call_all('accept_all', include_rejected, include_denied)

    def delete(self, match):
        self._call_all('delete', match)

    def delete_all(self):
        self._call_all('delete_all')

    def reject(self, match, include_accepted=False, include_denied=False):
        self._call_all('reject', match, include_accepted, include_denied)

    def reject_all(self, include_accepted=False, include_denied=False):
        self._call_all('reject_all', include_accepted, include_denied)

    def print_key(self, match):
        self._call_all('print_key', match)

    def print_all(self):
        self._call_all('print_all')

    def finger(self, match):
        self._call_all('finger', match)

    def finger_all(self):
        self._call_all('finger_all')

    def prep_signature(self):
        self._call_all('prep_signature')


class Key(object):
    '''
    The object that encapsulates saltkey actions
    '''
    ACC = 'minions'
    PEND = 'minions_pre'
    REJ = 'minions_rejected'
    DEN = 'minions_denied'

    def __init__(self, opts):
        self.opts = opts
        kind = self.opts.get('__role', '')  # application kind
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}'.".format(kind))
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
        minions_accepted = os.path.join(self.opts['pki_dir'], self.ACC)
        minions_pre = os.path.join(self.opts['pki_dir'], self.PEND)
        minions_rejected = os.path.join(self.opts['pki_dir'],
                                        self.REJ)

        minions_denied = os.path.join(self.opts['pki_dir'],
                                        self.DEN)
        return minions_accepted, minions_pre, minions_rejected, minions_denied

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

    def check_minion_cache(self, preserve_minions=None):
        '''
        Check the minion cache to make sure that old minion data is cleared

        Optionally, pass in a list of minions which should have their caches
        preserved. To preserve all caches, set __opts__['preserve_minion_cache']
        '''
        if preserve_minions is None:
            preserve_minions = []
        m_cache = os.path.join(self.opts['cachedir'], self.ACC)
        if not os.path.isdir(m_cache):
            return
        keys = self.list_keys()
        minions = []
        for key, val in six.iteritems(keys):
            minions.extend(val)
        if not self.opts.get('preserve_minion_cache', False) or not preserve_minions:
            for minion in os.listdir(m_cache):
                if minion not in minions and minion not in preserve_minions:
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
        if ',' in match and isinstance(match, str):
            match = match.split(',')
        for status, keys in six.iteritems(matches):
            for key in salt.utils.isorted(keys):
                if isinstance(match, list):
                    for match_item in match:
                        if fnmatch.fnmatch(key, match_item):
                            if status not in ret:
                                ret[status] = []
                            ret[status].append(key)
                else:
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
        for status, keys in six.iteritems(match_dict):
            for key in salt.utils.isorted(keys):
                for keydir in (self.ACC, self.PEND, self.REJ, self.DEN):
                    if keydir and fnmatch.filter(cur_keys.get(keydir, []), key):
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

        key_dirs = []

        # We have to differentiate between RaetKey._check_minions_directories
        # and Zeromq-Keys. Raet-Keys only have three states while ZeroMQ-keys
        # havd an additional 'denied' state.
        if self.opts['transport'] in ('zeromq', 'tcp'):
            key_dirs = self._check_minions_directories()
        else:
            key_dirs = self._check_minions_directories()

        ret = {}

        for dir_ in key_dirs:
            ret[os.path.basename(dir_)] = []
            try:
                for fn_ in salt.utils.isorted(os.listdir(dir_)):
                    if not fn_.startswith('.'):
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
        acc, pre, rej, den = self._check_minions_directories()
        ret = {}
        if match.startswith('acc'):
            ret[os.path.basename(acc)] = []
            for fn_ in salt.utils.isorted(os.listdir(acc)):
                if not fn_.startswith('.'):
                    if os.path.isfile(os.path.join(acc, fn_)):
                        ret[os.path.basename(acc)].append(fn_)
        elif match.startswith('pre') or match.startswith('un'):
            ret[os.path.basename(pre)] = []
            for fn_ in salt.utils.isorted(os.listdir(pre)):
                if not fn_.startswith('.'):
                    if os.path.isfile(os.path.join(pre, fn_)):
                        ret[os.path.basename(pre)].append(fn_)
        elif match.startswith('rej'):
            ret[os.path.basename(rej)] = []
            for fn_ in salt.utils.isorted(os.listdir(rej)):
                if not fn_.startswith('.'):
                    if os.path.isfile(os.path.join(rej, fn_)):
                        ret[os.path.basename(rej)].append(fn_)
        elif match.startswith('den'):
            ret[os.path.basename(den)] = []
            for fn_ in salt.utils.isorted(os.listdir(den)):
                if not fn_.startswith('.'):
                    if os.path.isfile(os.path.join(den, fn_)):
                        ret[os.path.basename(den)].append(fn_)
        elif match.startswith('all'):
            return self.all_keys()
        return ret

    def key_str(self, match):
        '''
        Return the specified public key or keys based on a glob
        '''
        ret = {}
        for status, keys in six.iteritems(self.name_match(match)):
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
        for status, keys in six.iteritems(self.list_keys()):
            ret[status] = {}
            for key in salt.utils.isorted(keys):
                path = os.path.join(self.opts['pki_dir'], status, key)
                with salt.utils.fopen(path, 'r') as fp_:
                    ret[status][key] = fp_.read()
        return ret

    def accept(self, match=None, match_dict=None, include_rejected=False, include_denied=False):
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
        keydirs = [self.PEND]
        if include_rejected:
            keydirs.append(self.REJ)
        if include_denied:
            keydirs.append(self.DEN)
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
                                self.ACC,
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
        for key in keys[self.PEND]:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            self.PEND,
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            self.ACC,
                            key)
                        )
                eload = {'result': True,
                         'act': 'accept',
                         'id': key}
                self.event.fire_event(eload, tagify(prefix='key'))
            except (IOError, OSError):
                pass
        return self.list_keys()

    def delete_key(self,
                    match=None,
                    match_dict=None,
                    preserve_minions=False,
                    revoke_auth=False):
        '''
        Delete public keys. If "match" is passed, it is evaluated as a glob.
        Pre-gathered matches can also be passed via "match_dict".

        To preserve the master caches of minions who are matched, set preserve_minions
        '''
        if match is not None:
            matches = self.name_match(match)
        elif match_dict is not None and isinstance(match_dict, dict):
            matches = match_dict
        else:
            matches = {}
        for status, keys in six.iteritems(matches):
            for key in keys:
                try:
                    if revoke_auth:
                        if self.opts.get('rotate_aes_key') is False:
                            print('Immediate auth revocation specified but AES key rotation not allowed. '
                                     'Minion will not be disconnected until the master AES key is rotated.')
                        else:
                            try:
                                client = salt.client.get_local_client(mopts=self.opts)
                                client.cmd(key, 'saltutil.revoke_auth')
                            except salt.exceptions.SaltClientError:
                                print('Cannot contact Salt master. '
                                      'Connection for {0} will remain up until '
                                      'master AES key is rotated or auth is revoked '
                                      'with \'saltutil.revoke_auth\'.'.format(key))
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                    eload = {'result': True,
                             'act': 'delete',
                             'id': key}
                    self.event.fire_event(eload, tagify(prefix='key'))
                except (OSError, IOError):
                    pass
        if preserve_minions:
            preserve_minions_list = matches.get('minions', [])
        else:
            preserve_minions_list = []
        self.check_minion_cache(preserve_minions=preserve_minions_list)
        if self.opts.get('rotate_aes_key'):
            salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'])
        return (
            self.name_match(match) if match is not None
            else self.dict_match(matches)
        )

    def delete_den(self):
        '''
        Delete all denied keys
        '''
        keys = self.list_keys()
        for status, keys in six.iteritems(self.list_keys()):
            for key in keys[self.DEN]:
                try:
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                    eload = {'result': True,
                                 'act': 'delete',
                                 'id': key}
                    self.event.fire_event(eload, tagify(prefix='key'))
                except (OSError, IOError):
                    pass
        self.check_minion_cache()
        return self.list_keys()

    def delete_all(self):
        '''
        Delete all keys
        '''
        for status, keys in six.iteritems(self.list_keys()):
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
            salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'])
        return self.list_keys()

    def reject(self, match=None, match_dict=None, include_accepted=False, include_denied=False):
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
        keydirs = [self.PEND]
        if include_accepted:
            keydirs.append(self.ACC)
        if include_denied:
            keydirs.append(self.DEN)
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
                                self.REJ,
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
        for key in keys[self.PEND]:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            self.PEND,
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            self.REJ,
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
            salt.crypt.dropfile(self.opts['cachedir'], self.opts['user'])
        return self.list_keys()

    def finger(self, match):
        '''
        Return the fingerprint for a specified key
        '''
        matches = self.name_match(match, True)
        ret = {}
        for status, keys in six.iteritems(matches):
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
        for status, keys in six.iteritems(self.list_keys()):
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
    ACC = 'accepted'
    PEND = 'pending'
    REJ = 'rejected'
    DEN = None

    def __init__(self, opts):
        Key.__init__(self, opts)
        self.auto_key = salt.daemons.masterapi.AutoKey(self.opts)
        self.serial = salt.payload.Serial(self.opts)

    def _check_minions_directories(self):
        '''
        Return the minion keys directory paths
        '''
        accepted = os.path.join(self.opts['pki_dir'], self.ACC)
        pre = os.path.join(self.opts['pki_dir'], self.PEND)
        rejected = os.path.join(self.opts['pki_dir'], self.REJ)
        return accepted, pre, rejected

    def check_minion_cache(self, preserve_minions=False):
        '''
        Check the minion cache to make sure that old minion data is cleared
        '''
        keys = self.list_keys()
        minions = []
        for key, val in six.iteritems(keys):
            minions.extend(val)

        m_cache = os.path.join(self.opts['cachedir'], 'minions')
        if os.path.isdir(m_cache):
            for minion in os.listdir(m_cache):
                if minion not in minions:
                    shutil.rmtree(os.path.join(m_cache, minion))

        kind = self.opts.get('__role', '')  # application kind
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}'.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)
        role = self.opts.get('id', '')
        if not role:
            emsg = ("Invalid id.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        name = "{0}_{1}".format(role, kind)
        road_cache = os.path.join(self.opts['cachedir'],
                                  'raet',
                                  name,
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
        acc, pre, rej = self._check_minions_directories()  # pylint: disable=W0632
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
                return self.ACC
        if os.path.isfile(rej_path):
            log.debug("Rejection Reason: Keys already rejected.\n")
            return self.REJ
        elif os.path.isfile(acc_path):
            # The minion id has been accepted, verify the key strings
            with salt.utils.fopen(acc_path, 'rb') as fp_:
                keydata = self.serial.loads(fp_.read())
            if keydata['pub'] == pub and keydata['verify'] == verify:
                return self.ACC
            else:
                log.debug("Rejection Reason: Keys not match prior accepted.\n")
                return self.REJ
        elif os.path.isfile(pre_path):
            auto_reject = self.auto_key.check_autoreject(minion_id)
            auto_sign = self.auto_key.check_autosign(minion_id)
            with salt.utils.fopen(pre_path, 'rb') as fp_:
                keydata = self.serial.loads(fp_.read())
            if keydata['pub'] == pub and keydata['verify'] == verify:
                if auto_reject:
                    self.reject(minion_id)
                    log.debug("Rejection Reason: Auto reject pended.\n")
                    return self.REJ
                elif auto_sign:
                    self.accept(minion_id)
                    return self.ACC
                return self.PEND
            else:
                log.debug("Rejection Reason: Keys not match prior pended.\n")
                return self.REJ
        # This is a new key, evaluate auto accept/reject files and place
        # accordingly
        auto_reject = self.auto_key.check_autoreject(minion_id)
        auto_sign = self.auto_key.check_autosign(minion_id)
        if self.opts['auto_accept']:
            w_path = acc_path
            ret = self.ACC
        elif auto_sign:
            w_path = acc_path
            ret = self.ACC
        elif auto_reject:
            w_path = rej_path
            log.debug("Rejection Reason: Auto reject new.\n")
            ret = self.REJ
        else:
            w_path = pre_path
            ret = self.PEND
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
        for status, keys in six.iteritems(self.name_match(match)):
            ret[status] = {}
            for key in salt.utils.isorted(keys):
                ret[status][key] = self._get_key_str(key, status)
        return ret

    def key_str_all(self):
        '''
        Return all managed key strings
        '''
        ret = {}
        for status, keys in six.iteritems(self.list_keys()):
            ret[status] = {}
            for key in salt.utils.isorted(keys):
                ret[status][key] = self._get_key_str(key, status)
        return ret

    def accept(self, match=None, match_dict=None, include_rejected=False, include_denied=False):
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
        keydirs = [self.PEND]
        if include_rejected:
            keydirs.append(self.REJ)
        if include_denied:
            keydirs.append(self.DEN)
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
                                self.ACC,
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
        for key in keys[self.PEND]:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            self.PEND,
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            self.ACC,
                            key)
                        )
            except (IOError, OSError):
                pass
        return self.list_keys()

    def delete_key(self,
                   match=None,
                   match_dict=None,
                   preserve_minions=False,
                   revoke_auth=False):
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
        for status, keys in six.iteritems(matches):
            for key in keys:
                if revoke_auth:
                    if self.opts.get('rotate_aes_key') is False:
                        print('Immediate auth revocation specified but AES key rotation not allowed. '
                                 'Minion will not be disconnected until the master AES key is rotated.')
                    else:
                        try:
                            client = salt.client.get_local_client(mopts=self.opts)
                            client.cmd(key, 'saltutil.revoke_auth')
                        except salt.exceptions.SaltClientError:
                            print('Cannot contact Salt master. '
                                  'Connection for {0} will remain up until '
                                  'master AES key is rotated or auth is revoked '
                                  'with \'saltutil.revoke_auth\'.'.format(key))
                try:
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                except (OSError, IOError):
                    pass
        self.check_minion_cache(preserve_minions=matches.get('minions', []))
        return (
            self.name_match(match) if match is not None
            else self.dict_match(matches)
        )

    def delete_all(self):
        '''
        Delete all keys
        '''
        for status, keys in six.iteritems(self.list_keys()):
            for key in keys:
                try:
                    os.remove(os.path.join(self.opts['pki_dir'], status, key))
                except (OSError, IOError):
                    pass
        self.check_minion_cache()
        return self.list_keys()

    def reject(self, match=None, match_dict=None, include_accepted=False, include_denied=False):
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
        keydirs = [self.PEND]
        if include_accepted:
            keydirs.append(self.ACC)
        if include_denied:
            keydirs.append(self.DEN)
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
                                self.REJ,
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
        for key in keys[self.PEND]:
            try:
                shutil.move(
                        os.path.join(
                            self.opts['pki_dir'],
                            self.PEND,
                            key),
                        os.path.join(
                            self.opts['pki_dir'],
                            self.REJ,
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
        for status, keys in six.iteritems(matches):
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
        for status, keys in six.iteritems(self.list_keys()):
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
        for status, mids in six.iteritems(self.list_keys()):
            for mid in mids:
                keydata = self.read_remote(mid, status)
                if keydata:
                    keydata['acceptance'] = status
                    data[mid] = keydata

        return data

    def read_remote(self, minion_id, status=ACC):
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
            shutil.rmtree(path)
