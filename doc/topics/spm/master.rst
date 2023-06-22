.. meta::
    :status: review

.. _spm-master:

=======================
Installing SPM Packages
=======================
SPM packages are installed to your Salt master, where they are available to Salt minions
using all of Salt's package management functions.

Configuring Remote Repositories
===============================
Before SPM can use a repository, two things need to happen. First, the Salt master needs to
know where the repository is through a configuration process. Then it needs to pull down the repository
metadata.

Repository Configuration Files
------------------------------
Repositories are configured by adding each of them to the
``/etc/salt/spm.repos.d/spm.repo`` file on each Salt master. This file contains
the name of the repository, and the link to the repository:

.. code-block:: yaml

    my_repo:
      url: https://spm.example.com/

For HTTP/HTTPS Basic authorization you can define credentials:

.. code-block:: yaml

    my_repo:
      url: https://spm.example.com/
      username: user
      password: pass

Beware of unauthorized access to this file, please set at least 0640 permissions for this configuration file:

The URL can use ``http``, ``https``, ``ftp``, or ``file``.

.. code-block:: yaml

    my_repo:
      url: file:///srv/spm_build


Updating Local Repository Metadata
----------------------------------
After the repository is configured on the Salt master, repository metadata is
downloaded using the ``spm update_repo`` command:

.. code-block:: bash

    spm update_repo

.. note::
    A file for each repo is placed in ``/var/cache/salt/spm`` on the Salt master
    after you run the `update_repo` command. If you add a repository and it
    does not seem to be showing up, check this path to verify that the
    repository was found.

Update File Roots
=================
SPM packages are installed to the ``srv/spm/salt`` folder on your Salt master.
This path needs to be added to the file roots on your Salt master
manually.

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt
        - /srv/spm/salt

Restart the salt-master service after updating the ``file_roots`` setting.

Installing Packages
===================
To install a package, use the ``spm install`` command:

.. code-block:: bash

    spm install apache


.. warning::
    Currently, SPM does not check to see if files are already in place before
    installing them. That means that existing files will be overwritten without
    warning.

.. _spm-master-local:

Installing directly from an SPM file
------------------------------------
You can also install SPM packages using a local SPM file using the ``spm local
install`` command:

.. code-block:: bash

    spm local install /srv/spm/apache-201506-1.spm

An SPM repository is not required when using `spm local install`.

Pillars
=======
If an installed package includes Pillar data, be sure to target the installed
pillar to the necessary systems using the pillar Top file.

Removing Packages
=================
Packages may be removed after they are installed using the ``spm remove``
command.

.. code-block:: bash

    spm remove apache

If files have been modified, they will not be removed. Empty directories will
also be removed.
