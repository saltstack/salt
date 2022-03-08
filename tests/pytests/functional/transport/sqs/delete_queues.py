import logging
from multiprocessing import Pool

import boto3
import pytest

log = logging.getLogger(__name__)
pytestmark = [
    # These are slow because they create a virtualenv and install salt in it
    # pytest.mark.slow_test,
]


def _delete_single_queue_func(queue_url):
    if not queue_url:
        raise ValueError("queue url must be set")

    # FIXME: we should really use a single instance of sqs client,
    # but there are some issues with threading / multi-processing and client reuse
    sqs_client = boto3.client("sqs", region_name="us-east-2")  # FIXME: hard-coded region
    ret = sqs_client.delete_queue(QueueUrl=queue_url)
    print("Deleted queue: " + str(ret))


def test_delete_queues():
    sqs_client = boto3.client("sqs", region_name="us-east-2") # FIXME: hard-coded region
    queues = sqs_client.list_queues(QueueNamePrefix="salt", MaxResults=1000)
    next_token = queues.get("NextToken")
    with Pool(processes=16) as pool:
        if queues.get("QueueUrls"):
            while len(queues["QueueUrls"]) > 0:
                pool.map(_delete_single_queue_func, queues["QueueUrls"])
                queues = (
                    sqs_client.list_queues(
                        QueueNamePrefix="salt", MaxResults=1000, NextToken=next_token
                    )
                    if next_token
                    else sqs_client.list_queues(QueueNamePrefix="salt", MaxResults=1000)
                )
                next_token = queues.get("NextToken")
