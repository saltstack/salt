"""
Create/Close an alert in OpsGenie
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2018.3.0

This state is useful for creating or closing alerts in OpsGenie
during state runs.

.. code-block:: yaml

    used_space:
      disk.status:
        - name: /
        - maximum: 79%
        - minimum: 20%

    opsgenie_create_action_sender:
      opsgenie.create_alert:
        - api_key: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        - reason: 'Disk capacity is out of designated range.'
        - name: disk.status
        - onfail:
          - disk: used_space

    opsgenie_close_action_sender:
      opsgenie.close_alert:
        - api_key: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        - name: disk.status
        - require:
          - disk: used_space

"""

import inspect
import logging

import salt.exceptions

log = logging.getLogger(__name__)


def create_alert(name=None, api_key=None, reason=None, action_type="Create"):
    """
    Create an alert in OpsGenie. Example usage with Salt's requisites and other
    global state arguments could be found above.

    Required Parameters:

    api_key
        It's the API Key you've copied while adding integration in OpsGenie.

    reason
        It will be used as alert's default message in OpsGenie.

    Optional Parameters:

    name
        It will be used as alert's alias. If you want to use the close
        functionality you must provide name field for both states like
        in above case.

    action_type
        OpsGenie supports the default values Create/Close for action_type.
        You can customize this field with OpsGenie's custom actions for
        other purposes like adding notes or acknowledging alerts.
    """

    _, _, _, values = inspect.getargvalues(inspect.currentframe())
    log.info("Arguments values: %s", values)

    ret = {"result": "", "name": "", "changes": "", "comment": ""}

    if api_key is None or reason is None:
        raise salt.exceptions.SaltInvocationError("API Key or Reason cannot be None.")

    if __opts__["test"] is True:
        ret[
            "comment"
        ] = 'Test: {} alert request will be processed using the API Key="{}".'.format(
            action_type, api_key
        )

        # Return ``None`` when running with ``test=true``.
        ret["result"] = None

        return ret

    response_status_code, response_text = __salt__["opsgenie.post_data"](
        api_key=api_key, name=name, reason=reason, action_type=action_type
    )

    if 200 <= response_status_code < 300:
        log.info(
            "POST Request has succeeded with message: %s status code: %s",
            response_text,
            response_status_code,
        )
        ret[
            "comment"
        ] = 'Test: {} alert request will be processed using the API Key="{}".'.format(
            action_type, api_key
        )
        ret["result"] = True
    else:
        log.error(
            "POST Request has failed with error: %s status code: %s",
            response_text,
            response_status_code,
        )
        ret["result"] = False

    return ret


def close_alert(
    name=None, api_key=None, reason="Conditions are met.", action_type="Close"
):
    """
    Close an alert in OpsGenie. It's a wrapper function for create_alert.
    Example usage with Salt's requisites and other global state arguments
    could be found above.

    Required Parameters:

    name
        It will be used as alert's alias. If you want to use the close
        functionality you must provide name field for both states like
        in above case.

    Optional Parameters:

    api_key
        It's the API Key you've copied while adding integration in OpsGenie.

    reason
        It will be used as alert's default message in OpsGenie.

    action_type
        OpsGenie supports the default values Create/Close for action_type.
        You can customize this field with OpsGenie's custom actions for
        other purposes like adding notes or acknowledging alerts.
    """
    if name is None:
        raise salt.exceptions.SaltInvocationError("Name cannot be None.")

    return create_alert(name, api_key, reason, action_type)
