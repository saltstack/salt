Salt Proxy Minion Documentation
===============================

.. toctree::
    :maxdepth: 3
    :glob:
    :hidden:

    *
    install/index

Proxy minions are a Salt feature that enables controlling devices that, for
whatever reason, cannot run a standard salt-minion.  Examples include network
gear that has an API but runs a proprietary OS, devices with limited CPU or
memory, or devices that could run a minion, but for security reasons, will not.

Proxy minions are not, for the most part, an "out of the box" feature.  Because
there are a myriad of devices outside the typical Linux or Windows worlds, if
you are trying to control something you will most likely have to write the
interface yourself. Fortunately, this is only as difficult as the actual
interface to the proxied device.  Devices that have an existing Python module
(PyUSB for example) would be relatively simple to interface.  Code to control
a device that has an HTML REST-based interface should be easy.  Code to control
your typical housecat would be excellent source material for a PhD thesis.

Salt-proxy-minions provide the 'plumbing' that allows device enumeration,
control, status, remote execution, and state management.

Getting Started
===============

Minion management
-----------------

Minion Discovery
----------------

Essential Components of a Proxy Minion Interface
------------------------------------------------

* Configuration file parameters

* The __proxyenabled__ directive

* test.ping



