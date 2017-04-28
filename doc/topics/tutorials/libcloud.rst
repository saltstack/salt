.. _tutorial-libcloud:

==============================================================================
Using Apache Libcloud for declarative and procedural multi-cloud orchestration
==============================================================================

.. versionadded:: Oxygen

.. note::

    This walkthrough assumes basic knowledge of Salt and Salt States. To get up to speed, check out the
    :ref:`Salt Walkthrough <tutorial-salt-walk-through>`.

Apache Libcloud is a Python library which hides differences between different cloud provider APIs and allows
you to manage different cloud resources through a unified and easy to use API. Apache Libcloud supports over
60 cloud platforms, including Amazon, Microsoft Azure, Digital Ocean, Google Cloud Platform and OpenStack.

Execution and state modules are available for DNS, Storage and Load Balancer drivers from Apache Libcloud in
 SaltStack.

* :mod:`libcloud_storage <salt.modules.libcloud_storage>` - Cloud Object Storage and CDN - 
    services such as Amazon S3 and Rackspace CloudFiles, OpenStack Swift
* :mod:`libcloud_loadbalancer <salt.modules.libcloud_loadbalancer>` - Load Balancers as a Service - 
    services such as Amazon Elastic Load Balancer and GoGrid LoadBalancers
* :mod:`libcloud_dns <salt.modules.libcloud_dns>` - DNS as a Service - 
    services such as Amazon Route 53 and Zerigo

These modules are designed as a way of having a multi-cloud deployment and abstracting simple differences 
between platform to design a high-availability architecture.

The Apache Libcloud functionality is available through both execution modules and Salt states.

Configuring Drivers
===================

Drivers can be configured in the Salt Configuration/Minion settings. All libcloud modules expect a list of "profiles" to
be configured with authentication details for each driver.

Each driver will have a string identifier, these can be found in the libcloud.<api>.types.Provider class 
for each API, http://libcloud.readthedocs.io/en/latest/supported_providers.html

Some drivers require additional parameters, which are documented in the Apache Libcloud documentation. For example,
GoDaddy DNS expects "`shopper_id`", which is the customer ID. These additional parameters can be added to the profile settings 
and will be passed directly to the driver instantiation method.

.. code-block:: yaml

    libcloud_dns:
        godaddy:
            driver: godaddy
            shopper_id: 90425123
            key: AFDDJFGIjDFVNSDIFNASMC
            secret: FG(#f8vdfgjlkm)

    libcloud_storage:
        google:
            driver: google_storage
            key: GOOG4ASDIDFNVIdfnIVW
            secret: R+qYE9hkfdhv89h4invhdfvird4Pq3an8rnK

You can have multiple profiles for a single driver, for example if you wanted 2 DNS profiles for Amazon Route53,
naming them "route53_prod" and "route54_test" would help your
administrators distinguish their purpose.

.. code-block:: yaml

    libcloud_dns:
        route53_prod:
            driver: route53
            key: AFDDJFGIjDFVNSDIFNASMC
            secret: FG(#f8vdfgjlkm)
        route53_test:
            driver: route53
            key: AFDDJFGIjdfgdfgdf
            secret: FG(#f8vdfgjlkm)

Using the execution modules
===========================

Amongst over 60 clouds that Apache Libcloud supports, you can add profiles to your Salt configuration to access and control these clouds. 
Each of the libcloud execution modules exposes the common API methods for controlling DNS, Load Balancers and Object Storage. 
To see which functions are supported across specific clouds, see the Libcloud `supported methods 
<http://libcloud.readthedocs.io/en/latest/supported_providers.html#supported-methods-block-storage>`_ documentation.

The module documentation explains each of the API methods and how to leverage them.

* :mod:`libcloud_storage <salt.modules.libcloud_storage>` - Cloud Object Storage and CDN 
    - services such as Amazon S3 and Rackspace CloudFiles, OpenStack Swift
* :mod:`libcloud_loadbalancer <salt.modules.libcloud_loadbalancer>` - Load Balancers as a Service 
    - services such as Amazon Elastic Load Balancer and GoGrid LoadBalancers
* :mod:`libcloud_dns <salt.modules.libcloud_dns>` - DNS as a Service 
    - services such as Amazon Route 53 and Zerigo

For example, listing buckets in the Google Storage platform: 

.. code-block:: bash

    $ salt-call libcloud_storage.list_containers google

        local:
            |_
            ----------
            extra:
                ----------
                creation_date:
                    2017-01-05T05:44:56.324Z
            name:
                anthonypjshaw


The Apache Libcloud storage module can be used to syncronize files between multiple storage clouds,
such as Google Storage, S3 and OpenStack Swift

.. code-block:: bash

    $ salt '*' libcloud_storage.download_object DeploymentTools test.sh /tmp/test.sh google_storage

Using the state modules
=======================

For each configured profile, the assets available in the API (e.g. storage objects, containers, 
DNS records and load balancers) can be deployed via Salt's state system.

The state module documentation explains the specific states that each module supports

* :mod:`libcloud_storage <salt.states.libcloud_storage>` - Cloud Object Storage and CDN 
    - services such as Amazon S3 and Rackspace CloudFiles, OpenStack Swift
* :mod:`libcloud_loadbalancer <salt.states.libcloud_loadbalancer>` - Load Balancers as a Service 
    - services such as Amazon Elastic Load Balancer and GoGrid LoadBalancers
* :mod:`libcloud_dns <salt.states.libcloud_dns>` - DNS as a Service 
    - services such as Amazon Route 53 and Zerigo

For DNS, the state modules can be used to provide DNS resilience for multiple nameservers, for example:

.. code-block:: yaml

    libcloud_dns:
        godaddy:
            driver: godaddy
            shopper_id: 12345
            key: 2orgk34kgk34g
            secret: fjgoidhjgoim
        amazon:
            driver: route53
            key: blah
            secret: blah

And then in a state file:

.. code-block:: yaml

    webserver:
      libcloud_dns.zone_present:
        name: mywebsite.com
        profile: godaddy
      libcloud_dns.record_present:
        name: www
        zone: mywebsite.com
        type: A
        data: 12.34.32.3
        profile: godaddy
      libcloud_dns.zone_present:
        name: mywebsite.com
        profile: amazon
      libcloud_dns.record_present:
        name: www
        zone: mywebsite.com
        type: A
        data: 12.34.32.3
        profile: amazon

This could be combined with a multi-cloud load balancer deployment,

.. code-block:: yaml

    webserver:
      libcloud_dns.zone_present:
        - name: mywebsite.com
        - profile: godaddy
        ...
      libcloud_loadbalancer.balancer_present:
        - name: web_main
        - port: 80
        - protocol: http
        - members:
            - ip: 1.2.4.5
              port: 80
            - ip: 2.4.5.6
              port: 80
        - profile: google_gce
      libcloud_loadbalancer.balancer_present:
        - name: web_main
        - port: 80
        - protocol: http
        - members:
            - ip: 1.2.4.5
              port: 80
            - ip: 2.4.5.6
              port: 80
        - profile: amazon_elb

Extended parameters can be passed to the specific cloud, for example you can specify the region with the Google Cloud API, because
`create_balancer` can accept a `ex_region` argument. Adding this argument to the state will pass the additional command to the driver.

.. code-block:: yaml

    lb_test:
        libcloud_loadbalancer.balancer_absent:
            - name: example
            - port: 80
            - protocol: http
            - profile: google
            - ex_region: us-east1

Accessing custom arguments in execution modules
===============================================

Some cloud providers have additional functionality that can be accessed on top of the base API, for example
the Google Cloud Engine load balancer service offers the ability to provision load balancers into a specific region.

Looking at the `API documentation <http://libcloud.readthedocs.io/en/latest/loadbalancer/drivers/gce.html#libcloud.loadbalancer.drivers.gce.GCELBDriver.create_balancer>`_, 
we can see that it expects an `ex_region` in the `create_balancer` method, so when we execute the salt command, we can add this additional parameter like this:

.. code-block:: bash

    $ salt myminion libcloud_storage.create_balancer my_balancer 80 http profile1 ex_region=us-east1
    $ salt myminion libcloud_storage.list_container_objects my_bucket profile1 ex_prefix=me

Accessing custom methods in Libcloud drivers
============================================

Some cloud APIs have additional methods that are prefixed with `ex_` in Apache Libcloud, these methods 
are part of the non-standard API but can still
be accessed from the Salt modules for `libcloud_storage`, `libcloud_loadbalancer` and `libcloud_dns`. 
The extra methods are available via the `extra` command, which expects the name of the method as the 
first argument, the profile as the second and then 
accepts a list of keyword arguments to pass onto the driver method, for example, accessing permissions in Google Storage objects:

.. code-block:: bash

    $ salt myminion libcloud_storage.extra ex_get_permissions google container_name=my_container object_name=me.jpg --out=yaml

Example profiles
================

Google Cloud
~~~~~~~~~~~~

Using Service Accounts with GCE, you can provide a path to the JSON file and the project name in the parameters.

.. code-block:: yaml

    google:
        driver: gce
        user_id: 234234-compute@developer.gserviceaccount.com
        key: /path/to/service_account_download.json
        auth_type: SA
        project: project-name
