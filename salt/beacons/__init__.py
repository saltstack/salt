# -*- coding: utf-8 -*-
'''
This package contains the loader modules for the salt streams system
'''
# Import Python libs
from __future__ import absolute_import
import logging
import copy
import re

# Import Salt libs
import salt.loader
import salt.utils
import salt.utils.minion
from salt.ext.six.moves import map
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


class Beacon(object):
    '''
    This class is used to evaluate and execute on the beacon system
    '''
    def __init__(self, opts, functions):
        self.opts = opts
        self.functions = functions
        self.beacons = salt.loader.beacons(opts, functions)
        self.interval_map = dict()

    def process(self, config, grains):
        '''
        Process the configured beacons

        The config must be a list and looks like this in yaml

        .. code_block:: yaml
            beacons:
              inotify:
                - /etc/fstab: {}
                - /var/cache/foo: {}
        '''
        ret = []
        b_config = copy.deepcopy(config)
        if 'enabled' in b_config and not b_config['enabled']:
            return
        for mod in config:
            if mod == 'enabled':
                continue

            # Convert beacons that are lists to a dict to make processing easier
            current_beacon_config = None
            if isinstance(config[mod], list):
                current_beacon_config = {}
                list(map(current_beacon_config.update, config[mod]))
            elif isinstance(config[mod], dict):
                raise CommandExecutionError(
                    'Beacon configuration should be a list instead of a dictionary.'
                )

            if 'enabled' in current_beacon_config:
                if not current_beacon_config['enabled']:
                    log.trace('Beacon {0} disabled'.format(mod))
                    continue
                else:
                    # remove 'enabled' item before processing the beacon
                    if isinstance(config[mod], dict):
                        del config[mod]['enabled']
                    else:
                        self._remove_list_item(config[mod], 'enabled')

            log.trace('Beacon processing: {0}'.format(mod))
            fun_str = '{0}.beacon'.format(mod)
            if fun_str in self.beacons:
                runonce = self._determine_beacon_config(current_beacon_config, 'run_once')
                interval = self._determine_beacon_config(current_beacon_config, 'interval')
                if interval:
                    b_config = self._trim_config(b_config, mod, 'interval')
                    if not self._process_interval(mod, interval):
                        log.trace('Skipping beacon {0}. Interval not reached.'.format(mod))
                        continue
                if self._determine_beacon_config(current_beacon_config, 'disable_during_state_run'):
                    log.trace('Evaluting if beacon {0} should be skipped due to a state run.'.format(mod))
                    b_config = self._trim_config(b_config, mod, 'disable_during_state_run')
                    is_running = False
                    running_jobs = salt.utils.minion.running(self.opts)
                    for job in running_jobs:
                        if re.match('state.*', job['fun']):
                            is_running = True
                    if is_running:
                        close_str = '{0}.close'.format(mod)
                        if close_str in self.beacons:
                            log.info('Closing beacon {0}. State run in progress.'.format(mod))
                            self.beacons[close_str](b_config[mod])
                        else:
                            log.info('Skipping beacon {0}. State run in progress.'.format(mod))
                        continue
                # Update __grains__ on the beacon
                self.beacons[fun_str].__globals__['__grains__'] = grains
                # Fire the beacon!
                raw = self.beacons[fun_str](b_config[mod])
                for data in raw:
                    tag = 'salt/beacon/{0}/{1}/'.format(self.opts['id'], mod)
                    if 'tag' in data:
                        tag += data.pop('tag')
                    if 'id' not in data:
                        data['id'] = self.opts['id']
                    ret.append({'tag': tag, 'data': data})
                if runonce:
                    self.disable_beacon(mod)
            else:
                log.warning('Unable to process beacon {0}'.format(mod))
        return ret

    def _trim_config(self, b_config, mod, key):
        '''
        Take a beacon configuration and strip out the interval bits
        '''
        if isinstance(b_config[mod], list):
            self._remove_list_item(b_config[mod], key)
        elif isinstance(b_config[mod], dict):
            b_config[mod].pop(key)
        return b_config

    def _determine_beacon_config(self, current_beacon_config, key):
        '''
        Process a beacon configuration to determine its interval
        '''

        interval = False
        if isinstance(current_beacon_config, dict):
            interval = current_beacon_config.get(key, False)

        return interval

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

    def _get_index(self, beacon_config, label):
        '''
        Return the index of a labeled config item in the beacon config, -1 if the index is not found
        '''

        indexes = [index for index, item in enumerate(beacon_config) if label in item]
        if len(indexes) < 1:
            return -1
        else:
            return indexes[0]

    def _remove_list_item(self, beacon_config, label):
        '''
        Remove an item from a beacon config list
        '''

        index = self._get_index(beacon_config, label)
        del beacon_config[index]

    def _update_enabled(self, name, enabled_value):
        '''
        Update whether an individual beacon is enabled
        '''

        if isinstance(self.opts['beacons'][name], dict):
            # Backwards compatibility
            self.opts['beacons'][name]['enabled'] = enabled_value
        else:
            enabled_index = self._get_index(self.opts['beacons'][name], 'enabled')
            if enabled_index >= 0:
                self.opts['beacons'][name][enabled_index]['enabled'] = enabled_value
            else:
                self.opts['beacons'][name].append({'enabled': enabled_value})

    def list_beacons(self):
        '''
        List the beacon items
        '''
        # Fire the complete event back along with the list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        b_conf = self.functions['config.merge']('beacons')
        self.opts['beacons'].update(b_conf)
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

        self._update_enabled(name, True)

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacon_enabled_complete')

        return True

    def disable_beacon(self, name):
        '''
        Disable a beacon
        '''

        self._update_enabled(name, False)

        # Fire the complete event back along with updated list of beacons
        evt = salt.utils.event.get_event('minion', opts=self.opts)
        evt.fire_event({'complete': True, 'beacons': self.opts['beacons']},
                       tag='/salt/minion/minion_beacon_disabled_complete')

        return True
