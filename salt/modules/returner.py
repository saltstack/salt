'''
Module to integrate with the returner system and retrive data sent to a salt
returner.
'''

# Import salt libs
import salt.loader


def get_jid(jid):
    '''
    Return the information for a specified job id

    CLI Example::

        salt '*' returner.get_jid 20421104181954700505
    '''
    returners = salt.loader.returners(__opts__, __salt__)
    return returners.get_jid(jid)


def get_fun(jid):
    '''
    Return the information for a specified job id

    CLI Example::

        salt '*' returner.get_fun network.interfaces
    '''
    returners = salt.loader.returners(__opts__, __salt__)
    return returners.get_fun(fun)
