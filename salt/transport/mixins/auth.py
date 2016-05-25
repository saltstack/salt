# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
import multiprocessing
import ctypes
import logging
import os
import hashlib
import shutil
import binascii

# Import Salt Libs
import salt.crypt
import salt.payload
import salt.master
import salt.transport.frame
import salt.utils.event
import salt.ext.six as six
from salt.utils.cache import CacheCli

# Import Third Party Libs
import tornado.gen
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA


log = logging.getLogger(__name__)


# TODO: rename
class AESPubClientMixin(object):
    def _verify_master_signature(self, payload):
        if payload.get('sig') and self.opts.get('sign_pub_messages'):
            # Verify that the signature is valid
            master_pubkey_path = os.path.join(self.opts['pki_dir'], 'minion_master.pub')
            if not salt.crypt.verify_signature(master_pubkey_path, payload['load'], payload.get('sig')):
                raise salt.crypt.AuthenticationError('Message signature failed to validate.')

    @tornado.gen.coroutine
    def _decode_payload(self, payload):
        # we need to decrypt it
        log.trace('Decoding payload: {0}'.format(payload))
        if payload['enc'] == 'aes':
            self._verify_master_signature(payload)
            try:
                payload['load'] = self.auth.crypticle.loads(payload['load'])
            except salt.crypt.AuthenticationError:
                yield self.auth.authenticate()
                payload['load'] = self.auth.crypticle.loads(payload['load'])

        raise tornado.gen.Return(payload)


# TODO: rename?
class AESReqServerMixin(object):
    '''
    Mixin to house all of the master-side auth crypto
    '''

    def pre_fork(self, _):
        '''
        Pre-fork we need to create the zmq router device
        '''
        if 'aes' not in salt.master.SMaster.secrets:
            # TODO: This is still needed only for the unit tests
            # 'tcp_test.py' and 'zeromq_test.py'. Fix that. In normal
            # cases, 'aes' is already set in the secrets.
            salt.master.SMaster.secrets['aes'] = {
                'secret': multiprocessing.Array(ctypes.c_char,
                              salt.crypt.Crypticle.generate_key_string()),
                'reload': salt.crypt.Crypticle.generate_key_string
            }

    def post_fork(self, _, __):
        self.serial = salt.payload.Serial(self.opts)
        self.crypticle = salt.crypt.Crypticle(self.opts, salt.master.SMaster.secrets['aes']['secret'].value)

        # other things needed for _auth
        # Create the event manager
        self.event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'], listen=False)
        self.auto_key = salt.daemons.masterapi.AutoKey(self.opts)

        # only create a con_cache-client if the con_cache is active
        if self.opts['con_cache']:
            self.cache_cli = CacheCli(self.opts)
        else:
            self.cache_cli = False
            # Make an minion checker object
            self.ckminions = salt.utils.minions.CkMinions(self.opts)

        self.master_key = salt.crypt.MasterKeys(self.opts)

    def _encrypt_private(self, ret, dictkey, target):
        '''
        The server equivalent of ReqChannel.crypted_transfer_decode_dictentry
        '''
        # encrypt with a specific AES key
        pubfn = os.path.join(self.opts['pki_dir'],
                             'minions',
                             target)
        key = salt.crypt.Crypticle.generate_key_string()
        pcrypt = salt.crypt.Crypticle(
            self.opts,
            key)
        try:
            with salt.utils.fopen(pubfn) as f:
                pub = RSA.importKey(f.read())
        except (ValueError, IndexError, TypeError):
            return self.crypticle.dumps({})
        except IOError:
            log.error('AES key not found')
            return 'AES key not found'

        pret = {}
        cipher = PKCS1_OAEP.new(pub)
        if six.PY2:
            pret['key'] = cipher.encrypt(key)
        else:
            pret['key'] = cipher.encrypt(salt.utils.to_bytes(key))
        pret[dictkey] = pcrypt.dumps(
            ret if ret is not False else {}
        )
        return pret

    def _update_aes(self):
        '''
        Check to see if a fresh AES key is available and update the components
        of the worker
        '''
        if salt.master.SMaster.secrets['aes']['secret'].value != self.crypticle.key_string:
            self.crypticle = salt.crypt.Crypticle(self.opts, salt.master.SMaster.secrets['aes']['secret'].value)
            return True
        return False

    def _decode_payload(self, payload):
        # we need to decrypt it
        if payload['enc'] == 'aes':
            try:
                payload['load'] = self.crypticle.loads(payload['load'])
            except salt.crypt.AuthenticationError:
                if not self._update_aes():
                    raise
                payload['load'] = self.crypticle.loads(payload['load'])
        return payload

    def _auth(self, load):
        '''
        Authenticate the client, use the sent public key to encrypt the AES key
        which was generated at start up.

        This method fires an event over the master event manager. The event is
        tagged "auth" and returns a dict with information about the auth
        event

        # Verify that the key we are receiving matches the stored key
        # Store the key if it is not there
        # Make an RSA key with the pub key
        # Encrypt the AES key as an encrypted salt.payload
        # Package the return and return it
        '''

        if not salt.utils.verify.valid_id(self.opts, load['id']):
            log.info(
                'Authentication request from invalid id {id}'.format(**load)
                )
            return {'enc': 'clear',
                    'load': {'ret': False}}
        log.info('Authentication request from {id}'.format(**load))

        # 0 is default which should be 'unlimited'
        if self.opts['max_minions'] > 0:
            # use the ConCache if enabled, else use the minion utils
            if self.cache_cli:
                minions = self.cache_cli.get_cached()
            else:
                minions = self.ckminions.connected_ids()
                if len(minions) > 1000:
                    log.info('With large numbers of minions it is advised '
                             'to enable the ConCache with \'con_cache: True\' '
                             'in the masters configuration file.')

            if not len(minions) <= self.opts['max_minions']:
                # we reject new minions, minions that are already
                # connected must be allowed for the mine, highstate, etc.
                if load['id'] not in minions:
                    msg = ('Too many minions connected (max_minions={0}). '
                           'Rejecting connection from id '
                           '{1}'.format(self.opts['max_minions'],
                                        load['id']))
                    log.info(msg)
                    eload = {'result': False,
                             'act': 'full',
                             'id': load['id'],
                             'pub': load['pub']}

                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': 'full'}}

        # Check if key is configured to be auto-rejected/signed
        auto_reject = self.auto_key.check_autoreject(load['id'])
        auto_sign = self.auto_key.check_autosign(load['id'])

        pubfn = os.path.join(self.opts['pki_dir'],
                             'minions',
                             load['id'])
        pubfn_pend = os.path.join(self.opts['pki_dir'],
                                  'minions_pre',
                                  load['id'])
        pubfn_rejected = os.path.join(self.opts['pki_dir'],
                                      'minions_rejected',
                                      load['id'])
        pubfn_denied = os.path.join(self.opts['pki_dir'],
                                    'minions_denied',
                                    load['id'])
        if self.opts['open_mode']:
            # open mode is turned on, nuts to checks and overwrite whatever
            # is there
            pass
        elif os.path.isfile(pubfn_rejected):
            # The key has been rejected, don't place it in pending
            log.info('Public key rejected for {0}. Key is present in '
                     'rejection key dir.'.format(load['id']))
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        elif os.path.isfile(pubfn):
            # The key has been accepted, check it
            if salt.utils.fopen(pubfn, 'r').read().strip() != load['pub'].strip():
                log.error(
                    'Authentication attempt from {id} failed, the public '
                    'keys did not match. This may be an attempt to compromise '
                    'the Salt cluster.'.format(**load)
                )
                # put denied minion key into minions_denied
                with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                    fp_.write(load['pub'])
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return {'enc': 'clear',
                        'load': {'ret': False}}

        elif not os.path.isfile(pubfn_pend):
            # The key has not been accepted, this is a new minion
            if os.path.isdir(pubfn_pend):
                # The key path is a directory, error out
                log.info(
                    'New public key {id} is a directory'.format(**load)
                )
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return {'enc': 'clear',
                        'load': {'ret': False}}

            if auto_reject:
                key_path = pubfn_rejected
                log.info('New public key for {id} rejected via autoreject_file'
                         .format(**load))
                key_act = 'reject'
                key_result = False
            elif not auto_sign:
                key_path = pubfn_pend
                log.info('New public key for {id} placed in pending'
                         .format(**load))
                key_act = 'pend'
                key_result = True
            else:
                # The key is being automatically accepted, don't do anything
                # here and let the auto accept logic below handle it.
                key_path = None

            if key_path is not None:
                # Write the key to the appropriate location
                with salt.utils.fopen(key_path, 'w+') as fp_:
                    fp_.write(load['pub'])
                ret = {'enc': 'clear',
                       'load': {'ret': key_result}}
                eload = {'result': key_result,
                         'act': key_act,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return ret

        elif os.path.isfile(pubfn_pend):
            # This key is in the pending dir and is awaiting acceptance
            if auto_reject:
                # We don't care if the keys match, this minion is being
                # auto-rejected. Move the key file from the pending dir to the
                # rejected dir.
                try:
                    shutil.move(pubfn_pend, pubfn_rejected)
                except (IOError, OSError):
                    pass
                log.info('Pending public key for {id} rejected via '
                         'autoreject_file'.format(**load))
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                eload = {'result': False,
                         'act': 'reject',
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                return ret

            elif not auto_sign:
                # This key is in the pending dir and is not being auto-signed.
                # Check if the keys are the same and error out if this is the
                # case. Otherwise log the fact that the minion is still
                # pending.
                if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                    log.error(
                        'Authentication attempt from {id} failed, the public '
                        'key in pending did not match. This may be an '
                        'attempt to compromise the Salt cluster.'
                        .format(**load)
                    )
                    # put denied minion key into minions_denied
                    with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                        fp_.write(load['pub'])
                    eload = {'result': False,
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': False}}
                else:
                    log.info(
                        'Authentication failed from host {id}, the key is in '
                        'pending and needs to be accepted with salt-key '
                        '-a {id}'.format(**load)
                    )
                    eload = {'result': True,
                             'act': 'pend',
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': True}}
            else:
                # This key is in pending and has been configured to be
                # auto-signed. Check to see if it is the same key, and if
                # so, pass on doing anything here, and let it get automatically
                # accepted below.
                if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                    log.error(
                        'Authentication attempt from {id} failed, the public '
                        'keys in pending did not match. This may be an '
                        'attempt to compromise the Salt cluster.'
                        .format(**load)
                    )
                    # put denied minion key into minions_denied
                    with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                        fp_.write(load['pub'])
                    eload = {'result': False,
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': False}}
                else:
                    pass

        else:
            # Something happened that I have not accounted for, FAIL!
            log.warning('Unaccounted for authentication failure')
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        log.info('Authentication accepted from {id}'.format(**load))
        # only write to disk if you are adding the file, and in open mode,
        # which implies we accept any key from a minion.
        if not os.path.isfile(pubfn) and not self.opts['open_mode']:
            with salt.utils.fopen(pubfn, 'w+') as fp_:
                fp_.write(load['pub'])
        elif self.opts['open_mode']:
            disk_key = ''
            if os.path.isfile(pubfn):
                with salt.utils.fopen(pubfn, 'r') as fp_:
                    disk_key = fp_.read()
            if load['pub'] and load['pub'] != disk_key:
                log.debug('Host key change detected in open mode.')
                with salt.utils.fopen(pubfn, 'w+') as fp_:
                    fp_.write(load['pub'])

        pub = None

        # the con_cache is enabled, send the minion id to the cache
        if self.cache_cli:
            self.cache_cli.put_cache([load['id']])

        # The key payload may sometimes be corrupt when using auto-accept
        # and an empty request comes in
        try:
            with salt.utils.fopen(pubfn) as f:
                pub = RSA.importKey(f.read())
        except (ValueError, IndexError, TypeError) as err:
            log.error('Corrupt public key "{0}": {1}'.format(pubfn, err))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        cipher = PKCS1_OAEP.new(pub)
        ret = {'enc': 'pub',
               'pub_key': self.master_key.get_pub_str(),
               'publish_port': self.opts['publish_port']}

        # sign the masters pubkey (if enabled) before it is
        # send to the minion that was just authenticated
        if self.opts['master_sign_pubkey']:
            # append the pre-computed signature to the auth-reply
            if self.master_key.pubkey_signature():
                log.debug('Adding pubkey signature to auth-reply')
                log.debug(self.master_key.pubkey_signature())
                ret.update({'pub_sig': self.master_key.pubkey_signature()})
            else:
                # the master has its own signing-keypair, compute the master.pub's
                # signature and append that to the auth-reply
                log.debug("Signing master public key before sending")
                pub_sign = salt.crypt.sign_message(self.master_key.get_sign_paths()[1],
                                                   ret['pub_key'])
                ret.update({'pub_sig': binascii.b2a_base64(pub_sign)})

        mcipher = PKCS1_OAEP.new(self.master_key.key)
        if self.opts['auth_mode'] >= 2:
            if 'token' in load:
                try:
                    mtoken = mcipher.decrypt(load['token'])
                    aes = '{0}_|-{1}'.format(salt.master.SMaster.secrets['aes']['secret'].value, mtoken)
                except Exception:
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass
            else:
                aes = salt.master.SMaster.secrets['aes']['secret'].value

            ret['aes'] = cipher.encrypt(aes)
        else:
            if 'token' in load:
                try:
                    mtoken = mcipher.decrypt(load['token'])
                    ret['token'] = cipher.encrypt(mtoken)
                except Exception:
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass

            aes = salt.master.SMaster.secrets['aes']['secret'].value
            ret['aes'] = cipher.encrypt(salt.master.SMaster.secrets['aes']['secret'].value)
        # Be aggressive about the signature
        digest = hashlib.sha256(aes).hexdigest()
        ret['sig'] = salt.crypt.private_encrypt(self.master_key.key, digest)
        eload = {'result': True,
                 'act': 'accept',
                 'id': load['id'],
                 'pub': load['pub']}
        self.event.fire_event(eload, salt.utils.event.tagify(prefix='auth'))
        return ret
