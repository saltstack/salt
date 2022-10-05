"""
Connection module for Telemetry

.. versionadded:: 2016.3.0

https://github.com/mongolab/mongolab-telemetry-api-docs/blob/master/alerts.md

:configuration: This module accepts explicit telemetry credentials or
    can also read api key credentials from a pillar. More Information available
    here__.

.. __: https://github.com/mongolab/mongolab-telemetry-api-docs/blob/master/alerts.md

In the minion's config file:

.. code-block:: yaml

   telemetry.telemetry_api_keys:
     - abc123  # Key 1
     - efg321  # Backup Key 1
   telemetry_api_base_url: https://telemetry-api.mongolab.com/v0

:depends: requests

"""

import logging

import salt.utils.json
import salt.utils.stringutils

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

log = logging.getLogger(__name__)

__virtualname__ = "telemetry"


def __virtual__():
    # Only load if imports exist.
    if not HAS_REQUESTS:
        return False
    return __virtualname__


def _get_telemetry_base(profile):
    config = __salt__["config.option"](profile)
    return config.get("telemetry_api_base_url")


def _auth(api_key=None, profile="telemetry"):
    # return telemetry api key in the header
    if api_key is None and profile is None:
        raise Exception("Missing api_key and profile")
    if profile:
        if isinstance(profile, str):
            _profile = __salt__["config.option"](profile)
        elif isinstance(profile, dict):
            _profile = profile

        if _profile:
            api_key = _profile.get("telemetry_api_keys")[0]
        else:
            raise Exception("Missing api_key")

    return {"Telemetry-API-Key": api_key, "content-type": "application/json"}


def _update_cache(deployment_id, metric_name, alert):
    key = "telemetry.{}.alerts".format(deployment_id)

    if key in __context__:
        alerts = __context__[key]
        alerts[metric_name] = alert
        __context__[key] = alerts

    return __context__.get(key, [])


def _retrieve_channel_id(email, profile="telemetry"):
    """
    Given an email address, checks the local
    cache if corresponding email address: channel_id
    mapping exists

    email
        Email escalation policy
    profile
        A dict of telemetry config information.
    """
    key = "telemetry.channels"
    auth = _auth(profile=profile)

    if key not in __context__:
        get_url = (
            _get_telemetry_base(profile)
            + "/notification-channels?_type=EmailNotificationChannel"
        )
        response = requests.get(get_url, headers=auth)

        if response.status_code == 200:
            cache_result = {}
            for index, alert in enumerate(response.json()):
                cache_result[alert.get("email")] = alert.get("_id", "false")

            __context__[key] = cache_result

    return __context__[key].get(email, False)


def get_alert_config(
    deployment_id, metric_name=None, api_key=None, profile="telemetry"
):
    """
    Get all alert definitions associated with a given deployment or if metric_name
    is specified, obtain the specific alert config

    Returns dictionary or list of dictionaries.

    CLI Example:

    .. code-block:: bash

        salt myminion telemetry.get_alert_config rs-ds033197 currentConnections profile=telemetry
        salt myminion telemetry.get_alert_config rs-ds033197 profile=telemetry
    """

    auth = _auth(profile=profile)
    alert = False

    key = "telemetry.{}.alerts".format(deployment_id)

    if key not in __context__:
        try:
            get_url = _get_telemetry_base(profile) + "/alerts?deployment={}".format(
                deployment_id
            )
            response = requests.get(get_url, headers=auth)
        except requests.exceptions.RequestException as e:
            log.error(str(e))
            return False

        http_result = {}
        if response.status_code == 200:
            for alert in response.json():
                http_result[alert.get("condition", {}).get("metric")] = alert
                __context__[key] = http_result

    if not __context__.get(key):
        return []

    alerts = __context__[key].values()

    if metric_name:
        return __context__[key].get(metric_name)

    return [alert["_id"] for alert in alerts if "_id" in alert]


def get_notification_channel_id(notify_channel, profile="telemetry"):
    """
    Given an email address, creates a notification-channels
    if one is not found and also returns the corresponding
    notification channel id.

    notify_channel
        Email escalation policy
    profile
        A dict of telemetry config information.

    CLI Example:

    .. code-block:: bash

        salt myminion telemetry.get_notification_channel_id userx@company.com profile=telemetry
    """

    # This helper is used to procure the channel ids
    # used to notify when the alarm threshold is violated
    auth = _auth(profile=profile)

    notification_channel_id = _retrieve_channel_id(notify_channel)

    if not notification_channel_id:
        log.info("%s channel does not exist, creating.", notify_channel)

        # create the notification channel and cache the id
        post_url = _get_telemetry_base(profile) + "/notification-channels"
        data = {
            "_type": "EmailNotificationChannel",
            "name": notify_channel[: notify_channel.find("@")] + "EscalationPolicy",
            "email": notify_channel,
        }
        response = requests.post(
            post_url, data=salt.utils.json.dumps(data), headers=auth
        )
        if response.status_code == 200:
            log.info(
                "Successfully created EscalationPolicy %s with"
                " EmailNotificationChannel %s",
                data.get("name"),
                notify_channel,
            )
            notification_channel_id = response.json().get("_id")
            __context__["telemetry.channels"][notify_channel] = notification_channel_id
        else:
            raise Exception(
                "Failed to created notification channel {}".format(notify_channel)
            )

    return notification_channel_id


def get_alarms(deployment_id, profile="telemetry"):
    """
    get all the alarms set up against the current deployment

    Returns dictionary of alarm information

    CLI Example:

    .. code-block:: bash

        salt myminion telemetry.get_alarms rs-ds033197 profile=telemetry

    """
    auth = _auth(profile=profile)

    try:
        response = requests.get(
            _get_telemetry_base(profile)
            + "/alerts?deployment={}".format(deployment_id),
            headers=auth,
        )
    except requests.exceptions.RequestException as e:
        log.error(str(e))
        return False

    if response.status_code == 200:
        alarms = response.json()

        if len(alarms) > 0:
            return alarms

        return "No alarms defined for deployment: {}".format(deployment_id)
    else:
        # Non 200 response, sent back the error response'
        return {
            "err_code": response.status_code,
            "err_msg": salt.utils.json.loads(response.text).get("err", ""),
        }


def create_alarm(deployment_id, metric_name, data, api_key=None, profile="telemetry"):
    """
    create an telemetry alarms.

    data is a dict of alert configuration data.

    Returns (bool success, str message) tuple.

    CLI Example:

    .. code-block:: bash

        salt myminion telemetry.create_alarm rs-ds033197 {} profile=telemetry

    """

    auth = _auth(api_key, profile)
    request_uri = _get_telemetry_base(profile) + "/alerts"

    key = "telemetry.{}.alerts".format(deployment_id)

    # set the notification channels if not already set
    post_body = {
        "deployment": deployment_id,
        "filter": data.get("filter"),
        "notificationChannel": get_notification_channel_id(
            data.get("escalate_to")
        ).split(),
        "condition": {
            "metric": metric_name,
            "max": data.get("max"),
            "min": data.get("min"),
        },
    }

    try:
        response = requests.post(
            request_uri, data=salt.utils.json.dumps(post_body), headers=auth
        )
    except requests.exceptions.RequestException as e:
        # TODO: May be we should retry?
        log.error(str(e))

    if response.status_code >= 200 and response.status_code < 300:
        # update cache
        log.info(
            "Created alarm on metric: %s in deployment: %s", metric_name, deployment_id
        )
        log.debug(
            "Updating cache for metric %s in deployment %s: %s",
            metric_name,
            deployment_id,
            response.json(),
        )
        _update_cache(deployment_id, metric_name, response.json())
    else:
        log.error(
            "Failed to create alarm on metric: %s in deployment %s: payload: %s",
            metric_name,
            deployment_id,
            salt.utils.json.dumps(post_body),
        )

    return response.status_code >= 200 and response.status_code < 300, response.json()


def update_alarm(deployment_id, metric_name, data, api_key=None, profile="telemetry"):
    """
    update an telemetry alarms. data is a dict of alert configuration data.

    Returns (bool success, str message) tuple.

    CLI Example:

    .. code-block:: bash

        salt myminion telemetry.update_alarm rs-ds033197 {} profile=telemetry

    """
    auth = _auth(api_key, profile)
    alert = get_alert_config(deployment_id, metric_name, api_key, profile)

    if not alert:
        return (
            False,
            "No entity found matching deployment {} and alarms {}".format(
                deployment_id, metric_name
            ),
        )

    request_uri = _get_telemetry_base(profile) + "/alerts/" + alert["_id"]

    # set the notification channels if not already set
    post_body = {
        "deployment": deployment_id,
        "filter": data.get("filter"),
        "notificationChannel": get_notification_channel_id(
            data.get("escalate_to")
        ).split(),
        "condition": {
            "metric": metric_name,
            "max": data.get("max"),
            "min": data.get("min"),
        },
    }

    try:
        response = requests.put(
            request_uri, data=salt.utils.json.dumps(post_body), headers=auth
        )
    except requests.exceptions.RequestException as e:
        log.error("Update failed: %s", e)
        return False, str(e)

    if response.status_code >= 200 and response.status_code < 300:
        # Also update cache
        log.debug(
            "Updating cache for metric %s in deployment %s: %s",
            metric_name,
            deployment_id,
            response.json(),
        )
        _update_cache(deployment_id, metric_name, response.json())
        log.info(
            "Updated alarm on metric: %s in deployment: %s", metric_name, deployment_id
        )
        return True, response.json()

    err_msg = (
        "Failed to create alarm on metric: {} in deployment: {} payload: {}".format(
            salt.utils.stringutils.to_unicode(metric_name),
            salt.utils.stringutils.to_unicode(deployment_id),
            salt.utils.json.dumps(post_body),
        )
    )
    log.error(err_msg)
    return False, err_msg


def delete_alarms(
    deployment_id, alert_id=None, metric_name=None, api_key=None, profile="telemetry"
):
    """delete an alert specified by alert_id or if not specified blows away all the alerts
         in the current deployment.

    Returns (bool success, str message) tuple.

    CLI Example:

    .. code-block:: bash

        salt myminion telemetry.delete_alarms rs-ds033197 profile=telemetry

    """
    auth = _auth(profile=profile)

    if alert_id is None:
        # Delete all the alarms associated with this deployment
        alert_ids = get_alert_config(deployment_id, api_key=api_key, profile=profile)
    else:
        alert_ids = [alert_id]

    if len(alert_ids) == 0:
        return (
            False,
            "failed to find alert associated with deployment: {}".format(deployment_id),
        )

    failed_to_delete = []
    for id in alert_ids:
        delete_url = _get_telemetry_base(profile) + "/alerts/{}".format(id)

        try:
            response = requests.delete(delete_url, headers=auth)
            if metric_name:
                log.debug(
                    "updating cache and delete %s key from %s",
                    metric_name,
                    deployment_id,
                )
                _update_cache(deployment_id, metric_name, None)

        except requests.exceptions.RequestException as e:
            log.error("Delete failed: %s", e)

        if response.status_code != 200:
            failed_to_delete.append(id)

    if len(failed_to_delete) > 0:
        return (
            False,
            "Failed to delete {} alarms in deployment: {}".format(
                ", ".join(failed_to_delete), deployment_id
            ),
        )

    return (
        True,
        "Successfully deleted {} alerts in deployment: {}".format(
            ", ".join(alert_ids), deployment_id
        ),
    )
