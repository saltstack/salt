# -*- coding: utf-8 -*-
'''
Module for functions that run on the salt master with no target

Useful for populating pillars
'''

# Import Python libs
import copy

# Import Salt libs
import salt

# this is the only way I could figure out how to get the REAL file_roots
# __opt__['file_roots'] is set to  __opt__['pillar_root']
class MMinion(object):
    def __new__(cls, env, reload_env=False):
        # this is to break out of salt.loaded.int and make this a true singleton
        # hack until https://github.com/saltstack/salt/pull/10273 is resolved
        # this is starting to look like PHP
        global _mminions
        if '_mminions' not in globals():
            _mminions = {}
        if env not in _mminions or reload_env:
            opts = copy.deepcopy(__opts__)
            del opts['file_roots']
            # grains at this point are in the context of the minion
            global __grains__
            grains = copy.deepcopy(__grains__)
            m = salt.minion.MasterMinion(opts)

            # this assignment is so that the rest of fxns called by salt still
            # have minion context
            __grains__ = grains

            # this assignment is so that fxns called by mminion have minion
            # context
            m.opts['grains'] = grains

            env_roots = m.opts['file_roots'][env]
            m.opts['module_dirs'] = [fp + '/_modules' for fp in env_roots]
            m.gen_modules()
            _mminions[env] = m
        return _mminions[env]

def mmodule(env, fun, *args, **kwargs):
    '''
    Loads minion modules from an environment so that they can be used in pillars
    for that environment
    '''
    mminion = MMinion(env)
    return mminion.functions[fun](*args, **kwargs)
