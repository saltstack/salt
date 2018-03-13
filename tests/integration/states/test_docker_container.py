# -*- coding: utf-8 -*-
'''
Integration tests for the docker_container states
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import functools
import logging
import os
import subprocess
import tempfile

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase
from tests.support.docker import with_network, random_name
from tests.support.paths import FILES, TMP
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Libs
import salt.utils.files
import salt.utils.network
import salt.utils.path
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

IPV6_ENABLED = bool(salt.utils.network.ip_addrs6(include_loopback=True))


def with_temp_dir(func):
    '''
    Generate a temp directory for a test
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        tempdir = tempfile.mkdtemp(dir=TMP)
        try:
            return func(self, tempdir, *args, **kwargs)
        finally:
            try:
                salt.utils.files.rm_rf(tempdir)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise
    return wrapper


def container_name(func):
    '''
    Generate a randomized name for a container and clean it up afterward
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        name = random_name(prefix='salt_test_')
        try:
            return func(self, name, *args, **kwargs)
        finally:
            try:
                self.run_function('docker.rm', [name], force=True)
            except CommandExecutionError as exc:
                if 'No such container' not in exc.__str__():
                    raise
    return wrapper


@destructiveTest
@skipIf(not salt.utils.path.which('busybox'), 'Busybox not installed')
@skipIf(not salt.utils.path.which('dockerd'), 'Docker not installed')
class DockerContainerTestCase(ModuleCase, SaltReturnAssertsMixin):
    '''
    Test docker_container states
    '''
    @classmethod
    def setUpClass(cls):
        '''
        '''
        # Create temp dir
        cls.image_build_rootdir = tempfile.mkdtemp(dir=TMP)
        # Generate image name
        cls.image = random_name(prefix='salt_busybox_')

        script_path = \
            os.path.join(FILES, 'file/base/mkimage-busybox-static')
        cmd = [script_path, cls.image_build_rootdir, cls.image]
        log.debug('Running \'%s\' to build busybox image', ' '.join(cmd))
        process = subprocess.Popen(
            cmd,
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        output = process.communicate()[0]
        log.debug('Output from mkimge-busybox-static:\n%s', output)

        if process.returncode != 0:
            raise Exception('Failed to build image')

        try:
            salt.utils.files.rm_rf(cls.image_build_rootdir)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

    @classmethod
    def tearDownClass(cls):
        cmd = ['docker', 'rmi', '--force', cls.image]
        log.debug('Running \'%s\' to destroy busybox image', ' '.join(cmd))
        process = subprocess.Popen(
            cmd,
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        output = process.communicate()[0]
        log.debug('Output from %s:\n%s', ' '.join(cmd), output)

        if process.returncode != 0:
            raise Exception('Failed to destroy image')

    def run_state(self, function, **kwargs):
        ret = super(DockerContainerTestCase, self).run_state(function, **kwargs)
        log.debug('ret = %s', ret)
        return ret

    @with_temp_dir
    @container_name
    def test_running_with_no_predefined_volume(self, name, bind_dir_host):
        '''
        This tests that a container created using the docker_container.running
        state, with binds defined, will also create the corresponding volumes
        if they aren't pre-defined in the image.
        '''
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            binds=bind_dir_host + ':/foo',
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Now check to ensure that the container has volumes to match the
        # binds that we used when creating it.
        ret = self.run_function('docker.inspect_container', [name])
        self.assertTrue('/foo' in ret['Config']['Volumes'])

    @container_name
    def test_running_with_no_predefined_ports(self, name):
        '''
        This tests that a container created using the docker_container.running
        state, with port_bindings defined, will also configure the
        corresponding ports if they aren't pre-defined in the image.
        '''
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            port_bindings='14505-14506:24505-24506,2123:2123/udp,8080',
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Now check to ensure that the container has ports to match the
        # port_bindings that we used when creating it.
        expected_ports = (4505, 4506, 8080, '2123/udp')
        ret = self.run_function('docker.inspect_container', [name])
        self.assertTrue(x in ret['NetworkSettings']['Ports']
                        for x in expected_ports)

    @container_name
    def test_running_updated_image_id(self, name):
        '''
        This tests the case of an image being changed after the container is
        created. The next time the state is run, the container should be
        replaced because the image ID is now different.
        '''
        # Create and start a container
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Get the container's info
        c_info = self.run_function('docker.inspect_container', [name])
        c_name, c_id = (c_info[x] for x in ('Name', 'Id'))
        # Alter the filesystem inside the container
        self.assertEqual(
            self.run_function('docker.retcode', [name, 'touch /.salttest']),
            0
        )
        # Commit the changes and overwrite the test class' image
        self.run_function('docker.commit', [c_id, self.image])
        # Re-run the state
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check to make sure that the container was replaced
        self.assertTrue('container_id' in ret['changes'])
        # Check to make sure that the image is in the changes dict, since
        # it should have changed
        self.assertTrue('image' in ret['changes'])
        # Check that the comment in the state return states that
        # container's image has changed
        self.assertTrue('Container has a new image' in ret['comment'])

    @container_name
    def test_running_start_false_without_replace(self, name):
        '''
        Test that we do not start a container which is stopped, when it is not
        being replaced.
        '''
        # Create a container
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Stop the container
        self.run_function('docker.stop', [name], force=True)
        # Re-run the state with start=False
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            start=False,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check to make sure that the container was not replaced
        self.assertTrue('container_id' not in ret['changes'])
        # Check to make sure that the state is not the changes dict, since
        # it should not have changed
        self.assertTrue('state' not in ret['changes'])

    @container_name
    def test_running_start_false_with_replace(self, name):
        '''
        Test that we do start a container which was previously stopped, even
        though start=False, because the container was replaced.
        '''
        # Create a container
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Stop the container
        self.run_function('docker.stop', [name], force=True)
        # Re-run the state with start=False but also change the command to
        # trigger the container being replaced.
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            command='sleep 600',
            start=False,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check to make sure that the container was not replaced
        self.assertTrue('container_id' in ret['changes'])
        # Check to make sure that the state is not the changes dict, since
        # it should not have changed
        self.assertTrue('state' not in ret['changes'])

    @container_name
    def test_running_start_true(self, name):
        '''
        This tests that we *do* start a container that is stopped, when the
        "start" argument is set to True.
        '''
        # Create a container
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Stop the container
        self.run_function('docker.stop', [name], force=True)
        # Re-run the state with start=True
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            start=True,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check to make sure that the container was not replaced
        self.assertTrue('container_id' not in ret['changes'])
        # Check to make sure that the state is in the changes dict, since
        # it should have changed
        self.assertTrue('state' in ret['changes'])
        # Check that the comment in the state return states that
        # container's state has changed
        self.assertTrue(
            "State changed from 'stopped' to 'running'" in ret['comment'])

    @container_name
    def test_running_with_invalid_input(self, name):
        '''
        This tests that the input tranlation code identifies invalid input and
        includes information about that invalid argument in the state return.
        '''
        # Try to create a container with invalid input
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            ulimits='nofile:2048',
            shutdown_timeout=1,
        )
        self.assertSaltFalseReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check to make sure that the container was not created
        self.assertTrue('container_id' not in ret['changes'])
        # Check that the error message about the invalid argument is
        # included in the comment for the state
        self.assertTrue(
            'Ulimit definition \'nofile:2048\' is not in the format '
            'type=soft_limit[:hard_limit]' in ret['comment']
        )

    @container_name
    def test_running_with_argument_collision(self, name):
        '''
        this tests that the input tranlation code identifies an argument
        collision (API args and their aliases being simultaneously used) and
        includes information about them in the state return.
        '''
        # try to create a container with invalid input
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            ulimits='nofile=2048',
            ulimit='nofile=1024:2048',
            shutdown_timeout=1,
        )
        self.assertSaltFalseReturn(ret)
        # Ciscard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check to make sure that the container was not created
        self.assertTrue('container_id' not in ret['changes'])
        # Check that the error message about the collision is included in
        # the comment for the state
        self.assertTrue(
            '\'ulimit\' is an alias for \'ulimits\'' in ret['comment'])

    @container_name
    def test_running_with_ignore_collisions(self, name):
        '''
        This tests that the input tranlation code identifies an argument
        collision (API args and their aliases being simultaneously used)
        includes information about them in the state return.
        '''
        # try to create a container with invalid input
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            ignore_collisions=True,
            ulimits='nofile=2048',
            ulimit='nofile=1024:2048',
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check to make sure that the container was created
        self.assertTrue('container_id' in ret['changes'])
        # Check that the value from the API argument was one that was used
        # to create the container
        c_info = self.run_function('docker.inspect_container', [name])
        actual = c_info['HostConfig']['Ulimits']
        expected = [{'Name': 'nofile', 'Soft': 2048, 'Hard': 2048}]
        self.assertEqual(actual, expected)

    @container_name
    def test_running_with_removed_argument(self, name):
        '''
        This tests that removing an argument from a created container will
        be detected and result in the container being replaced.

        It also tests that we revert back to the value from the image. This
        way, when the "command" argument is removed, we confirm that we are
        reverting back to the image's command.
        '''
        # Create the container
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            command='sleep 600',
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Run the state again with the "command" argument removed
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Now check to ensure that the changes include the command
        # reverting back to the image's command.
        image_info = self.run_function('docker.inspect_image', [self.image])
        self.assertEqual(
            ret['changes']['container']['Config']['Cmd']['new'],
            image_info['Config']['Cmd']
        )

    @container_name
    def test_running_with_port_bindings(self, name):
        '''
        This tests that the ports which are being bound are also exposed, even
        when not explicitly configured. This test will create a container with
        only some of the ports exposed, including some which aren't even bound.
        The resulting containers exposed ports should contain all of the ports
        defined in the "ports" argument, as well as each of the ports which are
        being bound.
        '''
        # Create the container
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            command='sleep 600',
            shutdown_timeout=1,
            port_bindings=[1234, '1235-1236', '2234/udp', '2235-2236/udp'],
            ports=[1235, '2235/udp', 9999],
        )
        self.assertSaltTrueReturn(ret)

        # Check the created container's port bindings and exposed ports. The
        # port bindings should only contain the ports defined in the
        # port_bindings argument, while the exposed ports should also contain
        # the extra port (9999/tcp) which was included in the ports argument.
        cinfo = self.run_function('docker.inspect_container', [name])
        ports = ['1234/tcp', '1235/tcp', '1236/tcp',
                 '2234/udp', '2235/udp', '2236/udp']
        self.assertEqual(
            sorted(cinfo['HostConfig']['PortBindings']),
            ports
        )
        self.assertEqual(
            sorted(cinfo['Config']['ExposedPorts']),
            ports + ['9999/tcp']
        )

    @container_name
    def test_absent_with_stopped_container(self, name):
        '''
        This tests the docker_container.absent state on a stopped container
        '''
        # Create the container
        self.run_function('docker.create', [self.image], name=name)
        # Remove the container
        ret = self.run_state(
            'docker_container.absent',
            name=name,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check that we have a removed container ID in the changes dict
        self.assertTrue('removed' in ret['changes'])

        # Run the state again to confirm it changes nothing
        ret = self.run_state(
            'docker_container.absent',
            name=name,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Nothing should have changed
        self.assertEqual(ret['changes'], {})
        # Ensure that the comment field says the container does not exist
        self.assertEqual(
            ret['comment'],
            'Container \'{0}\' does not exist'.format(name)
        )

    @container_name
    def test_absent_with_running_container(self, name):
        '''
        This tests the docker_container.absent state and
        '''
        # Create the container
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            command='sleep 600',
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)

        # Try to remove the container. This should fail because force=True
        # is needed to remove a container that is running.
        ret = self.run_state(
            'docker_container.absent',
            name=name,
            shutdown_timeout=1,
        )
        self.assertSaltFalseReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Nothing should have changed
        self.assertEqual(ret['changes'], {})
        # Ensure that the comment states that force=True is required
        self.assertEqual(
            ret['comment'],
            'Container is running, set force to True to forcibly remove it'
        )

        # Try again with force=True. This should succeed.
        ret = self.run_state('docker_container.absent',
            name=name,
            force=True,
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        # Discard the outer dict with the state compiler data to make below
        # asserts easier to read/write
        ret = ret[next(iter(ret))]
        # Check that we have a removed container ID in the changes dict
        self.assertTrue('removed' in ret['changes'])
        # The comment should mention that the container was removed
        self.assertEqual(
            ret['comment'],
            'Forcibly removed container \'{0}\''.format(name)
        )

    @container_name
    def test_env_with_running_container(self, name):
        '''
        docker_container.running environnment part. Testing issue 39838.
        '''
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            env='VAR1=value1,VAR2=value2,VAR3=value3',
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_function('docker.inspect_container', [name])
        self.assertTrue('VAR1=value1' in ret['Config']['Env'])
        self.assertTrue('VAR2=value2' in ret['Config']['Env'])
        self.assertTrue('VAR3=value3' in ret['Config']['Env'])
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image,
            env='VAR1=value1,VAR2=value2',
            shutdown_timeout=1,
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_function('docker.inspect_container', [name])
        self.assertTrue('VAR1=value1' in ret['Config']['Env'])
        self.assertTrue('VAR2=value2' in ret['Config']['Env'])
        self.assertTrue('VAR3=value3' not in ret['Config']['Env'])

    def _test_running(self, container_name, *nets):
        '''
        DRY function for testing static IPs
        '''
        networks = []
        for net in nets:
            net_def = {
                net.name: [
                    {net.ip_arg: net[0]}
                ]
            }
            networks.append(net_def)

        kwargs = {
            'name': container_name,
            'image': self.image,
            'networks': networks,
            'shutdown_timeout': 1,
        }
        # Create a container
        ret = self.run_state('docker_container.running', **kwargs)
        self.assertSaltTrueReturn(ret)

        inspect_result = self.run_function('docker.inspect_container',
                                           [container_name])
        connected_networks = inspect_result['NetworkSettings']['Networks']

        # Check that the correct IP was set
        try:
            for net in nets:
                self.assertEqual(
                    connected_networks[net.name]['IPAMConfig'][net.arg_map(net.ip_arg)],
                    net[0]
                )
        except KeyError:
            # Fail with a meaningful error
            msg = (
                'Container does not have the expected network config for '
                'network {0}'.format(net.name)
            )
            log.error(msg)
            log.error('Connected networks: %s', connected_networks)
            self.fail('{0}. See log for more information.'.format(msg))

        # Check that container continued running and didn't immediately exit
        self.assertTrue(inspect_result['State']['Running'])

        # Update the SLS configuration to use the second random IP so that we
        # can test updating a container's network configuration without
        # replacing the container.
        for idx, net in enumerate(nets):
            kwargs['networks'][idx][net.name][0][net.ip_arg] = net[1]
        ret = self.run_state('docker_container.running', **kwargs)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        expected = {'container': {'Networks': {}}}
        for net in nets:
            expected['container']['Networks'][net.name] = {
                'IPAMConfig': {
                    'old': {net.arg_map(net.ip_arg): net[0]},
                    'new': {net.arg_map(net.ip_arg): net[1]},
                }
            }
        self.assertEqual(ret['changes'], expected)

        expected = [
            "Container '{0}' is already configured as specified.".format(
                container_name
            )
        ]
        expected.extend([
            "Reconnected to network '{0}' with updated configuration.".format(
                x.name
            )
            for x in sorted(nets, key=lambda y: y.name)
        ])
        expected = ' '.join(expected)
        self.assertEqual(ret['comment'], expected)

        # Update the SLS configuration to remove the last network
        log.critical('networks = %s', kwargs['networks'])
        kwargs['networks'].pop(-1)
        ret = self.run_state('docker_container.running', **kwargs)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        expected = {
            'container': {
                'Networks': {
                    nets[-1].name: {
                        'IPAMConfig': {
                            'old': {
                                nets[-1].arg_map(nets[-1].ip_arg): nets[-1][1]
                            },
                            'new': None,
                        }
                    }
                }
            }
        }
        self.assertEqual(ret['changes'], expected)

        expected = (
            "Container '{0}' is already configured as specified. Disconnected "
            "from network '{1}'.".format(container_name, nets[-1].name)
        )
        self.assertEqual(ret['comment'], expected)

        # Update the SLS configuration to add back the last network, only use
        # an automatic IP instead of static IP.
        kwargs['networks'].append(nets[-1].name)
        ret = self.run_state('docker_container.running', **kwargs)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        # Get the automatic IP by inspecting the container, and use it to build
        # the expected changes.
        container_netinfo = self.run_function(
            'docker.inspect_container',
            [container_name]).get('NetworkSettings', {}).get('Networks', {})[nets[-1].name]
        autoip_keys = self.minion_opts['docker.compare_container_networks']['automatic']
        autoip_config = {
            x: y for x, y in six.iteritems(container_netinfo)
            if x in autoip_keys and y
        }

        expected = {'container': {'Networks': {nets[-1].name: {}}}}
        for key, val in six.iteritems(autoip_config):
            expected['container']['Networks'][nets[-1].name][key] = {
                'old': None, 'new': val
            }
        self.assertEqual(ret['changes'], expected)

        expected = (
            "Container '{0}' is already configured as specified. Connected "
            "to network '{1}'.".format(container_name, nets[-1].name)
        )
        self.assertEqual(ret['comment'], expected)

        # Update the SLS configuration to remove the last network
        kwargs['networks'].pop(-1)
        ret = self.run_state('docker_container.running', **kwargs)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]

        expected = {'container': {'Networks': {nets[-1].name: {}}}}
        for key, val in six.iteritems(autoip_config):
            expected['container']['Networks'][nets[-1].name][key] = {
                'old': val, 'new': None
            }
        self.assertEqual(ret['changes'], expected)

        expected = (
            "Container '{0}' is already configured as specified. Disconnected "
            "from network '{1}'.".format(container_name, nets[-1].name)
        )
        self.assertEqual(ret['comment'], expected)

    @with_network(subnet='10.247.197.96/27', create=True)
    @container_name
    def test_running_ipv4(self, container_name, *nets):
        self._test_running(container_name, *nets)

    @with_network(subnet='10.247.197.128/27', create=True)
    @with_network(subnet='10.247.197.96/27', create=True)
    @container_name
    def test_running_dual_ipv4(self, container_name, *nets):
        self._test_running(container_name, *nets)

    @with_network(subnet='fe3f:2180:26:1::/123', create=True)
    @container_name
    @skipIf(not IPV6_ENABLED, 'IPv6 not enabled')
    def test_running_ipv6(self, container_name, *nets):
        self._test_running(container_name, *nets)

    @with_network(subnet='fe3f:2180:26:1::20/123', create=True)
    @with_network(subnet='fe3f:2180:26:1::/123', create=True)
    @container_name
    @skipIf(not IPV6_ENABLED, 'IPv6 not enabled')
    def test_running_dual_ipv6(self, container_name, *nets):
        self._test_running(container_name, *nets)

    @with_network(subnet='fe3f:2180:26:1::/123', create=True)
    @with_network(subnet='10.247.197.96/27', create=True)
    @container_name
    @skipIf(not IPV6_ENABLED, 'IPv6 not enabled')
    def test_running_mixed_ipv4_and_ipv6(self, container_name, *nets):
        self._test_running(container_name, *nets)

    @container_name
    def test_run_with_onlyif(self, name):
        '''
        Test docker_container.run with onlyif. The container should not run
        (and the state should return a True result) if the onlyif has a nonzero
        return code, but if the onlyif has a zero return code the container
        should run.
        '''
        for cmd in ('/bin/false', ['/bin/true', '/bin/false']):
            log.debug('Trying %s', cmd)
            ret = self.run_state(
                'docker_container.run',
                name=name,
                image=self.image,
                command='whoami',
                onlyif=cmd)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertFalse(ret['changes'])
            self.assertTrue(
                ret['comment'].startswith(
                    'onlyif command /bin/false returned exit code of'
                )
            )
            self.run_function('docker.rm', [name], force=True)

        for cmd in ('/bin/true', ['/bin/true', 'ls /']):
            log.debug('Trying %s', cmd)
            ret = self.run_state(
                'docker_container.run',
                name=name,
                image=self.image,
                command='whoami',
                onlyif=cmd)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertEqual(ret['changes']['Logs'], 'root\n')
            self.assertEqual(
                ret['comment'],
                'Container ran and exited with a return code of 0'
            )
            self.run_function('docker.rm', [name], force=True)

    @container_name
    def test_run_with_unless(self, name):
        '''
        Test docker_container.run with unless. The container should not run
        (and the state should return a True result) if the unless has a zero
        return code, but if the unless has a nonzero return code the container
        should run.
        '''
        for cmd in ('/bin/true', ['/bin/false', '/bin/true']):
            log.debug('Trying %s', cmd)
            ret = self.run_state(
                'docker_container.run',
                name=name,
                image=self.image,
                command='whoami',
                unless=cmd)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertFalse(ret['changes'])
            self.assertEqual(
                ret['comment'],
                'unless command /bin/true returned exit code of 0'
            )
            self.run_function('docker.rm', [name], force=True)

        for cmd in ('/bin/false', ['/bin/false', 'ls /paththatdoesnotexist']):
            log.debug('Trying %s', cmd)
            ret = self.run_state(
                'docker_container.run',
                name=name,
                image=self.image,
                command='whoami',
                unless=cmd)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertEqual(ret['changes']['Logs'], 'root\n')
            self.assertEqual(
                ret['comment'],
                'Container ran and exited with a return code of 0'
            )
            self.run_function('docker.rm', [name], force=True)

    @container_name
    def test_run_with_creates(self, name):
        '''
        Test docker_container.run with creates. The container should not run
        (and the state should return a True result) if all of the files exist,
        but if if any of the files do not exist the container should run.
        '''
        def _mkstemp():
            fd, ret = tempfile.mkstemp()
            try:
                os.close(fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise exc
            else:
                self.addCleanup(os.remove, ret)
                return ret

        bad_file = '/tmp/filethatdoesnotexist'
        good_file1 = _mkstemp()
        good_file2 = _mkstemp()

        for path in (good_file1, [good_file1, good_file2]):
            log.debug('Trying %s', path)
            ret = self.run_state(
                'docker_container.run',
                name=name,
                image=self.image,
                command='whoami',
                creates=path)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertFalse(ret['changes'])
            self.assertEqual(
                ret['comment'],
                'All specified paths in \'creates\' argument exist'
            )
            self.run_function('docker.rm', [name], force=True)

        for path in (bad_file, [good_file1, bad_file]):
            log.debug('Trying %s', path)
            ret = self.run_state(
                'docker_container.run',
                name=name,
                image=self.image,
                command='whoami',
                creates=path)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertEqual(ret['changes']['Logs'], 'root\n')
            self.assertEqual(
                ret['comment'],
                'Container ran and exited with a return code of 0'
            )
            self.run_function('docker.rm', [name], force=True)

    @container_name
    def test_run_replace(self, name):
        '''
        Test the replace and force arguments to make sure they work properly
        '''
        # Run once to create the container
        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='whoami')
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['changes']['Logs'], 'root\n')
        self.assertEqual(
            ret['comment'],
            'Container ran and exited with a return code of 0'
        )

        # Run again with replace=False, this should fail
        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='whoami',
            replace=False)
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertFalse(ret['changes'])
        self.assertEqual(
            ret['comment'],
            'Encountered error running container: Container \'{0}\' exists. '
            'Run with replace=True to remove the existing container'.format(name)
        )

        # Run again with replace=True, this should proceed and there should be
        # a "Replaces" key in the changes dict to show that a container was
        # replaced.
        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='whoami',
            replace=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['changes']['Logs'], 'root\n')
        self.assertTrue('Replaces' in ret['changes'])
        self.assertEqual(
            ret['comment'],
            'Container ran and exited with a return code of 0'
        )

    @container_name
    def test_run_force(self, name):
        '''
        Test the replace and force arguments to make sure they work properly
        '''
        # Start up a container that will stay running
        ret = self.run_state(
            'docker_container.running',
            name=name,
            image=self.image)
        self.assertSaltTrueReturn(ret)

        # Run again with replace=True, this should fail because the container
        # is still running
        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='whoami',
            replace=True,
            force=False)
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertFalse(ret['changes'])
        self.assertEqual(
            ret['comment'],
            'Encountered error running container: Container \'{0}\' exists '
            'and is running. Run with replace=True and force=True to force '
            'removal of the existing container.'.format(name)
        )

        # Run again with replace=True and force=True, this should proceed and
        # there should be a "Replaces" key in the changes dict to show that a
        # container was replaced.
        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='whoami',
            replace=True,
            force=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['changes']['Logs'], 'root\n')
        self.assertTrue('Replaces' in ret['changes'])
        self.assertEqual(
            ret['comment'],
            'Container ran and exited with a return code of 0'
        )

    @container_name
    def test_run_failhard(self, name):
        '''
        Test to make sure that we fail a state when the container exits with
        nonzero status if failhard is set to True, and that we don't when it is
        set to False.
        '''
        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='/bin/false',
            failhard=True)
        self.assertSaltFalseReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['changes']['Logs'], '')
        self.assertTrue(
            ret['comment'].startswith(
                'Container ran and exited with a return code of'
            )
        )
        self.run_function('docker.rm', [name], force=True)

        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='/bin/false',
            failhard=False)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret['changes']['Logs'], '')
        self.assertTrue(
            ret['comment'].startswith(
                'Container ran and exited with a return code of'
            )
        )
        self.run_function('docker.rm', [name], force=True)

    @container_name
    def test_run_bg(self, name):
        '''
        Test to make sure that if the container is run in the background, we do
        not include an ExitCode or Logs key in the return. Then check the logs
        for the container to ensure that it ran as expected.
        '''
        ret = self.run_state(
            'docker_container.run',
            name=name,
            image=self.image,
            command='sh -c "sleep 5 && whoami"',
            bg=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertTrue('Logs' not in ret['changes'])
        self.assertTrue('ExitCode' not in ret['changes'])
        self.assertEqual(ret['comment'], 'Container was run in the background')

        # Now check the logs. The expectation is that the above asserts
        # completed during the 5-second sleep.
        self.assertEqual(
            self.run_function('docker.logs', [name], follow=True),
            'root\n'
        )
