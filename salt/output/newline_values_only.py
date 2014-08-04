# -*- coding: utf-8 -*-
'''
Display values only with simple data.
=================================

Example input 1::

    {
    'myminion': ["127.0.0.1", "10.0.0.1"],
    'second-minion': ["127.0.0.1", "10.0.0.2"]
    }

Example output 1::
    127.0.0.1
    10.0.0.1
    127.0.0.1
    10.0.0.2

Example input 2::

    {
    'myminion': 8,
    'second-minion': 10
    }

Example output 2::
    8
    10
'''


def get_values(data):
    # This should be able to be improved
    # by parsing kargs from command line
    # instantiation.
    # But I am not sure how to do it
    # just yet.
    # This would enable us to toggle
    # this functionality.
    values = []
    for _, minion_values in data.items():
        if isinstance(minion_values, list):
            values.extend(minion_values)
        else:
            values.append(minion_values)
    return values


def one_level_values(data):
    return '\n'.join(string_list(get_values(data)))


def string_list(a_list):
    return [str(item) for item in a_list]


def output(data):
    '''
    Rather basic....
    '''
    return one_level_values(data)
