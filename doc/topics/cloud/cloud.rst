==============================
Writing Cloud Provider Modules
==============================

Salt Cloud runs on a module system similar to the main Salt project. The
modules inside saltcloud exist in the ``saltcloud/clouds`` directory of the
salt-cloud source.

Adding a provider requires that a cloud module is created. The cloud module
needs to only impliment a single function ``create``, which will accept a
single virtual machine data structure. Whatever functions need to be called to
execute the create function can and should be included in the provider module.

A good example to follow for writing a cloud provider module is the module
provided for Linode:

https://github.com/saltstack/salt-cloud/blob/master/saltcloud/clouds/linode.py

If possible it is prefered that libcloud is used to connect to public cloud
systems, but if libcloud support is not available or another system makes more
sense then by all means, use the other system to connect to the cloud provider.

An example of a non-libcloud provider is the ec2 module:

https://github.com/saltstack/salt-cloud/blob/develop/saltcloud/clouds/ec2.py

