# -*- coding: utf-8 -*-
'''
.. |reclass| replace:: **reclass**

This :doc:`master_tops </topics/master_tops/index>` plugin provides access to
the |reclass| database, such that state information (top data) are retrieved
from |reclass|.

You can find more information about |reclass| at
http://reclass.pantsfullofunix.net.

To use the plugin, add it to the ``master_tops`` list in the Salt master config
and tell |reclass| by way of a few options how and where to find the
inventory:

.. code-block:: yaml

    master_tops:
      reclass:
        storage_type: yaml_fs
        base_inventory_uri: /srv/salt

This would cause |reclass| to read the inventory from YAML files in
``/srv/salt/nodes`` and ``/srv/salt/classes``.

If you are also using |reclass| as ``ext_pillar`` plugin, and you want to
avoid having to specify the same information for both, use YAML anchors (take
note of the differing data types for ``ext_pillar`` and ``master_tops``):

.. code-block:: yaml

    reclass: &reclass
      storage_type: yaml_fs
      base_inventory_uri: /srv/salt
      reclass_source_path: ~/code/reclass

    ext_pillar:
      - reclass: *reclass

    master_tops:
      reclass: *reclass

If you want to run reclass from source, rather than installing it, you can
either let the master know via the ``PYTHONPATH`` environment variable, or by
setting the configuration option, like in the example above.
'''

# This file cannot be called reclass.py, because then the module import would
# not work. Thanks to the __virtual__ function, however, the plugin still
# responds to the name 'reclass'.

import sys
from salt.utils.reclass import (
    prepend_reclass_source_path,
    filter_out_source_path_option,
    set_inventory_base_uri_default
)

from salt.exceptions import SaltInvocationError


def __virtual__(retry=False):
    try:
        import reclass
        return 'reclass'
    except ImportError:
        if retry:
            return False

        opts = __opts__.get('master_tops', {}).get('reclass', {})
        prepend_reclass_source_path(opts)
        return __virtual__(retry=True)


def top(**kwargs):
    '''
    Query |reclass| for the top data (states of the minions).
    '''

    # If reclass is installed, __virtual__ put it onto the search path, so we
    # don't need to protect against ImportError:
    from reclass.adapters.salt import top as reclass_top
    from reclass.errors import ReclassException

    try:
        # Salt's top interface is inconsistent with ext_pillar (see #5786) and
        # one is expected to extract the arguments to the master_tops plugin
        # by parsing the configuration file data. I therefore use this adapter
        # to hide this internality.
        reclass_opts = __opts__['master_tops']['reclass']

        # the source path we used above isn't something reclass needs to care
        # about, so filter it:
        filter_out_source_path_option(reclass_opts)

        # if no inventory_base_uri was specified, initialise it to the first
        # file_roots of class 'base' (if that exists):
        set_inventory_base_uri_default(__opts__, kwargs)

        # Salt expects the top data to be filtered by minion_id, so we better
        # let it know which minion it is dealing with. Unfortunately, we must
        # extract these data (see #6930):
        minion_id = kwargs['opts']['id']

        # I purposely do not pass any of __opts__ or __salt__ or __grains__
        # to reclass, as I consider those to be Salt-internal and reclass
        # should not make any assumptions about it. Reclass only needs to know
        # how it's configured, so:
        return reclass_top(minion_id, **reclass_opts)

    except ImportError as e:
        if 'reclass' in e.message:
            raise SaltInvocationError(
                'master_tops.reclass: cannot find reclass module '
                'in {0}'.format(sys.path)
            )
        else:
            raise

    except TypeError as e:
        if 'unexpected keyword argument' in e.message:
            arg = e.message.split()[-1]
            raise SaltInvocationError(
                'master_tops.reclass: unexpected option: {0}'.format(arg)
            )
        else:
            raise

    except KeyError as e:
        if 'reclass' in e.message:
            raise SaltInvocationError('master_tops.reclass: no configuration '
                                      'found in master config')
        else:
            raise

    except ReclassException as e:
        raise SaltInvocationError('master_tops.reclass: {0}'.format(e.message))
