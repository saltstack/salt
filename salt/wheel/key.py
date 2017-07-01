# -*- coding: utf-8 -*-
'''
Wheel system wrapper for the Salt key system to be used in interactions with
the Salt Master programmatically.

The key module for the wheel system is meant to provide an internal interface
for other Salt systems to interact with the Salt Master. The following usage
examples assume that a WheelClient is available:

.. code-block:: python

    import salt.config
    import salt.wheel
    opts = salt.config.master_config('/etc/salt/master')
    wheel = salt.wheel.WheelClient(opts)

Note that importing and using the ``WheelClient`` must be performed on the same
machine as the Salt Master and as the same user that runs the Salt Master,
unless :conf_master:`external_auth` is configured and the user is authorized
to execute wheel functions.

The function documentation starts with the ``wheel`` reference from the code
sample above and use the :py:class:`WheelClient` functions to show how they can
be called from a Python interpreter.

The wheel key functions can also be called via a ``salt`` command at the CLI
using the :ref:`saltutil execution module <salt.modules.saltutil>`.
'''

# Import python libs
from __future__ import absolute_import
import os
import hashlib
import logging

# Import salt libs
from salt.key import get_key
import salt.crypt
import salt.utils
from salt.utils.sanitizers import clean


__func_alias__ = {
    'list_': 'list',
    'key_str': 'print',
}

log = logging.getLogger(__name__)


def list_(match):
    '''
    List all the keys under a named status. Returns a dictionary.

    match
        The type of keys to list. The ``pre``, ``un``, and ``unaccepted``
        options will list unaccepted/unsigned keys. ``acc`` or ``accepted`` will
        list accepted/signed keys. ``rej`` or ``rejected`` will list rejected keys.
        Finally, ``all`` will list all keys.

    .. code-block:: python

        >>> wheel.cmd('key.list', ['accepted'])
        {'minions': ['minion1', 'minion2', 'minion3']}
    '''
    skey = get_key(__opts__)
    return skey.list_status(match)


def list_all():
    '''
    List all the keys. Returns a dictionary containing lists of the minions in
    each salt-key category, including ``minions``, ``minions_rejected``,
    ``minions_denied``, etc. Returns a dictionary.

    .. code-block:: python

        >>> wheel.cmd('key.list_all')
        {'local': ['master.pem', 'master.pub'], 'minions_rejected': [],
        'minions_denied': [], 'minions_pre': [],
        'minions': ['minion1', 'minion2', 'minion3']}
    '''
    skey = get_key(__opts__)
    return skey.all_keys()


def name_match(match):
    '''
    List all the keys based on a glob match
    '''
    skey = get_key(__opts__)
    return skey.name_match(match)


def accept(match, include_rejected=False, include_denied=False):
    '''
    Accept keys based on a glob match. Returns a dictionary.

    match
        The glob match of keys to accept.

    include_rejected
        To include rejected keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

    include_denied
        To include denied keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

    .. code-block:: python

        >>> wheel.cmd('key.accept', ['minion1'])
        {'minions': ['minion1']}
    '''
    skey = get_key(__opts__)
    return skey.accept(match, include_rejected=include_rejected, include_denied=include_denied)


def accept_dict(match, include_rejected=False, include_denied=False):
    '''
    Accept keys based on a dict of keys. Returns a dictionary.

    match
        The dictionary of keys to accept.

    include_rejected
        To include rejected keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

        .. versionadded:: 2016.3.4

    include_denied
        To include denied keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

        .. versionadded:: 2016.3.4

    Example to move a list of keys from the ``minions_pre`` (pending) directory
    to the ``minions`` (accepted) directory:

    .. code-block:: python

        >>> wheel.cmd('accept_dict',
        {
            'minions_pre': [
                'jerry',
                'stuart',
                'bob',
            ],
        })
        {'minions': ['jerry', 'stuart', 'bob']}
    '''
    skey = get_key(__opts__)
    return skey.accept(match_dict=match,
            include_rejected=include_rejected,
            include_denied=include_denied)


def delete(match):
    '''
    Delete keys based on a glob match. Returns a dictionary.

    match
        The glob match of keys to delete.

    .. code-block:: python

        >>> wheel.cmd_async({'fun': 'key.delete', 'match': 'minion1'})
        {'jid': '20160826201244808521', 'tag': 'salt/wheel/20160826201244808521'}
    '''
    skey = get_key(__opts__)
    return skey.delete_key(match)


def delete_dict(match):
    '''
    Delete keys based on a dict of keys. Returns a dictionary.

    match
        The dictionary of keys to delete.

    .. code-block:: python

        >>> wheel.cmd_async({'fun': 'key.delete_dict',
        'match': {
            'minions': [
                'jerry',
                'stuart',
                'bob',
            ],
        })
        {'jid': '20160826201244808521', 'tag': 'salt/wheel/20160826201244808521'}
    '''
    skey = get_key(__opts__)
    return skey.delete_key(match_dict=match)


def reject(match, include_accepted=False, include_denied=False):
    '''
    Reject keys based on a glob match. Returns a dictionary.

    match
        The glob match of keys to reject.

    include_accepted
        To include accepted keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

    include_denied
        To include denied keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

    .. code-block:: python

        >>> wheel.cmd_async({'fun': 'key.reject', 'match': 'minion1'})
        {'jid': '20160826201244808521', 'tag': 'salt/wheel/20160826201244808521'}
    '''
    skey = get_key(__opts__)
    return skey.reject(match, include_accepted=include_accepted, include_denied=include_denied)


def reject_dict(match, include_accepted=False, include_denied=False):
    '''
    Reject keys based on a dict of keys. Returns a dictionary.

    match
        The dictionary of keys to reject.

    include_accepted
        To include accepted keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

        .. versionadded:: 2016.3.4

    include_denied
        To include denied keys in the match along with pending keys, set this
        to ``True``. Defaults to ``False``.

        .. versionadded:: 2016.3.4

    .. code-block:: python

        >>> wheel.cmd_async({'fun': 'key.reject_dict',
        'match': {
            'minions': [
                'jerry',
                'stuart',
                'bob',
            ],
        })
        {'jid': '20160826201244808521', 'tag': 'salt/wheel/20160826201244808521'}
    '''
    skey = get_key(__opts__)
    return skey.reject(match_dict=match,
            include_accepted=include_accepted,
            include_denied=include_denied)


def key_str(match):
    '''
    Return information about the key. Returns a dictionary.

    match
        The key to return information about.

    .. code-block:: python

        >>> wheel.cmd('key.key_str', ['minion1'])
        {'minions': {'minion1': '-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0B
        ...
        TWugEQpPt\niQIDAQAB\n-----END PUBLIC KEY-----'}}
    '''
    skey = get_key(__opts__)
    return skey.key_str(match)


def finger(match, hash_type=None):
    '''
    Return the matching key fingerprints. Returns a dictionary.

    match
        The key for with to retrieve the fingerprint.

    hash_type
        The hash algorithm used to calculate the fingerprint

    .. code-block:: python

        >>> wheel.cmd('key.finger', ['minion1'])
        {'minions': {'minion1': '5d:f6:79:43:5e:d4:42:3f:57:b8:45:a8:7e:a4:6e:ca'}}

    '''
    if hash_type is None:
        hash_type = __opts__['hash_type']

    skey = get_key(__opts__)
    return skey.finger(match, hash_type)


def finger_master(hash_type=None):
    '''
    Return the fingerprint of the master's public key

    hash_type
        The hash algorithm used to calculate the fingerprint

    .. code-block:: python

        >>> wheel.cmd('key.finger_master')
        {'local': {'master.pub': '5d:f6:79:43:5e:d4:42:3f:57:b8:45:a8:7e:a4:6e:ca'}}
    '''
    keyname = 'master.pub'
    if hash_type is None:
        hash_type = __opts__['hash_type']

    fingerprint = salt.utils.pem_finger(
        os.path.join(__opts__['pki_dir'], keyname), sum_type=hash_type)
    return {'local': {keyname: fingerprint}}


def gen(id_=None, keysize=2048):
    '''
    Generate a key pair. No keys are stored on the master. A key pair is
    returned as a dict containing pub and priv keys. Returns a dictionary
    containing the the ``pub`` and ``priv`` keys with their generated values.

    id_
        Set a name to generate a key pair for use with salt. If not specified,
        a random name will be specified.

    keysize
        The size of the key pair to generate. The size must be ``2048``, which
        is the default, or greater. If set to a value less than ``2048``, the
        key size will be rounded up to ``2048``.

    .. code-block:: python

        >>> wheel.cmd('key.gen')
        {'pub': '-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBC
        ...
        BBPfamX9gGPQTpN9e8HwcZjXQnmg8OrcUl10WHw09SDWLOlnW+ueTWugEQpPt\niQIDAQAB\n
        -----END PUBLIC KEY-----',
        'priv': '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA42Kf+w9XeZWgguzv
        ...
        QH3/W74X1+WTBlx4R2KGLYBiH+bCCFEQ/Zvcu4Xp4bIOPtRKozEQ==\n
        -----END RSA PRIVATE KEY-----'}
    '''
    if id_ is None:
        id_ = hashlib.sha512(os.urandom(32)).hexdigest()
    else:
        id_ = clean.filename(id_)
    ret = {'priv': '',
           'pub': ''}
    priv = salt.crypt.gen_keys(__opts__['pki_dir'], id_, keysize)
    pub = '{0}.pub'.format(priv[:priv.rindex('.')])
    with salt.utils.fopen(priv) as fp_:
        ret['priv'] = fp_.read()
    with salt.utils.fopen(pub) as fp_:
        ret['pub'] = fp_.read()

    # The priv key is given the Read-Only attribute. The causes `os.remove` to
    # fail in Windows.
    if salt.utils.is_windows():
        os.chmod(priv, 128)

    os.remove(priv)
    os.remove(pub)
    return ret


def gen_accept(id_, keysize=2048, force=False):
    '''
    Generate a key pair then accept the public key. This function returns the
    key pair in a dict, only the public key is preserved on the master. Returns
    a dictionary.

    id_
        The name of the minion for which to generate a key pair.

    keysize
        The size of the key pair to generate. The size must be ``2048``, which
        is the default, or greater. If set to a value less than ``2048``, the
        key size will be rounded up to ``2048``.

    force
        If a public key has already been accepted for the given minion on the
        master, then the gen_accept function will return an empty dictionary
        and not create a new key. This is the default behavior. If ``force``
        is set to ``True``, then the minion's previously accepted key will be
        overwritten.

    .. code-block:: python

        >>> wheel.cmd('key.gen_accept', ['foo'])
        {'pub': '-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBC
        ...
        BBPfamX9gGPQTpN9e8HwcZjXQnmg8OrcUl10WHw09SDWLOlnW+ueTWugEQpPt\niQIDAQAB\n
        -----END PUBLIC KEY-----',
        'priv': '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA42Kf+w9XeZWgguzv
        ...
        QH3/W74X1+WTBlx4R2KGLYBiH+bCCFEQ/Zvcu4Xp4bIOPtRKozEQ==\n
        -----END RSA PRIVATE KEY-----'}

    We can now see that the ``foo`` minion's key has been accepted by the master:

    .. code-block:: python

        >>> wheel.cmd('key.list', ['accepted'])
        {'minions': ['foo', 'minion1', 'minion2', 'minion3']}
    '''
    id_ = clean.id(id_)
    ret = gen(id_, keysize)
    acc_path = os.path.join(__opts__['pki_dir'], 'minions', id_)
    if os.path.isfile(acc_path) and not force:
        return {}
    with salt.utils.fopen(acc_path, 'w+') as fp_:
        fp_.write(ret['pub'])
    return ret


def gen_keys(keydir=None, keyname=None, keysize=None, user=None):
    '''
    Generate minion RSA public keypair
    '''
    skey = get_key(__opts__)
    return skey.gen_keys(keydir, keyname, keysize, user)


def gen_signature(priv, pub, signature_path, auto_create=False, keysize=None):
    '''
    Generate master public-key-signature
    '''
    skey = get_key(__opts__)
    return skey.gen_keys_signature(priv, pub, signature_path, auto_create, keysize)
