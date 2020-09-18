import salt.renderers.py as pyrender
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class PyRendererTestCase(TestCase, LoaderModuleMockMixin):
    """
    Class for testing PyRenderer.
    """

    def setup_loader_modules(self):
        return {pyrender: {}}

    def test_py_render_string(self):
        data = 'print("lol", end="")'
        result = pyrender.render(data)

        # if this works, the whole python stack is loaded and run successfully
        self.assertEqual(result, "lol")
