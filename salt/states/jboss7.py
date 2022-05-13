"""
Manage JBoss 7 Application Server via CLI interface

.. versionadded:: 2015.5.0

This state uses the jboss-cli.sh script from a JBoss or Wildfly installation and parses its output to determine the execution result.

In order to run each state, a jboss_config dictionary with the following properties must be passed:

.. code-block:: yaml

   jboss:
      cli_path: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
      controller: 10.11.12.13:9999
      cli_user: 'jbossadm'
      cli_password: 'jbossadm'

If the controller doesn't require a password, then the cli_user and cli_password parameters are optional.

Since same dictionary with configuration will be used in all the states, it may be more convenient to move JBoss configuration and other properties
to the pillar.

Example of application deployment from local filesystem:

.. code-block:: yaml

     application_deployed:
       jboss7.deployed:
         - salt_source:
             target_file: '/tmp/webapp.war'
         - jboss_config: {{ pillar['jboss'] }}

For the sake of brevity, examples for each state assume that jboss_config is contained in the pillar.


"""


import logging
import re
import time
import traceback

import salt.utils.dictdiffer as dictdiffer
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def datasource_exists(
    name, jboss_config, datasource_properties, recreate=False, profile=None
):
    """
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
    profile : None
        The profile name for this datasource (domain mode only)

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
           - profile: full-ha

    """
    log.debug(
        " ======================== STATE: jboss7.datasource_exists (name: %s) ", name
    )
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    has_changed = False
    ds_current_properties = {}
    ds_result = __salt__["jboss7.read_datasource"](
        jboss_config=jboss_config, name=name, profile=profile
    )
    if ds_result["success"]:
        ds_current_properties = ds_result["result"]
        if recreate:
            remove_result = __salt__["jboss7.remove_datasource"](
                jboss_config=jboss_config, name=name, profile=profile
            )
            if remove_result["success"]:
                ret["changes"]["removed"] = name
            else:
                ret["result"] = False
                ret["comment"] = (
                    "Could not remove datasource. Stdout: " + remove_result["stdout"]
                )
                return ret

            has_changed = True  # if we are here, we have already made a change

            create_result = __salt__["jboss7.create_datasource"](
                jboss_config=jboss_config,
                name=name,
                datasource_properties=datasource_properties,
                profile=profile,
            )
            if create_result["success"]:
                ret["changes"]["created"] = name
            else:
                ret["result"] = False
                ret["comment"] = (
                    "Could not create datasource. Stdout: " + create_result["stdout"]
                )
                return ret

            read_result = __salt__["jboss7.read_datasource"](
                jboss_config=jboss_config, name=name, profile=profile
            )
            if read_result["success"]:
                ds_new_properties = read_result["result"]
            else:
                ret["result"] = False
                ret["comment"] = (
                    "Could not read datasource. Stdout: " + read_result["stdout"]
                )
                return ret

        else:
            update_result = __salt__["jboss7.update_datasource"](
                jboss_config=jboss_config,
                name=name,
                new_properties=datasource_properties,
                profile=profile,
            )
            if not update_result["success"]:
                ret["result"] = False
                ret["comment"] = (
                    "Could not update datasource. " + update_result["comment"]
                )
                # some changes to the datasource may have already been made, therefore we don't quit here
            else:
                ret["comment"] = "Datasource updated."

            read_result = __salt__["jboss7.read_datasource"](
                jboss_config=jboss_config, name=name, profile=profile
            )
            ds_new_properties = read_result["result"]
    else:
        if ds_result["err_code"] in (
            "JBAS014807",
            "WFLYCTL0216",
        ):  # ok, resource not exists:
            create_result = __salt__["jboss7.create_datasource"](
                jboss_config=jboss_config,
                name=name,
                datasource_properties=datasource_properties,
                profile=profile,
            )
            if create_result["success"]:
                read_result = __salt__["jboss7.read_datasource"](
                    jboss_config=jboss_config, name=name, profile=profile
                )
                ds_new_properties = read_result["result"]
                ret["comment"] = "Datasource created."
            else:
                ret["result"] = False
                ret["comment"] = (
                    "Could not create datasource. Stdout: " + create_result["stdout"]
                )
        else:
            raise CommandExecutionError(
                "Unable to handle error: {}".format(ds_result["failure-description"])
            )

    if ret["result"]:
        log.debug("ds_new_properties=%s", ds_new_properties)
        log.debug("ds_current_properties=%s", ds_current_properties)
        diff = dictdiffer.diff(ds_new_properties, ds_current_properties)

        added = diff.added()
        if len(added) > 0:
            has_changed = True
            ret["changes"]["added"] = __format_ds_changes(
                added, ds_current_properties, ds_new_properties
            )

        removed = diff.removed()
        if len(removed) > 0:
            has_changed = True
            ret["changes"]["removed"] = __format_ds_changes(
                removed, ds_current_properties, ds_new_properties
            )

        changed = diff.changed()
        if len(changed) > 0:
            has_changed = True
            ret["changes"]["changed"] = __format_ds_changes(
                changed, ds_current_properties, ds_new_properties
            )

        if not has_changed:
            ret["comment"] = "Datasource not changed."

    return ret


def __format_ds_changes(keys, old_dict, new_dict):
    log.debug(
        "__format_ds_changes(keys=%s, old_dict=%s, new_dict=%s)",
        keys,
        old_dict,
        new_dict,
    )
    changes = ""
    for key in keys:
        log.debug("key=%s", key)
        if key in old_dict and key in new_dict:
            changes += (
                key
                + ":"
                + __get_ds_value(old_dict, key)
                + "->"
                + __get_ds_value(new_dict, key)
                + "\n"
            )
        elif key in old_dict:
            changes += key + "\n"
        elif key in new_dict:
            changes += key + ":" + __get_ds_value(new_dict, key) + "\n"
    return changes


def __get_ds_value(dct, key):
    log.debug("__get_value(dict,%s)", key)
    if key == "password":
        return "***"
    elif dct[key] is None:
        return "undefined"
    else:
        return str(dct[key])


def bindings_exist(name, jboss_config, bindings, profile=None):
    """
    Ensures that given JNDI binding are present on the server.
    If a binding doesn't exist on the server it will be created.
    If it already exists its value will be changed.

    jboss_config:
        Dict with connection properties (see state description)
    bindings:
        Dict with bindings to set.
    profile:
        The profile name (domain mode only)

    Example:

    .. code-block:: yaml

            jndi_entries_created:
              jboss7.bindings_exist:
               - bindings:
                  'java:global/sampleapp/environment': 'DEV'
                  'java:global/sampleapp/configurationFile': '/var/opt/sampleapp/config.properties'
               - jboss_config: {{ pillar['jboss'] }}

    """
    log.debug(
        " ======================== STATE: jboss7.bindings_exist (name: %s) (profile:"
        " %s) ",
        name,
        profile,
    )
    log.debug("bindings=%s", bindings)
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "Bindings not changed.",
    }

    has_changed = False
    for key in bindings:
        value = str(bindings[key])
        query_result = __salt__["jboss7.read_simple_binding"](
            binding_name=key, jboss_config=jboss_config, profile=profile
        )
        if query_result["success"]:
            current_value = query_result["result"]["value"]
            if current_value != value:
                update_result = __salt__["jboss7.update_simple_binding"](
                    binding_name=key,
                    value=value,
                    jboss_config=jboss_config,
                    profile=profile,
                )
                if update_result["success"]:
                    has_changed = True
                    __log_binding_change(
                        ret["changes"], "changed", key, value, current_value
                    )
                else:
                    raise CommandExecutionError(update_result["failure-description"])
        else:
            if query_result["err_code"] in (
                "JBAS014807",
                "WFLYCTL0216",
            ):  # ok, resource not exists:
                create_result = __salt__["jboss7.create_simple_binding"](
                    binding_name=key,
                    value=value,
                    jboss_config=jboss_config,
                    profile=profile,
                )
                if create_result["success"]:
                    has_changed = True
                    __log_binding_change(ret["changes"], "added", key, value)
                else:
                    raise CommandExecutionError(create_result["failure-description"])
            else:
                raise CommandExecutionError(query_result["failure-description"])

    if has_changed:
        ret["comment"] = "Bindings changed."
    return ret


def __log_binding_change(changes, type_, key, new, old=None):
    if type_ not in changes:
        changes[type_] = ""
    if old is None:
        changes[type_] += key + ":" + new + "\n"
    else:
        changes[type_] += key + ":" + old + "->" + new + "\n"


def deployed(name, jboss_config, salt_source=None):
    """Ensures that the given application is deployed on server.

    jboss_config:
        Dict with connection properties (see state description)
    salt_source:
        How to find the artifact to be deployed.
            target_file:
                Where to look in the minion's file system for the artifact to be deployed (e.g. '/tmp/application-web-0.39.war').  When source is specified,  also specifies where to save the retrieved file.
            source:
                (optional) File on salt master (e.g. salt://application-web-0.39.war).  If absent, no files will be retrieved and the artifact in target_file will be used for the deployment.
            undeploy:
                (optional) Regular expression to match against existing deployments.  When present, if there is a deployment that matches the regular expression, it will be undeployed before the new artifact is deployed.
            undeploy_force:
                (optional) If True, the artifact will be undeployed although it has not changed.

    Examples:

    Deployment of a file from minion's local file system:

    .. code-block:: yaml

        application_deployed:
          jboss7.deployed:
            - salt_source:
                target_file: '/tmp/webapp.war'
            - jboss_config: {{ pillar['jboss'] }}

    It is assumed that /tmp/webapp.war was made available by some
    other means.  No applications will be undeployed; if an existing
    deployment that shares that name exists, then it will be replaced
    with the updated version.

    Deployment of a file from the Salt master's file system:

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

    If the source parameter of salt_source is specified, it can use
    any protocol that the file states use.  This includes not only
    downloading from the master but also HTTP, HTTPS, FTP,
    Amazon S3, and OpenStack Swift.

    """
    log.debug(" ======================== STATE: jboss7.deployed (name: %s) ", name)
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    comment = ""

    validate_success, validate_comment = __validate_arguments(jboss_config, salt_source)
    if not validate_success:
        return _error(ret, validate_comment)

    resolved_source, get_artifact_comment, changed = __get_artifact(salt_source)
    log.debug("resolved_source=%s", resolved_source)
    log.debug("get_artifact_comment=%s", get_artifact_comment)

    comment = __append_comment(
        new_comment=get_artifact_comment, current_comment=comment
    )
    if resolved_source is None:
        return _error(ret, get_artifact_comment)

    find_success, deployment, find_comment = __find_deployment(
        jboss_config, salt_source
    )
    if not find_success:
        return _error(ret, find_comment)

    require_deployment = True

    log.debug("deployment=%s", deployment)
    if deployment is not None:
        if "undeploy_force" in salt_source:
            if salt_source["undeploy_force"]:
                ret["changes"]["undeployed"] = __undeploy(jboss_config, deployment)
            else:
                if changed:
                    ret["changes"]["undeployed"] = __undeploy(jboss_config, deployment)
                else:
                    require_deployment = False
                    comment = __append_comment(
                        new_comment="The artifact {} was already deployed".format(
                            deployment
                        ),
                        current_comment=comment,
                    )
        else:
            ret["changes"]["undeployed"] = __undeploy(jboss_config, deployment)

    if require_deployment:
        deploy_result = __salt__["jboss7.deploy"](
            jboss_config=jboss_config, source_file=resolved_source
        )
        log.debug("deploy_result=%s", str(deploy_result))
        if deploy_result["success"]:
            comment = __append_comment(
                new_comment="Deployment completed.", current_comment=comment
            )
            ret["changes"]["deployed"] = resolved_source
        else:
            comment = __append_comment(
                new_comment="""Deployment failed\nreturn code={retcode}\nstdout='{stdout}'\nstderr='{stderr}""".format(
                    **deploy_result
                ),
                current_comment=comment,
            )
            _error(ret, comment)

    ret["comment"] = comment

    return ret


def __undeploy(jboss_config, deployment):
    __salt__["jboss7.undeploy"](jboss_config, deployment)
    return deployment


def __validate_arguments(jboss_config, salt_source):
    result, comment = __check_dict_contains(
        jboss_config, "jboss_config", ["cli_path", "controller"]
    )
    if salt_source is None:
        result = False
        comment = __append_comment("No salt_source defined", comment)
    result, comment = __check_dict_contains(
        salt_source, "salt_source", ["target_file"], comment, result
    )
    return result, comment


def __find_deployment(jboss_config, salt_source=None):
    result = None
    success = True
    comment = ""
    deployments = __salt__["jboss7.list_deployments"](jboss_config)
    if (
        salt_source is not None
        and "undeploy" in salt_source
        and salt_source["undeploy"]
    ):
        deployment_re = re.compile(salt_source["undeploy"])
        for deployment in deployments:
            if deployment_re.match(deployment):
                if result is not None:
                    success = False
                    comment = (
                        "More than one deployment matches regular expression: {}. \nFor"
                        " deployments from Salt file system deployments on JBoss are"
                        " searched to find one that matches regular expression in"
                        " 'undeploy' parameter.\nExisting deployments: {}".format(
                            salt_source["undeploy"], ",".join(deployments)
                        )
                    )
                else:
                    result = deployment

    return success, result, comment


def __get_artifact(salt_source):
    resolved_source = None
    comment = None
    changed = False

    if salt_source is None:
        log.debug("salt_source == None")
        comment = "No salt_source defined"

    elif isinstance(salt_source, dict):
        log.debug("file from salt master")

        if "source" in salt_source:
            try:
                sfn, source_sum, comment_ = __salt__["file.get_managed"](
                    name=salt_source["target_file"],
                    template=None,
                    source=salt_source["source"],
                    source_hash=None,
                    source_hash_name=None,
                    user=None,
                    group=None,
                    mode=None,
                    attrs=None,
                    saltenv=__env__,
                    context=None,
                    defaults=None,
                    skip_verify=False,
                    kwargs=None,
                )

                manage_result = __salt__["file.manage_file"](
                    name=salt_source["target_file"],
                    sfn=sfn,
                    ret=None,
                    source=salt_source["source"],
                    source_sum=source_sum,
                    user=None,
                    group=None,
                    mode=None,
                    attrs=None,
                    saltenv=__env__,
                    backup=None,
                    makedirs=False,
                    template=None,
                    show_diff=True,
                    contents=None,
                    dir_mode=None,
                )

                if manage_result["result"]:
                    resolved_source = salt_source["target_file"]
                else:
                    comment = manage_result["comment"]

                if manage_result["changes"]:
                    changed = True

            except Exception as e:  # pylint: disable=broad-except
                log.debug(traceback.format_exc())
                comment = "Unable to manage file: {}".format(e)

        else:
            resolved_source = salt_source["target_file"]
            comment = ""

    return resolved_source, comment, changed


def reloaded(name, jboss_config, timeout=60, interval=5):
    """
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
    """
    log.debug(" ======================== STATE: jboss7.reloaded (name: %s) ", name)
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    status = __salt__["jboss7.status"](jboss_config)
    if not status["success"] or status["result"] not in ("running", "reload-required"):
        ret["result"] = False
        ret["comment"] = (
            "Cannot reload server configuration, it should be up and in 'running' or"
            " 'reload-required' state."
        )
        return ret

    result = __salt__["jboss7.reload"](jboss_config)
    if (
        result["success"]
        or "Operation failed: Channel closed" in result["stdout"]
        or "Communication error: java.util.concurrent.ExecutionException: Operation failed"
        in result["stdout"]
    ):
        wait_time = 0
        status = None
        while (
            status is None or not status["success"] or status["result"] != "running"
        ) and wait_time < timeout:
            time.sleep(interval)
            wait_time += interval
            status = __salt__["jboss7.status"](jboss_config)

        if status["success"] and status["result"] == "running":
            ret["result"] = True
            ret["comment"] = "Configuration reloaded"
            ret["changes"]["reloaded"] = "configuration"
        else:
            ret["result"] = False
            ret[
                "comment"
            ] = "Could not reload the configuration. Timeout ({} s) exceeded. ".format(
                timeout
            )
            if not status["success"]:
                ret["comment"] = __append_comment(
                    "Could not connect to JBoss controller.", ret["comment"]
                )
            else:
                ret["comment"] = __append_comment(
                    "Server is in {} state".format(status["result"]), ret["comment"]
                )
    else:
        ret["result"] = False
        ret["comment"] = (
            "Could not reload the configuration, stdout:" + result["stdout"]
        )

    return ret


def __check_dict_contains(dct, dict_name, keys, comment="", result=True):
    for key in keys:
        if key not in dct.keys():
            result = False
            comment = __append_comment(
                "Missing {} in {}".format(key, dict_name), comment
            )
    return result, comment


def __append_comment(new_comment, current_comment=""):
    if current_comment is None and new_comment is None:
        return ""
    if current_comment is None:
        return new_comment
    if new_comment is None:
        return current_comment
    return current_comment + "\n" + new_comment


def _error(ret, err_msg):
    ret["result"] = False
    ret["comment"] = err_msg
    return ret
