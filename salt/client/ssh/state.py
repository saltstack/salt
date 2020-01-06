# -*- coding: utf-8 -*-
'''
Create ssh executor system
'''
from __future__ import absolute_import, print_function
# Import python libs
import logging
import os
import tarfile
import tempfile
import shutil
from contextlib import closing

# Import salt libs
import salt.client.ssh.shell
import salt.client.ssh
import salt.utils.files
import salt.utils.json
import salt.utils.path
import salt.utils.stringutils
import salt.utils.thin
import salt.utils.url
import salt.utils.verify
import salt.roster
import salt.state
import salt.loader
import salt.minion

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


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
        self.serializers = salt.loader.serializers(self.opts)
        locals_ = salt.loader.minion_mods(self.opts, utils=self.utils)
        self.states = salt.loader.states(self.opts, locals_, self.utils, self.serializers)
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
        self.matchers = salt.loader.matchers(self.opts)
        self.tops = salt.loader.tops(self.opts)

        self._pydsl_all_decls = {}
        self._pydsl_render_stack = []

    def push_active(self):
        salt.state.HighState.stack.append(self)

    def load_dynamic(self, matches):
        '''
        Stub out load_dynamic
        '''
        return

    def _master_tops(self):
        '''
        Evaluate master_tops locally
        '''
        if 'id' not in self.opts:
            log.error('Received call for external nodes without an id')
            return {}
        if not salt.utils.verify.valid_id(self.opts, self.opts['id']):
            return {}
        # Evaluate all configured master_tops interfaces

        grains = {}
        ret = {}

        if 'grains' in self.opts:
            grains = self.opts['grains']
        for fun in self.tops:
            if fun not in self.opts.get('master_tops', {}):
                continue
            try:
                ret.update(self.tops[fun](opts=self.opts, grains=grains))
            except Exception as exc:  # pylint: disable=broad-except
                # If anything happens in the top generation, log it and move on
                log.error(
                    'Top function %s failed with error %s for minion %s',
                    fun, exc, self.opts['id']
                )
        return ret


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
        if saltenv not in refs:
            refs[saltenv] = []
        if crefs:
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
    if isinstance(data, six.string_types):
        if data.startswith(proto) and data not in ret:
            ret.append(data)
    if isinstance(data, list):
        for comp in data:
            salt_refs(comp, ret)
    if isinstance(data, dict):
        for comp in data:
            salt_refs(data[comp], ret)
    return ret


def prep_trans_tar(file_client, chunks, file_refs, pillar=None, id_=None, roster_grains=None):
    '''
    Generate the execution package from the saltenv file refs and a low state
    data structure
    '''
    gendir = tempfile.mkdtemp()
    trans_tar = salt.utils.files.mkstemp()
    lowfn = os.path.join(gendir, 'lowstate.json')
    pillarfn = os.path.join(gendir, 'pillar.json')
    roster_grainsfn = os.path.join(gendir, 'roster_grains.json')
    sync_refs = [
            [salt.utils.url.create('_modules')],
            [salt.utils.url.create('_states')],
            [salt.utils.url.create('_grains')],
            [salt.utils.url.create('_renderers')],
            [salt.utils.url.create('_returners')],
            [salt.utils.url.create('_output')],
            [salt.utils.url.create('_utils')],
            ]
    with salt.utils.files.fopen(lowfn, 'w+') as fp_:
        salt.utils.json.dump(chunks, fp_)
    if pillar:
        with salt.utils.files.fopen(pillarfn, 'w+') as fp_:
            salt.utils.json.dump(pillar, fp_)
    if roster_grains:
        with salt.utils.files.fopen(roster_grainsfn, 'w+') as fp_:
            salt.utils.json.dump(roster_grains, fp_)

    if id_ is None:
        id_ = ''
    try:
        cachedir = os.path.join('salt-ssh', id_).rstrip(os.sep)
    except AttributeError:
        # Minion ID should always be a str, but don't let an int break this
        cachedir = os.path.join('salt-ssh', six.text_type(id_)).rstrip(os.sep)

    for saltenv in file_refs:
        # Location where files in this saltenv will be cached
        cache_dest_root = os.path.join(cachedir, 'files', saltenv)
        file_refs[saltenv].extend(sync_refs)
        env_root = os.path.join(gendir, saltenv)
        if not os.path.isdir(env_root):
            os.makedirs(env_root)
        for ref in file_refs[saltenv]:
            for name in ref:
                short = salt.utils.url.parse(name)[0].lstrip('/')
                cache_dest = os.path.join(cache_dest_root, short)
                try:
                    path = file_client.cache_file(name, saltenv, cachedir=cachedir)
                except IOError:
                    path = ''
                if path:
                    tgt = os.path.join(env_root, short)
                    tgt_dir = os.path.dirname(tgt)
                    if not os.path.isdir(tgt_dir):
                        os.makedirs(tgt_dir)
                    shutil.copy(path, tgt)
                    continue
                try:
                    files = file_client.cache_dir(name, saltenv, cachedir=cachedir)
                except IOError:
                    files = ''
                if files:
                    for filename in files:
                        fn = filename[len(file_client.get_cachedir(cache_dest)):].strip('/')
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
    try:
        # cwd may not exist if it was removed but salt was run from it
        cwd = os.getcwd()
    except OSError:
        cwd = None
    os.chdir(gendir)
    with closing(tarfile.open(trans_tar, 'w:gz')) as tfp:
        for root, dirs, files in salt.utils.path.os_walk(gendir):
            for name in files:
                full = os.path.join(root, name)
                tfp.add(full[len(gendir):].lstrip(os.sep))
    if cwd:
        os.chdir(cwd)
    shutil.rmtree(gendir)
    return trans_tar
