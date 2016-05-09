# -*- coding: utf-8 -*-
'''
Manage ufw rules.

.. versionadded:: #TODO ??

Todo: Add absent state. --dry-run doesn't work with delete, so the module would
have to parse the output of 'ufw status' or 'ufw show added' in order to know
which rules are present.
'''

# This state is an edit of Publysher Blog ufw state:
# (https://github.com/publysher/infra-example-nginx/tree/develop)

# The MIT License (MIT)
#
# Original work Copyright (c) 2013 publysher
# Modified work Copyright 2016 Alpha Ledger LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import logging

log = logging.getLogger(__name__)

def __virtual__():
    # Only load if the ufw module is available
    if 'ufw.add_rule' not in __salt__:
        return False, 'ufw module wasn\'t loaded'
    return 'ufw_rule'

def present(name, action, protocol=None,
            to_port=None, to_addr='any',
            from_port=None, from_addr='any',
            direction='in', interface=None):
    '''
    Add an UFW rule.

    .. code-block:: yaml

        allow ssh from anywhere:
          ufw_rule.present:
            - action: allow
            - protocol: tcp
            - to_port: 22
    '''
    ret = {'name': name, 'result': True, 'comment': None, 'changes': {}}

    cmd_args = [action, protocol, to_port, to_addr, from_port, from_addr, direction, interface]

    test_result = __salt__['ufw.add_rule'](*cmd_args, test=True)
    log.debug('Dry run result: {0}'.format(test_result))
    changes = []
    for line in test_result.split('\n'):
        if line.startswith('Rules added') or line.startswith('Rules updated'):
            changes.append(line)

    if len(changes) == 0:
        ret['comment'] = 'No changes'
        return ret
    ret['changes']['rule'] = '\n'.join(changes)

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Will update rules'
        return ret

    __salt__['ufw.add_rule'](*cmd_args)
    return ret
