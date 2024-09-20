==============================================
Contributing to Salt: A Guide for Contributors
==============================================

So, you want to contribute to the Salt project? That's fantastic! There are many
ways you can help improve Salt:

- Use Salt and report bugs with clear, detailed descriptions.
- Join a `working group <https://github.com/saltstack/community>`__ to
  collaborate with other contributors.
- Answer questions on platforms like `IRC <https://web.libera.chat/#salt>`__,
  the `community Discord <https://discord.com/invite/J7b7EscrAs>`__,
  the `salt-users mailing list <https://groups.google.com/forum/#!forum/salt-users>`__,
  `Server Fault <https://serverfault.com/questions/tagged/saltstack>`__,
  or `r/saltstack on Reddit <https://www.reddit.com/r/saltstack/>`__.
- Fix bugs or contribute to the `documentation <https://saltstack.gitlab.io/open/docs/docs-hub/topics/contributing.html>`__.
- Submit workarounds, patches, or code (even without tests).
- Share your experiences and solutions to problems you've solved using Salt.

Choosing the Right Branch for Your Pull Request
===============================================

We appreciate your contributions to the project! To ensure a smooth and
efficient workflow, please follow these guidelines when submitting a Pull
Request. Each type of contribution—whether it's fixing a bug, adding a feature,
updating documentation, or fixing tests—should be targeted at the appropriate
branch. This helps us manage changes effectively and maintain stability across
versions.

- **Bug Fixes:**

  Create your Pull Request against the oldest supported branch where the bug
  exists. This ensures that the fix can be applied to all relevant versions.

- **New Features**:

  For new features or enhancements, create your Pull Request against the master
  branch.

- **Documentation Updates:**

  Documentation changes should be made against the master branch, unless they
  are related to a bug fix, in which case they should follow the same branch as
  the bug fix.

- **Test Fixes:**

  Pull Requests that fix broken or failing tests should be created against the
  oldest supported branch where the issue occurs.

Setting Up Your Salt Development Environment
============================================

To hack on Salt or the docs you're going to need to set up your
development environment. If you already have a workflow that you're
comfortable with, you can use that, but otherwise this is an opinionated
guide for setting up your dev environment. Follow these steps and you'll
end out with a functioning dev environment and be able to submit your
first PR.

This guide assumes at least a passing familiarity with
`Git <https://git-scm.com/>`__, a common version control tool used
across many open source projects, and is necessary for contributing to
Salt. For an introduction to Git, watch `Salt Docs Clinic - Git For the
True
Beginner <https://www.youtube.com/watch?v=zJw6KNvmuq4&ab_channel=SaltStack>`__.
Because of its widespread use, there are many resources for learning
more about Git. One popular resource is the free online book `Learn Git
in a Month of
Lunches <https://www.manning.com/books/learn-git-in-a-month-of-lunches>`__.


pyenv, Virtual Environments, and you
------------------------------------
We recommend `pyenv <https://github.com/pyenv/pyenv>`__, since it allows
installing multiple different Python versions, which is important for
testing Salt across all the versions of Python that we support.

On Linux
^^^^^^^^
Install pyenv:

::

   git clone https://github.com/pyenv/pyenv.git ~/.pyenv
   export PATH="$HOME/.pyenv/bin:$PATH"
   git clone https://github.com/pyenv/pyenv-virtualenv.git $(pyenv root)/plugins/pyenv-virtualenv

On Mac
^^^^^^
Install pyenv using brew:

::

   brew update
   brew install pyenv
   brew install pyenv-virtualenv

--------------

Now add pyenv to your ``.bashrc``:

::

   echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
   pyenv init 2>> ~/.bashrc
   pyenv virtualenv-init 2>> ~/.bashrc

For other shells, see `the pyenv
instructions <https://github.com/pyenv/pyenv#basic-github-checkout>`__.

Go ahead and restart your shell. Now you should be able to install a new
version of Python:

::

   pyenv install 3.9.18

If that fails, don't panic! You're probably just missing some build
dependencies. Check out `pyenv common build
problems <https://github.com/pyenv/pyenv/wiki/Common-build-problems>`__.

Now that you've got your version of Python installed, you can create a
new virtual environment with this command:

::

   pyenv virtualenv 3.9.18 salt

Then activate it:

::

   pyenv activate salt

Sweet! Now you're ready to clone Salt so you can start hacking away! If
you get stuck at any point, check out the resources at the beginning of
this guide. IRC and Discord are particularly helpful places to go.


Get the source!
---------------
Salt uses the fork and clone workflow for Git contributions. See `Using
the Fork-and-Branch Git
Workflow <https://blog.scottlowe.org/2015/01/27/using-fork-branch-git-workflow/>`__
for how to implement it. But if you just want to hurry and get started
you can go ahead and follow these steps:

Clones are so shallow. Well, this one is anyway:

::

   git clone --depth=1 --origin salt https://github.com/saltstack/salt.git

This creates a shallow clone of Salt, which should be fast. Most of the
time that's all you'll need, and you can start building out other
commits as you go. If you *really* want all 108,300+ commits you can
just run ``git fetch --unshallow``. Then go make a sandwich because it's
gonna be a while.

You're also going to want to head over to GitHub and create your own
`fork of Salt <https://github.com/saltstack/salt/fork>`__. Once you've
got that set up you can add it as a remote:

::

   git remote add yourname <YOUR SALT REMOTE>

If you use your name to refer to your fork, and ``salt`` to refer to the
official Salt repo you'll never get ``upstream`` or ``origin`` confused.

.. note::

   Each time you start work on a new issue you should fetch the most recent
   changes from ``salt/upstream``.


Set up ``pre-commit`` and ``nox``
---------------------------------
Here at Salt we use `pre-commit <https://pre-commit.com/>`__ and
`nox <https://nox.thea.codes/en/stable/>`__ to make it easier for
contributors to get quick feedback, for quality control, and to increase
the chance that your merge request will get reviewed and merged. Nox
enables us to run multiple different test configurations, as well as
other common tasks. You can think of it as Make with superpowers.
Pre-commit does what it sounds like: it configures some Git pre-commit
hooks to run ``black`` for formatting, ``isort`` for keeping our imports
sorted, and ``pylint`` to catch issues like unused imports, among
others. You can easily install them in your virtualenv with:

::

   python -m pip install pre-commit nox
   pre-commit install

.. warning::
    Currently there is an issue with the pip-tools-compile pre-commit hook on Windows.
    The details around this issue are included here:
    https://github.com/saltstack/salt/issues/56642.
    Please ensure you export ``SKIP=pip-tools-compile`` to skip pip-tools-compile.

Now before each commit, it will ensure that your code at least *looks*
right before you open a pull request. And with that step, it's time to
start hacking on Salt!


Set up imagemagick
------------------
One last prerequisite is to have ``imagemagick`` installed, as it is required
by Sphinx for generating the HTML documentation.

::

   # On Mac, via homebrew
   brew install imagemagick

::

   # Example Linux installation: Debian-based
   sudo apt install imagemagick


Salt issues
===========

Create your own
---------------

Perhaps you've come to this guide because you found a problem in Salt,
and you've diagnosed the cause. Maybe you need some help figuring out
the problem. In any case, creating quality bug reports is a great way to
contribute to Salt even if you lack the skills, time, or inclination to
fix it yourself. If that's the case, head on over to `Salt's issue
tracker on
GitHub <https://github.com/saltstack/salt/issues/new/choose>`__.

Creating a **good** report can take a little bit of time - but every
minute you invest in making it easier for others to reproduce and
understand your issue is time well spent. The faster someone can
understand your issue, the faster it will be able to get fixed
correctly.

The thing that every issue needs goes by many names, but one at least as
good as any other is MCVE - **M**\ inimum **C**\ omplete
**V**\ erifiable **E**\ xample.

In a nutshell:

-  **Minimum**: All of the **extra** information has been removed. Will
   2 or 3 lines of master/minion config still exhibit the behavior?
-  **Complete**: Minimum also means complete. If your example is missing
   information, then it's not complete. Salt, Python, and OS versions
   are all bits of information that make your example complete. Have you
   provided the commands that you ran?
-  **Verifiable**: Can someone take your report and reproduce it?

Slow is smooth, and smooth is fast - it may feel like you're taking a
long time to create your issue if you're creating a proper MCVE, but a
MCVE eliminates back and forth required to reproduce/verify the issue so
someone can actually create a fix.

Pick an issue
-------------

If you don't already have an issue in mind, you can search for `help
wanted <https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22>`__
issues. If you also search for `good first
issue <https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22+label%3A%22good+first+issue%22>`__
then you should be able to find some issues that are good for getting
started contributing to Salt. `Documentation
issues <https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3Adocumentation+>`__
are also good starter issues. When you find an issue that catches your
eye (or one of your own), it's a good idea to comment on the issue and
mention that you're working on it. Good communication is key to
collaboration - so if you don't have time to complete work on the issue,
just leaving some information about when you expect to pick things up
again is a great idea!

Hacking away
============

Salt, tests, documentation, and you
-----------------------------------

Before approving code contributions, Salt requires:

-  documentation
-  meaningful passing tests
-  correct code

Documentation fixes just require correct documentation.

What if I don't write tests or docs?
------------------------------------

If you aren't into writing documentation or tests, we still welcome your
contributions! But your PR will be labeled ``Needs Testcase`` and
``Help Wanted`` until someone can get to write the tests/documentation.
Of course, if you have a desire but just lack the skill we are more than
happy to collaborate and help out! There's the `documentation working
group <https://saltstack.gitlab.io/open/docs/docs-hub/topics/home.html>`__
and the `testing working group <https://github.com/saltstack/community/tree/master/working_groups/wg-Testing>`__.
We also regularly stream our test clinic `live on
Twitch <https://www.twitch.tv/saltprojectoss>`__ every Tuesday afternoon
and Thursday morning, Central Time. If you'd like specific help with
tests, bring them to the clinic. If no community members need help, you
can also just watch tests written in real time.


Documentation
-------------

Salt uses both docstrings, as well as normal reStructuredText files in
the ``salt/doc`` folder for documentation. Sphinx is used to generate the
documentation, and does require ``imagemagick``. See `Set up imagemagick`_ for
more information.

Before submitting a documentation PR, it helps to first build the Salt docs
locally on your machine and preview them. Local previews helps you:

- Debug potential documentation output errors before submitting a PR.
- Saves you time by not needing to use the Salt CI/CD test suite to debug, which takes
  more than 30 minutes to run on a PR.
- Ensures the final output looks the way you intended it to look.

To set up your local environment to preview the core Salt and module
documentation:

#. Install the documentation dependencies. For example, on Ubuntu:

   ::

       sudo apt-get update

       sudo apt-get install -y enchant-2 git gcc imagemagick make zlib1g-dev libc-dev libffi-dev g++ libxml2 libxml2-dev libxslt-dev libcurl4-openssl-dev libssl-dev libgnutls28-dev xz-utils inkscape

#. Navigate to the folder where you store your Salt repository and remove any
   `.nox` directories that might be in that folder:

   ::

       rm -rf .nox

#. Install `pyenv` for the version of Python needed to run the docs. As of the
   time of writing, the Salt docs theme is not compatible with Python 3.10, so
   you'll need to run 3.9 or earlier. For example:

   ::

       pyenv install 3.9.18
       pyenv virtualenv 3.9.18 salt-docs
       echo 'salt-docs' > .python-version

#. Activate `pyenv` if it's not auto-activated:

   ::

       pyenv exec pip install -U pip setuptools wheel

#. Install `nox` into your pyenv environment, which is the utility that will
   build the Salt documentation:

   ::

       pyenv exec pip install nox


Since we use ``nox``, you can build your docs and view them in your browser
with this one-liner:

::

   python -m nox -e 'docs-html(compress=False, clean=False)'; cd doc/_build/html; python -m webbrowser http://localhost:8000/contents.html; python -m http.server

The first time you build the docs, it will take a while because there are a
*lot* of modules. Maybe you should go grab some dessert if you already finished
that sandwich. But once nox and Sphinx are done building the docs, python should
launch your default browser with the URL
http://localhost:8000/contents.html. Now you can navigate to your docs
and ensure your changes exist. If you make changes, you can simply run
this:

::

   cd -; python -m nox -e 'docs-html(compress=False, clean=False)'; cd doc/_build/html; python -m http.server

And then refresh your browser to get your updated docs. This one should
be quite a bit faster since Sphinx won't need to rebuild everything.

Alternatively, you could build the docs on your local machine and then preview
the build output. To build the docs locally:

::

    pyenv exec nox -e 'docs-html(compress=False, clean=True)'

The output from this command will put the preview files in: ``doc > _build > html``.

If your change is a docs-only change, you can go ahead and commit/push
your code and open a PR. You can indicate that it's a docs-only change by
adding ``[Documentation]`` to the title of your PR. Otherwise, you'll
want to write some tests and code.


Running development Salt
------------------------
Note: If you run into any issues in this section, check the
Troubleshooting section.

If you're going to hack on the Salt codebase you're going to want to be
able to run Salt locally. The first thing you need to do is install Salt
as an editable pip install:

::

   python -m pip install -e .

This will let you make changes to Salt without having to re-install it.

After all of the dependencies and Salt are installed, it's time to set
up the config for development. Typically Salt runs as ``root``, but you
can specify which user to run as. To configure that, just copy the
master and minion configs. We have .gitignore setup to ignore the
``local/`` directory, so we can put all of our personal files there.

::

   mkdir -p local/etc/salt/

Create a master config file as ``local/etc/salt/master``:

::

   cat <<EOF >local/etc/salt/master
   user: $(whoami)
   root_dir: $PWD/local/
   publish_port: 55505
   ret_port: 55506
   EOF

And a minion config as ``local/etc/salt/minion``:

::

   cat <<EOF >local/etc/salt/minion
   user: $(whoami)
   root_dir: $PWD/local/
   master: localhost
   id: saltdev
   master_port: 55506
   EOF

Now you can start your Salt master and minion, specifying the config
dir.

::

   salt-master --config-dir=local/etc/salt/ --log-level=debug --daemon
   salt-minion --config-dir=local/etc/salt/ --log-level=debug --daemon

Now you should be able to accept the minion key:

::

   salt-key -c local/etc/salt -Ay

And check that your master/minion are communicating:

::

   salt -c local/etc/salt \* test.version

Rather than running ``test.version`` from your master, you can run it
from the minion instead:

::

   salt-call -c local/etc/salt test.version

Note that you're running ``salt-call`` instead of ``salt``, and you're
not specifying the minion (``\*``), but if you're running the dev
version then you still will need to pass in the config dir. Now that
you've got Salt running, you can hack away on the Salt codebase!

If you need to restart Salt for some reason, if you've made changes and
they don't appear to be reflected, this is one option:

::

   kill -INT $(pgrep salt-master)
   kill -INT $(pgrep salt-minion)

If you'd rather not use ``kill``, you can have a couple of terminals
open with your salt virtualenv activated and omit the ``--daemon``
argument. Salt will run in the foreground, so you can just use ctrl+c to
quit.


Test first? Test last? Test meaningfully!
-----------------------------------------
You can write tests first or tests last, as long as your tests are
meaningful and complete! *Typically* the best tests for Salt are going
to be unit tests. Testing is `a whole topic on its
own <https://docs.saltproject.io/en/master/topics/tutorials/writing_tests.html>`__,
But you may also want to write functional or integration tests. You'll
find those in the ``tests/`` directory.

When you're thinking about tests to write, the most important thing to
keep in mind is, “What, exactly, am I testing?” When a test fails, you
should know:

-  What, specifically, failed?
-  Why did it fail?
-  As much as possible, what do I need to do to fix this failure?

If you can't answer those questions then you might need to refactor your
tests.

When you're running tests locally, you should make sure that if you
remove your code changes your tests are failing. If your tests *aren't*
failing when you haven't yet made changes, then it's possible that
you're testing the wrong thing.

But whether you adhere to TDD/BDD, or you write your code first and your
tests last, ensure that your tests are meaningful.


Running tests
-------------
As previously mentioned, we use ``nox``, and that's how we run our
tests. You should have it installed by this point but if not you can
install it with this:

::

   python -m pip install nox

Now you can run your tests:

::

   python -m nox -e "test-3(coverage=False)" -- tests/unit/cli/test_batch.py

It's a good idea to install
`espeak <https://github.com/espeak-ng/espeak-ng>`__ or use ``say`` on
Mac if you're running some long-running tests. You can do something like
this:

::

   python -m nox -e "test-3(coverage=False)" -- tests/unit/cli/test_batch.py; espeak "Tests done, woohoo!"

That way you don't have to keep monitoring the actual test run.


::

   python -m nox -e "test-3(coverage=False)" -- --core-tests

You can enable or disable test groups locally by passing their respected flag:

* --no-fast-tests - Tests that are ~10s or faster. Fast tests make up ~75% of tests and can run in 10 to 20 minutes.
* --slow-tests - Tests that are ~10s or slower.
* --core-tests - Tests of any speed that test the root parts of salt.
* --flaky-jail - Test that need to be temporarily skipped.

In your PR, you can enable or disable test groups by setting a label.
All fast, slow, and core tests specified in the change file will always run.

* test:no-fast
* test:core
* test:slow
* test:flaky-jail


Changelog and commit!
---------------------
When you write your commit message you should use imperative style. Do
this:

   Add frobnosticate capability

Don't do this:

   Added frobnosticate capability

But that advice is backwards for the changelog. We follow the
`keepachangelog <https://keepachangelog.com/en/1.0.0/>`__ approach for
our changelog, and use towncrier to generate it for each release. As a
contributor, all that means is that you need to add a file to the
``salt/changelog`` directory, using the ``<issue #>.<type>`` format. For
instance, if you fixed issue 123, you would do:

::

   echo "Made sys.doc inform when no minions return" > changelog/123.fixed

And that's all that would go into your file. When it comes to your
commit message, it's usually a good idea to add other information, such as

- What does a reviewer need to know about the change that you made?
- If someone isn't an expert in this area, what will they need to know?

This will also help you out, because when you go to create the PR it
will automatically insert the body of your commit messages.

See the `changelog <https://docs.saltproject.io/en/latest/topics/development/changelog.html>`__
docs for more information.


Pull request time!
------------------
Once you've done all your dev work and tested locally, you should check
out our `PR
guidelines <https://docs.saltproject.io/en/master/topics/development/pull_requests.html>`__.
After you read that page, it's time to `open a new
PR <https://github.com/saltstack/salt/compare>`__. Fill out the PR
template - you should have updated or created any necessary docs, and
written tests if you're providing a code change. When you submit your
PR, we have a suite of tests that will run across different platforms to
help ensure that no known bugs were introduced.


Now what?
---------
You've made your changes, added documentation, opened your PR, and have
passing tests… now what? When can you expect your code to be merged?

When you open your PR, a reviewer will get automatically assigned. If
your PR is submitted during the week you should be able to expect some
kind of communication within that business day. If your tests are
passing and we're not in a code freeze, ideally your code will be merged
that week or month. If you haven't heard from your assigned reviewer, ping them
on GitHub, `irc <https://web.libera.chat/#salt>`__, or Community Discord.

It's likely that your reviewer will leave some comments that need
addressing - it may be a style change, or you forgot a changelog entry,
or need to update the docs. Maybe it's something more fundamental -
perhaps you encountered the rare case where your PR has a much larger
scope than initially assumed.

Whatever the case, simply make the requested changes (or discuss why the
requests are incorrect), and push up your new commits. If your PR is
open for a significant period of time it may be worth rebasing your
changes on the most recent changes to Salt. If you need help, the
previously linked Git resources will be valuable.

But if, for whatever reason, you're not interested in driving your PR to
completion then just note that in your PR. Something like, “I'm not
interested in writing docs/tests, I just wanted to provide this fix -
someone else will need to complete this PR.” If you do that then we'll
add a “Help Wanted” label and someone will be able to pick up the PR,
make the required changes, and it can eventually get merged in.

In any case, now that you have a PR open, congrats! You're a Salt
developer! You rock!


Troubleshooting
===============


zmq.core.error.ZMQError
-----------------------
Once the minion starts, you may see an error like the following::

::

   zmq.core.error.ZMQError: ipc path "/path/to/your/virtualenv/var/run/salt/minion/minion_event_7824dcbcfd7a8f6755939af70b96249f_pub.ipc" is longer than 107 characters (sizeof(sockaddr_un.sun_path)).

This means that the path to the socket the minion is using is too long.
This is a system limitation, so the only workaround is to reduce the
length of this path. This can be done in a couple different ways:

1. Create your virtualenv in a path that is short enough.
2. Edit the :conf_minion:``sock_dir`` minion config variable and reduce
   its length. Remember that this path is relative to the value you set
   in :conf_minion:``root_dir``.

NOTE: The socket path is limited to 107 characters on Solaris and Linux,
and 103 characters on BSD-based systems.


No permissions to access ...
----------------------------
If you forget to pass your config path to any of the ``salt*`` commands,
you might see

::

   No permissions to access "/var/log/salt/master", are you running as the
   correct user?

Just pass ``-c local/etc/salt`` (or whatever you named it)


File descriptor limit
---------------------
You might need to raise your file descriptor limit. You can check it
with:

::

   ulimit -n

If the value is less than 3072, you should increase it with:

::

   ulimit -n 3072
   # For c-shell:
   limit descriptors 3072


Pygit2 or other dependency install fails
----------------------------------------
You may see some failure messages when installing requirements. You can
directly access your nox environment and possibly install pygit (or
other dependency) that way. When you run nox, you'll see a message like
this:

::

   nox > Re-using existing virtual environment at .nox/pytest-parametrized-3-crypto-none-transport-zeromq-coverage-false.

For this, you would be able to install with:

::

   .nox/pytest-parametrized-3-crypto-none-transport-zeromq-coverage-false/bin/python -m pip install pygit2
