================================
Preseed Minion with Accepted Key
================================

In some situations, it is not convenient to wait for a minion to start before
accepting its key on the master. For instance, you may want the minion to
bootstrap itself as soon as it comes online. You may also want to to let your
developers provision new development machines on the fly.

.. seealso:: Many ways to preseed minion keys

    Salt has other ways to generate and pre-accept minion keys in addition to
    the manual steps outlined below.

    salt-cloud performs these same steps automatically when new cloud VMs are
    created (unless instructed not to).

    salt-api exposes an HTTP call to Salt's REST API to :py:class:`generate and
    download the new minion keys as a tarball
    <salt.netapi.rest_cherrypy.app.Keys>`.

There is a general four step process to do this:

1. Generate the keys on the master:

.. code-block:: bash

    root@saltmaster# salt-key --gen-keys=[key_name]

Pick a name for the key, such as the minion's id.

2. Add the public key to the accepted minion folder:

.. code-block:: bash

    root@saltmaster# cp key_name.pub /etc/salt/pki/master/minions/[minion_id]

It is necessary that the public key file has the same name as your minion id.
This is how Salt matches minions with their keys. Also note that the pki folder
could be in a different location, depending on your OS or if specified in the
master config file.

3. Distribute the minion keys.

There is no single method to get the keypair to your minion.  The difficulty is
finding a distribution method which is secure. For Amazon EC2 only, an AWS best
practice is to use IAM Roles to pass credentials. (See blog post,
http://blogs.aws.amazon.com/security/post/Tx610S2MLVZWEA/Using-IAM-roles-to-distribute-non-AWS-credentials-to-your-EC2-instances )

.. admonition:: Security Warning

    Since the minion key is already accepted on the master, distributing
    the private key poses a potential security risk. A malicious party
    will have access to your entire state tree and other sensitive data if they
    gain access to a preseeded minion key.

4. Preseed the Minion with the keys

You will want to place the minion keys before starting the salt-minion daemon:

.. code-block:: bash

    /etc/salt/pki/minion/minion.pem
    /etc/salt/pki/minion/minion.pub

Once in place, you should be able to start salt-minion and run
``salt-call state.highstate`` or any other salt commands that require master
authentication.
