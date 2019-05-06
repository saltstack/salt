#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Creates a waiter for Amazon Elastic File System.

::codeauthor:: florian.benscheidt@ogd.nl

:params str: Input waiter names to create_waiter.

    Example: create_waiter('EFSAvailable')
'''
from __future__ import absolute_import


try:
    import boto3
    import botocore.waiter
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    if not HAS_BOTO3:
        return (False, 'The boto.efs module cannot be loaded.')
    else:
        return True


MODELS = botocore.waiter.WaiterModel({
              "version": 2,
              "waiters": {
                "EfsAvailable": {
                  "delay": 30,
                  "operation": "DescribeFileSystems",
                  "maxAttempts": 60,
                  "acceptors": [
                    {
                      "expected": "available",
                      "matcher": "pathAll",
                      "state": "success",
                      "argument": "FileSystems[].LifeCycleState"
                    },
                    {
                      "expected": "deleting",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "FileSystems[].LifeCycleState"
                    },
                    {
                      "expected": "deleted",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "FileSystems[].LifeCycleState"
                    }
                  ]
                },
                "EfsDeleted": {
                  "delay": 30,
                  "operation": "DescribeFileSystems",
                  "maxAttempts": 60,
                  "acceptors": [
                    {
                      "expected": "deleted",
                      "matcher": "pathAll",
                      "state": "success",
                      "argument": "FileSystems[].LifeCycleState"
                    },
                    {
                      "expected": "updating",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "FileSystems[].LifeCycleState"
                    },
                    {
                      "expected": "creating",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "FileSystems[].LifeCycleState"
                    }
                  ]
                },
                "MountTargetDeleted": {
                  "delay": 30,
                  "operation": "DescribeMountTargets",
                  "maxAttempts": 90,
                  "acceptors": [
                    {
                      "expected": "deleted",
                      "matcher": "pathAll",
                      "state": "success",
                      "argument": "MountTargets[].LifeCycleState"
                    },
                    {
                      "expected": "updating",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "MountTargets[].LifeCycleState"
                    },
                    {
                      "expected": "creating",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "MountTargets[].LifeCycleState"
                    }
                  ]
                },
                "MountTargetAvailable": {
                  "delay": 30,
                  "operation": "DescribeMountTargets",
                  "maxAttempts": 90,
                  "acceptors": [
                    {
                      "expected": "available",
                      "matcher": "pathAll",
                      "state": "success",
                      "argument": "MountTargets[].LifeCycleState"
                    },
                    {
                      "expected": "deleting",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "MountTargets[].LifeCycleState"
                    },
                    {
                      "expected": "deleted",
                      "matcher": "pathAll",
                      "state": "failure",
                      "argument": "MountTargets[].LifeCycleState"
                    }
                  ]
                }
              }
            }
        )


# pylint: disable=E0712
def get_waiter(client, waiter, keyid=None, key=None, profile=None, region=None):
    try:
        return botocore.waiter.create_waiter_with_client(waiter, MODELS, client)
    except boto3.exceptions.botocore.exceptions as err:
        return 'An error has occured in your waiters.\nret: {}'.format(err)
