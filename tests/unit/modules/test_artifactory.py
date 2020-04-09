# -*- coding: utf-8 -*-

# Import pytohn libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.modules.artifactory as artifactory

# Import Salt testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ArtifactoryTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {artifactory: {}}

    def test_artifact_get_metadata(self):
        with patch(
            "salt.modules.artifactory._get_artifact_metadata_xml",
            MagicMock(
                return_value="""<?xml version="1.0" encoding="UTF-8"?>
                <metadata>
                  <groupId>com.company.sampleapp.web-module</groupId>
                  <artifactId>web</artifactId>
                  <versioning>
                    <latest>1.1_RC11</latest>
                    <release>1.0.1</release>
                    <versions>
                      <version>1.0_RC20</version>
                      <version>1.0_RC22</version>
                    </versions>
                    <lastUpdated>20140623120632</lastUpdated>
                  </versioning>
                </metadata>
            """
            ),
        ):
            metadata = artifactory._get_artifact_metadata(
                artifactory_url="http://artifactory.example.com/artifactory",
                repository="libs-releases",
                group_id="com.company.sampleapp.web-module",
                artifact_id="web",
                headers={},
            )
            self.assertEqual(metadata["latest_version"], "1.1_RC11")

    def test_snapshot_version_get_metadata(self):
        with patch(
            "salt.modules.artifactory._get_snapshot_version_metadata_xml",
            MagicMock(
                return_value="""<?xml version="1.0" encoding="UTF-8"?>
                    <metadata>
                      <groupId>com.company.sampleapp.web-module</groupId>
                      <artifactId>web</artifactId>
                      <version>1.1_RC8-SNAPSHOT</version>
                      <versioning>
                        <snapshot>
                          <timestamp>20140418.150212</timestamp>
                          <buildNumber>1</buildNumber>
                        </snapshot>
                        <lastUpdated>20140623104055</lastUpdated>
                        <snapshotVersions>
                          <snapshotVersion>
                            <extension>pom</extension>
                            <value>1.1_RC8-20140418.150212-1</value>
                            <updated>20140418150212</updated>
                          </snapshotVersion>
                          <snapshotVersion>
                            <extension>war</extension>
                            <value>1.1_RC8-20140418.150212-1</value>
                            <updated>20140418150212</updated>
                          </snapshotVersion>
                        </snapshotVersions>
                      </versioning>
                    </metadata>
                """
            ),
        ):
            metadata = artifactory._get_snapshot_version_metadata(
                artifactory_url="http://artifactory.example.com/artifactory",
                repository="libs-releases",
                group_id="com.company.sampleapp.web-module",
                artifact_id="web",
                version="1.1_RC8-SNAPSHOT",
                headers={},
            )
            self.assertEqual(
                metadata["snapshot_versions"]["war"], "1.1_RC8-20140418.150212-1"
            )

    def test_artifact_metadata_url(self):
        metadata_url = artifactory._get_artifact_metadata_url(
            artifactory_url="http://artifactory.example.com/artifactory",
            repository="libs-releases",
            group_id="com.company.sampleapp.web-module",
            artifact_id="web",
        )

        self.assertEqual(
            metadata_url,
            "http://artifactory.example.com/artifactory/libs-releases/com/company/sampleapp/web-module/web/maven-metadata.xml",
        )

    def test_snapshot_version_metadata_url(self):
        metadata_url = artifactory._get_snapshot_version_metadata_url(
            artifactory_url="http://artifactory.example.com/artifactory",
            repository="libs-snapshots",
            group_id="com.company.sampleapp.web-module",
            artifact_id="web",
            version="1.0_RC10-SNAPSHOT",
        )

        self.assertEqual(
            metadata_url,
            "http://artifactory.example.com/artifactory/libs-snapshots/com/company/sampleapp/web-module/web/1.0_RC10-SNAPSHOT/maven-metadata.xml",
        )

    def test_construct_url_for_released_version(self):
        artifact_url, file_name = artifactory._get_release_url(
            repository="libs-releases",
            group_id="com.company.sampleapp.web-module",
            artifact_id="web",
            packaging="war",
            artifactory_url="http://artifactory.example.com/artifactory",
            version="1.0_RC20",
        )

        self.assertEqual(
            artifact_url,
            "http://artifactory.example.com/artifactory/libs-releases/com/company/sampleapp/web-module/web/1.0_RC20/web-1.0_RC20.war",
        )
        self.assertEqual(file_name, "web-1.0_RC20.war")

    def test_construct_url_for_snapshot_version(self):
        with patch(
            "salt.modules.artifactory._get_snapshot_version_metadata",
            MagicMock(
                return_value={
                    "snapshot_versions": {"war": "1.0_RC10-20131127.105838-2"}
                }
            ),
        ):

            artifact_url, file_name = artifactory._get_snapshot_url(
                artifactory_url="http://artifactory.example.com/artifactory",
                repository="libs-snapshots",
                group_id="com.company.sampleapp.web-module",
                artifact_id="web",
                version="1.0_RC10-SNAPSHOT",
                packaging="war",
                headers={},
            )

            self.assertEqual(
                artifact_url,
                "http://artifactory.example.com/artifactory/libs-snapshots/com/company/sampleapp/web-module/web/1.0_RC10-SNAPSHOT/web-1.0_RC10-20131127.105838-2.war",
            )
            self.assertEqual(file_name, "web-1.0_RC10-20131127.105838-2.war")
