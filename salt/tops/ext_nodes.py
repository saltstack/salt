# -*- coding: utf-8 -*-
'''
External Nodes Classifier
=========================

The External Nodes Classifier is a master tops subsystem used to hook into
systems used to provide mapping information used by major configuration
management systems. One of the most common external nodes classification
system is provided by Cobbler and is called ``cobbler-ext-nodes``.

The cobbler-ext-nodes command can be used with this configuration:

.. code-block:: yaml

    master_tops:
      ext_nodes: cobbler-ext-nodes

It is noteworthy that the Salt system does not directly ingest the data
sent from the ``cobbler-ext-nodes`` command, but converts the data into
information that is used by a Salt top file.
'''

# Import python libs
import subprocess

# Import third party libs
import yaml


def __virtual__():
    '''
    Only run if properly configured
    '''
    if __opts__['master_tops'].get('ext_nodes'):
        return 'ext_nodes'
    return False


def top(**kwargs):
    '''
    Run the command configured
    '''
    if not 'id' in kwargs['opts']:
        return {}
    cmd = '{0} {1}'.format(
            __opts__['master_tops']['ext_nodes'],
            kwargs['opts']['id']
            )
    ndata = yaml.safe_load(
            subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE
                ).communicate()[0])
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
    return ret
