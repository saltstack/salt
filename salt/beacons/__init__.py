# -*- coding: utf-8 -*-
'''
This package contains the loader modules for the salt streams system
'''

# Import salt libs
import salt.loader
import salt.utils.odict

class Beacon(object):
    '''
    This class is used to eveluate and execute on the beacon system
    '''
    def __init__(self, opts):
        self.opts = opts
        self.beacons = salt.loader.beacons(opts)

    def process(self, config):
        '''
        Process the configured beacons

        The config must be a dict and looks like this in yaml

        code_block:: yaml

            beacons:
                inotify:
                    - /etc/fstab
                    - /var/cache/foo/*
        '''
        ret = salt.utils.odict.OrderedDict()
        for mod in config:
            fun_str = '{0}.beacon'.format(mod)
            if fun_str in self.beacons:
                ret[mod] = self.beacons[fun_str](config[mod])
        return ret
