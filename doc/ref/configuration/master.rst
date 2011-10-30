===========================
Configuring the Salt Master
===========================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

.. toctree::
    :hidden:

    examples

.. seealso:: 
    :ref:`example master configuration file <configuration-examples-master>` 

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

.. conf_master:: publish_pull_port

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
accept all authentication. This will clean up the pki keys received from the
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

.. code-block:: yaml

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

.. code-block:: yaml

  log_granular_levels: {
    'salt': 'warning',
    'salt.modules': 'debug'
  }
