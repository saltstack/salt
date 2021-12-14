"""
Return data by SMS.

.. versionadded:: 2015.5.0

:maintainer:    Damian Myerscough
:maturity:      new
:depends:       twilio
:platform:      all

To enable this returner the minion will need the python twilio library
installed and the following values configured in the minion or master
config:

.. code-block:: yaml

    twilio.sid: 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    twilio.token: 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    twilio.to: '+1415XXXXXXX'
    twilio.from: '+1650XXXXXXX'

To use the sms returner, append '--return sms' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return sms

"""

import logging

import salt.returners

log = logging.getLogger(__name__)

try:
    import twilio

    # Grab version, ensure elements are ints
    twilio_version = tuple([int(x) for x in twilio.__version_info__])
    if twilio_version > (5,):
        TWILIO_5 = False
        from twilio.rest import Client as TwilioRestClient
        from twilio.rest import TwilioException as TwilioRestException
    else:
        TWILIO_5 = True
        from twilio.rest import TwilioRestClient
        from twilio import TwilioRestException  # pylint: disable=no-name-in-module

    HAS_TWILIO = True
except ImportError:
    HAS_TWILIO = False

__virtualname__ = "sms"


def __virtual__():
    if HAS_TWILIO:
        return __virtualname__

    return False, "Could not import sms returner; twilio is not installed."


def _get_options(ret=None):
    """
    Get the Twilio options from salt.
    """
    attrs = {"sid": "sid", "token": "token", "to": "to", "from": "from"}

    _options = salt.returners.get_returner_options(
        __virtualname__, ret, attrs, __salt__=__salt__, __opts__=__opts__
    )
    return _options


def returner(ret):
    """
    Return a response in an SMS message
    """
    _options = _get_options(ret)

    sid = _options.get("sid", None)
    token = _options.get("token", None)
    sender = _options.get("from", None)
    receiver = _options.get("to", None)

    if sid is None or token is None:
        log.error("Twilio sid/authentication token missing")
        return None

    if sender is None or receiver is None:
        log.error("Twilio to/from fields are missing")
        return None

    client = TwilioRestClient(sid, token)

    try:
        message = client.messages.create(
            body="Minion: {}\nCmd: {}\nSuccess: {}\n\nJid: {}".format(
                ret["id"], ret["fun"], ret["success"], ret["jid"]
            ),
            to=receiver,
            from_=sender,
        )
    except TwilioRestException as e:
        log.error("Twilio [https://www.twilio.com/docs/errors/%s]", e.code)
        return False

    return True
