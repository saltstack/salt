'''
Create ssh executor system
'''
# Import python libs
import os
import tarfile
import tempfile
import json
import shutil

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh
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
    st_ = SSHHighState(__opts__, __pillar__, __salt__)
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
    file_refs = lowstate_file_refs(chunks)
    trans_tar = prep_trans_tar(__opts__, chunks, file_refs)
    single = salt.client.ssh.Single(
            __opts__,
            'state.pkg /tmp/salt_state.tgz test={0}'.format(test),
            **__salt__.kwargs)
    single.shell.send(
            trans_tar,
            '/tmp/salt_state.tgz')
    stdout, stderr = single.cmd_block()
    return json.loads(stdout, object_hook=salt.utils.decode_dict)


class SSHState(salt.state.State):
    '''
    Create a State object which wraps the SSH functions for state operations
    '''
    def __init__(self, opts, pillar=None, wrapper=None):
        self.wrapper = wrapper
        super(SSHState, self).__init__(opts, pillar)

    def load_modules(self, data=None):
        '''
        Load up the modules for remote compilation via ssh
        '''
        self.functions = self.wrapper
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)

    def check_refresh(self, data, ret):
        '''
        Stub out check_refresh
        '''
        return

    def module_refresh(self):
        '''
        Module refresh is not needed, stub it out
        '''
        return


class SSHHighState(salt.state.BaseHighState):
    '''
    Used to compile the highstate on the master
    '''
    stack = []

    def __init__(self, opts, pillar=None, wrapper=None):
        self.client = salt.fileclient.LocalClient(opts)
        salt.state.BaseHighState.__init__(self, opts)
        self.state = SSHState(opts, pillar, wrapper)
        self.matcher = salt.minion.Matcher(self.opts)


def lowstate_file_refs(chunks):
    '''
    Create a list of file ref objects to reconcile
    '''
    refs = {}
    for chunk in chunks:
        env = 'base'
        crefs = []
        for state in chunk:
            if state == '__env__':
                env = chunk[state]
            elif state.startswith('__'):
                continue
            crefs.extend(salt_refs(chunk[state]))
        if crefs:
            if not env in refs:
                refs[env] = []
            refs[env].append(crefs)
    return refs


def salt_refs(data):
    '''
    Pull salt file references out of the states
    '''
    proto = 'salt://'
    ret = []
    if isinstance(data, str):
        if data.startswith(proto):
            return [data]
    if isinstance(data, list):
        for comp in data:
            if isinstance(comp, str):
                if comp.startswith(proto):
                    ret.append(comp)
    return ret


def prep_trans_tar(opts, chunks, file_refs):
    '''
    Generate the execution package from the env file refs and a low state
    data structure
    '''
    gendir = tempfile.mkdtemp()
    trans_tar = salt.utils.mkstemp()
    file_client = salt.fileclient.LocalClient(opts)
    lowfn = os.path.join(gendir, 'lowstate.json')
    with open(lowfn, 'w+') as fp_:
        fp_.write(json.dumps(chunks))
    for env in file_refs:
        env_root = os.path.join(gendir, env)
        if not os.path.isdir(env_root):
            os.makedirs(env_root)
        for ref in file_refs[env]:
            for name in ref:
                short = name[7:]
                path = file_client.cache_file(name, env)
                if path:
                    tgt = os.path.join(env_root, short)
                    tgt_dir = os.path.dirname(tgt)
                    if not os.path.isdir(tgt_dir):
                        os.makedirs(tgt_dir)
                    shutil.copy(path, tgt)
                    break
                files = file_client.cache_dir(name, env, True)
                if files:
                    for file in files:
                        tgt = os.path.join(
                                env_root,
                                short,
                                file[file.find(short) + len(short):],
                                )
                        tgt_dir = os.path.dirname(tgt)
                        if not os.path.isdir(tgt_dir):
                            os.makedirs(tgt_dir)
                        shutil.copy(path, tgt)
                    break
    cwd = os.getcwd()
    os.chdir(gendir)
    with tarfile.open(trans_tar, 'w:gz') as tfp:
        for root, dirs, files in os.walk(gendir):
            for name in files:
                full = os.path.join(root, name)
                tfp.add(full[len(gendir):].lstrip(os.sep))
    os.chdir(cwd)
    shutil.rmtree(gendir)
    return trans_tar
