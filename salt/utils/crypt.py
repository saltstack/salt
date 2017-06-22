# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)

# Import Salt libs
import salt.loader
from salt.exceptions import SaltInvocationError


def decrypt(data,
            rend,
            translate_newlines=False,
            renderers=None,
            opts=None,
            valid_rend=None):
    '''
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
    '''
    try:
        if valid_rend and rend not in valid_rend:
            raise SaltInvocationError(
                '\'{0}\' is not a valid decryption renderer. Valid choices '
                'are: {1}'.format(rend, ', '.join(valid_rend))
            )
    except TypeError as exc:
        # SaltInvocationError inherits TypeError, so check for it first and
        # raise if needed.
        if isinstance(exc, SaltInvocationError):
            raise
        # 'valid' argument is not iterable
        log.error('Non-iterable value %s passed for valid_rend', valid_rend)

    if renderers is None:
        if opts is None:
            raise TypeError('opts are required')
        renderers = salt.loader.render(opts, {})

    rend_func = renderers.get(rend)
    if rend_func is None:
        raise SaltInvocationError(
            'Decryption renderer \'{0}\' is not available'.format(rend)
        )

    return rend_func(data, translate_newlines=translate_newlines)
