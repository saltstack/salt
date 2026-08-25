"""
This state downloads artifacts from Nexus 3.x.

.. versionadded:: 2018.3.0
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "nexus"


def __virtual__():
    """
    Set the virtual name for the module
    """
    return __virtualname__


def downloaded(name, artifact, target_dir="/tmp", target_file=None):
    """
    Ensures that the artifact from nexus exists at given location. If it doesn't exist, then
    it will be downloaded. If it already exists then the checksum of existing file is checked
    against checksum in nexus. If it is different then the step will fail.

    artifact
        Details of the artifact to be downloaded from nexus. Various options are:

        - nexus_url: URL of the nexus instance
        - repository: Repository in nexus
        - artifact_id: Artifact ID
        - group_id: Group ID
        - packaging: Packaging
        - classifier: Classifier
        - version: Version
            One of the following:
            - Version to download
            - ``latest`` - Download the latest release of this artifact
            - ``latest_snapshot`` - Download the latest snapshot for this artifact

        - username: nexus username
        - password: nexus password

    target_dir
        Directory where the artifact should be downloaded. By default it is downloaded to /tmp directory.

    target_file
        Target file to download artifact to. By default file name is resolved by nexus.

    An example to download an artifact to a specific file:

    .. code-block:: yaml

        jboss_module_downloaded:
          nexus.downloaded:
           - artifact:
               nexus_url: http://nexus.intranet.example.com/repository
               repository: 'libs-release-local'
               artifact_id: 'module'
               group_id: 'com.company.module'
               packaging: 'jar'
               classifier: 'sources'
               version: '1.0'
           - target_file: /opt/jboss7/modules/com/company/lib/module.jar

    Download artifact to the folder (automatically resolves file name):

    .. code-block:: yaml

        maven_artifact_downloaded:
          nexus.downloaded:
           - artifact:
                nexus_url: http://nexus.intranet.example.com/repository
                repository: 'maven-releases'
                artifact_id: 'module'
                group_id: 'com.company.module'
                packaging: 'zip'
                classifier: 'dist'
                version: '1.0'
           - target_dir: /opt/maven/modules/com/company/release

    """
    log.debug(" ======================== STATE: nexus.downloaded (name: %s) ", name)
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    try:
        fetch_result = __fetch_from_nexus(artifact, target_dir, target_file)
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = str(exc)
        return ret

    log.debug("fetch_result=%s", fetch_result)

    ret["result"] = fetch_result["status"]
    ret["comment"] = fetch_result["comment"]
    ret["changes"] = fetch_result["changes"]
    log.debug("ret=%s", ret)

    return ret


def __fetch_from_nexus(artifact, target_dir, target_file):
    nexus_url = artifact["nexus_url"]
    repository = artifact["repository"]
    group_id = artifact["group_id"]
    artifact_id = artifact["artifact_id"]
    packaging = artifact["packaging"] if "packaging" in artifact else "jar"
    classifier = artifact["classifier"] if "classifier" in artifact else None
    username = artifact["username"] if "username" in artifact else None
    password = artifact["password"] if "password" in artifact else None
    version = artifact["version"] if "version" in artifact else None

    # determine module function to use
    if version == "latest_snapshot":
        function = "nexus.get_latest_snapshot"
        version_param = False
    elif version == "latest":
        function = "nexus.get_latest_release"
        version_param = False
    elif version.endswith("SNAPSHOT"):
        function = "nexus.get_snapshot"
        version_param = True
    else:
        function = "nexus.get_release"
        version_param = True

    if version_param:
        fetch_result = __salt__[function](
            nexus_url=nexus_url,
            repository=repository,
            group_id=group_id,
            artifact_id=artifact_id,
            packaging=packaging,
            classifier=classifier,
            target_dir=target_dir,
            target_file=target_file,
            username=username,
            password=password,
            version=version,
        )
    else:
        fetch_result = __salt__[function](
            nexus_url=nexus_url,
            repository=repository,
            group_id=group_id,
            artifact_id=artifact_id,
            packaging=packaging,
            classifier=classifier,
            target_dir=target_dir,
            target_file=target_file,
            username=username,
            password=password,
        )

    return fetch_result
