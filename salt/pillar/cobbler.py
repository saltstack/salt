'''
Cobbler Pillar
==============
A pillar module to pull data from Cobbler via its API
into the pillar dictionary.

.. code-block:: yaml
    ext_pillar:
       - cobbler:
         - url: https://example.com/ # Cobbler base URL. Default: http://localhost/
         - user: username # Cobbler username. Default is no username.
         - password: password # Cobbler password. Default is no password.
         - key: cobbler # Nest results within this key. By default, values are not nested.
         - only: [parameters] # Add only these keys to pillar.

'''

# Import python libs
import logging
import xmlrpclib


# Set up logging
log = logging.getLogger(__name__)

def ext_pillar(pillar, url='http://localhost/', user=None, password=None, key=None, only=[]):
    '''
    Read pillar data from Cobbler via its API.
    '''
    hostname = __opts__['id']
    log.info("Querying cobbler for information for %r", hostname)
    try:
		server = xmlrpclib.Server('%s/cobbler_api' % url, allow_none=True)
		if user:
			server = (server, server.login(user, password))
		result = server.get_blended_data(None, hostname)
    except Exception:
        log.exception(
			'Could not connect to cobbler.'
        )
        return {}

    if only:
        _result = {}
        for i in only:
            if i in result:
                _result[i] = result[i]
        result = _result

    if key:
        result = {key: result}
    return result
