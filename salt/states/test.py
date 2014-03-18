# -*- coding: utf-8 -*-
'''
Test States
==================

Provide test case states that enable easy testing of things to do with state calls, e.g. running, calling, logging, output filtering etc.

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

log = logging.getLogger(__name__)


def succeed_without_changes(name):
    '''
    Returns successful.

    name
        A unique string.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    return ret

def fail_without_changes(name):
    '''
    Returns failure.

    name:
        A unique string.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    return ret

def succeed_with_changes(name):
    '''
    Returns successful and changes is not empty

    name:
        A unique string.
    '''
    ret = {'name': name,
           'changes': {'Some virtual particles appeared then dissapeared.'},
           'result': True,
           'comment': ''}
    return ret

def fail_with_changes(name):
    '''
    Returns failure and changes is not empty.

    name:
        A unique string.
    '''
    ret = {'name': name,
           'changes': {'Some virtual particles appeared then dissapeared.'},
           'result': False,
           'comment': ''}
    return ret

def configurable_test_state(name, changes, result, comment):
    '''
    A configurable test state which determines its output based on the inputs.

    name:
        A unique string.
    changes:
        Do we return anything in the changes field? Accepts True, False, and 'Random'
    result:
        Do we return sucessfuly or not? Accepts True, False, and 'Random'
    comment:
        String to fill the comment field with.
    '''

    outcomes = [True, False]

    #check if they requested anything to be random first to keep things simple
    if changes == 'Random':
        changes = random.choice(outcomes)
    if result == 'Random':
        result = random.choice(outcomes)

    if changes:
        changes_content = {'Some virtual particles appeared then dissapeared.'}
    else:
        changes_content = {}

    if result:
        result_bool = True
    else:
        result_bool = False

    # ensure the name and comment are strings
    name = str(name)
    comment = str(comment)

    ret = {'name': name,
           'changes': changes_content,
           'result': result_bool,
           'comment': comment}
    return ret
