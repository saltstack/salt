"""
Integration tests for the ini_manage state
"""

import pytest


def test_options_present(salt_call_cli):
    """
    test ini.options_present when the file
    does not exist and then run it again
    when it does exist and run it again when
    we want to add more sections to the ini
    """
    with pytest.helpers.temp_file("ini_file.ini") as tpath:
        content = """
        test_ini:
          ini.options_present:
            - name: {}
            - sections:
                general:
                  server_hostname: foo.com
                  server_port: 1234
        """.format(
            tpath
        )

        with pytest.helpers.temp_state_file("manage_ini.sls", content) as sfpath:
            ret = salt_call_cli.run("--local", "state.apply", "manage_ini")
            assert ret.json[next(iter(ret.json))]["changes"] == {
                "general": {
                    "before": None,
                    "after": {"server_hostname": "foo.com", "server_port": "1234"},
                }
            }

        content = """
        test_ini:
          ini.options_present:
            - name: {}
            - sections:
                general:
                  server_hostname: foo.com
                  server_port: 1234
                  server_user: saltfoo
        """.format(
            tpath
        )

        with pytest.helpers.temp_state_file("manage_ini.sls", content) as sfpath:
            # check to see adding a new section works
            ret = salt_call_cli.run("--local", "state.apply", "manage_ini")
            assert ret.json[next(iter(ret.json))]["changes"] == {
                "general": {"server_user": {"before": None, "after": "saltfoo"}}
            }

            # check when no changes are expected
            ret = salt_call_cli.run("--local", "state.apply", "manage_ini")
            assert ret.json[next(iter(ret.json))]["changes"] == {}
