.. _netapi-enable-clients:

=================================
Enabling netapi client interfaces
=================================

From Salt's 3006.0 release onwards, all netapi client interfaces are disabled by default.

To enable netapi/:command:`salt-api` functionality, users should follow the process in this
documentation. If the :conf_master:`netapi_enable_clients` configuration is not added to the
Salt master configuration, then the netapi/:command:`salt-api` will not function.

.. admonition:: Breaking change in Salt 3006.0 and above

    Users of netapi/:command:`salt-api` upgrading to Salt 3006.0 **must** follow the process in
    this documentation to enable the required netapi client interfaces. If the
    :conf_master:`netapi_enable_clients` configuration is not added to the Salt master
    configuration netapi/:command:`salt-api` will not function


Steps to enable netapi client interfaces
========================================

1. :ref:`netapi-enable-clients-select`
2. :ref:`netapi-enable-clients-update`
3. :ref:`netapi-enable-clients-restart`
4. :ref:`netapi-enable-clients-verify`


.. _netapi-enable-clients-select:

Select client interfaces to enable
----------------------------------

Salt's client interfaces provide the ability to execute functions from execution, runner,
wheel modules, and via the salt-ssh system.

It is recommended to only enable the client interfaces required to complete the tasks needed
to reduce the amount of Salt functionality exposed via the netapi. For example, if the
salt-ssh system is not in use, not enabling the ssh client interface will help protect
the Salt master from attacks which look to exploit salt-ssh.

The main client interfaces are:

* local - run execution modules on minions
* local_subset - run execution modules on a subset of minions
* runner - run runner modules on master
* ssh - run salt-ssh commands
* wheel - run wheel modules

The local, runner, and wheel clients also have async variants to run modules asynchronously.
See :conf_master:`netapi_enable_clients` for the complete list.

Most scenarios will require enabling the local client (and potentially its local_subset and
local_async variants). The local client is equivalent to the :command:`salt` command line
tool and is required to run execution modules against minions.

Many deployments may also require the ability to call runner functions on the master (for
example, where orchestrations are used), but the runner client should only be enabled if
this is the case.

As there is not a standard netapi client application, existing users will need to assess
which client interfaces are in use. Where an application or tool is making a request to
a netapi module, it will usually pass an option indicating which client to use and it
should be possible to inspect the source of any tools to understand which client interfaces
should be enabled.

For common command line clients, such as `pepper <https://github.com/saltstack/pepper>`_
they will normally default to using the local client interface unless passed an
option to specify a different client interface.


.. _netapi-enable-clients-update:

Update Salt master config
-------------------------

Once it has been established which client interfaces will be required or are currently
in use, those should be listed in the Salt master config, under the
:conf_master:`netapi_enable_clients` key.

Example configuration to enable only the local client interfaces:

    netapi_enable_clients:
      - local
      - local_async
      - local_batch
      - local_subset


Example configuration to enable local client functionality and runners:

    netapi_enable_clients:
      - local
      - local_async
      - local_batch
      - local_subset
      - runner
      - runner_async

See :conf_master:`netapi_enable_clients` for the full list of available client interfaces.


.. _netapi-enable-clients-restart:


Restart salt-master and salt-api
--------------------------------

Changes to the Salt master configuration require a restart of the :command:`salt-master`
service. The :command:`salt-api` service should also be restarted.


.. _netapi-enable-clients-verify:

Verify required functionality
-----------------------------

Testing that the required functionality is available can be done using curl.
It is recommended to also check that client interfaces that are not
required are not enabled.

.. admonition:: Examples

    Examples will have to be adjusted to set the correct username, password and
    :ref:`external authentication <acl-eauth>` values for the user's system.


Checking that the local client is enabled:

.. code-block:: bash

    curl -sSKi https://localhost:8000/run \
        -H 'Accept: application/x-yaml' \
        -d client='local' \
        -d tgt='*' \
        -d fun='test.ping' \
        -d username='saltdev' \
        -d password='saltdev' \
        -d eauth='auto'

    HTTP/1.1 200 OK
    Content-Type: application/x-yaml
    Server: CherryPy/18.8.0
    Date: Mon, 23 Jan 2023 14:54:58 GMT
    Allow: GET, HEAD, POST
    Access-Control-Allow-Origin: *
    Access-Control-Expose-Headers: GET, POST
    Access-Control-Allow-Credentials: true
    Vary: Accept-Encoding
    Content-Length: 25

    return:
      - saltdev1: true


Checking that the runner client is **not** enabled:

.. code-block:: bash

    curl -sSKi https://localhost:8000/run \
        -H 'Accept: application/x-yaml' \
        -d client='runner' \
        -d fun='test.arg' \
        -d arg='test arg' \
        -d username='saltdev' \
        -d password='saltdev' \
        -d eauth='auto'

    HTTP/1.1 400 Bad Request
    Content-Type: text/html;charset=utf-8
    Server: CherryPy/18.8.0
    Date: Mon, 23 Jan 2023 14:59:33 GMT
    Allow: GET, HEAD, POST
    Access-Control-Allow-Origin: *
    Access-Control-Expose-Headers: GET, POST
    Access-Control-Allow-Credentials: true
    Content-Length: 750
    Vary: Accept-Encoding
    ...

Further examples are available in the
:ref:`neatpi modules <all-netapi-modules>` documentation.
