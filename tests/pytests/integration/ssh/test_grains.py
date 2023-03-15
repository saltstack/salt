import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(scope="module")
def grains_filter_by_lookup(salt_ssh_cli):
    ret = salt_ssh_cli.run("grains.get", "os")
    assert ret.returncode == 0
    assert ret.data
    os = ret.data

    return {
        "common": {
            "has_common": True,
        },
        "custom_default": {
            "defaulted": True,
        },
        "merge": {
            "merged": True,
        },
        os: {
            "filtered": True,
        },
    }


@pytest.fixture(scope="module")
def grains_filter_by_default():
    return {
        "common": {
            "has_common": True,
        },
        "custom_default": {
            "defaulted": True,
        },
        "merge": {
            "merged": True,
        },
    }


@pytest.fixture(scope="module")
def grains_filter_by_states(
    salt_master, salt_ssh_cli, grains_filter_by_lookup, grains_filter_by_default
):
    filter_content = f"{{%- set lookup = {grains_filter_by_lookup} %}}"
    default_content = f"{{%- set lookup = {grains_filter_by_default} %}}"
    content = r"""
{%- set res = salt["grains.filter_by"](lookup, grain="os", merge=lookup["merge"], base="common", default="custom_default") %}
grains-filter-by:
  file.managed:
    - name: {{ salt["temp.file"]() }}
    - context: {{ res | json }}
    """
    try:
        with salt_master.state_tree.base.temp_file(
            "grains_filter_by.sls", filter_content + content
        ):
            with salt_master.state_tree.base.temp_file(
                "grains_filter_by_default.sls", default_content + content
            ):
                ret = salt_ssh_cli.run("--regen-thin", "test.true")
                assert ret.returncode == 0
                yield
    finally:
        salt_ssh_cli.run("--regen-thin", "test.true")


def test_grains_id(salt_ssh_cli):
    """
    Test salt-ssh grains id work for localhost.
    """
    ret = salt_ssh_cli.run("grains.get", "id")
    assert ret.returncode == 0
    assert ret.data == "localhost"


def test_grains_items(salt_ssh_cli):
    """
    test grains.items with salt-ssh
    """
    ret = salt_ssh_cli.run("grains.items")
    assert ret.returncode == 0
    assert ret.data
    assert isinstance(ret.data, dict)
    if salt.utils.platform.is_darwin():
        grain = "Darwin"
    elif salt.utils.platform.is_aix():
        grain = "AIX"
    elif salt.utils.platform.is_freebsd():
        grain = "FreeBSD"
    else:
        grain = "Linux"
    assert ret.data["kernel"] == grain


def test_grains_filter_by(salt_ssh_cli, grains_filter_by_lookup):
    """
    test grains.filter_by with salt-ssh
    """
    ret = salt_ssh_cli.run(
        "grains.filter_by",
        grains_filter_by_lookup,
        grain="os",
        merge=grains_filter_by_lookup["merge"],
        base="common",
        default="custom_default",
    )
    assert ret.returncode == 0
    assert ret.data
    assert "has_common" in ret.data
    assert "filtered" in ret.data
    assert "merged" in ret.data
    assert "defaulted" not in ret.data


@pytest.mark.usefixtures("grains_filter_by_states")
def test_grains_filter_by_jinja(salt_ssh_cli):
    """
    test grains.filter_by during template rendering with salt-ssh
    """
    ret = salt_ssh_cli.run("state.show_sls", "grains_filter_by")
    assert ret.returncode == 0
    assert ret.data
    rendered = ret.data["grains-filter-by"]["file"][1]["context"]

    assert "has_common" in rendered
    assert "filtered" in rendered
    assert "merged" in rendered
    assert "defaulted" not in rendered


def test_grains_filter_by_default(salt_ssh_cli, grains_filter_by_default):
    """
    test grains.filter_by with salt-ssh and default parameter
    """
    ret = salt_ssh_cli.run(
        "grains.filter_by",
        grains_filter_by_default,
        grain="os",
        merge=grains_filter_by_default["merge"],
        base="common",
        default="custom_default",
    )
    assert ret.returncode == 0
    assert ret.data
    assert "has_common" in ret.data
    assert "merged" in ret.data
    assert "defaulted" in ret.data


@pytest.mark.usefixtures("grains_filter_by_states")
def test_grains_filter_by_default_jinja(salt_ssh_cli, grains_filter_by_default):
    """
    test grains.filter_by during template rendering with salt-ssh and default parameter
    """
    ret = salt_ssh_cli.run("state.show_sls", "grains_filter_by_default")
    assert ret.returncode == 0
    assert ret.data
    rendered = ret.data["grains-filter-by"]["file"][1]["context"]

    assert "has_common" in rendered
    assert "merged" in rendered
    assert "defaulted" in rendered
