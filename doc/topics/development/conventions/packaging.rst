=========================
SaltStack Packaging Guide
=========================

Since Salt provides a powerful toolkit for system management and automation,
the package can be spit into a number of sub-tools. While packaging Salt as
a single package containing all components is perfectly acceptable, the split
packages should follow this convention.

Patching Salt For Distributions
===============================

The occasion may arise where Salt source and default configurations may need
to be patched. It is preferable if Salt is only patched to include platform
specific additions or to fix release time bugs. It is preferable that
configuration settings and operations remain in the default state, as changes
here lowers the user experience for users moving across distributions.

In the event where a packager finds a need to change the default configuration
it is advised to add the files to the master.d or minion.d directories.

Source Files
============

Release packages should always be built from the source tarball distributed via
pypi. Release packages should *NEVER* use a git checkout as the source for
distribution.

Single Package
==============

Shipping Salt as a single package, where the minion, master, and all tools are
together is perfectly acceptable and practiced by distributions such as
FreeBSD.

Split Package
=============

Salt Should always be split in a standard way, with standard dependencies, this lowers
cross distribution confusion about what components are going to be shipped with
specific packages. These packages can be defined from the Salt Source as of
Salt 2014.1.0:

Salt Common
-----------

The `salt-common` or `salt` package should contain the files provided by the
salt python package, or all files distributed from the ``salt/`` directory in
the source distribution packages. The documentation contained under the
``doc/`` directory can be a part of this package but splitting out a doc
package is preferred.
Since salt-call is the entry point to utilize the libs and is useful for all
salt packages it is included in the salt-common package.

Name
~~~~

- `salt` OR `salt-common`

Files
~~~~~

- `salt/*`
- `man/salt.7`
- `scripts/salt-call`
- `tests/*`
- `man/salt-call.1`

Depends
~~~~~~~

- `Python 2.6-2.7`
- `PyYAML`
- `Jinja2`

Salt Master
-----------

The `salt-master` package contains the applicable scripts, related man
pages and init information for the given platform.

Name
~~~~

- `salt-master`

Files
~~~~~

- `scripts/salt-master`
- `scripts/salt`
- `scripts/salt-run`
- `scripts/salt-key`
- `scripts/salt-cp`
- `pkg/<master init data>`
- `man/salt.1`
- `man/salt-master.1`
- `man/salt-run.1`
- `man/salt-key.1`
- `man/salt-cp.1`
- `conf/master`

Depends
~~~~~~~

- `Salt Common`
- `ZeroMQ` >= 3.2
- `PyZMQ` >= 2.10
- `PyCrypto`
- `M2Crypto`
- `Python MessagePack` (Messagepack C lib, or msgpack-pure)

Salt Syndic
-----------

The Salt Syndic package can be rolled completely into the Salt Master package.
Platforms which start services as part of the package deployment need to
maintain a separate `salt-syndic` package (primarily Debian based platforms).

The Syndic may optionally not depend on the anything more than the Salt Master since
the master will bring in all needed dependencies, but fall back to the platform
specific packaging guidelines.

Name
~~~~

- `salt-syndic`

Files
~~~~~

- `scripts/salt-syndic`
- `pkg/<syndic init data>`
- `man/salt-syndic.1`

Depends
~~~~~~~

- `Salt Common`
- `Salt Master`
- `ZeroMQ` >= 3.2
- `PyZMQ` >= 2.10
- `PyCrypto`
- `M2Crypto`
- `Python MessagePack` (Messagepack C lib, or msgpack-pure)

Salt Minion
-----------

The Minion is a standalone package and should not be split beyond the
`salt-minion` and `salt-common` packages.

Name
~~~~

- `salt-minion`

Files
~~~~~

- `scripts/salt-minion`
- `pkg/<minion init data>`
- `man/salt-minion.1`
- `conf/minion`

Depends
~~~~~~~

- `Salt Common`
- `ZeroMQ` >= 3.2
- `PyZMQ` >= 2.10
- `PyCrypto`
- `M2Crypto`
- `Python MessagePack` (Messagepack C lib, or msgpack-pure)

Salt SSH
--------

Since Salt SSH does not require the same dependencies as the minion and master, it
should be split out.

Name
~~~~

- `salt-ssh`

Files
~~~~~

- `scripts/salt-ssh`
- `man/salt-ssh.1`
- `conf/cloud*`

Depends
~~~~~~~

- `Salt Common`
- `Python MessagePack` (Messagepack C lib, or msgpack-pure)

Salt Cloud
----------

As of Salt 2014.1.0 Salt Cloud is included in the same repo as Salt. This
can be split out into a separate package or it can be included in the
salt-master package.

Name
~~~~

- `salt-cloud`

Files
~~~~~

- `scripts/salt-cloud`
- `man/salt-cloud.1`

Depends
~~~~~~~

- `Salt Common`
- `apache libcloud` >= 0.14.0

Salt Doc
--------

The documentation package is very distribution optional. A completely split
package will split out the documentation, but some platform conventions do not
prefer this.
If the documentation is not split out, it should be included with the
`Salt Common` package.

Name
----

- `salt-doc`

Files
~~~~~

- `doc/*`

Optional Depends
~~~~~~~~~~~~~~~~

- `Salt Common`
- `Python Sphinx`
- `Make`
