'''
Control Modjk via the Apache Tomcat `Status worker`_

.. _`Status worker`: http://tomcat.apache.org/connectors-doc/reference/status.html

Below is an example of the configuration needed for this module. This
configuration data can be placed either in :doc:`grains
</topics/targeting/grains>` or :doc:`pillar </topics/pillar/index>`.

If using grains, this can be accomplished :ref:`statically
<static-custom-grains>` or via a :ref:`grain module <writing-grains>`.

If using pillar, the yaml configuration can be placed directly into a pillar
SLS file, making this both the easier and more dynamic method of configuring
this module.

.. code-block:: yaml

    modjk:
      default:
        url: http://localhost/jkstatus
        user: modjk
        pass: secret
        realm: authentication realm for digest passwords
        timeout: 5
      otherVhost:
        url: http://otherVhost/jkstatus
        user: modjk
        pass: secret2
        realm: authentication realm2 for digest passwords
        timeout: 600
'''

# Python libs
import urllib
import urllib2


def __virtual__():
    '''
    Always load
    '''

    return 'modjk'


def _auth(url, user, passwd, realm):
    '''
    returns a authentication handler.
    '''

    basic = urllib2.HTTPBasicAuthHandler()
    basic.add_password(realm=realm, uri=url, user=user, passwd=passwd)
    digest = urllib2.HTTPDigestAuthHandler()
    digest.add_password(realm=realm, uri=url, user=user, passwd=passwd)
    return urllib2.build_opener(basic, digest)


def _do_http(opts, profile='default'):
    '''
    Make the http request and return the data
    '''

    ret = {}

    url = __salt__['config.get']('modjk:' + profile + ':url', '')
    user = __salt__['config.get']('modjk:' + profile + ':user', '')
    passwd = __salt__['config.get']('modjk:' + profile + ':pass', '')
    realm = __salt__['config.get']('modjk:' + profile + ':realm', '')
    timeout = __salt__['config.get']('modjk:' + profile + ':timeout', 5)

    if not url:
        raise Exception('missing url in profile {0}'.format(profile))

    if user and passwd:
        auth = _auth(url, realm, user, passwd)
        urllib2.install_opener(auth)

    url += '?{0}'.format(urllib.urlencode(opts))

    for line in urllib2.urlopen(url, timeout=timeout).read().splitlines():
        splt = line.split('=', 1)
        ret[splt[0]] = splt[1]

    return ret


def _workerCtl(worker, lb, vwa, profile='default'):
    '''
    enable/disable/stop a worker
    '''

    cmd = {
        'cmd': 'update',
        'mime': 'prop',
        'w': lb,
        'sw': worker,
        'vwa': vwa,
    }
    return _do_http(cmd, profile)['worker.result.type'] == 'OK'


###############
### General ###
###############


def version(profile='default'):
    '''
    Return the modjk version

    CLI Examples::

        salt '*' modjk.version
        salt '*' modjk.version other-profile
    '''

    cmd = {
        'cmd': 'version',
        'mime': 'prop',
    }
    return _do_http(cmd, profile)['worker.jk_version'].split('/')[-1]


def get_running(profile='default'):
    '''
    Get the current running config (not from disk)

    CLI Examples::

        salt '*' modjk.get_running
        salt '*' modjk.get_running other-profile
    '''

    cmd = {
        'cmd': 'list',
        'mime': 'prop',
    }
    return _do_http(cmd, profile)


def dump_config(profile='default'):
    '''
    Dump the original configuration that was loaded from disk

    CLI Examples::

        salt '*' modjk.dump_config
        salt '*' modjk.dump_config other-profile
    '''

    cmd = {
        'cmd': 'dump',
        'mime': 'prop',
    }
    return _do_http(cmd, profile)


####################
### LB Functoins ###
####################


def list_configured_members(lb, profile='default'):
    '''
    Return a list of member workers from the configuration files

    CLI Examples::

        salt '*' modjk.list_configured_members loadbalancer1
        salt '*' modjk.list_configured_members loadbalancer1 other-profile
    '''

    config = dump_config(profile)

    try:
        ret = config['worker.{0}.balance_workers'.format(lb)].strip().split(',')
    except KeyError:
        return []

    return filter(None, ret)


def list_running_members(lb, profile='default'):
    '''
    Return a list of member workers

    CLI Examples::

        salt '*' modjk.list_running_members loadbalancer1
        salt '*' modjk.list_running_members loadbalancer1 other-profile
    '''

    config = get_running()
    try:
        return config['worker.{0}.balance_workers'.format(lb)].split(',')
    except KeyError:
        return []


def recover_all(lb, profile='default'):
    '''
    Set the all the workers in lb to recover and activate them if they are not

    CLI Examples::

        salt '*' modjk.recover_all loadbalancer1
        salt '*' modjk.recover_all loadbalancer1 other-profile
    '''

    ret = {}

    workers = list_running_members(lb, profile)
    for worker in workers:
        curr_state = worker_status(worker, profile)
        if curr_state['activation'] != 'ACT':
            worker_activate(worker, lb, profile)
        if not curr_state['state'].startswith('OK'):
            worker_recover(worker, lb, profile)
        ret[worker] = worker_status(worker, profile)

    return ret


def reset_stats(lb, profile='default'):
    '''
    Reset all runtime statistics for the load balancer

    CLI Examples::

        salt '*' modjk.reset_stats loadbalancer1
        salt '*' modjk.reset_stats loadbalancer1 other-profile
    '''

    cmd = {
        'cmd': 'reset',
        'mime': 'prop',
        'w': lb,
    }
    return _do_http(cmd, profile)['worker.result.type'] == 'OK'


def lb_edit(lb, settings, profile='default'):
    '''
    Edit the loadbalancer settings

    Note: http://tomcat.apache.org/connectors-doc/reference/status.html
    Data Parameters for the standard Update Action

    CLI Examples::

        salt '*' modjk.lb_edit loadbalancer1 "{'vlr': 1, 'vlt': 60}"
        salt '*' modjk.lb_edit loadbalancer1 "{'vlr': 1, 'vlt': 60}" other-profile
    '''

    settings['cmd'] = 'update'
    settings['mime'] = 'prop'
    settings['w'] = lb

    return _do_http(settings, profile)['worker.result.type'] == 'OK'


########################
### Worker Functions ###
########################


def worker_status(worker, profile='default'):
    '''
    Return the state of the worker

    CLI Examples::

        salt '*' modjk.worker_status node1
        salt '*' modjk.worker_status node1 other-profile
    '''

    config = get_running(profile)
    try:
        return {
            'activation': config['worker.{0}.activation'.format(worker)],
            'state': config['worker.{0}.state'.format(worker)],
        }
    except KeyError:
        return False


def worker_recover(worker, lb, profile='default'):
    '''
    Set the worker to recover
    this module will fail if it is in OK state

    CLI Examples::

        salt '*' modjk.worker_recover node1 loadbalancer1
        salt '*' modjk.worker_recover node1 loadbalancer1 other-profile
    '''

    cmd = {
        'cmd': 'recover',
        'mime': 'prop',
        'w': lb,
        'sw': worker,
    }
    return _do_http(cmd, profile)


def worker_disable(worker, lb, profile='default'):
    '''
    Set the worker to disable state in the lb load balancer

    CLI Examples::

        salt '*' modjk.worker_disable node1 loadbalancer1
        salt '*' modjk.worker_disable node1 loadbalancer1 other-profile
    '''

    return _workerCtl(worker, lb, 'd', profile)


def worker_activate(worker, lb, profile='default'):
    '''
    Set the worker to activate state in the lb load balancer

    CLI Examples::

        salt '*' modjk.worker_activate node1 loadbalancer1
        salt '*' modjk.worker_activate node1 loadbalancer1 other-profile
    '''

    return _workerCtl(worker, lb, 'a', profile)


def worker_stop(worker, lb, profile='default'):
    '''
    Set the worker to stopped state in the lb load balancer

    CLI Examples::

        salt '*' modjk.worker_activate node1 loadbalancer1
        salt '*' modjk.worker_activate node1 loadbalancer1 other-profile
    '''

    return _workerCtl(worker, lb, 's', profile)


def worker_edit(worker, lb, settings, profile='default'):
    '''
    Edit the worker settings

    Note: http://tomcat.apache.org/connectors-doc/reference/status.html
    Data Parameters for the standard Update Action

    CLI Examples::

        salt '*' modjk.lb_edit node1 loadbalancer1 "{'vwf': 500, 'vwd': 60}"
        salt '*' modjk.lb_edit node1 loadbalancer1 "{'vwf': 500, 'vwd': 60}" other-profile
    '''

    settings['cmd'] = 'update'
    settings['mime'] = 'prop'
    settings['w'] = lb
    settings['sw'] = worker

    return _do_http(settings, profile)['worker.result.type'] == 'OK'
