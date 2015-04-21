# -*- coding: utf-8 -*-
'''
This state downloads artifacts from artifactory.

'''
import logging

log = logging.getLogger(__name__)


def downloaded(name, artifact, target_dir='/tmp', target_file=None):
    '''
    Ensures that the artifact from artifactory exists at given location. If it doesn't exist, then
    it will be downloaded. It it already exists then the checksum of existing file is checked against checksum
    in artifactory. If it is different then the step will fail.

    artifact:
        Details of the artifact to be downloaded from artifactory.
            - artifactory_url: URL of the artifactory instance
            - repository: Repository in artifactory
            - artifact_id: Artifact ID
            - group_id: Group ID
            - packaging: Packaging
            - version: Version
    target_dir:
        Directory where the artifact should be downloaded. By default it is downloaded to /tmp directory.
    target_file:
        Target file to download artifact to. By default file name is resolved by artifactory.

    Example::
    Download artifact to a specific file:

    .. code-block:: yaml

        jboss_module_downloaded:
          artifactory.downloaded:
           - artifact:
                artifactory_url: http://artifactory.intranet.company.com/artifactory
                repository: 'libs-release-local'
                artifact_id: 'module'
                group_id: 'com.company.module'
                packaging: 'jar'
                version: '1.0'
           - target_file: /opt/jboss7/modules/com/company/lib/module.jar

    Download artifact to the folder (automatically resolves file name):

    .. code-block:: yaml

        jboss_module_downloaded:
          artifactory.downloaded:
           - artifact:
                artifactory_url: http://artifactory.intranet.company.com/artifactory
                repository: 'libs-release-local'
                artifact_id: 'module'
                group_id: 'com.company.module'
                packaging: 'jar'
                version: '1.0'
           - target_dir: /opt/jboss7/modules/com/company/lib

    '''
    log.debug(" ======================== STATE: artifactory.downloaded (name: %s) ", name)
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    try:
        fetch_result = __fetch_from_artifactory(artifact, target_dir, target_file)
        log.debug("fetch_result=%s", str(fetch_result))

        ret['result'] = fetch_result['status']
        ret['comment'] = fetch_result['comment']
        ret['changes'] = fetch_result['changes']
        log.debug("ret=%s", str(ret))

        return ret
    except Exception as exception:
        return None, exception


def __fetch_from_artifactory(artifact, target_dir, target_file):
    if 'latest_snapshot' in artifact and artifact['latest_snapshot']:
        fetch_result = __salt__['artifactory.get_latest_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                                   repository=artifact['repository'],
                                                                   group_id=artifact['group_id'],
                                                                   artifact_id=artifact['artifact_id'],
                                                                   packaging=artifact['packaging'],
                                                                   target_dir=target_dir,
                                                                   target_file=target_file)
    elif artifact['version'].endswith('SNAPSHOT'):
        fetch_result = __salt__['artifactory.get_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                            repository=artifact['repository'],
                                                            group_id=artifact['group_id'],
                                                            artifact_id=artifact['artifact_id'],
                                                            packaging=artifact['packaging'],
                                                            version=artifact['version'],
                                                            target_dir=target_dir,
                                                            target_file=target_file)
    else:
        fetch_result = __salt__['artifactory.get_release'](artifactory_url=artifact['artifactory_url'],
                                                           repository=artifact['repository'],
                                                           group_id=artifact['group_id'],
                                                           artifact_id=artifact['artifact_id'],
                                                           packaging=artifact['packaging'],
                                                           version=artifact['version'],
                                                           target_dir=target_dir,
                                                           target_file=target_file)
    return fetch_result
