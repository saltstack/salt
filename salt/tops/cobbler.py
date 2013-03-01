'''
Cobbler Tops
============

Cobbler Tops is a master tops subsystem used to look up mapping information
from Cobbler via its API.

.. code-block:: yaml
    master_tops:
      cobbler:
        - host: https://example.com/ #default is http://localhost/
        - user: username # default is no username
        - password: password # default is no password

'''

# Import python libs
import logging
import xmlrpclib


# Set up logging
log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only run if properly configured
    '''
    if __opts__['master_tops'].get('cobbler'):
        return 'cobbler'
    return False


def top(opts={}, host='http://localhost/', user=None, password=None, **kwargs):
    '''
    Look up top data for a host in Cobbler
    '''
    if not 'id' in opts:
        return {}

    hostname = opts['id']
    log.info("Querying cobbler for information for %r", hostname)
    try:
        server = xmlrpclib.Server('%s/cobbler_api' % host, allow_none=True)
        if user:
            server = (server, server.login(user, password))
        data = server.get_blended_data(None, hostname)
    except Exception:
        log.exception(
            'Could not connect to cobbler.'
        )
        return {}

    return {data['status']: data['mgmt_classes']}
