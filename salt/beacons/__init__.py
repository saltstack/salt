# -*- coding: utf-8 -*-
'''
This package contains the loader modules for the salt streams system
'''
# Import Python libs
from __future__ import absolute_import
import logging
import copy

# Import Salt libs
import salt.loader

log = logging.getLogger(__name__)


class Beacon(object):
    '''
    This class is used to eveluate and execute on the beacon system
    '''
    def __init__(self, opts, functions):
        self.opts = opts
        self.beacons = salt.loader.beacons(opts, functions)
        self.interval_map = dict()

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
        b_config = copy.deepcopy(config)
        for mod in config:
            log.trace('Beacon processing: {0}'.format(mod))
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

    def _process_interval(self, mod, interval):
        '''
        Process beacons with intervals
        Return True if a beacon should be run on this loop
        '''
        log.trace('Processing interval {0} for beacon mod {1}'.format(interval, mod))
        loop_interval = self.opts['loop_interval']
        if mod in self.interval_map:
            log.trace('Processing interval in map')
            counter = self.interval_map[mod]
            log.trace('Interval counter: {0}'.format(counter))
            if counter * loop_interval >= interval[0]['interval']:
                self.interval_map[mod] = 1
                return True
            else:
                self.interval_map[mod] += 1
        else:
            log.trace('Interval process inserting mod: {0}'.format(mod))
            self.interval_map[mod] = 1
        return False
