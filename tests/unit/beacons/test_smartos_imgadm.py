# coding: utf-8

# Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Salt libs
import salt.beacons.smartos_imgadm as imgadm
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase

# Mock Results
MOCK_CLEAN_STATE = {"first_run": True, "images": []}
MOCK_IMAGE_NONE = {}
MOCK_IMAGE_ONE = {
    "00000000-0000-0000-0000-000000000001": {
        "description": "Example Image 1",
        "name": "example-1",
        "os": "smartos",
        "published": "2018-01-01T00:42:00Z",
        "source": "https://images.joyent.com",
        "version": "18.1.0",
    },
}
MOCK_IMAGE_TWO = {
    "00000000-0000-0000-0000-000000000001": {
        "description": "Example Image 1",
        "name": "example-1",
        "os": "smartos",
        "published": "2018-01-01T00:42:00Z",
        "source": "https://images.joyent.com",
        "version": "18.1.0",
    },
    "00000000-0000-0000-0000-000000000002": {
        "description": "Example Image 2",
        "name": "example-2",
        "os": "smartos",
        "published": "2018-01-01T00:42:00Z",
        "source": "https://images.joyent.com",
        "version": "18.2.0",
    },
}


class SmartOSImgAdmBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.imgadm
    """

    def setup_loader_modules(self):
        return {imgadm: {"__context__": {}, "__salt__": {}}}

    def test_non_list_config(self):
        """
        We only have minimal validation so we test that here
        """
        assert imgadm.validate({}) == (
            False,
            "Configuration for imgadm beacon must be a list!",
        )

    def test_imported_startup(self):
        """
        Test with one image and startup_import_event
        """
        # NOTE: this should yield 1 imported event
        with patch.dict(imgadm.IMGADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            imgadm.__salt__, {"imgadm.list": MagicMock(return_value=MOCK_IMAGE_ONE)}
        ):

            config = [{"startup_import_event": True}]
            assert imgadm.validate(config) == (True, "Valid beacon configuration")

            ret = imgadm.beacon(config)
            res = [
                {
                    "description": "Example Image 1",
                    "name": "example-1",
                    "os": "smartos",
                    "published": "2018-01-01T00:42:00Z",
                    "source": "https://images.joyent.com",
                    "tag": "imported/00000000-0000-0000-0000-000000000001",
                    "version": "18.1.0",
                }
            ]
            assert ret == res

    def test_imported_nostartup(self):
        """
        Test with one image and startup_import_event unset/false
        """
        # NOTE: this should yield 0 imported event
        with patch.dict(imgadm.IMGADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            imgadm.__salt__, {"imgadm.list": MagicMock(return_value=MOCK_IMAGE_ONE)}
        ):

            config = []

            assert imgadm.validate(config) == (True, "Valid beacon configuration")
            assert imgadm.beacon(config) == []

    def test_imported(self):
        """
        Test with one image and a new image added on the 2nd pass
        """
        # NOTE: this should yield 1 imported event
        with patch.dict(imgadm.IMGADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            imgadm.__salt__,
            {"imgadm.list": MagicMock(side_effect=[MOCK_IMAGE_ONE, MOCK_IMAGE_TWO])},
        ):

            config = []
            assert imgadm.validate(config) == (True, "Valid beacon configuration")

            # Initial pass (Initialized state and do not yield imported images at startup)
            imgadm.beacon(config)

            # Second pass (After importing a new image)
            ret = imgadm.beacon(config)
            res = [
                {
                    "description": "Example Image 2",
                    "name": "example-2",
                    "os": "smartos",
                    "published": "2018-01-01T00:42:00Z",
                    "source": "https://images.joyent.com",
                    "tag": "imported/00000000-0000-0000-0000-000000000002",
                    "version": "18.2.0",
                }
            ]

            assert ret == res

    def test_deleted(self):
        """
        Test with two images and one gets deletes
        """
        # NOTE: this should yield 1 deleted event
        with patch.dict(imgadm.IMGADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            imgadm.__salt__,
            {"imgadm.list": MagicMock(side_effect=[MOCK_IMAGE_TWO, MOCK_IMAGE_ONE])},
        ):

            config = []
            assert imgadm.validate(config) == (True, "Valid beacon configuration")

            # Initial pass (Initialized state and do not yield imported images at startup)
            imgadm.beacon(config)

            # Second pass (After deleting one image)
            ret = imgadm.beacon(config)
            res = [
                {
                    "description": "Example Image 2",
                    "name": "example-2",
                    "os": "smartos",
                    "published": "2018-01-01T00:42:00Z",
                    "source": "https://images.joyent.com",
                    "tag": "deleted/00000000-0000-0000-0000-000000000002",
                    "version": "18.2.0",
                }
            ]

            assert ret == res

    def test_complex(self):
        """
        Test with one image, delete both, import 2
        """
        # NOTE: this should yield 1 delete and 2 import events
        with patch.dict(imgadm.IMGADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            imgadm.__salt__,
            {
                "imgadm.list": MagicMock(
                    side_effect=[MOCK_IMAGE_ONE, MOCK_IMAGE_NONE, MOCK_IMAGE_TWO]
                )
            },
        ):

            config = []
            assert imgadm.validate(config), (True, "Valid beacon configuration")

            # Initial pass (Initialized state and do not yield imported images at startup)
            imgadm.beacon(config)

            # Second pass (After deleting one image)
            ret = imgadm.beacon(config)
            res = [
                {
                    "description": "Example Image 1",
                    "name": "example-1",
                    "os": "smartos",
                    "published": "2018-01-01T00:42:00Z",
                    "source": "https://images.joyent.com",
                    "tag": "deleted/00000000-0000-0000-0000-000000000001",
                    "version": "18.1.0",
                }
            ]
            assert ret == res

            # Third pass (After importing two images)
            ret = imgadm.beacon(config)
            res = [
                {
                    "description": "Example Image 1",
                    "name": "example-1",
                    "os": "smartos",
                    "published": "2018-01-01T00:42:00Z",
                    "source": "https://images.joyent.com",
                    "tag": "imported/00000000-0000-0000-0000-000000000001",
                    "version": "18.1.0",
                },
                {
                    "description": "Example Image 2",
                    "name": "example-2",
                    "os": "smartos",
                    "published": "2018-01-01T00:42:00Z",
                    "source": "https://images.joyent.com",
                    "tag": "imported/00000000-0000-0000-0000-000000000002",
                    "version": "18.2.0",
                },
            ]
            assert len(ret) == 2
            for item in ret:
                assert item in res
