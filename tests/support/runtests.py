"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    .. _runtime_vars:

    Runtime Variables
    -----------------

    :command:`salt-runtests` provides a variable, :py:attr:`RUNTIME_VARS` which has some common paths defined at
    startup:

    .. autoattribute:: tests.support.runtests.RUNTIME_VARS
        :annotation:

        :TMP: Tests suite temporary directory
        :TMP_CONF_DIR: Configuration directory from where the daemons that :command:`salt-runtests` starts get their
                       configuration files.
        :TMP_CONF_MASTER_INCLUDES: Salt Master configuration files includes directory. See
                                   :salt_conf_master:`default_include`.
        :TMP_CONF_MINION_INCLUDES: Salt Minion configuration files includes directory. Seei
                                   :salt_conf_minion:`include`.
        :TMP_CONF_CLOUD_INCLUDES: Salt cloud configuration files includes directory. The same as the salt master and
                                  minion includes configuration, though under a different directory name.
        :TMP_CONF_CLOUD_PROFILE_INCLUDES: Salt cloud profiles configuration files includes directory. Same as above.
        :TMP_CONF_CLOUD_PROVIDER_INCLUDES: Salt cloud providers configuration files includes directory. Same as above.
        :TMP_SCRIPT_DIR: Temporary scripts directory from where the Salt CLI tools will be called when running tests.
        :TMP_SALT_INTEGRATION_FILES: Temporary directory from where Salt's test suite integration files are copied to.
        :TMP_BASEENV_STATE_TREE: Salt master's **base** environment state tree directory
        :TMP_PRODENV_STATE_TREE: Salt master's **production** environment state tree directory
        :TMP_BASEENV_PILLAR_TREE: Salt master's **base** environment pillar tree directory
        :TMP_PRODENV_PILLAR_TREE: Salt master's **production** environment pillar tree directory


    Use it on your test case in case of need. As simple as:

    .. code-block:: python

        import os
        from tests.support.runtests import RUNTIME_VARS

        # Path to the testing minion configuration file
        minion_config_path = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'minion')

    .. _`pytest`: http://pytest.org
    """

import logging
import os
import shutil

import salt.utils.path
import salt.utils.platform
import tests.support.paths as paths

try:
    import pwd
except ImportError:
    import salt.utils.win_functions

log = logging.getLogger(__name__)


def this_user():
    """
    Get the user associated with the current process.
    """
    if salt.utils.platform.is_windows():
        return salt.utils.win_functions.get_current_user(with_domain=False)
    return pwd.getpwuid(os.getuid())[0]


class RootsDict(dict):
    def merge(self, data):
        for key, values in data.items():
            if key not in self:
                self[key] = values
                continue
            for value in values:
                if value not in self[key]:
                    self[key].append(value)
        return self

    def to_dict(self):
        return dict(self)


def recursive_copytree(source, destination, overwrite=False):
    for root, dirs, files in os.walk(source):
        for item in dirs:
            src_path = os.path.join(root, item)
            dst_path = os.path.join(
                destination, src_path.replace(source, "").lstrip(os.sep)
            )
            if not os.path.exists(dst_path):
                log.debug("Creating directory: %s", dst_path)
                os.makedirs(dst_path)
        for item in files:
            src_path = os.path.join(root, item)
            dst_path = os.path.join(
                destination, src_path.replace(source, "").lstrip(os.sep)
            )
            if os.path.exists(dst_path) and not overwrite:
                if os.stat(src_path).st_mtime > os.stat(dst_path).st_mtime:
                    log.debug("Copying %s to %s", src_path, dst_path)
                    shutil.copy2(src_path, dst_path)
            else:
                if not os.path.isdir(os.path.dirname(dst_path)):
                    log.debug("Creating directory: %s", os.path.dirname(dst_path))
                    os.makedirs(os.path.dirname(dst_path))
                log.debug("Copying %s to %s", src_path, dst_path)
                shutil.copy2(src_path, dst_path)


class RuntimeVars:

    __self_attributes__ = ("_vars", "_locked", "lock")

    def __init__(self, **kwargs):
        self._vars = kwargs
        self._locked = False

    def lock(self):
        # Late import
        from salt.utils.immutabletypes import freeze

        frozen_vars = freeze(self._vars.copy())
        self._vars = frozen_vars
        self._locked = True

    def __iter__(self):
        yield from self._vars.items()

    def __getattribute__(self, name):
        if name in object.__getattribute__(self, "_vars"):
            return object.__getattribute__(self, "_vars")[name]
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if getattr(self, "_locked", False) is True:
            raise RuntimeError(
                "After {} is locked, no additional data can be added to it".format(
                    self.__class__.__name__
                )
            )
        if name in object.__getattribute__(self, "__self_attributes__"):
            object.__setattr__(self, name, value)
            return
        self._vars[name] = value


# <---- Helper Methods -----------------------------------------------------------------------------------------------


# ----- Global Variables -------------------------------------------------------------------------------------------->
XML_OUTPUT_DIR = os.environ.get(
    "SALT_XML_TEST_REPORTS_DIR", os.path.join(paths.TMP, "xml-test-reports")
)
# <---- Global Variables ---------------------------------------------------------------------------------------------


# ----- Tests Runtime Variables ------------------------------------------------------------------------------------->

RUNTIME_VARS = RuntimeVars(
    TMP=paths.TMP,
    SYS_TMP_DIR=paths.SYS_TMP_DIR,
    FILES=paths.FILES,
    CONF_DIR=paths.CONF_DIR,
    PILLAR_DIR=paths.PILLAR_DIR,
    ENGINES_DIR=paths.ENGINES_DIR,
    LOG_HANDLERS_DIR=paths.LOG_HANDLERS_DIR,
    TMP_ROOT_DIR=paths.TMP_ROOT_DIR,
    TMP_CONF_DIR=paths.TMP_CONF_DIR,
    TMP_MINION_CONF_DIR=paths.TMP_MINION_CONF_DIR,
    TMP_CONF_MASTER_INCLUDES=os.path.join(paths.TMP_CONF_DIR, "master.d"),
    TMP_CONF_MINION_INCLUDES=os.path.join(paths.TMP_CONF_DIR, "minion.d"),
    TMP_CONF_PROXY_INCLUDES=os.path.join(paths.TMP_CONF_DIR, "proxy.d"),
    TMP_CONF_CLOUD_INCLUDES=os.path.join(paths.TMP_CONF_DIR, "cloud.conf.d"),
    TMP_CONF_CLOUD_PROFILE_INCLUDES=os.path.join(
        paths.TMP_CONF_DIR, "cloud.profiles.d"
    ),
    TMP_CONF_CLOUD_PROVIDER_INCLUDES=os.path.join(
        paths.TMP_CONF_DIR, "cloud.providers.d"
    ),
    TMP_SUB_MINION_CONF_DIR=paths.TMP_SUB_MINION_CONF_DIR,
    TMP_SYNDIC_MASTER_CONF_DIR=paths.TMP_SYNDIC_MASTER_CONF_DIR,
    TMP_SYNDIC_MINION_CONF_DIR=paths.TMP_SYNDIC_MINION_CONF_DIR,
    TMP_SSH_CONF_DIR=paths.TMP_SSH_CONF_DIR,
    TMP_SCRIPT_DIR=paths.TMP_SCRIPT_DIR,
    TMP_STATE_TREE=paths.TMP_STATE_TREE,
    TMP_BASEENV_STATE_TREE=paths.TMP_STATE_TREE,
    TMP_PILLAR_TREE=paths.TMP_PILLAR_TREE,
    TMP_BASEENV_PILLAR_TREE=paths.TMP_PILLAR_TREE,
    TMP_PRODENV_STATE_TREE=paths.TMP_PRODENV_STATE_TREE,
    TMP_PRODENV_PILLAR_TREE=paths.TMP_PRODENV_PILLAR_TREE,
    SHELL_TRUE_PATH=(
        salt.utils.path.which("true")
        if not salt.utils.platform.is_windows()
        else "cmd /c exit 0 > nul"
    ),
    SHELL_FALSE_PATH=(
        salt.utils.path.which("false")
        if not salt.utils.platform.is_windows()
        else "cmd /c exit 1 > nul"
    ),
    RUNNING_TESTS_USER=this_user(),
    RUNTIME_CONFIGS={},
    CODE_DIR=paths.CODE_DIR,
    SALT_CODE_DIR=paths.SALT_CODE_DIR,
    BASE_FILES=paths.BASE_FILES,
    PROD_FILES=paths.PROD_FILES,
    TESTS_DIR=paths.TESTS_DIR,
)
# <---- Tests Runtime Variables --------------------------------------------------------------------------------------
