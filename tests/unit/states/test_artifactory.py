# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.artifactory as artifactory

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ArtifactoryTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.artifactory
    """

    def setup_loader_modules(self):
        return {artifactory: {}}

    # 'downloaded' function tests: 1

    def test_downloaded(self):
        """
        Test to ensures that the artifact from artifactory exists at
        given location.
        """
        name = "jboss"
        arti_url = "http://artifactory.intranet.example.com/artifactory"
        artifact = {
            "artifactory_url": arti_url,
            "artifact_id": "module",
            "repository": "libs-release-local",
            "packaging": "jar",
            "group_id": "com.company.module",
            "classifier": "sources",
            "version": "1.0",
        }

        ret = {"name": name, "result": False, "changes": {}, "comment": ""}

        mck = MagicMock(return_value={"status": False, "changes": {}, "comment": ""})
        with patch.dict(artifactory.__salt__, {"artifactory.get_release": mck}):
            self.assertDictEqual(artifactory.downloaded(name, artifact), ret)

        with patch.object(
            artifactory,
            "__fetch_from_artifactory",
            MagicMock(side_effect=Exception("error")),
        ):
            ret = artifactory.downloaded(name, artifact)
            self.assertEqual(ret["result"], False)
            self.assertEqual(ret["comment"], "error")

    # 'downloaded test=True' function tests: 1

    def test_downloaded_test_true(self):
        """
        Test to ensures that the artifact from artifactory exists at
        given location.
        """
        name = "jboss"
        arti_url = "http://artifactory.intranet.example.com/artifactory"
        artifact = {
            "artifactory_url": arti_url,
            "artifact_id": "module",
            "repository": "libs-release-local",
            "packaging": "jar",
            "group_id": "com.company.module",
            "classifier": "sources",
            "version": "1.0",
        }

        ret = {
            "name": name,
            "result": True,
            "changes": {},
            "comment": "Artifact would be downloaded from URL: http://artifactory.intranet.example.com/artifactory",
        }

        mck = MagicMock(return_value={"status": False, "changes": {}, "comment": ""})
        with patch.dict(artifactory.__salt__, {"artifactory.get_release": mck}):
            with patch.dict(artifactory.__opts__, {"test": True}):
                self.assertDictEqual(artifactory.downloaded(name, artifact), ret)

        with patch.object(
            artifactory,
            "__fetch_from_artifactory",
            MagicMock(side_effect=Exception("error")),
        ):
            ret = artifactory.downloaded(name, artifact)
            self.assertEqual(ret["result"], False)
            self.assertEqual(ret["comment"], "error")
