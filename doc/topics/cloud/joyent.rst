===========================
Getting Started With Joyent
===========================

Joyent is a public cloud host that supports SmartOS, Linux, FreeBSD, and
Windows.


Dependencies
============
This driver requires the Python ``requests`` library to be installed.


Configuration
=============
The Joyent cloud requires three configuration parameters. The user name and
password that are used to log into the Joyent system, and the location of the
private ssh key associated with the Joyent account. The ssh key is needed to
send the provisioning commands up to the freshly created virtual machine.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-joyent-config:
      driver: joyent
      user: fred
      password: saltybacon
      private_key: /root/mykey.pem
      keyname: mykey

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles`` or in the
``/etc/salt/cloud.profiles.d/`` directory:

.. code-block:: yaml

    joyent_512
      provider: my-joyent-config
      size: Extra Small 512 MB
      image: Arch Linux 2013.06

Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes my-joyent-config
    my-joyent-config:
        ----------
        joyent:
            ----------
            Extra Small 512 MB:
                ----------
                default:
                    false
                disk:
                    15360
                id:
                    Extra Small 512 MB
                memory:
                    512
                name:
                    Extra Small 512 MB
                swap:
                    1024
                vcpus:
                    1
    ...SNIP...

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images my-joyent-config
    my-joyent-config:
        ----------
        joyent:
            ----------
            base:
                ----------
                description:
                    A 32-bit SmartOS image with just essential packages
                    installed. Ideal for users who are comfortable with setting
                    up their own environment and tools.
                disabled:
                    False
                files:
                    ----------
                    - compression:
                        bzip2
                    - sha1:
                        40cdc6457c237cf6306103c74b5f45f5bf2d9bbe
                    - size:
                        82492182
                name:
                    base
                os:
                    smartos
                owner:
                    352971aa-31ba-496c-9ade-a379feaecd52
                public:
                    True
    ...SNIP...


SmartDataCenter
===============

This driver can also be used with the Joyent SmartDataCenter project. More
details can be found at:

.. _`SmartDataCenter`: https://github.com/joyent/sdc

Using SDC requires that an api_host_suffix is set. The default value for this is
`.api.joyentcloud.com`. All characters, including the leading `.`, should be
included:

.. code-block:: yaml

      api_host_suffix: .api.myhostname.com


Miscellaneous Configuration
===========================
The following configuration items can be set in either ``provider`` or
``profile`` confuration files.

use_ssl
~~~~~~~
When set to ``True`` (the default), attach ``https://`` to any URL that does not
already have ``http://`` or ``https://`` included at the beginning. The best
practice is to leave the protocol out of the URL, and use this setting to manage
it.

verify_ssl
~~~~~~~~~~
When set to ``True`` (the default), the underlying web library will verify the
SSL certificate. This should only be set to ``False`` for debugging.`
