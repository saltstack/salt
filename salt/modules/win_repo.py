# -*- coding: utf-8 -*-
r'''
Module to manage Windows software repo on a Standalone Minion

``file_client: local`` must be set in the minion config file.

For documentation on Salt's Windows Repo feature, see :ref:`here
<windows-package-manager>`.
'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import logging
import os

# Import salt libs
import salt.output
import salt.utils.functools
import salt.utils.path
import salt.utils.platform
import salt.loader
import salt.template
from salt.exceptions import CommandExecutionError, SaltRenderError

# All the "unused" imports here are needed for the imported winrepo runner code
# pylint: disable=unused-import
from salt.runners.winrepo import (
    genrepo as _genrepo,
    update_git_repos as _update_git_repos,
    PER_REMOTE_OVERRIDES,
    PER_REMOTE_ONLY
)
from salt.ext import six
try:
    import msgpack
except ImportError:
    import msgpack_pure as msgpack  # pylint: disable=import-error
import salt.utils.gitfs
# pylint: enable=unused-import

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'winrepo'


def __virtual__():
    '''
    Set the winrepo module if the OS is Windows
    '''
    if salt.utils.platform.is_windows():
        global _genrepo, _update_git_repos
        _genrepo = salt.utils.functools.namespaced_function(_genrepo, globals())
        _update_git_repos = \
            salt.utils.functools.namespaced_function(_update_git_repos, globals())
        return __virtualname__
    return (False, 'This module only works on Windows.')


def _get_local_repo_dir(saltenv='base'):
    winrepo_source_dir = __opts__['winrepo_source_dir']
    dirs = []
    dirs.append(salt.syspaths.CACHE_DIR)
    dirs.extend(['minion', 'files'])
    dirs.append(saltenv)
    dirs.extend(winrepo_source_dir[7:].strip('/').split('/'))
    return os.sep.join(dirs)


def genrepo():
    r'''
    Generate winrepo_cachefile based on sls files in the winrepo_dir

    CLI Example:

    .. code-block:: bash

        salt-call winrepo.genrepo
    '''
    return _genrepo(opts=__opts__, fire_event=False)


def update_git_repos(clean=False):
    '''
    Checkout git repos containing :ref:`Windows Software Package Definitions
    <windows-package-manager>`.

    .. important::
        This function requires `Git for Windows`_ to be installed in order to
        work. When installing, make sure to select an installation option which
        permits the git executable to be run from the Command Prompt.

    .. _`Git for Windows`: https://git-for-windows.github.io/

    clean : False
        Clean repo cachedirs which are not configured under
        :conf_minion:`winrepo_remotes`.

        .. note::
            This option only applies if either pygit2_ or GitPython_ is
            installed into Salt's bundled Python.

        .. warning::
            This argument should not be set to ``True`` if a mix of git and
            non-git repo definitions are being used, as it will result in the
            non-git repo definitions being removed.

        .. versionadded:: 2015.8.0

        .. _GitPython: https://github.com/gitpython-developers/GitPython
        .. _pygit2: https://github.com/libgit2/pygit2

    CLI Example:

    .. code-block:: bash

        salt-call winrepo.update_git_repos
    '''
    if not salt.utils.path.which('git'):
        raise CommandExecutionError(
            'Git for Windows is not installed, or not configured to be '
            'accessible from the Command Prompt'
        )
    return _update_git_repos(opts=__opts__, clean=clean, masterless=True)


def show_sls(name, saltenv='base'):
    r'''
    .. versionadded:: 2015.8.0
    Display the rendered software definition from a specific sls file in the
    local winrepo cache. This will parse all Jinja. Run pkg.refresh_db to pull
    the latest software definitions from the master.

    .. note::
        This function does not ask a master for an sls file to render. Instead
        it directly processes the file specified in `name`

    Args:
        name str: The name/path of the package you want to view. This can be the
        full path to a file on the minion file system or a file on the local
        minion cache.

        saltenv str: The default environment is ``base``

    Returns:
        dict: Returns a dictionary containing the rendered data structure

    .. note::
        To use a file from the minion cache start from the local winrepo root
        (``C:\salt\var\cache\salt\minion\files\base\win\repo-ng``). If you have
        ``.sls`` files organized in subdirectories you'll have to denote them
        with ``.``. For example, if you have a ``test`` directory in the winrepo
        root with a ``gvim.sls`` file inside, would target that file like so:
        ``test.gvim``. Directories can be targeted as well as long as they
        contain an ``init.sls`` inside. For example, if you have a ``node``
        directory with an ``init.sls`` inside, target that like so: ``node``.

    CLI Example:

    .. code-block:: bash

        salt '*' winrepo.show_sls gvim
        salt '*' winrepo.show_sls test.npp
        salt '*' winrepo.show_sls C:\test\gvim.sls
    '''
    # Passed a filename
    if os.path.exists(name):
        sls_file = name

    # Use a winrepo path
    else:
        # Get the location of the local repo
        repo = _get_local_repo_dir(saltenv)

        # Add the sls file name to the path
        repo = repo.split('\\')
        definition = name.split('.')
        repo.extend(definition)

        # Check for the sls file by name
        sls_file = '{0}.sls'.format(os.sep.join(repo))
        if not os.path.exists(sls_file):

            # Maybe it's a directory with an init.sls
            sls_file = '{0}\\init.sls'.format(os.sep.join(repo))
            if not os.path.exists(sls_file):

                # It's neither, return
                return 'Software definition {0} not found'.format(name)

    # Load the renderer
    renderers = salt.loader.render(__opts__, __salt__)
    config = {}

    # Run the file through the renderer
    try:
        config = salt.template.compile_template(
            sls_file,
            renderers,
            __opts__['renderer'],
            __opts__['renderer_blacklist'],
            __opts__['renderer_whitelist'])

    # Return the error if any
    except SaltRenderError as exc:
        log.debug('Failed to compile %s.', sls_file)
        log.debug('Error: %s.', exc)
        config['Message'] = 'Failed to compile {0}'.format(sls_file)
        config['Error'] = '{0}'.format(exc)

    return config
