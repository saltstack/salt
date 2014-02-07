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
    _mminion = None
    def __new__(cls, *args, **kwargs):
        if not cls._mminion:
            cls._mminion = super(MMinion, cls).__new__( cls, *args, **kwargs)
            opts = copy.deepcopy(__opts__)
            del opts['file_roots']
            # grains at this point are in the context of the minion
            grains = copy.deepcopy(__grains__)
            cls._mminion = salt.minion.MasterMinion(opts)
            # this assignment is so that the rest of fxns called by salt still
            # have minion context
            __grains__ = grains
            # this assignment is so that fxns called by mminion have minion
            # context
           cls._mminion.opts['grains'] = grains
        return cls._mminion

def mmodule(env, fun, *args, **kwargs):
    '''
    Loads minion modules from an environment so that they can be used in pillars
    for that environment
    '''
    mminion = MMinion()
    env_roots = mminion.opts['file_roots'][env]
    mminion.opts['module_dirs'] = [fp + '/_modules' for fp in env_roots]
    mminion.gen_modules()
    return mminion.functions[fun](*args, **kwargs)
