# -*- coding: utf-8 -*-
'''
Return data to an etcd server or cluster

:depends: - python-etcd

In order to return to an etcd server, a profile should be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 2379

It is technically possible to configure etcd without using a profile, but this
is not considered to be a best practice, especially when multiple etcd servers
or clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 2379

Additionally, two more options must be specified in the top-level configuration
in order to use the etcd returner:

.. code-block:: yaml

    etcd.returner: my_etcd_config
    etcd.returner_root: /salt/return

The ``etcd.returner`` option specifies which configuration profile to use. The
``etcd.returner_root`` option specifies the path inside etcd to use as the root
of the returner system.

Once the etcd options are configured, the returner may be used:

CLI Example:

    salt '*' test.ping --return etcd

A username and password can be set:

.. code-block:: yaml

    etcd.username: larry  # Optional; requires etcd.password to be set
    etcd.password: 123pass  # Optional; requires etcd.username to be set

You can also set a TTL (time to live) value for the returner:

.. code-block:: yaml

    etcd.ttl: 5

Authentication with username and password, and ttl, currently requires the
``master`` branch of ``python-etcd``.

You may also specify different roles for read and write operations. First,
create the profiles as specified above. Then add:

.. code-block:: yaml

    etcd.returner_read_profile: my_etcd_read
    etcd.returner_write_profile: my_etcd_write
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.jid
import salt.utils.json
try:
    import salt.utils.etcd_util
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'etcd'


def __virtual__():
    '''
    Only return if python-etcd is installed
    '''
    if HAS_LIBS:
        return __virtualname__

    return False, 'Could not import etcd returner; python-etcd is not installed.'


def _get_conn(opts, profile=None):
    '''
    Establish a connection to an etcd profile.
    '''
    if profile is None:
        profile = opts.get('etcd.returner')

    # Grab the returner_root from the options
    path = opts.get('etcd.returner_root', '/salt/return')

    # Grab a connection using etcd_util, and then return the EtcdClient
    # from one of its attributes
    wrapper = salt.utils.etcd_util.get_conn(opts, profile)
    return wrapper.client, path


def returner(ret):
    '''
    Return data to an etcd profile.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    if write_profile:
        ttl = __opts__.get(write_profile, {}).get('etcd.ttl')
    else:
        ttl = __opts__.get('etcd.ttl')

    client, path = _get_conn(__opts__, write_profile)

    # if a minion is returning a standalone job, get a jid
    if ret['jid'] == 'req':
        ret['jid'] = prep_jid(nocache=ret.get('nocache', False))

    # Update the given minion in the external job cache with the current (latest job)
    # This is used by get_fun() to return the last function that was called
    minionp = '/'.join([path, 'minions', ret['id']])
    log.debug("sdstack_etcd returner <returner> updating (last) job id (ttl={ttl:d}) of {id:s} at {path:s} with job {jid:s}".format(jid=ret['jid'], id=ret['id'], path=minionp, ttl=ttl))
    res = client.set(minionp, ret['jid'], ttl=ttl)
    if hasattr(res, '_prev_node'):
        log.trace("sdstack_etcd returner <returner> the previous job id {old:s} for {id:s} at {path:s} was set to {new:s}".format(old=res._prev_node.value, id=ret['id'], path=minionp, new=res.value))

    # Figure out the path for the specified job and minion
    jobp = '/'.join([path, 'jobs', ret['jid'], ret['id']])
    log.debug("sdstack_etcd returner <returner> writing job data (ttl={ttl:d}) for {jid:s} to {path:s} with {data}".format(jid=ret['jid'], path=jobp, ttl=ttl, data=ret))

    # Iterate through all the fields in the return dict and dump them under the
    # jobs/$jid/id/$field key. We aggregate all the exceptions so that if an
    # error happens, the rest of the fields will still be written.
    exceptions = []
    for field in ret:
        fieldp = '/'.join([jobp, field])
        data = salt.utils.json.dumps(ret[field])
        try:
            res = client.set(fieldp, data, ttl=ttl)
        except Exception as E:
            log.trace("sdstack_etcd returner <returner> unable to set field {field:s} for job {jid:s} at {path:s} to {result}".format(field=field, jid=ret['jid'], path=fieldp, result=ret[field]))
            exceptions.append((E, field, ret[field]))
            continue
        log.trace("sdstack_etcd returner <returner> set field {field:s} for job {jid:s} at {path:s} to {result}".format(field=field, jid=ret['jid'], path=res.key, result=ret[field]))

    # Go back through all the exceptions that occurred while trying to write the
    # fields and log them.
    for e, field, value in exceptions:
        log.exception("sdstack_etcd returner <returner> exception ({exception:s}) was raised while trying to set the field {field:s} for job {jid:s} to {value}".format(exception=e, field=field, jid=ret['jid'], value=value))
    return


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path = _get_conn(__opts__, write_profile)
    if write_profile:
        ttl = __opts__.get(write_profile, {}).get('etcd.ttl')
    else:
        ttl = __opts__.get('etcd.ttl')

    # Figure out the path using jobs/$jid/.load.p
    loadp = '/'.join([path, 'jobs', jid, '.load.p']),
    log.debug('sdstack_etcd returner <save_load> setting load data (ttl={ttl:d}) for job {jid:s} at {path:s} with {data:s}'.format(jid=jid, ttl=ttl, path=loadp, data=load))

    # Now we can just store the current load
    data = salt.utils.json.dumps(load)
    res = client.set(loadp, data, ttl=ttl)

    log.trace('sdstack_etcd returner <save_load> saved load data for job {jid:s} at {path:s} with {data}'.format(jid=jid, path=res.key, data=load))
    return


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    '''
    Save/update the minion list for a given jid. The syndic_id argument is
    included for API compatibility only.
    '''
    write_profile = __opts__.get('etcd.returner_write_profile')
    client, path = _get_conn(__opts__, write_profile)

    # Figure out the path that our job should be at
    jobp = '/'.join([path, 'jobs', jid])
    log.debug('sdstack_etcd returner <save_minions> adding minions for job {jid:s} to {path:s}'.format(jid=jid, path=jobp))

    # Iterate through all of the minions and add a directory for them to the job path
    for minion in set(minions):
        minionp = '/'.join([path, minion])
        res = client.set(minionp, None, dir=True)
        log.trace('sdstack_etcd returner <save_minions> added minion {id:s} for job {jid:s} to {path:s}'.format(id=minion, jid=jid, path=res.key))
    return


def clean_old_jobs():
    '''
    Included for API consistency.
    '''
    # Old jobs should be cleaned by the ttl that's written for each key, so therefore
    # the implementation of this api is not necessary.
    pass


def get_load(jid):
    '''
    Return the load data that marks a specified jid.
    '''
    read_profile = __opts__.get('etcd.returner_read_profile')
    client, path = _get_conn(__opts__, read_profile)

    # Figure out the path that our job should be at
    loadp = '/'.join([path, 'jobs', jid, '.load.p'])
    log.debug('sdstack_etcd returner <get_load> reading load data for job {jid:s} from {path:s}'.format(jid=jid, path=loadp))

    # Read it. If EtcdKeyNotFound was raised then the key doesn't exist and so
    # we need to return None, because that's what our caller expects on a
    # non-existent job.
    try:
        res = client.get(loadp)
    except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
        log.error("sdstack_etcd returner <get_load> could not find job {jid:s} at the path {path:s}".format(jid=jid, path=loadp))
        return None
    log.trace('sdstack_etcd returner <get_load> found load data for job {jid:s} at {path:s} with value {data}'.format(jid=jid, path=res.key, data=res.value))
    return salt.utils.json.loads(res.value)


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed.
    '''
    client, path = _get_conn(__opts__)

    # Figure out the path that our job should be at
    jobp = '/'.join([path, 'jobs', jid])
    log.debug('sdstack_etcd returner <get_jid> reading job fields for job {jid:s} from {path:s}'.format(jid=jid, path=jobp))

    # Try and read the job directory. If we have a missing key exception then no
    # minions have returned anything yet and so we return an empty dict for the
    # caller.
    try:
        items = client.get(jobp)
    except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
        return {}

    # Iterate through all of the children at our job path that are directories.
    # Anything that is a directory should be a minion that contains some results.
    ret = {}
    for item in items.leaves:
        if not item.dir:
            continue

        # Extract the minion name from the key in the job, and use it to build
        # the path to the return value
        comps = str(item.key).split('/')
        returnp = '/'.join([path, 'jobs', jid, comps[-1], 'return'])

        # Now we know the minion and the path to the return for its job, we can
        # just grab it. If the key exists, but the value is missing entirely,
        # then something that shouldn't happen has happened.
        try:
            res = client.get(returnp)
        except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
            log.debug("sdstack_etcd returner <get_jid> returned nothing from minion {id:s} for job {jid:s} at path {path:s}".format(id=comps[-1], jid=jid, path=returnp))
            continue

        # We found something, so update our return dict with the minion id and
        # the result that it returned.
        ret[comps[-1]] = {'return': salt.utils.json.loads(res.value)}
        log.trace("sdstack_etcd returner <get_jid> job {jid:s} from minion {id:s} at path {path:s} returned {result}".format(id=comps[-1], jid=jid, path=res.key, result=res.value))
    return ret


def get_fun(fun):
    '''
    Return a dict containing the last function called for all the minions that have called a function.
    '''
    client, path = _get_conn(__opts__)

    # Find any minions that had their last function registered by returner()
    minionsp = '/'.join([path, 'minions'])
    log.debug('sdstack_etcd returner <get_fun> reading minions at {path:s} for function {fun:s}'.format(path=minionsp, fun=fun))

    # If the minions key isn't found, then no minions registered a function
    # and thus we need to return an empty dict so the caller knows that
    # nothing is available.
    try:
        items = client.get(minionsp)
    except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
        return {}

    # Walk through the list of all the minions that have a jid registered,
    # and cross reference this with the job returns.
    ret = {}
    for item in items.leaves:

        # Now that we have a minion and it's last jid, we use it to fetch the
        # function field (fun) that was registered by returner().
        comps = str(item.key).split('/')
        funp = '/'.join([path, 'jobs', str(item.value), comps[-1], 'fun'])

        # Try and read the field, and skip it if it doesn't exist or wasn't
        # registered for some reason.
        try:
            res = client.get(funp)
        except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
            log.debug("sdstack_etcd returner <get_fun> returned nothing from minion {id:s} for job {jid:s} at path {path:s}".format(id=comps[-1], jid=str(item.value), path=funp))
            continue

        # Check if the function field (fun) matches what the user is looking for
        # If it does, then we can just add the minion to our results
        data = salt.utils.json.loads(res.value)
        if data == fun:
            ret[comps[-1]] = str(data)
            log.trace("sdstack_etcd returner <get_fun> found job {jid:s} for minion {id:s} using {fun:s} at {path:s}".format(jid=comps[-1], fun=data, id=item.value, path=item.key))
        continue
    return ret


def get_jids():
    '''
    Return a list of all job ids that have returned something.
    '''
    client, path = _get_conn(__opts__)

    # Enumerate all the jobs that are available.
    jobsp = '/'.join([path, 'jobs'])
    log.debug("sdstack_etcd returner <get_jids> listing jobs at {path:s}".format(path=jobsp))

    # Fetch all the jobs. If the key doesn't exist, then it's likely that no
    # jobs have been created yet so return an empty list to the caller.
    try:
        items = client.get(jobsp)
    except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
        return []

    # Anything that's a directory is a job id. Since that's all we're returning,
    # aggregate them into a list.
    ret = []
    for item in items.leaves:
        comps = str(item.key).split('/')
        if item.dir:
            jid = comps[-1]
            ret.append(jid)
            log.trace("sdstack_etcd returner <get_jids> found job {jid:s} at {path:s}".format(jid=comps[-1], path=item.key))
        continue
    return ret


def get_minions():
    '''
    Return a list of all minions that have returned something.
    '''
    client, path = _get_conn(__opts__)

    # Find any minions that have returned anything
    minionsp = '/'.join([path, 'minions'])
    log.debug('sdstack_etcd returner <get_minions> reading minions at {path:s}'.format(path=minionsp))

    # If no minions were found, then nobody has returned anything recently
    # (due to ttl). In this case, return an empty last for the caller.
    try:
        items = client.get(minionsp)
    except salt.utils.etcd_util.etcd.EtcdKeyNotFound as E:
        return []

    # We can just walk through everything that isn't a directory. This path
    # is simply a list of minions and the last job that each one returned.
    ret = []
    for item in items.leaves:
        if not item.dir:
            comps = str(item.key).split('/')
            ret.append(comps[-1])
            log.trace("sdstack_etcd returner <get_minions> found minion {id:s} at {path:s}".format(id=comps[-1], path=item.key))
        continue
    return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id.
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)


def event_return(events):
    '''
    Return event to etcd server

    Requires that configuration enabled via 'event_return'
    option in master config.
    '''
    ttl = __opts__.get('etcd.ttl', 5)
    client, path = _get_conn(__opts__)

    exceptions = []
    for event in events:
        package = {
            'tag': event.get('tag', ''),
            'data': event.get('data', ''),
            'master_id': __opts__['id'],
        }
        path = '/'.join([path, 'events', package['tag']])
        json = salt.utils.json.dumps(package)

        try:
            res = client.set(path, json, ttl=ttl)
        except Exception as err:
            log.exception('etcd: Unable to write event into returner path {:s} due to exception {:s}: {}'.format(path, package, err))
            exceptions.append(err)
            continue

        if not res:
            log.error('etcd: Unable to write event into returner path {:s}: {}'.format(path, package))
        continue

    return
