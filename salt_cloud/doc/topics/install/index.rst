Install Salt Cloud
==================

Salt Cloud has only two dependencies:

 * ``salt``
 * ``apache-libcloud``

 Of course, ``salt`` has it's own set of dependencies and the same applies to 
 ``apache-libcloud``.


Installing Salt Cloud for development
-------------------------------------

Clone the repository using:

.. code-block:: bash

    git clone https://github.com/saltstack/salt-cloud.git


Create a new `virtualenv`_:

.. code-block:: bash

    virtualenv /path/to/your/virtualenv

.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv


On Arch Linux, where Python 3 is the default installation of Python, use the
``virtualenv2`` command instead of ``virtualenv``.

.. note:: Using system Python modules in the virtualenv

    To use already-installed python modules in virtualenv (instead of having pip
    download and compile new ones), run ``virtualenv --system-site-packages``
    Using this method eliminates the requirement to install the salt 
    dependencies again, although it does assume that the listed modules are all 
    installed in the system ``PYTHONPATH`` at the time of virtualenv creation.


Activate the virtualenv:

.. code-block:: bash

    source /path/to/your/virtualenv/bin/activate


.. _dependencies:

Install Salt Cloud (and dependencies) into the virtualenv:

.. code-block:: bash

    pip install M2Crypto    # Don't install on Debian/Ubuntu (see below)
    pip install pyzmq PyYAML pycrypto msgpack-python jinja2 psutil salt
    pip install apache-libcloud
    pip install -e ./salt-cloud   # the path to the salt-cloud git clone


.. note:: Installing M2Crypto

    ``swig`` and ``libssl-dev`` are required to build M2Crypto. To fix the 
    error ``command 'swig' failed with exit status 1`` while installing 
    M2Crypto, try installing it with the following command:

    .. code-block:: bash

        env SWIG_FEATURES="-cpperraswarn -includeall -D__`uname -m`__ -I/usr/include/openssl" pip install M2Crypto

    Debian and Ubuntu systems have modified openssl libraries and mandate that
    a patched version of M2Crypto be installed. This means that M2Crypto
    needs to be installed via apt:

    .. code-block:: bash

        apt-get install python-m2crypto

    This also means that pulling in the M2Crypto installed using apt requires 
    using ``--system-site-packages`` when creating the virtualenv.

    Or using a pre-patched M2Crypto

    .. code-block:: bash

         pip install http://dl.dropbox.com/u/174789/m2crypto-0.20.1.tar.gz


Using easy_install to Install Salt Cloud
----------------------------------------

If you are installing using ``easy_install``, you will need to define a
:strong:`USE_SETUPTOOLS` environment variable, otherwise dependencies will not
be installed:

.. code-block:: bash

    USE_SETUPTOOLS=1 easy_install salt-cloud


Installing Salt Cloud from Git
------------------------------

To install salt cloud from ``git`` without any development purposes in mind,
install the required dependencies_ replacing the last step with:

.. code-block:: bash

    pip install git+https://github.com/saltstack/salt-cloud.git#egg=salt_cloud
