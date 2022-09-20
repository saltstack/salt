"""
Module for handling OpenStack Heat calls

.. versionadded:: 2017.7.0

:depends:   - heatclient Python module
:configuration: This module is not usable until the user, password, tenant, and
    auth URL are specified either in a pillar or in the minion's config file.
    For example::

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.insecure: False   #(optional)
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
        # Optional
        keystone.region_name: 'RegionOne'

    If configuration for multiple OpenStack accounts is required, they can be
    set up as different configuration profiles:
    For example::

        openstack1:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

        openstack2:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'

    With this configuration in place, any of the heat functions can make use of
    a configuration profile by declaring it explicitly.
    For example::

        salt '*' heat.flavor_list profile=openstack1
"""

import logging
import time

import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.versions
import salt.utils.yaml
from salt.exceptions import SaltInvocationError

# pylint: disable=import-error
HAS_HEAT = False
try:
    import heatclient

    HAS_HEAT = True
except ImportError:
    pass

HAS_OSLO = False
try:
    from oslo_serialization import jsonutils

    HAS_OSLO = True
except ImportError:
    pass

SECTIONS = (PARAMETER_DEFAULTS, PARAMETERS, RESOURCE_REGISTRY, EVENT_SINKS) = (
    "parameter_defaults",
    "parameters",
    "resource_registry",
    "event_sinks",
)

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load this module if heat
    is installed on this minion.
    """
    if HAS_HEAT and HAS_OSLO:
        return "heat"
    return (
        False,
        "The heat execution module cannot be loaded: "
        "the heatclient and oslo_serialization"
        # 'the heatclient and keystoneclient and oslo_serialization'
        " python library is not available.",
    )


def _auth(profile=None, api_version=1, **connection_args):
    """
    Set up heat credentials, returns
    `heatclient.client.Client`. Optional parameter
    "api_version" defaults to 1.

    Only intended to be used within heat-enabled modules
    """

    if profile:
        prefix = profile + ":keystone."
    else:
        prefix = "keystone."

    def get(key, default=None):
        """
        Checks connection_args, then salt-minion config,
        falls back to specified default value.
        """
        return connection_args.get(
            "connection_" + key, __salt__["config.get"](prefix + key, default)
        )

    user = get("user", "admin")
    password = get("password", None)
    tenant = get("tenant", "admin")
    tenant_id = get("tenant_id")
    auth_url = get("auth_url", "http://127.0.0.1:35357/v2.0")
    insecure = get("insecure", False)
    admin_token = get("token")
    region_name = get("region_name", None)

    if admin_token and api_version != 1 and not password:
        # If we had a password we could just
        # ignore the admin-token and move on...
        raise SaltInvocationError(
            "Only can use keystone admin token " + "with Heat API v1"
        )
    elif password:
        # Can't use the admin-token anyway
        kwargs = {
            "username": user,
            "password": password,
            "tenant_id": tenant_id,
            "auth_url": auth_url,
            "region_name": region_name,
            "tenant_name": tenant,
        }
        # 'insecure' keyword not supported by all v2.0 keystone clients
        #   this ensures it's only passed in when defined
        if insecure:
            kwargs["insecure"] = True
    elif api_version == 1 and admin_token:
        kwargs = {"token": admin_token, "auth_url": auth_url}
    else:
        raise SaltInvocationError("No credentials to authenticate with.")

    token = __salt__["keystone.token_get"](profile)
    kwargs["token"] = token["id"]
    # This doesn't realy prevent the password to show up
    # in the minion log as keystoneclient.session is
    # logging it anyway when in debug-mode
    kwargs.pop("password")
    try:
        heat_endpoint = __salt__["keystone.endpoint_get"]("heat", profile)["url"]
    except KeyError:
        heat_endpoint = __salt__["keystone.endpoint_get"]("heat", profile)["publicurl"]
    heat_endpoint = heat_endpoint % token
    log.debug(
        "Calling heatclient.client.Client(%s, %s, **%s)",
        api_version,
        heat_endpoint,
        kwargs,
    )
    # may raise exc.HTTPUnauthorized, exc.HTTPNotFound
    # but we deal with those elsewhere
    return heatclient.client.Client(api_version, endpoint=heat_endpoint, **kwargs)


def _parse_template(tmpl_str):
    """
    Parsing template
    """
    tmpl_str = tmpl_str.strip()
    if tmpl_str.startswith("{"):
        tpl = salt.utils.json.loads(tmpl_str)
    else:
        try:
            tpl = salt.utils.yaml.safe_load(tmpl_str)
        except salt.utils.yaml.YAMLError as exc:
            raise ValueError(str(exc))
        else:
            if tpl is None:
                tpl = {}
    if not (
        "HeatTemplateFormatVersion" in tpl
        or "heat_template_version" in tpl
        or "AWSTemplateFormatVersion" in tpl
    ):
        raise ValueError("Template format version not found.")
    return tpl


def _parse_environment(env_str):
    """
    Parsing template
    """
    try:
        env = salt.utils.yaml.safe_load(env_str)
    except salt.utils.yaml.YAMLError as exc:
        raise ValueError(str(exc))
    else:
        if env is None:
            env = {}
        elif not isinstance(env, dict):
            raise ValueError("The environment is not a valid YAML mapping data type.")

    for param in env:
        if param not in SECTIONS:
            raise ValueError('environment has wrong section "{}"'.format(param))

    return env


def _get_stack_events(h_client, stack_id, event_args):
    """
    Get event for stack
    """
    event_args["stack_id"] = stack_id
    event_args["resource_name"] = None
    try:
        events = h_client.events.list(**event_args)
    except heatclient.exc.HTTPNotFound as exc:
        raise heatclient.exc.CommandError(str(exc))
    else:
        for event in events:
            event.stack_name = stack_id.split("/")[0]
        return events


def _poll_for_events(
    h_client, stack_name, action=None, poll_period=5, timeout=60, marker=None
):
    """
    Polling stack events
    """
    if action:
        stop_status = ("{}_FAILED".format(action), "{}_COMPLETE".format(action))
        stop_check = lambda a: a in stop_status
    else:
        stop_check = lambda a: a.endswith("_COMPLETE") or a.endswith("_FAILED")
    timeout_sec = timeout * 60
    no_event_polls = 0
    msg_template = "\n Stack %(name)s %(status)s \n"
    while True:
        events = _get_stack_events(
            h_client,
            stack_id=stack_name,
            event_args={"sort_dir": "asc", "marker": marker},
        )

        if not events:
            no_event_polls += 1
        else:
            no_event_polls = 0
            # set marker to last event that was received.
            marker = getattr(events[-1], "id", None)
            for event in events:
                # check if stack event was also received
                if getattr(event, "resource_name", "") == stack_name:
                    stack_status = getattr(event, "resource_status", "")
                    msg = msg_template % dict(name=stack_name, status=stack_status)
                    if stop_check(stack_status):
                        return stack_status, msg

        if no_event_polls >= 2:
            # after 2 polls with no events, fall back to a stack get
            stack = h_client.stacks.get(stack_name)
            stack_status = stack.stack_status
            msg = msg_template % dict(name=stack_name, status=stack_status)
            if stop_check(stack_status):
                return stack_status, msg
            # go back to event polling again
            no_event_polls = 0

        time.sleep(poll_period)
        timeout_sec -= poll_period
        if timeout_sec <= 0:
            stack_status = "{}_FAILED".format(action)
            msg = "Timeout expired"
            return stack_status, msg


def list_stack(profile=None):
    """
    Return a list of available stack (heat stack-list)

    profile
        Profile to use

    CLI Example:

    .. code-block:: bash

        salt '*' heat.list_stack profile=openstack1
    """
    ret = {}
    h_client = _auth(profile)
    for stack in h_client.stacks.list():
        links = {}
        for link in stack.links:
            links[link["rel"]] = link["href"]
        ret[stack.stack_name] = {
            "status": stack.stack_status,
            "id": stack.id,
            "name": stack.stack_name,
            "creation": stack.creation_time,
            "owner": stack.stack_owner,
            "reason": stack.stack_status_reason,
            "links": links,
        }
    return ret


def show_stack(name=None, profile=None):
    """
    Return details about a specific stack (heat stack-show)

    name
        Name of the stack

    profile
        Profile to use

    CLI Example:

    .. code-block:: bash

        salt '*' heat.show_stack name=mystack profile=openstack1
    """
    h_client = _auth(profile)
    if not name:
        return {"result": False, "comment": "Parameter name missing or None"}
    try:
        ret = {}
        stack = h_client.stacks.get(name)
        links = {}
        for link in stack.links:
            links[link["rel"]] = link["href"]
        ret[stack.stack_name] = {
            "status": stack.stack_status,
            "id": stack.id,
            "name": stack.stack_name,
            "creation": stack.creation_time,
            "owner": stack.stack_owner,
            "reason": stack.stack_status_reason,
            "parameters": stack.parameters,
            "links": links,
        }
        ret["result"] = True
    except heatclient.exc.HTTPNotFound:
        return {"result": False, "comment": "No stack {}".format(name)}
    return ret


def delete_stack(name=None, poll=0, timeout=60, profile=None):
    """
    Delete a stack (heat stack-delete)

    name
        Name of the stack

    poll
        Poll and report events until stack complete

    timeout
        Stack creation timeout in minute

    profile
        Profile to use

    CLI Examples:

    .. code-block:: bash

        salt '*' heat.delete_stack name=mystack poll=5 \\
                 profile=openstack1
    """
    h_client = _auth(profile)
    ret = {"result": True, "comment": ""}
    if not name:
        ret["result"] = False
        ret["comment"] = "Parameter name missing or None"
        return ret
    try:
        h_client.stacks.delete(name)
    except heatclient.exc.HTTPNotFound:
        ret["result"] = False
        ret["comment"] = "No stack {}".format(name)
    except heatclient.exc.HTTPForbidden as forbidden:
        log.exception(forbidden)
        ret["result"] = False
        ret["comment"] = str(forbidden)
    if ret["result"] is False:
        return ret

    if poll > 0:
        try:
            stack_status, msg = _poll_for_events(
                h_client, name, action="DELETE", poll_period=poll, timeout=timeout
            )
        except heatclient.exc.CommandError:
            ret["comment"] = "Deleted stack {}.".format(name)
            return ret
        except Exception as ex:  # pylint: disable=W0703
            log.exception("Delete failed %s", ex)
            ret["result"] = False
            ret["comment"] = "{}".format(ex)
            return ret

        if stack_status == "DELETE_FAILED":
            ret["result"] = False
            ret["comment"] = "Deleted stack FAILED'{}'{}.".format(name, msg)
        else:
            ret["comment"] = "Deleted stack {}.".format(name)
    return ret


def create_stack(
    name=None,
    template_file=None,
    environment=None,
    parameters=None,
    poll=0,
    rollback=False,
    timeout=60,
    profile=None,
):
    """
    Create a stack (heat stack-create)

    name
        Name of the new stack

    template_file
        File of template

    environment
        File of environment

    parameters
        Parameter dict used to create the stack

    poll
        Poll and report events until stack complete

    rollback
        Enable rollback on create failure

    timeout
        Stack creation timeout in minutes

    profile
        Profile to build on

    CLI Example:

    .. code-block:: bash

        salt '*' heat.create_stack name=mystack \\
                 template_file=salt://template.yaml \\
                 environment=salt://environment.yaml \\
                 parameters="{"image": "Debian 8", "flavor": "m1.small"}" \\
                 poll=5 rollback=False timeout=60 profile=openstack1

    .. versionadded:: 2017.7.5,2018.3.1

        The spelling mistake in parameter `enviroment` was corrected to `environment`.
        The `enviroment` spelling mistake has been removed in Salt 3000.

    """
    h_client = _auth(profile)
    ret = {"result": True, "comment": ""}
    if not parameters:
        parameters = {}
    if template_file:
        template_tmp_file = salt.utils.files.mkstemp()
        tsfn, source_sum, comment_ = __salt__["file.get_managed"](
            name=template_tmp_file,
            template=None,
            source=template_file,
            source_hash=None,
            source_hash_name=None,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            context=None,
            defaults=None,
            skip_verify=False,
            kwargs=None,
        )

        template_manage_result = __salt__["file.manage_file"](
            name=template_tmp_file,
            sfn=tsfn,
            ret=None,
            source=template_file,
            source_sum=source_sum,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            backup=None,
            makedirs=True,
            template=None,
            show_changes=False,
            contents=None,
            dir_mode=None,
        )
        if template_manage_result["result"]:
            with salt.utils.files.fopen(template_tmp_file, "r") as tfp_:
                tpl = salt.utils.stringutils.to_unicode(tfp_.read())
                salt.utils.files.safe_rm(template_tmp_file)
                try:
                    template = _parse_template(tpl)
                except ValueError as ex:
                    ret["result"] = False
                    ret["comment"] = "Error parsing template {}".format(ex)
        else:
            ret["result"] = False
            ret["comment"] = "Can not open template: {} {}".format(
                template_file, comment_
            )
    else:
        ret["result"] = False
        ret["comment"] = "Can not open template"
    if ret["result"] is False:
        return ret

    kwargs = {}
    kwargs["template"] = template
    try:
        h_client.stacks.validate(**kwargs)
    except Exception as ex:  # pylint: disable=W0703
        log.exception("Template not valid %s", ex)
        ret["result"] = False
        ret["comment"] = "Template not valid {}".format(ex)
        return ret
    env = {}
    if environment:
        environment_tmp_file = salt.utils.files.mkstemp()
        esfn, source_sum, comment_ = __salt__["file.get_managed"](
            name=environment_tmp_file,
            template=None,
            source=environment,
            source_hash=None,
            source_hash_name=None,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            context=None,
            defaults=None,
            skip_verify=False,
            kwargs=None,
        )

        environment_manage_result = __salt__["file.manage_file"](
            name=environment_tmp_file,
            sfn=esfn,
            ret=None,
            source=environment,
            source_sum=source_sum,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            backup=None,
            makedirs=True,
            template=None,
            show_changes=False,
            contents=None,
            dir_mode=None,
        )
        if environment_manage_result["result"]:
            with salt.utils.files.fopen(environment_tmp_file, "r") as efp_:
                env_str = salt.utils.stringutils.to_unicode(efp_.read())
                salt.utils.files.safe_rm(environment_tmp_file)
                try:
                    env = _parse_environment(env_str)
                except ValueError as ex:
                    ret["result"] = False
                    ret["comment"] = "Error parsing template {}".format(ex)
        else:
            ret["result"] = False
            ret["comment"] = "Can not open environment: {}, {}".format(
                environment, comment_
            )
    if ret["result"] is False:
        return ret

    fields = {
        "stack_name": name,
        "disable_rollback": not rollback,
        "parameters": parameters,
        "template": template,
        "environment": env,
        "timeout_mins": timeout,
    }

    # If one or more environments is found, pass the listing to the server
    try:
        h_client.stacks.create(**fields)
    except Exception as ex:  # pylint: disable=W0703
        log.exception("Create failed %s", ex)
        ret["result"] = False
        ret["comment"] = "{}".format(ex)
        return ret
    if poll > 0:
        stack_status, msg = _poll_for_events(
            h_client, name, action="CREATE", poll_period=poll, timeout=timeout
        )
        if stack_status == "CREATE_FAILED":
            ret["result"] = False
            ret["comment"] = "Created stack FAILED'{}'{}.".format(name, msg)
    if ret["result"] is True:
        ret["comment"] = "Created stack '{}'.".format(name)
    return ret


def update_stack(
    name=None,
    template_file=None,
    environment=None,
    parameters=None,
    poll=0,
    rollback=False,
    timeout=60,
    profile=None,
):
    """
    Update a stack (heat stack-template)

    name
        Name of the  stack

    template_file
        File of template

    environment
        File of environment

    parameters
        Parameter dict used to update the stack

    poll
        Poll and report events until stack complete

    rollback
        Enable rollback on update failure

    timeout
        Stack creation timeout in minutes

    profile
        Profile to build on

    CLI Example:

    .. code-block:: bash

        salt '*' heat.update_stack name=mystack \\
                 template_file=salt://template.yaml \\
                 environment=salt://environment.yaml \\
                 parameters="{"image": "Debian 8", "flavor": "m1.small"}" \\
                 poll=5 rollback=False timeout=60 profile=openstack1

    .. versionadded:: 2017.7.5,2018.3.1

        The spelling mistake in parameter `enviroment` was corrected to `environment`.
        The `enviroment` spelling mistake has been removed in Salt 3000.

    """
    h_client = _auth(profile)
    ret = {"result": True, "comment": ""}
    if not name:
        ret["result"] = False
        ret["comment"] = "Parameter name missing or None"
        return ret
    if not parameters:
        parameters = {}
    if template_file:
        template_tmp_file = salt.utils.files.mkstemp()
        tsfn, source_sum, comment_ = __salt__["file.get_managed"](
            name=template_tmp_file,
            template=None,
            source=template_file,
            source_hash=None,
            source_hash_name=None,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            context=None,
            defaults=None,
            skip_verify=False,
            kwargs=None,
        )

        template_manage_result = __salt__["file.manage_file"](
            name=template_tmp_file,
            sfn=tsfn,
            ret=None,
            source=template_file,
            source_sum=source_sum,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            backup=None,
            makedirs=True,
            template=None,
            show_changes=False,
            contents=None,
            dir_mode=None,
        )
        if template_manage_result["result"]:
            with salt.utils.files.fopen(template_tmp_file, "r") as tfp_:
                tpl = salt.utils.stringutils.to_unicode(tfp_.read())
                salt.utils.files.safe_rm(template_tmp_file)
                try:
                    template = _parse_template(tpl)
                except ValueError as ex:
                    ret["result"] = False
                    ret["comment"] = "Error parsing template {}".format(ex)
        else:
            ret["result"] = False
            ret["comment"] = "Can not open template: {} {}".format(
                template_file, comment_
            )
    else:
        ret["result"] = False
        ret["comment"] = "Can not open template"
    if ret["result"] is False:
        return ret

    kwargs = {}
    kwargs["template"] = template
    try:
        h_client.stacks.validate(**kwargs)
    except Exception as ex:  # pylint: disable=W0703
        log.exception("Template not valid %s", ex)
        ret["result"] = False
        ret["comment"] = "Template not valid {}".format(ex)
        return ret
    env = {}
    if environment:
        environment_tmp_file = salt.utils.files.mkstemp()
        esfn, source_sum, comment_ = __salt__["file.get_managed"](
            name=environment_tmp_file,
            template=None,
            source=environment,
            source_hash=None,
            source_hash_name=None,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            context=None,
            defaults=None,
            skip_verify=False,
            kwargs=None,
        )

        environment_manage_result = __salt__["file.manage_file"](
            name=environment_tmp_file,
            sfn=esfn,
            ret=None,
            source=environment,
            source_sum=source_sum,
            user=None,
            group=None,
            mode=None,
            attrs=None,
            saltenv="base",
            backup=None,
            makedirs=True,
            template=None,
            show_changes=False,
            contents=None,
            dir_mode=None,
        )
        if environment_manage_result["result"]:
            with salt.utils.files.fopen(environment_tmp_file, "r") as efp_:
                env_str = salt.utils.stringutils.to_unicode(efp_.read())
                salt.utils.files.safe_rm(environment_tmp_file)
                try:
                    env = _parse_environment(env_str)
                except ValueError as ex:
                    ret["result"] = False
                    ret["comment"] = "Error parsing template {}".format(ex)
        else:
            ret["result"] = False
            ret["comment"] = "Can not open environment: {}, {}".format(
                environment, comment_
            )
    if ret["result"] is False:
        return ret

    fields = {
        "disable_rollback": not rollback,
        "parameters": parameters,
        "template": template,
        "environment": env,
        "timeout_mins": timeout,
    }

    try:
        h_client.stacks.update(name, **fields)
    except Exception as ex:  # pylint: disable=W0703
        log.exception("Update failed %s", ex)
        ret["result"] = False
        ret["comment"] = "Update failed {}".format(ex)
        return ret

    if poll > 0:
        stack_status, msg = _poll_for_events(
            h_client, name, action="UPDATE", poll_period=poll, timeout=timeout
        )
        if stack_status == "UPDATE_FAILED":
            ret["result"] = False
            ret["comment"] = "Updated stack FAILED'{}'{}.".format(name, msg)
    if ret["result"] is True:
        ret["comment"] = ("Updated stack '{}'.".format(name),)
    return ret


def template_stack(name=None, profile=None):
    """
    Return template a specific stack (heat stack-template)

    name
        Name of the stack

    profile
        Profile to use

    CLI Example:

    .. code-block:: bash

        salt '*' heat.template_stack name=mystack profile=openstack1
    """
    h_client = _auth(profile)

    if not name:
        return {"result": False, "comment": "Parameter name missing or None"}
    try:
        get_template = h_client.stacks.template(name)
    except heatclient.exc.HTTPNotFound:
        return {"result": False, "comment": "No stack with {}".format(name)}
    except heatclient.exc.BadRequest:
        return {"result": False, "comment": "Bad request fot stack {}".format(name)}
    if "heat_template_version" in get_template:
        template = salt.utils.yaml.safe_dump(get_template)
    else:
        template = jsonutils.dumps(get_template, indent=2, ensure_ascii=False)

    checksum = __salt__["hashutil.digest"](template)
    ret = {"template": template, "result": True, "checksum": checksum}
    return ret
