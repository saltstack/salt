# -*- coding: utf-8 -*-
'''
Loop state

Allows for looping over execution modules.

.. code-block:: yaml

    wait_for_service_to_be_healthy:
      loop.until:
        - name: boto_elb.get_instance_health
        - condition: m_ret[0]['state'] == 'InService'
        - period: 5
        - timeout: 20
        - m_args:
          - {{ elb }}
        - m_kwargs:
            keyid: {{ access_key }}
            key: {{ secret_key }}
            instances: "{{ instance }}"
'''
from __future__ import absolute_import

# Import python libs
import logging
import time

# Import salt libs
import salt.utils

# Initialize logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'loop'

def __virtual__():
    return True

def until(name,
          m_args=None,
          m_kwargs=None,
          condition=None,
          period=None,
          timeout=None):
    '''
    Loop over an execution module until a condition is met.

    name
        The name of the execution module

    m_args
        The execution module's positional arguments

    m_kwargs
        The execution module's keyword arguments

    condition
        The condition which must be met for the loop to break. This
        should contain ``m_ret`` which is the return from the execution
        module.

    period
        The number of seconds to wait between executions

    timeout
        The timeout in seconds
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if name not in __salt__:
        ret['comment'] = "Can't find module {0}".format(name)
        return ret
    if condition is None:
        ret['comment'] = 'An exit condition must be specified'
        return ret
    try:
        period = int(period)
    except ValueError:
        ret['comment'] = 'Period must be specified in seconds'
    try:
        timeout = int(timeout)
    except ValueError:
        ret['comment'] = 'Timeout must be specified in seconds'

    def timed_out():
        if timeout is None:
            return False
        if time.time() >= timeout:
            return True
        return False

    timeout = time.time() + timeout

    while not timed_out():
        m_ret = __salt__[name](*m_args, **m_kwargs)
        if eval(condition):
            ret['result'] = True
            ret['comment'] = 'Condition {0} was met'.format(condition)
            return ret
        time.sleep(period)

    ret['comment'] = 'Timed out while waiting for condition {0}'.format(condition)
    return ret
