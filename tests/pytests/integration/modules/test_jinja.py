"""
Test the jinja module
"""

import os

import salt.utils.files
import salt.utils.json
import salt.utils.yaml
from tests.support.runtests import RUNTIME_VARS


def _path(name, absolute=False):
    path = os.path.join("modules", "jinja", name)
    if absolute:
        return os.path.join(RUNTIME_VARS.BASE_FILES, path)
    else:
        return path


def test_import_json(salt_cli, salt_minion):
    json_file = "osarchmap.json"
    ret = salt_cli.run("jinja.import_json", _path(json_file), minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(_path(json_file, absolute=True)) as fh_:
        assert salt.utils.json.load(fh_) == ret.data


def test_import_yaml(salt_cli, salt_minion):
    yaml_file = "defaults.yaml"
    ret = salt_cli.run("jinja.import_yaml", _path(yaml_file), minion_tgt=salt_minion.id)
    with salt.utils.files.fopen(_path(yaml_file, absolute=True)) as fh_:
        assert salt.utils.yaml.safe_load(fh_) == ret.data


def test_load_map(grains, salt_cli, salt_minion):
    ret = salt_cli.run(
        "jinja.load_map", _path("map.jinja"), "template", minion_tgt=salt_minion.id
    )

    assert isinstance(
        ret.data, dict
    ), f"failed to return dictionary from jinja.load_map: {ret}"

    with salt.utils.files.fopen(_path("defaults.yaml", absolute=True)) as fh_:
        defaults = salt.utils.yaml.safe_load(fh_)
    with salt.utils.files.fopen(_path("osarchmap.json", absolute=True)) as fh_:
        osarchmap = salt.utils.json.load(fh_)
    with salt.utils.files.fopen(_path("osfamilymap.yaml", absolute=True)) as fh_:
        osfamilymap = salt.utils.yaml.safe_load(fh_)
    with salt.utils.files.fopen(_path("osmap.yaml", absolute=True)) as fh_:
        osmap = salt.utils.yaml.safe_load(fh_)
    with salt.utils.files.fopen(_path("osfingermap.yaml", absolute=True)) as fh_:
        osfingermap = salt.utils.yaml.safe_load(fh_)

    assert ret.data.get("arch") == osarchmap.get(grains["osarch"], {}).get("arch")
    assert ret.data.get("config") == osfingermap.get(grains["osfinger"], {}).get(
        "config",
        osmap.get(grains["os"], {}).get(
            "config",
            osfamilymap.get(grains["os_family"], {}).get(
                "config", defaults.get("template").get("config")
            ),
        ),
    )
