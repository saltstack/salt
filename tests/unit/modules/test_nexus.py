# -*- coding: utf-8 -*-

# Import pytohn libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.modules.nexus as nexus

# Import Salt testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class nexusTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {nexus: {}}

    def test_artifact_get_metadata(self):
        with patch(
            "salt.modules.nexus._get_artifact_metadata_xml",
            MagicMock(
                return_value="""<?xml version="1.0" encoding="UTF-8"?>
<metadata>
  <groupId>com.company.sampleapp.web-module</groupId>
  <artifactId>web</artifactId>
  <versioning>
    <release>0.1.0</release>
    <versions>
      <version>0.0.1</version>
      <version>0.0.2</version>
      <version>0.0.3</version>
      <version>0.1.0</version>
    </versions>
    <lastUpdated>20171010143552</lastUpdated>
  </versioning>
</metadata>"""
            ),
        ):
            metadata = nexus._get_artifact_metadata(
                nexus_url="http://nexus.example.com/repository",
                repository="libs-releases",
                group_id="com.company.sampleapp.web-module",
                artifact_id="web",
                headers={},
            )
            self.assertEqual(metadata["latest_version"], "0.1.0")

    def test_snapshot_version_get_metadata(self):
        with patch(
            "salt.modules.nexus._get_snapshot_version_metadata_xml",
            MagicMock(
                return_value="""<?xml version="1.0" encoding="UTF-8"?>
<metadata modelVersion="1.1.0">
  <groupId>com.company.sampleapp.web-module</groupId>
  <artifactId>web</artifactId>
  <version>0.0.2-SNAPSHOT</version>
  <versioning>
    <snapshot>
      <timestamp>20170920.212353</timestamp>
      <buildNumber>3</buildNumber>
    </snapshot>
    <lastUpdated>20171112171500</lastUpdated>
    <snapshotVersions>
      <snapshotVersion>
        <classifier>sans-externalized</classifier>
        <extension>jar</extension>
        <value>0.0.2-20170920.212353-3</value>
        <updated>20170920212353</updated>
      </snapshotVersion>
      <snapshotVersion>
        <classifier>dist</classifier>
        <extension>zip</extension>
        <value>0.0.2-20170920.212353-3</value>
        <updated>20170920212353</updated>
      </snapshotVersion>
    </snapshotVersions>
  </versioning>
</metadata>"""
            ),
        ):
            metadata = nexus._get_snapshot_version_metadata(
                nexus_url="http://nexus.example.com/repository",
                repository="libs-releases",
                group_id="com.company.sampleapp.web-module",
                artifact_id="web",
                version="0.0.2-SNAPSHOT",
                headers={},
            )
            self.assertEqual(
                metadata["snapshot_versions"]["dist"], "0.0.2-20170920.212353-3"
            )

    def test_artifact_metadata_url(self):
        metadata_url = nexus._get_artifact_metadata_url(
            nexus_url="http://nexus.example.com/repository",
            repository="libs-releases",
            group_id="com.company.sampleapp.web-module",
            artifact_id="web",
        )

        self.assertEqual(
            metadata_url,
            "http://nexus.example.com/repository/libs-releases/com/company/sampleapp/web-module/web/maven-metadata.xml",
        )

    def test_snapshot_version_metadata_url(self):
        metadata_url = nexus._get_snapshot_version_metadata_url(
            nexus_url="http://nexus.example.com/repository",
            repository="libs-snapshots",
            group_id="com.company.sampleapp.web-module",
            artifact_id="web",
            version="0.0.2-SNAPSHOT",
        )

        self.assertEqual(
            metadata_url,
            "http://nexus.example.com/repository/libs-snapshots/com/company/sampleapp/web-module/web/0.0.2-SNAPSHOT/maven-metadata.xml",
        )

    def test_construct_url_for_released_version(self):
        artifact_url, file_name = nexus._get_release_url(
            repository="libs-releases",
            group_id="com.company.sampleapp.web-module",
            artifact_id="web",
            packaging="zip",
            nexus_url="http://nexus.example.com/repository",
            version="0.1.0",
        )

        self.assertEqual(
            artifact_url,
            "http://nexus.example.com/repository/libs-releases/com/company/sampleapp/web-module/web/0.1.0/web-0.1.0.zip",
        )
        self.assertEqual(file_name, "web-0.1.0.zip")

    def test_construct_url_for_snapshot_version(self):
        with patch(
            "salt.modules.nexus._get_snapshot_version_metadata",
            MagicMock(
                return_value={"snapshot_versions": {"zip": "0.0.2-20170920.212353-3"}}
            ),
        ):

            artifact_url, file_name = nexus._get_snapshot_url(
                nexus_url="http://nexus.example.com/repository",
                repository="libs-snapshots",
                group_id="com.company.sampleapp.web-module",
                artifact_id="web",
                version="0.2.0-SNAPSHOT",
                packaging="zip",
                headers={},
            )

            self.assertEqual(
                artifact_url,
                "http://nexus.example.com/repository/libs-snapshots/com/company/sampleapp/web-module/web/0.2.0-SNAPSHOT/web-0.0.2-20170920.212353-3.zip",
            )
            self.assertEqual(file_name, "web-0.0.2-20170920.212353-3.zip")
