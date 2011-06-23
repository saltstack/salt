===================
Configuration guide
===================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

.. toctree::
    :hidden:

    examples

.. seealso:: 
    :ref:`example master configuration file <configuration-examples-master>` 
    |
    :ref:`example minion configuration file <configuration-examples-minion>` 

Configuring the Salt Master
===========================

The configuration file for the salt-master is located at
:file:`/etc/salt/master`. The available options are as follows:

Primary Master Configuration
----------------------------

.. conf_master:: interface

``interface``
-------------

Default: ``0.0.0.0`` (all interfaces)

The local interface to bind to.

.. code-block:: yaml

    interface: 192.168.0.1

.. conf_master:: publish_port

``publish_port``
----------------

Default: ``4505``

The network port to set up the publication interface

.. code-block:: yaml

    publish_port: 4505

.. conf_master:: publish_port

``publish_pull_port``
---------------------

Default: ``45055``

The port used to communicate to the local publisher

.. code-block:: yaml

    publish_pull_port: 45055

.. conf_master:: worker_threads

``worker_threads``
------------------

Default: ``5``

The number of threads to start for receiving commands and replies from minions.
If minions are stalling on replies because you have many minions, raise the
worker_threads value.

.. code-block:: yaml

    worker_threads: 5

``worker_start_port``
---------------------

Default: ``5``

The port to begin binding workers on, the workers will be created on
increasingly higher ports


.. code-block:: yaml

    worker_start_port: 45056

.. conf_master:: ret_port

``ret_port``
------------

Default: ``4506``

The port used by the return server, this is the server used by Salt to receive
execution returns and command executions.

.. code-block:: yaml

    ret_port: 4506

.. conf_master:: pki_dir

``pki_dir``
-----------

Default: :file:`/etc/salt/pki`

The directory to store the pki authentication keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki

.. conf_master:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location used to store cache information, particularly the job information
for executed salt commands.

.. code-block:: yaml

    cachedir: /var/cache/salt

.. conf_master:: keep_jobs

``keep_jobs``
-------------

Default: ``24``

Set the number of hours to keep old job information

Master Security Settings
------------------------

.. conf_master:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode is a dangerous security feature. One problem encountered with pki
authentication systems is that keys can become "mixed up" and authentication
begins to fail. Open mode turns off authentication and tells the master to
accept all authentication. This will clean up the pki keys recieved from the
minions. Open mode should not be turned on for general use, open mode should
only be used for a short period of time to clean up pki keys. To turn on open
mode the value passed must be ``True``.

.. code-block:: yaml

    open_mode: False

.. conf_master:: auto_accept

``auto_accept``
---------------

Default: ``False``

Enable auto_accept, this setting will automatically accept all incoming
public keys from the minions

.. code-block:: yaml

    auto_accept: False

Master State System Settings
----------------------------

.. conf_master:: state_top

``state_top``
-------------

Default: ``top.yml``

The state system uses a "top" file to tell the minions what environment to
use and what modules to use. The state_top file is defined relative to the
root of the base environment

.. code-block:: yaml

    state_top: top.yml

.. conf_master:: renderer

``renderer``
------------

Default: ``yaml_jinja``

The renderer to use on the minions to render the state data

.. code-block:: yaml

    renderer: yaml_jinja

Master File Server Settings
---------------------------

.. conf_master:: file_roots

``file_roots``
--------------

Default: ``base: [/srv/salt]``

Salt runs a lightweight file server written in zeromq to deliver files to
minions. This file server is built into the master daemon and does not
require a dedicated port.
The file server works on environments passed to the master, each environment
can have multiple root directories, the subdirectories in the multiple file
roots cannot match, otherwise the downloaded files will not be able to be
reliably ensured. A base environment is required to house the top file
Example:
file_roots:
  base:
    - /srv/salt/
  dev:
    - /srv/salt/dev/services
    - /srv/salt/dev/states
  prod:
    - /srv/salt/prod/services
    - /srv/salt/prod/states

.. code-block:: yaml

    base:
      - /srv/salt

.. conf_master:: hash_type

``hash_type``
-------------

Default: ``md5``

The hash_type is the hash to use when discovering the hash of a file on
the master server, the default is md5, but sha1, sha224, sha256, sha384
and sha512 are also supported.

.. code-block:: yaml

    hash_type: md5

.. conf_master:: file_buffer_size

``file_buffer_size``
--------------------

Default: ``1048576``

The buffer size in the file server in bytes

.. code-block:: yaml

    file_buffer_size: 1048576

Master Logging Settings
-----------------------

.. conf_master:: log_file

``log_file``
------------

Default: :file:`/etc/salt/pki`

The location of the master log file

.. code-block:: yaml

    log_file: /var/log/salt/master

.. conf_master:: log_level

``log_level``
-------------

Default: ``warning``

The level of messages to send to the log file.
One of 'info', 'quiet', 'critical', 'error', 'debug', 'warning'.

.. code-block:: yaml

    log_level: warning

.. conf_master:: log_granular_levels

``log_granular_levels``
-----------------------

Default: ``{}``

Logger levels can be used to tweak specific loggers logging levels.
Imagine you want to have the salt library at the 'warning' level, but, you
still wish to have 'salt.modules' at the 'debug' level:
  log_granular_levels: {
    'salt': 'warning',
    'salt.modules': 'debug'
  }


Configuring the Salt Minion
===========================

The Salt Minion configuration is very simple, typically the only value that
needs to be set is the master value so the minion can find its master.

Minion Primary Configuration
----------------------------

.. conf_minion:: master

``master``
----------

Default: ``salt``

The hostname or ipv4 of the master.

.. code-block:: yaml

    master: salt

.. conf_minion:: master_port

``master_port``
---------------

Default: ``4506``

The port of the master ret server, this needs to coincide with the ret_port
option on the salt master.

.. code-block:: yaml

    master_port: 4506

.. conf_minion:: pki_dir

``pki_dir``
-----------

Default: :file:`/etc/salt/pki`

The directory used to store the minion's public and private keys.

.. code-block:: yaml

    pki_dir: /etc/salt/pki

.. conf_minion:: hostname

``id``
------------

Default: hostname (as returned by the Python call: ``socket.getfqdn()``)

Explicitly declare the id for this minion to use, if left commented the id
will be the hostname as returned by the python call: socket.getfqdn()
Since salt uses detached ids it is possible to run multiple minions on the
same machine but with different ids, this can be useful for salt compute
clusters.

.. code-block:: yaml

    id: foo.bar.com

.. conf_minion:: cachedir

``cachedir``
------------

Default: :file:`/var/cache/salt`

The location for minion cache data.

.. code-block:: yaml

    cachedir: /var/cache/salt

Minion Module Management
------------------------

.. conf_minion:: disable_modules

``disable_modules``
-------------------

Default: ``[]`` (all modules are enabled by default)

The event may occur in which the administrator desires that a minion should not
be able to execute a certain module. The sys module is built into the minion
and cannot be disabled.

.. code-block:: yaml

    disable_modules: [cmd,virt,test]

.. conf_minion:: open_mode

``open_mode``
-------------

Default: ``False``

Open mode can be used to clean out the pki key recieved from the salt master,
turn on open mode, restart the minion, then turn off open mode and restart the
minion to clean the keys.

.. code-block:: yaml

    open_mode: False
