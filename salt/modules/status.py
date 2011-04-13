'''
Module for returning various status data about a minion.
These data can be useful for compiling into stats later.
'''
import subprocess

__opts__ = {}

def custom():
    ''' 
    Return a custom composite of status data and info for this minon,
    based on the minion config file. An example config like might be:

    status.cpustats.custom: [ 'cpu', 'ctxt', 'btime', 'processes' ]

    ...where status refers to status.py, cpustats is the function
    where we get our data, and custom is this function It is followed
    by a list of keys that we want returned.

    This function is meant to replace all_status(), which returns
    anything and everything, which we probably don't want.
    
    By default, nothing is returned. Warning: Depending on what you
    include, there can be a LOT here!

    CLI Example:
    salt '*' status.custom
    '''

    ret = {}
    for opt in __opts__:
        keys = opt.split('.')
        if keys[0] != 'status':
            continue
        func = '%s()' % keys[1]
        vals = eval(func)

        for item in __opts__[opt]:
            ret[item] = vals[item]

    return ret 

def uptime():
    '''
    Return the uptime for this minion

    CLI Example:
    salt '*' status.uptime
    '''
    return subprocess.Popen(['uptime'],
            stdout=subprocess.PIPE).communicate()[0].strip()

def loadavg():
    '''
    Return the load averages for this minion

    CLI Example:
    salt '*' status.loadavg
    '''
    comps = open('/proc/loadavg', 'r').read().strip()
    load_avg = comps.split()
    return { 
        '1-min':  load_avg[1],
        '5-min':  load_avg[2],
        '15-min': load_avg[3],
    }

def cpustats():
    '''
    Return the CPU stats for this minon

    CLI Example:
    salt '*' status.cpustats
    '''
    stats = open('/proc/stat', 'r').read().split('\n')
    ret = {}
    for line in stats:
        if not line.count(' '):
            continue
        comps = line.split()
        if comps[0] == 'cpu':
            ret[comps[0]] = {
                'user':    comps[1],
                'nice':    comps[2],
                'system':  comps[3],
                'idle':    comps[4],
                'iowait':  comps[5],
                'irq':     comps[6],
                'softirq': comps[7],
                'steal':   comps[8],
            }
        elif comps[0] == 'intr':
            ret[comps[0]] = {
                'total': comps[1],
                'irqs' : comps[2:],
            }
        elif comps[0] == 'softirq':
            ret[comps[0]] = {
                'total':    comps[1],
                'softirqs': comps[2:],
            }
        else:
            ret[comps[0]] = comps[1]
    return ret

def meminfo():
    '''
    Return the CPU stats for this minon

    CLI Example:
    salt '*' status.meminfo
    '''
    stats = open('/proc/meminfo', 'r').read().split('\n')
    ret = {}
    for line in stats:
        if not line.count(' '):
            continue
        comps = line.split()
        comps[0] = comps[0].replace(':', '')
        ret[comps[0]] = {
            'value':    comps[1],
        }
        if len(comps) > 2:
            ret[comps[0]]['unit'] = comps[2]
    return ret

def cpuinfo():
    ''' 
    Return the CPU info for this minon

    CLI Example:
    salt '*' status.cpuinfo
    '''
    stats = open('/proc/cpuinfo', 'r').read().split('\n')
    ret = {}
    for line in stats:
        if not line.count(' '):
            continue
        comps = line.split(':')
        comps[0] = comps[0].strip()
        if comps[0] == 'flags':
            ret[comps[0]] = comps[1].split()
        else:
            ret[comps[0]] = comps[1].strip()
    return ret 

def diskstats():
    '''
    Return the disk stats for this minon

    CLI Example:
    salt '*' status.diskstats
    '''
    stats = open('/proc/diskstats', 'r').read().split('\n')
    ret = {}
    for line in stats:
        if not line.count(' '):
            continue
        comps = line.split()
        ret[comps[2]] = {
            'major':                   comps[0],
            'minor':                   comps[1],
            'device':                  comps[2],
            'reads_issued':            comps[3],
            'reads_merged':            comps[4],
            'sectors_read':            comps[5],
            'ms_spent_reading':        comps[6],
            'writes_completed':        comps[7],
            'writes_merged':           comps[8],
            'sectors_written':         comps[9],
            'ms_spent_writing':        comps[10],
            'io_in_progress':          comps[11],
            'ms_spent_in_io':          comps[12],
            'weighted_ms_spent_in_io': comps[13],
        }
    return ret

def vmstats():
    '''
    Return the virtual memory stats for this minon

    CLI Example:
    salt '*' status.vmstats
    '''
    stats = open('/proc/vmstat', 'r').read().split('\n')
    ret = {}
    for line in stats:
        if not line.count(' '):
            continue
        comps = line.split()
        ret[comps[0]] = comps[1]
    return ret

def netstats():
    ''' 
    Return the network stats for this minon

    CLI Example:
    salt '*' status.netstats
    '''
    stats = open('/proc/net/netstat', 'r').read().split('\n')
    ret = {}
    headers = ['']
    for line in stats:
        if not line.count(' '):
            continue
        comps = line.split()
        if comps[0] == headers[0]:
            index = len(headers) - 1 
            row = {}
            for field in range(index):
                if field < 1:
                    continue
                else:
                    row[headers[field]] = comps[field]
            rowname = headers[0].replace(':', '') 
            ret[rowname] = row 
        else:
            headers = comps
    return ret 

def netdev():
    '''
    Return the network device stats for this minon

    CLI Example:
    salt '*' status.netdev
    '''
    stats = open('/proc/net/dev', 'r').read().split('\n')
    ret = {}
    for line in stats:
        if not line.count(' '):
            continue
        if line.find(':') < 0:
            continue
        comps = line.split()
        ret[comps[0]] = {
            'iface':         comps[0],
            'rx_bytes':      comps[1],
            'rx_packets':    comps[2],
            'rx_errs':       comps[3],
            'rx_drop':       comps[4],
            'rx_fifo':       comps[5],
            'rx_frame':      comps[6],
            'rx_compressed': comps[7],
            'rx_multicast':  comps[8],
            'tx_bytes':      comps[9],
            'tx_packets':    comps[10],
            'tx_errs':       comps[11],
            'tx_drop':       comps[12],
            'tx_fifo':       comps[13],
            'tx_colls':      comps[14],
            'tx_carrier':    comps[15],
            'tx_compressed': comps[16],
        }
    return ret

def w():
    ''' 
    Return a list of logged in users for this minon, using the w command

    CLI Example:
    salt '*' status.w
    '''
    users = subprocess.Popen(['w -h'],
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('\n')
    user_list = []
    for row in users:
        if not row.count(' '):
            continue
        comps = row.split()
        rec = { 
            'user':  comps[0],
            'tty':   comps[1],
            'login': comps[2],
            'idle':  comps[3],
            'jcpu':  comps[4],
            'pcpu':  comps[5],
            'what':  ' '.join(comps[6:]),
        }   
        user_list.append( rec )
    return user_list

def all_status():
    '''
    Return a composite of all status data and info for this minon. Warning: There is a LOT here!

    CLI Example:
    salt '*' status.all_status
    '''
    return {
        'cpuinfo':   cpuinfo(),
        'cpustats':  cpustats(),
        'diskstats': diskstats(),
        'loadavg':   loadavg(),
        'meminfo':   meminfo(),
        'netdev':    netdev(),
        'netstats':  netstats(),
        'uptime':    uptime(),
        'vmstats':   vmstats(),
        'w':         w(),
    }

