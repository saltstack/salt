# -*- coding: utf-8 -*-
'''
Module for fetching artifacts from Artifactory
'''

# Import python libs
import urllib2
import os
import xml.etree.ElementTree as ET
from urllib2 import HTTPError
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)


def get_latest_snapshot(artifactory_url, repository, group_id, artifact_id, packaging, target_dir='/tmp', target_file=None):
    '''
       Gets latest snapshot of the given artifact

       artifactory_url
           URL of artifactory instance
       repository
           Snapshot repository in artifactory to retrieve artifact from, for example: libs-snapshots
       group_id
           Group Id of the artifact
       artifact_id
           Artifact Id of the artifact
       packaging
           Packaging type (jar,war,ear,etc)
       target_dir
           Target directory to download artifact to (default: /tmp)
       target_file
           Target file to download artifact to (by default it is target_dir/artifact_id-snapshot_version.packaging)
       '''
    log.debug("======================== MODULE FUNCTION: artifactory.get_latest_snapshot, artifactory_url=%s, repository=%s, group_id=%s, artifact_id=%s, packaging=%s, target_dir=%s)",
                    artifactory_url, repository, group_id, artifact_id, packaging, target_dir)
    artifact_metadata = _get_artifact_metadata(artifactory_url=artifactory_url, repository=repository, group_id=group_id, artifact_id=artifact_id)
    version = artifact_metadata['latest_version']

    snapshot_url, file_name = _get_snapshot_url(artifactory_url, repository, group_id, artifact_id, version, packaging)
    target_file = __resolve_target_file(file_name, target_dir, target_file)

    return __save_artifact(snapshot_url, target_file)


def get_snapshot(artifactory_url, repository, group_id, artifact_id, packaging, version, snapshot_version=None, target_dir='/tmp', target_file=None):
    '''
       Gets snapshot of the desired version of the artifact

       artifactory_url
           URL of artifactory instance
       repository
           Snapshot repository in artifactory to retrieve artifact from, for example: libs-snapshots
       group_id
           Group Id of the artifact
       artifact_id
           Artifact Id of the artifact
       packaging
           Packaging type (jar,war,ear,etc)
       version
           Version of the artifact
       target_dir
           Target directory to download artifact to (default: /tmp)
       target_file
           Target file to download artifact to (by default it is target_dir/artifact_id-snapshot_version.packaging)
       '''
    log.debug('======================== MODULE FUNCTION: artifactory.get_snapshot(artifactory_url=%s, repository=%s, group_id=%s, artifact_id=%s, packaging=%s, version=%s, target_dir=%s)',
              artifactory_url, repository, group_id, artifact_id, packaging, version, target_dir)

    snapshot_url, file_name = _get_snapshot_url(artifactory_url, repository, group_id, artifact_id, version, packaging, snapshot_version)
    target_file = __resolve_target_file(file_name, target_dir, target_file)

    return __save_artifact(snapshot_url, target_file)


def get_release(artifactory_url, repository, group_id, artifact_id, packaging, version, target_dir='/tmp', target_file=None):
    '''
       Gets the specified release of the artifact

       artifactory_url
           URL of artifactory instance
       repository
           Release repository in artifactory to retrieve artifact from, for example: libs-releases
       group_id
           Group Id of the artifact
       artifact_id
           Artifact Id of the artifact
       packaging
           Packaging type (jar,war,ear,etc)
       version
           Version of the artifact
       target_dir
           Target directory to download artifact to (default: /tmp)
       target_file
           Target file to download artifact to (by default it is target_dir/artifact_id-version.packaging)
       '''
    log.debug('======================== MODULE FUNCTION: artifactory.get_release(artifactory_url=%s, repository=%s, group_id=%s, artifact_id=%s, packaging=%s, version=%s, target_dir=%s)',
              artifactory_url, repository, group_id, artifact_id, packaging, version, target_dir)

    release_url, file_name = _get_release_url(repository, group_id, artifact_id, packaging, version, artifactory_url)
    target_file = __resolve_target_file(file_name, target_dir, target_file)

    return __save_artifact(release_url, target_file)


def __resolve_target_file(file_name, target_dir, target_file=None):
    if target_file is None:
        target_file = os.path.join(target_dir, file_name)
    return target_file


def _get_snapshot_url(artifactory_url, repository, group_id, artifact_id, version, packaging, snapshot_version=None):
    if snapshot_version is None:
        snapshot_version_metadata = _get_snapshot_version_metadata(artifactory_url=artifactory_url, repository=repository, group_id=group_id, artifact_id=artifact_id, version=version)
        if packaging not in snapshot_version_metadata['snapshot_versions']:
            error_message = '''Cannot find requested packaging '{packaging}' in the snapshot version metadata.
                      artifactory_url: {artifactory_url}
                      repository: {repository}
                      group_id: {group_id}
                      artifact_id: {artifact_id}
                      packaging: {packaging}
                      version: {version}'''.format(
                        artifactory_url=artifactory_url,
                        repository=repository,
                        group_id=group_id,
                        artifact_id=artifact_id,
                        packaging=packaging,
                        version=version)
            raise ArtifactoryError(error_message)
        snapshot_version = snapshot_version_metadata['snapshot_versions'][packaging]

    group_url = __get_group_id_subpath(group_id)

    file_name = '{artifact_id}-{snapshot_version}.{packaging}'.format(
        artifact_id=artifact_id,
        snapshot_version=snapshot_version,
        packaging=packaging)
    snapshot_url = '{artifactory_url}/{repository}/{group_url}/{artifact_id}/{version}/{file_name}'.format(
                        artifactory_url=artifactory_url,
                        repository=repository,
                        group_url=group_url,
                        artifact_id=artifact_id,
                        version=version,
                        file_name=file_name)
    log.debug('snapshot_url=%s', snapshot_url)

    return snapshot_url, file_name


def _get_release_url(repository, group_id, artifact_id, packaging, version, artifactory_url):
    group_url = __get_group_id_subpath(group_id)
    # for released versions the suffix for the file is same as version
    file_name = '{artifact_id}-{version}.{packaging}'.format(
        artifact_id=artifact_id,
        version=version,
        packaging=packaging)

    release_url = '{artifactory_url}/{repository}/{group_url}/{artifact_id}/{version}/{file_name}'.format(
                        artifactory_url=artifactory_url,
                        repository=repository,
                        group_url=group_url,
                        artifact_id=artifact_id,
                        version=version,
                        file_name=file_name)
    log.debug('release_url=%s', release_url)
    return release_url, file_name


def _get_artifact_metadata_url(artifactory_url, repository, group_id, artifact_id):
    group_url = __get_group_id_subpath(group_id)
    # for released versions the suffix for the file is same as version
    artifact_metadata_url = '{artifactory_url}/{repository}/{group_url}/{artifact_id}/maven-metadata.xml'.format(
                                 artifactory_url=artifactory_url,
                                 repository=repository,
                                 group_url=group_url,
                                 artifact_id=artifact_id)
    log.debug('artifact_metadata_url=%s', artifact_metadata_url)
    return artifact_metadata_url


def _get_artifact_metadata_xml(artifactory_url, repository, group_id, artifact_id):
    artifact_metadata_url = _get_artifact_metadata_url(artifactory_url=artifactory_url, repository=repository, group_id=group_id, artifact_id=artifact_id)
    try:
        artifact_metadata_xml = urllib2.urlopen(artifact_metadata_url).read()
    except HTTPError as http_error:
        message = 'Could not fetch data from url: {url}, HTTPError: {error}'
        raise Exception(message.format(url=artifact_metadata_url, error=http_error))

    log.debug('artifact_metadata_xml=%s', artifact_metadata_xml)
    return artifact_metadata_xml


def _get_artifact_metadata(artifactory_url, repository, group_id, artifact_id):
    metadata_xml = _get_artifact_metadata_xml(artifactory_url=artifactory_url, repository=repository, group_id=group_id, artifact_id=artifact_id)
    root = ET.fromstring(metadata_xml)

    assert group_id == root.find('groupId').text
    assert artifact_id == root.find('artifactId').text
    latest_version = root.find('versioning').find('latest').text
    return {
        'latest_version': latest_version
    }


# functions for handling snapshots
def _get_snapshot_version_metadata_url(artifactory_url, repository, group_id, artifact_id, version):
    group_url = __get_group_id_subpath(group_id)
    # for released versions the suffix for the file is same as version
    snapshot_version_metadata_url = '{artifactory_url}/{repository}/{group_url}/{artifact_id}/{version}/maven-metadata.xml'.format(
                                         artifactory_url=artifactory_url,
                                         repository=repository,
                                         group_url=group_url,
                                         artifact_id=artifact_id,
                                         version=version)
    log.debug('snapshot_version_metadata_url=%s', snapshot_version_metadata_url)
    return snapshot_version_metadata_url


def _get_snapshot_version_metadata_xml(artifactory_url, repository, group_id, artifact_id, version):
    snapshot_version_metadata_url = _get_snapshot_version_metadata_url(artifactory_url=artifactory_url, repository=repository, group_id=group_id, artifact_id=artifact_id, version=version)
    try:
        snapshot_version_metadata_xml = urllib2.urlopen(snapshot_version_metadata_url).read()
    except HTTPError as http_error:
        message = 'Could not fetch data from url: {url}, HTTPError: {error}'
        raise Exception(message.format(url=snapshot_version_metadata_url, error=http_error))
    log.debug('snapshot_version_metadata_xml=%s', snapshot_version_metadata_xml)
    return snapshot_version_metadata_xml


def _get_snapshot_version_metadata(artifactory_url, repository, group_id, artifact_id, version):
    metadata_xml = _get_snapshot_version_metadata_xml(artifactory_url=artifactory_url, repository=repository, group_id=group_id, artifact_id=artifact_id, version=version)
    metadata = ET.fromstring(metadata_xml)

    assert group_id == metadata.find('groupId').text
    assert artifact_id == metadata.find('artifactId').text
    assert version == metadata.find('version').text

    snapshot_versions = metadata.find('versioning').find('snapshotVersions')
    extension_version_dict = {}
    for snapshot_version in snapshot_versions:
        extension = snapshot_version.find('extension').text
        value = snapshot_version.find('value').text
        extension_version_dict[extension] = value

    return {
        'snapshot_versions': extension_version_dict
    }


def __save_artifact(artifact_url, target_file):
    log.debug("__save_artifact(%s, %s)", artifact_url, target_file)
    result = {
        'status': False,
        'changes': {},
        'comment': ''
    }

    if os.path.isfile(target_file):
        log.debug("File {0} already exists, checking checksum...".format(target_file))
        checksum_url = artifact_url + ".sha1"

        checksum_success, artifact_sum, checksum_comment = __download(checksum_url)
        if checksum_success:
            log.debug("Downloaded SHA1 SUM: %s", artifact_sum)
            file_sum = __salt__['file.get_hash'](path=target_file, form='sha1')
            log.debug("Target file (%s) SHA1 SUM: %s", target_file, file_sum)

            if artifact_sum == file_sum:
                result['status'] = True
                result['target_file'] = target_file
                result['comment'] = 'File {0} already exists, checksum matches with Artifactory.\n' \
                                    'Checksum URL: {1}'.format(target_file, checksum_url)
                return result
            else:
                result['comment'] = 'File {0} already exists, checksum does not match with Artifactory!\n'\
                                    'Checksum URL: {1}'.format(target_file, checksum_url)

        else:
            result['status'] = False
            result['comment'] = checksum_comment
            return result

    log.debug('Downloading: {url} -> {target_file}'.format(url=artifact_url, target_file=target_file))
    try:
        f = urllib2.urlopen(artifact_url)
        with salt.utils.fopen(target_file, "wb") as local_file:
            local_file.write(f.read())
        result['status'] = True
        result['comment'] = __append_comment(('Artifact downloaded from URL: {0}'.format(artifact_url)), result['comment'])
        result['changes']['downloaded_file'] = target_file
        result['target_file'] = target_file
    except (HTTPError, urllib2.URLError) as e:
        result['status'] = False
        result['comment'] = __get_error_comment(e, artifact_url)

    return result


def __get_group_id_subpath(group_id):
    group_url = group_id.replace('.', '/')
    return group_url


def __download(request_url):
    log.debug('Downloading content from {0}'.format(request_url))

    success = False
    content = None
    comment = None
    try:
        url = urllib2.urlopen(request_url)
        content = url.read()
        success = True
    except HTTPError as e:
        comment = __get_error_comment(e, request_url)

    return success, content, comment


def __get_error_comment(http_error, request_url):
    if http_error.code == 404:
        comment = 'HTTP Error 404. Request URL: ' + request_url
    elif http_error.code == 409:
        comment = 'HTTP Error 409: Conflict. Requested URL: {0}. \n' \
                  'This error may be caused by reading snapshot artifact from non-snapshot repository.'.format(request_url)
    else:
        comment = 'HTTP Error {err_code}. Request URL: {url}'.format(err_code=http_error.code, url=request_url)

    return comment


def __append_comment(new_comment, current_comment=''):
    return current_comment+'\n'+new_comment


class ArtifactoryError(Exception):

    def __init__(self, value):
        super(ArtifactoryError, self).__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)
