# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
# Import python libs
import os
import copy
import json

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh.state
import salt.utils
import salt.utils.thin
import salt.roster
import salt.state
import salt.loader
import salt.minion


def sls(mods, env='base', test=None, exclude=None, **kwargs):
    '''
    Create the seed file for a state.sls run
    '''
    __pillar__.update(kwargs.get('pillar', {}))
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    if isinstance(mods, str):
        mods = mods.split(',')
    high, errors = st_.render_highstate({env: mods})
    if exclude:
        if isinstance(exclude, str):
            exclude = exclude.split(',')
        if '__exclude__' in high:
            high['__exclude__'].extend(exclude)
        else:
            high['__exclude__'] = exclude
    high, ext_errors = st_.state.reconcile_extend(high)
    errors += ext_errors
    errors += st_.state.verify_high(high)
    if errors:
        return errors
    high, req_in_errors = st_.state.requisite_in(high)
    errors += req_in_errors
    high = st_.state.apply_exclude(high)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    # Compile and verify the raw chunks
    chunks = st_.state.compile_high_data(high)
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs)
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
    stdout, stderr = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


def low(data):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    '''
    chunks = [data]
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    err = st_.verify_data(data)
    if err:
        return err
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs)
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
    stdout, stderr = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


def high(data):
    '''
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    chunks = st_.state.compile_high_data(high)
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs)
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
    stdout, stderr = single.cmd_block()
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
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs)
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
    stdout, stderr = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


def top(topfn, test=None, **kwargs):
    '''
    Execute a specific top file instead of the default

    CLI Example:

    .. code-block:: bash

        salt '*' state.top reverse_top.sls
        salt '*' state.top reverse_top.sls exclude=sls_to_exclude
        salt '*' state.top reverse_top.sls exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    if salt.utils.test_mode(test=test, **kwargs):
        __opts__['test'] = True
    else:
        __opts__['test'] = __opts__.get('test', None)
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    st_.opts['state_top'] = os.path.join('salt://', topfn)
    chunks = st_.compile_low_chunks()
    file_refs = salt.client.ssh.state.lowstate_file_refs(chunks)
    trans_tar = salt.client.ssh.state.prep_trans_tar(
            __opts__,
            chunks,
            file_refs)
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
    stdout, stderr = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


def show_highstate():
    '''
    Retrieve the highstate data from the salt master and display it

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_highstate
    '''
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    return st_.compile_highstate()


def show_lowstate():
    '''
    List out the low data that will be applied to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_lowstate
    '''
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    return st_.compile_low_chunks()


def show_sls(mods, env='base', test=None, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    opts = copy.copy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    high, errors = st_.render_highstate({env: mods})
    high, ext_errors = st_.state.reconcile_extend(high)
    errors += ext_errors
    errors += st_.state.verify_high(high)
    if errors:
        return errors
    high, req_in_errors = st_.state.requisite_in(high)
    errors += req_in_errors
    high = st_.state.apply_exclude(high)
    # Verify that the high data is structurally sound
    if errors:
        return errors
    return high


def show_top():
    '''
    Return the top data that the minion will use for a highstate

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_top
    '''
    st_ = salt.client.ssh.state.SSHHighState(__opts__, __pillar__, __salt__)
    top = st_.get_top()
    errors = []
    errors += st_.verify_tops(top)
    if errors:
        return errors
    matches = st_.top_matches(top)
    return matches
