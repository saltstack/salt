import pytest
import salt.modules.ansiblegate as ansiblegate

pytestmark = [
    pytest.mark.skipif(ansiblegate.ansible is None, reason="Ansible is not installed"),
    pytest.mark.skip_on_windows(reason="Not supported on Windows"),
]


def test_ansible_functions_loaded(modules):
    """
    Test that the ansible functions are actually loaded
    """
    if "ansible.system.ping" in modules:
        # we need to go by getattr() because salt's loader will try to find "system" in the dictionary and fail
        # The ansible hack injects, in this case, "system.ping" as an attribute to the loaded module
        ret = getattr(modules.ansible, "system.ping")()
    elif "ansible.ping" in modules:
        # Ansible >= 2.10
        ret = modules.ansible.ping()
    else:
        pytest.fail("Where is the ping function these days in Ansible?!")

    ret.pop("timeout", None)
    assert ret == {"ping": "pong"}
