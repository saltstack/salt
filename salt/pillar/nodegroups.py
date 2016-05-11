#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
=================
Nodegroups Pillar
=================

Introspection: to which nodegroups does my minion belong?
Provides a pillar with the default name of `nodegroups`
which contains a list of nodegroups which match for a given minion.

Command Line
------------

.. code-block:: bash
    salt-call pillar.get nodegroups
    local:
        - class_infra
        - colo_sj
        - state_active
        - country_US
        - type_saltmaster

Configuring Nodegroups Pillar
-----------------------------

.. code-block:: yaml

    ext_pillar:
    extension_modules: /srv/salt/ext
      - nodegroups:
          pillar_name: 'nodegroups'

'''

# Import futures
from __future__ import absolute_import

# Import Salt libs
from salt.minion import Matcher

# Import 3rd-party libs
import salt.ext.six as six


__author__ = 'Andrew Hammond <andrew.george.hammond@gmail.com>'
__copyright__ = 'Copyright (c) 2016 AnchorFree Inc.'
__license__ = 'Apache License, Version 2.0'
__version__ = '0.0.1'


def ext_pillar(minion_id, pillar, pillar_name=None, *args, **kwargs):
    pillar_name = pillar_name or 'nodegroups'
    m = Matcher(__opts__)
    all_nodegroups = __opts__['nodegroups']
    nodegroups_minion_is_in = []
    for nodegroup_name in six.iterkeys(all_nodegroups):
        if m.nodegroup_match(nodegroup_name, all_nodegroups):
            nodegroups_minion_is_in.append(nodegroup_name)
    return {pillar_name: nodegroups_minion_is_in}
