import pytest
import salt.pillar


@pytest.fixture()
def makostack_basic_config(tmp_path):
    mako_config = tmp_path / "mako" / "mako.cfg"
    simple_pillar = tmp_path / "mako" / "present.yml"
    mako_config.parent.mkdir(parents=True, exist_ok=True)
    mako_config.write_text("present.yml\n\n\n")
    simple_pillar.write_text(
        """
some random:
  pillar values
have:
  - some
  - simple
  - data: in them
    """
    )

    yield mako_config


@pytest.fixture()
def makostack_basic_pillar(salt_master, grains, makostack_basic_config):
    opts = salt_master.config.copy()
    opts["ext_pillar"] = [{"makostack": [str(makostack_basic_config)]}]
    pillar_obj = salt.pillar.Pillar(opts, grains, "minion", "base")
    return pillar_obj


@pytest.fixture()
def config_with_missing_file(makostack_basic_config):
    with makostack_basic_config.open(mode="a") as f:
        print("missing.yml", file=f)
    return makostack_basic_config


@pytest.fixture()
def config_with_broken_file(makostack_basic_config):
    broken_yml = makostack_basic_config.parent / "broken.yml"
    broken_yml.write_text("foo:\nbar")
    with makostack_basic_config.open(mode="a") as f:
        print("broken.yml", file=f)
    return makostack_basic_config


@pytest.fixture()
def makostack_with_missing_file(makostack_basic_pillar, config_with_missing_file):
    expected_error = {
        "_errors": [
            "Failed to load ext_pillar makostack: MakoStack template `missing.yml` not found - aborting compilation."
        ]
    }
    yield makostack_basic_pillar, expected_error


@pytest.fixture()
def makostack_borked_pillar(
    makostack_basic_pillar, config_with_missing_file, config_with_broken_file
):
    config_file = config_with_missing_file
    with config_file.open(mode="a") as f:
        print("more_good.yml", file=f)
    more_good_yaml = config_file.parent / "more_good.yml"
    more_good_yaml.write_text("and: then some")
    return makostack_basic_pillar


def test_makostack_with_simple_config_should_return_expected_pillar(
    makostack_basic_pillar,
):
    expected_pillar = {
        "have": ["some", "simple", {"data": "in them"}],
        "some random": "pillar values",
    }
    ret = makostack_basic_pillar.compile_pillar()
    assert ret == expected_pillar


def test_makostack_with_basic_yaml_config_should_return_expected_pillar(
    tmp_path, salt_master, grains
):
    expected_pillar = {"simple": "data"}
    mako_config = tmp_path / "mako" / "mako.cfg"
    simple_pillar = tmp_path / "mako" / "simple.yml"
    mako_config.parent.mkdir(parents=True, exist_ok=True)
    mako_config.write_text("- simple.yml\n\n\n")
    simple_pillar.write_text("simple: data")
    opts = salt_master.config.copy()
    opts["ext_pillar"] = [{"makostack": [str(mako_config)]}]
    pillar_obj = salt.pillar.Pillar(opts, grains, "minion", "base")

    ret = pillar_obj.compile_pillar()

    assert ret == expected_pillar


def test_makostack_with_missing_and_broken_files_but_default_behavior_should_ignore_missing_and_broken_files(
    makostack_borked_pillar,
):
    expected_pillar = {
        "have": ["some", "simple", {"data": "in them"}],
        "some random": "pillar values",
        "and": "then some",
    }
    ret = makostack_borked_pillar.compile_pillar()
    assert ret == expected_pillar


@pytest.mark.xfail(reason="not yet supported")
def test_makostack_with_fail_on_missing_file_should_produce_expected_error(
    makostack_with_missing_file,
):
    pillar_obj, expected_error = makostack_with_missing_file
    pillar_obj.opts["ext_pillar"][0]["makostack"].append(
        {"config": {"fail_on_missing_file": True}}
    )
    ret = pillar_obj.compile_pillar()
    assert ret == expected_error


@pytest.mark.xfail(reason="not yet supported")
def test_makostack_with_fail_on_parse_error_should_produce_expected_error(
    makostack_borked_pillar,
):
    expected_error_start = "Failed to load ext_pillar makostack: Invalid MakoStack template `broken.yml` - aborting compilation:\n"
    makostack_borked_pillar.opts["ext_pillar"][0]["makostack"].append(
        {"config": {"fail_on_parse_error": True}}
    )

    ret = makostack_borked_pillar.compile_pillar()

    assert "_errors" in ret
    assert ret["_errors"][0].startswith(expected_error_start)
