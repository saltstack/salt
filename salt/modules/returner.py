'''
Module to integrate with the returner system and retrieve data sent to a salt
returner.
'''

# Import salt libs
import salt.loader


def get_jid(returner, jid):
    '''
    Return the information for a specified job id

    CLI Example::

        salt '*' returner.get_jid redis 20421104181954700505
    '''
    returners = salt.loader.returners(__opts__, __salt__)
    return returners['{0}.get_jid'.format(returner)](jid)


def get_fun(returner, fun):
    '''
    Return the information for a specified job id

    CLI Example::

        salt '*' returner.get_fun network.interfaces
    '''
    returners = salt.loader.returners(__opts__, __salt__)
    return returners['{0}.get_fun'.format(returner)](fun)
