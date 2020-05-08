# -*- coding: utf-8 -*-
"""
Test the jinja module
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

import salt.utils.files

# Import Salt libs
import salt.utils.json
import salt.utils.yaml
from tests.support.case import ModuleCase
from tests.support.helpers import requires_system_grains

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS


class TestModulesJinja(ModuleCase):
    """
    Test the jinja map module
    """

    def _path(self, name, absolute=False):
        path = os.path.join("modules", "jinja", name)
        if absolute:
            return os.path.join(RUNTIME_VARS.BASE_FILES, path)
        else:
            return path

    def test_import_json(self):
        json_file = "osarchmap.json"
        ret = self.run_function("jinja.import_json", [self._path(json_file)])
        with salt.utils.files.fopen(self._path(json_file, absolute=True)) as fh_:
            self.assertDictEqual(salt.utils.json.load(fh_), ret)

    def test_import_yaml(self):
        yaml_file = "defaults.yaml"
        ret = self.run_function("jinja.import_yaml", [self._path(yaml_file)])
        with salt.utils.files.fopen(self._path(yaml_file, absolute=True)) as fh_:
            self.assertDictEqual(salt.utils.yaml.safe_load(fh_), ret)

    @requires_system_grains
    def test_load_map(self, grains):
        ret = self.run_function("jinja.load_map", [self._path("map.jinja"), "template"])

        with salt.utils.files.fopen(self._path("defaults.yaml", absolute=True)) as fh_:
            defaults = salt.utils.yaml.safe_load(fh_)
        with salt.utils.files.fopen(self._path("osarchmap.json", absolute=True)) as fh_:
            osarchmap = salt.utils.json.load(fh_)
        with salt.utils.files.fopen(
            self._path("osfamilymap.yaml", absolute=True)
        ) as fh_:
            osfamilymap = salt.utils.yaml.safe_load(fh_)
        with salt.utils.files.fopen(self._path("osmap.yaml", absolute=True)) as fh_:
            osmap = salt.utils.yaml.safe_load(fh_)
        with salt.utils.files.fopen(
            self._path("osfingermap.yaml", absolute=True)
        ) as fh_:
            osfingermap = salt.utils.yaml.safe_load(fh_)

        self.assertEqual(
            ret.get("arch"), osarchmap.get(grains["osarch"], {}).get("arch")
        )
        self.assertEqual(
            ret.get("config"),
            osfingermap.get(grains["osfinger"], {}).get(
                "config",
                osmap.get(grains["os"], {}).get(
                    "config",
                    osfamilymap.get(grains["os_family"], {}).get(
                        "config", defaults.get("template").get("config")
                    ),
                ),
            ),
        )
