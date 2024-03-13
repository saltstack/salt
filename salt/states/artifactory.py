"""
This state downloads artifacts from artifactory.

"""

import logging

log = logging.getLogger(__name__)


def downloaded(
    name, artifact, target_dir="/tmp", target_file=None, use_literal_group_id=False
):
    """
    Ensures that the artifact from artifactory exists at given location. If it doesn't exist, then
    it will be downloaded. If it already exists then the checksum of existing file is checked against checksum
    in artifactory. If it is different then the step will fail.

    artifact
        Details of the artifact to be downloaded from artifactory. Various options are:

        - artifactory_url: URL of the artifactory instance
        - repository: Repository in artifactory
        - artifact_id: Artifact ID
        - group_id: Group ID
        - packaging: Packaging
        - classifier: Classifier
          .. versionadded:: 2015.8.0
        - version: Version
            One of the following:
            - Version to download
            - ``latest`` - Download the latest release of this artifact
            - ``latest_snapshot`` - Download the latest snapshot for this artifact

        - username: Artifactory username
          .. versionadded:: 2015.8.0
        - password: Artifactory password
          .. versionadded:: 2015.8.0

    target_dir
        Directory where the artifact should be downloaded. By default it is downloaded to /tmp directory.

    target_file
        Target file to download artifact to. By default file name is resolved by artifactory.

    An example to download an artifact to a specific file:

    .. code-block:: yaml

        jboss_module_downloaded:
          artifactory.downloaded:
           - artifact:
               artifactory_url: http://artifactory.intranet.example.com/artifactory
               repository: 'libs-release-local'
               artifact_id: 'module'
               group_id: 'com.company.module'
               packaging: 'jar'
               classifier: 'sources'
               version: '1.0'
           - target_file: /opt/jboss7/modules/com/company/lib/module.jar

    Download artifact to the folder (automatically resolves file name):

    .. code-block:: yaml

        jboss_module_downloaded:
          artifactory.downloaded:
           - artifact:
                artifactory_url: http://artifactory.intranet.example.com/artifactory
                repository: 'libs-release-local'
                artifact_id: 'module'
                group_id: 'com.company.module'
                packaging: 'jar'
                classifier: 'sources'
                version: '1.0'
           - target_dir: /opt/jboss7/modules/com/company/lib

    """
    log.debug(
        " ======================== STATE: artifactory.downloaded (name: %s) ", name
    )
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    if "test" in __opts__ and __opts__["test"] is True:
        fetch_result = {}
        fetch_result["status"] = True
        fetch_result["comment"] = "Artifact would be downloaded from URL: {}".format(
            artifact["artifactory_url"]
        )
        fetch_result["changes"] = {}
    else:
        try:
            fetch_result = __fetch_from_artifactory(
                artifact, target_dir, target_file, use_literal_group_id
            )
        except Exception as exc:  # pylint: disable=broad-except
            ret["result"] = False
            ret["comment"] = str(exc)
            return ret

    log.debug("fetch_result = %s", fetch_result)

    ret["result"] = fetch_result["status"]
    ret["comment"] = fetch_result["comment"]
    ret["changes"] = fetch_result["changes"]
    log.debug("ret = %s", ret)

    return ret


def __fetch_from_artifactory(artifact, target_dir, target_file, use_literal_group_id):
    if ("latest_snapshot" in artifact and artifact["latest_snapshot"]) or artifact[
        "version"
    ] == "latest_snapshot":
        fetch_result = __salt__["artifactory.get_latest_snapshot"](
            artifactory_url=artifact["artifactory_url"],
            repository=artifact["repository"],
            group_id=artifact["group_id"],
            artifact_id=artifact["artifact_id"],
            packaging=artifact["packaging"] if "packaging" in artifact else "jar",
            classifier=artifact["classifier"] if "classifier" in artifact else None,
            target_dir=target_dir,
            target_file=target_file,
            username=artifact["username"] if "username" in artifact else None,
            password=artifact["password"] if "password" in artifact else None,
            use_literal_group_id=use_literal_group_id,
        )
    elif artifact["version"].endswith("SNAPSHOT"):
        fetch_result = __salt__["artifactory.get_snapshot"](
            artifactory_url=artifact["artifactory_url"],
            repository=artifact["repository"],
            group_id=artifact["group_id"],
            artifact_id=artifact["artifact_id"],
            packaging=artifact["packaging"] if "packaging" in artifact else "jar",
            classifier=artifact["classifier"] if "classifier" in artifact else None,
            version=artifact["version"],
            target_dir=target_dir,
            target_file=target_file,
            username=artifact["username"] if "username" in artifact else None,
            password=artifact["password"] if "password" in artifact else None,
            use_literal_group_id=use_literal_group_id,
        )
    elif artifact["version"] == "latest":
        fetch_result = __salt__["artifactory.get_latest_release"](
            artifactory_url=artifact["artifactory_url"],
            repository=artifact["repository"],
            group_id=artifact["group_id"],
            artifact_id=artifact["artifact_id"],
            packaging=artifact["packaging"] if "packaging" in artifact else "jar",
            classifier=artifact["classifier"] if "classifier" in artifact else None,
            target_dir=target_dir,
            target_file=target_file,
            username=artifact["username"] if "username" in artifact else None,
            password=artifact["password"] if "password" in artifact else None,
            use_literal_group_id=use_literal_group_id,
        )
    else:
        fetch_result = __salt__["artifactory.get_release"](
            artifactory_url=artifact["artifactory_url"],
            repository=artifact["repository"],
            group_id=artifact["group_id"],
            artifact_id=artifact["artifact_id"],
            packaging=artifact["packaging"] if "packaging" in artifact else "jar",
            classifier=artifact["classifier"] if "classifier" in artifact else None,
            version=artifact["version"],
            target_dir=target_dir,
            target_file=target_file,
            username=artifact["username"] if "username" in artifact else None,
            password=artifact["password"] if "password" in artifact else None,
            use_literal_group_id=use_literal_group_id,
        )
    return fetch_result
