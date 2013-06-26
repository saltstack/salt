'''
master_tops adapter for reclass.

Please refer to the file `README.Salt` in the reclass source for more
information on how to use these. In a nutshell, you'll just add the plugin to
the master_tops hash in the master config and tell reclass by way of a few
options how and where to find the inventory:

    ---
    master_tops:
        reclass:
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
    from reclass.adapters.salt import top as reclass_top
    from reclass.errors import ReclassException
    __virtual__ = lambda: 'reclass'

except ImportError:
    __virtual__ = lambda: False

from salt.exceptions import SaltInvocationError

def top(**kwargs):
    try:
        # Salt's top interface is inconsistent with ext_pillar (see #5786) and
        # one is expected to extract the arguments to the master_tops plugin
        # by parsing the configuration file data. I therefore use this adapter
        # to hide this internality.
        reclass_opts = __opts__['master_tops']['reclass']

        # I purposely do not pass any of __opts__ or __salt__ or __grains__
        # to reclass, as I consider those to be Salt-internal and reclass
        # should not make any assumptions about it. Reclass only needs to know
        # how it's configured, so:
        return reclass_top(**reclass_opts)

    except TypeError, e:
        if e.message.find('unexpected keyword argument') > -1:
            arg = e.message.split()[-1]
            raise SaltInvocationError('master_tops.reclass: unexpected option: ' + arg)
        else:
            raise

    except KeyError, e:
        if e.message.find('reclass') > -1:
            raise SaltInvocationError('master_tops.reclass: no configuration '\
                                      'found in master config')
        else:
            raise

    except ReclassException, e:
        raise SaltInvocationError('master_tops.reclass: ' + e.message)
