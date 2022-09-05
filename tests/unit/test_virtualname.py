"""
    tests.unit.test_virtualname
    ~~~~~~~~~~~~~~~~~~~~
"""

import importlib.util
import logging
import os

from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class FakeEntry:
    def __init__(self, name, path, is_file=True):
        self.name = name
        self.path = path
        self._is_file = is_file

    def is_file(self):
        return self._is_file


class VirtualNameTestCase(TestCase):
    """
    Test that the virtualname is in the module name, to speed up lookup of
    modules.
    """

    maxDiff = None

    @staticmethod
    def _import_module(testpath):
        spec = importlib.util.spec_from_file_location("tmpmodule", testpath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _check_modules(self, path):
        """
        check modules in directory
        """
        ret = []
        for entry in os.listdir(path):
            name, path = os.path.splitext(os.path.basename(entry))[0], entry
            if name.startswith(".") or name.startswith("_"):
                continue
            if os.path.isfile(path) and not name.endswith(".py"):
                continue
            testpath = (
                path if os.path.isfile(path) else os.path.join(path, "__init__.py")
            )
            module = self._import_module(testpath)
            if hasattr(module, "__virtualname__"):
                if module.__virtualname__ not in name:
                    ret.append(
                        'Virtual name "{}" is not in the module filename "{}": {}'.format(
                            module.__virtualname__, name, path
                        )
                    )
        return ret

    def test_check_virtualname(self):
        """
        Test that the virtualname is in __name__ of the module
        """
        errors = []
        for entry in os.listdir(RUNTIME_VARS.SALT_CODE_DIR):
            name, path = os.path.splitext(os.path.basename(entry))[0], entry
            if name.startswith(".") or name.startswith("_") or not os.path.isdir(path):
                continue
            if name in ("cli", "defaults", "spm", "daemons", "ext", "templates"):
                continue
            if name == "cloud":
                entry = os.path.join(RUNTIME_VARS.SALT_CODE_DIR, "cloud", "clouds")
            errors.extend(self._check_modules(entry))
        for error in errors:
            log.critical(error)
        assert not errors
