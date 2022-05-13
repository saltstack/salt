"""
Use pycrypto to generate random passwords on the fly.
"""
import logging
import random
import re
import string

import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError

try:
    try:
        from M2Crypto.Rand import rand_bytes as get_random_bytes
    except ImportError:
        try:
            from Cryptodome.Random import get_random_bytes
        except ImportError:
            from Crypto.Random import get_random_bytes  # nosec
    HAS_RANDOM = True
except ImportError:
    HAS_RANDOM = False

try:
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


def secure_password(
    length=20,
    use_random=True,
    chars=None,
    lowercase=True,
    uppercase=True,
    digits=True,
    punctuation=True,
    whitespace=False,
    printable=False,
):
    """
    Generate a secure password.
    """
    chars = chars or ""
    if printable:
        # as printable includes all other string character classes
        # the other checks can be skipped
        chars = string.printable
    if not chars:
        if lowercase:
            chars += string.ascii_lowercase
        if uppercase:
            chars += string.ascii_uppercase
        if digits:
            chars += string.digits
        if punctuation:
            chars += string.punctuation
        if whitespace:
            chars += string.whitespace
    try:
        length = int(length)
        pw = ""
        while len(pw) < length:
            if HAS_RANDOM and use_random:
                encoding = None
                if salt.utils.platform.is_windows():
                    encoding = "UTF-8"
                while True:
                    try:
                        char = salt.utils.stringutils.to_str(
                            get_random_bytes(1), encoding=encoding
                        )
                        break
                    except UnicodeDecodeError:
                        continue
                pw += re.sub(
                    salt.utils.stringutils.to_str(
                        r"[^{}]".format(re.escape(chars)), encoding=encoding
                    ),
                    "",
                    char,
                )
            else:
                pw += random.SystemRandom().choice(chars)
        return pw
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Failed to generate secure passsword")
        raise CommandExecutionError(str(exc))


if HAS_CRYPT:
    methods = {m.name.lower(): m for m in crypt.methods}
else:
    methods = {}
known_methods = ["sha512", "sha256", "blowfish", "md5", "crypt"]


def _gen_hash_passlib(crypt_salt=None, password=None, algorithm=None):
    """
    Generate a /etc/shadow-compatible hash for a non-local system
    """
    # these are the passlib equivalents to the 'known_methods' defined in crypt
    schemes = ["sha512_crypt", "sha256_crypt", "bcrypt", "md5_crypt", "des_crypt"]

    ctx = passlib.context.CryptContext(schemes=schemes)

    kwargs = {"secret": password, "scheme": schemes[known_methods.index(algorithm)]}
    if crypt_salt and "$" in crypt_salt:
        # this salt has a rounds specifier.
        #  passlib takes it as a separate parameter, split it out
        roundsstr, split_salt = crypt_salt.split("$")
        rounds = int(roundsstr.split("=")[-1])
        kwargs.update({"salt": split_salt, "rounds": rounds})
    else:
        # relaxed = allow salts that are too long
        kwargs.update({"salt": crypt_salt, "relaxed": True})
    return ctx.hash(**kwargs)


def _gen_hash_crypt(crypt_salt=None, password=None, algorithm=None):
    """
    Generate /etc/shadow hash using the native crypt module
    """
    if crypt_salt is None:
        # setting crypt_salt to the algorithm makes crypt generate
        #  a salt compatible with the specified algorithm.
        crypt_salt = methods[algorithm]
    else:
        if algorithm != "crypt":
            # all non-crypt algorithms are specified as part of the salt
            crypt_salt = "${}${}".format(methods[algorithm].ident, crypt_salt)

    try:
        ret = crypt.crypt(password, crypt_salt)
    except OSError:
        ret = None
    return ret


def gen_hash(crypt_salt=None, password=None, algorithm=None):
    """
    Generate /etc/shadow hash
    """
    if password is None:
        password = secure_password()

    if algorithm is None:
        # prefer the most secure natively supported method
        algorithm = crypt.methods[0].name.lower() if HAS_CRYPT else known_methods[0]

    if algorithm == "crypt" and crypt_salt and len(crypt_salt) != 2:
        log.warning("Hash salt is too long for 'crypt' hash.")

    if HAS_CRYPT and algorithm in methods:
        return _gen_hash_crypt(
            crypt_salt=crypt_salt, password=password, algorithm=algorithm
        )
    elif HAS_PASSLIB and algorithm in known_methods:
        return _gen_hash_passlib(
            crypt_salt=crypt_salt, password=password, algorithm=algorithm
        )
    else:
        raise SaltInvocationError(
            "Cannot hash using '{}' hash algorithm. Natively supported "
            "algorithms are: {}. If passlib is installed ({}), the supported "
            "algorithms are: {}.".format(
                algorithm, list(methods), HAS_PASSLIB, known_methods
            )
        )
