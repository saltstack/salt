import pytest
import salt.renderers.tomlmod
import salt.serializers.toml


@pytest.mark.skipif(
    salt.serializers.toml.HAS_TOML is False, reason="The 'toml' library is missing"
)
def test_toml_render_string():
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
    result = salt.renderers.tomlmod.render(data)

    assert result == expected_result
