# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
# Import python libs
import os
import tarfile
import tempfile
import json
import shutil
from contextlib import closing

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh
import salt.utils
import salt.utils.thin
import salt.roster
import salt.state
import salt.loader
import salt.minion


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
        locals_ = salt.loader.minion_mods(self.opts)
        self.states = salt.loader.states(self.opts, locals_)
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

    def load_dynamic(self, matches):
        '''
        Stub out load_dynamic
        '''
        return


def lowstate_file_refs(chunks):
    '''
    Create a list of file ref objects to reconcile
    '''
    refs = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        saltenv = 'base'
        crefs = []
        for state in chunk:
            if state == '__env__':
                saltenv = chunk[state]
            elif state.startswith('__'):
                continue
            crefs.extend(salt_refs(chunk[state]))
        if crefs:
            if not saltenv in refs:
                refs[saltenv] = []
            refs[saltenv].append(crefs)
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
    Generate the execution package from the saltenv file refs and a low state
    data structure
    '''
    gendir = tempfile.mkdtemp()
    trans_tar = salt.utils.mkstemp()
    file_client = salt.fileclient.LocalClient(opts)
    lowfn = os.path.join(gendir, 'lowstate.json')
    with open(lowfn, 'w+') as fp_:
        fp_.write(json.dumps(chunks))
    for saltenv in file_refs:
        env_root = os.path.join(gendir, saltenv)
        if not os.path.isdir(env_root):
            os.makedirs(env_root)
        for ref in file_refs[saltenv]:
            for name in ref:
                short = name[7:]
                path = file_client.cache_file(name, saltenv)
                if path:
                    tgt = os.path.join(env_root, short)
                    tgt_dir = os.path.dirname(tgt)
                    if not os.path.isdir(tgt_dir):
                        os.makedirs(tgt_dir)
                    shutil.copy(path, tgt)
                    break
                files = file_client.cache_dir(name, saltenv)
                if files:
                    for filename in files:
                        tgt = os.path.join(
                                env_root,
                                short,
                                filename[filename.find(short) + len(short) + 1:],
                                )
                        tgt_dir = os.path.dirname(tgt)
                        if not os.path.isdir(tgt_dir):
                            os.makedirs(tgt_dir)
                        shutil.copy(filename, tgt)
                    break
    cwd = os.getcwd()
    os.chdir(gendir)
    with closing(tarfile.open(trans_tar, 'w:gz')) as tfp:
        for root, dirs, files in os.walk(gendir):
            for name in files:
                full = os.path.join(root, name)
                tfp.add(full[len(gendir):].lstrip(os.sep))
    os.chdir(cwd)
    shutil.rmtree(gendir)
    return trans_tar
