# -*- coding: utf-8 -*-
"""
Functions dealing with encryption
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import hashlib
import logging
import os

# Import Salt libs
import salt.loader
import salt.utils.files
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


try:
    import Crypto.Random

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def decrypt(
    data, rend, translate_newlines=False, renderers=None, opts=None, valid_rend=None
):
    """
    .. versionadded:: 2017.7.0

    Decrypt a data structure using the specified renderer. Written originally
    as a common codebase to handle decryption of encrypted elements within
    Pillar data, but should be flexible enough for other uses as well.

    Returns the decrypted result, but any decryption renderer should be
    recursively decrypting mutable types in-place, so any data structure passed
    should be automagically decrypted using this function. Immutable types
    obviously won't, so it's a good idea to check if ``data`` is hashable in
    the calling function, and replace the original value with the decrypted
    result if that is not the case. For an example of this, see
    salt.pillar.Pillar.decrypt_pillar().

    data
        The data to be decrypted. This can be a string of ciphertext or a data
        structure. If it is a data structure, the items in the data structure
        will be recursively decrypted.

    rend
        The renderer used to decrypt

    translate_newlines : False
        If True, then the renderer will convert a literal backslash followed by
        an 'n' into a newline before performing the decryption.

    renderers
        Optionally pass a loader instance containing loaded renderer functions.
        If not passed, then the ``opts`` will be required and will be used to
        invoke the loader to get the available renderers. Where possible,
        renderers should be passed to avoid the overhead of loading them here.

    opts
        The master/minion configuration opts. Used only if renderers are not
        passed.

    valid_rend
        A list containing valid renderers, used to restrict the renderers which
        this function will be allowed to use. If not passed, no restriction
        will be made.
    """
    try:
        if valid_rend and rend not in valid_rend:
            raise SaltInvocationError(
                "'{0}' is not a valid decryption renderer. Valid choices "
                "are: {1}".format(rend, ", ".join(valid_rend))
            )
    except TypeError as exc:
        # SaltInvocationError inherits TypeError, so check for it first and
        # raise if needed.
        if isinstance(exc, SaltInvocationError):
            raise
        # 'valid' argument is not iterable
        log.error("Non-iterable value %s passed for valid_rend", valid_rend)

    if renderers is None:
        if opts is None:
            raise TypeError("opts are required")
        renderers = salt.loader.render(opts, {})

    rend_func = renderers.get(rend)
    if rend_func is None:
        raise SaltInvocationError(
            "Decryption renderer '{0}' is not available".format(rend)
        )

    return rend_func(data, translate_newlines=translate_newlines)


def reinit_crypto():
    """
    When a fork arises, pycrypto needs to reinit
    From its doc::

        Caveat: For the random number generator to work correctly,
        you must call Random.atfork() in both the parent and
        child processes after using os.fork()

    """
    if HAS_CRYPTO:
        Crypto.Random.atfork()


def pem_finger(path=None, key=None, sum_type="sha256"):
    """
    Pass in either a raw pem string, or the path on disk to the location of a
    pem file, and the type of cryptographic hash to use. The default is SHA256.
    The fingerprint of the pem will be returned.

    If neither a key nor a path are passed in, a blank string will be returned.
    """
    if not key:
        if not os.path.isfile(path):
            return ""

        with salt.utils.files.fopen(path, "rb") as fp_:
            key = b"".join([x for x in fp_.readlines() if x.strip()][1:-1])

    pre = getattr(hashlib, sum_type)(key).hexdigest()
    finger = ""
    for ind, _ in enumerate(pre):
        if ind % 2:
            # Is odd
            finger += "{0}:".format(pre[ind])
        else:
            finger += pre[ind]
    return finger.rstrip(":")
