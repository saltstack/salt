# -*- coding: utf-8 -*-
'''
Process Management
==================

Ensure a process matching a given pattern is absent.

.. code-block:: yaml

    httpd-absent:
      process.absent:
        - name: apache2
'''


def __virtual__():
    return 'process' if 'ps.pkill' in __salt__ else False


def absent(name):
    '''
    Ensures that the named command is not running.

    name
        The pattern to match.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        running = __salt__['ps.pgrep'](name)
        ret['result'] = None
        if running:
            ret['comment'] = '{0} processes will be killed'.format(len(running))
        else:
            ret['comment'] = 'No matching processes running'
        return ret

    status = __salt__['ps.pkill'](name, full=True)

    ret['result'] = True
    if status:
        ret['comment'] = 'Killed {0} processes'.format(len(status['killed']))
        ret['changes'] = status
    else:
        ret['comment'] = 'No matching processes running'
    return ret
