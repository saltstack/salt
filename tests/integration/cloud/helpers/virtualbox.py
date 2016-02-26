# -*- coding: utf-8 -*-
from __future__ import absolute_import
from unittest2 import skipIf
from integration.cloud.helpers import random_name
from salt.utils import virtualbox
import json
import logging
import os
import unittest
import integration

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = random_name()
PROVIDER_NAME = "virtualbox"
CONFIG_NAME = PROVIDER_NAME + "-config"
PROFILE_NAME = PROVIDER_NAME + "-test"
DEPLOY_PROFILE_NAME = PROVIDER_NAME + "-deploy-test"
DRIVER_NAME = "virtualbox"
BASE_BOX_NAME = "__temp_test_vm__"
BOOTABLE_BASE_BOX_NAME = "SaltMiniBuntuTest"

# Setup logging
log = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.INFO)
log.addHandler(log_handler)
log.setLevel(logging.INFO)
info = log.info


@skipIf(virtualbox.HAS_LIBS is False, 'virtualbox has to be installed')
class VirtualboxTestCase(unittest.TestCase):
    def setUp(self):
        self.vbox = virtualbox.vb_get_box()

    def assertMachineExists(self, name, msg=None):
        try:
            self.vbox.findMachine(name)
        except Exception as e:
            if msg:
                self.fail(msg)
            else:
                self.fail(e.message)

    def assertMachineDoesNotExist(self, name):
        self.assertRaisesRegexp(Exception, "Could not find a registered machine", self.vbox.findMachine, name)


@skipIf(virtualbox.HAS_LIBS is False, 'salt-cloud requires virtualbox to be installed')
class VirtualboxCloudTestCase(integration.ShellCase):
    def run_cloud(self, arg_str, catch_stderr=False, timeout=None):
        """
        Execute salt-cloud with json output and try to interpret it

        @return:
        @rtype: dict
        """
        config_path = os.path.join(
            integration.FILES,
            'conf'
        )
        arg_str = '--out=json -c {0} {1}'.format(config_path, arg_str)
        # arg_str = "{0} --log-level=error".format(arg_str)
        log.debug("running salt-cloud with %s", arg_str)
        output = self.run_script('salt-cloud', arg_str, catch_stderr, timeout=timeout)

        # Sometimes tuples are returned???
        if isinstance(output, tuple) and len(output) == 2:
            output = output[0]

        # Attempt to clean json output before fix of https://github.com/saltstack/salt/issues/27629
        valid_initial_chars = ['{', '[', '"']
        for line in output[:]:
            if len(line) == 0 or (line[0] not in valid_initial_chars):
                output.pop(0)
            else:
                break
        if len(output) is 0:
            return dict()
        else:
            return json.loads("".join(output))

    def run_cloud_function(self, function, kw_function_args=None, **kwargs):
        """
        A helper to call `salt-cloud -f function provider`

        @param function:
        @type function:
        @param kw_function_args: Keyword arguments for the argument string in the commandline
        @type dict:
        @param kwargs: For the `run_cloud` function
        @type kwargs:
        @return:
        @rtype: dict
        """
        args = []
        # Args converted in the form of key1='value1' ... keyN='valueN'
        if kw_function_args:
            args = [
                "{0}='{1}'".format(key, value)
                for key, value in kw_function_args.iteritems()
                ]

        output = self.run_cloud("-f {0} {1} {2}".format(function, CONFIG_NAME, " ".join(args)), **kwargs)
        return output.get(CONFIG_NAME, {}).get(PROVIDER_NAME, {})

    def run_cloud_action(self, action, instance_name, **kwargs):
        """
        A helper to call `salt-cloud -a action instance_name`

        @param action:
        @type action: str
        @param instance_name:
        @type instance_name: str
        @return:
        @rtype: dict
        """

        output = self.run_cloud("-a {0} {1} --assume-yes".format(action, instance_name), **kwargs)
        return output.get(CONFIG_NAME, {}).get(PROVIDER_NAME, {})
