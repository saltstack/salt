=======================
States tutorial, part 3
=======================

.. note::

  This tutorial builds on topics covered in :doc:`part 1 <states_pt1>`,
  :doc:`part 2 <states_pt2>` and :doc:`part 3 <states_pt3>`. It is recommended
  that you begin there.

This part of the tutorial will show how to use salt's :conf_master:`file_roots`
to set up a workflow in which states can be "promoted" from dev, to QA, to
production.

Salt fileserver path inheritance
================================

Salt's fileserver allows for more than one root directory per environment, like
in the below example, which uses both a local directory and a secondary
location shared to the salt master via NFS:

.. code-block:: yaml

    # In the master config file (/etc/salt/master)
    file_roots:
      base:
        - /srv/salt/base
        - /mnt/salt-nfs/base

Salt's fileserver collapses the list of root directories into a single virtual
environment containing all files from each root. If the same file exists at the
same relative path in more than one root, then the top-most match "wins". For
example, if ``/srv/salt/foo.txt`` and ``/mnt/salt-nfs/base/foo.txt`` both
exist, then ``salt://foo.txt`` will point to ``/srv/salt/foo.txt``.

Environment configuration
=========================

Configure a multiple-environment setup like so:

.. code-block:: yaml

file_roots:
  base:
    - /srv/salt/base
  dev:
    - /srv/salt/dev
    - /srv/salt/qa
    - /srv/salt/base
  qa:
    - /srv/salt/qa
    - /srv/salt/base

Given the path inheritance described above, files within ``/srv/salt/base``
would be available in all environments. Files within ``/srv/salt/qa`` would be
available in both ``qa``, and ``dev``. Finally, the files within
``/srv/salt/dev`` would only be available within the ``dev`` environment.

Based on the order in which the roots are defined, new files/states can be
placed within ``/srv/salt/dev``, and pushed out to the dev hosts for testing.

Those files/states can then be moved to the same relative path within
``/srv/salt/qa``, and they are now available only in the ``dev`` and ``qa``
environments, allowing them to be pushed to QA hosts and tested.

Finally, if moved to the same relative path within ``/srv/salt/base``, the
files are now available in all three environments.


Continue learning
=================

The best way to continue learning about Salt States is to read through the
:doc:`reference documentation </ref/states/index>` and to look through examples
of existing :term:`state trees <state tree>`. Many pre-configured state trees
can be found on Github in the `saltstack-formulas`_ collection of repositories.

.. _`saltstack-formulas`: https://github.com/saltstack-formulas

If you have any questions, suggestions, or just want to chat with other people
who are using Salt, we have a very :doc:`active community </topics/community>`
and we'd love to hear from you.
