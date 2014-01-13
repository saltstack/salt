'''
Helper functions and constants for AWS integration.
'''
import json

# Import salt libs
import salt.utils


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
    return u'--output json'


def region(region):
    '''
    Returns the region argument to pass to awscli.

    region
        AWS region e.g. us-east-1
    '''
    return u' --region {r}'.format(r=region)


_region = region


def cli(module, cmd, region, salt_cmd, opts, user, **kwargs):
    '''
    Runs the given command against awscli. Returns either a JSON string, or
    a raw error message.

    module
        Module to execute
    cmd
        Command to run
    region
        Region to execute cmd in
    salt_cmd
        The salt command to run. We need this because __salt__ isn't injected
        into utils
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
        region=_region(region),
        out=output())

    rtn = salt_cmd['cmd.run'](cmd, runas=user)

    try:
        return json.loads(rtn)
    except ValueError:
        return rtn
