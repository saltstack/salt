# -*- coding: utf-8 -*-
'''
Used to manage the thorium register. The thorium register is where compound
values are stored and computed, such as averages etc.

.. versionadded:: Carbon

:depends: statistics PyPi module
'''

# import python libs
from __future__ import absolute_import

try:
    import statistics
    HAS_STATS = True
except ImportError:
    HAS_STATS = False


def __virtual__():
    '''
    The statistics module must be pip installed
    '''
    return HAS_STATS


def calc(name, num, oper, minimum=0, maximum=0, ref=None):
    '''
    Perform a calculation on the ``num`` most recent values. Requires a list.
    Valid values for ``oper`` are:

      - add: Add last ``num`` values together
      - mul: Multiple last ``num`` values together
      - mean: Calculate mean of last ``num`` values
      - median: Calculate median of last ``num`` values
      - median_low: Calculate low median of last ``num`` values
      - median_high: Calculate high median of last ``num`` values
      - median_grouped: Calculate grouped median of last ``num`` values
      - mode: Calculate mode of last ``num`` values


    USAGE::

    code-block:: yaml

        foo:
          reg.calc:
            - name: myregentry
            - num: 5
            - oper: mean
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if name not in __reg__:
        ret['comment'] = '{0} not found in register'.format(name)
        ret['result'] = False

    def opadd(vals):
        sum = 0
        for val in vals:
            sum = sum + val
        return sum

    def opmul(vals):
        prod = 0
        for val in vals:
            prod = prod * val
        return prod

    ops = {
        'add': opadd,
        'mul': opmul,
        'mean': statistics.mean,
        'median': statistics.median,
        'median_low': statistics.median_low,
        'median_high': statistics.median_high,
        'median_grouped': statistics.median_grouped,
        'mode': statistics.mode,
    }

    count = 0
    vals = []
    __reg__[name]['val'].reverse()
    for regitem in __reg__[name]['val']:
        count += 1
        if count > num:
            break
        if ref is None:
            vals.append(regitem)
        else:
            vals.append(regitem[ref])

    answer = ops[oper](vals)

    if minimum > 0 and answer < minimum:
        ret['result'] = False

    if maximum > 0 and answer > maximum:
        ret['result'] = False

    ret['changes'] = {
        'Number of values': len(vals),
        'Operator': oper,
        'Answer': answer,
    }
    return ret


def add(name, num, minimum=0, maximum=0, ref=None):
    '''
    Adds together the ``num`` most recent values. Requires a list.

    USAGE::

    code-block:: yaml

        foo:
          reg.add:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'add', ref)


def mul(name, num, minimum=0, maximum=0, ref=None):
    '''
    Multiplies together the ``num`` most recent values. Requires a list.

    USAGE::

    code-block:: yaml

        foo:
          reg.mul:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'mul', ref)


def mean(name, num, minimum=0, maximum=0, ref=None):
    '''
    Calculates the mean of the ``num`` most recent values. Requires a list.

    USAGE::

    code-block:: yaml

        foo:
          reg.mean:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'mean', ref)


def median(name, num, minimum=0, maximum=0, ref=None):
    '''
    Calculates the mean of the ``num`` most recent values. Requires a list.

    USAGE::

    code-block:: yaml

        foo:
          reg.median:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'median', ref)


def median_low(name, num, minimum=0, maximum=0, ref=None):
    '''
    Calculates the low mean of the ``num`` most recent values. Requires a list.

    USAGE::

    code-block:: yaml

        foo:
          reg.median_low:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'median_low', ref)


def median_high(name, num, minimum=0, maximum=0, ref=None):
    '''
    Calculates the high mean of the ``num`` most recent values. Requires a list.

    USAGE::

    code-block:: yaml

        foo:
          reg.median_high:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'median_high', ref)


def median_grouped(name, num, minimum=0, maximum=0, ref=None):
    '''
    Calculates the grouped mean of the ``num`` most recent values. Requires a
    list.

    USAGE::

    code-block:: yaml

        foo:
          reg.median_grouped:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'median_grouped', ref)


def mode(name, num, minimum=0, maximum=0, ref=None):
    '''
    Calculates the mode of the ``num`` most recent values. Requires a list.

    USAGE::

    code-block:: yaml

        foo:
          reg.mode:
            - name: myregentry
            - num: 5
    '''
    return calc(name, num, 'mode', ref)
