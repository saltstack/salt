# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
from copy import deepcopy
import pkg_resources
import os.path
import sys

# imprt salt paths
from tests.support.paths import TESTS_DIR

# import Python Third Party Libs
# pylint: disable=import-error
try:
    import boto
    boto.ENDPOINTS_PATH = os.path.join(TESTS_DIR, 'unit/files/endpoints.json')
    import boto.ec2.elb
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    from moto import mock_ec2_deprecated, mock_elb_deprecated
    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

    def mock_ec2_deprecated(self):
        '''
        if the mock_ec2_deprecated function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto_elb unit tests to use the @mock_ec2_deprecated decorator
        without a "NameError: name 'mock_ec2_deprecated' is not defined" error.
        '''
        def stub_function(self):
            pass
        return stub_function

    def mock_elb_deprecated(self):
        '''
        if the mock_elb_deprecated function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto_elb unit tests to use the @mock_elb_deprecated decorator
        without a "NameError: name 'mock_elb_deprecated' is not defined" error.
        '''
        def stub_function(self):
            pass
        return stub_function
# pylint: enable=import-error

# Import Salt Libs
import salt.config
from salt.ext import six
import salt.loader
import salt.modules.boto_elb as boto_elb
import salt.utils.versions

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

log = logging.getLogger(__name__)

region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key,
                   'profile': {}}
boto_conn_parameters = {'aws_access_key_id': access_key,
                        'aws_secret_access_key': secret_key}
instance_parameters = {'instance_type': 't1.micro'}
required_moto = '0.3.7'
required_moto_py3 = '1.0.1'


def _has_required_moto():
    '''
    Returns True or False depending on if ``moto`` is installed and at the correct version,
    depending on what version of Python is running these tests.
    '''
    if not HAS_MOTO:
        return False
    else:
        moto_version = salt.utils.versions.LooseVersion(pkg_resources.get_distribution('moto').version)
        if moto_version < salt.utils.versions.LooseVersion(required_moto):
            return False
        elif six.PY3 and moto_version < salt.utils.versions.LooseVersion(required_moto_py3):
            return False

    return True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_moto() is False, 'The moto module must be >= to {0} for '
                                       'PY2 or {1} for PY3.'.format(required_moto, required_moto_py3))
class BotoElbTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.boto_elb module
    '''

    def setup_loader_modules(self):
        opts = salt.config.DEFAULT_MASTER_OPTS.copy()
        utils = salt.loader.utils(
            opts,
            whitelist=['boto', 'args', 'systemd', 'path', 'platform'])
        funcs = salt.loader.minion_mods(opts, utils=utils)
        return {
            boto_elb: {
                '__opts__': opts,
                '__utils__': utils,
                '__salt__': funcs
            }
        }

    def setUp(self):
        TestCase.setUp(self)
        # __virtual__ must be caller in order for _get_conn to be injected
        boto_elb.__virtual__()

    @mock_ec2_deprecated
    @mock_elb_deprecated
    @skipIf(sys.version_info > (3, 6), 'Disabled for 3.7+ pending https://github.com/spulec/moto/issues/1706.')
    def test_register_instances_valid_id_result_true(self):
        '''
        tests that given a valid instance id and valid ELB that
        register_instances returns True.
        '''
        conn_ec2 = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        conn_elb = boto.ec2.elb.connect_to_region(region,
                                                  **boto_conn_parameters)
        zones = [zone.name for zone in conn_ec2.get_all_zones()]
        elb_name = 'TestRegisterInstancesValidIdResult'
        conn_elb.create_load_balancer(elb_name, zones, [(80, 80, 'http')])
        reservations = conn_ec2.run_instances('ami-08389d60')
        register_result = boto_elb.register_instances(elb_name,
                                                      reservations.instances[0].id,
                                                      **conn_parameters)
        self.assertEqual(True, register_result)

    @mock_ec2_deprecated
    @mock_elb_deprecated
    @skipIf(sys.version_info > (3, 6), 'Disabled for 3.7+ pending https://github.com/spulec/moto/issues/1706.')
    def test_register_instances_valid_id_string(self):
        '''
        tests that given a string containing a instance id and valid ELB that
        register_instances adds the given instance to an ELB
        '''
        conn_ec2 = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        conn_elb = boto.ec2.elb.connect_to_region(region,
                                                  **boto_conn_parameters)
        zones = [zone.name for zone in conn_ec2.get_all_zones()]
        elb_name = 'TestRegisterInstancesValidIdResult'
        conn_elb.create_load_balancer(elb_name, zones, [(80, 80, 'http')])
        reservations = conn_ec2.run_instances('ami-08389d60')
        boto_elb.register_instances(elb_name, reservations.instances[0].id,
                                    **conn_parameters)
        load_balancer_refreshed = conn_elb.get_all_load_balancers(elb_name)[0]
        registered_instance_ids = [instance.id for instance in
                                   load_balancer_refreshed.instances]

        log.debug(load_balancer_refreshed.instances)
        self.assertEqual([reservations.instances[0].id], registered_instance_ids)

    @mock_ec2_deprecated
    @mock_elb_deprecated
    @skipIf(sys.version_info > (3, 6), 'Disabled for 3.7+ pending https://github.com/spulec/moto/issues/1706.')
    def test_deregister_instances_valid_id_result_true(self):
        '''
        tests that given an valid id the boto_elb deregister_instances method
        removes exactly one of a number of ELB registered instances
        '''
        conn_ec2 = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        conn_elb = boto.ec2.elb.connect_to_region(region,
                                                  **boto_conn_parameters)
        zones = [zone.name for zone in conn_ec2.get_all_zones()]
        elb_name = 'TestDeregisterInstancesValidIdResult'
        load_balancer = conn_elb.create_load_balancer(elb_name, zones,
                                                      [(80, 80, 'http')])
        reservations = conn_ec2.run_instances('ami-08389d60')
        load_balancer.register_instances(reservations.instances[0].id)
        deregister_result = boto_elb.deregister_instances(elb_name,
                                                          reservations.instances[0].id,
                                                          **conn_parameters)
        self.assertEqual(True, deregister_result)

    @mock_ec2_deprecated
    @mock_elb_deprecated
    @skipIf(sys.version_info > (3, 6), 'Disabled for 3.7+ pending https://github.com/spulec/moto/issues/1706.')
    def test_deregister_instances_valid_id_string(self):
        '''
        tests that given an valid id the boto_elb deregister_instances method
        removes exactly one of a number of ELB registered instances
        '''
        conn_ec2 = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        conn_elb = boto.ec2.elb.connect_to_region(region,
                                                  **boto_conn_parameters)
        zones = [zone.name for zone in conn_ec2.get_all_zones()]
        elb_name = 'TestDeregisterInstancesValidIdString'
        load_balancer = conn_elb.create_load_balancer(elb_name, zones,
                                                      [(80, 80, 'http')])
        reservations = conn_ec2.run_instances('ami-08389d60', min_count=2)
        all_instance_ids = [instance.id for instance in reservations.instances]
        load_balancer.register_instances(all_instance_ids)
        boto_elb.deregister_instances(elb_name, reservations.instances[0].id,
                                      **conn_parameters)
        load_balancer_refreshed = conn_elb.get_all_load_balancers(elb_name)[0]
        expected_instances = deepcopy(all_instance_ids)
        expected_instances.remove(reservations.instances[0].id)
        actual_instances = [instance.id for instance in
                            load_balancer_refreshed.instances]
        self.assertEqual(actual_instances, expected_instances)

    @mock_ec2_deprecated
    @mock_elb_deprecated
    @skipIf(sys.version_info > (3, 6), 'Disabled for 3.7+ pending https://github.com/spulec/moto/issues/1706.')
    def test_deregister_instances_valid_id_list(self):
        '''
        tests that given an valid ids in the form of a list that the boto_elb
        deregister_instances all members of the given list
        '''
        conn_ec2 = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        conn_elb = boto.ec2.elb.connect_to_region(region,
                                                  **boto_conn_parameters)
        zones = [zone.name for zone in conn_ec2.get_all_zones()]
        elb_name = 'TestDeregisterInstancesValidIdList'
        load_balancer = conn_elb.create_load_balancer(elb_name, zones,
                                                      [(80, 80, 'http')])
        reservations = conn_ec2.run_instances('ami-08389d60', min_count=3)
        all_instance_ids = [instance.id for instance in reservations.instances]
        load_balancer.register_instances(all_instance_ids)
        # reservations.instances[:-1] refers to all instances except list
        # instance
        deregister_instances = [instance.id for instance in
                                reservations.instances[:-1]]
        expected_instances = [reservations.instances[-1].id]
        boto_elb.deregister_instances(elb_name, deregister_instances,
                                      **conn_parameters)
        load_balancer_refreshed = conn_elb.get_all_load_balancers(elb_name)[0]
        actual_instances = [instance.id for instance in
                            load_balancer_refreshed.instances]
        self.assertEqual(actual_instances, expected_instances)
