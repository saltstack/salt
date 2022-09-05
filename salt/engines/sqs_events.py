"""
An engine that continuously reads messages from SQS and fires them as events.

Note that long polling is utilized to avoid excessive CPU usage.

.. versionadded:: 2015.8.0

:depends: boto

Configuration
=============

This engine can be run on the master or on a minion.

Example Config:

.. code-block:: yaml

    sqs.keyid: GKTADJGHEIQSXMKKRBJ08H
    sqs.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    sqs.message_format: json

Explicit sqs credentials are accepted but this engine can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More Information available at::

   http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

If IAM roles are not (or for ``boto`` version < 2.5.1) used you need to
specify them either in a pillar or in the config file of the master or
minion, as appropriate:

To deserialize the message from json:

.. code-block:: yaml

    sqs.message_format: json

It's also possible to specify key, keyid and region via a profile:

.. code-block:: yaml

    sqs.keyid: GKTADJGHEIQSXMKKRBJ08H
    sqs.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

A region may also be specified in the configuration:

.. code-block:: yaml

    sqs.region: us-east-1

If a region is not specified, the default is us-east-1.

It's also possible to specify key, keyid and region via a profile:

.. code-block:: yaml

    myprofile:
      keyid: GKTADJGHEIQSXMKKRBJ08H
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
      region: us-east-1

Additionally you can define cross account sqs:

.. code-block:: yaml

    engines:
      - sqs_events:
          queue: prod
          owner_acct_id: 111111111111

"""

import logging
import time

import salt.utils.event
import salt.utils.json

try:
    import boto.sqs

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    if not HAS_BOTO:
        return (
            False,
            "Cannot import engine sqs_events because the required boto module is"
            " missing",
        )
    else:
        return True


log = logging.getLogger(__name__)


def _get_sqs_conn(profile, region=None, key=None, keyid=None):
    """
    Get a boto connection to SQS.
    """
    if profile:
        if isinstance(profile, str):
            _profile = __opts__[profile]
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get("key", None)
        keyid = _profile.get("keyid", None)
        region = _profile.get("region", None)

    if not region:
        region = __opts__.get("sqs.region", "us-east-1")
    if not key:
        key = __opts__.get("sqs.key", None)
    if not keyid:
        keyid = __opts__.get("sqs.keyid", None)
    try:
        conn = boto.sqs.connect_to_region(
            region, aws_access_key_id=keyid, aws_secret_access_key=key
        )
    except boto.exception.NoAuthHandlerFound:
        log.error(
            "No authentication credentials found when attempting to"
            " make sqs_event engine connection to AWS."
        )
        return None
    return conn


def _process_queue(
    q,
    q_name,
    fire_master,
    tag="salt/engine/sqs",
    owner_acct_id=None,
    message_format=None,
):
    if not q:
        log.warning(
            "failure connecting to queue: %s, waiting 10 seconds.",
            ":".join([_f for _f in (str(owner_acct_id), q_name) if _f]),
        )
        time.sleep(10)
    else:
        msgs = q.get_messages(wait_time_seconds=20)
        for msg in msgs:
            if message_format == "json":
                fire_master(
                    tag=tag, data={"message": salt.utils.json.loads(msg.get_body())}
                )
            else:
                fire_master(tag=tag, data={"message": msg.get_body()})
            msg.delete()


def start(queue, profile=None, tag="salt/engine/sqs", owner_acct_id=None):
    """
    Listen to sqs and fire message on event bus
    """
    if __opts__.get("__role") == "master":
        fire_master = salt.utils.event.get_master_event(
            __opts__, __opts__["sock_dir"], listen=False
        ).fire_event
    else:
        fire_master = __salt__["event.send"]

    message_format = __opts__.get("sqs.message_format", None)

    sqs = _get_sqs_conn(profile)
    q = None
    while True:
        if not q:
            q = sqs.get_queue(queue, owner_acct_id=owner_acct_id)
            q.set_message_class(boto.sqs.message.RawMessage)

        _process_queue(
            q,
            queue,
            fire_master,
            tag=tag,
            owner_acct_id=owner_acct_id,
            message_format=message_format,
        )
