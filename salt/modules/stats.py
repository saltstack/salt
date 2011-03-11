'''
Module for returning statistics about a minion
'''
import subprocess

def uptime():
    '''
    Return the uptime for this minion
    '''
    return subprocess.Popen(['uptime'],
            stdout=subprocess.PIPE).communicate()[0]
