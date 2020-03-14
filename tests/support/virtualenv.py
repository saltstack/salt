# -*- coding: utf-8 -*-
'''
helper for creating virtualenv's in tests
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import shutil
import tempfile

# Import salt libs
import salt.utils.path
import salt.utils.platform

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.helpers import patched_environ


class VirtualEnvHelper(ModuleCase):

    def setUp(self):
        self.venv_test_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        # Remove the venv test directory
        self.addCleanup(shutil.rmtree, self.venv_test_dir, ignore_errors=True)
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')
        self.pip_temp = os.path.join(self.venv_test_dir, '.pip-temp')
        if not os.path.isdir(self.pip_temp):
            os.makedirs(self.pip_temp)
        self.patched_environ = patched_environ(
            PIP_SOURCE_DIR='',
            PIP_BUILD_DIR='',
            __cleanup__=[k for k in os.environ if k.startswith('PIP_')]
        )
        self.patched_environ.__enter__()
        self.addCleanup(self.patched_environ.__exit__)

    def _create_virtualenv(self, path):
        '''
        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, one windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        '''
        try:
            if salt.utils.platform.is_windows():
                python = os.path.join(sys.real_prefix, os.path.basename(sys.executable))
            else:
                python_binary_names = [
                    'python{}.{}'.format(*sys.version_info),
                    'python{}'.format(*sys.version_info),
                    'python'
                ]
                for binary_name in python_binary_names:
                    python = os.path.join(sys.real_prefix, 'bin', binary_name)
                    if os.path.exists(python):
                        break
                else:
                    self.fail(
                        'Couldn\'t find a python binary name under \'{}\' matching: {}'.format(
                            os.path.join(sys.real_prefix, 'bin'),
                            python_binary_names
                        )
                    )
            # We're running off a virtualenv, and we don't want to create a virtualenv off of
            # a virtualenv
            kwargs = {'python': python}
        except AttributeError:
            # We're running off of the system python
            kwargs = {}
        self.run_function('virtualenv.create', [path], **kwargs)
