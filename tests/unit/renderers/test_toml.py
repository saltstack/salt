# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.renderers.toml as toml
import salt.serializers.toml

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf


@skipIf(not salt.serializers.toml.available, "The 'toml' library is missing")
class TOMLRendererTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {toml: {}}

    def test_toml_render_string(self):
        data = """[[user-sshkey."ssh_auth.present"]]
                    user = "username"
                    [[user-sshkey."ssh_auth.present"]]
                    config = "%h/.ssh/authorized_keys"
                    [[user-sshkey."ssh_auth.present"]]
                    names = [
                      "hereismykey",
                      "anotherkey"
                    ]
                """
        expected_result = {
            "user-sshkey": {
                "ssh_auth.present": [
                    {"user": "username"},
                    {"config": "%h/.ssh/authorized_keys"},
                    {"names": ["hereismykey", "anotherkey"]},
                ]
            }
        }
        result = toml.render(data)

        self.assertEqual(result, expected_result)
