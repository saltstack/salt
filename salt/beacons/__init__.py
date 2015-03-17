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
                interval = [arg for arg in config[mod] if 'interval' in arg]
                if interval:
                    b_config[mod].remove(interval[0])
                    if not self._process_interval(mod, interval):
                        log.trace('Skipping beacon {0}. Interval not reached.'.format(mod))
                        continue
                raw = self.beacons[fun_str](b_config[mod])
                for data in raw:
                    tag = 'salt/beacon/{0}/{1}/'.format(self.opts['id'], mod)
                    if 'tag' in data:
                        tag += data.pop('tag')
                    if 'id' not in data:
                        data['id'] = self.opts['id']
                    ret.append({'tag': tag, 'data': data})
        return ret
