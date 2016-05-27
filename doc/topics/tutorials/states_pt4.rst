=======================
States tutorial, part 4
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
        - /srv/salt
        - /mnt/salt-nfs/base

Salt's fileserver collapses the list of root directories into a single virtual
environment containing all files from each root. If the same file exists at the
same relative path in more than one root, then the top-most match "wins". For
example, if ``/srv/salt/foo.txt`` and ``/mnt/salt-nfs/base/foo.txt`` both
exist, then ``salt://foo.txt`` will point to ``/srv/salt/foo.txt``.

.. note::

    When using multiple fileserver backends, the order in which they are listed
    in the :conf_master:`fileserver_backend` parameter also matters. If both
    ``roots`` and ``git`` backends contain a file with the same relative path,
    and ``roots`` appears before ``git`` in the
    :conf_master:`fileserver_backend` list, then the file in ``roots`` will
    "win", and the file in gitfs will be ignored.

    A more thorough explanation of how Salt's modular fileserver works can be
    found :ref:`here <file-server-backends>`. We recommend reading this.

Environment configuration
=========================

Configure a multiple-environment setup like so:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt/prod
      qa:
        - /srv/salt/qa
        - /srv/salt/prod
      dev:
        - /srv/salt/dev
        - /srv/salt/qa
        - /srv/salt/prod

Given the path inheritance described above, files within ``/srv/salt/prod``
would be available in all environments. Files within ``/srv/salt/qa`` would be
available in both ``qa``, and ``dev``. Finally, the files within
``/srv/salt/dev`` would only be available within the ``dev`` environment.

Based on the order in which the roots are defined, new files/states can be
placed within ``/srv/salt/dev``, and pushed out to the dev hosts for testing.

Those files/states can then be moved to the same relative path within
``/srv/salt/qa``, and they are now available only in the ``dev`` and ``qa``
environments, allowing them to be pushed to QA hosts and tested.

Finally, if moved to the same relative path within ``/srv/salt/prod``, the
files are now available in all three environments.

Practical Example
=================

As an example, consider a simple website, installed to ``/var/www/foobarcom``.
Below is a top.sls that can be used to deploy the website:

``/srv/salt/prod/top.sls:``

.. code-block:: yaml

    base:
      'web*prod*':
        - webserver.foobarcom
    qa:
      'web*qa*':
        - webserver.foobarcom
    dev:
      'web*dev*':
        - webserver.foobarcom


Using pillar, roles can be assigned to the hosts:

``/srv/pillar/top.sls:``

.. code-block:: yaml

    base:
      'web*prod*':
        - webserver.prod
      'web*qa*':
        - webserver.qa
      'web*dev*':
        - webserver.dev

``/srv/pillar/webserver/prod.sls:``

.. code-block:: yaml

    webserver_role: prod

``/srv/pillar/webserver/qa.sls:``

.. code-block:: yaml

    webserver_role: qa

``/srv/pillar/webserver/dev.sls:``

.. code-block:: yaml

    webserver_role: dev


And finally, the SLS to deploy the website:

``/srv/salt/prod/webserver/foobarcom.sls:``

.. code-block:: yaml

    {% if pillar.get('webserver_role', '') %}
    /var/www/foobarcom:
      file.recurse:
        - source: salt://webserver/src/foobarcom
        - env: {{ pillar['webserver_role'] }}
        - user: www
        - group: www
        - dir_mode: 755
        - file_mode: 644
    {% endif %}

Given the above SLS, the source for the website should initially be placed in
``/srv/salt/dev/webserver/src/foobarcom``.

First, let's deploy to dev. Given the configuration in the top file, this can
be done using :py:func:`state.apply <salt.modules.state.apply_>`:

.. code-block:: bash

    salt --pillar 'webserver_role:dev' state.apply

However, in the event that it is not desirable to apply all states configured
in the top file (which could be likely in more complex setups), it is possible
to apply just the states for the ``foobarcom`` website, by invoking
:py:func:`state.apply <salt.modules.state.apply_>` with the desired SLS target
as an argument:

.. code-block:: bash

    salt --pillar 'webserver_role:dev' state.apply webserver.foobarcom

Once the site has been tested in dev, then the files can be moved from
``/srv/salt/dev/webserver/src/foobarcom`` to
``/srv/salt/qa/webserver/src/foobarcom``, and deployed using the following:

.. code-block:: bash

    salt --pillar 'webserver_role:qa' state.apply webserver.foobarcom

Finally, once the site has been tested in qa, then the files can be moved from
``/srv/salt/qa/webserver/src/foobarcom`` to
``/srv/salt/prod/webserver/src/foobarcom``, and deployed using the following:

.. code-block:: bash

    salt --pillar 'webserver_role:prod' state.apply webserver.foobarcom

Thanks to Salt's fileserver inheritance, even though the files have been moved
to within ``/srv/salt/prod``, they are still available from the same
``salt://`` URI in both the qa and dev environments.


Continue Learning
=================

The best way to continue learning about Salt States is to read through the
:doc:`reference documentation </ref/states/index>` and to look through examples
of existing state trees. Many pre-configured state trees
can be found on GitHub in the `saltstack-formulas`_ collection of repositories.

.. _`saltstack-formulas`: https://github.com/saltstack-formulas

If you have any questions, suggestions, or just want to chat with other people
who are using Salt, we have a very :ref:`active community <salt-community>`
and we'd love to hear from you.

In addition, by continuing to :doc:`part 5 <states_pt5>`, you can learn about
the powerful orchestration of which Salt is capable.
