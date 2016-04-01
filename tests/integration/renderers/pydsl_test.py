# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import textwrap

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../')

# Import Salt libs
import integration
import salt.utils


class PyDSLRendererIncludeTestCase(integration.ModuleCase):

    def test_rendering_includes(self):
        '''
        This test is currently hard-coded to /tmp to work-around a seeming
        inability to load custom modules inside the pydsl renderers. This
        is a FIXME.
        '''
        try:
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

            with salt.utils.fopen('/tmp/output', 'r') as f:
                self.assertEqual(sorted(f.read()), sorted(expected))

        finally:
            os.remove('/tmp/output')

if __name__ == '__main__':
    from integration import run_tests
    tests = [PyDSLRendererIncludeTestCase]
    run_tests(*tests, needs_daemon=True)
