# -*- coding: utf-8 -*-
'''
A convenience system to manage jobs, both active and already run
'''

# Import python libs
from __future__ import absolute_import, print_function
import fnmatch
import logging
import os

# Import salt libs
import salt.client
import salt.payload
import salt.utils
import salt.utils.jid
import salt.minion
import salt.returners

# Import 3rd-party libs
import salt.ext.six as six
from salt.exceptions import SaltClientError

try:
    import dateutil.parser as dateutil_parser
    DATEUTIL_SUPPORT = True
except ImportError:
    DATEUTIL_SUPPORT = False

log = logging.getLogger(__name__)


def active(outputter=None, display_progress=False):
    '''
    Return a report on all actively running jobs from a job id centric
    perspective

    CLI Example:

    .. code-block:: bash

        salt-run jobs.active
    '''
    ret = {}
    client = salt.client.get_local_client(__opts__['conf_file'])
    try:
        active_ = client.cmd('*', 'saltutil.running', timeout=__opts__['timeout'])
    except SaltClientError as client_error:
        print(client_error)
        return ret

    if display_progress:
        __jid_event__.fire_event({
            'message': 'Attempting to contact minions: {0}'.format(list(active_.keys()))
            }, 'progress')
    for minion, data in six.iteritems(active_):
        if display_progress:
            __jid_event__.fire_event({'message': 'Received reply from minion {0}'.format(minion)}, 'progress')
        if not isinstance(data, list):
            continue
        for job in data:
            if not job['jid'] in ret:
                ret[job['jid']] = _format_jid_instance(job['jid'], job)
                ret[job['jid']].update({'Running': [{minion: job.get('pid', None)}], 'Returned': []})
            else:
                ret[job['jid']]['Running'].append({minion: job['pid']})

    mminion = salt.minion.MasterMinion(__opts__)
    for jid in ret:
        returner = _get_returner((__opts__['ext_job_cache'], __opts__['master_job_cache']))
        data = mminion.returners['{0}.get_jid'.format(returner)](jid)
        for minion in data:
            if minion not in ret[jid]['Returned']:
                ret[jid]['Returned'].append(minion)

    if outputter:
        salt.utils.warn_until(
            'Carbon',
            'The \'outputter\' argument to the jobs.active runner '
            'has been deprecated. Please specify an outputter using --out. '
            'See the output of \'salt-run -h\' for more information.'
        )
        return {'outputter': outputter, 'data': ret}
    else:
        return ret


def lookup_jid(jid,
               ext_source=None,
               returned=True,
               missing=False,
               outputter=None,
               display_progress=False):
    '''
    Return the printout from a previously executed job

    jid
        The jid to look up.

    ext_source
        The external job cache to use. Default: `None`.

    returned
        When set to `True`, adds the minions that did return from the command.
        Default: `True`.

        .. versionadded:: 2015.8.0

    missing
        When set to `True`, adds the minions that did NOT return from the command.
        Default: `False`.

    display_progress
        Displays progress events when set to `True`. Default: `False`.

        .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run jobs.lookup_jid 20130916125524463507
        salt-run jobs.lookup_jid 20130916125524463507 outputter=highstate
    '''
    ret = {}
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))
    if display_progress:
        __jid_event__.fire_event({'message': 'Querying returner: {0}'.format(returner)}, 'progress')

    try:
        data = mminion.returners['{0}.get_jid'.format(returner)](jid)
    except TypeError:
        return 'Requested returner could not be loaded. No JIDs could be retrieved.'

    for minion in data:
        if display_progress:
            __jid_event__.fire_event({'message': minion}, 'progress')
        if u'return' in data[minion]:
            if returned:
                ret[minion] = data[minion].get(u'return')
        else:
            if returned:
                ret[minion] = data[minion].get('return')
    if missing:
        load = mminion.returners['{0}.get_load'.format(returner)](jid)
        ckminions = salt.utils.minions.CkMinions(__opts__)
        exp = ckminions.check_minions(load['tgt'], load['tgt_type'])
        for minion_id in exp:
            if minion_id not in data:
                ret[minion_id] = 'Minion did not return'

    # Once we remove the outputter argument in a couple releases, we still
    # need to check to see if the 'out' key is present and use it to specify
    # the correct outputter, so we get highstate output for highstate runs.
    if outputter is None:
        try:
            # Check if the return data has an 'out' key. We'll use that as the
            # outputter in the absence of one being passed on the CLI.
            outputter = data[next(iter(data))].get('out')
        except (StopIteration, AttributeError):
            outputter = None
    else:
        salt.utils.warn_until(
            'Carbon',
            'The \'outputter\' argument to the jobs.lookup_jid runner '
            'has been deprecated. Please specify an outputter using --out. '
            'See the output of \'salt-run -h\' for more information.'
        )

    if outputter:
        return {'outputter': outputter, 'data': ret}
    else:
        return ret


def list_job(jid, ext_source=None, outputter=None):
    '''
    List a specific job given by its jid

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_job 20130916125524463507
    '''
    ret = {'jid': jid}
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))

    job = mminion.returners['{0}.get_load'.format(returner)](jid)
    ret.update(_format_jid_instance(jid, job))
    ret['Result'] = mminion.returners['{0}.get_jid'.format(returner)](jid)

    fstr = '{0}.get_endtime'.format(__opts__['master_job_cache'])
    if (__opts__.get('job_cache_store_endtime')
            and fstr in mminion.returners):
        endtime = mminion.returners[fstr](jid)
        if endtime:
            ret['EndTime'] = endtime

    if outputter:
        salt.utils.warn_until(
            'Carbon',
            'The \'outputter\' argument to the jobs.list_job runner '
            'has been deprecated. Please specify an outputter using --out. '
            'See the output of \'salt-run -h\' for more information.'
        )
        return {'outputter': outputter, 'data': ret}
    else:
        return ret


def list_jobs(ext_source=None,
              outputter=None,
              search_metadata=None,
              search_function=None,
              search_target=None,
              start_time=None,
              end_time=None,
              display_progress=False):
    '''
    List all detectable jobs and associated functions

    ext_source
        The external job cache to use. Default: `None`.

    search_metadata
        Search the metadata of a job for the provided string of dictionary.
        Default: 'None'.

    search_function
        Search the function of a job for the provided string.
        Default: 'None'.

    search_target
        Search the target of a job for the provided minion name.
        Default: 'None'.

    start_time
        Search for jobs where the start time of the job is greater than
        or equal to the provided time stamp.  Any timestamp supported
        by the Dateutil (required) module can be used.
        Default: 'None'.

    end_time
        Search for jobs where the start time of the job is less than
        or equal to the provided time stamp.  Any timestamp supported
        by the Dateutil (required) module can be used.
        Default: 'None'.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_jobs
        salt-run jobs.list_jobs search_function='test.*' search_target='localhost' search_metadata='{"bar": "foo"}'
        salt-run jobs.list_jobs start_time='2015, Mar 16 19:00' end_time='2015, Mar 18 22:00'

    '''
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))
    if display_progress:
        __jid_event__.fire_event({'message': 'Querying returner {0} for jobs.'.format(returner)}, 'progress')
    mminion = salt.minion.MasterMinion(__opts__)

    ret = mminion.returners['{0}.get_jids'.format(returner)]()

    mret = {}
    for item in ret:
        _match = True
        if search_metadata:
            _match = False
            if 'Metadata' in ret[item]:
                if isinstance(search_metadata, dict):
                    for key in search_metadata:
                        if key in ret[item]['Metadata']:
                            if ret[item]['Metadata'][key] == search_metadata[key]:
                                _match = True
                else:
                    log.info('The search_metadata parameter must be specified'
                             ' as a dictionary.  Ignoring.')
        if search_target and _match:
            _match = False
            if 'Target' in ret[item]:
                if isinstance(search_target, list):
                    for key in search_target:
                        if fnmatch.fnmatch(ret[item]['Target'], key):
                            _match = True
                elif isinstance(search_target, six.string_types):
                    if fnmatch.fnmatch(ret[item]['Target'], search_target):
                        _match = True

        if search_function and _match:
            _match = False
            if 'Function' in ret[item]:
                if isinstance(search_function, list):
                    for key in search_function:
                        if fnmatch.fnmatch(ret[item]['Function'], key):
                            _match = True
                elif isinstance(search_function, six.string_types):
                    if fnmatch.fnmatch(ret[item]['Function'], search_function):
                        _match = True

        if start_time and _match:
            _match = False
            if DATEUTIL_SUPPORT:
                parsed_start_time = dateutil_parser.parse(start_time)
                _start_time = dateutil_parser.parse(ret[item]['StartTime'])
                if _start_time >= parsed_start_time:
                    _match = True
            else:
                log.error('"dateutil" library not available, skipping start_time comparision.')

        if end_time and _match:
            _match = False
            if DATEUTIL_SUPPORT:
                parsed_end_time = dateutil_parser.parse(end_time)
                _start_time = dateutil_parser.parse(ret[item]['StartTime'])
                if _start_time <= parsed_end_time:
                    _match = True
            else:
                log.error('"dateutil" library not available, skipping start_time comparision.')

        if _match:
            mret[item] = ret[item]

    if outputter:
        return {'outputter': outputter, 'data': mret}
    else:
        return mret


def list_jobs_filter(count,
                     filter_find_job=True,
                     ext_source=None,
                     outputter=None,
                     display_progress=False):
    '''
    List all detectable jobs and associated functions

    ext_source
        The external job cache to use. Default: `None`.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.list_jobs_filter 50
        salt-run jobs.list_jobs_filter 100 filter_find_job=False

    '''
    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))
    if display_progress:
        __jid_event__.fire_event({'message': 'Querying returner {0} for jobs.'.format(returner)}, 'progress')
    mminion = salt.minion.MasterMinion(__opts__)

    fun = '{0}.get_jids_filter'.format(returner)
    if fun not in mminion.returners:
        raise salt.exceptions.NotImplemented('\'{0}\' returner function not implemented yet.'.format(fun))
    ret = mminion.returners[fun](count, filter_find_job)

    if outputter:
        return {'outputter': outputter, 'data': ret}
    else:
        return ret


def print_job(jid, ext_source=None, outputter=None):
    '''
    Print a specific job's detail given by it's jid, including the return data.

    CLI Example:

    .. code-block:: bash

        salt-run jobs.print_job 20130916125524463507
    '''
    ret = {}

    returner = _get_returner((__opts__['ext_job_cache'], ext_source, __opts__['master_job_cache']))
    mminion = salt.minion.MasterMinion(__opts__)

    try:
        job = mminion.returners['{0}.get_load'.format(returner)](jid)
        ret[jid] = _format_jid_instance(jid, job)
    except TypeError:
        ret[jid]['Result'] = ('Requested returner {0} is not available. Jobs cannot be retrieved. '
            'Check master log for details.'.format(returner))
        return ret
    ret[jid]['Result'] = mminion.returners['{0}.get_jid'.format(returner)](jid)

    fstr = '{0}.get_endtime'.format(__opts__['master_job_cache'])
    if (__opts__.get('job_cache_store_endtime')
            and fstr in mminion.returners):
        endtime = mminion.returners[fstr](jid)
        if endtime:
            ret[jid]['EndTime'] = endtime

    if outputter:
        salt.utils.warn_until(
            'Carbon',
            'The \'outputter\' argument to the jobs.print_job runner '
            'has been deprecated. Please specify an outputter using --out. '
            'See the output of \'salt-run -h\' for more information.'
        )
        return {'outputter': outputter, 'data': ret}
    else:
        return ret


def last_run(ext_source=None,
             outputter=None,
             metadata=None,
             function=None,
             target=None,
             display_progress=False):
    '''
    List all detectable jobs and associated functions

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-run jobs.last_run

        salt-run jobs.last_run target=nodename

        salt-run jobs.last_run function='cmd.run'

        salt-run jobs.last_run metadata="{'foo': 'bar'}"
    '''

    if metadata:
        if not isinstance(metadata, dict):
            log.info('The metadata parameter must be specified as a dictionary')
            return False

    _all_jobs = list_jobs(ext_source, outputter, metadata, function, target, display_progress)
    if _all_jobs:
        last_job = sorted(_all_jobs)[-1]
        return print_job(last_job, ext_source, outputter)
    else:
        return False


def _get_returner(returner_types):
    '''
    Helper to iterate over returner_types and pick the first one
    '''
    for returner in returner_types:
        if returner and returner is not None:
            return returner


def _format_job_instance(job):
    '''
    Helper to format a job instance
    '''
    ret = {'Function': job.get('fun', 'unknown-function'),
           'Arguments': list(job.get('arg', [])),
           # unlikely but safeguard from invalid returns
           'Target': job.get('tgt', 'unknown-target'),
           'Target-type': job.get('tgt_type', []),
           'User': job.get('user', 'root')}

    if 'metadata' in job:
        ret['Metadata'] = job.get('metadata', {})
    else:
        if 'kwargs' in job:
            if 'metadata' in job['kwargs']:
                ret['Metadata'] = job['kwargs'].get('metadata', {})

    if 'Minions' in job:
        ret['Minions'] = job['Minions']
    return ret


def _format_jid_instance(jid, job):
    '''
    Helper to format jid instance
    '''
    ret = _format_job_instance(job)
    ret.update({'StartTime': salt.utils.jid.jid_to_time(jid)})
    return ret


def _walk_through(job_dir, display_progress=False):
    '''
    Walk through the job dir and return jobs
    '''
    serial = salt.payload.Serial(__opts__)

    for top in os.listdir(job_dir):
        t_path = os.path.join(job_dir, top)

        for final in os.listdir(t_path):
            load_path = os.path.join(t_path, final, '.load.p')
            job = serial.load(salt.utils.fopen(load_path, 'rb'))

            if not os.path.isfile(load_path):
                continue

            job = serial.load(salt.utils.fopen(load_path, 'rb'))
            jid = job['jid']
            if display_progress:
                __jid_event__.fire_event({'message': 'Found JID {0}'.format(jid)}, 'progress')
            yield jid, job, t_path, final
