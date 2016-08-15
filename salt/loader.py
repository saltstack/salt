# -*- coding: utf-8 -*-
'''The Salt loader is the core to Salt's plugin system, the loader scans
directories for python loadable code and organizes the code into the
plugin interfaces used by Salt.

Import this module directly.  Support pieces are in `loader_core` and
`loader_pre` and are not directly usable.  Functions from
`loader_core` and that load Salt sub-system extensions modules from
`.loader.py` files will show up *here*.

Example:

.. code-block:: python

  from salt import loader

  def example1(opts):
      returners = loader.returners(opts, funcs)
      auth = loader.auth(opts)
      beacons = loader.beacons(opts, funcs)


Each of the `loader.FUNCNAME()` functions used above in `example1()`
are imported from the `.loader.py` files from the extension
sub-systems.
'''


from __future__ import absolute_import

import salt.loader_pre as loader_pre
from salt import loader_core

# Side-effect of importing `salt.loader` - discover extensions and load all of the pre-loaders
loader_pre.load_all_loaders(loader_core.SALT_BASE_PATH, globals())
