# -*- coding: utf-8 -*-
'''Provide authentication using configured shared secret

.. code-block:: yaml

    external_auth:
      sharedsecret:
        fred:
          - .*
          - '@jobs'


The shared secret should be added to the master configuration, for
example in /etc/salt/master.d/sharedsecret.conf (make sure that file
is only readable by the user running the master):

.. code-block:: yaml

   sharedsecret: OIUHF_CHANGE_THIS_12h88

This auth module should be used with caution. It was initially
designed to work with a frontal that takes care of authentication (for
example kerberos) and places the shared secret in the HTTP headers to
the salt-api call. This salt-api call should really be done on
localhost to avoid someone eavesdropping on the shared secret.

See the documentation for cherrypy to setup the headers in your
frontal.

.. versionadded:: Beryllium
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)


def auth(username, sharedsecret, **kwargs):
    '''
    Shared secret authentication
    '''
    return sharedsecret == __opts__.get('sharedsecret')
