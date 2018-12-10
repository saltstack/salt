.. meta::
    :status: review

.. _spm-repo:

=========================
Distributing SPM Packages
=========================
SPM packages can be distributed to Salt masters over HTTP(S), FTP, or through the
file system. The SPM repo can be hosted on any system where you can install
Salt. Salt is installed so you can run the ``spm create_repo`` command when you
update or add a package to the repo. SPM repos do not require the salt-master,
salt-minion, or any other process running on the system.

.. note::
    If you are hosting the SPM repo on a system where you can not or do not
    want to install Salt, you can run the ``spm create_repo`` command on the
    build system and then copy the packages and the generated ``SPM-METADATA``
    file to the repo. You can also install SPM files :ref:`directly on a Salt
    master <spm-master-local>`, bypassing the repository completely.

Setting up a Package Repository
===============================
After packages are built, the generated SPM files are placed in the
``srv/spm_build`` folder.

Where you place the built SPM files on your repository server depends on how
you plan to make them available to your Salt masters.

You can share the ``srv/spm_build`` folder on the network, or copy the files to
your FTP or Web server.

Adding a Package to the repository
==================================
New packages are added by simply copying the SPM file to the repo folder, and then
generating repo metadata.

Generate Repo Metadata
======================
Each time you update or add an SPM package to your repository, issue an ``spm
create_repo`` command:

.. code-block:: bash

    spm create_repo /srv/spm_build

SPM generates the repository metadata for all of the packages in that directory
and places it in an ``SPM-METADATA`` file at the folder root. This command is
used even if repository metadata already exists in that directory.
