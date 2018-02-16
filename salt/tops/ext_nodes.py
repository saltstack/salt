# -*- coding: utf-8 -*-
'''
External Nodes Classifier
=========================

The External Nodes Classifier is a master tops subsystem that retrieves mapping
information from major configuration management systems. One of the most common
external nodes classifiers system is provided by Cobbler and is called
``cobbler-ext-nodes``.

The cobbler-ext-nodes command can be used with this configuration:

.. code-block:: yaml

    master_tops:
      ext_nodes: cobbler-ext-nodes

It is noteworthy that the Salt system does not directly ingest the data
sent from the ``cobbler-ext-nodes`` command, but converts the data into
information that is used by a Salt top file.

Any command can replace the call to 'cobbler-ext-nodes' above, but currently the
data must be formatted in the same way that the standard 'cobbler-ext-nodes'
does.

See (admittedly degenerate and probably not complete) example:

.. code-block:: yaml

    classes:
      - basepackages
      - database

The above essentially is the same as a top.sls containing the following:

.. code-block:: yaml

    base:
      '*':
        - basepackages
        - database

    base:
      '*':
        - basepackages
        - database
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import subprocess

# Import Salt libs
import salt.utils.yaml

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only run if properly configured
    '''
    if __opts__['master_tops'].get('ext_nodes'):
        return True
    return False


def top(**kwargs):
    '''
    Run the command configured
    '''
    if 'id' not in kwargs['opts']:
        return {}
    cmd = '{0} {1}'.format(
            __opts__['master_tops']['ext_nodes'],
            kwargs['opts']['id']
            )
    ndata = salt.utils.yaml.safe_load(
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE.communicate()[0])
    )
    if not ndata:
        log.info('master_tops ext_nodes call did not return any data')
    ret = {}
    if 'environment' in ndata:
        env = ndata['environment']
    else:
        env = 'base'

    if 'classes' in ndata:
        if isinstance(ndata['classes'], dict):
            ret[env] = list(ndata['classes'])
        elif isinstance(ndata['classes'], list):
            ret[env] = ndata['classes']
        else:
            return ret
    else:
        log.info('master_tops ext_nodes call did not have a dictionary with a "classes" key.')

    return ret
