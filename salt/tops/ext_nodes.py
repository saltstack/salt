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
from __future__ import absolute_import

# Import python libs
import logging
import subprocess

# Import third party libs
import yaml

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only run if properly configured
    '''
    if __opts__[u'master_tops'].get(u'ext_nodes'):
        return True
    return False


def top(**kwargs):
    '''
    Run the command configured
    '''
    if u'id' not in kwargs[u'opts']:
        return {}
    cmd = u'{0} {1}'.format(
            __opts__[u'master_tops'][u'ext_nodes'],
            kwargs[u'opts'][u'id']
            )
    ndata = yaml.safe_load(
            subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE
                ).communicate()[0])
    if not ndata:
        log.info(u'master_tops ext_nodes call did not return any data')
    ret = {}
    if u'environment' in ndata:
        env = ndata[u'environment']
    else:
        env = u'base'

    if u'classes' in ndata:
        if isinstance(ndata[u'classes'], dict):
            ret[env] = list(ndata[u'classes'])
        elif isinstance(ndata[u'classes'], list):
            ret[env] = ndata[u'classes']
        else:
            return ret
    else:
        log.info(u'master_tops ext_nodes call did not have a dictionary with a "classes" key.')

    return ret
