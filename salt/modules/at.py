'''
Wrapper module for at(1)

Also, a 'tag' feature has been added to more
easily tag jobs.
'''

import re

__outputter__ = {
    'atc': 'txt',
}


def __virtual__():
    '''
    Most everything has the ability to support at(1)
    '''
    return False if __grains__['os'] == 'Windows' else 'at'


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
    output = _cmd('at', '-l')
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

        job, spec = line.split('\t')
        specs = spec.split()

        # Search for any tags
        atc_out = _cmd('at', '-c', job)
        for line in atc_out.split('\n'):
            tmp = job_kw_regex.match(line)
            if tmp:
                job_tag = tmp.groups()[0]

        # If a tag is supplied, only list jobs with that tag
        if tag:

            # TODO: Looks like there is a difference between salt and salt-call
            # If I don't wrap job in an int(), it fails on salt but works on
            # salt-call. With the int(), it fails with salt-call but not salt.
            if tag == job_tag or tag == int(job):
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

    if not pargs:
        return {'jobs': {'removed': [], 'tag': None}}

    if pargs[0] == 'all':
        if len(pargs) > 1:
            opts = ' '.join([j['job'] for j in atq(pargs[1])['jobs']])
            ret = {'jobs': {'removed': opts.split(), 'tag': pargs[1]}}
        else:
            opts = ' '.join([j['job'] for j in atq()['jobs']])
            ret = {'jobs': {'removed': opts.split(), 'tag': None}}
    else:
        opts = ' '.join([i['job'] for i in atq()['jobs']
            if int(i['job']) in pargs])
        ret = {'jobs': {'removed': opts.split(), 'tag': None}}

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    output = _cmd('at', '-d', opts)
    if output == None:
        return '"{0}" is not available.'.format('at.atrm')

    return ret


def at(*pargs, **kwargs):
    '''
    Add a job to the queue. Please note that the <cmd>
    will be piped to at(1) using 'echo -e'.

    The 'timespec' follows the format documented in the
    at(1) manpage.

    CLI Example::

        salt '*' at.at <timespec> <cmd> [tag=<tag>] [runas=<user>]
        salt '*' at.at 12:05am '/sbin/reboot' tag=reboot
        salt '*' at.at '3:05am +3 days' 'bin/myscript' tag=nightly runas=jim
    '''
    if len(pargs) < 2:
        return {'jobs': []}

    bin = __salt__['cmd.which']('at')
    if not bin:
        return '"{0}" is not available.'.format('at.at')

    # Shim to produce output similar to what __virtual__() should do
    # but __salt__ isn't available in __virtual__()
    if 'tag' in kwargs:
        cmd = "echo -e '### SALT: {0}\n{1}' | {2} {3}".format(kwargs['tag'],
            ' '.join(pargs[1:]), bin, pargs[0])
    else:
        cmd = "echo -e '{1}' | {2} {0}".format(pargs[0], ' '.join(pargs[1:]),
            bin)

    # Can't use _cmd here since we need to prepend 'echo -e'
    if 'runas' in kwargs:
        output = __salt__['cmd.run']('{0}'.format(cmd), runas=kwargs['runas'])
    else:
        output = __salt__['cmd.run']('{0}'.format(cmd))

    if output == None:
        return '"{0}" is not available.'.format('at.at')

    if output.endswith('Garbled time'):
        return {'jobs': [], 'error': 'invalid timespec'}

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
