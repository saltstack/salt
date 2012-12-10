========================
OS Support for Cloud VMS
========================

Salt cloud works primarily by executing a script on the virtual machines as
soon as they become available. The script that is executed is referenced in
the cloud profile as the ``script``.

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


Post-Deploy Commands
====================

Once a minion has been deployed, it has the option to run a salt command. Normally, this would be the state.highstate command, which would finish provisioning the VM. Another common option is state.sls, or for just testing, test.ping. This is configured in the main cloud config file:

.. code-block:: yaml

    start_action: state.highstate

This is currently considered to be experimental functionality, and may not work well with all providers. If you experience problems with Salt Cloud hanging after Salt is deployed, consider using Startup States instead:

http://docs.saltstack.org/en/latest/ref/states/startup.html


Skipping the Deploy Script
==========================

For whatever reason, you may want to skip the deploy script altogether. This results in a VM being spun up much faster, with absolutely no configuration. This can be set from the command line:

.. code-block:: bash

    salt-cloud --no-deploy -p micro_aws my_instance

Or it can be set from the main cloud config file:

.. code-block:: yaml

    deploy: False

The default for deploy is True.

