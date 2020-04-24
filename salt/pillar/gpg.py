# -*- coding: utf-8 -*-

"""
Decrypt pillar data through the builtin GPG renderer

In most cases, you'll want to make this the last external pillar used. For
example, to pair with the builtin stack pillar you could do something like
this:

.. code:: yaml

    ext_pillar:
      - stack: /path/to/stack.cfg
      - gpg: {}

Set ``gpg_keydir`` in your config to adjust the homedir the renderer uses.

"""

from __future__ import absolute_import, print_function, unicode_literals

import salt.loader


def ext_pillar(minion_id, pillar, *args, **kwargs):
    render_function = salt.loader.render(__opts__, __salt__).get("gpg")
    return render_function(pillar)
