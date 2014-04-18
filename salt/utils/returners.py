'''
Helper functions for returners
'''


def valid_jid(jid, returners, mminion):
    '''
    Return boolean of wether this jid exists in any of the returners passed in
    '''
    valid_jid = False
    for returner in returners:
        if mminion.returners['{0}.get_load'.format(returner)](jid) != {}:
            valid_jid = True
            break
    return valid_jid


