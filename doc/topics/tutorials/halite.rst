=================================
Installing and Configuring Halite
=================================

In this tutorial, we'll walk through installing and setting up Halite. As of
2013-10-12, a packaged version of Halite is not available. In addition, the
current version of Halite is considered pre-alpha and is supported only in
Salt 0.17 or greater. Additional information is available on GitHub:
https://github.com/saltstack/halite

Before beginning this tutorial, ensure that the salt-master is installed. To
install the salt-master, please review the installation documentation:
http://docs.saltstack.com/topics/installation/index.html

.. note::

    Halite only works with Salt versions greater than 0.17.

Installing Halite Via Package
=============================

On CentOS, RHEL, or Fedora:

.. code-block:: bash

    $ yum install python-halite

.. note::

    By default python-halite only installs CherryPy. If you would like to use
    a different webserver please review the instructions below to install
    pip and your server of choice. The package does not modify the master
    configuration with ``/etc/salt/master``.

Installing Halite Using pip
===========================

To begin the installation of Halite from PyPi, you'll need to install pip. The
Salt package, as well as the bootstrap, do not install pip by default.

On CentOS, RHEL, or Fedora:

.. code-block:: bash

    $ yum install python-pip


On Debian:

.. code-block:: bash

    $ apt-get install python-pip


Once you have pip installed, use it to install halite:

.. code-block:: bash

    $ pip install -U halite


Depending on the webserver you want to run halite through, you'll need to
install that piece as well. On RHEL based distros, use one of the following:

.. code-block:: bash

    $ pip install cherrypy


.. code-block:: bash

    $ pip install paste


.. code-block:: bash

    $ yum install python-devel
    $ yum install gcc
    $ pip install gevent


On Debian based distributions:

.. code-block:: bash

    $ pip install CherryPy


.. code-block:: bash

    $ pip install paste


.. code-block:: bash

    $ apt-get install gcc
    $ apt-get install python-dev
    $ apt-get install libevent-dev
    $ pip install gevent


Configuring Halite Permissions
==============================

Configuring Halite access permissions is easy. By default, you only need to
ensure that the @runner group is configured. In the ``/etc/salt/master file``,
uncomment and modify the following lines:

.. code-block:: yaml

    external_auth:
      pam:
        testuser:
          - .*
          - '@runner'


.. note::

    You cannot use the root user for pam login; it will fail to authenticate.

Halite uses the runner manage.status to get the status of minions, so runner
permissions are required. As you can see in this example, the root user has
been configured. If you aren't running Halite as the root user, you'll need
to modify this value. For example:

.. code-block:: yaml

    external_auth:
      pam:
        mytestuser:
          - .*
          - '@runner'
          - '@wheel'


Currently Halite allows, but does not require, any wheel modules.


Configuring Halite Settings
===========================

Once you've configured the permissions for Halite, you'll need to set up the
Halite settings in the /etc/salt/master file. Halite supports CherryPy, Paste
and Gevent out of the box.

To configure cherrypy, add the following to the bottom of your /etc/salt/master file:

.. code-block:: yaml

    halite:
      level: 'debug'
      server: 'cherrypy'
      host: '0.0.0.0'
      port: '8080'
      cors: False
      tls: True
      certpath: '/etc/pki/tls/certs/localhost.crt'
      keypath: '/etc/pki/tls/certs/localhost.key'
      pempath: '/etc/pki/tls/certs/localhost.pem'


If you wish to use paste:

.. code-block:: yaml

    halite:
      level: 'debug'
      server: 'paste'
      host: '0.0.0.0'
      port: '8080'
      cors: False
      tls: True
      certpath: '/etc/pki/tls/certs/localhost.crt'
      keypath: '/etc/pki/tls/certs/localhost.key'
      pempath: '/etc/pki/tls/certs/localhost.pem'


To use gevent:

.. code-block:: yaml

    halite:
      level: 'debug'
      server: 'gevent'
      host: '0.0.0.0'
      port: '8080'
      cors: False
      tls: True
      certpath: '/etc/pki/tls/certs/localhost.crt'
      keypath: '/etc/pki/tls/certs/localhost.key'
      pempath: '/etc/pki/tls/certs/localhost.pem'


The "cherrypy" and "gevent" servers require the certpath and keypath files
to run tls/ssl. The .crt file holds the public cert and the .key file holds
the private key. Whereas the "paste" server requires a single .pem file that
contains both the cert and key. This can be created simply by concatenating
the .crt and .key files.

If you want to use a self-signed cert, you can create one using the Salt.tls
module:

.. note::

    You might wish to target only a specific minion. The example below
    targets all connected minions.

.. code-block:: bash

    salt '*' tls.create_self_signed_cert test 

You can also use ``salt-call`` to create a self-signed cert.
.. code-block:: bash

    salt-call tls.create_self_signed_cert tls

When using self-signed certs, browsers will need approval before accepting the
cert. If the web application page has been cached with a non-HTTPS version of
the app, then the browser cache will have to be cleared before it will
recognize and prompt to accept the self-signed certificate.


Starting Halite
===============

Once you've configured the halite section of your /etc/salt/master, you can
restart the salt-master service, and your halite instance will be available.
Depending on your configuration, the instance will be available either at
http://localhost:8080/app, http://domain:8080/app, or 
http://123.456.789.012:8080/app .

.. note::

    halite requires an HTML 5 compliant browser.


All logs relating to halite are logged to the default /var/log/salt/master file.


Running Your Halite Instance Through Nginx
==========================================



Running Your Halite Instance Through Apache
===========================================


