# -*- coding: utf-8 -*-
from salt.modules import artifactory
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, NO_MOCK, NO_MOCK_REASON


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArtifactoryTestCase(TestCase):

    org_module_functions = {}

    def __save_module_functions(self):
        for name, val in artifactory.__dict__.iteritems():
            if callable(val):
                self.org_module_functions[name] = val

    def __restore_module_functions(self):
        for name, val in self.org_module_functions.iteritems():
            artifactory.__dict__[name] = val

    def setUp(self):
        self.__save_module_functions()

    def tearDown(self):
        self.__restore_module_functions()

    def test_artifact_get_metadata(self):
        artifactory._get_artifact_metadata_xml = MagicMock(return_value='''<?xml version="1.0" encoding="UTF-8"?>
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
        ''')
        metadata = artifactory._get_artifact_metadata(artifactory_url='http://artifactory.company.com/artifactory',
                                            repository='libs-releases',
                                            group_id='com.company.sampleapp.web-module',
                                            artifact_id='web')
        self.assertEqual(metadata['latest_version'], '1.1_RC11')

    def test_snapshot_version_get_metadata(self):
        artifactory._get_snapshot_version_metadata_xml = MagicMock(return_value='''<?xml version="1.0" encoding="UTF-8"?>
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
        ''')
        metadata = artifactory._get_snapshot_version_metadata(artifactory_url='http://artifactory.company.com/artifactory',
                                                             repository='libs-releases',
                                                             group_id='com.company.sampleapp.web-module',
                                                             artifact_id='web',
                                                             version='1.1_RC8-SNAPSHOT')
        self.assertEqual(metadata['snapshot_versions']['war'], '1.1_RC8-20140418.150212-1')

    def test_artifact_metadata_url(self):
        metadata_url = artifactory._get_artifact_metadata_url(artifactory_url='http://artifactory.company.com/artifactory',
                                                             repository='libs-releases',
                                                             group_id='com.company.sampleapp.web-module',
                                                             artifact_id='web')

        self.assertEqual(metadata_url, "http://artifactory.company.com/artifactory/libs-releases/com/company/sampleapp/web-module/web/maven-metadata.xml")

    def test_snapshot_version_metadata_url(self):
        metadata_url = artifactory._get_snapshot_version_metadata_url(artifactory_url='http://artifactory.company.com/artifactory',
                                                             repository='libs-snapshots',
                                                             group_id='com.company.sampleapp.web-module',
                                                             artifact_id='web',
                                                             version='1.0_RC10-SNAPSHOT')

        self.assertEqual(metadata_url, "http://artifactory.company.com/artifactory/libs-snapshots/com/company/sampleapp/web-module/web/1.0_RC10-SNAPSHOT/maven-metadata.xml")

    def test_construct_url_for_released_version(self):
        artifact_url, file_name = artifactory._get_release_url(repository='libs-releases',
                                      group_id='com.company.sampleapp.web-module',
                                      artifact_id='web',
                                      packaging='war',
                                      artifactory_url='http://artifactory.company.com/artifactory',
                                      version='1.0_RC20')

        self.assertEqual(artifact_url, "http://artifactory.company.com/artifactory/libs-releases/com/company/sampleapp/web-module/web/1.0_RC20/web-1.0_RC20.war")
        self.assertEqual(file_name, "web-1.0_RC20.war")

    def test_construct_url_for_snapshot_version(self):
        prev_artifactory_get_snapshot_version_metadata = artifactory._get_snapshot_version_metadata
        artifactory._get_snapshot_version_metadata = MagicMock(return_value={'snapshot_versions': {'war': '1.0_RC10-20131127.105838-2'}})

        artifact_url, file_name = artifactory._get_snapshot_url(artifactory_url='http://artifactory.company.com/artifactory',
                                               repository='libs-snapshots',
                                               group_id='com.company.sampleapp.web-module',
                                               artifact_id='web',
                                               version='1.0_RC10-SNAPSHOT',
                                               packaging='war')

        self.assertEqual(artifact_url, "http://artifactory.company.com/artifactory/libs-snapshots/com/company/sampleapp/web-module/web/1.0_RC10-SNAPSHOT/web-1.0_RC10-20131127.105838-2.war")
        self.assertEqual(file_name, "web-1.0_RC10-20131127.105838-2.war")
