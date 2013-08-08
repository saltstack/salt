=============
Salt Formulas
=============

Formulas are pre-written Salt States and optional Pillar configuration. They
are as open-ended as Salt States themselves and can be used for tasks such as
installing a package, configuring and starting a service, setting up users or
permissions, and many other common tasks.

.. seealso:: Salt Formula repositories

    All official Salt Formulas are found as separate Git repositories in the
    "saltstack-formulas" organization on GitHub:

    https://github.com/saltstack-formulas

As an example, quickly install and configure the popular memcached server using
sane defaults simply by including the :formula:`memcached-formula` repository
into an existing Salt States tree.

Installation
============

Each Salt Formula is an individual Git repository designed as a drop-in
addition to an existing Salt State tree either by using Salt's GitFS fileserver
backend or by cloning the repository manually.

Adding a Formula as a GitFS remote
----------------------------------

One design goal of Salt's GitFS fileserver backend was to facilitate reusable
States so this is a quick and natural way to use Formulas.

.. seealso:: :ref:`Setting up GitFS <tutorial-gitfs>`

1.  Add one or more Formula repository URLs as remotes in the
    :conf_master:`gitfs_remotes` list in the Salt Master configuration file.
2.  Restart the Salt master.

Adding a Formula directory manually
-----------------------------------

Since Formulas are simply directories they can be copied onto the local file
system by using Git to clone the repository or by downloading and expanding a
tarball or zip file of the directory.

Usage
=====

Each Formula is intended to be immediately usable with sane defaults without
any additional configuration. Many formulas are also configurable by including
data in Pillar Many formulas are also configurable by including data in Pillar;
see the :file:`pillar.example` file in each Formula repository for available
options.

Including a Formula in an existing State tree
---------------------------------------------

Formula may be included in an existing ``sls`` file. This is often useful when
a state you are writing needs to ``require`` or ``extend`` a state defined in
the formula.

Here is an example of a state that uses the :formula:`epel-formula` in a
``require`` declaration which directs Salt to not install the ``python26``
package until after the EPEL repository has also been installed:

.. code:: yaml

    include:
      - epel

    python26:
      pkg:
        - installed
        - require:
          - pkg: epel

Including a Formula from a Top File
-----------------------------------

Some Formula perform completely standalone installations that are not
referenced from other state files. It is usually cleanest to include these
Formula directly from a Top File.

For example the easiest way to set up an OpenStack deployment on a single
machine is to include the :formula:`openstack-standalone-formula` directly from
a :file:`top.sls` file:

.. code:: yaml

    base:
      'myopenstackmaster':
        - openstack

Quickly deploying OpenStack across several dedicated machines could also be
done directly from a Top File and may look something like this:

.. code:: yaml

    base:
      'controller':
        - openstack.horizon
        - openstack.keystone
      'hyper-*':
        - openstack.nova
        - openstack.glance
      'storage-*':
        - openstack.swift

Configuring Formula using Pillar
--------------------------------

Although Salt Formulas are designed to work out of the box many Formula support
additional configuration through :ref:`Pillar <pillar>`. Examples of available
options can be found in a file named :file:`pillar.example` in the root
directory of each Formula repository.

Modifying default Formula behavior
----------------------------------

Remember that Formula are regular Salt States and can be used with all Salt's
normal mechanisms for determining execution order. Formula can be required from
other States with ``require`` declarations, they can be modified using
``extend``, they can made to watch other states with ``watch_in``, they can be
used as templates for other States with ``use``. Don't be shy to read through
the source for each Formula!

Reporting problems & making additions
-------------------------------------

Each Formula is a separate repository on GitHub. If you encounter a bug with a
Formula please file an issue in the respective repository! Send fixes and
additions as a pull request. Add tips and tricks to the repository wiki.

Writing Formulas
================

Each Formula is a separate repository in the `saltstack-formulas`_ organization
on GitHub.

.. note:: Get involved creating new Formula

    The best way to create new Formula repositories for now is to create a
    repository in your own account on GitHub and notify a SaltStack employee
    when it is ready. We will add you as a collaborator on the
    `saltstack-formulas`_ organization and help you transfer the repository
    over. Ping a SaltStack employee on IRC (``#salt`` on Freenode) or send an
    email to the Salt mailing list.

Each Salt Formula must be platform-agnostic and should be usable in a default
state. Formula can be configured and parameterized using values from Pillar.

Repository structure
--------------------

A basic Formula repository should have the following characteristics:

* The repository name must have the "-formula" suffix.
* A :file:`LICENSE` file describing the software license governing the repo.
* A :file:`README.rst` file describing each available ``.sls`` file, target
  platforms, and any other installation or usage instructions or tips.
* If the formula has any configuration parameters the repository should contain
  a :file:`pillar.example` file containing all available parameters that is
  suitable for copy-and-pasting into an existing Pillar tree.
* Finally each repo must have a directory containing the ``.sls`` files.

SLS files
---------

* Individual standalone files

Platform agnostic
-----------------

* Parameterize platform-specific package names using Jinja variables.
* Wrap platform-specific states within conditionals.

Configuration and parameterization
----------------------------------

* Use Pillar; use Pillar defaults

Scripting
---------

* Call out to Salt execution modules as much as needed.
* Jinja macros are discouraged.

Testing Formulas
================

Salt Formulas are tested by running each ``.sls`` file via :py:func:`state.sls
<salt.modules.state.sls>` and checking the output for success or failure. This
is done for each supported platform.

.. ............................................................................

.. _`saltstack-formulas`: https://github.com/saltstack-formulas
