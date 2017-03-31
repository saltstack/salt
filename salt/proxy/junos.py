# -*- coding: utf-8 -*-
'''
Interface with a Junos device via proxy-minion. To connect to a junos device \
via junos proxy, specify the host information in the pillar in '/srv/pillar/details.sls'

.. code-block:: yaml

    proxy:
      proxytype: junos
      host: <ip or dns name of host>
      username: <username>
      port: 830
      password: <secret>

In '/srv/pillar/top.sls' map the device details with the proxy name.

.. code-block:: yaml

    base:
      'vmx':
        - details

After storing the device information in the pillar, configure the proxy \
in '/etc/salt/proxy'

.. code-block:: yaml

    master: <ip or hostname of salt-master>

Run the salt proxy via the following command:

.. code-block:: bash

    salt-proxy --proxyid=vmx


'''
from __future__ import absolute_import

# Import python libs
import logging

# Import 3rd-party libs
try:
    HAS_JUNOS = True
    import jnpr.junos
    import jnpr.junos.utils
    import jnpr.junos.utils.config
    import jnpr.junos.utils.sw
except ImportError:
    HAS_JUNOS = False

__proxyenabled__ = ['junos']

thisproxy = {}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'junos'


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not HAS_JUNOS:
        return False, 'Missing dependency: The junos proxy minion requires the \'jnpr\' Python module.'

    return __virtualname__


def init(opts):
    '''
    Open the connection to the Junos device, login, and bind to the
    Resource class
    '''
    opts['multiprocessing'] = False
    log.debug('Opening connection to junos')

    args = {"host": opts['proxy']['host']}
    optional_args = ['user',
                     'username',
                     'password',
                     'passwd',
                     'port',
                     'gather_facts',
                     'mode',
                     'baud',
                     'attempts',
                     'auto_probe',
                     'ssh_private_key_file',
                     'ssh_config',
                     'normalize'
                     ]

    if 'username' in opts['proxy'].keys():
        opts['proxy']['user'] = opts['proxy'].pop('username')
    proxy_keys = opts['proxy'].keys()
    for arg in optional_args:
        if arg in proxy_keys:
            args[arg] = opts['proxy'][arg]

    thisproxy['conn'] = jnpr.junos.Device(**args)
    thisproxy['conn'].open()
    thisproxy['conn'].bind(cu=jnpr.junos.utils.config.Config)
    thisproxy['conn'].bind(sw=jnpr.junos.utils.sw.SW)
    thisproxy['initialized'] = True


def initialized():
    return thisproxy.get('initialized', False)


def conn():
    return thisproxy['conn']


def proxytype():
    '''
    Returns the name of this proxy
    '''
    return 'junos'


def get_serialized_facts():
    facts = dict(thisproxy['conn'].facts)
    if 'version_info' in facts:
        facts['version_info'] = \
            dict(facts['version_info'])
    # For backward compatibility. 'junos_info' is present
    # only of in newer versions of facts.
    if 'junos_info' in facts:
        facts['junos_info']['re0']['object'] = \
            dict(facts['junos_info']['re0']['object'])
        facts['junos_info']['re1']['object'] = \
            dict(facts['junos_info']['re1']['object'])
    return facts


def ping():
    '''
    Ping?  Pong!
    '''
    return thisproxy['conn'].connected


def shutdown(opts):
    '''
    This is called when the proxy-minion is exiting to make sure the
    connection to the device is closed cleanly.
    '''
    log.debug('Proxy module {0} shutting down!!'.format(opts['id']))
    try:
        thisproxy['conn'].close()

    except Exception:
        pass
