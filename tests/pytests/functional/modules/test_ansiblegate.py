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
def ansible(modules):
    return modules.ansible


def test_short_alias(modules, ansible):
    """
    Test that the ansible functions are actually loaded and we can target using the short alias.
    """
    ret = ansible.ping()
    assert ret == {"ping": "pong"}

    ansible_ping_func = None
    if "ansible.system.ping" in modules:
        # we need to go by getattr() because salt's loader will try to find "system" in the dictionary and fail
        # The ansible hack injects, in this case, "system.ping" as an attribute to the loaded module
        ansible_ping_func = getattr(modules.ansible, "system.ping")
        # Make sure we don't set the full ansible module
        assert "ansible.ansible.system.ping" not in modules
    elif "ansible.builtin.ping" in modules:
        # Ansible >= 2.14
        # we need to go by getattr() because salt's loader will try to find "builtin" in the dictionary and fail
        # The ansible hack injects, in this case, "builtin.ping" as an attribute to the loaded module
        ansible_ping_func = getattr(modules.ansible, "builtin.ping")
        # Make sure we don't set the full ansible module
        assert "ansible.ansible.builtin.ping" not in modules

    # if ansible_ping_func is None, then it's ok, we already ran 'ping' at the
    # top if this test, so it worked.
    if ansible_ping_func:
        ret = ansible_ping_func()
        assert ret == {"ping": "pong"}


def test_passing_data_to_ansible_modules(ansible):
    """
    Test that the ansible functions are actually loaded
    """
    expected = "foobar"
    ret = ansible.ping(data=expected)
    assert ret == {"ping": expected}
