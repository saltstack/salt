# -*- coding: utf-8 -*-
'''
Use pycrypto to generate random passwords on the fly.
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import logging
import re
import string
import random

# Import 3rd-party libs
try:
    try:
        from M2Crypto.Rand import rand_bytes as get_random_bytes
    except ImportError:
        try:
            from Cryptodome.Random import get_random_bytes  # pylint: disable=E0611
        except ImportError:
            from Crypto.Random import get_random_bytes  # pylint: disable=E0611
    HAS_RANDOM = True
except ImportError:
    HAS_RANDOM = False

try:
    # Windows does not have the crypt module
    import crypt
    HAS_CRYPT = True
except ImportError:
    HAS_CRYPT = False

# Import salt libs
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext import six

log = logging.getLogger(__name__)


def secure_password(length=20, use_random=True):
    '''
    Generate a secure password.
    '''
    try:
        length = int(length)
        pw = ''
        while len(pw) < length:
            if HAS_RANDOM and use_random:
                while True:
                    try:
                        char = salt.utils.stringutils.to_str(get_random_bytes(1))
                        break
                    except UnicodeDecodeError:
                        continue
                pw += re.sub(
                    salt.utils.stringutils.to_str(r'[\W_]'),
                    str(),  # future lint: disable=blacklisted-function
                    char
                )
            else:
                pw += random.SystemRandom().choice(string.ascii_letters + string.digits)
        return pw
    except Exception as exc:
        log.exception('Failed to generate secure passsword')
        raise CommandExecutionError(six.text_type(exc))


def gen_hash(crypt_salt=None, password=None, algorithm='sha512'):
    '''
    Generate /etc/shadow hash
    '''
    if not HAS_CRYPT:
        raise SaltInvocationError('No crypt module for windows')

    hash_algorithms = dict(
        md5='$1$', blowfish='$2a$', sha256='$5$', sha512='$6$'
    )
    if algorithm not in hash_algorithms:
        raise SaltInvocationError(
            'Algorithm \'{0}\' is not supported'.format(algorithm)
        )

    if password is None:
        password = secure_password()

    if crypt_salt is None:
        crypt_salt = secure_password(8)

    crypt_salt = hash_algorithms[algorithm] + crypt_salt

    return crypt.crypt(password, crypt_salt)
