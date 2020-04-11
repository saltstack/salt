# -*- coding: utf-8 -*-
"""
Use a git repository as a Pillar source
---------------------------------------

This external pillar allows for a Pillar top file and Pillar SLS files to be
sourced from a git repository.

However, since git_pillar does not have an equivalent to the
:conf_master:`pillar_roots` parameter, configuration is slightly different. A
Pillar top file is required to be in the git repository and must still contain
the relevant environment, like so:

.. code-block:: yaml

    base:
      '*':
        - foo

The branch/tag which maps to that environment must then be specified along with
the repo's URL. Configuration details can be found below.

.. important::
    Each branch/tag used for git_pillar must have its own top file. This is
    different from how the top file works when configuring :ref:`States
    <states-tutorial>`. The reason for this is that each git_pillar branch/tag
    is processed separately from the rest. Therefore, if the ``qa`` branch is
    to be used for git_pillar, it would need to have its own top file, with the
    ``qa`` environment defined within it, like this:

    .. code-block:: yaml

        qa:
          'dev-*':
            - bar

    Additionally, while git_pillar allows for the branch/tag to be overridden
    (see :ref:`here <git-pillar-env-remap>`), keep in
    mind that the top file must reference the actual environment name. It is
    common practice to make the environment in a git_pillar top file match the
    branch/tag name, but when remapping, the environment of course no longer
    matches the branch/tag, and the top file needs to be adjusted accordingly.
    When expected Pillar values configured in git_pillar are missing, this is a
    common misconfiguration that may be to blame, and is a good first step in
    troubleshooting.

.. _git-pillar-configuration:

Configuring git_pillar for Salt
===============================

Beginning with Salt version 2015.8.0, pygit2_ is now supported in addition to
GitPython_. The requirements for GitPython_ and pygit2_ are the same as for
GitFS, as described :ref:`here <gitfs-dependencies>`.

.. important::
    git_pillar has its own set of global configuration parameters. While it may
    seem intuitive to use the global gitfs configuration parameters
    (:conf_master:`gitfs_base`, etc.) to manage git_pillar, this will not work.
    The main difference for this is the fact that the different components
    which use Salt's git backend code do not all function identically. For
    instance, in git_pillar it is necessary to specify which branch/tag to be
    used for git_pillar remotes. This is the reverse behavior from gitfs, where
    branches/tags make up your environments.

    See :ref:`here <git-pillar-config-opts>` for documentation on the
    git_pillar configuration options and their usage.

Here is an example git_pillar configuration:

.. code-block:: yaml

    ext_pillar:
      - git:
        # Use 'prod' instead of the branch name 'production' as the environment
        - production https://gitserver/git-pillar.git:
          - env: prod
        # Use 'dev' instead of the branch name 'develop' as the environment
        - develop https://gitserver/git-pillar.git:
          - env: dev
        # No per-remote config parameters (and no trailing colon), 'qa' will
        # be used as the environment
        - qa https://gitserver/git-pillar.git
        # SSH key authentication
        - master git@other-git-server:pillardata-ssh.git:
          # Pillar SLS files will be read from the 'pillar' subdirectory in
          # this repository
          - root: pillar
          - privkey: /path/to/key
          - pubkey: /path/to/key.pub
          - passphrase: CorrectHorseBatteryStaple
        # HTTPS authentication
        - master https://other-git-server/pillardata-https.git:
          - user: git
          - password: CorrectHorseBatteryStaple

The main difference between this and the old way of configuring git_pillar is
that multiple remotes can be configured under one ``git`` section under
:conf_master:`ext_pillar`. More than one ``git`` section can be used, but it is
not necessary. Remotes will be evaluated sequentially.

Per-remote configuration parameters are supported (similar to :ref:`gitfs
<gitfs-per-remote-config>`), and global versions of the git_pillar
configuration parameters can also be set.

.. _git-pillar-env-remap:

To remap a specific branch to a specific Pillar environment, use the ``env``
per-remote parameter:

.. code-block:: yaml

    ext_pillar:
      - git:
        - production https://gitserver/git-pillar.git:
          - env: prod

If ``__env__`` is specified as the branch name, then git_pillar will decide
which branch to use based on the following criteria:

- If the minion has a :conf_minion:`pillarenv` configured, it will use that
  pillar environment. (2016.11.2 and later)
- Otherwise, if the minion has an ``environment`` configured, it will use that
  environment.
- Otherwise, the master's :conf_master:`git_pillar_base` will be used.

.. note::
    The use of :conf_minion:`environment` to choose the pillar environment
    dates from a time before the :conf_minion:`pillarenv` parameter was added.
    In a future release, it will be ignored and either the minion's
    :conf_minion:`pillarenv` or the master's :conf_master:`git_pillar_base`
    will be used.

Here's an example of using ``__env__`` as the git_pillar environment:

.. code-block:: yaml

    ext_pillar:
      - git:
        - __env__ https://gitserver/git-pillar.git:
          - root: pillar

The corresponding Pillar top file would look like this:

.. code-block:: yaml

    "{{saltenv}}":
      '*':
        - bar

With the addition of pygit2_ support, git_pillar can now interact with
authenticated remotes. Authentication works just like in gitfs (as outlined in
the :ref:`Git Fileserver Backend Walkthrough <gitfs-authentication>`), only
with the global authenication parameter names prefixed with ``git_pillar``
instead of ``gitfs`` (e.g. :conf_master:`git_pillar_pubkey`,
:conf_master:`git_pillar_privkey`, :conf_master:`git_pillar_passphrase`, etc.).

.. note::
    The ``name`` parameter can be used to further differentiate between two
    remotes with the same URL and branch. When using two remotes with the same
    URL, the ``name`` option is required.

.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _pygit2: https://github.com/libgit2/pygit2

.. _git-pillar-multiple-remotes:

How Multiple Remotes Are Handled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As noted above, multiple remotes can be included in the same ``git`` ext_pillar
configuration. Consider the following:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001

    ext_pillar:
      - etcd: my_etcd_config
      - git:
        - master https://mydomain.tld/foo.git:
          - root: pillar
        - master https://mydomain.tld/bar.git
        - master https://mydomain.tld/baz.git
        - dev https://mydomain.tld/qux.git
      - git:
        - master https://mydomain.tld/abc.git
        - dev https://mydomain.tld/123.git

To understand how pillar data from these repos will be compiled, it's important
to know how Salt will process them. The following points should be kept in
mind:

1. Each ext_pillar is called separately from the others. So, in the above
   example, the :mod:`etcd <salt.pillar.etcd>` ext_pillar will be evaluated
   first, with the first group of git_pillar remotes evaluated next (and merged
   into the etcd pillar data). Lastly, the second group of git_pillar remotes
   will be evaluated, and then merged into the ext_pillar data evaluated before
   it.

2. Within a single group of git_pillar remotes, each remote will be evaluated in
   order, with results merged together as each remote is evaluated.

   .. note::
       Prior to the 2017.7.0 release, remotes would be evaluated in a
       non-deterministic order.

3. By default, when a repo is evaluated, other remotes' which share its pillar
   environment will have their files made available to the remote being
   processed.

The first point should be straightforward enough, but the second and third
could use some additional clarification.

First, point #2. In the first group of git_pillar remotes, the top file and
pillar SLS files in the ``foo`` remote will be evaluated first. The ``bar``
remote will be evaluated next, and its results will be merged into the pillar
data compiled when the ``foo`` remote was evaluated. As the subsequent remotes
are evaluated, their data will be merged in the same fashion.

But wait, don't these repositories belong to more than one pillar environments?
Well, yes. The default method of generating pillar data compiles pillar data
from all environments. This behavior can be overridden using a ``pillarenv``.
Setting a :conf_minion:`pillarenv` in the minion config file will make that
minion tell the master to ignore any pillar data from environments which don't
match that pillarenv. A pillarenv can also be specified for a given minion or
set of minions when :mod:`running states <salt.modules.state>`, by using the
``pillarenv`` argument. The CLI pillarenv will override one set in the minion
config file. So, assuming that a pillarenv of ``base`` was set for a minion, it
would not get any of the pillar variables configured in the ``qux`` remote,
since that remote is assigned to the ``dev`` environment. The only way to get
its pillar data would be to specify a pillarenv of ``dev``, which would mean
that it would then ignore any items from the ``base`` pillarenv. A more
detailed explanation of pillar environments can be found :ref:`here
<pillar-environments>`.

Moving on to point #3, and looking at the example ext_pillar configuration, as
the ``foo`` remote is evaluated, it will also have access to the files from the
``bar`` and ``baz`` remotes, since all three are assigned to the ``base``
pillar environment. So, if an SLS file referenced by the ``foo`` remotes's top
file does not exist in the ``foo`` remote, it will be searched for in the
``bar`` remote, followed by the ``baz`` remote. When it comes time to evaluate
the ``bar`` remote, SLS files referenced by the ``bar`` remote's top file will
first be looked for in the ``bar`` remote, followed by ``foo``, and ``baz``,
and when the ``baz`` remote is processed, SLS files will be looked for in
``baz``, followed by ``foo`` and ``bar``. This "failover" logic is called a
:ref:`directory overlay <file-roots-directory-overlay>`, and it is also used by
:conf_master:`file_roots` and :conf_minion`pillar_roots`. The ordering of which
remote is checked for SLS files is determined by the order they are listed.
First the remote being processed is checked, then the others that share the
same environment are checked. However, before the 2017.7.0 release, since
evaluation was unordered, the remote being processed would be checked, followed
in no specific order by the other repos which share the same environment.

Beginning with the 2017.7.0 release, this behavior of git_pillar remotes having
access to files in other repos which share the same environment can be disabled
by setting :conf_master:`git_pillar_includes` to ``False``. If this is done,
then all git_pillar remotes will only have access to their own SLS files.
Another way of ensuring that a git_pillar remote will not have access to SLS
files from other git_pillar remotes which share the same pillar environment is
to put them in a separate ``git`` section under ``ext_pillar``. Look again at
the example configuration above. In the second group of git_pillar remotes, the
``abc`` remote would not have access to the SLS files from the ``foo``,
``bar``, and ``baz`` remotes, and vice-versa.

.. _git-pillar-mountpoints:

Mountpoints
~~~~~~~~~~~

.. versionadded:: 2017.7.0

Assume the following pillar top file:

.. code-block:: yaml

    base:
      'web*':
        - common
        - web.server.nginx
        - web.server.appdata

Now, assume that you would like to configure the ``web.server.nginx`` and
``web.server.appdata`` SLS files in separate repos. This could be done using
the following ext_pillar configuration (assuming that
:conf_master:`git_pillar_includes` has not been set to ``False``):

.. code-block:: yaml

    ext_pillar:
      - git:
        - master https://mydomain.tld/pillar-common.git
        - master https://mydomain.tld/pillar-nginx.git
        - master https://mydomain.tld/pillar-appdata.git

However, in order to get the files in the second and third git_pillar remotes
to work, you would need to first create the directory structure underneath it
(i.e. place them underneath ``web/server/`` in the repository). This also makes
it tedious to reorganize the configuration, as changing ``web.server.nginx`` to
``web.nginx`` in the top file would require you to also move the SLS files in
the ``pillar-nginx`` up a directory level.

For these reasons, much like gitfs, git_pillar now supports a "mountpoint"
feature. Using the following ext_pillar configuration, the SLS files in the
second and third git_pillar remotes can be placed in the root of the git
repository:

.. code-block:: yaml

    ext_pillar:
      - git:
        - master https://mydomain.tld/pillar-common.git
        - master https://mydomain.tld/pillar-nginx.git:
          - mountpoint: web/server/
        - master https://mydomain.tld/pillar-appdata.git:
          - mountpoint: web/server/

Now, if the top file changed the SLS target from ``web.server.nginx``, instead
of reorganizing the git repository, you would just need to adjust the
mountpoint to ``web/`` (and restart the ``salt-master`` daemon).

.. note::
    - Leading and trailing slashes on the mountpoints are optional.
    - Use of the ``mountpoint`` feature requires that
      :conf_master:`git_pillar_includes` is not disabled.
    - Content from mounted git_pillar repos can only be referenced by a top
      file in the same pillar environment.
    - Salt versions prior to 2018.3.4 ignore the ``root`` parameter when
      ``mountpoint`` is set.

.. _git-pillar-all_saltenvs:

all_saltenvs
~~~~~~~~~~~~

.. versionadded:: 2018.3.4

When ``__env__`` is specified as the branch name, ``all_saltenvs`` per-remote configuration parameter overrides the logic Salt uses to map branches/tags to pillar environments (i.e. pillarenvs). This allows a single branch/tag to appear in all saltenvs. Example:

.. code-block:: yaml

    ext_pillar:
      - git:
        - __env__ https://mydomain.tld/top.git
          - all_saltenvs: master
        - __env__ https://mydomain.tld/pillar-nginx.git:
          - mountpoint: web/server/
        - __env__ https://mydomain.tld/pillar-appdata.git:
          - mountpoint: web/server/

.. _git_pillar_update_interval:

git_pillar_update_interval
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 3000

This option defines the default update interval (in seconds) for git_pillar
remotes. The update is handled within the global loop, hence
``git_pillar_update_interval`` should be a multiple of ``loop_interval``.

.. code-block:: yaml

    git_pillar_update_interval: 120

"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import copy
import logging

import salt.utils.dictupdate

# Import salt libs
import salt.utils.gitfs
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import FileserverConfigError

# Import third party libs
from salt.ext import six
from salt.pillar import Pillar

PER_REMOTE_OVERRIDES = ("env", "root", "ssl_verify", "refspecs")
PER_REMOTE_ONLY = ("name", "mountpoint", "all_saltenvs")
GLOBAL_ONLY = ("base", "branch")

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "git"


def __virtual__():
    """
    Only load if gitpython is available
    """
    git_ext_pillars = [x for x in __opts__["ext_pillar"] if "git" in x]
    if not git_ext_pillars:
        # No git external pillars were configured
        return False

    try:
        salt.utils.gitfs.GitPillar(__opts__, init_remotes=False)
        # Initialization of the GitPillar object did not fail, so we
        # know we have valid configuration syntax and that a valid
        # provider was detected.
        return __virtualname__
    except FileserverConfigError:
        return False


def ext_pillar(minion_id, pillar, *repos):  # pylint: disable=unused-argument
    """
    Checkout the ext_pillar sources and compile the resulting pillar SLS
    """
    opts = copy.deepcopy(__opts__)
    opts["pillar_roots"] = {}
    opts["__git_pillar"] = True
    git_pillar = salt.utils.gitfs.GitPillar(
        opts,
        repos,
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
        global_only=GLOBAL_ONLY,
    )
    if __opts__.get("__role") == "minion":
        # If masterless, fetch the remotes. We'll need to remove this once
        # we make the minion daemon able to run standalone.
        git_pillar.fetch_remotes()
    git_pillar.checkout()
    ret = {}
    merge_strategy = __opts__.get("pillar_source_merging_strategy", "smart")
    merge_lists = __opts__.get("pillar_merge_lists", False)
    for pillar_dir, env in six.iteritems(git_pillar.pillar_dirs):
        # Map env if env == '__env__' before checking the env value
        if env == "__env__":
            env = (
                opts.get("pillarenv")
                or opts.get("saltenv")
                or opts.get("git_pillar_base")
            )
            log.debug("__env__ maps to %s", env)

        # If pillarenv is set, only grab pillars with that match pillarenv
        if opts["pillarenv"] and env != opts["pillarenv"]:
            log.debug(
                "env '%s' for pillar dir '%s' does not match "
                "pillarenv '%s', skipping",
                env,
                pillar_dir,
                opts["pillarenv"],
            )
            continue
        if pillar_dir in git_pillar.pillar_linked_dirs:
            log.debug(
                "git_pillar is skipping processing on %s as it is a " "mounted repo",
                pillar_dir,
            )
            continue
        else:
            log.debug(
                "git_pillar is processing pillar SLS from %s for pillar " "env '%s'",
                pillar_dir,
                env,
            )

        pillar_roots = [pillar_dir]

        if __opts__["git_pillar_includes"]:
            # Add the rest of the pillar_dirs in this environment to the
            # list, excluding the current pillar_dir being processed. This
            # is because it was already specified above as the first in the
            # list, so that its top file is sourced from the correct
            # location and not from another git_pillar remote.
            pillar_roots.extend(
                [
                    d
                    for (d, e) in six.iteritems(git_pillar.pillar_dirs)
                    if env == e and d != pillar_dir
                ]
            )

        opts["pillar_roots"] = {env: pillar_roots}

        local_pillar = Pillar(opts, __grains__, minion_id, env)
        ret = salt.utils.dictupdate.merge(
            ret,
            local_pillar.compile_pillar(ext=False),
            strategy=merge_strategy,
            merge_lists=merge_lists,
        )
    return ret


def _extract_key_val(kv, delimiter="="):
    """Extract key and value from key=val string.

    Example:
    >>> _extract_key_val('foo=bar')
    ('foo', 'bar')
    """
    pieces = kv.split(delimiter)
    key = pieces[0]
    val = delimiter.join(pieces[1:])
    return key, val
