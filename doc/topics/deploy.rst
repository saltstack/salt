========================
OS Support for Cloud VMS
========================

Salt cloud works primarily by executing a script on the virtual machines as
soon as they become available. The script that is executed is referenced in
the cloud profile as the ``os``.

The script should be written in bash and is a Jinja template. Deploy scripts
need to execute a number of functions to do a complete salt setup. These
functions include:

1. Install the salt minion. If this can be done via system packages this method
   is HIGHLY preferred.
2. Add the salt minion keys before the minion is started for the first time.
   The minion keys are available as strings that can be copied into place in
   the Jinja template under the dict named "vm".
3. Start the salt-minion daemon and enable it at startup time.
4. Set up the minion configuration file from the "minion" data available in
   the Jinja template.

A good, well commented, example of this process is the Fedora deployment
script:

https://github.com/saltstack/salt-cloud/blob/master/saltcloud/deploy/Fedora.sh


.. code-block:: bash

    #!/bin/bash

    # Install the salt-minion package from yum. This is easy for Fedora because
    # Salt packages are in the Fedora package repos
    yum install -y salt-minion
    # Save in the minion public and private RSA keys before the minion is started
    mkdir -p /etc/salt/pki
    echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
    echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
    # Copy the minion configuration file into place before starting the minion
    echo '{{ minion }}' > /etc/salt/minion
    # Set the minion to start on reboot
    systemctl enable salt-minion.service
    # Start the minion!
    systemctl start salt-minion.service

