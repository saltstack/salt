'''
Module for viewing and modifying sysctl paramters
'''
import subprocess

def list():
    '''
    Return a list of sysctl parameters for this minion

    CLI Example:
    salt '*' sysctl.list
    '''
    cmd = 'sysctl -a'
    ret = {}
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        comps = line.split(' = ')
        ret[comps[0]] = comps[1]
    return ret
