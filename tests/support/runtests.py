# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

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
    .. _`nose`: https://nose.readthedocs.org
    '''

# Import Python modules
from __future__ import absolute_import, print_function
import os
import sys
import json
import shutil
import logging
import multiprocessing

# Import tests support libs
import tests.support.paths as paths

# Import 3rd-party libs
import salt.ext.six as six
try:
    import coverage  # pylint: disable=import-error
    HAS_COVERAGE = True
except ImportError:
    HAS_COVERAGE = False

try:
    import multiprocessing.util
    # Force forked multiprocessing processes to be measured as well

    def multiprocessing_stop(coverage_object):
        '''
        Save the multiprocessing process coverage object
        '''
        coverage_object.stop()
        coverage_object.save()

    def multiprocessing_start(obj):
        coverage_options = json.loads(os.environ.get('SALT_RUNTESTS_COVERAGE_OPTIONS', '{}'))
        if not coverage_options:
            return

        if coverage_options.get('data_suffix', False) is False:
            return

        coverage_object = coverage.coverage(**coverage_options)
        coverage_object.start()

        multiprocessing.util.Finalize(
            None,
            multiprocessing_stop,
            args=(coverage_object,),
            exitpriority=1000
        )

    if HAS_COVERAGE:
        multiprocessing.util.register_after_fork(
            multiprocessing_start,
            multiprocessing_start
        )
except ImportError:
    pass

if sys.platform.startswith('win'):
    import win32api  # pylint: disable=import-error
    RUNNING_TESTS_USER = win32api.GetUserName()
else:
    import pwd
    RUNNING_TESTS_USER = pwd.getpwuid(os.getuid()).pw_name

log = logging.getLogger(__name__)


class RootsDict(dict):
    def merge(self, data):
        for key, values in six.iteritems(data):
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
            dst_path = os.path.join(destination, src_path.replace(source, '').lstrip(os.sep))
            if not os.path.exists(dst_path):
                log.debug('Creating directory: {0}'.format(dst_path))
                os.makedirs(dst_path)
        for item in files:
            src_path = os.path.join(root, item)
            dst_path = os.path.join(destination, src_path.replace(source, '').lstrip(os.sep))
            if os.path.exists(dst_path) and not overwrite:
                if os.stat(src_path).st_mtime > os.stat(dst_path).st_mtime:
                    log.debug('Copying {0} to {1}'.format(src_path, dst_path))
                    shutil.copy2(src_path, dst_path)
            else:
                if not os.path.isdir(os.path.dirname(dst_path)):
                    log.debug('Creating directory: {0}'.format(os.path.dirname(dst_path)))
                    os.makedirs(os.path.dirname(dst_path))
                log.debug('Copying {0} to {1}'.format(src_path, dst_path))
                shutil.copy2(src_path, dst_path)


class RuntimeVars(object):

    __self_attributes__ = ('_vars', '_locked', 'lock')

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
        for name, value in six.iteritems(self._vars):
            yield name, value

    def __getattribute__(self, name):
        if name in object.__getattribute__(self, '_vars'):
            return object.__getattribute__(self, '_vars')[name]
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if getattr(self, '_locked', False) is True:
            raise RuntimeError(
                'After {0} is locked, no additional data can be added to it'.format(
                    self.__class__.__name__
                )
            )
        if name in object.__getattribute__(self, '__self_attributes__'):
            object.__setattr__(self, name, value)
            return
        self._vars[name] = value
# <---- Helper Methods -----------------------------------------------------------------------------------------------

# ----- Global Variables -------------------------------------------------------------------------------------------->
XML_OUTPUT_DIR = os.environ.get('SALT_XML_TEST_REPORTS_DIR', os.path.join(paths.TMP, 'xml-test-reports'))
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
    TMP_CONF_DIR=paths.TMP_CONF_DIR,
    TMP_CONF_MASTER_INCLUDES=os.path.join(paths.TMP_CONF_DIR, 'master.d'),
    TMP_CONF_MINION_INCLUDES=os.path.join(paths.TMP_CONF_DIR, 'minion.d'),
    TMP_CONF_CLOUD_INCLUDES=os.path.join(paths.TMP_CONF_DIR, 'cloud.conf.d'),
    TMP_CONF_CLOUD_PROFILE_INCLUDES=os.path.join(paths.TMP_CONF_DIR, 'cloud.profiles.d'),
    TMP_CONF_CLOUD_PROVIDER_INCLUDES=os.path.join(paths.TMP_CONF_DIR, 'cloud.providers.d'),
    TMP_SUB_MINION_CONF_DIR=paths.TMP_SUB_MINION_CONF_DIR,
    TMP_SYNDIC_MASTER_CONF_DIR=paths.TMP_SYNDIC_MASTER_CONF_DIR,
    TMP_SYNDIC_MINION_CONF_DIR=paths.TMP_SYNDIC_MINION_CONF_DIR,
    TMP_SCRIPT_DIR=paths.TMP_SCRIPT_DIR,
    TMP_STATE_TREE=paths.TMP_STATE_TREE,
    TMP_PRODENV_STATE_TREE=paths.TMP_PRODENV_STATE_TREE,
    RUNNING_TESTS_USER=RUNNING_TESTS_USER,
    RUNTIME_CONFIGS={}
)
# <---- Tests Runtime Variables --------------------------------------------------------------------------------------
