'''
Helper functions and constants for AWS integration.
'''
import json


def installed():
    '''
    Called by __virtual__() to determine whether awscli is available.`
    '''
    if salt.utils.which('aws'):
        # awscli is installed, load the module
        return True
    return False


def output():
    '''
    Return the output data as json.
    '''
    return u'-- output json'


def region(region):
    '''
    Returns the region argument to pass to awscli.

    region
        AWS region e.g. us-east-1
    '''
    return u' --region {r}'.format(r=region)


def cli(module, cmd, region, opts, user, **kwargs):
    '''
    Runs the given command against awscli.

    module
        Module to execute
    cmd
        Command to run
    region
        Region to execute cmd in
    opts
        Pass in from salt
    user
        Pass in from salt
    kwargs
        Key-value arguments to pass to the command
    '''
    _formatted_args = [
        u'--{0} "{1}"'.format(k, v) for k, v in kwargs.iteritems()]

    cmd = u'aws {module} {cmd} {args} {region} {out}'.format(
        module=module,
        cmd=cmd,
        args=' '.join(_formatted_args),
        region=region(region),
        out=output())

    rtn = __salt__['cmd.run'](cmd, runas=user)

    return json.loads(rtn) if rtn else ''
