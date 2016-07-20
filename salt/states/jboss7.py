# -*- coding: utf-8 -*-
'''
Manage JBoss 7 Application Server via CLI interface

.. versionadded:: 2015.5.0

This state uses jboss-cli.sh script from JBoss installation and parses its output to determine execution result.

In order to run each state, jboss_config dictionary with the following properties must be passed:

.. code-block:: yaml

   jboss:
      cli_path: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
      controller: 10.11.12.13:9999
      cli_user: 'jbossadm'
      cli_password: 'jbossadm'

If controller doesn't require password, then passing cli_user and cli_password parameters is not obligatory.

Example of application deployment:

.. code-block:: yaml

     application_deployed:
      jboss7.deployed:
       - artifact:
           artifactory_url: http://artifactory.intranet.example.com/artifactory
           repository: 'ext-release-local'
           artifact_id: 'webcomponent'
           group_id: 'com.company.application'
           packaging: 'war'
           version: '0.1'
           target_dir: '/tmp'
        - jboss_config:
           cli_path: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
           controller: 10.11.12.13:9999
           cli_user: 'jbossadm'
           cli_password: 'jbossadm'

Since same dictionary with configuration will be used in all the states, it is much more convenient to move jboss configuration and other properties
to pillar. For example, configuration of jboss server, artifactory address and application version could be moved to pillars:

.. code-block:: yaml

     application_deployed:
      jboss7.deployed:
       - artifact:
           artifactory_url: {{ pillar['artifactory']['url'] }}
           repository: {{ pillar['artifactory']['repository'] }}
           artifact_id: 'webcomponent'
           group_id: 'com.company.application'
           packaging: 'war'
           version: {{ pillar['webcomponent-artifact']['version'] }}
           latest_snapshot: {{ pillar['webcomponent-artifact']['latest_snapshot'] }}
           repository: {{ pillar['webcomponent-artifact']['repository'] }}
       - jboss_config: {{ pillar['jboss'] }}


Configuration in pillars:

.. code-block:: yaml

   artifactory:
      url: 'http://artifactory.intranet.example.com/artifactory'
      repository: 'libs-snapshots-local'

   webcomponent-artifact:
      repository: 'libs-snapshots-local'
      latest_snapshot: True
      version: -1 #If latest_snapshot then version is ignored

For the sake of brevity, examples for each state assume that jboss_config is moved to pillars.


'''

# Import python libs
from __future__ import absolute_import
import time
import logging
import re
import traceback

# Import Salt libs
from salt.utils import dictdiffer
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


def datasource_exists(name, jboss_config, datasource_properties, recreate=False):
    '''
    Ensures that a datasource with given properties exist on the jboss instance.
    If datasource doesn't exist, it is created, otherwise only the properties that are different will be updated.

    name
        Datasource property name
    jboss_config
        Dict with connection properties (see state description)
    datasource_properties
        Dict with datasource properties
    recreate : False
        If set to True and datasource exists it will be removed and created again. However, if there are deployments that depend on the datasource, it will not me possible to remove it.

    Example:

    .. code-block:: yaml

        sampleDS:
          jboss7.datasource_exists:
           - recreate: False
           - datasource_properties:
               driver-name: mysql
               connection-url: 'jdbc:mysql://localhost:3306/sampleDatabase'
               jndi-name: 'java:jboss/datasources/sampleDS'
               user-name: sampleuser
               password: secret
               min-pool-size: 3
               use-java-context: True
           - jboss_config: {{ pillar['jboss'] }}

    '''
    log.debug(" ======================== STATE: jboss7.datasource_exists (name: %s) ", name)
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    has_changed = False
    ds_current_properties = {}
    ds_result = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
    if ds_result['success']:
        ds_current_properties = ds_result['result']
        if recreate:
            remove_result = __salt__['jboss7.remove_datasource'](jboss_config=jboss_config, name=name)
            if remove_result['success']:
                ret['changes']['removed'] = name
            else:
                ret['result'] = False
                ret['comment'] = 'Could not remove datasource. Stdout: '+remove_result['stdout']
                return ret

            has_changed = True  # if we are here, we have already made a change

            create_result = __salt__['jboss7.create_datasource'](jboss_config=jboss_config, name=name, datasource_properties=datasource_properties)
            if create_result['success']:
                ret['changes']['created'] = name
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create datasource. Stdout: '+create_result['stdout']
                return ret

            read_result = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
            if read_result['success']:
                ds_new_properties = read_result['result']
            else:
                ret['result'] = False
                ret['comment'] = 'Could not read datasource. Stdout: '+read_result['stdout']
                return ret

        else:
            update_result = __salt__['jboss7.update_datasource'](jboss_config=jboss_config, name=name, new_properties=datasource_properties)
            if not update_result['success']:
                ret['result'] = False
                ret['comment'] = 'Could not update datasource. '+update_result['comment']
                # some changes to the datasource may have already been made, therefore we don't quit here
            else:
                ret['comment'] = 'Datasource updated.'

            read_result = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
            ds_new_properties = read_result['result']
    else:
        if ds_result['err_code'] == 'JBAS014807':  # ok, resource not exists:
            create_result = __salt__['jboss7.create_datasource'](jboss_config=jboss_config, name=name, datasource_properties=datasource_properties)
            if create_result['success']:
                read_result = __salt__['jboss7.read_datasource'](jboss_config=jboss_config, name=name)
                ds_new_properties = read_result['result']
                ret['comment'] = 'Datasource created.'
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create datasource. Stdout: '+create_result['stdout']
        else:
            raise CommandExecutionError('Unable to handle error: {0}'.format(ds_result['failure-description']))

    if ret['result']:
        log.debug("ds_new_properties=%s", str(ds_new_properties))
        log.debug("ds_current_properties=%s", str(ds_current_properties))
        diff = dictdiffer.diff(ds_new_properties, ds_current_properties)

        added = diff.added()
        if len(added) > 0:
            has_changed = True
            ret['changes']['added'] = __format_ds_changes(added, ds_current_properties, ds_new_properties)

        removed = diff.removed()
        if len(removed) > 0:
            has_changed = True
            ret['changes']['removed'] = __format_ds_changes(removed, ds_current_properties, ds_new_properties)

        changed = diff.changed()
        if len(changed) > 0:
            has_changed = True
            ret['changes']['changed'] = __format_ds_changes(changed, ds_current_properties, ds_new_properties)

        if not has_changed:
            ret['comment'] = 'Datasource not changed.'

    return ret


def __format_ds_changes(keys, old_dict, new_dict):
    log.debug("__format_ds_changes(keys=%s, old_dict=%s, new_dict=%s)", str(keys), str(old_dict), str(new_dict))
    changes = ''
    for key in keys:
        log.debug("key=%s", str(key))
        if key in old_dict and key in new_dict:
            changes += key+':'+__get_ds_value(old_dict, key)+'->'+__get_ds_value(new_dict, key)+'\n'
        elif key in old_dict:
            changes += key+'\n'
        elif key in new_dict:
            changes += key+':'+__get_ds_value(new_dict, key)+'\n'
    return changes


def __get_ds_value(dct, key):
    log.debug("__get_value(dict,%s)", key)
    if key == "password":
        return "***"
    elif dct[key] is None:
        return 'undefined'
    else:
        return str(dct[key])


def bindings_exist(name, jboss_config, bindings):
    '''
    Ensures that given JNDI binding are present on the server.
    If a binding doesn't exist on the server it will be created.
    If it already exists its value will be changed.

    jboss_config:
        Dict with connection properties (see state description)
    bindings:
        Dict with bindings to set.

    Example:

    .. code-block:: yaml

            jndi_entries_created:
              jboss7.bindings_exist:
               - bindings:
                  'java:global/sampleapp/environment': 'DEV'
                  'java:global/sampleapp/configurationFile': '/var/opt/sampleapp/config.properties'
               - jboss_config: {{ pillar['jboss'] }}

    '''
    log.debug(" ======================== STATE: jboss7.bindings_exist (name: %s) ", name)
    log.debug('bindings='+str(bindings))
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': 'Bindings not changed.'}

    has_changed = False
    for key in bindings:
        value = str(bindings[key])
        query_result = __salt__['jboss7.read_simple_binding'](binding_name=key, jboss_config=jboss_config)
        if query_result['success']:
            current_value = query_result['result']['value']
            if current_value != value:
                update_result = __salt__['jboss7.update_simple_binding'](binding_name=key, value=value, jboss_config=jboss_config)
                if update_result['success']:
                    has_changed = True
                    __log_binding_change(ret['changes'], 'changed', key, value, current_value)
                else:
                    raise CommandExecutionError(update_result['failure-description'])
        else:
            if query_result['err_code'] == 'JBAS014807':  # ok, resource not exists:
                create_result = __salt__['jboss7.create_simple_binding'](binding_name=key, value=value, jboss_config=jboss_config)
                if create_result['success']:
                    has_changed = True
                    __log_binding_change(ret['changes'], 'added', key, value)
                else:
                    raise CommandExecutionError(create_result['failure-description'])
            else:
                raise CommandExecutionError(query_result['failure-description'])

    if has_changed:
        ret['comment'] = 'Bindings changed.'
    return ret


def __log_binding_change(changes, type_, key, new, old=None):
    if type_ not in changes:
        changes[type_] = ''
    if old is None:
        changes[type_] += key + ':' + new + '\n'
    else:
        changes[type_] += key + ':' + old + '->' + new + '\n'


def deployed(name, jboss_config, artifact=None, salt_source=None):
    '''
    Ensures that the given application is deployed on server.

    jboss_config:
        Dict with connection properties (see state description)
    artifact:
        If set, the artifact will be fetched from artifactory. This is a Dict object with the following properties:
           - artifactory_url: Full url to artifactory instance, for example: http://artifactory.intranet.example.com/artifactory
           - repository: One of the repositories, for example: libs-snapshots, ext-release-local, etc..
           - artifact_id: Artifact ID of the artifact
           - group_id: Group ID of the artifact
           - packaging: war/jar/ear, etc...
           - version: Artifact version. If latest_snapshot is set to True, the value of this attribute will be ignored, and newest snapshot will be taken instead.
           - latest_snapshot: If set to True and repository is a snapshot repository it will automatically select the newest snapshot.
           - snapshot_version: Exact version of the snapshot (with timestamp). A snapshot version may have several builds and a way to differentiate is to provide a build timestamp.
           - target_dir: Temporary directory on minion where artifacts will be downloaded
    salt_source:
        If set, the artifact to be deployed will be fetched from salt master. This is a Dict object with the following properties:
           - source: File on salt master (eg. salt://application-web-0.39.war)
           - target_file: Temporary file on minion to save file to (eg. '/tmp/application-web-0.39.war')
           - undeploy: Regular expression to match against existing deployments. If any deployment matches the regular expression then it will be undeployed.

    The deployment consists of the following steps:

    * Fetch artifact (salt filesystem, artifact or filesystem on minion)
    * Check if same artifact is not deployed yet (perhaps with different version)
    * Undeploy the artifact if it is already deployed
    * Deploy the new artifact

    Examples:

    Deployment of a file from Salt file system:

    .. code-block:: yaml

        application_deployed:
          jboss7.deployed:
           - salt_source:
                source: salt://application-web-0.39.war
                target_file: '/tmp/application-web-0.39.war'
                undeploy: 'application-web-.*'
           - jboss_config: {{ pillar['jboss'] }}

    Here, application-web-0.39.war file is downloaded from Salt file system to /tmp/application-web-0.39.war file on minion.
    Existing deployments are checked if any of them matches 'application-web-.*' regular expression, and if so then it
    is undeployed before deploying the application. This is useful to automate deployment of new application versions.

    JBoss state is capable of deploying artifacts directly from Artifactory repository. Here are some examples of deployments:

    1) Deployment of released version of artifact from Artifactory.

    .. code-block:: yaml

            application_deployed:
              jboss7.deployed:
               - artifact:
                   artifactory_url: http://artifactory.intranet.example.com/artifactory
                   repository: 'ext-release-local'
                   artifact_id: 'webcomponent'
                   group_id: 'com.company.application'
                   packaging: 'war'
                   version: '0.1'
                   target_dir: '/tmp'
                - jboss_config: {{ pillar['jboss'] }}

    This performs the following operations:

    * Download artifact from artifactory. In the example above the artifact will be fetched from: http://artifactory.intranet.example.com/artifactory/ext-release-local/com/company/application/webcomponent/0.1/webcomponent-0.1.war
      As a rule, for released versions the artifacts are downloaded from: artifactory_url/repository/group_id_with_slashed_instead_of_dots/artifact_id/version/artifact_id-version.packaging'
      This follows artifactory convention for artifact resolution. By default the artifact will be downloaded to /tmp directory on minion.
    * Connect to JBoss via controller (defined in jboss_config dict) and check if the artifact is not deployed already. In case of artifactory
      it will check if any deployment's name starts with artifact_id value. If deployment already exists it will be undeployed
    * Deploy the downloaded artifact to JBoss via cli interface.

    2) Deployment of last updated version of given SNAPSHOT version of artifact from Artifactory.

    .. code-block:: yaml

        application_deployed:
          jboss7.deployed:
           - artifact:
               artifactory_url: http://artifactory.intranet.example.com/artifactory
               repository: 'ext-snapshot-local'
               artifact_id: 'webcomponent'
               group_id: 'com.company.application'
               packaging: 'war'
               version: '0.1-SNAPSHOT'
            - jboss_config: {{ pillar['jboss'] }}

    Deploying snapshot version involves an additional step of resolving the exact version of the artifact (including the timestamp), which
    is not necessary when deploying a release.
    In the example above first a request will be made to retrieve the update timestamp from:
    http://artifactory.intranet.example.com/artifactory/ext-snapshot-local/com/company/application/webcomponent/0.1-SNAPSHOT/maven-metadata.xml
    Then the artifact will be fetched from
    http://artifactory.intranet.example.com/artifactory/ext-snapshot-local/com/company/application/webcomponent/0.1-SNAPSHOT/webcomponent-RESOLVED_SNAPSHOT_VERSION.war

    .. note:: In order to perform a snapshot deployment you have to:

        * Set repository to a snapshot repository.
        * Choose a version that ends with "SNAPSHOT" string.
          Snapshot repositories have a different layout and provide some extra information that is needed for deployment of the last or a specific snapshot.

    3) Deployment of SNAPSHOT version (with exact timestamp) of artifact from Artifactory.

    If you need to deploy an exact version of the snapshot you may provide snapshot_version parameter.

    .. code-block:: yaml

        application_deployed:
          jboss7.deployed:
           - artifact:
               artifactory_url: http://artifactory.intranet.example.com/artifactory
               repository: 'ext-snapshot-local'
               artifact_id: 'webcomponent'
               group_id: 'com.company.application'
               packaging: 'war'
               version: '0.1-SNAPSHOT'
               snapshot_version: '0.1-20141023.131756-19'
            - jboss_config: {{ pillar['jboss'] }}


    In this example the artifact will be retrieved from:
    http://artifactory.intranet.example.com/artifactory/ext-snapshot-local/com/company/application/webcomponent/0.1-SNAPSHOT/webcomponent-0.1-20141023.131756-19.war

    4) Deployment of latest snapshot of artifact from Artifactory.

    .. code-block:: yaml

        application_deployed:
          jboss7.deployed:
           - artifact:
               artifactory_url: http://artifactory.intranet.example.com/artifactory
               repository: 'ext-snapshot-local'
               artifact_id: 'webcomponent'
               group_id: 'com.company.application'
               packaging: 'war'
               latest_snapshot: True
            - jboss_config: {{ pillar['jboss'] }}

    Instead of providing an exact version of a snapshot it is sometimes more convenient to get the newest version. If artifact.latest_snapshot
    is set to True, then the newest snapshot will be downloaded from Artifactory. In this case it is not necessary to specify version.
    This is particulary useful when integrating with CI tools that will deploy the current snapshot to the Artifactory.

    '''
    log.debug(" ======================== STATE: jboss7.deployed (name: %s) ", name)
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    comment = ''

    validate_success, validate_comment = __validate_arguments(jboss_config, artifact, salt_source)
    if not validate_success:
        return _error(ret, validate_comment)

    log.debug('artifact=%s', str(artifact))
    resolved_source, get_artifact_comment = __get_artifact(artifact, salt_source)
    log.debug('resolved_source=%s', resolved_source)
    log.debug('get_artifact_comment=%s', get_artifact_comment)

    comment = __append_comment(new_comment=get_artifact_comment, current_comment=comment)
    if resolved_source is None:
        return _error(ret, get_artifact_comment)

    find_success, deployment, find_comment = __find_deployment(jboss_config, artifact, salt_source)
    if not find_success:
        return _error(ret, find_comment)

    log.debug('deployment=%s', deployment)
    if deployment is not None:
        __salt__['jboss7.undeploy'](jboss_config, deployment)
        ret['changes']['undeployed'] = deployment

    deploy_result = __salt__['jboss7.deploy'](jboss_config=jboss_config, source_file=resolved_source)
    log.debug('deploy_result=%s', str(deploy_result))
    if deploy_result['success']:
        comment = __append_comment(new_comment='Deployment completed.', current_comment=comment)
        ret['comment'] = comment
        ret['changes']['deployed'] = resolved_source
    else:
        comment = __append_comment(new_comment='''Deployment failed\nreturn code={retcode}\nstdout='{stdout}'\nstderr='{stderr}'''.format(**deploy_result), current_comment=comment)
        return _error(ret, comment)

    return ret


def __validate_arguments(jboss_config, artifact, salt_source):
    result, comment = __check_dict_contains(jboss_config, 'jboss_config', ['cli_path', 'controller'])
    if artifact is None and salt_source is None:
        result = False
        comment = __append_comment('No salt_source or artifact defined', comment)
    if artifact:
        result, comment = __check_dict_contains(artifact, 'artifact', ['artifactory_url', 'repository', 'artifact_id', 'group_id', 'packaging'], comment, result)
        if 'latest_snapshot' in artifact and isinstance(artifact['latest_snapshot'], str):
            if artifact['latest_snapshot'] == 'True':
                artifact['latest_snapshot'] = True
            elif artifact['latest_snapshot'] == 'False':
                artifact['latest_snapshot'] = False
            else:
                result = False
                comment = __append_comment('Cannot convert jboss_config.latest_snapshot={0} to boolean'.format(artifact['latest_snapshot']), comment)
        if 'version' not in artifact and ('latest_snapshot' not in artifact or not artifact['latest_snapshot']):
            result = False
            comment = __append_comment('No version or latest_snapshot=True in artifact')
    if salt_source:
        result, comment = __check_dict_contains(salt_source, 'salt_source', ['source', 'target_file'], comment, result)

    return result, comment


def __find_deployment(jboss_config, artifact=None, salt_source=None):
    result = None
    success = True
    comment = ''
    deployments = __salt__['jboss7.list_deployments'](jboss_config)
    if artifact is not None:
        for deployment in deployments:
            if deployment.startswith(artifact['artifact_id']):
                if result is not None:
                    success = False
                    comment = "More than one deployment's name starts with {0}. \n" \
                              "For deployments from artifactory existing deployments on JBoss are searched to find one that starts with artifact_id.\n"\
                              "Existing deployments: {1}".format(artifact['artifact_id'], ",".join(deployments))
                else:
                    result = deployment
    elif salt_source is not None and salt_source['undeploy']:
        deployment_re = re.compile(salt_source['undeploy'])
        for deployment in deployments:
            if deployment_re.match(deployment):
                if result is not None:
                    success = False
                    comment = "More than one deployment matches regular expression: {0}. \n" \
                              "For deployments from Salt file system deployments on JBoss are searched to find one that matches regular expression in 'undeploy' parameter.\n" \
                              "Existing deployments: {1}".format(salt_source['undeploy'], ",".join(deployments))
                else:
                    result = deployment

    return success, result, comment


def __get_artifact(artifact, salt_source):
    resolved_source = None
    comment = None

    if artifact is None and salt_source is None:
        log.debug('artifact == None and salt_source == None')
        comment = 'No salt_source or artifact defined'
    elif isinstance(artifact, dict):
        log.debug('artifact from artifactory')
        try:
            fetch_result = __fetch_from_artifactory(artifact)
            log.debug('fetch_result={0}'.format(fetch_result))
        except Exception as exception:
            log.debug(traceback.format_exc())
            return None, exception

        if fetch_result['status']:
            resolved_source = fetch_result['target_file']
            comment = fetch_result['comment']
        else:
            comment = 'Cannot fetch artifact (artifactory comment:{0}) '.format(fetch_result['comment'])
    elif isinstance(salt_source, dict):
        log.debug('file from salt master')

        try:
            sfn, source_sum, comment_ = __salt__['file.get_managed'](
                name=salt_source['target_file'],
                template=None,
                source=salt_source['source'],
                source_hash=None,
                user=None,
                group=None,
                mode=None,
                saltenv=__env__,
                context=None,
                defaults=None,
                kwargs=None)

            manage_result = __salt__['file.manage_file'](
                name=salt_source['target_file'],
                sfn=sfn,
                ret=None,
                source=salt_source['source'],
                source_sum=source_sum,
                user=None,
                group=None,
                mode=None,
                saltenv=__env__,
                backup=None,
                makedirs=False,
                template=None,
                show_diff=True,
                contents=None,
                dir_mode=None)
            if manage_result['result']:
                resolved_source = salt_source['target_file']
            else:
                comment = manage_result['comment']

        except Exception as e:
            log.debug(traceback.format_exc())
            comment = 'Unable to manage file: {0}'.format(e)

    return resolved_source, comment


def __fetch_from_artifactory(artifact):
    target_dir = '/tmp'
    if 'temp_dir' in artifact:
        target_dir = artifact['temp_dir']

    if 'latest_snapshot' in artifact and artifact['latest_snapshot']:
        fetch_result = __salt__['artifactory.get_latest_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                                   repository=artifact['repository'],
                                                                   group_id=artifact['group_id'],
                                                                   artifact_id=artifact['artifact_id'],
                                                                   packaging=artifact['packaging'],
                                                                   target_dir=target_dir)
    elif str(artifact['version']).endswith('SNAPSHOT'):
        if 'snapshot_version' in artifact:
            fetch_result = __salt__['artifactory.get_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                                repository=artifact['repository'],
                                                                group_id=artifact['group_id'],
                                                                artifact_id=artifact['artifact_id'],
                                                                packaging=artifact['packaging'],
                                                                version=artifact['version'],
                                                                snapshot_version=artifact['snapshot_version'],
                                                                target_dir=target_dir)
        else:
            fetch_result = __salt__['artifactory.get_snapshot'](artifactory_url=artifact['artifactory_url'],
                                                                repository=artifact['repository'],
                                                                group_id=artifact['group_id'],
                                                                artifact_id=artifact['artifact_id'],
                                                                packaging=artifact['packaging'],
                                                                version=artifact['version'],
                                                                target_dir=target_dir)
    else:
        fetch_result = __salt__['artifactory.get_release'](artifactory_url=artifact['artifactory_url'],
                                                           repository=artifact['repository'],
                                                           group_id=artifact['group_id'],
                                                           artifact_id=artifact['artifact_id'],
                                                           packaging=artifact['packaging'],
                                                           version=artifact['version'],
                                                           target_dir=target_dir)
    return fetch_result


def reloaded(name, jboss_config, timeout=60, interval=5):
    '''
    Reloads configuration of jboss server.

    jboss_config:
        Dict with connection properties (see state description)
    timeout:
        Time to wait until jboss is back in running state. Default timeout is 60s.
    interval:
        Interval between state checks. Default interval is 5s. Decreasing the interval may slightly decrease waiting time
        but be aware that every status check is a call to jboss-cli which is a java process. If interval is smaller than
        process cleanup time it may easily lead to excessive resource consumption.

    This step performs the following operations:

    * Ensures that server is in running or reload-required state (by reading server-state attribute)
    * Reloads configuration
    * Waits for server to reload and be in running state

    Example:

    .. code-block:: yaml

        configuration_reloaded:
           jboss7.reloaded:
            - jboss_config: {{ pillar['jboss'] }}
    '''
    log.debug(" ======================== STATE: jboss7.reloaded (name: %s) ", name)
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    status = __salt__['jboss7.status'](jboss_config)
    if not status['success'] or status['result'] not in ('running', 'reload-required'):
        ret['result'] = False
        ret['comment'] = "Cannot reload server configuration, it should be up and in 'running' or 'reload-required' state."
        return ret

    result = __salt__['jboss7.reload'](jboss_config)
    if result['success'] or \
                    'Operation failed: Channel closed' in result['stdout'] or \
                    'Communication error: java.util.concurrent.ExecutionException: Operation failed' in result['stdout']:
        wait_time = 0
        status = None
        while (status is None or not status['success'] or status['result'] != 'running') and wait_time < timeout:
            time.sleep(interval)
            wait_time += interval
            status = __salt__['jboss7.status'](jboss_config)

        if status['success'] and status['result'] == 'running':
            ret['result'] = True
            ret['comment'] = 'Configuration reloaded'
            ret['changes']['reloaded'] = 'configuration'
        else:
            ret['result'] = False
            ret['comment'] = 'Could not reload the configuration. Timeout ({0} s) exceeded. '.format(timeout)
            if not status['success']:
                ret['comment'] = __append_comment('Could not connect to JBoss controller.', ret['comment'])
            else:
                ret['comment'] = __append_comment(('Server is in {0} state'.format(status['result'])), ret['comment'])
    else:
        ret['result'] = False
        ret['comment'] = 'Could not reload the configuration, stdout:'+result['stdout']

    return ret


def __check_dict_contains(dct, dict_name, keys, comment='', result=True):
    for key in keys:
        if key not in six.iterkeys(dct):
            result = False
            comment = __append_comment("Missing {0} in {1}".format(key, dict_name), comment)
    return result, comment


def __append_comment(new_comment, current_comment=''):
    return current_comment+'\n'+new_comment


def _error(ret, err_msg):
    ret['result'] = False
    ret['comment'] = err_msg
    return ret
