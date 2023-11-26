"""
Salt package
"""

import importlib
import locale
import os
import sys
import warnings

if sys.version_info < (3,):  # pragma: no cover
    sys.stderr.write(
        "\n\nAfter the Sodium release, 3001, Salt no longer supports Python 2. Exiting.\n\n"
    )
    sys.stderr.flush()


class NaclImporter:
    """
    Import hook to force PyNaCl to perform dlopen on libsodium with the
    RTLD_DEEPBIND flag. This is to work around an issue where pyzmq does a dlopen
    with RTLD_GLOBAL which then causes calls to libsodium to resolve to
    tweetnacl when it's been bundled with pyzmq.

    See:  https://github.com/zeromq/pyzmq/issues/1878
    """

    loading = False

    def find_module(self, module_name, package_path=None):
        if not NaclImporter.loading and module_name.startswith("nacl"):
            NaclImporter.loading = True
            return self
        return None

    def create_module(self, spec):
        dlopen = hasattr(sys, "getdlopenflags")
        if dlopen:
            dlflags = sys.getdlopenflags()
            # Use RTDL_DEEPBIND in case pyzmq was compiled with ZMQ_USE_TWEETNACL. This is
            # needed because pyzmq imports libzmq with RTLD_GLOBAL.
            if hasattr(os, "RTLD_DEEPBIND"):
                flags = os.RTLD_DEEPBIND | dlflags
            else:
                flags = dlflags
            sys.setdlopenflags(flags)
        try:
            mod = importlib.import_module(spec.name)
        finally:
            if dlopen:
                sys.setdlopenflags(dlflags)
        NaclImporter.loading = False
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        return None


# Try our importer first
sys.meta_path = [NaclImporter()] + sys.meta_path


# All salt related deprecation warnings should be shown once each!
warnings.filterwarnings(
    "once",  # Show once
    "",  # No deprecation message match
    DeprecationWarning,  # This filter is for DeprecationWarnings
    r"^(salt|salt\.(.*))$",  # Match module(s) 'salt' and 'salt.<whatever>'
    # Do *NOT* add append=True here - if we do, salt's DeprecationWarnings will
    # never show up
)

# Filter the backports package UserWarning about being re-imported
warnings.filterwarnings(
    "ignore",
    "^Module backports was already imported from (.*), but (.*) is being added to sys.path$",
    UserWarning,
    append=True,
)

# Filter the setuptools UserWarning until we stop relying on distutils
warnings.filterwarnings(
    "ignore",
    message="Setuptools is replacing distutils.",
    category=UserWarning,
    module="_distutils_hack",
)

warnings.filterwarnings(
    "ignore",
    message="invalid escape sequence.*",
    category=DeprecationWarning,
)


def __define_global_system_encoding_variable__():
    # This is the most trustworthy source of the system encoding, though, if
    # salt is being imported after being daemonized, this information is lost
    # and reset to None
    encoding = None

    if not sys.platform.startswith("win") and sys.stdin is not None:
        # On linux we can rely on sys.stdin for the encoding since it
        # most commonly matches the filesystem encoding. This however
        # does not apply to windows
        encoding = sys.stdin.encoding

    if not encoding:
        # If the system is properly configured this should return a valid
        # encoding. MS Windows has problems with this and reports the wrong
        # encoding
        try:
            encoding = locale.getencoding()
        except AttributeError:
            # Python < 3.11
            encoding = locale.getpreferredencoding(do_setlocale=True)

        if not encoding:
            # This is most likely ascii which is not the best but we were
            # unable to find a better encoding. If this fails, we fall all
            # the way back to ascii
            encoding = sys.getdefaultencoding()
        if not encoding:
            if sys.platform.startswith("darwin"):
                # Mac OS X uses UTF-8
                encoding = "utf-8"
            elif sys.platform.startswith("win"):
                # Windows uses a configurable encoding; on Windows, Python uses the name “mbcs”
                # to refer to whatever the currently configured encoding is.
                encoding = "mbcs"
            else:
                # On linux default to ascii as a last resort
                encoding = "ascii"

    import builtins

    # Define the detected encoding as a built-in variable for ease of use
    setattr(builtins, "__salt_system_encoding__", encoding)

    # This is now garbage collectable
    del builtins
    del encoding


__define_global_system_encoding_variable__()

# This is now garbage collectable
del __define_global_system_encoding_variable__

# Make sure Salt's logging tweaks are always present
# DO NOT MOVE THIS IMPORT
# pylint: disable=unused-import
import salt._logging  # isort:skip

# pylint: enable=unused-import
