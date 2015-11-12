# -*- coding: utf-8 -*-
"""
Utilities for comparing and updating configurations while keeping track of
changes in a way that can be easily reported in a state.
"""
from __future__ import absolute_import


def compare_and_update_config(config, update_config, changes, namespace=''):
    '''
    Recursively compare two configs, writing any needed changes to the
    update_config and capturing changes in the changes dict.
    '''
    if isinstance(config, dict):
        if not update_config:
            if config:
                # the updated config is more valid--report that we are using it
                changes[namespace] = {
                    'new': config,
                    'old': update_config,
                }
            return config
        elif not isinstance(update_config, dict):
            # new config is a dict, other isn't--new one wins
            changes[namespace] = {
                'new': config,
                'old': update_config,
            }
            return config
        else:
            # compare each key in the base config with the values in the
            # update_config, overwriting the values that are different but
            # keeping any that are not defined in config
            for key, value in config.iteritems():
                _namespace = key
                if namespace:
                    _namespace = '{0}.{1}'.format(namespace, _namespace)
                update_config[key] = compare_and_update_config(
                    value,
                    update_config.get(key, None),
                    changes,
                    namespace=_namespace,
                )
            return update_config

    elif isinstance(config, list):
        if not update_config:
            if config:
                # the updated config is more valid--report that we are using it
                changes[namespace] = {
                    'new': config,
                    'old': update_config,
                }
            return config
        elif not isinstance(update_config, list):
            # new config is a list, other isn't--new one wins
            changes[namespace] = {
                'new': config,
                'old': update_config,
            }
            return config
        else:
            # iterate through config list, ensuring that each index in the
            # update_config list is the same
            for idx, item in enumerate(config):
                _namespace = '[{0}]'.format(idx)
                if namespace:
                    _namespace = '{0}{1}'.format(namespace, _namespace)
                _update = None
                if len(update_config) > idx:
                    _update = update_config[idx]
                if _update:
                    update_config[idx] = compare_and_update_config(
                        config[idx],
                        _update,
                        changes,
                        namespace=_namespace,
                    )
                else:
                    changes[_namespace] = {
                        'new': config[idx],
                        'old': _update,
                    }
                    update_config.append(config[idx])

            if len(update_config) > len(config):
                # trim any items in update_config that are not in config
                for idx, old_item in enumerate(update_config):
                    if idx < len(config):
                        continue
                    _namespace = '[{0}]'.format(idx)
                    if namespace:
                        _namespace = '{0}{1}'.format(namespace, _namespace)
                    changes[_namespace] = {
                        'new': None,
                        'old': old_item,
                    }
                del update_config[len(config):]
            return update_config

    else:
        if config != update_config:
            changes[namespace] = {
                'new': config,
                'old': update_config,
            }
        return config
