# -*- coding: utf-8 -*-
'''
Test States
==================

Provide test case states that enable easy testing of things to do with
 state calls, e.g. running, calling, logging, output filtering etc.

.. code-block:: yaml

    always-passes:
      test.succeed_without_changes:
        - name: foo

    always-fails:
      test.fail_without_changes:
        - name: foo

    always-changes-and-succeeds:
      test.succeed_with_changes:
        - name: foo

    always-changes-and-fails:
      test.fail_with_changes:
        - name: foo

    my-custom-combo:
      test.configurable_test_state:
        - name: foo
        - changes: True
        - result: False
        - comment: bar.baz

'''

# Import Python libs
import logging
import random
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def succeed_without_changes(name):
    '''
    Returns successful.

    .. versionadded:: Helium

    name
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'This is just a test, nothing actually happened'
    }
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = (
            'Yo dawg I heard you like tests,'
            ' so I put tests in your tests,'
            ' so you can test while you test.'
        )
    return ret


def fail_without_changes(name):
    '''
    Returns failure.

    .. versionadded:: Helium

    name:
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': 'This is just a test, nothing actually happened'
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = (
            'Yo dawg I heard you like tests,'
            ' so I put tests in your tests,'
            ' so you can test while you test.'
        )

    return ret


def succeed_with_changes(name):
    '''
    Returns successful and changes is not empty

    .. versionadded:: Helium

    name:
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'This is just a test, nothing actually happened'
    }

    # Following the docs as written here
    # http://docs.saltstack.com/ref/states/writing.html#return-data
    ret['changes'] = {
        'testing': {
            'old': 'Nothing has changed yet',
            'new': 'Were pretending really hard that we changed something'
        }
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = (
            'Yo dawg I heard you like tests,'
            ' so I put tests in your tests,'
            ' so you can test while you test.'
        )

    return ret


def fail_with_changes(name):
    '''
    Returns failure and changes is not empty.

    .. versionadded:: Helium

    name:
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': 'This is just a test, nothing actually happened'
    }

    # Following the docs as written here
    # http://docs.saltstack.com/ref/states/writing.html#return-data
    ret['changes'] = {
        'testing': {
            'old': 'Nothing has changed yet',
            'new': 'Were pretending really hard that we changed something'
        }
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = (
            'Yo dawg I heard you like tests,'
            ' so I put tests in your tests,'
            ' so you can test while you test.'
        )

    return ret


def configurable_test_state(name, changes=True, result=True, comment=''):
    '''
    A configurable test state which determines its output based on the inputs.

    .. versionadded:: Helium

    name:
        A unique string.
    changes:
        Do we return anything in the changes field?
        Accepts True, False, and 'Random'
        Default is True
    result:
        Do we return sucessfuly or not?
        Accepts True, False, and 'Random'
        Default is True
    comment:
        String to fill the comment field with.
        Default is ''
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': comment
    }

    # E8712 is disabled because this code is a LOT cleaner if we allow it.
    if changes == "Random":
        if random.choice([True, False]):
            # Following the docs as written here
            # http://docs.saltstack.com/ref/states/writing.html#return-data
            ret['changes'] = {
            'testing': {
                'old': 'Nothing has changed yet',
                'new': 'Were pretending really hard that we changed something'
                }
            }
    elif changes == True:  # pylint: disable=E8712
        # If changes is True we place our dummy change dictionary into it.
        # Following the docs as written here
        # http://docs.saltstack.com/ref/states/writing.html#return-data
        ret['changes'] = {
        'testing': {
            'old': 'Nothing has changed yet',
            'new': 'Were pretending really hard that we changed something'
            }
        }
    elif changes == False:  # pylint: disable=E8712
        ret['changes'] = {}
    else:
        err = ('You have specified the state option \'Changes\' with'
            ' invalid arguments. It must be either '
            ' \'True\', \'False\', or \'Random\'')
        raise SaltInvocationError(err)

    if result == 'Random':
        # since result is a boolean, if its random we just set it here,
        ret['result'] = random.choice([True, False])
    elif result == True:  # pylint: disable=E8712
        ret['result'] = True
    elif result == False:  # pylint: disable=E8712
        ret['result'] = False
    else:
        raise SaltInvocationError('You have specified the state option \'Result\' with invalid arguments. '
                                  'It must be either \'True\', \'False\', or \'Random\'')

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = (
            'Yo dawg I heard you like tests, so I put tests in your tests, so you can test while you test.'
        )

    return ret
