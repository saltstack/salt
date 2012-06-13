===========================
Configuring the Salt Master
===========================

The Salt system is amazingly simple and easy to configure, the two components
of the Salt system each have a respective configuration file. The
:command:`salt-master` is configured via the master configuration file, and the
:command:`salt-minion` is configured via the minion configuration file.

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

.. conf_master:: user

``user``
--------

Default: ``root``

The user to run the Salt processes

.. code-block:: yaml

    user: root

.. conf_master:: worker_threads

``worker_threads``
------------------

Default: ``5``

The number of threads to start for receiving commands and replies from minions.
If minions are stalling on replies because you have many minions, raise the
worker_threads value.

.. code-block:: yaml

    worker_threads: 5

.. conf_master:: ret_port

``ret_port``
------------

Default: ``4506``

The port used by the return server, this is the server used by Salt to receive
execution returns and command executions.

.. code-block:: yaml

    ret_port: 4506

.. conf_master:: root_dir

``root_dir``
------------

Default: :file:`/`

The system root directory to operate from, change this to make Salt run from
an alternative root

.. code-block:: yaml

    root_dir: /

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

.. conf_master:: job_cache

``job_cache``
-------------

Default: ``True``

The master maintains a job cache, while this is a great addition it can be
a burden on the master for larger deployments (over 5000 minions).
Disabling the job cache will make previously executed jobs unavailable to
the jobs system and is not generally recommended. Normally it is wise to make
sure the master has access to a faster IO system or a tmpfs is mounted to the
jobs dir

.. conf_master:: sock_dir

``sock_dir``
------------

Default:: :file:`/tmp/salt-unix`

Set the location to use for creating Unix sockets for master process
communication

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
minions. Open mode should not be turned on for general use. Open mode should
only be used for a short period of time to clean up pki keys. To turn on open
mode set this value to ``True``.

.. code-block:: yaml

    open_mode: False

.. conf_master:: auto_accept

``auto_accept``
---------------

Default: ``False``

Enable auto_accept. This setting will automatically accept all incoming
public keys from the minions

.. code-block:: yaml

    auto_accept: False


Master Module Management
------------------------

.. conf_master:: runner_dirs

``runner_dirs``
---------------

Default: ``[]``

Set additional directories to search for runner modules

.. conf_master:: cython_enable

``cython_enable``
-----------------

Default: ``False``

Set to true to enable cython modules (.pyx files) to be compiled on the fly on
the Salt master

.. code-block:: yaml

    cython_enable: False

Master State System Settings
----------------------------

.. conf_master:: state_top

``state_top``
-------------

Default: ``top.sls``

The state system uses a "top" file to tell the minions what environment to
use and what modules to use. The state_top file is defined relative to the
root of the base environment

.. code-block:: yaml

    state_top: top.sls

.. conf_master:: external_nodes

``external_nodes``
------------------

Default: None

The external_nodes option allows Salt to gather data that would normally be
placed in a top file from and external node controller. The external_nodes
option is the executable that will return the ENC data. Remember that Salt
will look for external nodes AND top files and combine the results if both
are enabled and available!

.. code-block:: yaml

    external_nodes: cobbler-ext-nodes

.. conf_master:: renderer

``renderer``
------------

Default: ``yaml_jinja``

The renderer to use on the minions to render the state data

.. code-block:: yaml

    renderer: yaml_jinja

.. conf_master:: failhard

``failhard``
------------

Default:: ``False``

Set the global failhard flag, this informs all states to stop running states
at the moment a single state fails

.. code-block:: yaml

    failhard: False

.. conf_master:: test

``test``
--------

Default:: ``False``

Set all state calls to only test if they are going to acctually make changes
or just post what changes are going to be made

.. code-block:: yaml

    test: False

Master File Server Settings
---------------------------

.. conf_master:: file_roots

``file_roots``
--------------

Default: ``base: [/srv/salt]``

Salt runs a lightweight file server written in zeromq to deliver files to
minions. This file server is built into the master daemon and does not
require a dedicated port.

The file server works on environments passed to the master. Each environment
can have multiple root directories. The subdirectories in the multiple file
roots cannot match, otherwise the downloaded files will not be able to be
reliably ensured. A base environment is required to house the top file.
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

Pillar Configuration
--------------------

.. conf_master:: pillar_roots

``pillar_roots``
----------------

Set the environments and directorirs used to hold pillar sls data. This
configuration is the same as file_roots:

Default: ``base: [/srv/pillar]``

.. code-block:: yaml

    file_roots:
      base:
        - /srv/pillar/
      dev:
        - /srv/pillar/dev/
      prod:
        - /srv/pillar/prod/

.. code-block:: yaml

    base:
      - /srv/pillar

.. conf_master:: ext_pillar

``ext_pillar``
--------------

The ext_pillar option allows for any number of external pillar interfaces to be
called when populating pillar data. The configuration is based on ext_pillar
functions. The available ext_pillar functions are: hiera, cmd_yaml. By default
the ext_pillar interface is not configued to run.

Default:: ``None``

.. code-block:: yaml

    ext_pillar:
      - hiera: /etc/hiera.yaml
      - cmd: cat /etc/salt/yaml


Syndic Server Settings
----------------------

A Salt syndic is a Salt master used to pass commands from a higher Salt master to
minions below the syndic. Using the syndic is simple. If this is a master that
will have syndic servers(s) below it, set the "order_masters" setting to True. If this
is a master that will be running a syndic daemon for passthrough the
"syndic_master" setting needs to be set to the location of the master server

.. conf_master:: order_masters

``order_masters``
-----------------

Default: ``False``

Extra data needs to be sent with publications if the master is controlling a
lower level master via a syndic minion. If this is the case the order_masters
value must be set to True

.. code-block:: yaml

    order_masters: False

.. conf_master:: syndic_master

``syndic_master``
-----------------

Default: ``None``

If this master will be running a salt-syndic to connect to a higher level
master, specify the higher level master with this configuration value

.. code-block:: yaml

    syndic_master: masterofmasters

Peer Publish Settings
---------------------

Salt minions can send commands to other minions, but only if the minion is
allowed to. By default "Peer Publication" is disabled, and when enabled it
is enabled for specific minions and specific commands. This allows secure
compartmentalization of commands based on individual minions.

.. conf_master:: peer

``peer``
--------

Default: ``{}``

The configuration uses regular expressions to match minions and then a list
of regular expressions to match functions. The following will allow the
minion authenticated as foo.example.com to execute functions from the test
and pkg modules

.. code-block:: yaml

    peer:
      foo.example.com:
          - test.*
          - pkg.*

This will allow all minions to execute all commands:

.. code-block:: yaml

    peer:
      .*:
          - .*

This is not recommended, since it would allow anyone who gets root on any
single minion to instantly have root on all of the minions!

.. conf_master:: peer_run

``peer_run``
------------

Default: ``{}``

The peer_run option is used to open up runners on the master to access from the
minions. The peer_run configuration matches the format of the peer
configuration.

The following example would allow foo.example.com to execute the manage.up
runner:


.. code-block:: yaml

    peer_run:
      foo.example.com:
          - manage.up

Node Groups
-----------

.. conf_master:: nodegroups

Default: ``{}``

Node groups allow for logical groupings of minion nodes.
A group consists of a group name and a compound target.

.. code-block:: yaml

    nodegroups:
      group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com and bl*.domain.com'
      group2: 'G@os:Debian and foo.domain.com'

Master Logging Settings
-----------------------

.. conf_master:: log_file

``log_file``
------------

Default: :file:`/var/log/salt/master`

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
Imagine you want to have the Salt library at the 'warning' level, but you
still wish to have 'salt.modules' at the 'debug' level:

.. code-block:: yaml

  log_granular_levels:
    'salt': 'warning',
    'salt.modules': 'debug'
