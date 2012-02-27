===============
Debian & Ubuntu
===============

Ubuntu
------

We are working to get Salt into apt. In the meantime we have a PPA available
for Lucid::

    aptitude -y install python-software-properties
    add-apt-repository ppa:saltstack/salt
    aptitude update
    aptitude install salt-master        # on the master
    aptitude install salt-minion        # on the minion
    aptitude install salt-syndic        # instead of a slaved master

Debian
------

`A deb package is currently in testing`__ for inclusion in apt. Until that is
accepted you can install Salt by downloading the latest ``.deb`` in the
`downloads section on GitHub`__ and installing that manually using ``dpkg -i``.

.. __: http://mentors.debian.net/package/salt
.. __: https://github.com/saltstack/salt/downloads

.. admonition:: Installing ZeroMQ on Squeeze (Debian 6)

    There is a `python-zmq`__ package available in Debian \"wheezy (testing)\".
    If you don't have that repo enabled the best way to install Salt and pyzmq
    is by using ``pip`` (or ``easy_install``)::

        pip install pyzmq salt

.. __: http://packages.debian.org/search?keywords=python-zmq
