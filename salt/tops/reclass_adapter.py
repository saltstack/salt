'''
master_tops adapter for reclass.

Please refer to the file ``README.Salt`` in the reclass source for more
information on how to use these. In a nutshell, you'll just add the plugin to
the master_tops hash in the master config and tell reclass by way of a few
options how and where to find the inventory:

.. code-block:: yaml

    master_tops:
        reclass:
            storage_type: yaml_fs
            base_inventory_uri: /srv/salt

This would cause reclass to read the inventory from YAML files in
``/srv/salt/nodes`` and ``/srv/salt/classes``.

More information about reclass: http://github.com/madduck/reclass

If you are also using ext_pillar and you want to avoid having to specify the
same information for both, use YAML anchors:

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
from salt.utils.reclass import prepend_reclass_source_path, \
        filter_out_source_path_option, set_inventory_base_uri_default

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

from salt.exceptions import SaltInvocationError

def top(**kwargs):
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

        # I purposely do not pass any of __opts__ or __salt__ or __grains__
        # to reclass, as I consider those to be Salt-internal and reclass
        # should not make any assumptions about it. Reclass only needs to know
        # how it's configured, so:
        return reclass_top(**reclass_opts)

    except ImportError as e:
        if 'reclass' in e.message:
            raise SaltInvocationError('master_tops.reclass: cannot find reclass '
                                      'module in ' + sys.path)
        else:
            raise

    except TypeError as e:
        if 'unexpected keyword argument' in e.message:
            arg = e.message.split()[-1]
            raise SaltInvocationError('master_tops.reclass: unexpected option: ' + arg)
        else:
            raise

    except KeyError as e:
        if 'reclass' in e.message:
            raise SaltInvocationError('master_tops.reclass: no configuration '
                                      'found in master config')
        else:
            raise

    except ReclassException as e:
        raise SaltInvocationError('master_tops.reclass: ' + e.message)
