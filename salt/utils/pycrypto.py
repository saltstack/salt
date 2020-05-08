# -*- coding: utf-8 -*-
"""
Use pycrypto to generate random passwords on the fly.
"""

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals

import logging
import random
import re
import string

# Import salt libs
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext import six

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
    # consider using passlib.hash instead
    import crypt

    HAS_CRYPT = True
except ImportError:
    HAS_CRYPT = False

try:
    import passlib.context

    HAS_PASSLIB = True
except ImportError:
    HAS_PASSLIB = False

log = logging.getLogger(__name__)


def secure_password(length=20, use_random=True):
    """
    Generate a secure password.
    """
    try:
        length = int(length)
        pw = ""
        while len(pw) < length:
            if HAS_RANDOM and use_random:
                while True:
                    try:
                        char = salt.utils.stringutils.to_str(get_random_bytes(1))
                        break
                    except UnicodeDecodeError:
                        continue
                pw += re.sub(
                    salt.utils.stringutils.to_str(r"[\W_]"),
                    str(),  # future lint: disable=blacklisted-function
                    char,
                )
            else:
                pw += random.SystemRandom().choice(string.ascii_letters + string.digits)
        return pw
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Failed to generate secure passsword")
        raise CommandExecutionError(six.text_type(exc))


if HAS_CRYPT:
    methods = {m.name.lower(): m for m in crypt.methods}
else:
    methods = {}
known_methods = ["sha512", "sha256", "blowfish", "md5", "crypt"]


def _fallback_gen_hash(crypt_salt=None, password=None, algorithm=None):
    """
    Generate a /etc/shadow-compatible hash for a non-local system
    """
    if algorithm is None:
        algorithm = 0

    # these are the passlib equivalents to the 'known_methods' defined in crypt
    schemes = ["sha512_crypt", "sha256_crypt", "bcrypt", "md5_crypt", "des_crypt"]

    ctx = passlib.context.CryptContext(schemes=schemes)
    return ctx.hash(
        password, salt=crypt_salt, scheme=schemes[known_methods.index(algorithm)]
    )


def gen_hash(crypt_salt=None, password=None, algorithm=None, force=False):
    """
    Generate /etc/shadow hash
    """
    if password is None:
        password = secure_password()

    if algorithm not in methods:
        if force and HAS_PASSLIB:
            return _fallback_gen_hash(crypt_salt, password, algorithm)
        else:
            raise SaltInvocationError(
                "Algorithm '{}' is not natively supported by this platform, use force=True with passlib installed to override.".format(
                    algorithm
                )
            )

    if algorithm is None:
        # use the most secure natively supported method
        algorithm = crypt.methods[0].name.lower()

    if crypt_salt is None:
        crypt_salt = methods[algorithm]
    elif methods[algorithm].ident:
        crypt_salt = "${}${}".format(methods[algorithm].ident, crypt_salt)
    else:  # method is crypt (DES)
        if len(crypt_salt) != 2:
            raise ValueError(
                "Invalid salt for hash, 'crypt' salt must be 2 characters."
            )

    return crypt.crypt(password, crypt_salt)
