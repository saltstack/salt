
# -*- coding: utf-8 -*-
'''
Use pycrypto to generate random passwords on the fly.
'''

# Import python libraries
try:
    import Crypto.Random  # pylint: disable=E0611
    HAS_RANDOM = True
except ImportError:
    HAS_RANDOM = False
import crypt
import re


def secure_password(length=20):
    '''
    Generate a secure password.
    '''
    if not HAS_RANDOM:
        raise ImportError('generating passwords requires >= pycrypto v2.1.0')
    pw = ''
    while len(pw) < length:
        pw += re.sub(r'\W', '', Crypto.Random.get_random_bytes(1))
    return pw


def gen_hash(salt=None, password=None):
    '''
    Generate /etc/shadow hash
    '''

    if password is None:
        password = secure_password()

    if salt is None:
        salt = '$6' + secure_password(8)

    return crypt.crypt(password, salt)
