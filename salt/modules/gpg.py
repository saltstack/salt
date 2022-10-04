# -*- coding: utf-8 -*-
'''
Manage a GPG keychains, add keys, create keys, retrieve keys from keyservers.
Sign, encrypt and sign plus encrypt text and files.

.. versionadded:: 2015.5.0

.. note::

    The ``python-gnupg`` library and ``gpg`` binary are required to be
    installed.

'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import functools
import logging
import os
import re
import time

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError
from salt.utils.versions import LooseVersion as _LooseVersion

# Import 3rd-party libs
from salt.ext import six

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'gpg'

LETTER_TRUST_DICT = {
    'e': 'Expired',
    'q': 'Unknown',
    'n': 'Not Trusted',
    'f': 'Fully Trusted',
    'm': 'Marginally Trusted',
    'u': 'Ultimately Trusted',
    '-': 'Unknown',
}

NUM_TRUST_DICT = {
    'expired': '1',
    'unknown': '2',
    'not_trusted': '3',
    'marginally': '4',
    'fully': '5',
    'ultimately': '6',
}

INV_NUM_TRUST_DICT = {
    '1': 'Expired',
    '2': 'Unknown',
    '3': 'Not Trusted',
    '4': 'Marginally',
    '5': 'Fully Trusted',
    '6': 'Ultimately Trusted'
}

VERIFY_TRUST_LEVELS = {
    '0': 'Undefined',
    '1': 'Never',
    '2': 'Marginal',
    '3': 'Fully',
    '4': 'Ultimate'
}

GPG_1_3_1 = False
try:
    import gnupg
    HAS_GPG_BINDINGS = True
    GPG_1_3_1 = _LooseVersion(gnupg.__version__) >= _LooseVersion('1.3.1')
except ImportError:
    HAS_GPG_BINDINGS = False


def _gpg():
    '''
    Returns the path to the gpg binary
    '''
    # Get the path to the gpg binary.
    return salt.utils.path.which('gpg')


def __virtual__():
    '''
    Makes sure that python-gnupg and gpg are available.
    '''
    if not _gpg():
        return (False, 'The gpg execution module cannot be loaded: '
                'gpg binary is not in the path.')

    return __virtualname__ if HAS_GPG_BINDINGS \
        else (False, 'The gpg execution module cannot be loaded; the '
                     'gnupg python module is not installed.')


def _get_user_info(user=None):
    '''
    Wrapper for user.info Salt function
    '''
    if not user:
        # Get user Salt runnining as
        user = __salt__['config.option']('user')

    userinfo = __salt__['user.info'](user)

    if not userinfo:
        if user == 'salt':
            # Special case with `salt` user:
            # if it doesn't exist then fall back to user Salt running as
            userinfo = _get_user_info()
        else:
            raise SaltInvocationError('User {0} does not exist'.format(user))

    return userinfo


def _get_user_gnupghome(user):
    '''
    Return default GnuPG home directory path for a user
    '''
    if user == 'salt':
        gnupghome = os.path.join(__salt__['config.get']('config_dir'), 'gpgkeys')
    else:
        gnupghome = os.path.join(_get_user_info(user)['home'], '.gnupg')

    return gnupghome


def _restore_ownership(func):
    @functools.wraps(func)
    def func_wrapper(*args, **kwargs):
        '''
        Wrap gpg function calls to fix permissions
        '''
        user = kwargs.get('user')
        gnupghome = kwargs.get('gnupghome')

        if not gnupghome:
            gnupghome = _get_user_gnupghome(user)

        userinfo = _get_user_info(user)
        run_user = _get_user_info()

        if userinfo['uid'] != run_user['uid'] and os.path.exists(gnupghome):
            # Given user is different from one who runs Salt process,
            # need to fix ownership permissions for GnuPG home dir
            group = __salt__['file.gid_to_group'](run_user['gid'])
            for path in [gnupghome] + __salt__['file.find'](gnupghome):
                __salt__['file.chown'](path, run_user['name'], group)

        # Filter special kwargs
        for key in list(kwargs):
            if key.startswith('__'):
                del kwargs[key]

        ret = func(*args, **kwargs)

        if userinfo['uid'] != run_user['uid']:
            group = __salt__['file.gid_to_group'](userinfo['gid'])
            for path in [gnupghome] + __salt__['file.find'](gnupghome):
                __salt__['file.chown'](path, user, group)

        return ret

    return func_wrapper


def _create_gpg(user=None, gnupghome=None):
    '''
    Create the GPG object
    '''
    if not gnupghome:
        gnupghome = _get_user_gnupghome(user)

    if GPG_1_3_1:
        gpg = gnupg.GPG(homedir=gnupghome)  # pylint: disable=unexpected-keyword-arg
    else:
        gpg = gnupg.GPG(gnupghome=gnupghome)

    return gpg


def _list_keys(user=None, gnupghome=None, secret=False):
    '''
    Helper function for Listing keys
    '''
    gpg = _create_gpg(user, gnupghome)
    _keys = gpg.list_keys(secret)
    return _keys


def _search_keys(text, keyserver, user=None):
    '''
    Helper function for searching keys from keyserver
    '''
    gpg = _create_gpg(user)
    if keyserver:
        _keys = gpg.search_keys(text, keyserver)
    else:
        _keys = gpg.search_keys(text)
    return _keys


def search_keys(text, keyserver=None, user=None):
    '''
    Search keys from keyserver

    text
        Text to search the keyserver for, e.g. email address, keyID or fingerprint.

    keyserver
        Keyserver to use for searching for GPG keys, defaults to pgp.mit.edu.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.search_keys user@example.com

        salt '*' gpg.search_keys user@example.com keyserver=keyserver.ubuntu.com

        salt '*' gpg.search_keys user@example.com keyserver=keyserver.ubuntu.com user=username

    '''
    if GPG_1_3_1:
        raise SaltInvocationError('The search_keys function is not support with this version of python-gnupg.')
    else:
        if not keyserver:
            keyserver = 'pgp.mit.edu'

        _keys = []
        for _key in _search_keys(text, keyserver, user):
            tmp = {'keyid': _key['keyid'],
                   'uids': _key['uids']}

            expires = _key.get('expires', None)
            date = _key.get('date', None)
            length = _key.get('length', None)

            if expires:
                tmp['expires'] = time.strftime('%Y-%m-%d',
                                               time.localtime(float(_key['expires'])))
            if date:
                tmp['created'] = time.strftime('%Y-%m-%d',
                                               time.localtime(float(_key['date'])))
            if length:
                tmp['keyLength'] = _key['length']
            _keys.append(tmp)
        return _keys


def list_keys(user=None, gnupghome=None):
    '''
    List keys in GPG keychain

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.list_keys

    '''
    _keys = []
    for _key in _list_keys(user, gnupghome):
        tmp = {'keyid': _key['keyid'],
               'fingerprint': _key['fingerprint'],
               'uids': _key['uids']}

        expires = _key.get('expires', None)
        date = _key.get('date', None)
        length = _key.get('length', None)
        owner_trust = _key.get('ownertrust', None)
        trust = _key.get('trust', None)

        if expires:
            tmp['expires'] = time.strftime('%Y-%m-%d',
                                           time.localtime(float(_key['expires'])))
        if date:
            tmp['created'] = time.strftime('%Y-%m-%d',
                                           time.localtime(float(_key['date'])))
        if length:
            tmp['keyLength'] = _key['length']
        if owner_trust:
            tmp['ownerTrust'] = LETTER_TRUST_DICT[_key['ownertrust']]
        if trust:
            tmp['trust'] = LETTER_TRUST_DICT[_key['trust']]
        _keys.append(tmp)
    return _keys


def list_secret_keys(user=None, gnupghome=None):
    '''
    List secret keys in GPG keychain

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.list_secret_keys

    '''
    _keys = []
    for _key in _list_keys(user, gnupghome, secret=True):
        tmp = {'keyid': _key['keyid'],
               'fingerprint': _key['fingerprint'],
               'uids': _key['uids']}

        expires = _key.get('expires', None)
        date = _key.get('date', None)
        length = _key.get('length', None)
        owner_trust = _key.get('ownertrust', None)
        trust = _key.get('trust', None)

        if expires:
            tmp['expires'] = time.strftime('%Y-%m-%d',
                                           time.localtime(float(_key['expires'])))
        if date:
            tmp['created'] = time.strftime('%Y-%m-%d',
                                           time.localtime(float(_key['date'])))
        if length:
            tmp['keyLength'] = _key['length']
        if owner_trust:
            tmp['ownerTrust'] = LETTER_TRUST_DICT[_key['ownertrust']]
        if trust:
            tmp['trust'] = LETTER_TRUST_DICT[_key['trust']]
        _keys.append(tmp)
    return _keys


@_restore_ownership
def create_key(key_type='RSA',
               key_length=1024,
               name_real='Autogenerated Key',
               name_comment='Generated by SaltStack',
               name_email=None,
               subkey_type=None,
               subkey_length=None,
               expire_date=None,
               use_passphrase=False,
               user=None,
               gnupghome=None):
    '''
    Create a key in the GPG keychain

    .. note::

        GPG key generation requires *a lot* of entropy and randomness.
        Difficult to do over a remote connection, consider having
        another process available which is generating randomness for
        the machine.  Also especially difficult on virtual machines,
        consider the `rng-tools
        <http://www.gnu.org/software/hurd/user/tlecarrour/rng-tools.html>`_
        package.

        The create_key process takes awhile so increasing the timeout
        may be necessary, e.g. -t 15.

    key_type
        The type of the primary key to generate. It must be capable of signing.
        'RSA' or 'DSA'.

    key_length
        The length of the primary key in bits.

    name_real
        The real name of the user identity which is represented by the key.

    name_comment
        A comment to attach to the user id.

    name_email
        An email address for the user.

    subkey_type
        The type of the secondary key to generate.

    subkey_length
        The length of the secondary key in bits.

    expire_date
        The expiration date for the primary and any secondary key.
        You can specify an ISO date, A number of days/weeks/months/years,
        an epoch value, or 0 for a non-expiring key.

    use_passphrase
        Whether to use a passphrase with the signing key. Passphrase is received
        from Pillar.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt -t 15 '*' gpg.create_key

    '''
    ret = {
           'res': True,
           'fingerprint': '',
           'message': ''
          }

    create_params = {'key_type': key_type,
                     'key_length': key_length,
                     'name_real': name_real,
                     'name_comment': name_comment,
                     }

    gpg = _create_gpg(user, gnupghome)

    if name_email:
        create_params['name_email'] = name_email

    if subkey_type:
        create_params['subkey_type'] = subkey_type

    if subkey_length:
        create_params['subkey_length'] = subkey_length

    if expire_date:
        create_params['expire_date'] = expire_date

    if use_passphrase:
        gpg_passphrase = __salt__['pillar.get']('gpg_passphrase')
        if not gpg_passphrase:
            ret['res'] = False
            ret['message'] = "gpg_passphrase not available in pillar."
            return ret
        else:
            create_params['passphrase'] = gpg_passphrase

    input_data = gpg.gen_key_input(**create_params)

    key = gpg.gen_key(input_data)
    if key.fingerprint:
        ret['fingerprint'] = key.fingerprint
        ret['message'] = 'GPG key pair successfully generated.'
    else:
        ret['res'] = False
        ret['message'] = 'Unable to generate GPG key pair.'
    return ret


def delete_key(keyid=None,
               fingerprint=None,
               delete_secret=False,
               user=None,
               gnupghome=None):
    '''
    Get a key from the GPG keychain

    keyid
        The keyid of the key to be deleted.

    fingerprint
        The fingerprint of the key to be deleted.

    delete_secret
        Whether to delete a corresponding secret key prior to deleting the public key.
        Secret keys must be deleted before deleting any corresponding public keys.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.delete_key keyid=3FAD9F1E

        salt '*' gpg.delete_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.delete_key keyid=3FAD9F1E user=username

        salt '*' gpg.delete_key keyid=3FAD9F1E user=username delete_secret=True

    '''
    ret = {
           'res': True,
           'message': ''
          }

    if fingerprint and keyid:
        ret['res'] = False
        ret['message'] = 'Only specify one argument, fingerprint or keyid'
        return ret

    if not fingerprint and not keyid:
        ret['res'] = False
        ret['message'] = 'Required argument, fingerprint or keyid'
        return ret

    gpg = _create_gpg(user, gnupghome)
    key = get_key(keyid, fingerprint, user)
    if key:
        fingerprint = key['fingerprint']
        skey = get_secret_key(keyid, fingerprint, user)
        if skey and not delete_secret:
            ret['res'] = False
            ret['message'] = 'Secret key exists, delete first or pass delete_secret=True.'
            return ret
        elif skey and delete_secret and six.text_type(gpg.delete_keys(fingerprint, True)) == 'ok':
            # Delete the secret key
            ret['message'] = 'Secret key for {0} deleted\n'.format(fingerprint)

        # Delete the public key
        if six.text_type(gpg.delete_keys(fingerprint)) == 'ok':
            ret['message'] += 'Public key for {0} deleted'.format(fingerprint)
        ret['res'] = True
        return ret
    else:
        ret['res'] = False
        ret['message'] = 'Key not available in keychain.'
        return ret


def get_key(keyid=None, fingerprint=None, user=None, gnupghome=None):
    '''
    Get a key from the GPG keychain

    keyid
        The key ID (short or long) of the key to be retrieved.

    fingerprint
        The fingerprint of the key to be retrieved.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.get_key keyid=3FAD9F1E

        salt '*' gpg.get_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.get_key keyid=3FAD9F1E user=username

    '''
    tmp = {}
    for _key in _list_keys(user, gnupghome):
        if (_key['fingerprint'] == fingerprint or
                _key['keyid'] == keyid or
                _key['keyid'][8:] == keyid):
            tmp['keyid'] = _key['keyid']
            tmp['fingerprint'] = _key['fingerprint']
            tmp['uids'] = _key['uids']

            expires = _key.get('expires', None)
            date = _key.get('date', None)
            length = _key.get('length', None)
            owner_trust = _key.get('ownertrust', None)
            trust = _key.get('trust', None)

            if expires:
                tmp['expires'] = time.strftime('%Y-%m-%d',
                                               time.localtime(float(_key['expires'])))
            if date:
                tmp['created'] = time.strftime('%Y-%m-%d',
                                               time.localtime(float(_key['date'])))
            if length:
                tmp['keyLength'] = _key['length']
            if owner_trust:
                tmp['ownerTrust'] = LETTER_TRUST_DICT[_key['ownertrust']]
            if trust:
                tmp['trust'] = LETTER_TRUST_DICT[_key['trust']]
    if not tmp:
        return False
    else:
        return tmp


def get_secret_key(keyid=None, fingerprint=None, user=None, gnupghome=None):
    '''
    Get a key from the GPG keychain

    keyid
        The key ID (short or long) of the key to be retrieved.

    fingerprint
        The fingerprint of the key to be retrieved.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.get_secret_key keyid=3FAD9F1E

        salt '*' gpg.get_secret_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.get_secret_key keyid=3FAD9F1E user=username

    '''
    tmp = {}
    for _key in _list_keys(user, gnupghome, secret=True):
        if (_key['fingerprint'] == fingerprint or
                _key['keyid'] == keyid or
                _key['keyid'][8:] == keyid):
            tmp['keyid'] = _key['keyid']
            tmp['fingerprint'] = _key['fingerprint']
            tmp['uids'] = _key['uids']

            expires = _key.get('expires', None)
            date = _key.get('date', None)
            length = _key.get('length', None)
            owner_trust = _key.get('ownertrust', None)
            trust = _key.get('trust', None)

            if expires:
                tmp['expires'] = time.strftime('%Y-%m-%d',
                                               time.localtime(float(_key['expires'])))
            if date:
                tmp['created'] = time.strftime('%Y-%m-%d',
                                               time.localtime(float(_key['date'])))
            if length:
                tmp['keyLength'] = _key['length']
            if owner_trust:
                tmp['ownerTrust'] = LETTER_TRUST_DICT[_key['ownertrust']]
            if trust:
                tmp['trust'] = LETTER_TRUST_DICT[_key['trust']]
    if not tmp:
        return False
    else:
        return tmp


@_restore_ownership
def import_key(text=None,
               filename=None,
               user=None,
               gnupghome=None):
    r'''
    Import a key from text or file

    text
        The text containing to import.

    filename
        The filename containing the key to import.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.import_key text='-----BEGIN PGP PUBLIC KEY BLOCK-----\n ... -----END PGP PUBLIC KEY BLOCK-----'
        salt '*' gpg.import_key filename='/path/to/public-key-file'

    '''
    ret = {
        'res': True,
        'message': ''
        }

    gpg = _create_gpg(user, gnupghome)

    if not text and not filename:
        raise SaltInvocationError('filename or text must be passed.')

    if filename:
        try:
            with salt.utils.files.flopen(filename, 'rb') as _fp:
                text = salt.utils.stringutils.to_unicode(_fp.read())
        except IOError:
            raise SaltInvocationError('filename does not exist.')

    imported_data = gpg.import_keys(text)

    if GPG_1_3_1:
        counts = imported_data.counts
        if counts.get('imported') or counts.get('imported_rsa'):
            ret['message'] = 'Successfully imported key(s).'
        elif counts.get('unchanged'):
            ret['message'] = 'Key(s) already exist in keychain.'
        elif counts.get('not_imported'):
            ret['res'] = False
            ret['message'] = 'Unable to import key.'
        elif not counts.get('count'):
            ret['res'] = False
            ret['message'] = 'Unable to import key.'
    else:
        if imported_data.imported or imported_data.imported_rsa:
            ret['message'] = 'Successfully imported key(s).'
        elif imported_data.unchanged:
            ret['message'] = 'Key(s) already exist in keychain.'
        elif imported_data.not_imported:
            ret['res'] = False
            ret['message'] = 'Unable to import key.'
        elif not imported_data.count:
            ret['res'] = False
            ret['message'] = 'Unable to import key.'
    return ret


def export_key(keyids=None, secret=False, user=None, gnupghome=None):
    '''
    Export a key from the GPG keychain

    keyids
        The key ID(s) of the key(s) to be exported. Can be specified as a comma
        separated string or a list. Anything which GnuPG itself accepts to
        identify a key - for example, the key ID or the fingerprint could be
        used.

    secret
        Export the secret key identified by the ``keyids`` information passed.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.export_key keyids=3FAD9F1E

        salt '*' gpg.export_key keyids=3FAD9F1E secret=True

        salt '*' gpg.export_key keyids="['3FAD9F1E','3FBD8F1E']" user=username

    '''
    gpg = _create_gpg(user, gnupghome)

    if isinstance(keyids, six.string_types):
        keyids = keyids.split(',')
    return gpg.export_keys(keyids, secret)


@_restore_ownership
def receive_keys(keyserver=None, keys=None, user=None, gnupghome=None):
    '''
    Receive key(s) from keyserver and add them to keychain

    keyserver
        Keyserver to use for searching for GPG keys, defaults to pgp.mit.edu

    keys
        The keyID(s) to retrieve from the keyserver.  Can be specified as a comma
        separated string or a list.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.receive_keys keys='3FAD9F1E'

        salt '*' gpg.receive_keys keys="['3FAD9F1E','3FBD9F2E']"

        salt '*' gpg.receive_keys keys=3FAD9F1E user=username

    '''
    ret = {
           'res': True,
           'changes': {},
           'message': []
          }

    gpg = _create_gpg(user, gnupghome)

    if not keyserver:
        keyserver = 'pgp.mit.edu'

    if isinstance(keys, six.string_types):
        keys = keys.split(',')

    recv_data = gpg.recv_keys(keyserver, *keys)
    for result in recv_data.results:
        if 'ok' in result:
            if result['ok'] == '1':
                ret['message'].append('Key {0} added to keychain'.format(result['fingerprint']))
            elif result['ok'] == '0':
                ret['message'].append('Key {0} already exists in keychain'.format(result['fingerprint']))
        elif 'problem' in result:
            ret['message'].append('Unable to add key to keychain')
    return ret


def trust_key(keyid=None,
              fingerprint=None,
              trust_level=None,
              user=None):
    '''
    Set the trust level for a key in GPG keychain

    keyid
        The keyid of the key to set the trust level for.

    fingerprint
        The fingerprint of the key to set the trust level for.

    trust_level
        The trust level to set for the specified key, must be one
        of the following:
        expired, unknown, not_trusted, marginally, fully, ultimately

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.trust_key keyid='3FAD9F1E' trust_level='marginally'
        salt '*' gpg.trust_key fingerprint='53C96788253E58416D20BCD352952C84C3252192' trust_level='not_trusted'
        salt '*' gpg.trust_key keys=3FAD9F1E trust_level='ultimately' user='username'

    '''
    ret = {
           'res': True,
           'message': ''
          }

    _VALID_TRUST_LEVELS = ['expired', 'unknown',
                           'not_trusted', 'marginally',
                           'fully', 'ultimately']

    if fingerprint and keyid:
        ret['res'] = False
        ret['message'] = 'Only specify one argument, fingerprint or keyid'
        return ret

    if not fingerprint:
        if keyid:
            key = get_key(keyid, user=user)
            if key:
                if 'fingerprint' not in key:
                    ret['res'] = False
                    ret['message'] = 'Fingerprint not found for keyid {0}'.format(keyid)
                    return ret
                fingerprint = key['fingerprint']
            else:
                ret['res'] = False
                ret['message'] = 'KeyID {0} not in GPG keychain'.format(keyid)
                return ret
        else:
            ret['res'] = False
            ret['message'] = 'Required argument, fingerprint or keyid'
            return ret

    if trust_level not in _VALID_TRUST_LEVELS:
        return 'ERROR: Valid trust levels - {0}'.format(','.join(_VALID_TRUST_LEVELS))

    stdin = '{0}:{1}\n'.format(fingerprint, NUM_TRUST_DICT[trust_level])
    cmd = [_gpg(), '--import-ownertrust']
    _user = user

    if user == 'salt':
        homeDir = os.path.join(__salt__['config.get']('config_dir'), 'gpgkeys')
        cmd.extend(['--homedir', homeDir])
        _user = 'root'
    res = __salt__['cmd.run_all'](cmd,
                                  stdin=stdin,
                                  runas=_user,
                                  python_shell=False)

    if not res['retcode'] == 0:
        ret['res'] = False
        ret['message'] = res['stderr']
    else:
        if res['stderr']:
            _match = re.findall(r'\d', res['stderr'])
            if len(_match) == 2:
                ret['fingerprint'] = fingerprint
                ret['message'] = 'Changing ownership trust from {0} to {1}.'.format(
                                                                                    INV_NUM_TRUST_DICT[_match[0]],
                                                                                    INV_NUM_TRUST_DICT[_match[1]]
                                                                                  )
            else:
                ret['fingerprint'] = fingerprint
                ret['message'] = 'Setting ownership trust to {0}.'.format(INV_NUM_TRUST_DICT[_match[0]])
        else:
            ret['message'] = res['stderr']
    return ret


def sign(user=None,
         keyid=None,
         text=None,
         filename=None,
         output=None,
         use_passphrase=False,
         gnupghome=None):
    '''
    Sign message or file

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    keyid
        The keyid of the key to set the trust level for, defaults to
        first key in the secret keyring.

    text
        The text to sign.

    filename
        The filename to sign.

    output
        The filename where the signed file will be written, default is standard out.

    use_passphrase
        Whether to use a passphrase with the signing key. Passphrase is received
        from Pillar.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.sign text='Hello there.  How are you?'

        salt '*' gpg.sign filename='/path/to/important.file'

        salt '*' gpg.sign filename='/path/to/important.file' use_passphrase=True

    '''
    gpg = _create_gpg(user, gnupghome)
    if use_passphrase:
        gpg_passphrase = __salt__['pillar.get']('gpg_passphrase')
        if not gpg_passphrase:
            raise SaltInvocationError('gpg_passphrase not available in pillar.')
    else:
        gpg_passphrase = None

    # Check for at least one secret key to sign with

    gnupg_version = _LooseVersion(gnupg.__version__)
    if text:
        if gnupg_version >= _LooseVersion('1.3.1'):
            signed_data = gpg.sign(text, default_key=keyid, passphrase=gpg_passphrase)
        else:
            signed_data = gpg.sign(text, keyid=keyid, passphrase=gpg_passphrase)
    elif filename:
        with salt.utils.files.flopen(filename, 'rb') as _fp:
            if gnupg_version >= _LooseVersion('1.3.1'):
                signed_data = gpg.sign(text, default_key=keyid, passphrase=gpg_passphrase)
            else:
                signed_data = gpg.sign_file(_fp, keyid=keyid, passphrase=gpg_passphrase)
        if output:
            with salt.utils.files.flopen(output, 'wb') as fout:
                fout.write(salt.utils.stringutils.to_bytes(signed_data.data))
    else:
        raise SaltInvocationError('filename or text must be passed.')

    return signed_data.data


def verify(text=None,
           user=None,
           filename=None,
           gnupghome=None,
           signature=None):
    '''
    Verify a message or file

    text
        The text to verify.

    filename
        The filename to verify.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    signature
        Specify the filename of a detached signature.

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.verify text='Hello there.  How are you?'
        salt '*' gpg.verify filename='/path/to/important.file'
        salt '*' gpg.verify filename='/path/to/important.file' use_passphrase=True

    '''
    gpg = _create_gpg(user)

    if text:
        verified = gpg.verify(text)
    elif filename:
        if signature:
            # need to call with fopen instead of flopen due to:
            # https://bitbucket.org/vinay.sajip/python-gnupg/issues/76/verify_file-closes-passed-file-handle
            with salt.utils.files.fopen(signature, 'rb') as _fp:
                verified = gpg.verify_file(_fp, filename)
        else:
            with salt.utils.files.flopen(filename, 'rb') as _fp:
                verified = gpg.verify_file(_fp)
    else:
        raise SaltInvocationError('filename or text must be passed.')

    ret = {}
    if verified.trust_level is not None:
        ret['res'] = True
        ret['username'] = verified.username
        ret['key_id'] = verified.key_id
        ret['trust_level'] = VERIFY_TRUST_LEVELS[six.text_type(verified.trust_level)]
        ret['message'] = 'The signature is verified.'
    else:
        ret['res'] = False
        ret['message'] = 'The signature could not be verified.'
    return ret


def encrypt(user=None,
            recipients=None,
            text=None,
            filename=None,
            output=None,
            sign=None,
            use_passphrase=False,
            gnupghome=None,
            bare=False):
    '''
    Encrypt a message or file

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    recipients
        The fingerprints for those recipient whom the data is being encrypted for.

    text
        The text to encrypt.

    filename
        The filename to encrypt.

    output
        The filename where the signed file will be written, default is standard out.

    sign
        Whether to sign, in addition to encrypt, the data. ``True`` to use
        default key or fingerprint to specify a different key to sign with.

    use_passphrase
        Whether to use a passphrase with the signing key. Passphrase is received
        from Pillar.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    bare
        If ``True``, return the (armored) encrypted block as a string without
        the standard comment/res dict.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.encrypt text='Hello there.  How are you?'

        salt '*' gpg.encrypt filename='/path/to/important.file'

        salt '*' gpg.encrypt filename='/path/to/important.file' use_passphrase=True

    '''
    ret = {
        'res': True,
        'comment': ''
    }
    gpg = _create_gpg(user, gnupghome)

    if use_passphrase:
        gpg_passphrase = __salt__['pillar.get']('gpg_passphrase')
        if not gpg_passphrase:
            raise SaltInvocationError('gpg_passphrase not available in pillar.')
        gpg_passphrase = gpg_passphrase['gpg_passphrase']
    else:
        gpg_passphrase = None

    if text:
        result = gpg.encrypt(text, recipients, passphrase=gpg_passphrase)
    elif filename:
        if GPG_1_3_1:
            # This version does not allow us to encrypt using the
            # file stream # have to read in the contents and encrypt.
            with salt.utils.files.flopen(filename, 'rb') as _fp:
                _contents = salt.utils.stringutils.to_unicode(_fp.read())
            result = gpg.encrypt(_contents, recipients, passphrase=gpg_passphrase, output=output)
        else:
            # This version allows encrypting the file stream
            with salt.utils.files.flopen(filename, 'rb') as _fp:
                if output:
                    result = gpg.encrypt_file(_fp, recipients, passphrase=gpg_passphrase, output=output, sign=sign)
                else:
                    result = gpg.encrypt_file(_fp, recipients, passphrase=gpg_passphrase, sign=sign)
    else:
        raise SaltInvocationError('filename or text must be passed.')

    if result.ok:
        if not bare:
            if output:
                ret['comment'] = 'Encrypted data has been written to {0}'.format(output)
            else:
                ret['comment'] = result.data
        else:
            ret = result.data
    else:
        if not bare:
            ret['res'] = False
            ret['comment'] = '{0}.\nPlease check the salt-minion log.'.format(result.status)
        else:
            ret = False
        log.error(result.stderr)
    return ret


def decrypt(user=None,
            text=None,
            filename=None,
            output=None,
            use_passphrase=False,
            gnupghome=None,
            bare=False):
    '''
    Decrypt a message or file

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to the
        ``/etc/salt/gpgkeys``.

    text
        The encrypted text to decrypt.

    filename
        The encrypted filename to decrypt.

    output
        The filename where the decrypted data will be written, default is standard out.

    use_passphrase
        Whether to use a passphrase with the signing key. Passphrase is received
        from Pillar.

    gnupghome
        Specify the location where GPG keyring and related files are stored.

    bare
        If ``True``, return the (armored) decrypted block as a string without the
        standard comment/res dict.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.decrypt filename='/path/to/important.file.gpg'

        salt '*' gpg.decrypt filename='/path/to/important.file.gpg' use_passphrase=True

    '''
    ret = {
        'res': True,
        'comment': ''
    }
    gpg = _create_gpg(user, gnupghome)
    if use_passphrase:
        gpg_passphrase = __salt__['pillar.get']('gpg_passphrase')
        if not gpg_passphrase:
            raise SaltInvocationError('gpg_passphrase not available in pillar.')
        gpg_passphrase = gpg_passphrase['gpg_passphrase']
    else:
        gpg_passphrase = None

    if text:
        result = gpg.decrypt(text, passphrase=gpg_passphrase)
    elif filename:
        with salt.utils.files.flopen(filename, 'rb') as _fp:
            if output:
                result = gpg.decrypt_file(_fp, passphrase=gpg_passphrase, output=output)
            else:
                result = gpg.decrypt_file(_fp, passphrase=gpg_passphrase)
    else:
        raise SaltInvocationError('filename or text must be passed.')

    if result.ok:
        if not bare:
            if output:
                ret['comment'] = 'Decrypted data has been written to {0}'.format(output)
            else:
                ret['comment'] = result.data
        else:
            ret = result.data
    else:
        if not bare:
            ret['res'] = False
            ret['comment'] = '{0}.\nPlease check the salt-minion log.'.format(result.status)
        else:
            ret = False

        log.error(result.stderr)

    return ret
