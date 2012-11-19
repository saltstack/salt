'''
Execute puppet routines
'''

from salt import utils

__outputter__ = {
    'run':  'txt',
    'noop': 'txt',
    'fact': 'txt',
    'facts': None,
}

def _check_puppet():
    '''
    Checks if puppet is installed
    '''
    # I thought about making this a virtual module, but then I realized that I
    # would require the minion to restart if puppet was installed after the
    # minion was started, and that would be rubbish
    utils.check_or_die('puppet')

def _check_facter():
    '''
    Checks if facter is installed
    '''
    utils.check_or_die('facter')

def _format_fact(output):
    try:
        fact, value = output.split(' => ', 1)
        value = value.strip()
    except ValueError:
        fact = None
        value = None
    return (fact, value)


def run(tags=None):
    '''
    Execute a puppet run and return a dict with the stderr, stdout,
    return code, etc. If an argument is specified, it is treated as
    a comma separated list of tags passed to puppet --test --tags:
    http://projects.puppetlabs.com/projects/1/wiki/Using_Tags

    CLI Examples::

        salt '*' puppet.run

        salt '*' puppet.run basefiles::edit,apache::server
    '''
    _check_puppet()

    if not tags:
        cmd = 'puppet agent --test'
    else:
        cmd = 'puppet agent --test --tags "{0}"'.format(tags)

    return __salt__['cmd.run_all'](cmd)

def noop(tags=None):
    '''
    Execute a puppet noop run and return a dict with the stderr, stdout,
    return code, etc. If an argument is specified, it is  treated  as  a
    comma separated list of tags passed to puppet --test --noop   --tags

    CLI Example::

        salt '*' puppet.noop

        salt '*' puppet.noop web::server,django::base
    '''
    _check_puppet()

    if not tags:
        cmd = 'puppet agent --test --noop'
    else:
        cmd = 'puppet agent --test --tags "{0}" --noop'.format(tags)

    return __salt__['cmd.run_all'](cmd)

def facts():
    '''
    Run facter and return the results

    CLI Example::

        salt '*' puppet.facts
    '''
    _check_facter()

    ret = {}
    output = __salt__['cmd.run']('facter')

    # Loop over the facter output and  properly
    # parse it into a nice dictionary for using
    # elsewhere
    for line in output.splitlines():
        if not line: continue
        fact, value = _format_fact(line)
        if not fact:
            continue
        ret[fact] = value
    return ret

def fact(name):
    '''
    Run facter for a specific fact

    CLI Example::

        salt '*' puppet.fact kernel
    '''
    _check_facter()

    ret = __salt__['cmd.run']('facter {0}'.format(name))
    if not ret:
        return ''
    return ret

def run_masterless(manifest, modulepath=None, vardir='/var/lib/puppet', confdir='/etc/puppet', tags=None):
    '''
    Execute a puppet run without a master server and return a dict
    with the stderr, stdout, return code etc. The first unnamed
    argument is the manifest to use for the run. The second is the
    path to the directory holding modules to be used in the run.

    Tags must be provided as a keyword argument.

    CLI Examples::

        salt '*' puppet.run_masterless /a/b/manifests/site.pp modulepath=/a/b/modules

        salt '*' puppet.run_masterless /a/b/manifests/site.pp modulepath=/a/b/modules tags=basefiles::edit,apache::server
    '''
    _check_puppet()

    cmd = 'puppet apply --modulepath={0} --vardir={1} --confdir={2} {3}'.format(modulepath,
                                                                                vardir,
                                                                                confdir,
                                                                                manifest)
    if tags:
        cmd = '{0} --tags "{1}"'.format(cmd, tags)

    return __salt__['cmd.run_all'](cmd)

def noop_masterless(manifest, modulepath=None, vardir='/var/lib/puppet', confdir='/etc/puppet', tags=None):
    '''
    Execute a puppet noop run without a master server and return a dict
    with the stderr, stdout, return code etc. The first unnamed
    argument is the manifest to use for the run. The second is the
    path to the directory holding modules to be used in the run.

    Tags must be provided as a keyword argument.

    CLI Examples::

        salt '*' puppet.noop_masterless /a/b/manifests/site.pp modulepath=/a/b/modules

        salt '*' puppet.noop_masterless /a/b/manifests/site.pp modulepath=/a/b/modules tags=basefiles::edit,apache::server
    '''
    _check_puppet()

    cmd = 'puppet apply --noop --modulepath={0} --vardir={1} --confdir={2} {3}'.format(modulepath,
                                                                                vardir,
                                                                                confdir,
                                                                                manifest)
    if tags:
        cmd = '{0} --tags "{1}"'.format(cmd, tags)

    return __salt__['cmd.run_all'](cmd)
