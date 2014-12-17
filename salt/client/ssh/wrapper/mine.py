'''
Wrapper function for mine operations for salt-ssh

.. versionadded:: Lithium
'''

def get(tgt, fun, expr_form='glob', roster='flat'):
    '''
    Get data from the mine based on the target, function and expr_form

    This is basically a wrapper around publish.publish, as salt-ssh clients
    can't update the mine themselves.

    Targets can be matched based on any standard matching system that can be
    matched on the defined roster (in salt-ssh) via these keywords::

    CLI Example:

    .. code-block:: bash

        salt-ssh '*' mine.get '*' network.interfaces
        salt-ssh '*' mine.get 'myminion' network.interfaces roster=flat
        salt-ssh '*' mine.get '192.168.5.0' network.ipaddrs roster=scan
    '''
    return __salt__['publish.publish'](tgt,
                                       fun,
                                       expr_form=expr_form,
                                       roster=roster)
