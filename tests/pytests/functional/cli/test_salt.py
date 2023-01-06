import pytest

import salt.version


@pytest.mark.windows_whitelisted
def test_versions_report(salt_cli):
    """
    Test that we can re-parse the version report back into
    a similar format with the necessary headers
    """
    expected = salt.version.versions_information()
    # sanitize expected of unnnecessary whitespace
    for _, section in expected.items():
        for key in section:
            if isinstance(section[key], str):
                section[key] = section[key].strip()

    ret = salt_cli.run("--versions-report")
    assert ret.stdout
    ret_lines = ret.stdout.split("\n")

    assert ret_lines
    # sanitize lines
    ret_lines = [line.strip() for line in ret_lines]

    for header in expected:
        assert "{}:".format(header) in ret_lines

    ret_dict = {}
    expected_keys = set()
    for line in ret_lines:
        if not line:
            continue
        if line.endswith(":"):
            assert not expected_keys
            current_header = line.rstrip(":")
            assert current_header in expected
            ret_dict[current_header] = {}
            expected_keys = set(expected[current_header].keys())
        else:
            key, *value_list = line.split(":", 1)
            assert value_list
            assert len(value_list) == 1
            value = value_list[0].strip()
            if value == "Not Installed":
                value = None
            ret_dict[current_header][key] = value
            assert key in expected_keys
            expected_keys.remove(key)
    assert not expected_keys
