"""
Module for sending messages to Pushbullet (https://www.pushbullet.com)

.. versionadded:: 2015.8.0

Requires an ``api_key`` in ``/etc/salt/minion``:

.. code-block:: yaml

    pushbullet:
      api_key: 'ABC123abc123ABC123abc123ABC123ab'

For example:

.. code-block:: yaml

    pushbullet:
      device: "Chrome"
      title: "Example push message"
      body: "Message body."

"""


import logging

try:
    import pushbullet

    HAS_PUSHBULLET = True
except ImportError:
    HAS_PUSHBULLET = False

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_PUSHBULLET:
        return (False, "Missing pushbullet library.")
    if not __salt__["config.get"]("pushbullet.api_key") and not __salt__["config.get"](
        "pushbullet:api_key"
    ):
        return (False, "Pushbullet API Key Unavailable, not loading.")
    return True


class _SaltPushbullet:
    def __init__(self, device_name):
        api_key = __salt__["config.get"]("pushbullet.api_key") or __salt__[
            "config.get"
        ]("pushbullet:api_key")
        self.pb = pushbullet.Pushbullet(api_key)
        self.target = self._find_device_by_name(device_name)

    def push_note(self, title, body):
        push = self.pb.push_note(title, body, device=self.target)
        return push

    def _find_device_by_name(self, name):
        for dev in self.pb.devices:
            if dev.nickname == name:
                return dev


def push_note(device=None, title=None, body=None):
    """
    Pushing a text note.

    :param device:   Pushbullet target device
    :param title:    Note title
    :param body:     Note body

    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt "*" pushbullet.push_note device="Chrome" title="Example title" body="Example body."
    """
    spb = _SaltPushbullet(device)
    res = spb.push_note(title, body)

    return res
