# -*- coding: utf-8 -*-
"""
Manage a GPG keychains, add keys, create keys, retrieve keys from keyservers.
Sign, encrypt and sign plus encrypt text and files.

.. versionadded:: 2015.5.0

.. note::

    The ``python-gnupg`` library and ``gpg`` binary are required to be
    installed.

"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import functools
import logging
import os
import re
import time
import errno

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.utils.data
from salt.exceptions import SaltInvocationError, CheckError
from salt.utils.decorators import depends
from salt.utils.decorators.jinja import jinja_filter

# Import 3rd-party libs
from salt.ext import six
from salt.utils.versions import LooseVersion as _LooseVersion

try:  # pylint: disable=incompatible-py3-code
    import gnupg

    HAS_GPG_BINDINGS = True
    GPG_VERSION = '.'.join(map(str, gnupg.GPG().version))
except ImportError:
    HAS_GPG_BINDINGS = False

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "gpg"

LETTER_TRUST_DICT = {
    '-': 'Unknown',
    'e': 'Expired',
    'q': 'Unknown',
    'n': 'Not Trusted',
    'm': 'Marginally Trusted',
    'f': 'Fully Trusted',
    'u': 'Ultimately Trusted',
}

NUM_TRUST_DICT = {
    'expired': '1',
    'unknown': '2',
    'not_trusted': '3',
    'never': '3',
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
    '6': 'Ultimately Trusted',
}

VERIFY_TRUST_LEVELS = {
    '0': 'Undefined', '1': 'Never', '2': 'Marginal', '3': 'Fully', '4': 'Ultimate',
}

STR_TRUST_LEVELS = {
    'unknown': 'TRUST_UNDEFINED',
    'never': 'TRUST_NEVER',
    'marginally': 'TRUST_MARGINAL',
    'fully': 'TRUST_FULLY',
    'ultimately': 'TRUST_ULTIMATE',
}


def _gpg():
    """
    Returns the path to the gpg binary
    """
    # Get the path to the gpg binary.
    return salt.utils.path.which("gpg")


def __virtual__():
    """
    Makes sure that python-gnupg and gpg are available.
    """
    if not _gpg():
        return (
            False,
            'The gpg execution module cannot be loaded: '
            'gpg binary is not in the path.',
        )

    return (
        __virtualname__ if HAS_GPG_BINDINGS else (
            False,
            'The gpg execution module cannot be loaded; the '
            'python-gnupg library is not installed.',
        )
    )


def _get_user_info(user=None):
    """
    Wrapper for user.info Salt function
    """
    if not user:
        # Get user Salt runnining as
        user = __salt__["config.option"]("user")

    userinfo = __salt__["user.info"](user)

    if not userinfo:
        if user == "salt":
            # Special case with `salt` user:
            # if it doesn't exist then fall back to user Salt running as
            userinfo = _get_user_info()
        else:
            raise SaltInvocationError('User {} does not exist'.format(user))

    return userinfo


def _get_user_gnupghome(user):
    """
    Return default GnuPG home directory path for a user
    """
    if user == "salt":
        gnupghome = os.path.join(__salt__["config.get"]("config_dir"), "gpgkeys")
    else:
        gnupghome = os.path.join(_get_user_info(user)['home'], '.gnupg')
    return gnupghome


def _restore_ownership(func):
    '''
    Wraps gpg function calls to fix permissions of created directories or files.
    '''
    @functools.wraps(func)
    def func_wrapper(*args, **kwargs):
        """
        Wrap gpg function calls to fix permissions
        """
        user = kwargs.get("user")
        gnupghome = kwargs.get("gnupghome")

        if not gnupghome:
            gnupghome = _get_user_gnupghome(user)

        userinfo = _get_user_info(user)
        run_user = _get_user_info()

        if userinfo["uid"] != run_user["uid"] and os.path.exists(gnupghome):
            # Given user is different from one who runs Salt process,
            # need to fix ownership permissions for GnuPG home dir
            group = __salt__["file.gid_to_group"](run_user["gid"])
            for path in [gnupghome] + __salt__["file.find"](gnupghome):
                __salt__["file.chown"](path, run_user["name"], group)

        # Filter special kwargs
        for key in list(kwargs):
            if key.startswith("__"):
                del kwargs[key]

        ret = func(*args, **kwargs)

        if userinfo["uid"] != run_user["uid"]:
            group = __salt__["file.gid_to_group"](userinfo["gid"])
            for path in [gnupghome] + __salt__["file.find"](gnupghome):
                __salt__["file.chown"](path, user, group)

        return ret

    return func_wrapper


def _create_gpg(user=None, gnupghome=None):
    """
    Create the GPG object
    """
    if not gnupghome:
        gnupghome = _get_user_gnupghome(user)

    options = []
    gpg = None

    try:
        if os.geteuid() != os.stat(gnupghome).st_uid:
            # Suppress the warning about unsafe file and home directory (--homedir)
            # permissions. Required for any user or gnupghome that is not owned by
            # the user Salt is running as.
            # Since using the gnupg library means we cannot "run as" another user,
            # all gpg-calls are done as the user salt is running as.
            options.append('--no-permission-warning')
    except EnvironmentError as exc:
        if exc.errno != errno.ENOENT:
            raise
        log.error('%s: GNUPGHOME="%s" does not exist.', __name__, gnupghome)
    else:
        gpg = gnupg.GPG(gnupghome=gnupghome, options=options)
    return gpg


def _list_keys(user=None, gnupghome=None, secret=False):
    """
    Helper function for Listing keys
    """
    ret = []
    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if gpg:
        ret = gpg.list_keys(secret)
    return ret


def _search_keys(text, keyserver, user=None, gnupghome=None):
    '''
    Helper function for searching keys from keyserver
    '''
    ret = []
    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if gpg:
        if keyserver:
            ret = gpg.search_keys(text, keyserver)
        else:
            ret = gpg.search_keys(text)
    return ret


def _parse_key(gpg_key):
    '''
    Helper function to parse a key dict as returned from calling gnupg.
    '''
    res = salt.utils.data.filter_falsey({
        'keyid': gpg_key.get('keyid'),
        'fingerprint': gpg_key.get('fingerprint'),
        'uids': gpg_key.get('uids'),
        'expires': gpg_key.get('expires'),
        'created': gpg_key.get('date'),
        'keyLength': gpg_key.get('length'),
        'ownerTrust': LETTER_TRUST_DICT.get(gpg_key.get('ownertrust')),
        'trust': LETTER_TRUST_DICT.get(gpg_key.get('trust')),
    })
    # Translate expires and created
    for item in ['expires', 'created']:
        if item in res:
            res[item] = time.strftime('%Y-%m-%d', time.localtime(float(res[item])))
    return res


@depends('gnupg', version='0.3.5')
def search_keys(text, keyserver='pool.sks-keyservers.net', user=None, gnupghome=None):
    '''
    Search keys from keyserver

    :param str text: Text to search the keyserver for, e.g. email address, keyID
        or fingerprint.
    :param str keyserver: Keyserver to use for searching for GPG keys, defaults
        to pool.sks-keyservers.net.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :rtype: list
    :return: List of dicts with keydata.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.search_keys user@example.com
        salt '*' gpg.search_keys user@example.com keyserver=keyserver.ubuntu.com
        salt '*' gpg.search_keys user@example.com keyserver=keyserver.ubuntu.com user=username

    Jinja Example:

    .. code-block:: jinja

        search_keys_id:
          gpg.search_keys:
          - name: 'user@example.com'
          - keyserver: 'keyserver.ubuntu.com'
          - user: 'username'

    '''
    return [
        _parse_key(gpg_key)
        for gpg_key in _search_keys(text, keyserver, user=user, gnupghome=gnupghome)
    ]


def list_keys(user=None, gnupghome=None):
    """
    List keys in GPG keychain

    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.list_keys

    """
    return [_parse_key(gpg_key) for gpg_key in _list_keys(user=user, gnupghome=gnupghome)]


def list_secret_keys(user=None, gnupghome=None):
    """
    List secret keys in GPG keychain

    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.

    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.list_secret_keys

    """
    return [
        _parse_key(gpg_key)
        for gpg_key in _list_keys(user=user, gnupghome=gnupghome, secret=True)
    ]


@_restore_ownership
def create_key(
    key_type='RSA',
    key_length=1024,
    name_real='Autogenerated Key',
    name_comment='Generated by SaltStack',
    name_email=None,
    subkey_type=None,
    subkey_length=None,
    expire_date=None,
    passphrase=None,
    passphrase_pillar=None,
    user=None,
    gnupghome=None,
):
    '''
    Create a key in the GPG keychain

    .. note::

        GPG key generation requires *a lot* of entropy and randomness.
        Difficult to do over a remote connection, consider having
        another process available which is generating randomness for
        the machine.  Also especially difficult on virtual machines,
        it is highly recommended to install the `rng-tools
        <http://www.gnu.org/software/hurd/user/tlecarrour/rng-tools.html>`_
        package.

        The create_key process takes awhile so increasing the timeout
        may be necessary, e.g. -t 15.

    :param str key_type: The type of the primary key to generate.
        It must be capable of signing. Valid values: 'RSA' or 'DSA'.
    :param str key_length: The length of the primary key in bits.
    :param str name_real: The real name of the user identity which is represented
        by the key.
    :param str name_comment: A comment to attach to the user id.
    :param str name_email: An email address for the user.
    :param str subkey_type: The type of the secondary key to generate.
    :param str subkey_length: The length of the secondary key in bits.
    :param str expire_date: The expiration date for the primary and any secondary key.
        You can specify an ISO date, A number of days/weeks/months/years,
        an epoch value, or 0 for a non-expiring key.
    :param str passphrase: Passphrase to use with the signing key, default is None.
        Overiddes passphrase_pillar if both are given.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from,
        default is None.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt -t 15 '*' gpg.create_key

    '''
    ret = {'result': 'changeme', 'fingerprint': '', 'message': ''}

    gpg_passphrase = None
    if passphrase_pillar:
        gpg_passphrase = __salt__['pillar.get'](passphrase_pillar)
        if not gpg_passphrase:
            raise SaltInvocationError(
                'Passphrase could not be read from pillar. '
                '{} does not exist.'.format(passphrase_pillar)
            )
    gpg_passphrase = passphrase or gpg_passphrase

    if salt.utils.versions.version_cmp(GPG_VERSION, '2.1') >= 0:
        # Passphrase is required for GnuPG >= 2.1
        if not gpg_passphrase:
            raise SaltInvocationError(
                'No or empty passphrase supplied. '
                'GnuPG version >= 2.1 requires a password.'
            )

    create_params = salt.utils.data.filter_falsey({
        'key_type': key_type,
        'key_length': key_length,
        'name_real': name_real,
        'name_comment': name_comment,
        'name_email': name_email,
        'subkey_type': subkey_type,
        'subkey_length': subkey_length,
        'expire_date': expire_date,
        'passphrase': gpg_passphrase,
    })

    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret
    key = gpg.gen_key(gpg.gen_key_input(**create_params))
    ret['result'] = bool(key)
    if ret['result']:
        ret['fingerprint'] = key.fingerprint
        ret['message'] = 'GPG key pair successfully generated.'
    else:
        ret['message'] = 'Unable to generate GPG key pair.'

    if ret['result'] and not isinstance(ret['result'], bool):
        raise salt.exceptions.CheckError(
            'The value of ret["result"] was not updated properly.'
        )
    return ret


def delete_key(
    keyid=None,
    fingerprint=None,
    delete_secret=False,
    passphrase=None,
    user=None,
    gnupghome=None,
):
    '''
    Get a key from the GPG keychain

    :param str keyid: The keyid of the key to be deleted.
    :param str fingerprint: The fingerprint of the key to be deleted.
    :param bool delete_secret: Whether to delete a corresponding secret key prior
        to deleting the public key. Secret keys must be deleted before deleting
        any corresponding public keys.
    :param str passphrase: The passphrase for the secret key to delete. Required
        for GNUPG 2.1 or newer.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.delete_key keyid=3FAD9F1E

        salt '*' gpg.delete_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.delete_key keyid=3FAD9F1E user=username

        salt '*' gpg.delete_key keyid=3FAD9F1E user=username delete_secret=True passphrase='foo'

    '''
    ret = {'result': 'changeme', 'message': []}

    if not salt.utils.data.exactly_one((keyid, fingerprint)):
        raise SaltInvocationError(
            'Exactly one of either keyid or fingerprint must be specified.'
        )

    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret

    get_key_kwargs = salt.utils.data.filter_falsey({
        'keyid': keyid,
        'fingerprint': fingerprint,
        'user': user,
        'gnupghome': gnupghome,
    })
    key = get_key(**get_key_kwargs)
    if key:
        fingerprint = key['fingerprint']
        skey = get_secret_key(
            keyid=keyid, fingerprint=fingerprint, user=user, gnupghome=gnupghome
        )
        if skey:
            if delete_secret:
                res = six.text_type(
                    gpg.delete_keys(fingerprint, secret=True, passphrase=passphrase)
                )
                if res == 'ok':
                    ret['message'].append('Secret key {} deleted.'.format(fingerprint))
                else:
                    ret['message'].append(
                        'Failed to delete secret key {}: {}\n'
                        ''.format(fingerprint, res)
                    )
            else:
                ret['result'] = False
                ret['message'] = 'Secret key exists, delete first or pass delete_secret=True.'
                return ret
        # Delete the public key
        res = six.text_type(gpg.delete_keys(fingerprint))
        if res == 'ok':
            ret['result'] = True
            ret['message'].append('Public key {} deleted'.format(fingerprint))
        else:
            ret['result'] = False
            ret['message'].append(
                'Failed to delete public key {}: {}'.format(fingerprint, res)
            )
    else:
        ret['result'] = False
        ret['message'].append('Key not available in keychain.')

    if ret['result'] and not isinstance(ret['result'], bool):
        raise salt.exceptions.CheckError(
            'The value of ret["result"] was not updated properly.'
        )
    ret['message'] = '\n'.join(ret['message'])
    return ret


def get_key(keyid=None, fingerprint=None, user=None, gnupghome=None):
    """
    Get a key from the GPG keychain

    :param str keyid: The key ID (short or long) of the key to be retrieved.
    :param str fingerprint: The fingerprint of the key to be retrieved.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.get_key keyid=3FAD9F1E

        salt '*' gpg.get_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.get_key keyid=3FAD9F1E user=username

    """
    return next(
        iter([
            _parse_key(gpg_key)
            for gpg_key in _list_keys(user=user, gnupghome=gnupghome)
            if gpg_key['fingerprint'] == fingerprint or gpg_key['keyid'] == keyid
            or gpg_key['keyid'][8:] == keyid
        ]),
        False,
    )


def get_secret_key(keyid=None, fingerprint=None, user=None, gnupghome=None):
    """
    Get a key from the GPG keychain

    :param str keyid: The key ID (short or long) of the key to be retrieved.
    :param str fingerprint: The fingerprint of the key to be retrieved.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.get_secret_key keyid=3FAD9F1E

        salt '*' gpg.get_secret_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.get_secret_key keyid=3FAD9F1E user=username

    """
    return next(
        iter([
            _parse_key(gpg_key)
            for gpg_key in _list_keys(user=user, gnupghome=gnupghome, secret=True)
            if gpg_key['fingerprint'] == fingerprint or gpg_key['keyid'] == keyid
            or gpg_key['keyid'][8:] == keyid
        ]),
        False,
    )


@_restore_ownership
def import_key(text=None, filename=None, user=None, gnupghome=None):
    r'''
    Import a key from text or file

    :param str text: The text containing to import.
    :param str filename: The filename containing the key to import.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.import_key text='-----BEGIN PGP PUBLIC KEY BLOCK-----\n ... -----END PGP PUBLIC KEY BLOCK-----'
        salt '*' gpg.import_key filename='/path/to/public-key-file'

    '''
    ret = {'result': 'changeme', 'message': 'Unable to import GPG key.'}

    if not salt.utils.data.exactly_one((text, filename)):
        raise SaltInvocationError(
            'Exactly one of either filename or text must be specified.'
        )

    if filename:
        try:
            with salt.utils.files.flopen(filename, "rb") as _fp:
                text = salt.utils.stringutils.to_unicode(_fp.read())
        except IOError:
            raise SaltInvocationError('filename "{}" does not exist.'.format(filename))

    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret

    res = gpg.import_keys(text)
    if res.imported or res.imported_rsa:
        ret['result'] = True
        ret['message'] = 'Successfully imported key(s).'
        ret['fingerprints'] = res.fingerprints
    elif res.unchanged:
        ret['result'] = True
        ret['message'] = 'Key(s) already exist in keychain.'
    elif res.not_imported or not res.count:
        ret['result'] = False
        ret['message'] = 'Unable to import key'
        if res.results:
            ret['message'] += ': {}'.format(res.results[-1]['text'])
        log.error(res.stderr)
    else:
        ret['result'] = False
        ret['message'] = 'Unexpected result from gnupg, check salt minion log for details.'
        log.error(res.stderr)
    if ret['result'] and not isinstance(ret['result'], bool):
        raise salt.exceptions.CheckError(
            'The value of ret["result"] was not updated properly.'
        )
    return ret


def export_key(keyids=None, secret=False, user=None, gnupghome=None, passphrase=None):
    '''
    Export a key from the GPG keychain

    :param keyids: The key ID(s) of the key(s) to be exported. Can be specified
        as a comma-separated string or a list. Anything which GnuPG itself accepts
        to identify a key - for example, the key ID or the fingerprint could be
        used.
    :type keyids: str or list
    :param str secret: Export the secret key identified by the ``keyids`` information
        passed.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param str passphrase: Specify the passphrase to protect the secret key with.
        This is required for GnuPG >= 2.1.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.export_key keyids=3FAD9F1E
        salt '*' gpg.export_key keyids=3FAD9F1E secret=True
        salt '*' gpg.export_key keyids="['3FAD9F1E','3FBD8F1E']" user=username

    '''
    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    ret = None
    if gpg:
        if isinstance(keyids, six.string_types):
            keyids = keyids.split(',')
        ret = gpg.export_keys(keyids, secret=secret, passphrase=passphrase)
    return ret


@_restore_ownership
def receive_keys(keyserver=None, keys=None, user=None, gnupghome=None):
    """
    Receive key(s) from keyserver and add them to keychain

    :param str keyserver: Keyserver to use for searching for GPG keys, defaults
        to pool.sks-keyservers.net
    :param keys: The keyID(s) to retrieve from the keyserver.
        Can be specified as a comma-separated string or a list.
    :type keys: str or list
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.receive_keys keys='3FAD9F1E'
        salt '*' gpg.receive_keys keys="['3FAD9F1E','3FBD9F2E']"
        salt '*' gpg.receive_keys keys=3FAD9F1E user=username

    """
    ret = {'result': 'changeme', 'message': []}

    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret
    if not keyserver:
        keyserver = 'pool.sks-keyservers.net'

    if isinstance(keys, six.string_types):
        keys = keys.split(',')
    recv_data = gpg.recv_keys(keyserver, *keys)
    if recv_data.results:
        for result in recv_data.results:
            if 'ok' in result:
                if result['ok'] == '1':
                    ret['result'] = True
                    ret['message'].append(
                        'Key {} added to keychain'.format(result['fingerprint'])
                    )
                elif result['ok'] == '0':
                    ret['result'] = True
                    ret['message'].append(
                        'Key {} already exists in keychain'.format(result['fingerprint'])
                    )
            elif 'problem' in result:
                ret['result'] = False
                ret['message'].append('Unable to receive key: {}'.format(result['text']))
    elif not bool(recv_data):
        ret['result'] = False
        ret['message'].append(
            'Something unexpected went wrong: {}'.format(recv_data.stderr)
        )
    else:
        ret['result'] = False
        ret['message'].append('No results were returned. No reason given as to why.')

    if ret['result'] and not isinstance(ret['result'], bool):
        raise CheckError('Internal error, result not properly specified.')
    ret['message'] = '\n'.join(ret['message'])
    return ret


def trust_key(keyid=None, fingerprint=None, trust_level=None, user=None, gnupghome=None):
    '''
    Set the trust level for a key in GPG keychain

    :param str keyid: The keyid of the key to set the trust level for.
    :param str fingerprint: The fingerprint of the key to set the trust level for.
        Either `fingerprint` or `keyid` must be provided.
    :param str trust_level: The trust level to set for the specified key, must
        be one of the following:
        expired, unknown, not_trusted, marginally, fully, ultimately
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.trust_key '3FAD9F1E' trust_level='marginally'
        salt '*' gpg.trust_key '53C96788253E58416D20BCD352952C84C3252192' trust_level='not_trusted'
        salt '*' gpg.trust_key '3FAD9F1E' trust_level='ultimately' user='username'

    '''
    ret = {'result': 'changeme', 'message': ''}
    if not salt.utils.data.exactly_one((keyid, fingerprint)):
        raise SaltInvocationError(
            'Exactly one of either keyid or fingerprint must be provided.'
        )

    if trust_level not in NUM_TRUST_DICT:
        raise SaltInvocationError(
            'Invalid trust level "{}" specified. Valid trust levels are: {}'
            ''.format(trust_level, ','.join(NUM_TRUST_DICT.keys()))
        )

    if keyid:
        gpg_key = get_key(keyid=keyid, user=user, gnupghome=gnupghome)
    else:
        gpg_key = get_key(fingerprint=fingerprint, user=user, gnupghome=gnupghome)

    if not gpg_key:
        ret['result'] = False
        ret['message'] = 'KeyID or fingerprint {} not in GPG keychain'.format(
            keyid or fingerprint
        )
        return ret
    if 'fingerprint' not in gpg_key:
        ret['result'] = False
        ret['message'] = 'Fingerprint not found for KeyID {}'.format(keyid)
        return ret
    fingerprint = gpg_key['fingerprint']

    if salt.utils.versions.version_cmp(gnupg.__version__, '0.4.2') < 0:
        # Use the gpg cli
        homedir = gnupghome if gnupghome else _get_user_gnupghome(user)
        cmd = [_gpg(), '--import-ownertrust', '--homedir', homedir]
        run_kwargs = salt.utils.data.filter_falsey({
            'runas': None if user == 'salt' else user,
        })
        ownertrust_string = '{}:{}\n'.format(fingerprint, NUM_TRUST_DICT[trust_level])

        res = __salt__['cmd.run_all'](
            cmd, stdin=ownertrust_string, python_shell=False, **run_kwargs
        )

        if not res['retcode'] == 0:
            ret['result'] = False
            ret['message'] = res['stderr']
        elif res['stderr']:
            ret['result'] = True
            _match = re.findall(r'\d', res['stderr'])
            if len(_match) == 2:
                ret['message'] = 'Changing ownership trust from {} to {}.'.format(
                    INV_NUM_TRUST_DICT[_match[0]], INV_NUM_TRUST_DICT[_match[1]]
                )
            else:
                ret['message'] = 'Setting ownership trust to {}.'.format(
                    INV_NUM_TRUST_DICT[_match[0]]
                )
    else:
        # Use gnupg library, which actually does exactly the same as above :/
        gpg = _create_gpg(user=user, gnupghome=gnupghome)
        if gpg:
            res = gpg.trust_keys(fingerprint, STR_TRUST_LEVELS[trust_level])
            ret['result'] = res.status == 'ok'
            if not ret['result']:
                ret['message'] = res.problem_reason
            else:
                ret['message'] = 'Setting ownership trust to {}'.format(
                    INV_NUM_TRUST_DICT[NUM_TRUST_DICT[trust_level]]
                )
        else:
            ret['result'] = False
            ret['message'] = 'Error initializing GPG object.'
    if ret['result'] and not isinstance(ret['result'], bool):
        raise CheckError('Internal error, result not properly specified.')
    return ret


@depends('gnupg', version='0.3.7')
def sign(
    user=None,
    keyid=None,
    text=None,
    filename=None,
    detach=False,
    output=None,
    passphrase_pillar=None,
    passphrase=None,
    gnupghome=None,
    bare=False,
):
    '''
    Sign message or file.

    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str keyid: The keyid of the secret key to use to sign the data, defaults
        to first key in the secret keyring.
    :param str text: The text to sign.
    :param str filename: The name of the file to sign.
    :param bool detach: Only return or output (see below) the signature. Default ``False``.
    :param str output: The name of the file where the signed data and signature
        will be written to. Default is to return it in the `message`-key.
    :param str passphrase: Passphrase to use with the signing key, default is None.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from.
        Default ``None``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param bool bare: If ``True``, return the signed data and signature as a string
        without the standard message/result dict. Default ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.sign text='Hello there.  How are you?'
        salt '*' gpg.sign filename='/path/to/important.file'
        salt '*' gpg.sign filename='/path/to/important.file' passphrase='werybigSecret!'

    Jinja Example:

    .. code-block:: jinja

        sign_something:
          gpg.sign:
          - filename: '/path/to/important.file'
          - passphrase_pillar: gpg_passphrase
    '''
    ret = {'result': 'changeme', 'message': ''}
    if not salt.utils.data.exactly_one((text, filename)):
        raise SaltInvocationError(
            'Exactly one of either text or filename must be provided.'
        )
    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret

    gpg_passphrase = None
    if passphrase_pillar:
        gpg_passphrase = __salt__['pillar.get'](passphrase_pillar)
        if not gpg_passphrase:
            raise SaltInvocationError(
                'Passphrase could not be read from pillar. '
                '{} does not exist or is empty.'.format(passphrase_pillar)
            )
    gpg_passphrase = passphrase or gpg_passphrase

    if keyid is None:
        secret_keys = list_secret_keys(user=user, gnupghome=gnupghome)
        if not secret_keys:
            raise SaltInvocationError('No keyid provided and no secret keys found.')
        keyid = secret_keys[0]['keyid']

    call_kwargs = salt.utils.data.filter_falsey({
        'keyid': keyid,
        'passphrase': gpg_passphrase,
        'detach': detach,
        'output':
            output
            if salt.utils.versions.version_cmp(gnupg.__version__, '0.3.7') >= 0 else None,
    })
    if salt.utils.versions.version_cmp(gnupg.__version__, '0.4.1') >= 0:
        # Avoid getting a popup asking for a password
        call_kwargs.update({'extra_args': ['--pinentry-mode', 'loopback']})
    if text:
        res = gpg.sign(text, **call_kwargs)
    else:
        with salt.utils.files.flopen(filename, 'rb') as _fp:
            res = gpg.sign_file(_fp, **call_kwargs)
    if isinstance(res, gnupg.Sign):
        if res.status:
            ret['result'] = True
            if (salt.utils.versions.version_cmp(gnupg.__version__, '0.3.7') < 0 and output):
                with salt.utils.files.flopen(output, 'wb') as fout:
                    fout.write(res.data)
            if output:
                ret['message'] = '{} has been written to {}'.format(
                    'Signature' if detach else 'Signed data', output
                )
            else:
                ret['message'] = res.data
        else:
            ret['result'] = False
            ret['message'] = 'Failed to sign data. Check minion log for details.'
            log.error(res.stderr)
    else:
        ret['result'] = False
        ret['message'] = 'Please check the salt-minion log for errors.'
    if ret['result'] and not isinstance(ret['result'], bool):
        raise CheckError('Internal error, result not properly specified.')
    if bare:
        ret = res.data if ret['result'] else None
    return ret


def verify(
    text=None, user=None, filename=None, gnupghome=None, signature=None, trustmodel=None
):
    '''
    Verify a message or file.

    :param str text: The text to verify.
    :param str filename: The filename to verify.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param str signature: Provide the signature itself as GPG armored text, or
        the URL filename of the signature (this can be anything accepted by
        cp.cache_file including the local filesystem).
    :param str trustmodel: Explicitly define the used trust model. One of:
          - pgp
          - classic
          - tofu
          - tofu+pgp
          - direct
          - always
          - auto

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.verify text='Hello there.  How are you?'
        salt '*' gpg.verify filename='/path/to/important.file'
        salt '*' gpg.verify filename='/path/to/important.file' trustmodel=direct

    '''
    ret = {'result': 'changeme', 'message': ''}
    if not salt.utils.data.exactly_one((text, filename)):
        raise SaltInvocationError(
            'Exactly one of either text or filename must be provided.'
        )

    trustmodels = ('pgp', 'classic', 'tofu', 'tofu+pgp', 'direct', 'always', 'auto')

    if trustmodel and trustmodel not in trustmodels:
        raise SaltInvocationError('Invalid trustmodel provided: {}.'.format(trustmodel))

    extra_args = []
    cached_signature = None

    if trustmodel:
        extra_args.extend(["--trust-model", trustmodel])

    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret
    if signature:
        if signature.startswith('-----BEGIN PGP SIGNATURE-----'):
            try:
                cached_signature = salt.utils.files.mkstemp()
                with salt.utils.files.flopen(cached_signature, 'w') as _fp:
                    _fp.write(signature)
            except IOError as exc:
                ret['result'] = False
                ret['message'] = 'Failed to store signature in tempfile: {}.'.format(
                    exc.__str__()
                )
        else:
            cached_signature = __salt__['cp.cache_file'](signature)
            if not cached_signature:
                ret['result'] = False
                ret['message'] = 'Failed to cache source locally.'
    if not ret['result']:
        salt.utils.files.safe_rm(cached_signature)
        return ret
    if text:
        if signature:
            verified = gpg.verify_data(
                cached_signature,
                salt.utils.stringutils.to_bytes(text),
                extra_args=extra_args,
            )
        else:
            verified = gpg.verify(text, extra_args=extra_args)
    else:
        if signature:
            with salt.utils.files.fopen(cached_signature, 'rb') as _fp:
                verified = gpg.verify_file(_fp, filename, extra_args=extra_args)
        else:
            with salt.utils.files.fopen(filename, 'rb') as _fp:
                verified = gpg.verify_file(_fp, extra_args=extra_args)
    if cached_signature:
        salt.utils.files.safe_rm(cached_signature)

    if verified and verified.trust_level is not None:
        ret['result'] = True
        ret['username'] = verified.username
        ret['key_id'] = verified.key_id
        ret['trust_level'] = VERIFY_TRUST_LEVELS[six.text_type(verified.trust_level)]
        ret['message'] = 'The signature is verified.'
    else:
        ret['result'] = False
        ret['message'] = 'The signature could not be verified.'
    if ret['result'] and not isinstance(ret['result'], bool):
        raise CheckError('Internal error, result not properly specified.')
    return ret


def encrypt(
    user=None,
    recipients=None,
    symmetric=None,
    text=None,
    filename=None,
    output=None,
    sign=None,
    passphrase=None,
    passphrase_pillar=None,
    gnupghome=None,
    bare=False,
    armor=True,
):
    '''
    Encrypt a message or file.

    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str recipients: The fingerprints for those recipients whom the data is
        being encrypted for.
    :param symmetric: If ``True`` or equal to some string, will use symmetric encryption.
        The value passed will be interpreted to be the cipher to use. Default: ``None``.
        When ``True``, the default cipher will be set to AES256.
        When used, a passphrase will need to be supplied.
    :type symmetric: bool or str
    :param str text: The text to encrypt.
    :param str filename: The name of the file whose contents are to be encrypted.
    :param str output: The name of the file where the encrypted data will be written
        to. Only works when specifying a ``filename`` to encrypt.
        Default is to return it under ``message``-key in resulting dict.
    :param sign: Whether to sign, in addition to encrypt, the data. Set to ``True``
        to use default key or provide the fingerprint of a different key to sign with.
    :type sign: bool or str
    :param str passphrase: Passphrase to use with the signing key or symmetric encryption.
        default is None.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from, default
        is None.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param bool bare: If ``True``, return the armored encrypted block as a string
        without the standard message/result dict.
    :param bool armor: Whether to use ASCII armor. If ``False``, binary data is produced.
        Default ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.encrypt text='Hello there.  How are you?'
        salt '*' gpg.encrypt filename='/path/to/important.file'
        salt '*' gpg.encrypt filename='/path/to/important.file' passphrase='werybigSecret!'

    Jinja Example:

    .. code-block:: jinja

        encrypt_something:
          gpg.encrypt:
          - filename: '/path/to/important.file'
          - passphrase: {{ salt['pillar.get']('gpg_passphrase', 'werybigSecret!') }}

    '''
    ret = {'result': 'changeme', 'message': ''}
    if not salt.utils.data.exactly_one((text, filename)):
        raise SaltInvocationError(
            'Exactly one of either text or filename must be provided.'
        )
    gpg_passphrase = None
    if passphrase_pillar:
        gpg_passphrase = __salt__['pillar.get'](passphrase_pillar)
        if not gpg_passphrase:
            raise SaltInvocationError(
                'Passphrase could not be read from pillar. '
                '{} does not exist or is empty.'.format(passphrase_pillar)
            )
    gpg_passphrase = passphrase or gpg_passphrase
    if symmetric and not gpg_passphrase:
        raise SaltInvocationError(
            'Symmetric encryption specified, but no passphrase supplied.'
        )

    encrypt_kwargs = salt.utils.data.filter_falsey({
        'passphrase': gpg_passphrase,
        'output': output,
        'symmetric': 'AES256' if symmetric and isinstance(symmetric, bool) else symmetric,
        'sign': sign,
        'armor': armor,
    })

    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret
    res = None
    if text:
        res = gpg.encrypt(text, recipients, **encrypt_kwargs)
    else:
        with salt.utils.files.flopen(filename, 'rb') as _fp:
            res = gpg.encrypt_file(_fp, recipients, **encrypt_kwargs)

    if isinstance(res, gnupg.Crypt):
        if res.ok:
            ret['result'] = True
            if output:
                ret['message'] = 'Encrypted data has been written to {}'.format(output)
            else:
                ret['message'] = res.data
        elif res.status:
            ret['result'] = False
            ret['message'] = '{}.\nPlease check the salt-minion log.'.format(res.status)
            log.error(res.stderr)
    else:
        ret['result'] = False
        ret['message'] = 'Please check the salt-minion log for errors.'
    if ret['result'] and not isinstance(ret['result'], bool):
        raise CheckError('Internal error, result not properly specified.')
    if bare:
        ret = ret['message'] if ret['result'] else None
    return ret


def decrypt(
    user=None,
    text=None,
    filename=None,
    output=None,
    passphrase=None,
    passphrase_pillar=None,
    gnupghome=None,
    bare=False,
    always_trust=False,
):
    r'''
    Decrypt a message or file

    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str text: The encrypted text to decrypt.
    :param str filename: The encrypted filename to decrypt.
    :param str output: The filename where the decrypted data will be written, default
        returns data under ``message``-key. Only works when specifying a ``filename`` to decrypt.
    :param str passphrase: Passphrase to use when accessing the keyrings or when
        message was encrypted with symmetric encryption.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from, default
        is None.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param bool bare: If ``True``, return the (armored) decrypted block as a string
        without the standard message/result dict.
    :param bool always_trust: Skip key validation and assume that used keys are
        always fully trusted. Default: ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.decrypt filename='/path/to/important.file.gpg'
        salt '*' gpg.decrypt filename='/path/to/important.file.gpg' passphrase='werybigSecret!'
        salt '*' gpg.decrypt filename='/path/to/important.file.gpg' passphrase='werybigSecret!' \
        output='/path/to/decrypted.file'
        salt '*' gpg.decrypt filename='/path/to/important.file.gpg' passphrase_pillar=gpg_passphrase

    Jinja Example:

    ... code-block:: jinja

        decrypt_file:
          gpg.decrypt:
          - filename: '/path/to/important.file.gpg'
          - passphrase: {{ salt['pillar.get']('gpg_passphrase', 'werybigSecret!') }}

        decrypt_file:
          gpg.decrypt:
          - filename: '/path/to/important.file.gpg'
          - passphrase_pillar: gpg_passphrase
          - output: '/path/to/decrypted.file'

    '''
    ret = {'result': 'changeme', 'message': ''}
    if not salt.utils.data.exactly_one((text, filename)):
        raise SaltInvocationError(
            'Exactly one of either text or filename must be provided.'
        )
    gpg_passphrase = None
    if passphrase_pillar:
        gpg_passphrase = __salt__['pillar.get'](passphrase_pillar)
        if not gpg_passphrase:
            raise SaltInvocationError(
                'Passphrase could not be read from pillar. '
                '{} does not exist or is empty.'.format(passphrase_pillar)
            )
    gpg_passphrase = passphrase or gpg_passphrase

    decrypt_kwargs = salt.utils.data.filter_falsey({
        'always_trust': always_trust,
        'output': output if filename else None,
        'passphrase': gpg_passphrase,
    })

    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if not gpg:
        ret['result'] = False
        ret['message'] = 'Unable to initialize GPG.'
        return ret
    res = None
    if text:
        res = gpg.decrypt(text, **decrypt_kwargs)
    else:
        with salt.utils.files.flopen(filename, 'rb') as _fp:
            res = gpg.decrypt_file(_fp, **decrypt_kwargs)

    if isinstance(res, gnupg.Crypt):
        ret['result'] = res.ok
        if res.ok:
            for item in ['username',
                         'key_id',
                         'signature_id',
                         'fingerprint',
                         'trust_level',
                         'trust_text', ]:
                ret[item] = getattr(res, item, None)
            ret = salt.utils.data.filter_falsey(ret)
            if output:
                ret['message'] = 'Decrypted data has been written to {}'.format(output)
                if not filename:
                    # Write the output ourselves
                    try:
                        with salt.utils.files.flopen(output, 'wb') as _fp:
                            _fp.write(res.data)
                    except IOError as exc:
                        ret['result'] = False
                        ret['message'] = 'Error writing decrypted data to file "{}".'.format(
                            output
                        )
            else:
                ret['message'] = salt.utils.stringutils.to_unicode(res.data)
        elif res.status:
            ret['message'] = '{}.\nPlease check the salt-minion log for further details.'.format(
                res.status
            )
            log.error(res.stderr)
    else:
        ret['result'] = False
        ret['message'] = 'Call to gpg.decrypt did not return properly'

    if ret['result'] and not isinstance(ret['result'], bool):
        raise CheckError('Internal error, result not properly specified.')
    if bare:
        ret = ret['message'] if ret['result'] else None
    return ret


@depends(salt.utils.versions.version_cmp(GPG_VERSION, '2.1') >= 0)
def get_fingerprint_from_data(keydata, secret=False):
    '''
    This will return the fingerprint from a GPG key.

    :param str keydata: (potentially armored) key data.

    :rtype: str or None
    :return: Fingerprint of the provided key. ``None`` if no fingerprint was found.

    Note: If the keydata contains multiple keys, only the fingerprint of the first
    key is returned.
    Note2: This will only work for GNUPG 2.1 or greater.
    '''
    res = __salt__['cmd.run_stdout'](
        'gpg --dry-run --import-options import-show --import --with-colons',
        stdin=keydata,
    )
    fingerprint = re.match('^.*?(?:pub|sec):.*?fpr:{9}([0-9A-F]*):.*$', res, re.DOTALL)
    try:
        fingerprint = fingerprint.group(1)
    except AttributeError:
        pass
    return fingerprint


@jinja_filter('gpg_encrypt')
def text_encrypt(
    text=None,
    recipients=None,
    symmetric=None,
    passphrase=None,
    passphrase_pillar=None,
    sign=None,
    user=None,
    gnupghome=None,
):
    '''
    Wrapper function for ``encrypt`` to be used as Jinja filter for encrypting
    text.

    :param str text: The text to encrypt.
    :param str recipients: The fingerprints for those recipients whom the data is
        being encrypted for.
    :type symmetric: bool or str
    :param symmetric: If ``True`` or equal to some string, will use symmetric encryption.
        The value passed will be interpreted to be the cipher to use. Default: ``None``.
        When ``True``, the default cipher will be set to AES256.
        When used, a passphrase will need to be supplied.
    :param str passphrase: Passphrase to use with the signing key or symmetric encryption.
        default is None.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from, default
        is None.
    :type sign: bool or str
    :param sign: Whether to sign, in addition to encrypt, the data. Set to ``True``
        to use default key or provide the fingerprint of a different key to sign with.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.

    :rtype: str
    :return: Armored, encrypted and optionally also signed text block

    Jinja Example:

    .. code-block:: jinja

        encrypt_something:
          file.managed:
            - name: '/path/to/encrypted_file.asc'
            - contents: {{ 'some text' | gpg_encrypt(recipients='salt@saltstack.com') }}
    '''
    return encrypt(
        user=user,
        recipients=recipients,
        symmetric=symmetric,
        text=text,
        sign=sign,
        passphrase=passphrase,
        passphrase_pillar=passphrase_pillar,
        gnupghome=gnupghome,
        bare=True,
    )
