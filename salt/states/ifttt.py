# -*- coding: utf-8 -*-
"""
Trigger an event in IFTTT
=========================

This state is useful for trigging events in IFTTT.

.. versionadded:: 2015.8.0

.. code-block:: yaml

    ifttt-event:
      ifttt.trigger_event:
        - event: TestEvent
        - value1: 'This state was executed successfully.'
        - value2: 'Another value we can send.'
        - value3: 'A third value we can send.'

The api key can be specified in the master or minion configuration like below:
.. code-block:: yaml

    ifttt:
      secret_key: bzMRb-KKIAaNOwKEEw792J7Eb-B3z7muhdhYblJn4V6

"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if the ifttt module is available in __salt__
    """
    return "ifttt" if "ifttt.trigger_event" in __salt__ else False


def trigger_event(name, event, value1=None, value2=None, value3=None):
    """
    Trigger an event in IFTTT

    .. code-block:: yaml

        ifttt-event:
          ifttt.trigger_event:
            - event: TestEvent
            - value1: 'A value that we want to send.'
            - value2: 'A second value that we want to send.'
            - value3: 'A third value that we want to send.'

    The following parameters are required:

    name
        The unique name for this event.

    event
        The name of the event to trigger in IFTTT.

    The following parameters are optional:

    value1
        One of the values that we can send to IFTT.

    value2
        One of the values that we can send to IFTT.

    value3
        One of the values that we can send to IFTT.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if __opts__["test"]:
        ret["comment"] = "The following trigger would be sent to IFTTT: {0}".format(
            event
        )
        ret["result"] = None
        return ret

    ret["result"] = __salt__["ifttt.trigger_event"](
        event=event, value1=value1, value2=value2, value3=value3
    )

    if ret and ret["result"]:
        ret["result"] = True
        ret["comment"] = "Triggered Event: {0}".format(name)
    else:
        ret["comment"] = "Failed to trigger event: {0}".format(name)

    return ret
