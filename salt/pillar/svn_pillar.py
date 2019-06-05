# -*- coding: utf-8 -*-
'''
Clone a remote SVN repository and use the filesystem as a Pillar source

This external Pillar source can be configured in the master config file like
so:

.. code-block:: yaml

    ext_pillar:
      - svn: trunk svn://svnserver/repo root=subdirectory

The `root=` parameter is optional and used to set the subdirectory from where
to look for Pillar files (such as ``top.sls``).

.. versionchanged:: 2014.7.0
    The optional ``root`` parameter will be added.

Note that this is not the same thing as configuring pillar data using the
:conf_master:`pillar_roots` parameter. The branch referenced in the
:conf_master:`ext_pillar` entry above (``master``), would evaluate to the
``base`` environment, so this branch needs to contain a ``top.sls`` with a
``base`` section in it, like this:

.. code-block:: yaml

    base:
      '*':
        - foo

To use other environments from the same SVN repo as svn_pillar sources, just
add additional lines, like so:

.. code-block:: yaml

    ext_pillar:
      - svn: trunk svn://svnserver/repo
      - svn: dev svn://svnserver/repo

In this case, the ``dev`` branch would need its own ``top.sls`` with a ``dev``
section in it, like this:

.. code-block:: yaml

    dev:
      '*':
        - bar
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
from copy import deepcopy
import logging
import os
import hashlib

# Import third party libs
HAS_SVN = False
try:
    import pysvn
    HAS_SVN = True
    CLIENT = pysvn.Client()
except ImportError:
    pass

# Import salt libs
from salt.pillar import Pillar

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'svn'


def __virtual__():
    ext_pillar_sources = [x for x in __opts__.get('ext_pillar', [])]
    if not any(['svn' in x for x in ext_pillar_sources]):
        return False
    if not HAS_SVN:
        log.error('SVN-based ext_pillar is enabled in configuration but '
                  'could not be loaded, is pysvn installed?')
        return False
    return __virtualname__


class SvnPillar(object):
    '''
    Deal with the remote SVN repository for Pillar
    '''

    def __init__(self, branch, repo_location, root, opts):
        '''
        Try to initialize the SVN repo object
        '''
        repo_hash = hashlib.md5(repo_location).hexdigest()
        repo_dir = os.path.join(opts['cachedir'], 'pillar_svnfs', repo_hash)

        self.branch = branch
        self.root = root
        self.repo_dir = repo_dir
        self.repo_location = repo_location

        if not os.path.isdir(repo_dir):
            os.makedirs(repo_dir)
            log.debug('Checking out fileserver for svn_pillar module')
            try:
                CLIENT.checkout(repo_location, repo_dir)
            except pysvn.ClientError:
                log.error(
                    'Failed to initialize svn_pillar %s %s',
                    repo_location, repo_dir
                )

    def update(self):
        try:
            log.debug('Updating fileserver for svn_pillar module')
            CLIENT.update(self.repo_dir)
        except pysvn.ClientError as exc:
            log.error(
                'Unable to fetch the latest changes from remote %s: %s',
                self.repo_location, exc
            )

    def pillar_dir(self):
        '''
        Returns the directory of the pillars (repo cache + branch + root)
        '''
        repo_dir = self.repo_dir
        root = self.root
        branch = self.branch
        if branch == 'trunk' or branch == 'base':
            working_dir = os.path.join(repo_dir, 'trunk', root)
            if not os.path.isdir(working_dir):
                log.error('Could not find %s/trunk/%s', self.repo_location, root)
            else:
                return os.path.normpath(working_dir)
        working_dir = os.path.join(repo_dir, 'branches', branch, root)
        if os.path.isdir(working_dir):
            return os.path.normpath(working_dir)
        working_dir = os.path.join(working_dir, 'tags', branch, root)
        if os.path.isdir(working_dir):
            return os.path.normpath(working_dir)
        log.error('Could not find %s/branches/%s/%s', self.repo_location, branch, root)
        return repo_dir


def _extract_key_val(kv, delimiter='='):
    '''Extract key and value from key=val string.

    Example:
    >>> _extract_key_val('foo=bar')
    ('foo', 'bar')
    '''
    pieces = kv.split(delimiter)
    key = pieces[0]
    val = delimiter.join(pieces[1:])
    return key, val


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               repo_string):
    '''
    Execute a command and read the output as YAML
    '''
    # split the branch, repo name and optional extra (key=val) parameters.
    options = repo_string.strip().split()
    branch = options[0]
    repo_location = options[1]
    root = ''

    for extraopt in options[2:]:
        # Support multiple key=val attributes as custom parameters.
        DELIM = '='
        if DELIM not in extraopt:
            log.error('Incorrectly formatted extra parameter. '
                      'Missing \'%s\': %s', DELIM, extraopt)
        key, val = _extract_key_val(extraopt, DELIM)
        if key == 'root':
            root = val
        else:
            log.warning('Unrecognized extra parameter: %s', key)

    svnpil = SvnPillar(branch, repo_location, root, __opts__)

    # environment is "different" from the branch
    branch = (branch == 'trunk' and 'base' or branch)

    pillar_dir = svnpil.pillar_dir()
    log.debug("[pillar_roots][%s] = %s", branch, pillar_dir)

    # Don't recurse forever-- the Pillar object will re-call the ext_pillar
    # function
    if __opts__['pillar_roots'].get(branch, []) == [pillar_dir]:
        return {}
    svnpil.update()
    opts = deepcopy(__opts__)
    opts['pillar_roots'][branch] = [pillar_dir]
    pil = Pillar(opts, __grains__, minion_id, branch)
    return pil.compile_pillar(ext=False)
