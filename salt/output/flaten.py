# -*- coding: utf-8 -*-
'''
Display data
=================================

Example input::

    {'myminion':
        {'foo':
            {'list': ['Hello', 'World'],
            'bar': 'baz',
             'dictionary': {'abc': 123, 'def': 456}
             }
        }

    'second-minion':
        {'bar':
            {'list': ['Hello', 'World'],
            'bar': 'baz',
             'dictionary': {'abc': 123, 'def': 456}
             }
        }
    }


Example output::
    {'bar': 'baz', 'list': ['Hello', 'World'], 'dictionary': {'abc': 123, 'def': 456}}
    {'bar': 'baz', 'list': ['Hello', 'World'], 'dictionary': {'abc': 123, 'def': 456}}

'''


def string_list(a_list):
    return [str(item) for item in a_list]


def get_values(data):
    l = []
    items = data.values()
    for item in items:
        if isinstance(item, dict):
            l.extend(item.values())
        else:
            l.append(item)
    return l


def output(data):
    '''
    Rather basic....
    '''
    # return one_level_values(data)
    return '\n'.join(string_list(get_values(data)))
