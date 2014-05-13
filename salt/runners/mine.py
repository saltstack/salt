# -*- coding: utf-8 -*-
'''
A runner to access data from the salt mine
'''

# Import salt libs
import salt.mine
import salt.output


def get(tgt, fun, tgt_type='glob'):
    '''
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type

    CLI Example::

        salt-run mine.get '*' network.interfaces
    '''
    ret = salt.mine.get(tgt, fun, tgt_type, __opts__)
    salt.output.display_output(ret, 'yaml', __opts__)
    return ret
