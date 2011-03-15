'''
Module for returning statistics about a minion
'''
import subprocess

def uptime():
    '''
    Return the uptime for this minion

    CLI Example:
    salt '*' stats.uptime
    '''
    return subprocess.Popen(['uptime'],
            stdout=subprocess.PIPE).communicate()[0]
