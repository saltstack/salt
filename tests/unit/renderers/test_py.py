# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    patch
)

# Import Salt libs
import salt.renderers.py as pyrender


class PyRendererTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {pyrender: {}}

    def test_py_render_string(self):
        data = 'print("lol", end="")'
        result = pyrender.render(data)

        # if this works, the whole python stack is loaded and run successfully
        self.assertEqual(result, "lol")
