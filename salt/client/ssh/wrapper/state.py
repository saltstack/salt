# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''

from __future__ import absolute_import
# Import python libs
import os
import copy
import json
import logging

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh.state
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.hashutils
import salt.utils.platform
import salt.utils.thin
import salt.roster
import salt.state
import salt.loader
import salt.minion
import salt.log

# Import 3rd-party libs
from salt.ext import six

__func_alias__ = {
    'apply_': 'apply'
}
log = logging.getLogger(__name__)


def _merge_extra_filerefs(*args):
    '''
    Takes a list of filerefs and returns a merged list
    '''
    ret = []
    for arg in args:
        if isinstance(arg, six.string_types):
            if arg:
                ret.extend(arg.split(','))
        elif isinstance(arg, list):
            if arg:
                ret.extend(arg)
    return ','.join(ret)


def sls(mods, saltenv='base', test=None, exclude=None, **kwargs):
    '''
    Create the seed file for a state.sls run
    '''
    st_kwargs = __salt__.kwargs
    __opts__['grains'] = __grains__
    __pillar__.update(kwargs.get('pillar', {}))
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    if isinstance(mods, six.string_types):
        mods = mods.split(',')
    high_data, errors = st_.render_highstate({saltenv: mods})
    if exclude:
        if isinstance(exclude, six.string_types):
            exclude = exclude.split(',')
        if '__exclude__' in high_data:
            high_data['__exclude__'].extend(exclude)
        else:
            high_data['__exclude__'] = exclude
    high_data, ext_errors = st_.state.reconcile_extend(high_data)
    errors += ext_errors
    errors += st_.state.verify_high(high_data)
    if errors:
        return errors
    high_data, req_in_errors = st_.state.requisite_in(high_data)
    errors += req_in_errors
    high_data = st_.state.apply_exclude(high_data)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    # Compile and verify the raw chunks
    chunks = st_.state.compile_high_data(high_data)
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get('extra_filerefs', ''),
                __opts__.get('extra_filerefs', '')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get('roster', 'flat'))
    roster_grains = roster.opts['grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__['fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs['id_'],
            roster_grains)
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__['thin_dir'],
            test,
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__['fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            '{0}/salt_state.tgz'.format(__opts__['thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.data.decode_dict)
    except Exception as e:
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def low(data, **kwargs):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    '''
    st_kwargs = __salt__.kwargs
    __opts__['grains'] = __grains__
    chunks = [data]
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    for chunk in chunks:
        chunk['__id__'] = chunk['name'] if not chunk.get('__id__') else chunk['__id__']
    err = st_.state.verify_data(data)
    if err:
        return err
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get('extra_filerefs', ''),
                __opts__.get('extra_filerefs', '')
                )
            )
    roster = salt.roster.Roster(__opts__, __opts__.get('roster', 'flat'))
    roster_grains = roster.opts['grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__['fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs['id_'],
            roster_grains)
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg {0}/salt_state.tgz pkg_sum={1} hash_type={2}'.format(
            __opts__['thin_dir'],
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__['fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            '{0}/salt_state.tgz'.format(__opts__['thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.data.decode_dict)
    except Exception as e:
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def high(data, **kwargs):
    '''
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    __pillar__.update(kwargs.get('pillar', {}))
    st_kwargs = __salt__.kwargs
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    chunks = st_.state.compile_high_data(data)
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get('extra_filerefs', ''),
                __opts__.get('extra_filerefs', '')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get('roster', 'flat'))
    roster_grains = roster.opts['grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__['fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs['id_'],
            roster_grains)
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg {0}/salt_state.tgz pkg_sum={1} hash_type={2}'.format(
            __opts__['thin_dir'],
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__['fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            '{0}/salt_state.tgz'.format(__opts__['thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.data.decode_dict)
    except Exception as e:
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def apply_(mods=None,
          **kwargs):
    '''
    .. versionadded:: 2015.5.3

    Apply states! This function will call highstate or state.sls based on the
    arguments passed in, state.apply is intended to be the main gateway for
    all state executions.

    CLI Example:

    .. code-block:: bash

        salt '*' state.apply
        salt '*' state.apply test
        salt '*' state.apply test,pkgs
    '''
    if mods:
        return sls(mods, **kwargs)
    return highstate(**kwargs)


def request(mods=None,
            **kwargs):
    '''
    .. versionadded:: 2017.7.3

    Request that the local admin execute a state run via
    `salt-call state.run_request`
    All arguments match state.apply

    CLI Example:

    .. code-block:: bash

        salt '*' state.request
        salt '*' state.request test
        salt '*' state.request test,pkgs
    '''
    kwargs['test'] = True
    ret = apply_(mods, **kwargs)
    notify_path = os.path.join(__opts__['cachedir'], 'req_state.p')
    serial = salt.payload.Serial(__opts__)
    req = check_request()
    req.update({kwargs.get('name', 'default'): {
            'test_run': ret,
            'mods': mods,
            'kwargs': kwargs
            }
        })
    cumask = os.umask(0o77)
    try:
        if salt.utils.platform.is_windows():
            # Make sure cache file isn't read-only
            __salt__['cmd.run']('attrib -R "{0}"'.format(notify_path))
        with salt.utils.files.fopen(notify_path, 'w+b') as fp_:
            serial.dump(req, fp_)
    except (IOError, OSError):
        msg = 'Unable to write state request file {0}. Check permission.'
        log.error(msg.format(notify_path))
    os.umask(cumask)
    return ret


def check_request(name=None):
    '''
    .. versionadded:: 2017.7.3

    Return the state request information, if any

    CLI Example:

    .. code-block:: bash

        salt '*' state.check_request
    '''
    notify_path = os.path.join(__opts__['cachedir'], 'req_state.p')
    serial = salt.payload.Serial(__opts__)
    if os.path.isfile(notify_path):
        with salt.utils.files.fopen(notify_path, 'rb') as fp_:
            req = serial.load(fp_)
        if name:
            return req[name]
        return req
    return {}


def clear_request(name=None):
    '''
    .. versionadded:: 2017.7.3

    Clear out the state execution request without executing it

    CLI Example:

    .. code-block:: bash

        salt '*' state.clear_request
    '''
    notify_path = os.path.join(__opts__['cachedir'], 'req_state.p')
    serial = salt.payload.Serial(__opts__)
    if not os.path.isfile(notify_path):
        return True
    if not name:
        try:
            os.remove(notify_path)
        except (IOError, OSError):
            pass
    else:
        req = check_request()
        if name in req:
            req.pop(name)
        else:
            return False
        cumask = os.umask(0o77)
        try:
            if salt.utils.platform.is_windows():
                # Make sure cache file isn't read-only
                __salt__['cmd.run']('attrib -R "{0}"'.format(notify_path))
            with salt.utils.files.fopen(notify_path, 'w+b') as fp_:
                serial.dump(req, fp_)
        except (IOError, OSError):
            msg = 'Unable to write state request file {0}. Check permission.'
            log.error(msg.format(notify_path))
        os.umask(cumask)
    return True


def run_request(name='default', **kwargs):
    '''
    .. versionadded:: 2017.7.3

    Execute the pending state request

    CLI Example:

    .. code-block:: bash

        salt '*' state.run_request
    '''
    req = check_request()
    if name not in req:
        return {}
    n_req = req[name]
    if 'mods' not in n_req or 'kwargs' not in n_req:
        return {}
    req[name]['kwargs'].update(kwargs)
    if 'test' in n_req['kwargs']:
        n_req['kwargs'].pop('test')
    if req:
        ret = apply_(n_req['mods'], **n_req['kwargs'])
        try:
            os.remove(os.path.join(__opts__['cachedir'], 'req_state.p'))
        except (IOError, OSError):
            pass
        return ret
    return {}


def highstate(test=None, **kwargs):
    '''
    Retrieve the state data from the salt master for this minion and execute it

    CLI Example:

    .. code-block:: bash

        salt '*' state.highstate

        salt '*' state.highstate exclude=sls_to_exclude
        salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    __pillar__.update(kwargs.get('pillar', {}))
    st_kwargs = __salt__.kwargs
    __opts__['grains'] = __grains__

    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get('extra_filerefs', ''),
                __opts__.get('extra_filerefs', '')
                )
            )
    # Check for errors
    for chunk in chunks:
        if not isinstance(chunk, dict):
            __context__['retcode'] = 1
            return chunks

    roster = salt.roster.Roster(__opts__, __opts__.get('roster', 'flat'))
    roster_grains = roster.opts['grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__['fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs['id_'],
            roster_grains)
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__['thin_dir'],
            test,
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__['fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            '{0}/salt_state.tgz'.format(__opts__['thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.data.decode_dict)
    except Exception as e:
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def top(topfn, test=None, **kwargs):
    '''
    Execute a specific top file instead of the default

    CLI Example:

    .. code-block:: bash

        salt '*' state.top reverse_top.sls
        salt '*' state.top reverse_top.sls exclude=sls_to_exclude
        salt '*' state.top reverse_top.sls exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    __pillar__.update(kwargs.get('pillar', {}))
    st_kwargs = __salt__.kwargs
    __opts__['grains'] = __grains__
    if salt.utils.args.test_mode(test=test, **kwargs):
        __opts__['test'] = True
    else:
        __opts__['test'] = __opts__.get('test', None)
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    st_.opts['state_top'] = os.path.join('salt://', topfn)
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get('extra_filerefs', ''),
                __opts__.get('extra_filerefs', '')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get('roster', 'flat'))
    roster_grains = roster.opts['grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__['fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs['id_'],
            roster_grains)
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__['thin_dir'],
            test,
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__['fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            '{0}/salt_state.tgz'.format(__opts__['thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.data.decode_dict)
    except Exception as e:
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return stdout


def show_highstate():
    '''
    Retrieve the highstate data from the salt master and display it

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_highstate
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    return st_.compile_highstate()


def show_lowstate():
    '''
    List out the low data that will be applied to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_lowstate
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    return st_.compile_low_chunks()


def show_sls(mods, saltenv='base', test=None, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    __pillar__.update(kwargs.get('pillar', {}))
    __opts__['grains'] = __grains__
    opts = copy.copy(__opts__)
    if salt.utils.args.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    if isinstance(mods, six.string_types):
        mods = mods.split(',')
    high_data, errors = st_.render_highstate({saltenv: mods})
    high_data, ext_errors = st_.state.reconcile_extend(high_data)
    errors += ext_errors
    errors += st_.state.verify_high(high_data)
    if errors:
        return errors
    high_data, req_in_errors = st_.state.requisite_in(high_data)
    errors += req_in_errors
    high_data = st_.state.apply_exclude(high_data)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    return high_data


def show_low_sls(mods, saltenv='base', test=None, **kwargs):
    '''
    Display the low state data from a specific sls or list of sls files on the
    master.

    .. versionadded:: 2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    __pillar__.update(kwargs.get('pillar', {}))
    __opts__['grains'] = __grains__

    opts = copy.copy(__opts__)
    if salt.utils.args.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    if isinstance(mods, six.string_types):
        mods = mods.split(',')
    high_data, errors = st_.render_highstate({saltenv: mods})
    high_data, ext_errors = st_.state.reconcile_extend(high_data)
    errors += ext_errors
    errors += st_.state.verify_high(high_data)
    if errors:
        return errors
    high_data, req_in_errors = st_.state.requisite_in(high_data)
    errors += req_in_errors
    high_data = st_.state.apply_exclude(high_data)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    ret = st_.state.compile_high_data(high_data)
    return ret


def show_top():
    '''
    Return the top data that the minion will use for a highstate

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_top
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__['fileclient'])
    top_data = st_.get_top()
    errors = []
    errors += st_.verify_tops(top_data)
    if errors:
        return errors
    matches = st_.top_matches(top_data)
    return matches


def single(fun, name, test=None, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Execute a single state function with the named kwargs, returns False if
    insufficient data is sent to the command

    By default, the values of the kwargs will be parsed as YAML. So, you can
    specify lists values, or lists of single entry key-value maps, as you
    would in a YAML salt file. Alternatively, JSON format of keyword values
    is also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' state.single pkg.installed name=vim

    '''
    st_kwargs = __salt__.kwargs
    __opts__['grains'] = __grains__

    # state.fun -> [state, fun]
    comps = fun.split('.')
    if len(comps) < 2:
        __context__['retcode'] = 1
        return 'Invalid function passed'

    # Create the low chunk, using kwargs as a base
    kwargs.update({'state': comps[0],
                   'fun': comps[1],
                   '__id__': name,
                   'name': name})

    opts = copy.deepcopy(__opts__)

    # Set test mode
    if salt.utils.args.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)

    # Get the override pillar data
    __pillar__.update(kwargs.get('pillar', {}))

    # Create the State environment
    st_ = salt.client.ssh.state.SSHState(__opts__, __pillar__)

    # Verify the low chunk
    err = st_.verify_data(kwargs)
    if err:
        __context__['retcode'] = 1
        return err

    # Must be a list of low-chunks
    chunks = [kwargs]

    # Retrieve file refs for the state run, so we can copy relevant files down
    # to the minion before executing the state
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get('extra_filerefs', ''),
                __opts__.get('extra_filerefs', '')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get('roster', 'flat'))
    roster_grains = roster.opts['grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__['fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs['id_'],
            roster_grains)

    # Create a hash so we can verify the tar on the target system
    trans_tar_sum = salt.utils.hashutils.get_hash(trans_tar, __opts__['hash_type'])

    # We use state.pkg to execute the "state package"
    cmd = 'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__['thin_dir'],
            test,
            trans_tar_sum,
            __opts__['hash_type'])

    # Create a salt-ssh Single object to actually do the ssh work
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__['fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)

    # Copy the tar down
    single.shell.send(
            trans_tar,
            '{0}/salt_state.tgz'.format(__opts__['thin_dir']))

    # Run the state.pkg command on the target
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.data.decode_dict)
    except Exception as e:
        log.error("JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return stdout
