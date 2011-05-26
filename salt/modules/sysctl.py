'''
Module for viewing and modifying sysctl parameters
'''
import subprocess

def show():
    '''
    Return a list of sysctl parameters for this minion

    CLI Example:
    salt '*' sysctl.show
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

def get(name):
    '''
    Return a single sysctl parameter for this minion

    CLI Example:
    salt '*' sysctl.get net.ipv4.ip_forward
    '''
    cmd = 'sysctl -n %s' % name
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]
    return out[0]

def assign(name, value):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example:
    salt '*' sysctl.assign net.ipv4.ip_forward 1
    '''
    cmd = 'sysctl -w %s=%s' % ( name, value )
    ret = {}
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].strip()
    comps = out.split(' = ')
    ret[comps[0]] = comps[1]
    return ret
