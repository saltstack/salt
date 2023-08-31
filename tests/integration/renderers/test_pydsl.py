import os
import shutil
import textwrap

import pytest

import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from tests.support.case import ModuleCase


@pytest.mark.windows_whitelisted
class PyDSLRendererIncludeTestCase(ModuleCase):
    def setUp(self):
        self.directory_created = False
        if salt.utils.platform.is_windows():
            if not os.path.isdir("\\tmp"):
                os.mkdir("\\tmp")
                self.directory_created = True

    def tearDown(self):
        if salt.utils.platform.is_windows():
            if self.directory_created:
                shutil.rmtree("\\tmp")

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_rendering_includes(self):
        """
        This test is currently hard-coded to /tmp to work-around a seeming
        inability to load custom modules inside the pydsl renderers. This
        is a FIXME.
        """
        self.run_function("state.sls", ["pydsl.aaa"])

        expected = textwrap.dedent(
            """\
            X1
            X2
            X3
            Y1 extended
            Y2 extended
            Y3
            hello red 1
            hello green 2
            hello blue 3
            """
        )

        # Windows adds `linefeed` in addition to `newline`. There's also an
        # unexplainable space before the `linefeed`...
        if salt.utils.platform.is_windows():
            expected = (
                "X1 \r\n"
                "X2 \r\n"
                "X3 \r\n"
                "Y1 extended \r\n"
                "Y2 extended \r\n"
                "Y3 \r\n"
                "hello red 1 \r\n"
                "hello green 2 \r\n"
                "hello blue 3 \r\n"
            )

        try:
            with salt.utils.files.fopen("/tmp/output", "r") as f:
                ret = salt.utils.stringutils.to_unicode(f.read())
        finally:
            os.remove("/tmp/output")

        self.assertEqual(sorted(ret), sorted(expected))
