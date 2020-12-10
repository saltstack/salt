# Developing Salt


So you want to contribute to the Salt project? Excellent! You can help in a
number of ways:

- Using Salt and opening bug reports.
- Joining a [working group](https://github.com/saltstack/community).
- Answering questions on [irc][salt on freenode], the
  [community Slack](https://saltstackcommunity.herokuapp.com/), or the
  [salt-users mailing list](https://groups.google.com/forum/#!forum/salt-users).
- Fixing issues.

If you'd like to update docs or fix an issue, you're going to need the Salt
repo. The best way to contribute is using [Git](https://git-scm.com/).

## Environment Setup

To hack on Salt or the docs you're going to need to setup your development
environment. If you already have a workflow that you're comfortable with, you
can use that, but otherwise this is an opinionated guide for setting up your
dev environment. Follow these steps and you'll end out with a functioning dev
environment and be able to submit your first PR.

This guide assumes at least a passing familiarity with
[Git](https://git-scm.com/), and that you already have it installed and
configured.

## `pyenv`, Virtual Environments, and You

We recommend [pyenv](https://github.com/pyenv/pyenv), since it allows
installing multiple different Python versions, which is important for testing
Salt across all the versions of Python that we support.

### On Linux

Install pyenv: 

    git clone https://github.com/pyenv/pyenv.git ~/.pyenv
    export PATH="$HOME/.pyenv/bin:$PATH"
    git clone https://github.com/pyenv/pyenv-virtualenv.git $(pyenv root)/plugins/pyenv-virtualenv

### On Mac

Install pyenv using brew:

    brew update
    brew install pyenv
    brew install pyenv-virtualenv

---

Now add pyenv to your `.bashrc`:

    export PATH="$HOME/.pyenv/bin:$PATH" >> ~/.bashrc
    pyenv init 2>> ~/.bashrc
    pyenv virtualenv-init 2>> ~/.bashrc

For other shells, see [the pyenv instructions](https://github.com/pyenv/pyenv#basic-github-checkout).

Go ahead and restart your shell. Now you should be able to install a new
version of Python:

    pyenv install 3.7.0

If that fails, don't panic! You're probably just missing some build
dependencies. Check out [pyenv common build
problems](https://github.com/pyenv/pyenv/wiki/Common-build-problems).

Now that you've got your version of Python installed, you can create a new
virtual environment with this command:

    pyenv virtualenv 3.7.0 salt

Then activate it:

    pyenv activate salt

Sweet! Now you're ready to clone salt so you can start hacking away!

### Cloning Salt

Clones are so shallow. Well, this one is anyway:

    git clone --depth=1 --origin salt https://github.com/saltstack/salt.git

This creates a shallow clone of salt, which should be fast. Most of the time
that's all you'll need, and you can start building out other commits as you go.
If you *really* want all 108,300+ commits you can just run `git fetch
--unshallow`. Then go make a sandwich because it's gonna be a while.

### Fork Salt

You're also going to want to head over to GitHub and create your own [fork of
salt](https://github.com/saltstack/salt/fork). Once you've got that setup you
can add it as a remote:

    git remote add yourname <YOUR SALT REMOTE>

If you use your name to refer to your fork, and `salt` to refer to the official
Salt repo you'll never get `upstream` or `origin` confused.

### `pre-commit` and `nox` Setup

Here at Salt we use [pre-commit](https://pre-commit.com/) and
[nox](https://nox.thea.codes/en/stable/) to make it easier for contributors to
get quick feedback. Nox enables us to run multiple different test
configurations, as well as other common tasks. You can think of it as Make with
superpowers. Pre-commit does what it sounds like - it configures some Git
pre-commit hooks to run `black` for formatting, `isort` for keeping our imports
sorted, and `pylint` to catch issues like unused imports, among others. You can
easily install them in your virtualenv with:

    python -m pip install pre-commit nox
    pre-commit install

Now before each commit, it will ensure that your code at least *looks* right
before you open a pull request. And with that step, it's time to start hacking
on Salt!


## Selecting an Issue

If you don't already have an issue in mind, you can search for [help
wanted](https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)
issues. If you also search for [good first
issue](https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22+label%3A%22good+first+issue%22)
then you should be able to find some issues that are good for getting started
contributing to Salt. [Documentation
issues](https://github.com/saltstack/salt/issues?q=is%3Aissue+is%3Aopen+label%3Adocumentation+)
are also good starter issues. When you find an issue that catches your eye (or
one of your own), it's a good idea to comment on the issue and mention that
you're working on it. Good communication is key to collaboration - so if you
don't have time to complete work on the issue, just leaving some information
about when you expect to pick things up again is a great idea!

## Hacking Away

### Salt, Tests, Documentation, and You

To merge code contributions, Salt requires:

- documentation
- meaningful passing tests
- correct code

Documentation fixes just require correct documentation.

#### What If I Don't Write Tests or Docs?

If you aren't into writing documentation or tests, we still welcome your
contributions! But your PR will be labeled `Needs Testcase` and `Help Wanted`
until someone can get to write the tests/documentation. Of course, if you have
a desire but just lack the skill we are more than happy to collaborate and help
out! There's the [documentation working
group](https://github.com/saltstack/docs-hub) and the [testing working
group](https://github.com/saltstack/community/tree/master/working_groups/wg-Testing).
We also regularly stream our test clinic [live on
Twitch](https://www.twitch.tv/saltstackinc) every Tuesday afternoon and
Thursday morning, Central Time. If you'd like specific help with tests, bring
them to the clinic.  If no community members need help, you can also just watch
tests written in real time.

### Documentation

Salt uses both docstrings, as well as normal reStructuredText files in the
`salt/doc` folder for documentation. Since we use nox, you can build your docs
and view them in your browser with this one-liner:

    python -m nox -e 'docs-html(compress=False, clean=False)'; cd doc/_build/html; python -m webbrowser http://localhost:8000/contents.html; python -m http.server

The first time this will take a while because there are a *lot* of modules.
Maybe you should go grab some dessert if you already finished that sandwich.
But once Sphinx is done building the docs, python should launch your default
browser with the URL http://localhost:8000/contents.html. Now you can navigate
to your docs and ensure your changes exist. If you make changes, you can simply
run this:

    cd -; python -m nox -e 'docs-html(compress=False, clean=False)'; cd doc/_build/html; python -m http.server

And then refresh your browser to get your updated docs. This one should be
quite a bit faster since Sphinx won't need to rebuild everything.

If your change is a doc-only change, you can go ahead and commit/push your code
and open a PR. Otherwise you'll want to write some tests and code.

### Running Development Salt

Note: If you run into any issues in this section, check the Troubleshooting
section.

If you're going to hack on the Salt codebase you're going to want to be able to
run Salt locally. The first thing you need to do is install Salt as an editable
pip install:

    python -m pip install -e .

This will let you make changes to Salt without having to re-install it.

After all of the dependencies and Salt are installed, it's time to set up the
config for development. Typically Salt runs as `root`, but you can specify
which user to run as. To configure that, just copy the master and minion
configs. We have .gitignore setup to ignore the `local/` directory, so we can
put all of our personal files there.

    mkdir -p local/etc/salt/

Create a master config file as `local/etc/salt/master`:

    cat <<EOF >local/etc/salt/master
    user: $(whoami)
    root_dir: $PWD/local/
    publish_port: 55505
    ret_port: 55506
    EOF

And a minion config as `local/etc/salt/minion`:

    cat <<EOF >local/etc/salt/minion
    user: $(whoami)
    root_dir: $PWD/local/
    master: localhost
    id: saltdev
    master_port: 55506
    EOF

Now you can start your Salt master and minion, specifying the config dir.

    salt-master --config-dir=local/etc/salt/ --log-level=debug --daemon
    salt-minion --config-dir=local/etc/salt/ --log-level=debug --daemon

Now you should be able to accept the minion key:

    salt-key -c local/etc/salt -Ay

And check that your master/minion are communicating:

    salt -c local/etc/salt \* test.version

Rather than running `test.version` from your master, you can run it from the
minion instead:

    salt-call -c local/etc/salt test.version

Note that you're running `salt-call` instead of `salt`, and you're not
specifying the minion (`\*`), but if you're running the dev version then you
still will need to pass in the config dir. Now that you've got Salt running,
you can hack away on the Salt codebase!

If you need to restart Salt for some reason, if you've made changes and they
don't appear to be reflected, this is one option:

    kill -INT $(pgrep salt-master)
    kill -INT $(pgrep salt-minion)

If you'd rather not use `kill`, you can have a couple of terminals open with
your salt virtualenv activated and omit the `--daemon` argument. Salt will run
in the foreground, so you can just use ctrl+c to quit.

### Test First? Test Last? Test Meaningfully!

You can write tests first or tests last, as long as your tests are meaningful
and complete! *Typically* the best tests for Salt are going to be unit tests.
Testing is [a whole topic on its
own](https://docs.saltstack.com/en/master/topics/tutorials/writing_tests.html),
But you may also want to write functional or integration tests. You'll find
those in the `salt/tests` directory.

When you're thinking about tests to write, the most important thing to keep in
mind is, "What, exactly, am I testing?" When a test fails, you should know:

- What, specifically, failed?
- Why did it fail?
- As much as possible, what do I need to do to fix this failure?

If you can't answer those questions then you might need to refactor your tests.

When you're running tests locally, you should make sure that if you remove your
code changes your tests are failing. If your tests *aren't* failing when you
haven't yet made changes, then it's possible that you're testing the wrong
thing.

But whether you adhere to TDD/BDD, or you write your code first and your tests
last, ensure that your tests are meaningful.

#### Running Tests

As previously mentioned, we use `nox`, and that's how we run our tests. You
should have it installed by this point but if not you can install it with this:

    python -m pip install nox

Now you can run your tests:

    python -m nox -e "pytest-3.7(coverage=False)" -- tests/unit/cli/test_batch.py

It's a good idea to install [espeak](https://github.com/espeak-ng/espeak-ng) or
use `say` on Mac if you're running some long-running tests. You can do
something like this:

    python -m nox -e "pytest-3.7(coverage=False)" -- tests/unit/cli/test_batch.py; espeak "Tests done, woohoo!"

That way you don't have to keep monitoring the actual test run.

### Changelog and Commit!

When you write your commit message you should use imperative style. Do this:

> Add frobnosticate capability

Don't do this:

> Added frobnosticate capability

But that advice is backwards for the changelog. We follow the
[keepachangelog](https://keepachangelog.com/en/1.0.0/) approach for our
changelog, and use towncrier to generate it for each release. As a contributor,
all that means is that you need to add a file to the `salt/changelog`
directory, using the `<issue #>.<type>` format. For instanch, if you fixed
issue 123, you would do:

    echo "Made sys.doc inform when no minions return" > changelog/123.fixed

And that's all that would go into your file. When it comes to your commit
message, it's usually a good idea to add other information - what does a
reviewer need to know about the change that you made? If someone isn't an
expert in this area, what will they need to know?

This will also help you out, because when you go to create the PR it will
automatically insert the body of your commit messages.

## PR Time!

Once you've done all your dev work and tested locally, you should check out our
[PR
guidelines](https://docs.saltstack.com/en/develop/topics/development/pull_requests.html).
After you read that page, it's time to [open a new
PR](https://github.com/saltstack/salt/compare). Fill out the PR template - you
should have updated or created any necessary docs, and written tests if you're
providing a code change. When you submit your PR, we have a suite of tests that
will run across different platforms. You will also get a reviewer assigned. If
your PR is submitted during the week you should be able to expect some kind of
communication within that business day. If your tests are passing and we're not
in a code freeze, ideally your code will be merged that day. If you haven't
heard from your assigned reviewer, ping them on GitHub, [irc][salt on
freenode], or Community Slack.

If, as mentioned earlier, you're not interested in writing tests or docs, just
note that in your PR. Something like, "I'm not interested in writing
docs/tests, I just wanted to provide this fix." Otherwise, we will request that
you add appropriate docs/tests.

Congrats! You're a Salt developer! You rock!

## Troubleshooting

### zmq.core.error.ZMQError

Once the minion starts, you may see an error like the following::

    zmq.core.error.ZMQError: ipc path "/path/to/your/virtualenv/var/run/salt/minion/minion_event_7824dcbcfd7a8f6755939af70b96249f_pub.ipc" is longer than 107 characters (sizeof(sockaddr_un.sun_path)).

This means that the path to the socket the minion is using is too long. This is
a system limitation, so the only workaround is to reduce the length of this
path. This can be done in a couple different ways:

1.  Create your virtualenv in a path that is short enough.
2.  Edit the :conf_minion:`sock_dir` minion config variable and reduce its
    length. Remember that this path is relative to the value you set in
    :conf_minion:`root_dir`.

NOTE: The socket path is limited to 107 characters on Solaris and Linux, and
103 characters on BSD-based systems.

### No permissions to access ...

If you forget to pass your config path to any of the `salt*` commands, you might see

    No permissions to access "/var/log/salt/master", are you running as the
    correct user?

Just pass `-c local/etc/salt` (or whatever you named it)

### File descriptor limit

You might need to raise your file descriptor limit. You can check it with:

    ulimit -n

If the value is less than 2047, you should increase it with:

    ulimit -n 2047
    # For c-shell:
    limit descriptors 2047
    
[salt on freenode]: https://webchat.freenode.net/#salt


### Pygit2 or other dependency install fails

You may see some failure messages when installing requirements. You can
directly access your nox environment and possibly install pygit (or other
dependency) that way. When you run nox, you'll see a message like this:

    nox > Re-using existing virtual environment at .nox/pytest-parametrized-3-crypto-none-transport-zeromq-coverage-false.

For this, you would be able to install with:

    .nox/pytest-parametrized-3-crypto-none-transport-zeromq-coverage-false/bin/python -m pip install pygit2
