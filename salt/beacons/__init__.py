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
import salt.utils

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
                    /etc/fstab: {}
                    /var/cache/foo: {}
        '''
        ret = []
        b_config = copy.deepcopy(config)
        if 'enabled' in b_config and not b_config['enabled']:
            return
        for mod in config:
            if mod == 'enabled':
                continue
            if 'enabled' in config[mod] and not config[mod]['enabled']:
                log.trace('Beacon {0} disabled'.format(mod))
                continue
            elif 'enabled' in config[mod] and config[mod]['enabled']:
                # remove 'enabled' item before processing the beacon
                del config[mod]['enabled']

            log.trace('Beacon processing: {0}'.format(mod))
            fun_str = '{0}.beacon'.format(mod)
            if fun_str in self.beacons:
                if isinstance(config[mod], list):
                    interval = None
                    interval_config = [arg for arg in config[mod] if 'interval' in arg]
                    if interval_config:
                        interval = interval_config[0]['interval']
                elif isinstance(config[mod], dict):
                    interval = config[mod].get('interval', False)
                if interval:
                    if isinstance(b_config[mod], list):
                        b_config[mod].remove(interval_config[0])
                    elif isinstance(b_config[mod], dict):
                        b_config[mod].pop('interval')
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
            if counter * loop_interval >= interval:
                self.interval_map[mod] = 1
                return True
            else:
                self.interval_map[mod] += 1
        else:
            log.trace('Interval process inserting mod: {0}'.format(mod))
            self.interval_map[mod] = 1
        return False

    def list_beacons(self):
        '''
        List the beacon items
        '''
        # Fire the complete event back along with the list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacons_list_complete')

        return True

    def add_beacon(self, name, beacon_data):
        '''
        Add a beacon item
        '''

        data = {}
        data[name] = beacon_data

        if name in self.opts['beacons']:
            log.info('Updating settings for beacon '
                     'item: {0}'.format(name))
        else:
            log.info('Added new beacon item {0}'.format(name))
        self.opts['beacons'].update(data)

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacon_add_complete')

        return True

    def modify_beacon(self, name, beacon_data):
        '''
        Modify a beacon item
        '''

        data = {}
        data[name] = beacon_data

        log.info('Updating settings for beacon '
                 'item: {0}'.format(name))
        self.opts['beacons'].update(data)

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacon_modify_complete')

        return True

    def delete_beacon(self, name):
        '''
        Delete a beacon item
        '''

        if name in self.opts['beacons']:
            log.info('Deleting beacon item {0}'.format(name))
            del self.opts['beacons'][name]

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacon_delete_complete')

        return True

    def enable_beacons(self):
        '''
        Enable beacons
        '''

        self.opts['beacons']['enabled'] = True

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacons_enabled_complete')

        return True

    def disable_beacons(self):
        '''
        Enable beacons
        '''

        self.opts['beacons']['enabled'] = False

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacons_disabled_complete')

        return True

    def enable_beacon(self, name):
        '''
        Enable a beacon
        '''

        self.opts['beacons'][name]['enabled'] = True

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacon_enabled_complete')

        return True

    def disable_beacon(self, name):
        '''
        Disable a beacon
        '''

        self.opts['beacons'][name]['enabled'] = False

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacon_disabled_complete')

        return True
