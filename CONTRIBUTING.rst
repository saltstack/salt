==============================================
Contributing to Salt: A Guide for Contributors
==============================================

Thanks for your interest in contributing to Salt! There are many ways you can
help:

- Use Salt and report bugs with clear, detailed descriptions.
- Join a `working group <https://github.com/saltstack/community>`__ to
  collaborate with other contributors.
- Answer questions on platforms like
  the `community Discord <https://discord.com/invite/J7b7EscrAs>`__,
  the `salt-users mailing list <https://groups.google.com/forum/#!forum/salt-users>`__,
  `Server Fault <https://serverfault.com/questions/tagged/saltstack>`__,
  or `r/saltstack on Reddit <https://www.reddit.com/r/saltstack/>`__.
- Fix bugs, write tests, or improve `the documentation
  <https://docs.saltproject.io>`__.
- Submit patches even if you do not have time to add tests or docs - we will
  label the PR ``Needs Testcase`` / ``Help Wanted`` and someone else can pick
  it up.
- Share workarounds and solutions you have built with Salt.

.. _contributing-what-a-pr-needs:

What a pull request needs before it can merge
=============================================

A reviewer will look for these specific things. Plan for them up front and
your PR will move faster.

1. **CI must be green.** The PR-trigger workflows run lint, the relevant
   pytest subset, the docs build, and packaging smoke tests. If anything is
   red and the failure is related to your change, expect the reviewer to ask
   you to fix it rather than rerun. Pre-existing flakes are tracked separately
   - say so in the PR and link the tracking issue.

2. **A changelog fragment.** Every behavior change adds one file under
   ``changelog/`` named ``<issue-or-pr-number>.<type>.md``. See
   :ref:`add-changelog` for the full set of types and exceptions.

3. **Test coverage for the change.** A regression test for bug fixes; a new
   test exercising the new code path for features. We do not require coverage
   for unrelated lines you happened to touch. See
   :ref:`salt-test-suite` for how the tests are organized.

4. **Targeted at the right branch.** See
   :ref:`contributing-branch-choice` below.

5. **A reasonable PR description.** Link the issue, describe what changed and
   why, and call out anything risky (cross-platform, security-adjacent,
   public API surface).

That is the baseline. The full review checklist lives in
:ref:`pull_requests` - it covers performance, security, error handling,
backwards compatibility, and the other questions a reviewer will keep in mind.

We do not require you to be in a specific working group, post in Discord, or
attend the test clinic to get your PR merged. Those communities exist if you
want help, not as gates.


.. _contributing-branch-choice:

Choosing the right branch
=========================

Salt currently maintains the following branches:

- ``3006.x`` - Sulfur LTS, bug fixes only.
- ``3007.x`` - Chlorine, bug fixes only.
- ``3008.x`` - Argon, bug fixes only.
- ``master`` - next feature release (Potassium).

Open your PR against the **oldest supported branch where the change applies**.
The maintainers merge-forward into newer branches.

- **Bug fix:** open against the oldest supported branch where the bug
  reproduces. Do not target ``master`` for a fix that also affects ``3006.x``.

- **New feature or enhancement:** target ``master``.

- **Documentation:** target ``master`` unless the change describes a behavior
  that only exists in a specific release branch, in which case target that
  branch.

- **Test fixes:** target the oldest supported branch where the test is
  failing.

- **Security fix (CVE):** follow `SECURITY.md
  <https://github.com/saltstack/salt/blob/master/SECURITY.md>`__ -
  do not open a public PR.

If you target the wrong branch we will say so on the PR; you can usually fix
it by changing the base branch in the GitHub UI and rebasing.


How the project is governed
===========================

Larger or controversial changes go through the Salt Enhancement Proposal
process. See `salt-enhancement-proposals
<https://github.com/saltstack/salt-enhancement-proposals>`__ for the active
list and the template. You do not need a SEP for a normal bug fix or
self-contained feature; if you are unsure, open an issue or ask on Discord
before writing the code.

The git workflow, release cadence, and merge-forward policy are documented at
:ref:`saltstack-git-policy`.


Setting up your development environment
=======================================

This guide is opinionated; if you already have a Python workflow you like,
use it. The goal is a clone of Salt you can run, test, and rebuild.

You will need basic familiarity with `Git <https://git-scm.com/>`__. The free
`Pro Git book <https://git-scm.com/book/en/v2>`__ is a good reference if you
get stuck.

Install Python with pyenv
-------------------------

We recommend `pyenv <https://github.com/pyenv/pyenv>`__ so you can keep
multiple Python versions side by side. Salt 3007.x supports CPython 3.9
through 3.14; the 3007.x CI runs against 3.10.20.

On Linux::

   git clone https://github.com/pyenv/pyenv.git ~/.pyenv
   git clone https://github.com/pyenv/pyenv-virtualenv.git \
       ~/.pyenv/plugins/pyenv-virtualenv

On macOS::

   brew update
   brew install pyenv pyenv-virtualenv

Then wire pyenv into your shell. For bash::

   echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
   echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
   echo 'eval "$(pyenv init -)"' >> ~/.bashrc
   echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

See the `pyenv install instructions
<https://github.com/pyenv/pyenv#installation>`__ for zsh, fish, and Windows.

Restart your shell and install a supported Python::

   pyenv install 3.10.20
   pyenv virtualenv 3.10.20 salt
   pyenv activate salt

If ``pyenv install`` fails, you are usually missing system build dependencies.
The `pyenv wiki common build problems
<https://github.com/pyenv/pyenv/wiki/Common-build-problems>`__ page has the
package list for each OS.

Get the source
--------------

Salt uses the fork-and-clone workflow. Fork
`saltstack/salt <https://github.com/saltstack/salt/fork>`__ on GitHub, then::

   git clone --origin upstream https://github.com/saltstack/salt.git
   cd salt
   git remote add origin git@github.com:<your-user>/salt.git

Now ``upstream`` is the canonical repo and ``origin`` is your fork - push
branches to ``origin``, open PRs back to ``upstream``.

If cloning the full history is slow, ``git clone --depth=1`` is fine for a
first pass; run ``git fetch --unshallow`` later if you need it.

Install pre-commit and nox
--------------------------

Salt uses `pre-commit <https://pre-commit.com/>`__ and
`nox <https://nox.thea.codes/en/stable/>`__. Install them into your
virtualenv::

   python -m pip install pre-commit nox
   pre-commit install

``pre-commit`` runs ``black``, ``isort``, ``pyupgrade``, ``pylint``, the
changelog-entry check, and a few project-specific hooks before every commit.
Run it on demand with::

   pre-commit run --all-files

``nox`` drives the test suites and the docs build. The configuration lives in
``noxfile.py``.

System dependencies
-------------------

The docs build needs ``imagemagick``. On Debian/Ubuntu::

   sudo apt install imagemagick

On macOS::

   brew install imagemagick

If you plan to build the full docs you will also want
``enchant-2`` (for the spell-check builder), ``inkscape``, and the usual
build toolchain. A working starter set on Debian/Ubuntu::

   sudo apt install enchant-2 git gcc imagemagick make zlib1g-dev \
       libc-dev libffi-dev g++ libxml2 libxml2-dev libxslt-dev \
       libcurl4-openssl-dev libssl-dev libgnutls28-dev xz-utils inkscape

Install Salt in editable mode
-----------------------------

::

   python -m pip install -e .

This lets you edit ``salt/`` and immediately see the change without
re-installing.


Running Salt from source
========================

Salt normally runs as ``root``; for development, run it as your user against
a local config under ``local/`` (the directory is gitignored)::

   mkdir -p local/etc/salt

Master config (``local/etc/salt/master``)::

   user: $(whoami)
   root_dir: $PWD/local/
   publish_port: 55505
   ret_port: 55506

Minion config (``local/etc/salt/minion``)::

   user: $(whoami)
   root_dir: $PWD/local/
   master: localhost
   id: saltdev
   master_port: 55506

Start the daemons::

   salt-master --config-dir=local/etc/salt/ --log-level=debug --daemon
   salt-minion --config-dir=local/etc/salt/ --log-level=debug --daemon

Accept the minion key and verify the round trip::

   salt-key -c local/etc/salt -Ay
   salt -c local/etc/salt \* test.version

Or run a function directly on the minion::

   salt-call -c local/etc/salt test.version

If you would rather not daemonize, drop ``--daemon`` and run each in its own
terminal. To restart after changes::

   pkill -INT -f salt-master
   pkill -INT -f salt-minion


.. _contributing-running-tests:

Running tests
=============

Salt's tests run under pytest, orchestrated by nox. The canonical command
during development is::

   nox -e 'test-3(coverage=False)' -- tests/pytests/unit/cli/test_batch.py

Pass a directory or file path after ``--`` to scope the run. Useful subsets:

- ``tests/pytests/unit/`` - fast in-process unit tests.
- ``tests/pytests/functional/`` - in-process tests that use real loaders.
- ``tests/pytests/integration/`` - tests that start salt-master/minion
  daemons.

Test-group flags you can pass through nox:

- ``--no-fast-tests`` - skip tests that run in ~10s or less.
- ``--slow-tests`` - include tests marked slow.
- ``--core-tests`` - run the core-tagged subset.
- ``--run-destructive`` - allow tests that change system state.

On a PR you can opt in to bigger test matrices via labels:

- ``test:core`` / ``test:slow`` / ``test:no-fast`` - test-group selectors.
- ``test:pkg`` - run packaging tests.
- ``test:full`` - run the full suite (used before merge for risky changes).
- ``test:coverage`` - run the full suite with coverage on.
- ``test:os:<os>-<arch>`` - add a specific OS to the run, or
  ``test:os:all``.

See :ref:`salt-test-suite` for how the suite is laid out and
:ref:`tutorial-salt-testing` for an introduction to writing tests.


Writing the changelog fragment
==============================

Add a file to ``changelog/`` named ``<issue-or-pr-number>.<type>.md``. For
example, fixing issue #123::

   echo "sys.doc now reports when no minions return." > changelog/123.fixed.md

The pre-commit hook ``check-changelog-entries`` will fail the commit if the
filename does not match the expected format. The :ref:`changelog` page
documents the full type vocabulary (``added``, ``fixed``, ``changed``,
``deprecated``, ``removed``, ``security``) and the special CVE filename
form.

Commit message style: imperative mood, ``Add foo`` not ``Added foo``. The
changelog fragment uses past-tense narrative ("Fixed ...", "Added ...")
because it ends up in CHANGELOG.md.


Building the docs locally
=========================

If your change touches ``doc/``, ``salt/`` docstrings, or any user-facing
text, preview the rendered output before opening the PR::

   nox -e 'docs-html(compress=False, clean=False)'

The first build takes a while; subsequent incremental builds are fast. To
serve the result::

   cd doc/_build/html
   python -m http.server

Then open http://localhost:8000/contents.html.

A docs-only PR can include ``[Documentation]`` in the title to skip the
heavier test runs.


Submitting the pull request
===========================

Push to your fork and open the PR against the branch you chose in
:ref:`contributing-branch-choice`. Fill out the PR template - it asks for
the change description, related issue, and whether tests/docs were updated.

After you submit:

- A reviewer is auto-assigned. If you do not hear back within a few
  business days, ping the PR or post in
  `Community Discord <https://discord.com/invite/J7b7EscrAs>`__.
- Address review feedback by pushing new commits to the same branch. Do
  not force-push unless asked - the reviewer is reading the incremental
  diff.
- If the PR sits long enough to develop merge conflicts, rebase onto the
  current base branch and push. Do not merge the base back into your PR
  branch.

Read :ref:`pull_requests` once before your first PR; it spells out the full
review checklist the maintainers actually use.


Filing a good bug report
========================

If you came here because you found a bug, open it at
`saltstack/salt/issues/new/choose
<https://github.com/saltstack/salt/issues/new/choose>`__. Pick the
**Bug Report** template - it asks for the install type, OS, Salt version,
and reproduction steps. Filling those in completely is the single biggest
thing you can do to speed up the fix.

The other templates available are:

- **Documentation** - typos, missing topics, wrong output.
- **Tech Debt** - refactoring proposals that do not change behavior.
- **Test Failure** - flakes or platform-specific failures in CI.

A good report is short and complete: minimum config that reproduces the
issue, exact commands run, observed output, expected output, and version
strings.

To find an issue to work on, browse the `help wanted
<https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22>`__
and `good first issue
<https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22>`__
lists, or the `documentation
<https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3Adocumentation+>`__
label. Comment on the issue to claim it before you start so two people are
not working in parallel.


Troubleshooting
===============

zmq.core.error.ZMQError: ipc path too long
------------------------------------------

::

   zmq.core.error.ZMQError: ipc path ".../minion_event_*.ipc" is longer than 107 characters (sizeof(sockaddr_un.sun_path)).

The socket path is too long. Either move your virtualenv to a shorter path
or set :conf_minion:`sock_dir` to a short absolute path in your minion
config. The limit is 107 characters on Linux/Solaris and 103 on BSDs.


No permissions to access /var/log/salt/master
---------------------------------------------

You forgot ``-c local/etc/salt`` on the ``salt`` command. Pass it explicitly
or set ``SALT_CONFIG_DIR``.


File descriptor limit
---------------------

Some tests open a lot of sockets. Bump the limit if you hit
``Too many open files``::

   ulimit -n 3072


pygit2 (or other dependency) fails to install
---------------------------------------------

The nox virtualenv may already have what you need. Find the env::

   ls .nox/

Then install the missing package into it::

   .nox/<env>/bin/python -m pip install pygit2

If it still fails, the dependency probably needs system libraries
(``libgit2-dev`` for pygit2 on Debian/Ubuntu).
