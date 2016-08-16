# -*- coding: utf-8; mode: python -*-

'''Pre-loader for "modules" sub-system'''


from __future__ import absolute_import

import salt
from salt import loader_core
from salt import loader_pre


@loader_pre.LoaderFunc
def minion_mods(
        opts,
        context=None,
        utils=None,
        whitelist=None,
        include_errors=False,
        initial_load=False,
        loaded_base_name=None,
        notify=False,
        static_modules=None,
        proxy=None):
    '''
    Load execution modules

    Returns a dictionary of execution modules appropriate for the current
    system by evaluating the __virtual__() function in each module.

    :param dict opts: The Salt options dictionary

    :param dict context: A Salt context that should be made present inside
                            generated modules in __context__

    :param dict utils: Utility functions which should be made available to
                            Salt modules in __utils__. See `utils_dir` in
                            salt.config for additional information about
                            configuration.

    :param list whitelist: A list of modules which should be whitelisted.
    :param bool include_errors: Deprecated flag! Unused.
    :param bool initial_load: Deprecated flag! Unused.
    :param str loaded_base_name: A string marker for the loaded base name.
    :param bool notify: Flag indicating that an event should be fired upon
                        completion of module loading.

    .. code-block:: python

        import salt.config
        import salt.loader

        __opts__ = salt.config.minion_config('/etc/salt/minion')
        __grains__ = salt.loader.grains(__opts__)
        __opts__['grains'] = __grains__
        __utils__ = salt.loader.utils(__opts__)
        __salt__ = salt.loader.minion_mods(__opts__, utils=__utils__)
        __salt__['test.ping']()
    '''
    # TODO Publish documentation for module whitelisting
    if not whitelist:
        whitelist = opts.get('whitelist_modules', None)
    ret = loader_core.LazyLoader(
        loader_core.module_dirs(opts, 'modules', 'module'),
        opts,
        tag='module',
        pack={'__context__': context, '__utils__': utils, '__proxy__': proxy},
        whitelist=whitelist,
        loaded_base_name=loaded_base_name,
        static_modules=static_modules,
    )

    ret.pack['__salt__'] = ret

    # Load any provider overrides from the configuration file providers option
    #  Note: Providers can be pkg, service, user or group - not to be confused
    #        with cloud providers.
    providers = opts.get('providers', False)
    if providers and isinstance(providers, dict):
        for mod in providers:
            # sometimes providers opts is not to diverge modules but
            # for other configuration
            try:
                funcs = loader_core.raw_mod(opts, providers[mod], ret)
            except TypeError:
                break
            else:
                if funcs:
                    for func in funcs:
                        f_key = '{0}{1}'.format(mod, func[func.rindex('.'):])
                        ret[f_key] = funcs[func]

    if notify:
        evt = salt.utils.event.get_event('minion', opts=opts, listen=False)
        evt.fire_event({'complete': True}, tag='/salt/minion/minion_mod_complete')

    return ret
