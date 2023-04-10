"""
Salt package
"""

import importlib
import sys
import warnings

if sys.version_info < (3,):
    sys.stderr.write(
        "\n\nAfter the Sodium release, 3001, Salt no longer supports Python 2. Exiting.\n\n"
    )
    sys.stderr.flush()

USE_VENDORED_TORNADO = True


class TornadoImporter:
    def find_module(self, module_name, package_path=None):
        if USE_VENDORED_TORNADO:
            if module_name.startswith("tornado"):
                return self
        else:
            if module_name.startswith("salt.ext.tornado"):
                return self
        return None

    def load_module(self, name):
        if USE_VENDORED_TORNADO:
            mod = importlib.import_module("salt.ext.{}".format(name))
        else:
            # Remove 'salt.ext.' from the module
            mod = importlib.import_module(name[9:])
        sys.modules[name] = mod
        return mod

    def create_module(self, spec):
        return self.load_module(spec.name)

    def exec_module(self, module):
        return None


# Try our importer first
sys.meta_path = [TornadoImporter()] + sys.meta_path


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


def __define_global_system_encoding_variable__():
    import sys

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
    del sys
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


# When we are running in a 'onedir' environment, setup the path for user
# installed packages.
if hasattr(sys, "RELENV"):
    sys.path.insert(0, str(sys.RELENV / "extras-{}.{}".format(*sys.version_info)))
