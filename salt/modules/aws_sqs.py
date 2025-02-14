"""
Support for the Amazon Simple Queue Service.
"""

import logging

import salt.utils.json
import salt.utils.path

log = logging.getLogger(__name__)

_OUTPUT = "--output json"


def __virtual__():
    if salt.utils.path.which("aws"):
        # awscli is installed, load the module
        return True
    return (False, "The module aws_sqs could not be loaded: aws command not found")


def _region(region):
    """
    Return the region argument.
    """
    return f" --region {region}"


def _run_aws(cmd, region, opts, user, **kwargs):
    """
    Runs the given command against AWS.
    cmd
        Command to run
    region
        Region to execute cmd in
    opts
        Pass in from salt
    user
        Pass in from salt
    kwargs
        Key-value arguments to pass to the command
    """
    # These args need a specific key value that aren't
    # valid python parameter keys
    receipthandle = kwargs.pop("receipthandle", None)
    if receipthandle:
        kwargs["receipt-handle"] = receipthandle
    num = kwargs.pop("num", None)
    if num:
        kwargs["max-number-of-messages"] = num

    _formatted_args = [f'--{k} "{v}"' for k, v in kwargs.items()]

    cmd = "aws sqs {cmd} {args} {region} {out}".format(
        cmd=cmd, args=" ".join(_formatted_args), region=_region(region), out=_OUTPUT
    )

    rtn = __salt__["cmd.run"](cmd, runas=user, python_shell=False)

    return salt.utils.json.loads(rtn) if rtn else ""


def receive_message(queue, region, num=1, opts=None, user=None):
    """
    Receive one or more messages from a queue in a region

    queue
        The name of the queue to receive messages from

    region
        Region where SQS queues exists

    num : 1
        The max number of messages to receive

    opts : None
        Any additional options to add to the command line

    user : None
        Run as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' aws_sqs.receive_message <sqs queue> <region>
        salt '*' aws_sqs.receive_message <sqs queue> <region> num=10

    .. versionadded:: 2014.7.0

    """
    ret = {
        "Messages": None,
    }
    queues = list_queues(region, opts, user)
    url_map = _parse_queue_list(queues)
    if queue not in url_map:
        log.info('"%s" queue does not exist.', queue)
        return ret

    out = _run_aws("receive-message", region, opts, user, queue=url_map[queue], num=num)
    ret["Messages"] = out["Messages"]
    return ret


def delete_message(queue, region, receipthandle, opts=None, user=None):
    """
    Delete one or more messages from a queue in a region

    queue
        The name of the queue to delete messages from

    region
        Region where SQS queues exists

    receipthandle
        The ReceiptHandle of the message to delete. The ReceiptHandle
        is obtained in the return from receive_message

    opts : None
        Any additional options to add to the command line

    user : None
        Run as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' aws_sqs.delete_message <sqs queue> <region> receipthandle='<sqs ReceiptHandle>'

    .. versionadded:: 2014.7.0

    """
    queues = list_queues(region, opts, user)
    url_map = _parse_queue_list(queues)
    if queue not in url_map:
        log.info('"%s" queue does not exist.', queue)
        return False

    out = _run_aws(
        "delete-message",
        region,
        opts,
        user,
        receipthandle=receipthandle,
        queue=url_map[queue],
    )
    return True


def list_queues(region, opts=None, user=None):
    """
    List the queues in the selected region.

    region
        Region to list SQS queues for

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' aws_sqs.list_queues <region>

    """
    out = _run_aws("list-queues", region, opts, user)

    ret = {
        "retcode": 0,
        "stdout": out["QueueUrls"],
    }
    return ret


def create_queue(name, region, opts=None, user=None):
    """
    Creates a queue with the correct name.

    name
        Name of the SQS queue to create

    region
        Region to create the SQS queue in

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' aws_sqs.create_queue <sqs queue> <region>

    """

    create = {"queue-name": name}
    out = _run_aws("create-queue", region=region, opts=opts, user=user, **create)

    ret = {
        "retcode": 0,
        "stdout": out["QueueUrl"],
        "stderr": "",
    }
    return ret


def delete_queue(name, region, opts=None, user=None):
    """
    Deletes a queue in the region.

    name
        Name of the SQS queue to deletes
    region
        Name of the region to delete the queue from

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' aws_sqs.delete_queue <sqs queue> <region>

    """
    queues = list_queues(region, opts, user)
    url_map = _parse_queue_list(queues)

    log.debug("map %s", url_map)
    if name in url_map:
        delete = {"queue-url": url_map[name]}

        rtn = _run_aws("delete-queue", region=region, opts=opts, user=user, **delete)
        success = True
        err = ""
        out = f"{name} deleted"

    else:
        out = ""
        err = "Delete failed"
        success = False

    ret = {
        "retcode": 0 if success else 1,
        "stdout": out,
        "stderr": err,
    }
    return ret


def queue_exists(name, region, opts=None, user=None):
    """
    Returns True or False on whether the queue exists in the region

    name
        Name of the SQS queue to search for

    region
        Name of the region to search for the queue in

    opts : None
        Any additional options to add to the command line

    user : None
        Run hg as a user other than what the minion runs as

    CLI Example:

    .. code-block:: bash

        salt '*' aws_sqs.queue_exists <sqs queue> <region>

    """
    output = list_queues(region, opts, user)

    return name in _parse_queue_list(output)


def _parse_queue_list(list_output):
    """
    Parse the queue to get a dict of name -> URL
    """
    queues = {q.split("/")[-1]: q for q in list_output["stdout"]}
    return queues
