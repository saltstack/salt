# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
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

log = logging.getLogger(__name__)


def sls(mods, saltenv='base', test=None, exclude=None, env=None, **kwargs):
    '''
    Create the seed file for a state.sls run
    '''
    __opts__['grains'] = __grains__
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    __pillar__.update(kwargs.get('pillar', {}))
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    if isinstance(mods, str):
        mods = mods.split(',')
    high_data, errors = st_.render_highstate({saltenv: mods})
    if exclude:
        if isinstance(exclude, str):
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
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks, kwargs.get('extra_filerefs', ''))
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs,
            __pillar__)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg /tmp/.salt/salt_state.tgz test={0} pkg_sum={1} hash_type={2}'.format(
            test,
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            **__salt__.kwargs)
    single.shell.send(
            trans_tar,
            '/tmp/.salt/salt_state.tgz')
    stdout, stderr, _ = single.cmd_block()
    try:
        return json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception, e:
        log.error("JSON Render failed for: {0}".format(stdout))
        log.error(str(e))
    return stdout


def low(data, **kwargs):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    '''
    __opts__['grains'] = __grains__
    chunks = [data]
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    err = st_.verify_data(data)
    if err:
        return err
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks, kwargs.get('extra_filerefs', ''))
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs,
            __pillar__)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg /tmp/.salt/salt_state.tgz pkg_sum={0} hash_type={1}'.format(
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            **__salt__.kwargs)
    single.shell.send(
            trans_tar,
            '/tmp/.salt/salt_state.tgz')
    stdout, stderr, _ = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


def high(data, **kwargs):
    '''
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    chunks = st_.state.compile_high_data(high)
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks, kwargs.get('extra_filerefs', ''))
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs,
            __pillar__)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg /tmp/.salt/salt_state.tgz pkg_sum={0} hash_type={1}'.format(
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            **__salt__.kwargs)
    single.shell.send(
            trans_tar,
            '/tmp/.salt/salt_state.tgz')
    stdout, stderr, _ = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


def highstate(test=None, **kwargs):
    '''
    Retrieve the state data from the salt master for this minion and execute it

    CLI Example:

    .. code-block:: bash

        salt '*' state.highstate

        salt '*' state.highstate exclude=sls_to_exclude
        salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks, kwargs.get('extra_filerefs', ''))
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs,
            __pillar__)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg /tmp/.salt/salt_state.tgz test={0} pkg_sum={1} hash_type={2}'.format(
            test,
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            **__salt__.kwargs)
    single.shell.send(
            trans_tar,
            '/tmp/.salt/salt_state.tgz')
    stdout, stderr, _ = single.cmd_block()
    try:
        stdout = json.loads(stdout, object_hook=salt.utils.decode_dict)
    except Exception, e:
        log.error("JSON Render failed for: {0}".format(stdout))
        log.error(str(e))
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
    __opts__['grains'] = __grains__
    if salt.utils.test_mode(test=test, **kwargs):
        __opts__['test'] = True
    else:
        __opts__['test'] = __opts__.get('test', None)
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    st_.opts['state_top'] = os.path.join('salt://', topfn)
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks, kwargs.get('extra_filerefs', ''))
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs,
            __pillar__)
    trans_tar_sum = salt.utils.get_hash(trans_tar, __opts__['hash_type'])
    cmd = 'state.pkg /tmp/.salt/salt_state.tgz test={0} pkg_sum={1} hash_type={2}'.format(
            test,
            trans_tar_sum,
            __opts__['hash_type'])
    single = salt.client.ssh.Single(
            __opts__,
            cmd,
            **__salt__.kwargs)
    single.shell.send(
            trans_tar,
            '/tmp/.salt/salt_state.tgz')
    stdout, stderr, _ = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


def show_highstate():
    '''
    Retrieve the highstate data from the salt master and display it

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_highstate
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    return st_.compile_highstate()


def show_lowstate():
    '''
    List out the low data that will be applied to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_lowstate
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    return st_.compile_low_chunks()


def show_sls(mods, saltenv='base', test=None, env=None, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    __opts__['grains'] = __grains__
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    opts = copy.copy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
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


def show_top():
    '''
    Return the top data that the minion will use for a highstate

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_top
    '''
    __opts__['grains'] = __grains__
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    top_data = st_.get_top()
    errors = []
    errors += st_.verify_tops(top_data)
    if errors:
        return errors
    matches = st_.top_matches(top_data)
    return matches
