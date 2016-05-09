# -*- coding: utf-8 -*-
'''
Manage ufw status.

.. versionadded:: #TODO ??
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
    if 'ufw.is_enabled' not in __salt__:
        return False, 'ufw module wasn\'t loaded'
    return 'ufw_status'

def enabled(name, enable):
    '''
    Ensure ufw is active or inactive, according to `enable`.

    .. code-block:: yaml

        enable ufw:
          ufw_status.enabled:
            - enable: True

    name
        Unused

    enable
        True to activate ufw, False otherwise
    '''
    ret = {'name': name, 'result': True, 'comment': 'Status unchanged', 'changes': {}}

    if not isinstance(enable, bool):
        ret['result'] = False
        ret['comment'] = 'enabled must be a bool, got {0}'.format(enabled)
        return ret

    if __salt__['ufw.is_enabled']() == enable:
        log.debug('Skipping, ufw.is_enabled == {0}'.format(enable))
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Status will change'
        return ret

    __salt__['ufw.set_enabled'](enable)
    ret['changes'][name] = 'Enabled: {0}'.format(enable)
    return ret
