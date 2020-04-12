# -*- coding: utf-8 -*-
"""
    tests.unit.cloud
    ~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import, print_function, unicode_literals

import salt.cloud
from tests.support.unit import TestCase


class CloudTest(TestCase):
    def test_vm_config_merger(self):
        """
        Validate the vm's config is generated correctly.

        https://github.com/saltstack/salt/issues/49226
        """
        main = {
            "minion": {"master": "172.31.39.213"},
            "log_file": "var/log/salt/cloud.log",
            "pool_size": 10,
        }
        provider = {
            "private_key": "dwoz.pem",
            "grains": {"foo1": "bar", "foo2": "bang"},
            "availability_zone": "us-west-2b",
            "driver": "ec2",
            "ssh_interface": "private_ips",
            "ssh_username": "admin",
            "location": "us-west-2",
        }
        profile = {
            "profile": "default",
            "grains": {"meh2": "bar", "meh1": "foo"},
            "provider": "ec2-default:ec2",
            "ssh_username": "admin",
            "image": "ami-0a1fbca0e5b419fd1",
            "size": "t2.micro",
        }
        vm = salt.cloud.Cloud.vm_config("test_vm", main, provider, profile, {})
        self.assertEqual(
            {
                "minion": {"master": "172.31.39.213"},
                "log_file": "var/log/salt/cloud.log",
                "pool_size": 10,
                "private_key": "dwoz.pem",
                "grains": {
                    "foo1": "bar",
                    "foo2": "bang",
                    "meh2": "bar",
                    "meh1": "foo",
                },
                "availability_zone": "us-west-2b",
                "driver": "ec2",
                "ssh_interface": "private_ips",
                "ssh_username": "admin",
                "location": "us-west-2",
                "profile": "default",
                "provider": "ec2-default:ec2",
                "image": "ami-0a1fbca0e5b419fd1",
                "size": "t2.micro",
                "name": "test_vm",
            },
            vm,
        )
