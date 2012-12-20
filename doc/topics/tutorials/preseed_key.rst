=================================
Preseed Minion with Accepted Key
=================================

In some situations, it is not convenient to wait for a minion to start before 
accepting its key on the master. For instance, you may want the minion to 
bootstrap itself as soon as it comes online. You may also want to to let your 
developers provision new development machines on the fly.

There is a general four step process to do this:

1. Generate the keys on the master::

    root@saltmaster# salt-key --gen-keys=[key_name]

Pick a name for the key, such as the minion's id.

2. Add the public key to the accepted minion folder:: 

    root@saltmaster# cp key_name.pub /etc/salt/pki/minions/[minion_id]

It is necessary that the public key file has the same name as your minion id. 
This is how Salt matches minions with their keys. Also note that the pki folder 
could be in a different location, depending on your OS or if specified in the 
master config file.

3. Distribute the minion keys.

There is no single method to get the keypair to your minion. If you are 
spooling up minions on EC2, you could pass them in using user_data or a 
cloud-init script. If you are handing them off to a team of developers for provisioning dev machines, you will need a secure file transfer.

.. admonition:: Security Warning

	Since the minion key is already accepted on the master, distributing 
	the private key poses a potential security risk. A malicious party 
	will have access to your entire state tree and other sensitive data.

4. Preseed the Minion with the keys

You will want to place the minion keys before starting the salt-minion daemon::

    /etc/salt/pki/minion.pem
    /etc/salt/pki/minion.pub

Once in place, you should be able to start salt-minion and run 
``salt-call state.highstate`` or any other salt commands that require master 
authentication.