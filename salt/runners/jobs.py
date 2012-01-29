'''
A conveniance system to manage jobs, both active and already run
'''

# Import Python Modules
import os

# Import Salt Modules
import salt.client
import salt.payload
import salt.utils

# Import Third party libs
import yaml

def active():
    '''
    Return a report on all actively running jobs from a job id centric
    perspective
    '''
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    client = salt.client.LocalClient(__opts__['config'])
    active = client.cmd('*', 'saltutil.running', timeout=1)
    for minion, data in active.items():
        if not isinstance(data, tuple):
            continue
        for job in data:
            if not job['jid'] in ret:
                ret[job['jid']] = {'Running': [],
                                   'Returned': [],
                                   'Function': job['fun'],
                                   'Arguments': list(job['arg']),
                                   'Target': job['tgt'],
                                   'Target-type': job['tgt_type']}
            else:
                ret[job['jid']]['running'].append({minion: job['pid']})
    if os.path.isdir(job_dir):
        for jid in os.listdir(job_dir):
            if not jid in ret:
                continue
            jid_dir = os.path.join(job_dir, jid)
            if not os.path.isdir(jid_dir):
                continue
            for minion in os.listdir(jid_dir):
                if minion.startswith('.'):
                    continue
                if os.path.exists(os.path.join(jid_dir, minion)):
                    ret[jid]['returned'].append(minion)
    print yaml.dump(ret)


def lookup_jid(jid):
    '''
    Return the printout from a previousely executed job
    '''

    def _format_ret(full_ret):
        '''
        Take the full return data and format it to simple output
        '''
        ret = {}
        out = ''
        for key, data in full_ret.items():
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
            return ret, out

    client = salt.client.LocalClient(__opts__['config'])
    full_ret = client.get_full_returns(jid, [], 0)
    ret, out = _format_ret(full_ret)
    # Determine the proper output method and run it
    get_outputter = salt.output.get_outputter
    if isinstance(ret, list) or isinstance(ret, dict):
        if out:
            printout = get_outputter(out)
        else:
            printout = get_outputter(None)
    # Pretty print any salt exceptions
    elif isinstance(ret, SaltException):
        printout = get_outputter("txt")
    printout(ret)
    return ret

def list_jobs():
    '''
    List all detectable jobs and associated functions
    '''
    serial = salt.payload.Serial(__opts__)
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    for jid in os.listdir(job_dir):
        loadpath = os.path.join(job_dir, jid, '.load.p')
        if not os.path.isfile(loadpath):
            continue
        load = serial.load(open(loadpath, 'rb'))
        ret[jid] = {'Start Time': salt.utils.jid_to_time(jid),
                    'Function': load['fun'],
                    'Arguments': list(load['arg']),
                    'Target': load['tgt'],
                    'Target-type': load['tgt_type']}
    print yaml.dump(ret)

