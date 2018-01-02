# -*- coding: utf-8 -*-
'''
unittests for terraform roster
'''
from __future__ import absolute_import
import os.path
from salt.roster import terraform

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TerraformTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.roster.terraform
    '''
    def setup_loader_modules(self):
        return {terraform: {}}

    def test_default_output(self):
        '''
        Test the output of a fixture tfstate file wich contains libvirt
        and AWS resources.
        '''
        tfstate = os.path.join(os.path.dirname(__file__), 'terraform.data', 'terraform.tfstate')
        pki_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'terraform.data'))

        with patch.dict(terraform.__opts__, {'roster_file': tfstate, 'pki_dir': pki_dir}):
            expected_result = {
                'minsles12sp1': {
                    'host': '192.168.127.222',
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa')},
                'package-mirror': {
                    'host': '192.168.127.157',
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa')},
                'moio-sumaform-package-mirror': {
                    'host': 'ec2-54-209-95-95.compute-1.amazonaws.com',
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa')},
                'suma3pg': {
                    'host': '192.168.127.187',
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa')}
            }

            ret = terraform.targets('*')
            self.assertDictEqual(expected_result, ret)

    def test_default_matching(self):
        '''
        Test the output of a fixture tfstate file wich contains libvirt
        and AWS resources using matching
        '''
        tfstate = os.path.join(os.path.dirname(__file__), 'terraform.data', 'terraform.tfstate')
        pki_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'terraform.data'))

        with patch.dict(terraform.__opts__, {'roster_file': tfstate, 'pki_dir': pki_dir}):
            expected_result = {
                'package-mirror': {
                    'host': '192.168.127.157',
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa')},
                'moio-sumaform-package-mirror': {
                    'host': 'ec2-54-209-95-95.compute-1.amazonaws.com',
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa')}
            }

            ret = terraform.targets('*mirror*')
            self.assertDictEqual(expected_result, ret)

    def test_override(self):
        '''
        Test that values specified as output variables override the defaults
        '''
        tfstate = os.path.join(os.path.dirname(__file__), 'terraform.data', 'terraform.override.tfstate')
        pki_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'terraform.data'))

        with patch.dict(terraform.__opts__, {'roster_file': tfstate, 'pki_dir': pki_dir}):
            # timeout is overriden for all resources, timeout only for domain-0
            expected_result = {
                'domain-0': {
                    'host': u'192.168.122.250',
                    'port': 44,
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa'),
                    'timeout': 60},
                'domain-1': {
                    'host': u'192.168.122.160',
                    'priv': os.path.join(pki_dir, 'ssh/salt-ssh.rsa'),
                    'timeout': 60}}

            ret = terraform.targets('*')
            self.assertDictEqual(expected_result, ret)
