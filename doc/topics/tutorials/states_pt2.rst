=======================
States tutorial, part 2
=======================

This tutorial builds on the topic covered in :doc:`part 1 <states_pt1>`. It is
recommended that you begin there.

In the last Salt States tutorial we covered the basics of installing a package.
In this tutorial we will modify our ``webserver.sls`` file to be more
complicated, have requirements, and use even more Salt States.

Call multiple States
====================

You can specify multiple :term:`state declarations <state declaration>` under
an :term:`ID declaration`. For example, a quick modification to our
``webserver.sls`` to also start Apache if it is not running:

.. code-block:: yaml
    :linenos:
    :emphasize-lines: 4,5

    apache:
      pkg:
        - installed
      service:
        - running

Try stopping Apache before running ``state.highstate`` once again and observe
the output.

Expand the SLS module
=====================

As you have seen, SLS modules are appended with the file extension ``.sls`` and
are referenced by name starting at the root of the state tree. An SLS module
can be also defined as a directory. Demonstrate that now by creating a
directory named ``webserver`` and moving and renaming ``webserver.sls`` to
``webserver/init.sls``. Your state directory should now resemble:

::

    |- top.sls
    `- webserver/
       `- init.sls

.. admonition:: Organizing SLS modules

    You can place additional ``.sls`` files in a state file directory. This
    affords much cleaner organization of your state tree on the filesystem. For
    example, if we created a ``webserver/django.sls`` file that module would be
    referenced as ``webserver.django``.

    In addition, States provide powerful includes and extending functionality
    which we will cover in :doc:`Part 3 <states_pt3>`.

Require other states
====================

We now have a working installation of Apache so let's add an HTML file to
customize our website. It isn't exactly useful to have a website without a
webserver so we don't want Salt to install our HTML file until Apache is
installed and running. Include the following at the bottom of your
``webserver/init.sls`` file:

.. code-block:: yaml
    :linenos:
    :emphasize-lines: 7,11

    apache:
      pkg:
        - installed
      service:
        - running

    /var/www/index.html:                        # ID declaration
      file:                                     # state declaration
        - managed                               # function
        - source: salt://webserver/index.html   # function arg
        - require:                              # requisite declaration
          - pkg: apache                         # requisite reference

**line 7** is the :term:`ID declaration`. In this example it is the
location we want to install our custom HTML file. (**Note:** the default
location that Apache serves may differ from the above on your OS or distro.
``/srv/www`` could also be a likely place to look.)

**Line 8** the :term:`state declaration`. This example uses the Salt :mod:`file
state <salt.states.file>`.

**Line 9** is the :term:`function declaration`. The :func:`managed function
<salt.states.file.managed>` will download a file from the master and install it
in the location specified.

**Line 10** is a :term:`function arg declaration` which, in this example, passes
the ``source`` argument to the :func:`managed function
<salt.states.file.managed>`.

**Line 11** is a :term:`requisite declaration`.

**Line 12** is a :term:`requisite reference` which refers to a state and an ID.
In this example, it is referring to the ``ID declaration`` from our example in
:doc:`part 1 <states_pt1>`. This declaration tells Salt not to install the HTML
file until Apache is installed.

Next, create the ``index.html`` file and save it in the ``webserver``
directory:

.. code-block:: html

    <html>
        <head><title>Salt rocks</title></head>
        <body>
            <h1>This file brought to you by Salt</h1>
        </body>
    </html>

Last, call :func:`state.highstate <salt.modules.state.highstate>` again and the
minion will fetch and execute the highstate as well as our HTML file from the
master using Salt's File Server::

    salt '*' state.highstate

Verify that Apache is now serving your custom HTML.

.. admonition:: ``require`` vs. ``watch``

    There are two :term:`requisite declarations <requisite declaration>`,
    “require” and “watch”. Not every state supports “watch”. The :mod:`service
    state <salt.states.service>` does support “watch” and will restart a
    service based on the watch condition.

    For example, if you use Salt to install an Apache virtual host
    configuration file and want to restart Apache whenever that file is changed
    you could modify our Apache example from earlier as follows:

    .. code-block:: yaml
        :emphasize-lines: 1,2,3,4,11,12

        /etc/httpd/extra/httpd-vhosts.conf:
          file:
            - managed
            - source: salt://webserver/httpd-vhosts.conf

        apache:
          pkg:
            - installed
          service:
            - running
            - watch:
              - file: /etc/httpd/extra/httpd-vhosts.conf

    If the pkg and service names differ on your OS or distro of choice you can
    specify each one separately using a :term:`name declaration` which
    explained in :doc:`Part 3 <states_pt3>`.

Next steps
==========

In :doc:`part 3 <states_pt3>` we will discuss how to use includes, extends and
templating to make hugely complicated State Tree configurations dead-simple.
