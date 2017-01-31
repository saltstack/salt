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

# Import python libs
from __future__ import absolute_import
from __future__ import print_function
import logging
import copy

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
    port = opts['proxy'].get('port', 830)
    thisproxy['conn'] = jnpr.junos.Device(user=opts['proxy']['username'],
                                          host=opts['proxy']['host'],
                                          password=opts['proxy']['passwd'],
                                          port=port)
    thisproxy['conn'].open()
    thisproxy['conn'].bind(cu=jnpr.junos.utils.config.Config)
    thisproxy['conn'].bind(sw=jnpr.junos.utils.sw.SW)
    thisproxy['conn'].facts['version_info'] = dict(
        thisproxy['conn'].facts['version_info'])
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


def grains():
    thisproxy['grains'] = copy.deepcopy(thisproxy['conn'].facts)
    if not thisproxy['grains']:
        log.error(
            'The device must be master to gather facts. Grains will not be populated by junos facts.')
        
    if 'version_info' in thisproxy['grains'] and thisproxy['grains']['version_info']:
        thisproxy['grains']['version_info'] = thisproxy['grains']['version_info'].v_dict

    return thisproxy['grains']


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
