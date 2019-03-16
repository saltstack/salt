.. _salt-bootstrap:

==============
Salt Bootstrap
==============

The Salt Bootstrap Script allows a user to install the Salt Minion or Master
on a variety of system distributions and versions.

The Salt Bootstrap Script is a shell script is known as ``bootstrap-salt.sh``.
It runs through a series of checks to determine the operating system type and
version. It then installs the Salt binaries using the appropriate methods.

The Salt Bootstrap Script installs the minimum number of packages required to
run Salt. This means that in the event you run the bootstrap to install via
package, Git will not be installed. Installing the minimum number of packages
helps ensure the script stays as lightweight as possible, assuming the user
will install any other required packages after the Salt binaries are present
on the system.

The Salt Bootstrap Script is maintained in a separate repo from Salt, complete
with its own issues, pull requests, contributing guidelines, release protocol,
etc.

To learn more, please see the Salt Bootstrap repo links:

- `Salt Bootstrap repo`_
- `README`_: includes supported operating systems, example usage, and more.
- `Contributing Guidelines`_
- `Release Process`_

.. note::

    The Salt Bootstrap script can be found in the Salt repo under the
    ``salt/cloud/deploy/bootstrap-salt.sh`` path. Any changes to this file
    will be overwritten! Bug fixes and feature additions must be submitted
    via the `Salt Bootstrap repo`_. Please see the Salt Bootstrap Script's
    `Release Process`_ for more information.

.. _Salt Bootstrap repo: https://github.com/saltstack/salt-bootstrap
.. _README: https://github.com/saltstack/salt-bootstrap#bootstrapping-salt
.. _Contributing Guidelines: https://github.com/saltstack/salt-bootstrap/blob/develop/CONTRIBUTING.md
.. _Release Process: https://github.com/saltstack/salt-bootstrap/blob/develop/CONTRIBUTING.md#release-information
