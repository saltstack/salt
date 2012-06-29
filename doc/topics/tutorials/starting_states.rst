=========================
How Do I Use Salt States?
=========================

Simplicity, Simplicity, Simplicity

Many of the most powerful and useful engineering solutions are founded on
simple principals, the Salt SLS system strives to do just that. K.I.S.S.

The core of the Salt State system is the SLS, or the SaLt State file. The SLS
is a representation of the state in which a system should be in, and is set up
to contain this data simply. This is often called configuration management.

It is All Just Data
===================

Before delving into the particulars, it will help to understand that the SLS
is just a data structure under the hood. While understanding that the SLS is
just a data structure is not at all critical to understand to make use Salt
States, it should help bolster the understanding of where the real power is.

SLS files are therefore, in reality, just `dictionaries`_, `lists`_,
`strings`_, and `numbers`_. By using this approach Salt can be much more
flexible. As someone writes more state files, it becomes clear exactly what is
being written. The result is a system that is easy to understand, yet grows
with the needs of the admin or developer.

In the section titled "State Data Structures" a reference exists, explaining
in depth how the data is laid out.

.. _`dictionaries`: http://docs.python.org/glossary.html#term-dictionary
.. _`lists`: http://docs.python.org/glossary.html#term-list
.. _`strings`: http://docs.python.org/library/stdtypes.html#typesseq
.. _`numbers`: http://docs.python.org/library/stdtypes.html#numeric-types-int-float-long-complex

Default Data - YAML
===================

By default Salt represents the SLS data in what is one of the simplest
serialization formats available - `YAML`_.

A typical SLS file will often look like this in YAML:

.. code-block:: yaml
   :linenos:

    apache:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: apache

This SLS data will ensure that the package named apache is installed, and
that the apache service is running. The components can be explained in a
simple way.

The first line is the ID for a set of data, and it is called the ID
Declaration. This ID sets the name of the thing that needs to be manipulated.

The second and fourth lines are the start of the State Declarations, so they
are using the pkg and service states respectively. The pkg state manages a
software package to get installed via the system's native package manager,
and the service state manages a system daemon. Below the pkg and service
lines are the function to run. This function defines what state the named
package and service should be in. Here the package is to be installed, and
the service should be running.

Finally, on line 6, is the word ``require``. This is called a Requisite
Statement, and it makes sure that the Apache service is only started after
the successful installation of the apache package.

.. _`YAML`: http://yaml.org/spec/1.1/

Adding Configs and Users
========================

When setting up a service like an Apache web server, many more components may
need to be added. The Apache configuration file will most likely be managed,
and a user and group may need to be set up.

.. code-block:: yaml
   :linenos:

    apache:
      pkg:
        - installed
      service:
        - running
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

Next,the ``require`` statement under service was changed to watch, and is
now watching 3 states instead of just one. The watch statement does the same
thing as require, making sure that the other states run before running the
state with a watch, but it adds an extra component. The ``watch`` statement
will run the state's watcher function if any of the watched states changed
anything. So if the package was updated, the config file changed, or the user
uid modified, then the service state's watcher will be run. The service
state's watcher just restarts the service, so in this case, a change in the
config file will also trigger a restart of the respective service.

Moving Beyond a Single SLS
==========================

When setting up Salt States, more than one SLS will need to be used. The above
examples were just in a single SLS file, but more than one SLS file can be
combined to build out a State Tree. The above example also references a file
with a strange source - ``salt://apache/httpd.conf``. That file will need to
be available as well.

The SLS files are laid out in a directory on the Salt master. Files are laid
out as just files. A SLS is just a file and files to download are just files.

The Apache example would be laid out in the root of the Salt file server like
this: ::

    /apache/init.sls
    /apache/httpd.conf

So the httpd.conf is just a file in the apache directory, and is referenced
directly.

But with more than a single SLS file, more components can be added to the
toolkit, consider this SSH example:

``/ssh/init.sls:``

.. code-block:: yaml
   :linenos:

    openssh-client:
      pkg.installed

    /etc/ssh/ssh_config
      file.managed:
        - user: root
        - group: root
        - mode: 644
        - source: salt://ssh/ssh_config
        - require:
          - pkg: openssh-client

``ssh/server.sls:``

.. code-block:: yaml
   :linenos:

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

Now our State Tree looks like this: ::

    /apache/init.sls
    /apache/httpd.conf
    /ssh/init.sls
    /ssh/server.sls
    /ssh/banner
    /ssh/ssh_config
    /ssh/sshd_config

This example now introduces the ``include`` statement. The include statement
includes another SLS file so that components found in it can be required,
watched or as will soon be demonstrated - extended.

The include statement allows for states to be cross linked. When an SLS
has an include statement it is literally extended to include the contents of
the included SLS files.

Extending Included SLS Data
===========================

Sometimes SLS data needs to be extended. Perhaps the apache service needs to
watch additional resources, or under certain circumstances a different file
needs to be placed.

These examples will add more watchers to apache and change the ssh banner.

``/ssh/custom-server.sls:``

.. code-block:: yaml
   :linenos:

    include:
      - ssh.server

    extend:
      /etc/ssh/banner:
        file:
          - source: salt://ssh/custom-banner

``/python/mod_python.sls:``

.. code-block:: yaml
   :linenos:

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

There is a bit of a trick here, in the extend statement Requisite Statements
are extended, so the ``- pkg: mod_python`` is appended to the watch list. But
all other statements are overwritten.

Understanding the Render System
===============================

Since the SLS data is just plain old data, it does not need to be represented
with YAML. Salt defaults to YAML because it is very straightforward and easy
to learn and use. But the SLS files can be rendered from almost any imaginable
medium, so long as a renderer module is provided.

The default rendering system is the ``yaml_jinja`` renderer. The
``yaml_jinja`` renderer will first pass the template through the `Jinja2`_
templating system, and then through the YAML parser. The benefit here is that
full programming constructs are available when creating SLS files.

Other renderers available are ``yaml_mako`` which uses the `Mako`_ templating
system rather than the jinja templating system, and more notably, the pure
Python or ``py`` renderer. The ``py`` renderer allows for SLS files to be
written in pure Python, allowing for the utmost level of flexibility and
power when preparing SLS data.

.. _`Jinja2`: http://jinja.pocoo.org/
.. _`Mako`: http://www.makotemplates.org/

Getting to Know the Default - yaml_jinja
----------------------------------------

The default renderer - ``yaml_jinja``, allows for the use of the jinja
templating system. A guide to the Jinja templating system can be found here:
http://jinja.pocoo.org/docs

When working with renderers a few very useful bits of data are passed in. In
the case of templating engine based renderers, three critical components are
available, ``salt``, ``grains``, and ``pillar``. The ``salt`` object allows for
any Salt function to be called from within the template, and ``grains`` allows for
the Grains to be accessed from within the template. A few examples:

``/apache/init.sls:``

.. code-block:: yaml
   :linenos:

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

A more aggressive way to use Jinja can be found here, in a module to set up
a MooseFS distributed filesystem chunkserver:

``/moosefs/chunk.sls:``

.. code-block:: yaml
   :linenos:

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

    '/etc/mfshdd.cfg':
      file.managed:
        - source: salt://moosefs/mfshdd.cfg
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - require:
          - pkg: mfs-chunkserver

    '/etc/mfschunkserver.cfg':
      file.managed:
        - source: salt://moosefs/mfschunkserver.cfg
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - require:
          - pkg: mfs-chunkserver

    mfs-chunkserver:
      pkg:
        - installed
    mfschunkserver:
      service:
        - running
        - require:
    {% for mnt in salt['cmd.run']('ls /dev/data/moose*') %}
          - mount: /mnt/moose{{ mnt[-1] }}
          - file: /mnt/moose{{ mnt[-1] }}
    {% endfor %}
          - file: /etc/mfschunkserver.cfg
          - file: /etc/mfshdd.cfg
          - file: /var/lib/mfs

This example shows much more of the available power provided by Jinja.
Multiple for loops are used to dynamically detect available hard drives
and set them up to be mounted, and the ``salt`` object is used multiple
times to call shell commands to gather data.

Introducing the Python Renderer
-------------------------------

Sometimes the chosen default renderer might not have enough logical power to
accomplish the needed task. When this happens, the Python renderer can be
used. Normally a YAML renderer should be used for the majority of SLS files,
but a SLS file set to use another renderer can be easily added to the tree.

This example shows a very basic Python SLS file:

``/python/django.sls:``

.. code-block:: python
   :linenos:

    #!py

    def run():
        '''
        Install the django package
        '''
        return {'include': ['python'],
                'django': {'pkg': ['installed']}}

This is a very simple example, the first line has a SLS shebang line that
tells Salt to not use the default renderer, but to use the ``py`` renderer.
Then the run function is defined, the return value from the run function
must be a Salt friendly data structure, or better known as a Salt
:doc:`HighState data structure</ref/states/highstate>`.

This Python example would look like this if it were written in YAML:

.. code-block:: yaml
   :linenos:

    include:
      - python

    django:
      pkg.installed

This clearly illustrates, that not only is using the YAML renderer a wise
decision as the default, but that unbridled power can be obtained where
needed by using a pure Python SLS.


Running and debugging salt states.
----------------------------------

after writing out your top.sls file, to run it you call
``salt '*' state.highstate``. If you get back just the hostnames with 
a : after, but no return, then chances are there is a problem with the sls
files.  To debug these, to see what's going on, and see the errors, use the
``salt-call`` command like so: ``salt-call state.highstate -l debug``. This
should help you figure out what's going wrong.  You can also start the minions
in the foreground in debug mode, as a possible way to help debug as well.
To start the minion in debug mode call it like this: ``salt-minion -l debug``.


Now onto the :doc:`States tutorial, part 1</topics/tutorials/states_pt1>`.
