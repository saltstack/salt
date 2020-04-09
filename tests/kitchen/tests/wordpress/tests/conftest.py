# -*- coding: utf-8 -*-
from __future__ import absolute_import
import functools
import os
import pytest
import subprocess
import testinfra

if os.environ.get('KITCHEN_USERNAME') == 'vagrant':
    if 'windows' in os.environ.get('KITCHEN_INSTANCE'):
        test_host = testinfra.get_host('winrm://{KITCHEN_USERNAME}:{KITCHEN_PASSWORD}@{KITCHEN_HOSTNAME}:{KITCHEN_PORT}'.format(**os.environ), no_ssl=True)
    else:
        test_host = testinfra.get_host('paramiko://{KITCHEN_USERNAME}@{KITCHEN_HOSTNAME}:{KITCHEN_PORT}'.format(**os.environ),
                                       ssh_identity_file=os.environ.get('KITCHEN_SSH_KEY'))
elif 'KITCHEN_USERNAME' in os.environ:
    test_host = testinfra.get_host('docker://{KITCHEN_USERNAME}@{KITCHEN_CONTAINER_ID}'.format(**os.environ))


@pytest.fixture
def host():
    return test_host


@pytest.fixture
def salt():
    if 'windows' in os.environ.get('KITCHEN_INSTANCE'):
        tmpconf = r'c:\Users\vagrant\AppData\Local\Temp\kitchen\etc\salt'
    else:
        test_host.run('sudo chown -R {0} /tmp/kitchen'.format(os.environ.get('KITCHEN_USERNAME')))
        tmpconf = '/tmp/kitchen/etc/salt'
    return functools.partial(test_host.salt, config=tmpconf)


@pytest.fixture
def http_port():
    return subprocess.check_output(
        ['docker', 'inspect',
         '-f', '{{(index (index .NetworkSettings.Ports "80/tcp") 0).HostPort}}',
         os.environ.get('KITCHEN_CONTAINER_ID')]
    ).strip().decode()


@pytest.fixture
def host_ip():
    return os.environ.get('KITCHEN_HOSTNAME')
