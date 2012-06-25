'''
A conveniance system to manage jobs, both active and already run
'''

# Import Python Modules
import os

# Import Salt Modules
import salt.client
import salt.payload
import salt.utils
from salt._compat import string_types
from salt.exceptions import SaltException

# Import Third party libs
import yaml


def active():
    '''
    Return a report on all actively running jobs from a job id centric
    perspective
    '''
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    client = salt.client.LocalClient(__opts__['conf_file'])
    active_ = client.cmd('*', 'saltutil.running', timeout=1)
    for minion, data in active_.items():
        if not isinstance(data, list):
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
                ret[job['jid']]['Running'].append({minion: job['pid']})
    for jid in ret:
        jid_dir = salt.utils.jid_dir(
                jid,
                __opts__['cachedir'],
                __opts__['hash_type']
                )
        if not os.path.isdir(jid_dir):
            continue
        for minion in os.listdir(jid_dir):
            if minion.startswith('.'):
                continue
            if os.path.exists(os.path.join(jid_dir, minion)):
                ret[jid]['Returned'].append(minion)
    print(yaml.dump(ret))
    return ret


def lookup_jid(jid):
    '''
    Return the printout from a previousely executed job
    '''
    def _format_ret(full_ret):
        '''
        Take the full return data and format it to simple output
        '''
        out = None
        ret = {}
        for key, data in full_ret.items():
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
        return ret, out

    client = salt.client.LocalClient(__opts__['conf_file'])
    full_ret = client.get_full_returns(jid, [], 0)
    formatted = _format_ret(full_ret)

    if formatted:
        ret = formatted[0]
        out = formatted[1]
    else:
        ret = SaltException('Job {0} hasn\'t finished. No data yet :('.format(jid))
        out = ''

    # Determine the proper output method and run it
    get_outputter = salt.output.get_outputter
    if isinstance(ret, (list, dict, string_types)) and out:
        printout = get_outputter(out)
    # Pretty print any salt exceptions
    elif isinstance(ret, SaltException):
        printout = get_outputter("txt")
    else:
        printout = get_outputter(None)
    printout(ret)
    return ret


def list_jobs():
    '''
    List all detectable jobs and associated functions
    '''
    serial = salt.payload.Serial(__opts__)
    ret = {}
    job_dir = os.path.join(__opts__['cachedir'], 'jobs')
    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)
        for final in os.listdir(t_path):
            loadpath = os.path.join(t_path, final, '.load.p')
            if not os.path.isfile(loadpath):
                continue
            load = serial.load(open(loadpath, 'rb'))
            jid = load['jid']
            ret[jid] = {'Start Time': salt.utils.jid_to_time(jid),
                        'Function': load['fun'],
                        'Arguments': list(load['arg']),
                        'Target': load['tgt'],
                        'Target-type': load['tgt_type']}
    print(yaml.dump(ret))
    return ret
