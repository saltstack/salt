# -*- coding: utf-8 -*-
'''
Test States
==================

Provide test case states that enable easy testing of things to do with
 state calls, e.g. running, calling, logging, output filtering etc.

.. code-block:: yaml

    always-passes-with-any-kwarg:
      test.nop:
        - name: foo
        - something: else
        - foo: bar

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
from __future__ import absolute_import

# Import Python libs
import logging
import random
from salt.state import _gen_tag
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def nop(name, **kwargs):
    '''
    A no-op state that does nothing. Useful in conjunction with the `use`
    requisite, or in templates which could otherwise be empty due to jinja
    rendering

    .. versionadded:: 2015.5.6
    '''
    return succeed_without_changes(name)


def succeed_without_changes(name):
    '''
    Returns successful.

    .. versionadded:: 2014.7.0

    name
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Success!'
    }
    return ret


def fail_without_changes(name):
    '''
    Returns failure.

    .. versionadded:: 2014.7.0

    name:
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': 'Failure!'
    }

    if __opts__['test']:
        ret['result'] = False
        ret['comment'] = 'If we weren\'t testing, this would be a failure!'

    return ret


def succeed_with_changes(name):
    '''
    Returns successful and changes is not empty

    .. versionadded:: 2014.7.0

    name:
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Success!'
    }

    # Following the docs as written here
    # http://docs.saltstack.com/ref/states/writing.html#return-data
    ret['changes'] = {
        'testing': {
            'old': 'Unchanged',
            'new': 'Something pretended to change'
        }
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('If we weren\'t testing, this would be successful '
                          'with changes')

    return ret


def fail_with_changes(name):
    '''
    Returns failure and changes is not empty.

    .. versionadded:: 2014.7.0

    name:
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': 'Failure!'
    }

    # Following the docs as written here
    # http://docs.saltstack.com/ref/states/writing.html#return-data
    ret['changes'] = {
        'testing': {
            'old': 'Unchanged',
            'new': 'Something pretended to change'
        }
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('If we weren\'t testing, this would be failed with '
                          'changes')

    return ret


def configurable_test_state(name, changes=True, result=True, comment=''):
    '''
    A configurable test state which determines its output based on the inputs.

    .. versionadded:: 2014.7.0

    name:
        A unique string.
    changes:
        Do we return anything in the changes field?
        Accepts True, False, and 'Random'
        Default is True
    result:
        Do we return successfully or not?
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

    if changes == 'Random':
        if random.choice([True, False]):
            # Following the docs as written here
            # http://docs.saltstack.com/ref/states/writing.html#return-data
            ret['changes'] = {
                'testing': {
                    'old': 'Unchanged',
                    'new': 'Something pretended to change'
                }
            }
    elif changes is True:
        # If changes is True we place our dummy change dictionary into it.
        # Following the docs as written here
        # http://docs.saltstack.com/ref/states/writing.html#return-data
        ret['changes'] = {
            'testing': {
                'old': 'Unchanged',
                'new': 'Something pretended to change'
            }
        }
    elif changes is False:
        ret['changes'] = {}
    else:
        err = ('You have specified the state option \'Changes\' with'
            ' invalid arguments. It must be either '
            ' \'True\', \'False\', or \'Random\'')
        raise SaltInvocationError(err)

    if result == 'Random':
        # since result is a boolean, if its random we just set it here,
        ret['result'] = random.choice([True, False])
    elif result is True:
        ret['result'] = True
    elif result is False:
        ret['result'] = False
    else:
        raise SaltInvocationError('You have specified the state option '
                                  '\'Result\' with invalid arguments. It must '
                                  'be either \'True\', \'False\', or '
                                  '\'Random\'')

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'This is a test'

    return ret


def mod_watch(name, sfun=None, **kwargs):
    ''''
    Call this function via a watch statement

    .. versionadded:: 2014.7.0

    Any parameters in the state return dictionary can be customized by adding
    the keywords ``result``, ``comment``, and ``changes``.

    .. code-block:: yaml

        this_state_will_return_changes:
          test.succeed_with_changes

        this_state_will_NOT_return_changes:
          test.succeed_without_changes

        this_state_is_watching_another_state:
          test.succeed_without_changes:
            - comment: 'This is a custom comment'
            - watch:
              - test: this_state_will_return_changes
              - test: this_state_will_NOT_return_changes

        this_state_is_also_watching_another_state:
          test.succeed_without_changes:
            - watch:
              - test: this_state_will_NOT_return_changes
    '''
    has_changes = []
    for req in __low__['__reqs__']['watch']:
        tag = _gen_tag(req)
        if __running__[tag]['changes']:
            has_changes.append('{state}: {__id__}'.format(**req))

    ret = {
        'name': name,
        'result': kwargs.get('result', True),
        'comment': kwargs.get('comment', 'Watch statement fired.'),
        'changes': kwargs.get('changes', {
            'Requisites with changes': has_changes,
        }),
    }
    return ret
