# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase

# Import Salt libs
import salt.utils


class PyDSLRendererIncludeTestCase(ModuleCase):

    def test_rendering_includes(self):
        '''
        This test is currently hard-coded to /tmp to work-around a seeming
        inability to load custom modules inside the pydsl renderers. This
        is a FIXME.
        '''
        self.run_function('state.sls', ['pydsl.aaa'])

        expected = textwrap.dedent('''\
            X1
            X2
            X3
            Y1 extended
            Y2 extended
            Y3
            hello red 1
            hello green 2
            hello blue 3
            ''')

        # Windows adds `linefeed` in addition to `newline`. There's also an
        # unexplainable space before the `linefeed`...
        if salt.utils.is_windows():
            expected = 'X1 \r\n' \
                       'X2 \r\n' \
                       'X3 \r\n' \
                       'Y1 extended \r\n' \
                       'Y2 extended \r\n' \
                       'Y3 \r\n' \
                       'hello red 1 \r\n' \
                       'hello green 2 \r\n' \
                       'hello blue 3 \r\n'

        with salt.utils.fopen('/tmp/output', 'r') as f:
            ret = f.read()

        os.remove('/tmp/output')

        self.assertEqual(sorted(ret), sorted(expected))
