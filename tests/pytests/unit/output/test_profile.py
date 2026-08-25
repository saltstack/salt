import pytest

import salt.output.profile as profile


@pytest.fixture
def configure_loader_modules():
    return {profile: {"__opts__": {"extension_modules": "", "color": False}}}


def test_no_states_found():
    """
    Simulate the result of the "profile" outputter with state.apply.
    i.e. salt-call --local state.apply --output=profile
    """
    data = {
        "local": {
            "no_|-states_|-states_|-None": {
                "result": False,
                "comment": "No Top file or master_tops data matches found. Please see master log for details.",
                "name": "No States",
                "changes": {},
                "__run_num__": 0,
            }
        }
    }

    expected_output = (
        "    ---------------------------------------\n"
        "    |    name   | mod.fun | duration (ms) |\n"
        "    ---------------------------------------\n"
        "    | No States | no.None |       -1.0000 |\n"
        "    ---------------------------------------"
    )

    ret = profile.output(data)
    assert expected_output in ret


def test_no_matching_sls():
    """
    Simulate the result of the "profile" outputter with state.sls.
    i.e. salt-call --local state.sls foo --output=profile
    """
    data = {"local": ["No matching sls found for 'foo' in env 'base'"]}

    expected_output = (
        "    ---------------------------------------------------------------------------\n"
        "    | name |                     mod.fun                      | duration (ms) |\n"
        "    ---------------------------------------------------------------------------\n"
        "    |  <>  | No matching sls found for 'foo' in env 'base'.No |       -1.0000 |\n"
        "    ---------------------------------------------------------------------------"
    )

    ret = profile.output(data)
    assert expected_output in ret


def test_output_with_grains_data():
    """
    Simulate the result of the "profile" outputter with grains data.
    i.e. salt-call --local grains.items --output=profile
    """
    grains_data = {
        "local": {
            "dns": {"nameservers": ["0.0.0.0", "1.1.1.1"], "search": ["dns.com"]},
            "fqdns": [],
            "disks": ["sda"],
            "ssds": ["nvme0n1"],
            "shell": "/bin/bash",
            "efi-secure-boot": False,
        }
    }

    ret = profile.output(grains_data)
    expected_ret = (
        "    ---------------------------------------------------------------------\n"
        "    |       name      |             mod.fun             | duration (ms) |\n"
        "    ---------------------------------------------------------------------\n"
        "    |        <>       |             dns.dns             |       -1.0000 |\n"
        "    ---------------------------------------------------------------------\n"
        "    |      disks      |           disks.disks           |       -1.0000 |\n"
        "    ---------------------------------------------------------------------\n"
        "    | efi-secure-boot | efi-secure-boot.efi-secure-boot |       -1.0000 |\n"
        "    ---------------------------------------------------------------------\n"
        "    |      fqdns      |           fqdns.fqdns           |       -1.0000 |\n"
        "    ---------------------------------------------------------------------\n"
        "    |      shell      |           shell.shell           |       -1.0000 |\n"
        "    ---------------------------------------------------------------------\n"
        "    |       ssds      |            ssds.ssds            |       -1.0000 |\n"
        "    ---------------------------------------------------------------------"
    )

    assert ret == expected_ret
