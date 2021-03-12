import os

import salt.wheel
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.unit import TestCase


class WheelPillarRootsTest(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self.wheel = salt.wheel.Wheel(dict(self.get_config("client_config")))
        self.pillar_dir = self.wheel.opts["pillar_roots"]["base"][0]
        self.traversed_dir = os.path.dirname(self.pillar_dir)

    def tearDown(self):
        try:
            os.remove(os.path.join(self.pillar_dir, "foo"))
        except OSError:
            pass
        try:
            os.remove(os.path.join(self.traversed_dir, "foo"))
        except OSError:
            pass
        del self.wheel

    def test_write(self):
        ret = self.wheel.cmd(
            "pillar_roots.write", kwarg={"data": "foo: bar", "path": "foo"}
        )
        assert os.path.exists(os.path.join(self.pillar_dir, "foo"))
        assert ret.find("Wrote data to file") != -1

    def test_cvr_2021_25282(self):
        ret = self.wheel.cmd(
            "pillar_roots.write", kwarg={"data": "foo", "path": "../foo"}
        )
        assert not os.path.exists(os.path.join(self.traversed_dir, "foo"))
        assert ret.find("Invalid path") != -1
