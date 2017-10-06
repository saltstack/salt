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
import salt.utils
import salt.utils.thin
import salt.roster
import salt.state
import salt.loader
import salt.minion
import salt.log

# Import 3rd-party libs
from salt.ext import six

__func_alias__ = {
    u'apply_': u'apply'
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
                ret.extend(arg.split(u','))
        elif isinstance(arg, list):
            if arg:
                ret.extend(arg)
    return u','.join(ret)


def sls(mods, saltenv=u'base', test=None, exclude=None, **kwargs):
    '''
    Create the seed file for a state.sls run
    '''
    st_kwargs = __salt__.kwargs
    __opts__[u'grains'] = __grains__
    __pillar__.update(kwargs.get(u'pillar', {}))
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    if isinstance(mods, six.string_types):
        mods = mods.split(u',')
    high_data, errors = st_.render_highstate({saltenv: mods})
    if exclude:
        if isinstance(exclude, six.string_types):
            exclude = exclude.split(u',')
        if u'__exclude__' in high_data:
            high_data[u'__exclude__'].extend(exclude)
        else:
            high_data[u'__exclude__'] = exclude
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
                kwargs.get(u'extra_filerefs', u''),
                __opts__.get(u'extra_filerefs', u'')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get(u'roster', u'flat'))
    roster_grains = roster.opts[u'grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__[u'fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs[u'id_'],
            roster_grains)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__[u'hash_type'])
    cmd = u'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__[u'thin_dir'],
            test,
            trans_tar_sum,
            __opts__[u'hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__[u'fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            u'{0}/salt_state.tgz'.format(__opts__[u'thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception as e:
        log.error(u"JSON Render failed for: %s\n%s", stdout, stderr)
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
    __opts__[u'grains'] = __grains__
    chunks = [data]
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    for chunk in chunks:
        chunk[u'__id__'] = chunk[u'name'] if not chunk.get(u'__id__') else chunk[u'__id__']
    err = st_.state.verify_data(data)
    if err:
        return err
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get(u'extra_filerefs', u''),
                __opts__.get(u'extra_filerefs', u'')
                )
            )
    roster = salt.roster.Roster(__opts__, __opts__.get(u'roster', u'flat'))
    roster_grains = roster.opts[u'grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__[u'fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs[u'id_'],
            roster_grains)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__[u'hash_type'])
    cmd = u'state.pkg {0}/salt_state.tgz pkg_sum={1} hash_type={2}'.format(
            __opts__[u'thin_dir'],
            trans_tar_sum,
            __opts__[u'hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__[u'fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            u'{0}/salt_state.tgz'.format(__opts__[u'thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception as e:
        log.error(u"JSON Render failed for: %s\n%s", stdout, stderr)
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
    __pillar__.update(kwargs.get(u'pillar', {}))
    st_kwargs = __salt__.kwargs
    __opts__[u'grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    chunks = st_.state.compile_high_data(data)
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get(u'extra_filerefs', u''),
                __opts__.get(u'extra_filerefs', u'')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get(u'roster', u'flat'))
    roster_grains = roster.opts[u'grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__[u'fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs[u'id_'],
            roster_grains)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__[u'hash_type'])
    cmd = u'state.pkg {0}/salt_state.tgz pkg_sum={1} hash_type={2}'.format(
            __opts__[u'thin_dir'],
            trans_tar_sum,
            __opts__[u'hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__[u'fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            u'{0}/salt_state.tgz'.format(__opts__[u'thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception as e:
        log.error(u"JSON Render failed for: %s\n%s", stdout, stderr)
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


def highstate(test=None, **kwargs):
    '''
    Retrieve the state data from the salt master for this minion and execute it

    CLI Example:

    .. code-block:: bash

        salt '*' state.highstate

        salt '*' state.highstate exclude=sls_to_exclude
        salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    __pillar__.update(kwargs.get(u'pillar', {}))
    st_kwargs = __salt__.kwargs
    __opts__[u'grains'] = __grains__

    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get(u'extra_filerefs', u''),
                __opts__.get(u'extra_filerefs', u'')
                )
            )
    # Check for errors
    for chunk in chunks:
        if not isinstance(chunk, dict):
            __context__[u'retcode'] = 1
            return chunks

    roster = salt.roster.Roster(__opts__, __opts__.get(u'roster', u'flat'))
    roster_grains = roster.opts[u'grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__[u'fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs[u'id_'],
            roster_grains)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__[u'hash_type'])
    cmd = u'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__[u'thin_dir'],
            test,
            trans_tar_sum,
            __opts__[u'hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__[u'fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            u'{0}/salt_state.tgz'.format(__opts__[u'thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception as e:
        log.error(u"JSON Render failed for: %s\n%s", stdout, stderr)
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
    __pillar__.update(kwargs.get(u'pillar', {}))
    st_kwargs = __salt__.kwargs
    __opts__[u'grains'] = __grains__
    if salt.utils.test_mode(test=test, **kwargs):
        __opts__[u'test'] = True
    else:
        __opts__[u'test'] = __opts__.get(u'test', None)
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    st_.opts[u'state_top'] = os.path.join(u'salt://', topfn)
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get(u'extra_filerefs', u''),
                __opts__.get(u'extra_filerefs', u'')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get(u'roster', u'flat'))
    roster_grains = roster.opts[u'grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__[u'fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs[u'id_'],
            roster_grains)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__[u'hash_type'])
    cmd = u'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__[u'thin_dir'],
            test,
            trans_tar_sum,
            __opts__[u'hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__[u'fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)
    single.shell.send(
            trans_tar,
            u'{0}/salt_state.tgz'.format(__opts__[u'thin_dir']))
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception as e:
        log.error(u"JSON Render failed for: %s\n%s", stdout, stderr)
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
    __opts__[u'grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    return st_.compile_highstate()


def show_lowstate():
    '''
    List out the low data that will be applied to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_lowstate
    '''
    __opts__[u'grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    return st_.compile_low_chunks()


def show_sls(mods, saltenv=u'base', test=None, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    __pillar__.update(kwargs.get(u'pillar', {}))
    __opts__[u'grains'] = __grains__
    opts = copy.copy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts[u'test'] = True
    else:
        opts[u'test'] = __opts__.get(u'test', None)
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    if isinstance(mods, six.string_types):
        mods = mods.split(u',')
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


def show_low_sls(mods, saltenv=u'base', test=None, **kwargs):
    '''
    Display the low state data from a specific sls or list of sls files on the
    master.

    .. versionadded:: 2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    __pillar__.update(kwargs.get(u'pillar', {}))
    __opts__[u'grains'] = __grains__

    opts = copy.copy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts[u'test'] = True
    else:
        opts[u'test'] = __opts__.get(u'test', None)
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
    if isinstance(mods, six.string_types):
        mods = mods.split(u',')
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
    __opts__[u'grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(
            __opts__,
            __pillar__,
            __salt__,
            __context__[u'fileclient'])
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
    __opts__[u'grains'] = __grains__

    # state.fun -> [state, fun]
    comps = fun.split(u'.')
    if len(comps) < 2:
        __context__[u'retcode'] = 1
        return u'Invalid function passed'

    # Create the low chunk, using kwargs as a base
    kwargs.update({u'state': comps[0],
                   u'fun': comps[1],
                   u'__id__': name,
                   u'name': name})

    opts = copy.deepcopy(__opts__)

    # Set test mode
    if salt.utils.test_mode(test=test, **kwargs):
        opts[u'test'] = True
    else:
        opts[u'test'] = __opts__.get(u'test', None)

    # Get the override pillar data
    __pillar__.update(kwargs.get(u'pillar', {}))

    # Create the State environment
    st_ = salt.client.ssh.state.SSHState(__opts__, __pillar__)

    # Verify the low chunk
    err = st_.verify_data(kwargs)
    if err:
        __context__[u'retcode'] = 1
        return err

    # Must be a list of low-chunks
    chunks = [kwargs]

    # Retrieve file refs for the state run, so we can copy relevant files down
    # to the minion before executing the state
    file_refs = salt.client.ssh.state.lowstate_file_refs(
            chunks,
            _merge_extra_filerefs(
                kwargs.get(u'extra_filerefs', u''),
                __opts__.get(u'extra_filerefs', u'')
                )
            )

    roster = salt.roster.Roster(__opts__, __opts__.get(u'roster', u'flat'))
    roster_grains = roster.opts[u'grains']

    # Create the tar containing the state pkg and relevant files.
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            __context__[u'fileclient'],
            chunks,
            file_refs,
            __pillar__,
            st_kwargs[u'id_'],
            roster_grains)

    # Create a hash so we can verify the tar on the target system
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__[u'hash_type'])

    # We use state.pkg to execute the "state package"
    cmd = u'state.pkg {0}/salt_state.tgz test={1} pkg_sum={2} hash_type={3}'.format(
            __opts__[u'thin_dir'],
            test,
            trans_tar_sum,
            __opts__[u'hash_type'])

    # Create a salt-ssh Single object to actually do the ssh work
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            fsclient=__context__[u'fileclient'],
            minion_opts=__salt__.minion_opts,
            **st_kwargs)

    # Copy the tar down
    single.shell.send(
            trans_tar,
            u'{0}/salt_state.tgz'.format(__opts__[u'thin_dir']))

    # Run the state.pkg command on the target
    stdout, stderr, _ = single.cmd_block()

    # Clean up our tar
    try:
        os.remove(trans_tar)
    except (OSError, IOError):
        pass

    # Read in the JSON data and return the data structure
    try:
        return json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception as e:
        log.error(u"JSON Render failed for: %s\n%s", stdout, stderr)
        log.error(str(e))

    # If for some reason the json load fails, return the stdout
    return stdout
