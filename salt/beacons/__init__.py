# -*- coding: utf-8 -*-
'''
This package contains the loader modules for the salt streams system
'''
# Import salt libs
import salt.loader


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
        ret = []
        for mod in config:
            fun_str = '{0}.beacon'.format(mod)
            if fun_str in self.beacons:
                tag = 'salt/beacon/{0}/{1}/'.format(self.opts['id'], mod)
                raw = self.beacons[fun_str](config[mod])
                for data in raw:
                    if 'tag' in data:
                        tag += data.pop('tag')
                    if 'id' not in data:
                        data['id'] = self.opts['id']
                    ret.append({'tag': tag, 'data': data})
        return ret
