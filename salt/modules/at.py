'''
Wrapper module for at(1)

Also, a 'tag' feature has been added to more
easily tag jobs.
'''

import re
import datetime
import time

__outputter__ = {
    'atc': 'txt',
}

# OS Families that should work (Ubuntu and Debian are the
# default)

# Tested on CentOS 5.8
rhel = ('CentOS', 'Scientific', 'RedHat', 'Fedora', 'CloudLinux')

# Tested on OpenBSD 5.0
bsd = ('OpenBSD', 'FreeBSD')

# Known not to work
bad = ('Windows')


def __virtual__():
    '''
    Most everything has the ability to support at(1)
    '''
    return False if __grains__['os'] in bad else 'at'


def _cmd(bin, *opts):
    '''
    Wrapper to run at(1) or return None.
    '''
    bin = __salt__['cmd.which'](bin)
    if bin:
        return __salt__['cmd.run_stdout']('{0} {1}'.format(bin,
            ' '.join(opts)))


def atq(tag=None):
    '''
    List all queued and running jobs or only those with
    an optional 'tag'.

    CLI Example::

        salt '*' at.atq
        salt '*' at.atq [tag]
        salt '*' at.atq [job number]
    '''
    jobs = []

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    if __grains__['os'] in rhel:
        output = _cmd('at', '-l')
    else:
        output = _cmd('atq')

    if output == None:
        return '"{0}" is not available.'.format('at.atq')

    # No jobs so return
    if output == '':
        return {'jobs': jobs}

    # Split each job into a dictionary and handle
    # pulling out tags or only listing jobs with a certain
    # tag
    for line in output.split('\n'):
        job_tag = ''

        # Jobs created with at.at() will use the following
        # comment to denote a tagged job.
        job_kw_regex = re.compile('^### SALT: (\w+)')

        # Redhat/CentOS
        if __grains__['os'] in rhel:
            job, spec = line.split('\t')
            specs = spec.split()
        elif __grains__['os'] in bsd:
            if line.startswith(' Rank'):
                continue
            else:
                tmp = line.split()
                timestr = ' '.join(tmp[1:5])
                job = tmp[6]
                specs = datetime.datetime(*(time.strptime(timestr, '%b %d, %Y '
                    '%H:%M')[0:5])).isoformat().split('T')
                specs.append(tmp[7])
                specs.append(tmp[5])

        else:
            job, spec = line.split('\t')
            tmp = spec.split()
            timestr = ' '.join(tmp[0:5])
            specs = datetime.datetime(*(time.strptime(timestr)
                [0:5])).isoformat().split('T')
            specs.append(tmp[5])
            specs.append(tmp[6])

        # Search for any tags
        atc_out = _cmd('at', '-c', job)
        for line in atc_out.split('\n'):
            tmp = job_kw_regex.match(line)
            if tmp:
                job_tag = tmp.groups()[0]

        if __grains__['os'] in bsd:
            job = str(job)
        else:
            job = int(job)

        # If a tag is supplied, only list jobs with that tag
        if tag:

            # TODO: Looks like there is a difference between salt and salt-call
            # If I don't wrap job in an int(), it fails on salt but works on
            # salt-call. With the int(), it fails with salt-call but not salt.
            if tag == job_tag or tag == job:
                jobs.append({'job': job, 'date': specs[0], 'time': specs[1],
                    'queue': specs[2], 'user': specs[3], 'tag': job_tag})
        else:
            jobs.append({'job': job, 'date': specs[0], 'time': specs[1],
                'queue': specs[2], 'user': specs[3], 'tag': job_tag})

    return {'jobs': jobs}


def atrm(*pargs):
    '''
    Remove jobs from the queue.

    CLI Example::

        salt '*' at.atrm <jobid> <jobid> .. <jobid>
        salt '*' at.atrm all
        salt '*' at.atrm all [tag]
    '''
    opts = ''

    # Need to do this here also since we use atq()
    if not __salt__['cmd.which']('at'):
        return '"{0}" is not available.'.format('at.atrm')

    if not pargs:
        return {'jobs': {'removed': [], 'tag': None}}

    if pargs[0] == 'all':
        if len(pargs) > 1:
            opts = map(str, [j['job'] for j in atq(pargs[1])['jobs']])
            ret = {'jobs': {'removed': opts, 'tag': pargs[1]}}
        else:
            opts = map(str, [j['job'] for j in atq()['jobs']])
            ret = {'jobs': {'removed': opts, 'tag': None}}
    else:
        opts = map(str, [i['job'] for i in atq()['jobs']
            if i['job'] in pargs])
        ret = {'jobs': {'removed': opts, 'tag': None}}

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    output = _cmd('at', '-d', ' '.join(opts))
    if output == None:
        return '"{0}" is not available.'.format('at.atrm')

    return ret


def at(*pargs, **kwargs):
    '''
    Add a job to the queue.

    The 'timespec' follows the format documented in the
    at(1) manpage.

    CLI Example::

        salt '*' at.at <timespec> <cmd> [tag=<tag>] [runas=<user>]
        salt '*' at.at 12:05am '/sbin/reboot' tag=reboot
        salt '*' at.at '3:05am +3 days' 'bin/myscript' tag=nightly runas=jim
    '''
    echo_cmd = ''

    if len(pargs) < 2:
        return {'jobs': []}

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    bin = __salt__['cmd.which']('at')
    if not bin:
        return '"{0}" is not available.'.format('at.at')

    if __grains__['os'] in rhel:
        echo_cmd = 'echo -e'
    else:
        echo_cmd = 'echo'

    if 'tag' in kwargs:
        cmd = '{4} "### SALT: {0}\n{1}" | {2} {3}'.format(kwargs['tag'],
            ' '.join(pargs[1:]), bin, pargs[0], echo_cmd)
    else:
        cmd = '{3} "{1}" | {2} {0}'.format(pargs[0], ' '.join(pargs[1:]),
            bin, echo_cmd)

    # Can't use _cmd here since we need to prepend 'echo_cmd'
    if 'runas' in kwargs:
        output = __salt__['cmd.run']('{0}'.format(cmd), runas=kwargs['runas'])
    else:
        output = __salt__['cmd.run']('{0}'.format(cmd))

    if output == None:
        return '"{0}" is not available.'.format('at.at')

    if output.endswith('Garbled time'):
        return {'jobs': [], 'error': 'invalid timespec'}

    if output.startswith('warning: commands'):
        output = output.split('\n')[1]

    if output.startswith('commands will be executed'):
        output = output.split('\n')[1]

    if __grains__['os'] in bsd:
        return atq(str(output.split()[1]))
    else:
        return atq(int(output.split()[1]))


def atc(jobid):
    '''
    Print the at(1) script that will run for the passed job
    id. This is mostly for debugging so the output will
    just be text.

    CLI Example::

        salt '*' at.atc <jobid>
    '''
    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    output = _cmd('at', '-c', str(jobid))
    if output == None:
        return '"{0}" is not available.'.format('at.atc')

    if output == '':
        return {'error': 'invalid job id "{0}"'.format(str(jobid))}

    return output
