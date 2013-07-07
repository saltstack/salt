'''
ext_pillar adapter for reclass.

Please refer to the file ``README.Salt`` in the reclass source for more
information on how to use these. In a nutshell, you'll just add the plugin to
the ext_pillar hash in the master config and tell reclass by way of a few
options how and where to find the inventory::

    ---
    ext_pillar:
        - reclass:
            storage_type: yaml_fs
            base_inventory_uri: /srv/salt

This would cause reclass to read the inventory from YAML files in
``/srv/salt/nodes`` and ``/srv/salt/classes``.

More information about reclass: http://github.com/madduck/reclass

If you are also using master_tops and you want to avoid having to specify the
same information for both, use YAML anchors:

    ---
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

from salt.utils.reclass import prepend_reclass_source_path, \
        filter_out_source_path_option, set_inventory_base_uri_default

def __virtual__(retry=False):
    try:
        import reclass
        return 'reclass'

    except ImportError as e:
        if retry:
            return False

        for pillar in __opts__.get('ext_pillar', []):
            if 'reclass' not in pillar.keys():
                continue

            # each pillar entry is a single-key hash of name -> options
            opts = pillar.values()[0]
            prepend_reclass_source_path(opts)
            break

        return __virtual__(retry=True)


from salt.exceptions import SaltInvocationError

def ext_pillar(minion_id, pillar, **kwargs):
    # If reclass is installed, __virtual__ put it onto the search path, so we
    # don't need to protect against ImportError:
    from reclass.adapters.salt import ext_pillar as reclass_ext_pillar
    from reclass.errors import ReclassException

    try:
        # the source path we used above isn't something reclass needs to care
        # about, so filter it:
        filter_out_source_path_option(kwargs)

        # if no inventory_base_uri was specified, initialise it to the first
        # file_roots of class 'base' (if that exists):
        set_inventory_base_uri_default(__opts__, kwargs)

        # I purposely do not pass any of __opts__ or __salt__ or __grains__
        # to reclass, as I consider those to be Salt-internal and reclass
        # should not make any assumptions about it.
        return reclass_ext_pillar(minion_id, pillar, **kwargs)

    except TypeError as e:
        if 'unexpected keyword argument' in e.message:
            arg = e.message.split()[-1]
            raise SaltInvocationError('ext_pillar.reclass: unexpected option: '\
                                      + arg)
        else:
            raise

    except KeyError as e:
        if 'id' in e.message:
            raise SaltInvocationError('ext_pillar.reclass: __opts__ does not '\
                                      'define minion ID')
        else:
            raise

    except ReclassException as e:
        raise SaltInvocationError('ext_pillar.reclass: ' + e.message)
