# -*- coding: utf-8 -*-
'''
Wheel system wrapper for key system
'''

# Import python libs
import os
import hashlib
import random

# Import salt libs
import salt.key
import salt.crypt

__func_alias__ = {
    'list_': 'list'
}


def list_(match):
    '''
    List all the keys under a named status
    '''
    skey = salt.key.Key(__opts__)
    return skey.list_status(match)


def list_all():
    '''
    List all the keys
    '''
    skey = salt.key.Key(__opts__)
    return skey.all_keys()


def accept(match):
    '''
    Accept keys based on a glob match
    '''
    skey = salt.key.Key(__opts__)
    return skey.accept(match)


def delete(match):
    '''
    Delete keys based on a glob match
    '''
    skey = salt.key.Key(__opts__)
    return skey.delete_key(match)


def reject(match):
    '''
    Delete keys based on a glob match
    '''
    skey = salt.key.Key(__opts__)
    return skey.reject(match)


def key_str(match):
    '''
    Return the key strings
    '''
    skey = salt.key.Key(__opts__)
    return skey.key_str(match)


def finger(match):
    '''
    Return the matching key fingerprints
    '''
    skey = salt.key.Key(__opts__)
    return skey.finger(match)


def gen(id_=None, keysize=2048):
    '''
    Generate a key pair. No keys are stored on the master, a keypair is
    returned as a dict containing pub and priv keys
    '''
    if id_ is None:
        id_ = hashlib.sha512(str(random.randint(0, 99999999))).hexdigest()
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
