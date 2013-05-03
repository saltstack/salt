===================
Debian Installation
===================

Currently the latest packages for Debian Stable and Testing (Squeeze
and Wheezy) are published in our (saltstack.com) debian repository.

Packages for Debian Unstable (Sid) are available in the main debian
repository.

Configure Apt
-------------


Squeeze (Stable)
~~~~~~~~~~~~~~~~

For squeeze, you will need to enable the debian backports repository
as well as the debian.saltstack.com repository. To do so, add the
following to ``/etc/apt/sources.list`` or a file in
``/etc/apt/sources.list.d``::

  deb http://debian.saltstack.com/debian squeeze-saltstack main
  deb http://backports.debian.org/debian-backports squeeze-backports main contrib non-free



Wheezy (Testing)
~~~~~~~~~~~~~~~~

For wheezy, the following line is needed in either
``/etc/apt/sources.list`` or a file in ``/etc/apt/sources.list.d``::

  deb http://debian.saltstack.com/debian wheezy-saltstack main



Sid (Unstable)
~~~~~~~~~~~~~~

You do not need to add anything to your apt sources. Salt is already
in the main debian archive.




Import the repository key.
--------------------------

If you are using the debian.saltstack.com repository (ie using squeeze
or wheezy), you will need to import the key used for signing. This is
not needed for those using sid.

.. code-block:: bash

    wget -q -O- "http://debian.saltstack.com/debian-salt-team-joehealy.gpg.key" | apt-key add -

.. note:: 
 
    You can optionally verify the key integrity with ``sha512sum`` using the 
    public key signature shown here. E.g::

        echo "b702969447140d5553e31e9701be13ca11cc0a7ed5fe2b30acb8491567560ee62f834772b5095d735dfcecb2384a5c1a20045f52861c417f50b68dd5ff4660e6  debian-salt-team-joehealy.gpg.key" | sha512sum -c

Update the package database
---------------------------

.. code-block:: bash

    apt-get update


Install packages
----------------

Install the Salt master, minion, or syndic from the repository with the apt-get 
command. These examples each install one daemon, but more than one package name 
may be given at a time:

.. code-block:: bash

    apt-get install salt-master 

.. code-block:: bash

    apt-get install salt-minion

.. code-block:: bash

    apt-get install salt-syndic

.. _Debian-config:

Post-installation tasks
-----------------------

Now go to the :doc:`Configuring Salt</topics/configuration>` page.


Notes
-----

1. These packages will be backported from the packages in debian
unstable. This means that the packages will be uploaded to unstable
first and then backported over the next day or so.

2. These packages will be tracking the released versions of salt
rather than maintaining a stable fixed feature set. If a fixed version
is what you desire, then either pinning or manual installation may be
more appropriate for you.

3. The version numbering and backporting process should provide clean
upgrade paths between debian versions.

4. The packages currently depend on zeromq 2 rather than 3.2. This is
likely to be a problem for some users. Following the next debian
stable release (expected shortly), work will commence to depend on and
build against zeromq 3.2. Depending on other packages, this migration
may take some time. 

There many situations where these packages (and their predecessors)
have proven to be stable.

If you have any questions regarding these, please email the mailing
list or look for joehh on irc.



