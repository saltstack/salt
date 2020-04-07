# -*- coding: utf-8 -*-

"""
Decrypt pillar data through the builtin NACL renderer

In most cases, you'll want to make this the last external pillar used. For
example, to pair with the builtin stack pillar you could do something like
this:

.. code:: yaml

    nacl.config:
        keyfile: /root/.nacl

    ext_pillar:
      - stack: /path/to/stack.cfg
      - nacl: {}

Set ``nacl.config`` in your config.

"""

from __future__ import absolute_import, print_function, unicode_literals

import salt


def ext_pillar(minion_id, pillar, *args, **kwargs):
    render_function = salt.loader.render(__opts__, __salt__).get("nacl")
    return render_function(pillar)
