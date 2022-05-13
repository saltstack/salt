==========================
Troubleshooting Salt Cloud
==========================

This page describes various steps for troubleshooting problems that may arise
while using Salt Cloud.

Virtual Machines Are Created, But Do Not Respond
================================================

Are TCP ports 4505 and 4506 open on the master? This is easy to overlook on new
masters. Information on how to open firewall ports on various platforms can be
found :ref:`here <firewall>`.


Generic Troubleshooting Steps
=============================
This section describes a set of instructions that are useful to a large number
of situations, and are likely to solve most issues that arise.

Debug Mode
----------
Frequently, running Salt Cloud in debug mode will reveal information about a
deployment which would otherwise not be obvious:

.. code-block:: bash

    salt-cloud -p myprofile myinstance -l debug

Keep in mind that a number of messages will appear that look at first like
errors, but are in fact intended to give developers factual information to
assist in debugging. A number of messages that appear will be for cloud
providers that you do not have configured; in these cases, the message usually
is intended to confirm that they are not configured.


Salt Bootstrap
--------------
By default, Salt Cloud uses the Salt Bootstrap script to provision instances:

.. _`Salt Bootstrap`: https://github.com/saltstack/salt-bootstrap

This script is packaged with Salt Cloud, but may be updated without updating
the Salt package:

.. code-block:: bash

    salt-cloud -u


The Bootstrap Log
-----------------
If the default deploy script was used, there should be a file in the ``/tmp/``
directory called ``bootstrap-salt.log``. This file contains the full output from
the deployment, including any errors that may have occurred.


Keeping Temp Files
------------------
Salt Cloud uploads minion-specific files to instances once they are available
via SSH, and then executes a deploy script to put them into the correct place
and install Salt. The ``--keep-tmp`` option will instruct Salt Cloud not to
remove those files when finished with them, so that the user may inspect them
for problems:

.. code-block:: bash

    salt-cloud -p myprofile myinstance --keep-tmp

By default, Salt Cloud will create a directory on the target instance called
``/tmp/.saltcloud/``. This directory should be owned by the user that is to
execute the deploy script, and should have permissions of ``0700``.

Most cloud hosts are configured to use ``root`` as the default initial user
for deployment, and as such, this directory and all files in it should be owned
by the ``root`` user.

The ``/tmp/.saltcloud/`` directory should the following files:

- A ``deploy.sh`` script. This script should have permissions of ``0755``.
- A ``.pem`` and ``.pub`` key named after the minion. The ``.pem`` file should
  have permissions of ``0600``. Ensure that the ``.pem`` and ``.pub`` files have
  been properly copied to the ``/etc/salt/pki/minion/`` directory.
- A file called ``minion``. This file should have been copied to the
  ``/etc/salt/`` directory.
- Optionally, a file called ``grains``. This file, if present, should have been
  copied to the ``/etc/salt/`` directory.


Unprivileged Primary Users
--------------------------
Some cloud hosts, most notably EC2, are configured with a different primary user.
Some common examples are ``ec2-user``, ``ubuntu``, ``fedora``, and ``bitnami``.
In these cases, the ``/tmp/.saltcloud/`` directory and all files in it should
be owned by this user.

Some cloud hosts, such as EC2, are configured to not require these users to
provide a password when using the ``sudo`` command. Because it is more secure
to require ``sudo`` users to provide a password, other hosts are configured
that way.

If this instance is required to provide a password, it needs to be configured
in Salt Cloud. A password for sudo to use may be added to either the provider
configuration or the profile configuration:

.. code-block:: yaml

    sudo_password: mypassword


``/tmp/`` is Mounted as ``noexec``
----------------------------------
It is more secure to mount the ``/tmp/`` directory with a ``noexec`` option.
This is uncommon on most cloud hosts, but very common in private
environments. To see if the ``/tmp/`` directory is mounted this way, run the
following command:

.. code-block:: bash

    mount | grep tmp

The if the output of this command includes a line that looks like this, then
the ``/tmp/`` directory is mounted as ``noexec``:

.. code-block:: console

    tmpfs on /tmp type tmpfs (rw,noexec)

If this is the case, then the ``deploy_command`` will need to be changed
in order to run the deploy script through the ``sh`` command, rather than trying
to execute it directly. This may be specified in either the provider or the
profile config:

.. code-block:: yaml

    deploy_command: sh /tmp/.saltcloud/deploy.sh

Please note that by default, Salt Cloud will place its files in a directory
called ``/tmp/.saltcloud/``. This may be also be changed in the provider or
profile configuration:

.. code-block:: yaml

    tmp_dir: /tmp/.saltcloud/

If this directory is changed, then the ``deploy_command`` need to be changed
in order to reflect the ``tmp_dir`` configuration.


Executing the Deploy Script Manually
------------------------------------
If all of the files needed for deployment were successfully uploaded to the
correct locations, and contain the correct permissions and ownerships, the
deploy script may be executed manually in order to check for other issues:

.. code-block:: bash

    cd /tmp/.saltcloud/
    ./deploy.sh
