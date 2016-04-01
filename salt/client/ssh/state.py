# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
from __future__ import absolute_import
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
import salt.utils.url
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

    def load_modules(self, data=None, proxy=None):
        '''
        Load up the modules for remote compilation via ssh
        '''
        self.functions = self.wrapper
        self.utils = salt.loader.utils(self.opts)
        locals_ = salt.loader.minion_mods(self.opts, utils=self.utils)
        self.states = salt.loader.states(self.opts, locals_, self.utils)
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

    def __init__(self, opts, pillar=None, wrapper=None, fsclient=None):
        self.client = fsclient
        salt.state.BaseHighState.__init__(self, opts)
        self.state = SSHState(opts, pillar, wrapper)
        self.matcher = salt.minion.Matcher(self.opts)

    def load_dynamic(self, matches):
        '''
        Stub out load_dynamic
        '''
        return


def lowstate_file_refs(chunks, extras=''):
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
            if saltenv not in refs:
                refs[saltenv] = []
            refs[saltenv].append(crefs)
    if extras:
        extra_refs = extras.split(',')
        if extra_refs:
            for env in refs:
                for x in extra_refs:
                    refs[env].append([x])
    return refs


def salt_refs(data, ret=None):
    '''
    Pull salt file references out of the states
    '''
    proto = 'salt://'
    if ret is None:
        ret = []
    if isinstance(data, str):
        if data.startswith(proto) and data not in ret:
            ret.append(data)
    if isinstance(data, list):
        for comp in data:
            salt_refs(comp, ret)
    if isinstance(data, dict):
        for comp in data:
            salt_refs(data[comp], ret)
    return ret


def prep_trans_tar(file_client, chunks, file_refs, pillar=None, id_=None):
    '''
    Generate the execution package from the saltenv file refs and a low state
    data structure
    '''
    gendir = tempfile.mkdtemp()
    trans_tar = salt.utils.mkstemp()
    lowfn = os.path.join(gendir, 'lowstate.json')
    pillarfn = os.path.join(gendir, 'pillar.json')
    sync_refs = [
            [salt.utils.url.create('_modules')],
            [salt.utils.url.create('_states')],
            [salt.utils.url.create('_grains')],
            [salt.utils.url.create('_renderers')],
            [salt.utils.url.create('_returners')],
            [salt.utils.url.create('_output')],
            [salt.utils.url.create('_utils')],
            ]
    with salt.utils.fopen(lowfn, 'w+') as fp_:
        fp_.write(json.dumps(chunks))
    if pillar:
        with salt.utils.fopen(pillarfn, 'w+') as fp_:
            fp_.write(json.dumps(pillar))
    cachedir = os.path.join('salt-ssh', id_)
    for saltenv in file_refs:
        file_refs[saltenv].extend(sync_refs)
        env_root = os.path.join(gendir, saltenv)
        if not os.path.isdir(env_root):
            os.makedirs(env_root)
        for ref in file_refs[saltenv]:
            for name in ref:
                short = salt.utils.url.parse(name)[0]
                path = file_client.cache_file(name, saltenv, cachedir=cachedir)
                if path:
                    tgt = os.path.join(env_root, short)
                    tgt_dir = os.path.dirname(tgt)
                    if not os.path.isdir(tgt_dir):
                        os.makedirs(tgt_dir)
                    shutil.copy(path, tgt)
                    continue
                files = file_client.cache_dir(name, saltenv, cachedir=cachedir)
                if files:
                    for filename in files:
                        fn = filename[filename.find(short) + len(short):]
                        if fn.startswith('/'):
                            fn = fn.strip('/')
                        tgt = os.path.join(
                                env_root,
                                short,
                                fn,
                                )
                        tgt_dir = os.path.dirname(tgt)
                        if not os.path.isdir(tgt_dir):
                            os.makedirs(tgt_dir)
                        shutil.copy(filename, tgt)
                    continue
    try:  # cwd may not exist if it was removed but salt was run from it
        cwd = os.getcwd()
    except OSError:
        cwd = None
    os.chdir(gendir)
    with closing(tarfile.open(trans_tar, 'w:gz')) as tfp:
        for root, dirs, files in os.walk(gendir):
            for name in files:
                full = os.path.join(root, name)
                tfp.add(full[len(gendir):].lstrip(os.sep))
    if cwd:
        os.chdir(cwd)
    shutil.rmtree(gendir)
    return trans_tar
