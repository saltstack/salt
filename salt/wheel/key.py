# -*- coding: utf-8 -*-
'''
Wheel system wrapper for key system
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

__func_alias__ = {
    'list_': 'list',
    'key_str': 'print',
}

log = logging.getLogger(__name__)


def list_(match):
    '''
    List all the keys under a named status
    '''
    skey = get_key(__opts__)
    return skey.list_status(match)


def list_all():
    '''
    List all the keys
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
    Accept keys based on a glob match
    '''
    skey = get_key(__opts__)
    return skey.accept(match, include_rejected=include_rejected, include_denied=include_denied)


def accept_dict(match):
    '''
    Accept keys based on a dict of keys

    Example to move a list of keys from the `minions_pre` (pending) directory
    to the `minions` (accepted) directory:

    .. code-block:: python

        {
            'minions_pre': [
                'jerry',
                'stuart',
                'bob',
            ],
        }
    '''
    skey = get_key(__opts__)
    return skey.accept(match_dict=match)


def delete(match):
    '''
    Delete keys based on a glob match
    '''
    skey = get_key(__opts__)
    return skey.delete_key(match)


def delete_dict(match):
    '''
    Delete keys based on a dict of keys
    '''
    skey = get_key(__opts__)
    return skey.delete_key(match_dict=match)


def reject(match, include_accepted=False, include_denied=False):
    '''
    Reject keys based on a glob match
    '''
    skey = get_key(__opts__)
    return skey.reject(match, include_accepted=include_accepted, include_denied=include_denied)


def reject_dict(match):
    '''
    Reject keys based on a dict of keys
    '''
    skey = get_key(__opts__)
    return skey.reject(match_dict=match)


def key_str(match):
    '''
    Return the key strings
    '''
    skey = get_key(__opts__)
    return skey.key_str(match)


def finger(match):
    '''
    Return the matching key fingerprints
    '''
    skey = get_key(__opts__)
    return skey.finger(match)


def gen(id_=None, keysize=2048):
    '''
    Generate a key pair. No keys are stored on the master, a keypair is
    returned as a dict containing pub and priv keys
    '''
    if id_ is None:
        id_ = hashlib.sha512(os.urandom(32)).hexdigest()
    ret = {'priv': '',
           'pub': ''}
    priv = salt.crypt.gen_keys(__opts__['pki_dir'], id_, keysize)
    pub = '{0}.pub'.format(priv[:priv.rindex('.')])
    with salt.utils.fopen(priv) as fp_:
        ret['priv'] = fp_.read()
    with salt.utils.fopen(pub) as fp_:
        ret['pub'] = fp_.read()
    os.remove(priv)
    os.remove(pub)
    return ret


def gen_accept(id_, keysize=2048, force=False):
    '''
    Generate a key pair then accept the public key. This function returns the
    key pair in a dict, only the public key is preserved on the master.
    '''
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
