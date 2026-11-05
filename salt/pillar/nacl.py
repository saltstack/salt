"""
Decrypt pillar data through the builtin NACL renderer

In most cases, you'll want to make this the last external pillar used. For
example, to pair with the builtin stack pillar you could do something like
this:

.. code:: yaml

    nacl.config:
        sk_file: /root/.nacl

    ext_pillar:
      - stack: /path/to/stack.cfg
      - nacl: {}

Set ``nacl.config`` in your config.

"""

import salt

__virtualname__ = "nacl"


def __virtual__():
    if __opts__["fips_mode"] is True:
        return False, "nacl pillar data not available in FIPS mode"
    return __virtualname__


def ext_pillar(minion_id, pillar, *args, **kwargs):
    """Decrypt accumulated pillar data using the NaCl renderer."""
    render_function = salt.loader.render(__opts__, __salt__).get("nacl")
    return render_function(pillar)
