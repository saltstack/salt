'''
ext_pillar adapter for reclass.

Please refer to the file `README.Salt` in the reclass source for more
information on how to use these. In a nutshell, you'll just add the plugin to
the ext_pillar hash in the master config and tell reclass by way of a few
options how and where to find the inventory:

    ---
    ext_pillar:
        - reclass:
            storage_type: yaml_fs
            base_inventory_uri: /srv/salt

This would cause reclass to read the inventory from YAML files in
`/srv/salt/nodes` and `/srv/salt/classes`.

More information about reclass: http://github.com/madduck/reclass

There is currently no way to avoid having to specify the same configuration
for `ext_pillar` and `master_tops`.

Unfortunately, there is currently no way to specify the location of the
reclass source in the master config, because Salt provides no way to access
the configuration file data at the module scope (`__opts__` is injected by the
Salt loader), where we need to know about whether reclass is import-able to be
able to define the `__virtual__` function. You will hence either have to
install reclass to `PYTHONPATH`, or extend `PYTHONPATH` when running the
master, e.g.:

    PYTHONPATH=~/code/reclass:$PYTHONPATH salt-master …
'''
# This file cannot be called reclass.py, because then the module import would
# not work. Thanks to the __virtual__ function, however, the plugin still
# responds to the name 'reclass'.

try:
    from reclass.adapters.salt import ext_pillar as reclass_ext_pillar
    from reclass.errors import ReclassException
    __virtual__ = lambda: 'reclass'

except ImportError:
    __virtual__ = lambda: False

from salt.exceptions import SaltInvocationError

def ext_pillar(pillar, **kwargs):
    try:
        return reclass_ext_pillar(__opts__, __salt__, __grains__, pillar, **kwargs)

    except TypeError, e:
        if e.message.find('unexpected keyword argument') > -1:
            arg = e.message.split()[-1]
            raise SaltInvocationError('pillar.reclass: unexpected option: ' + arg)

        else:
            raise

    except ReclassException, e:
        raise SaltInvocationError('pillar.reclass: ' + e.message)
