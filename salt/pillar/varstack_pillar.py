# -*- coding: utf-8 -*-
'''
Use `Varstack <https://github.com/conversis/varstack>`_ data as a Pillar source

Configuring Varstack
====================

Using varstack in Salt is fairly simple. Just put the following into the
config file of your master:

.. code-block:: yaml

    ext_pillar:
      - varstack: /etc/varstack.yaml

Varstack will then use /etc/varstack.yaml to determine which configuration
data to return as pillar information. From there you can take a look at the
`README <https://github.com/conversis/varstack/blob/master/README.md>`_ of
varstack on how this file is evaluated.
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

HAS_VARSTACK = False
try:
    import varstack
    HAS_VARSTACK = True
except ImportError:
    pass

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'varstack'


def __virtual__():
    if not HAS_VARSTACK:
        return False
    return __virtualname__


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Parse varstack data and return the result
    '''
    vs = varstack.Varstack(config_filename=conf)
    return vs.evaluate(__grains__)
