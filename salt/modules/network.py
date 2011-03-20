'''
Module for gathering and managing network information
'''
import subprocess

def ping( host ):
    '''
    Return usage information for volumes mounted on this minion
    
    CLI Example:
    salt '*' network.ping archlinux.org -c 4
    '''
    cmd = 'ping -c 4 %s' % host

    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]
    return out

def netstat():
    '''
    Return information on open ports and states
    
    CLI Example:
    salt '*' network.netstat
    '''
    cmd = 'netstat -tulpnea'
    ret = []
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        comps = line.split()
        if line.startswith('tcp'):
            ret.append( {
                'proto':          comps[0],
                'recv-q':         comps[1],
                'send-q':         comps[2],
                'local-address':  comps[3],
                'remote-address': comps[4],
                'state':          comps[5],
                'user':           comps[6],
                'inode':          comps[7],
                'program':        comps[8],
            } )
        if line.startswith('udp'):
            ret.append( {
                'proto':          comps[0],
                'recv-q':         comps[1],
                'send-q':         comps[2],
                'local-address':  comps[3],
                'remote-address': comps[4],
                'user':           comps[5],
                'inode':          comps[6],
                'program':        comps[7],
            } )
    return ret

def traceroute( host ):
    '''
    Performs a traceroute to a 3rd party host
    
    CLI Example:
    salt '*' network.traceroute archlinux.org
    '''
    cmd = 'traceroute %s' % host
    ret = []
    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    for line in out:
        if not line.count(' '):
            continue
        if line.startswith('traceroute'):
            continue
        comps = line.split()
        result = {
            'count':    comps[0],
            'hostname': comps[1],
            'ip':       comps[2],
            'ping1':    comps[3],
            'ms1':      comps[4],
            'ping2':    comps[5],
            'ms2':      comps[6],
            'ping3':    comps[7],
            'ms3':      comps[8],
        }
        ret.append(result)
    return ret

def dig( host ):
    '''
    Return usage information for volumes mounted on this minion
    
    CLI Example:
    salt '*' network.dig archlinux.org
    '''
    cmd = 'dig %s' % host

    out = subprocess.Popen(cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]
    return out

def isportopen( port ):
    '''
    Return usage information for volumes mounted on this minion
    
    CLI Example:
    salt '*' network.isportopen 22
    '''
    cmd = 'nc -zv localhost %s' % port

    out = subprocess.Popen(cmd,
            shell=True,
            stderr=subprocess.PIPE).communicate()[1]
    return out

