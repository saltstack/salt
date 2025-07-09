"""
Module for fetching artifacts from Artifactory
"""

import http.client
import logging
import os
import urllib.request
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError

import salt.utils.files
import salt.utils.hashutils
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "artifactory"


def __virtual__():
    """
    Only load if elementtree xml library is available.
    """
    return True


def get_latest_snapshot(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    packaging,
    target_dir="/tmp",
    target_file=None,
    classifier=None,
    username=None,
    password=None,
    use_literal_group_id=False,
):
    """
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
    classifier
        Artifact classifier name (ex: sources,javadoc,etc). Optional parameter.
    username
        Artifactory username. Optional parameter.
    password
        Artifactory password. Optional parameter.
    """
    log.debug(
        "======================== MODULE FUNCTION: artifactory.get_latest_snapshot,"
        " artifactory_url=%s, repository=%s, group_id=%s, artifact_id=%s, packaging=%s,"
        " target_dir=%s, classifier=%s)",
        artifactory_url,
        repository,
        group_id,
        artifact_id,
        packaging,
        target_dir,
        classifier,
    )

    headers = {}
    if username and password:
        headers["Authorization"] = "Basic {}".format(
            salt.utils.hashutils.base64_b64encode(
                "{}:{}".format(username.replace("\n", ""), password.replace("\n", ""))
            )
        )
    artifact_metadata = _get_artifact_metadata(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        headers=headers,
        use_literal_group_id=use_literal_group_id,
    )
    version = artifact_metadata["latest_version"]
    snapshot_url, file_name = _get_snapshot_url(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        version=version,
        packaging=packaging,
        classifier=classifier,
        headers=headers,
        use_literal_group_id=use_literal_group_id,
    )
    target_file = __resolve_target_file(file_name, target_dir, target_file)

    return __save_artifact(snapshot_url, target_file, headers)


def get_snapshot(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    packaging,
    version,
    snapshot_version=None,
    target_dir="/tmp",
    target_file=None,
    classifier=None,
    username=None,
    password=None,
    use_literal_group_id=False,
):
    """
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
    classifier
        Artifact classifier name (ex: sources,javadoc,etc). Optional parameter.
    username
        Artifactory username. Optional parameter.
    password
        Artifactory password. Optional parameter.
    """
    log.debug(
        "======================== MODULE FUNCTION:"
        " artifactory.get_snapshot(artifactory_url=%s, repository=%s, group_id=%s,"
        " artifact_id=%s, packaging=%s, version=%s, target_dir=%s, classifier=%s)",
        artifactory_url,
        repository,
        group_id,
        artifact_id,
        packaging,
        version,
        target_dir,
        classifier,
    )
    headers = {}
    if username and password:
        headers["Authorization"] = "Basic {}".format(
            salt.utils.hashutils.base64_b64encode(
                "{}:{}".format(username.replace("\n", ""), password.replace("\n", ""))
            )
        )
    snapshot_url, file_name = _get_snapshot_url(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        version=version,
        packaging=packaging,
        snapshot_version=snapshot_version,
        classifier=classifier,
        headers=headers,
        use_literal_group_id=use_literal_group_id,
    )
    target_file = __resolve_target_file(file_name, target_dir, target_file)

    return __save_artifact(snapshot_url, target_file, headers)


def get_latest_release(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    packaging,
    target_dir="/tmp",
    target_file=None,
    classifier=None,
    username=None,
    password=None,
    use_literal_group_id=False,
):
    """
    Gets the latest release of the artifact

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
    target_dir
        Target directory to download artifact to (default: /tmp)
    target_file
        Target file to download artifact to (by default it is target_dir/artifact_id-version.packaging)
    classifier
        Artifact classifier name (ex: sources,javadoc,etc). Optional parameter.
    username
        Artifactory username. Optional parameter.
    password
        Artifactory password. Optional parameter.
    """
    log.debug(
        "======================== MODULE FUNCTION:"
        " artifactory.get_latest_release(artifactory_url=%s, repository=%s,"
        " group_id=%s, artifact_id=%s, packaging=%s, target_dir=%s, classifier=%s)",
        artifactory_url,
        repository,
        group_id,
        artifact_id,
        packaging,
        target_dir,
        classifier,
    )
    headers = {}
    if username and password:
        headers["Authorization"] = "Basic {}".format(
            salt.utils.hashutils.base64_b64encode(
                "{}:{}".format(username.replace("\n", ""), password.replace("\n", ""))
            )
        )
    version = __find_latest_version(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        headers=headers,
    )
    release_url, file_name = _get_release_url(
        repository,
        group_id,
        artifact_id,
        packaging,
        version,
        artifactory_url,
        classifier,
        use_literal_group_id,
    )
    target_file = __resolve_target_file(file_name, target_dir, target_file)

    return __save_artifact(release_url, target_file, headers)


def get_release(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    packaging,
    version,
    target_dir="/tmp",
    target_file=None,
    classifier=None,
    username=None,
    password=None,
    use_literal_group_id=False,
):
    """
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
    classifier
        Artifact classifier name (ex: sources,javadoc,etc). Optional parameter.
    username
        Artifactory username. Optional parameter.
    password
        Artifactory password. Optional parameter.
    """
    log.debug(
        "======================== MODULE FUNCTION:"
        " artifactory.get_release(artifactory_url=%s, repository=%s, group_id=%s,"
        " artifact_id=%s, packaging=%s, version=%s, target_dir=%s, classifier=%s)",
        artifactory_url,
        repository,
        group_id,
        artifact_id,
        packaging,
        version,
        target_dir,
        classifier,
    )
    headers = {}
    if username and password:
        headers["Authorization"] = "Basic {}".format(
            salt.utils.hashutils.base64_b64encode(
                "{}:{}".format(username.replace("\n", ""), password.replace("\n", ""))
                ## f"{username.replace("\n", "")}:{password.replace("\n", "")}")
            )
        )
    release_url, file_name = _get_release_url(
        repository,
        group_id,
        artifact_id,
        packaging,
        version,
        artifactory_url,
        classifier,
        use_literal_group_id,
    )
    target_file = __resolve_target_file(file_name, target_dir, target_file)

    return __save_artifact(release_url, target_file, headers)


def __resolve_target_file(file_name, target_dir, target_file=None):
    if target_file is None:
        target_file = os.path.join(target_dir, file_name)
    return target_file


def _get_snapshot_url(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    version,
    packaging,
    snapshot_version=None,
    classifier=None,
    headers=None,
    use_literal_group_id=False,
):
    if headers is None:
        headers = {}
    has_classifier = classifier is not None and classifier != ""

    if snapshot_version is None:
        try:
            snapshot_version_metadata = _get_snapshot_version_metadata(
                artifactory_url=artifactory_url,
                repository=repository,
                group_id=group_id,
                artifact_id=artifact_id,
                version=version,
                headers=headers,
            )
            if (
                not has_classifier
                and packaging not in snapshot_version_metadata["snapshot_versions"]
            ):
                error_message = """Cannot find requested packaging '{packaging}' in the snapshot version metadata.
                          artifactory_url: {artifactory_url}
                          repository: {repository}
                          group_id: {group_id}
                          artifact_id: {artifact_id}
                          packaging: {packaging}
                          classifier: {classifier}
                          version: {version}""".format(
                    artifactory_url=artifactory_url,
                    repository=repository,
                    group_id=group_id,
                    artifact_id=artifact_id,
                    packaging=packaging,
                    classifier=classifier,
                    version=version,
                )
                raise ArtifactoryError(error_message)

            packaging_with_classifier = (
                packaging if not has_classifier else packaging + ":" + classifier
            )
            if (
                has_classifier
                and packaging_with_classifier
                not in snapshot_version_metadata["snapshot_versions"]
            ):
                error_message = """Cannot find requested classifier '{classifier}' in the snapshot version metadata.
                          artifactory_url: {artifactory_url}
                          repository: {repository}
                          group_id: {group_id}
                          artifact_id: {artifact_id}
                          packaging: {packaging}
                          classifier: {classifier}
                          version: {version}""".format(
                    artifactory_url=artifactory_url,
                    repository=repository,
                    group_id=group_id,
                    artifact_id=artifact_id,
                    packaging=packaging,
                    classifier=classifier,
                    version=version,
                )
                raise ArtifactoryError(error_message)

            snapshot_version = snapshot_version_metadata["snapshot_versions"][
                packaging_with_classifier
            ]
        except CommandExecutionError as err:
            log.error(
                "Could not fetch maven-metadata.xml. Assuming snapshot_version=%s.",
                version,
            )
            snapshot_version = version

    group_url = __get_group_id_subpath(group_id, use_literal_group_id)

    file_name = "{artifact_id}-{snapshot_version}{classifier}.{packaging}".format(
        artifact_id=artifact_id,
        snapshot_version=snapshot_version,
        packaging=packaging,
        classifier=__get_classifier_url(classifier),
    )

    snapshot_url = "{artifactory_url}/{repository}/{group_url}/{artifact_id}/{version}/{file_name}".format(
        artifactory_url=artifactory_url,
        repository=repository,
        group_url=group_url,
        artifact_id=artifact_id,
        version=version,
        file_name=file_name,
    )
    log.debug("snapshot_url=%s", snapshot_url)

    return snapshot_url, file_name


def _get_release_url(
    repository,
    group_id,
    artifact_id,
    packaging,
    version,
    artifactory_url,
    classifier=None,
    use_literal_group_id=False,
):
    group_url = __get_group_id_subpath(group_id, use_literal_group_id)

    # for released versions the suffix for the file is same as version
    file_name = "{artifact_id}-{version}{classifier}.{packaging}".format(
        artifact_id=artifact_id,
        version=version,
        packaging=packaging,
        classifier=__get_classifier_url(classifier),
    )

    release_url = "{artifactory_url}/{repository}/{group_url}/{artifact_id}/{version}/{file_name}".format(
        artifactory_url=artifactory_url,
        repository=repository,
        group_url=group_url,
        artifact_id=artifact_id,
        version=version,
        file_name=file_name,
    )
    log.debug("release_url=%s", release_url)
    return release_url, file_name


def _get_artifact_metadata_url(
    artifactory_url, repository, group_id, artifact_id, use_literal_group_id=False
):
    group_url = __get_group_id_subpath(group_id, use_literal_group_id)
    # for released versions the suffix for the file is same as version
    artifact_metadata_url = "{artifactory_url}/{repository}/{group_url}/{artifact_id}/maven-metadata.xml".format(
        artifactory_url=artifactory_url,
        repository=repository,
        group_url=group_url,
        artifact_id=artifact_id,
    )
    log.debug("artifact_metadata_url=%s", artifact_metadata_url)
    return artifact_metadata_url


def _get_artifact_metadata_xml(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    headers,
    use_literal_group_id=False,
):

    artifact_metadata_url = _get_artifact_metadata_url(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        use_literal_group_id=use_literal_group_id,
    )

    try:
        request = urllib.request.Request(artifact_metadata_url, None, headers)
        artifact_metadata_xml = urllib.request.urlopen(request).read()
    except (HTTPError, URLError) as err:
        message = "Could not fetch data from url: {}. ERROR: {}".format(
            artifact_metadata_url, err
        )
        raise CommandExecutionError(message)

    log.debug("artifact_metadata_xml=%s", artifact_metadata_xml)
    return artifact_metadata_xml


def _get_artifact_metadata(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    headers,
    use_literal_group_id=False,
):
    metadata_xml = _get_artifact_metadata_xml(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        headers=headers,
        use_literal_group_id=use_literal_group_id,
    )
    root = ET.fromstring(metadata_xml)

    assert group_id == root.find("groupId").text
    assert artifact_id == root.find("artifactId").text
    latest_version = root.find("versioning").find("latest").text
    return {"latest_version": latest_version}


# functions for handling snapshots
def _get_snapshot_version_metadata_url(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    version,
    use_literal_group_id=False,
):
    group_url = __get_group_id_subpath(group_id, use_literal_group_id)
    # for released versions the suffix for the file is same as version
    snapshot_version_metadata_url = "{artifactory_url}/{repository}/{group_url}/{artifact_id}/{version}/maven-metadata.xml".format(
        artifactory_url=artifactory_url,
        repository=repository,
        group_url=group_url,
        artifact_id=artifact_id,
        version=version,
    )
    log.debug("snapshot_version_metadata_url=%s", snapshot_version_metadata_url)
    return snapshot_version_metadata_url


def _get_snapshot_version_metadata_xml(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    version,
    headers,
    use_literal_group_id=False,
):

    snapshot_version_metadata_url = _get_snapshot_version_metadata_url(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        version=version,
        use_literal_group_id=use_literal_group_id,
    )

    try:
        request = urllib.request.Request(snapshot_version_metadata_url, None, headers)
        snapshot_version_metadata_xml = urllib.request.urlopen(request).read()
    except (HTTPError, URLError) as err:
        message = "Could not fetch data from url: {}. ERROR: {}".format(
            snapshot_version_metadata_url, err
        )
        raise CommandExecutionError(message)

    log.debug("snapshot_version_metadata_xml=%s", snapshot_version_metadata_xml)
    return snapshot_version_metadata_xml


def _get_snapshot_version_metadata(
    artifactory_url, repository, group_id, artifact_id, version, headers
):
    metadata_xml = _get_snapshot_version_metadata_xml(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        version=version,
        headers=headers,
    )
    metadata = ET.fromstring(metadata_xml)

    assert group_id == metadata.find("groupId").text
    assert artifact_id == metadata.find("artifactId").text
    assert version == metadata.find("version").text

    snapshot_versions = metadata.find("versioning").find("snapshotVersions")
    extension_version_dict = {}
    for snapshot_version in snapshot_versions:
        extension = snapshot_version.find("extension").text
        value = snapshot_version.find("value").text
        if snapshot_version.find("classifier") is not None:
            classifier = snapshot_version.find("classifier").text
            extension_version_dict[extension + ":" + classifier] = value
        else:
            extension_version_dict[extension] = value

    return {"snapshot_versions": extension_version_dict}


def __get_latest_version_url(
    artifactory_url, repository, group_id, artifact_id, use_literal_group_id=False
):
    group_url = __get_group_id_subpath(group_id, use_literal_group_id)
    # for released versions the suffix for the file is same as version
    latest_version_url = "{artifactory_url}/api/search/latestVersion?g={group_url}&a={artifact_id}&repos={repository}".format(
        artifactory_url=artifactory_url,
        repository=repository,
        group_url=group_url,
        artifact_id=artifact_id,
    )
    log.debug("latest_version_url=%s", latest_version_url)
    return latest_version_url


def __find_latest_version(
    artifactory_url,
    repository,
    group_id,
    artifact_id,
    headers,
    use_literal_group_id=False,
):

    latest_version_url = __get_latest_version_url(
        artifactory_url=artifactory_url,
        repository=repository,
        group_id=group_id,
        artifact_id=artifact_id,
        use_literal_group_id=use_literal_group_id,
    )

    try:
        request = urllib.request.Request(latest_version_url, None, headers)
        version = urllib.request.urlopen(request).read()
    except (HTTPError, URLError) as err:
        message = "Could not fetch data from url: {}. ERROR: {}".format(
            latest_version_url, err
        )
        raise CommandExecutionError(message)

    log.debug("Response of: %s", version)

    if version is None or version == "":
        raise ArtifactoryError("Unable to find release version")

    return version


def __save_artifact(artifact_url, target_file, headers):
    log.debug("__save_artifact(%s, %s)", artifact_url, target_file)
    result = {"status": False, "changes": {}, "comment": ""}

    if os.path.isfile(target_file):
        log.debug("File %s already exists, checking checksum...", target_file)
        checksum_url = artifact_url + ".sha1"

        checksum_success, artifact_sum, checksum_comment = __download(
            checksum_url, headers
        )
        if checksum_success:
            artifact_sum = salt.utils.stringutils.to_unicode(artifact_sum)
            log.debug("Downloaded SHA1 SUM: %s", artifact_sum)
            file_sum = __salt__["file.get_hash"](path=target_file, form="sha1")
            log.debug("Target file (%s) SHA1 SUM: %s", target_file, file_sum)

            if artifact_sum == file_sum:
                result["status"] = True
                result["target_file"] = target_file
                result["comment"] = (
                    "File {} already exists, checksum matches with Artifactory.\n"
                    "Checksum URL: {}".format(target_file, checksum_url)
                )
                return result
            else:
                result["comment"] = (
                    "File {} already exists, checksum does not match with"
                    " Artifactory!\nChecksum URL: {}".format(target_file, checksum_url)
                )

        else:
            result["status"] = False
            result["comment"] = checksum_comment
            return result

    log.debug("Downloading: %s -> %s", artifact_url, target_file)

    try:
        request = urllib.request.Request(artifact_url, None, headers)
        f = urllib.request.urlopen(request)
        with salt.utils.files.fopen(target_file, "wb") as local_file:
            local_file.write(salt.utils.stringutils.to_bytes(f.read()))
        result["status"] = True
        result["comment"] = __append_comment(
            f"Artifact downloaded from URL: {artifact_url}",
            result["comment"],
        )
        result["changes"]["downloaded_file"] = target_file
        result["target_file"] = target_file
    except (HTTPError, URLError) as e:
        result["status"] = False
        result["comment"] = __get_error_comment(e, artifact_url)

    return result


def __get_group_id_subpath(group_id, use_literal_group_id=False):
    if not use_literal_group_id:
        group_url = group_id.replace(".", "/")
        return group_url
    return group_id


def __get_classifier_url(classifier):
    has_classifier = classifier is not None and classifier != ""
    return "-" + classifier if has_classifier else ""


def __download(request_url, headers):
    log.debug("Downloading content from %s", request_url)

    success = False
    content = None
    comment = None
    try:
        request = urllib.request.Request(request_url, None, headers)
        url = urllib.request.urlopen(request)
        content = url.read()
        success = True
    except HTTPError as e:
        comment = __get_error_comment(e, request_url)

    return success, content, comment


def __get_error_comment(http_error, request_url):
    if http_error.code == http.client.NOT_FOUND:
        comment = "HTTP Error 404. Request URL: " + request_url
    elif http_error.code == http.client.CONFLICT:
        comment = (
            "HTTP Error 409: Conflict. Requested URL: {}. \nThis error may be caused by"
            " reading snapshot artifact from non-snapshot repository.".format(
                request_url
            )
        )
    else:
        comment = "HTTP Error {err_code}. Request URL: {url}".format(
            err_code=http_error.code, url=request_url
        )

    return comment


def __append_comment(new_comment, current_comment=""):
    return current_comment + "\n" + new_comment


class ArtifactoryError(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)
