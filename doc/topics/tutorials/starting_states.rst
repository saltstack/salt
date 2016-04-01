=========================
How Do I Use Salt States?
=========================

Simplicity, Simplicity, Simplicity

Many of the most powerful and useful engineering solutions are founded on
simple principles. Salt States strive to do just that: K.I.S.S. (Keep It
Stupidly Simple)

The core of the Salt State system is the SLS, or **S**\ a\ **L**\ t
**S**\ tate file. The SLS is a representation of the state in which
a system should be in, and is set up to contain this data in a simple format.
This is often called configuration management.

.. note::

    This is just the beginning of using states, make sure to read up on pillar
    :doc:`Pillar </topics/tutorials/pillar>` next.


It is All Just Data
===================

Before delving into the particulars, it will help to understand that the SLS
file is just a data structure under the hood. While understanding that the SLS
is just a data structure isn't critical for understanding and making use of
Salt States, it should help bolster knowledge of where the real power is.

SLS files are therefore, in reality, just :ref:`dictionaries
<python2:typesmapping>`, :ref:`lists <python2:typesseq>`, :ref:`strings
<python2:typesseq>`, and :ref:`numbers <python2:typesnumeric>`.
By using this approach Salt can be much more flexible. As one writes more state
files, it becomes clearer exactly what is being written. The result is a system
that is easy to understand, yet grows with the needs of the admin or developer.


The Top File
============

The example SLS files in the below sections can be assigned to hosts using a
file called :strong:`top.sls`. This file is described in-depth :doc:`here
</ref/states/top>`.


Default Data - YAML
===================

By default Salt represents the SLS data in what is one of the simplest
serialization formats available - `YAML`_.

A typical SLS file will often look like this in YAML:

.. note::

    These demos use some generic service and package names, different
    distributions often use different names for packages and services. For
    instance `apache` should be replaced with `httpd` on a Red Hat system.
    Salt uses the name of the init script, systemd name, upstart name etc.
    based on what the underlying service management for the platform. To
    get a list of the available service names on a platform execute the
    service.get_all salt function.

    Information on how to make states work with multiple distributions
    is later in the tutorial.

.. code-block:: yaml

    apache:
      pkg.installed: []
      service.running:
        - require:
          - pkg: apache

This SLS data will ensure that the package named apache is installed, and
that the apache service is running. The components can be explained in a
simple way.

The first line is the ID for a set of data, and it is called the ID
Declaration. This ID sets the name of the thing that needs to be manipulated.

The second and third lines contain the state module function to be run, in the
format ``<state_module>.<function>``. The ``pkg.installed`` state module
function ensures that a software package is installed via the system's native
package manager. The ``service.running`` state module function ensures that a
given system daemon is running.

Finally, on line five, is the word ``require``. This is called a Requisite
Statement, and it makes sure that the Apache service is only started after
a successful installation of the apache package.

.. _`YAML`: http://yaml.org/spec/1.1/


Adding Configs and Users
========================

When setting up a service like an Apache web server, many more components may
need to be added. The Apache configuration file will most likely be managed,
and a user and group may need to be set up.

.. code-block:: yaml

    apache:
      pkg.installed: []
      service.running:
        - watch:
          - pkg: apache
          - file: /etc/httpd/conf/httpd.conf
          - user: apache
      user.present:
        - uid: 87
        - gid: 87
        - home: /var/www/html
        - shell: /bin/nologin
        - require:
          - group: apache
      group.present:
        - gid: 87
        - require:
          - pkg: apache

    /etc/httpd/conf/httpd.conf:
      file.managed:
        - source: salt://apache/httpd.conf
        - user: root
        - group: root
        - mode: 644

This SLS data greatly extends the first example, and includes a config file,
a user, a group and new requisite statement: ``watch``.

Adding more states is easy, since the new user and group states are under
the Apache ID, the user and group will be the Apache user and group. The
``require`` statements will make sure that the user will only be made after
the group, and that the group will be made only after the Apache package is
installed.

Next, the ``require`` statement under service was changed to watch, and is
now watching 3 states instead of just one. The watch statement does the same
thing as require, making sure that the other states run before running the
state with a watch, but it adds an extra component. The ``watch`` statement
will run the state's watcher function for any changes to the watched states.
So if the package was updated, the config file changed, or the user
uid modified, then the service state's watcher will be run. The service
state's watcher just restarts the service, so in this case, a change in the
config file will also trigger a restart of the respective service.


Moving Beyond a Single SLS
==========================

When setting up Salt States in a scalable manner, more than one SLS will need
to be used. The above examples were in a single SLS file, but two or more
SLS files can be combined to build out a State Tree. The above example also
references a file with a strange source - ``salt://apache/httpd.conf``. That
file will need to be available as well.

The SLS files are laid out in a directory structure on the Salt master; an
SLS is just a file and files to download are just files.

The Apache example would be laid out in the root of the Salt file server like
this:

.. code-block:: text

    apache/init.sls
    apache/httpd.conf

So the httpd.conf is just a file in the apache directory, and is referenced
directly.

.. include:: ../../_incl/_incl/sls_filename_cant_contain_period.rst

But when using more than one single SLS file, more components can be added to
the toolkit. Consider this SSH example:

``ssh/init.sls:``

.. code-block:: yaml

    openssh-client:
      pkg.installed

    /etc/ssh/ssh_config:
      file.managed:
        - user: root
        - group: root
        - mode: 644
        - source: salt://ssh/ssh_config
        - require:
          - pkg: openssh-client

``ssh/server.sls:``

.. code-block:: yaml

    include:
      - ssh

    openssh-server:
      pkg.installed

    sshd:
      service.running:
        - require:
          - pkg: openssh-client
          - pkg: openssh-server
          - file: /etc/ssh/banner
          - file: /etc/ssh/sshd_config

    /etc/ssh/sshd_config:
      file.managed:
        - user: root
        - group: root
        - mode: 644
        - source: salt://ssh/sshd_config
        - require:
          - pkg: openssh-server

    /etc/ssh/banner:
      file:
        - managed
        - user: root
        - group: root
        - mode: 644
        - source: salt://ssh/banner
        - require:
          - pkg: openssh-server

.. note::

    Notice that we use two similar ways of denoting that a file
    is managed by Salt. In the `/etc/ssh/sshd_config` state section above,
    we use the `file.managed` state declaration whereas with the
    `/etc/ssh/banner` state section, we use the `file` state declaration
    and add a `managed` attribute to that state declaration. Both ways
    produce an identical result; the first way -- using `file.managed` --
    is merely a shortcut.

Now our State Tree looks like this:

.. code-block:: text

    apache/init.sls
    apache/httpd.conf
    ssh/init.sls
    ssh/server.sls
    ssh/banner
    ssh/ssh_config
    ssh/sshd_config

This example now introduces the ``include`` statement. The include statement
includes another SLS file so that components found in it can be required,
watched or as will soon be demonstrated - extended.

The include statement allows for states to be cross linked. When an SLS
has an include statement it is literally extended to include the contents of
the included SLS files.

Note that some of the SLS files are called init.sls, while others are not. More
info on what this means can be found in the :ref:`States Tutorial
<sls-file-namespace>`.


Extending Included SLS Data
===========================

Sometimes SLS data needs to be extended. Perhaps the apache service needs to
watch additional resources, or under certain circumstances a different file
needs to be placed.

In these examples, the first will add a custom banner to ssh and the second will
add more watchers to apache to include mod_python.

``ssh/custom-server.sls:``

.. code-block:: yaml

    include:
      - ssh.server

    extend:
      /etc/ssh/banner:
        file:
          - source: salt://ssh/custom-banner

``python/mod_python.sls:``

.. code-block:: yaml

    include:
      - apache

    extend:
      apache:
        service:
          - watch:
            - pkg: mod_python

    mod_python:
      pkg.installed

The ``custom-server.sls`` file uses the extend statement to overwrite where the
banner is being downloaded from, and therefore changing what file is being used
to configure the banner.

In the new mod_python SLS the mod_python package is added, but more importantly
the apache service was extended to also watch the mod_python package.

.. include:: ../../_incl/extend_with_require_watch.rst


Understanding the Render System
===============================

Since SLS data is simply that (data), it does not need to be represented
with YAML. Salt defaults to YAML because it is very straightforward and easy
to learn and use. But the SLS files can be rendered from almost any imaginable
medium, so long as a renderer module is provided.

The default rendering system is the ``yaml_jinja`` renderer. The
``yaml_jinja`` renderer will first pass the template through the `Jinja2`_
templating system, and then through the YAML parser. The benefit here is that
full programming constructs are available when creating SLS files.

Other renderers available are ``yaml_mako`` and ``yaml_wempy`` which each use
the `Mako`_ or `Wempy`_ templating system respectively rather than the jinja
templating system, and more notably, the pure Python or ``py``, ``pydsl`` &
``pyobjects`` renderers.
The ``py`` renderer allows for SLS files to be written in pure Python,
allowing for the utmost level of flexibility and power when preparing SLS
data; while the :doc:`pydsl</ref/renderers/all/salt.renderers.pydsl>` renderer
provides a flexible, domain-specific language for authoring SLS data in Python;
and the :doc:`pyobjects</ref/renderers/all/salt.renderers.pyobjects>` renderer
gives you a `"Pythonic"`_ interface to building state data.

.. _`Jinja2`: http://jinja.pocoo.org/
.. _`Mako`: http://www.makotemplates.org/
.. _`Wempy`: https://fossil.secution.com/u/gcw/wempy/doc/tip/README.wiki
.. _`"Pythonic"`: http://legacy.python.org/dev/peps/pep-0008/

.. note::

    The templating engines described above aren't just available in SLS files.
    They can also be used in :mod:`file.managed <salt.states.file.managed>`
    states, making file management much more dynamic and flexible. Some
    examples for using templates in managed files can be found in the
    documentation for the :doc:`file states
    </ref/states/all/salt.states.file>`, as well as the :ref:`MooseFS
    example<jinja-example-moosefs>` below.


Getting to Know the Default - yaml_jinja
----------------------------------------

The default renderer - ``yaml_jinja``, allows for use of the jinja
templating system. A guide to the Jinja templating system can be found here:
http://jinja.pocoo.org/docs

When working with renderers a few very useful bits of data are passed in. In
the case of templating engine based renderers, three critical components are
available, ``salt``, ``grains``, and ``pillar``. The ``salt`` object allows for
any Salt function to be called from within the template, and ``grains`` allows
for the Grains to be accessed from within the template. A few examples:

``apache/init.sls:``

.. code-block:: yaml

    apache:
      pkg.installed:
        {% if grains['os'] == 'RedHat'%}
        - name: httpd
        {% endif %}
      service.running:
        {% if grains['os'] == 'RedHat'%}
        - name: httpd
        {% endif %}
        - watch:
          - pkg: apache
          - file: /etc/httpd/conf/httpd.conf
          - user: apache
      user.present:
        - uid: 87
        - gid: 87
        - home: /var/www/html
        - shell: /bin/nologin
        - require:
          - group: apache
      group.present:
        - gid: 87
        - require:
          - pkg: apache

    /etc/httpd/conf/httpd.conf:
      file.managed:
        - source: salt://apache/httpd.conf
        - user: root
        - group: root
        - mode: 644

This example is simple. If the ``os`` grain states that the operating system is
Red Hat, then the name of the Apache package and service needs to be httpd.

.. _jinja-example-moosefs:

A more aggressive way to use Jinja can be found here, in a module to set up
a MooseFS distributed filesystem chunkserver:

``moosefs/chunk.sls:``

.. code-block:: yaml

    include:
      - moosefs

    {% for mnt in salt['cmd.run']('ls /dev/data/moose*').split() %}
    /mnt/moose{{ mnt[-1] }}:
      mount.mounted:
        - device: {{ mnt }}
        - fstype: xfs
        - mkmnt: True
      file.directory:
        - user: mfs
        - group: mfs
        - require:
          - user: mfs
          - group: mfs
    {% endfor %}

    /etc/mfshdd.cfg:
      file.managed:
        - source: salt://moosefs/mfshdd.cfg
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - require:
          - pkg: mfs-chunkserver

    /etc/mfschunkserver.cfg:
      file.managed:
        - source: salt://moosefs/mfschunkserver.cfg
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - require:
          - pkg: mfs-chunkserver

    mfs-chunkserver:
      pkg.installed: []
    mfschunkserver:
      service.running:
        - require:
    {% for mnt in salt['cmd.run']('ls /dev/data/moose*') %}
          - mount: /mnt/moose{{ mnt[-1] }}
          - file: /mnt/moose{{ mnt[-1] }}
    {% endfor %}
          - file: /etc/mfschunkserver.cfg
          - file: /etc/mfshdd.cfg
          - file: /var/lib/mfs

This example shows much more of the available power of Jinja.
Multiple for loops are used to dynamically detect available hard drives
and set them up to be mounted, and the ``salt`` object is used multiple
times to call shell commands to gather data.


Introducing the Python, PyDSL, and the Pyobjects Renderers
----------------------------------------------------------

Sometimes the chosen default renderer might not have enough logical power to
accomplish the needed task. When this happens, the Python renderer can be
used. Normally a YAML renderer should be used for the majority of SLS files,
but an SLS file set to use another renderer can be easily added to the tree.

This example shows a very basic Python SLS file:

``python/django.sls:``

.. code-block:: python

    #!py

    def run():
        '''
        Install the django package
        '''
        return {'include': ['python'],
                'django': {'pkg': ['installed']}}

This is a very simple example; the first line has an SLS shebang that
tells Salt to not use the default renderer, but to use the ``py`` renderer.
Then the run function is defined, the return value from the run function
must be a Salt friendly data structure, or better known as a Salt
:doc:`HighState data structure</ref/states/highstate>`.

Alternatively, using the :doc:`pydsl</ref/renderers/all/salt.renderers.pydsl>`
renderer, the above example can be written more succinctly as:

.. code-block:: python

    #!pydsl

    include('python', delayed=True)
    state('django').pkg.installed()

The :doc:`pyobjects</ref/renderers/all/salt.renderers.pyobjects>` renderer
provides an `"Pythonic"`_ object based approach for building the state data.
The above example could be written as:

.. code-block:: python

    #!pyobjects

    include('python')
    Pkg.installed("django")


These Python examples would look like this if they were written in YAML:

.. code-block:: yaml

    include:
      - python

    django:
      pkg.installed

This example clearly illustrates that; one, using the YAML renderer by default
is a wise decision and two, unbridled power can be obtained where needed by
using a pure Python SLS.

Running and debugging salt states.
----------------------------------

Once the rules in an SLS are ready, they should be tested to ensure they
work properly. To invoke these rules, simply execute
``salt '*' state.apply`` on the command line. If you get back only
hostnames with a ``:`` after, but no return, chances are there is a problem with
one or more of the sls files. On the minion, use the ``salt-call`` command to
examine the output for errors:

.. code-block:: bash

    salt-call state.apply -l debug

This should help troubleshoot the issue. The minion can also be started in the
foreground in debug mode by running ``salt-minion -l debug``.

Next Reading
============

With an understanding of states, the next recommendation is to become familiar
with Salt's pillar interface:

    :doc:`Pillar Walkthrough </topics/tutorials/pillar>`
