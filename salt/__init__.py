# -*- coding: utf-8 -*-
'''
Salt package
'''

# Import Python libs
from __future__ import absolute_import
import warnings

# All salt related deprecation warnings should be shown once each!
warnings.filterwarnings(
    'once',  # Show once
    '',  # No deprecation message match
    DeprecationWarning,  # This filter is for DeprecationWarnings
    r'^(salt|salt\.(.*))$'  # Match module(s) 'salt' and 'salt.<whatever>'
)

# While we are supporting Python2.6, hide nested with-statements warnings
warnings.filterwarnings(
    'ignore',
    'With-statements now directly support multiple context managers',
    DeprecationWarning
)

# Filter the backports package UserWarning about being re-imported
warnings.filterwarnings(
    'ignore',
    '^Module backports was already imported from (.*), but (.*) is being added to sys.path$',
    UserWarning
)


def __define_global_system_encoding_variable__():
    import sys
    # This is the most trustworthy source of the system encoding, though, if
    # salt is being imported after being daemonized, this information is lost
    # and reset to None
    encoding = None

    if not sys.platform.startswith('win') and sys.stdin is not None:
        # On linux we can rely on sys.stdin for the encoding since it
        # most commonly matches the filesystem encoding. This however
        # does not apply to windows
        encoding = sys.stdin.encoding

    if not encoding:
        # If the system is properly configured this should return a valid
        # encoding. MS Windows has problems with this and reports the wrong
        # encoding
        import locale
        try:
            encoding = locale.getdefaultlocale()[-1]
        except ValueError:
            # A bad locale setting was most likely found:
            #   https://github.com/saltstack/salt/issues/26063
            pass

        # This is now garbage collectable
        del locale
        if not encoding:
            # This is most likely ascii which is not the best but we were
            # unable to find a better encoding. If this fails, we fall all
            # the way back to ascii
            encoding = sys.getdefaultencoding()
        if not encoding:
            if sys.platform.startswith('darwin'):
                # Mac OS X uses UTF-8
                encoding = 'utf-8'
            elif sys.platform.startswith('win'):
                # Windows uses a configurable encoding; on Windows, Python uses the name “mbcs”
                # to refer to whatever the currently configured encoding is.
                encoding = 'mbcs'
            else:
                # On linux default to ascii as a last resort
                encoding = 'ascii'

    # We can't use six.moves.builtins because these builtins get deleted sooner
    # than expected. See:
    #    https://github.com/saltstack/salt/issues/21036
    if sys.version_info[0] < 3:
        import __builtin__ as builtins  # pylint: disable=incompatible-py3-code
    else:
        import builtins  # pylint: disable=import-error

    # Define the detected encoding as a built-in variable for ease of use
    setattr(builtins, '__salt_system_encoding__', encoding)

    # This is now garbage collectable
    del sys
    del builtins
    del encoding


__define_global_system_encoding_variable__()

# This is now garbage collectable
del __define_global_system_encoding_variable__
