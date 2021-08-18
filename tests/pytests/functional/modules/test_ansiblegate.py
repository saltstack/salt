import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="Not supported on Windows"),
    pytest.mark.skip_if_binaries_missing(
        "ansible",
        "ansible-doc",
        "ansible-playbook",
        check_all=True,
        reason="ansible is not installed",
    ),
]


@pytest.fixture
def ansible_ping_func(modules):
    if "ansible.system.ping" in modules:
        # we need to go by getattr() because salt's loader will try to find "system" in the dictionary and fail
        # The ansible hack injects, in this case, "system.ping" as an attribute to the loaded module
        return getattr(modules.ansible, "system.ping")

    if "ansible.ping" in modules:
        # Ansible >= 2.10
        return modules.ansible.ping

    pytest.fail("Where is the ping function these days in Ansible?!")


def test_ansible_functions_loaded(ansible_ping_func):
    """
    Test that the ansible functions are actually loaded
    """
    ret = ansible_ping_func()
    assert ret == {"ping": "pong"}


def test_passing_data_to_ansible_modules(ansible_ping_func):
    """
    Test that the ansible functions are actually loaded
    """
    expected = "foobar"
    ret = ansible_ping_func(data=expected)
    assert ret == {"ping": expected}
