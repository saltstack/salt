# -*- coding: utf-8 -*-
"""
Manage SQS Queues

Create and destroy SQS queues. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses the awscli tool provided by Amazon. This can be downloaded
from pip. Also check the documentation for awscli for configuration
information.

.. code-block:: yaml

    myqueue:
        aws_sqs.exists:
            - region: eu-west-1
"""
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if aws is available.
    """
    if __salt__["cmd.has_exec"]("aws"):
        return "aws_sqs"
    return False


def exists(name, region, user=None, opts=False):
    """
    Ensure the SQS queue exists.

    name
        Name of the SQS queue.

    region
        Region to create the queue

    user
        Name of the user performing the SQS operations

    opts
        Include additional arguments and options to the aws command line
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    does_exist = __salt__["aws_sqs.queue_exists"](name, region, opts, user)

    if not does_exist:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "AWS SQS queue {0} is set to be created".format(name)
            return ret
        created = __salt__["aws_sqs.create_queue"](name, region, opts, user)
        if created["retcode"] == 0:
            ret["changes"]["new"] = created["stdout"]
        else:
            ret["result"] = False
            ret["comment"] = created["stderr"]

    else:
        ret["comment"] = "{0} exists in {1}".format(name, region)

    return ret


def absent(name, region, user=None, opts=False):
    """
    Remove the named SQS queue if it exists.

    name
        Name of the SQS queue.

    region
        Region to remove the queue from

    user
        Name of the user performing the SQS operations

    opts
        Include additional arguments and options to the aws command line
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    does_exist = __salt__["aws_sqs.queue_exists"](name, region, opts, user)

    if does_exist:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "AWS SQS queue {0} is set to be removed".format(name)
            return ret
        removed = __salt__["aws_sqs.delete_queue"](name, region, opts, user)
        if removed["retcode"] == 0:
            ret["changes"]["removed"] = removed["stdout"]
        else:
            ret["result"] = False
            ret["comment"] = removed["stderr"]
    else:
        ret["comment"] = "{0} does not exist in {1}".format(name, region)

    return ret
