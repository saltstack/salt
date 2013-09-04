'''
Create ssh executor system
'''
# Import python libs
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
    single = salt.client.ssh.Single(
            __opts__,
            'state.pkg /tmp/salt_state.tgz test={0}'.format(test),
            **__salt__.kwargs)
    single.shell.send(
            trans_tar,
            '/tmp/salt_state.tgz')
    stdout, stderr = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)
