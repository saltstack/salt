# -*- coding: utf-8 -*-
'''
    tests.unit.test_virtualname
    ~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

try:
    import importlib.util
except ImportError:
    import imp

# Import Salt libs
import salt.ext.six as six

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


class FakeEntry(object):
    def __init__(self, name, path, is_file=True):
        self.name = name
        self.path = path
        self._is_file = is_file

    def is_file(self):
        return self._is_file


class VirtualNameTestCase(TestCase):
    '''
    Test that the virtualname is in the module name, to speed up lookup of
    modules.
    '''
    maxDiff = None

    @staticmethod
    def _import_module(testpath):
        if six.PY3:
            spec = importlib.util.spec_from_file_location('tmpmodule', testpath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            fp, pathname, description = imp.find_module('tmpmodule', testpath)
            try:
                module = imp.load_module('tmpmodule', fp, pathname, description)
            finally:
                # Since we may exit via an exception, close fp explicitly.
                if fp:
                    fp.close()
        return module

    def _check_modules(self, path):
        '''
        check modules in directory
        '''
        ret = []
        for entry in os.listdir(path):
            name, path = os.path.splitext(os.path.basename(entry))[0], entry
            if name.startswith('.') or name.startswith('_'):
                continue
            if os.path.isfile(path) and not name.endswith('.py'):
                continue
            testpath = path if os.path.isfile(path) else os.path.join(path, '__init__.py')
            module = self._import_module(testpath)
            if hasattr(module, '__virtualname__'):
                if module.__virtualname__ not in name:
                    ret.append(
                        'Virtual name "{0}" is not in the module filename "{1}": {2}'.format(
                            module.__virtualname__,
                            name,
                            path
                        )
                    )
        return ret

    def test_check_virtualname(self):
        '''
        Test that the virtualname is in __name__ of the module
        '''
        errors = []
        for entry in os.listdir(os.path.join(RUNTIME_VARS.CODE_DIR, 'salt/')):
            name, path = os.path.splitext(os.path.basename(entry))[0], entry
            if name.startswith('.') or name.startswith('_') or not os.path.isdir(path):
                continue
            if name in ('cli', 'defaults', 'spm', 'daemons', 'ext', 'templates'):
                continue
            if name == 'cloud':
                entry = os.path.join(RUNTIME_VARS.CODE_DIR, 'salt', 'cloud', 'clouds')
            errors.extend(self._check_modules(entry))
        for error in errors:
            log.critical(error)
        assert not errors
