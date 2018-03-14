# -*- coding: utf-8 -*-
'''
States for solrcloud alias and collection configuration

.. versionadded:: 2017.7.0

'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt libs
import salt.utils.json

# Import 3rd party libs
from salt.ext import six


def alias(name, collections, **kwargs):
    '''
    Create alias and enforce collection list.

    Use the solrcloud module to get alias members and set them.

    You can pass additional arguments that will be forwarded to http.query

    name
        The collection name
    collections
        list of collections to include in the alias
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': '',
        'pchanges': {},
    }

    if __salt__["solrcloud.alias_exists"](name, **kwargs):
        alias_content = __salt__['solrcloud.alias_get_collections'](name, **kwargs)
        diff = set(alias_content).difference(set(collections))

        if len(diff) == 0:
            ret['result'] = True
            ret['comment'] = 'Alias is in desired state'
            return ret

        if __opts__['test']:
            ret['comment'] = 'The alias "{0}" will be updated.'.format(name)
            ret['pchanges'] = {
                'old': ",".join(alias_content),
                'new': ",".join(collections)
            }
            ret['result'] = None
        else:
            __salt__["solrcloud.alias_set_collections"](name, collections, **kwargs)
            ret['comment'] = 'The alias "{0}" has been updated.'.format(name)
            ret['changes'] = {
                'old': ",".join(alias_content),
                'new': ",".join(collections)
            }

            ret['result'] = True
    else:
        if __opts__['test']:
            ret['comment'] = 'The alias "{0}" will be created.'.format(name)
            ret['pchanges'] = {
                'old': None,
                'new': ",".join(collections)
            }
            ret['result'] = None
        else:
            __salt__["solrcloud.alias_set_collections"](name, collections, **kwargs)
            ret['comment'] = 'The alias "{0}" has been created.'.format(name)
            ret['changes'] = {
                'old': None,
                'new': ",".join(collections)
            }

            ret['result'] = True

    return ret


def collection(name, options=None, **kwargs):
    '''
    Create collection and enforce options.

    Use the solrcloud module to get collection parameters.

    You can pass additional arguments that will be forwarded to http.query

    name
        The collection name
    options : {}
        options to ensure
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': '',
        'pchanges': {},
    }

    if options is None:
        options = {}

    if __salt__["solrcloud.collection_exists"](name, **kwargs):

        diff = {}

        current_options = __salt__["solrcloud.collection_get_options"](name, **kwargs)

        # Filter options that can be updated
        updatable_options = [
            "maxShardsPerNode",
            "replicationFactor",
            "autoAddReplicas",
            "collection.configName",
            "rule",
            "snitch"]

        options = [k for k in six.iteritems(options) if k in updatable_options]

        for key, value in options:
            if key not in current_options or current_options[key] != value:
                diff[key] = value

        if len(diff) == 0:
            ret['result'] = True
            ret['comment'] = 'Collection options are in desired state'
            return ret

        else:

            if __opts__['test']:
                ret['comment'] = 'Collection options "{0}" will be changed.'.format(name)
                ret['pchanges'] = {
                    'old': salt.utils.json.dumps(current_options, sort_keys=True, indent=4, separators=(',', ': ')),
                    'new': salt.utils.json.dumps(options, sort_keys=True, indent=4, separators=(',', ': '))
                }
                ret['result'] = None

                return ret
            else:
                __salt__["solrcloud.collection_set_options"](name, diff, **kwargs)

                ret['comment'] = 'Parameters were updated for collection "{0}".'.format(name)
                ret['result'] = True
                ret['changes'] = {
                    'old': salt.utils.json.dumps(current_options, sort_keys=True, indent=4, separators=(',', ': ')),
                    'new': salt.utils.json.dumps(options, sort_keys=True, indent=4, separators=(',', ': '))
                }

                return ret

    else:
        new_changes = salt.utils.json.dumps(options, sort_keys=True, indent=4, separators=(',', ': '))
        if __opts__['test']:
            ret['comment'] = 'The collection "{0}" will be created.'.format(name)
            ret['pchanges'] = {
                'old': None,
                'new': str('options=') + new_changes  # future lint: disable=blacklisted-function
            }
            ret['result'] = None
        else:
            __salt__["solrcloud.collection_create"](name, options, **kwargs)
            ret['comment'] = 'The collection "{0}" has been created.'.format(name)
            ret['changes'] = {
                'old': None,
                'new': str('options=') + new_changes  # future lint: disable=blacklisted-function
            }

            ret['result'] = True

    return ret
