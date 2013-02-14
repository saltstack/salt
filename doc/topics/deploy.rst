========================
OS Support for Cloud VMs
========================

Salt Cloud works primarily by executing a script on the virtual machines as
soon as they become available. The script that is executed is referenced in
the cloud profile as the ``script``. In older versions, this was the ``os``
argument. This was changed in 0.8.2.

A number of legacy scripts exist in the deploy directory in the saltcloud
source tree. The preferred method is currently to use the salt-bootstrap
script. A stable version is included with each release tarball starting with
0.8.4. The most updated version can be found at:

https://github.com/saltstack/salt-bootstrap

If you do not specify a script argument, this script will be used at the
default.

If the Salt Bootstrap script does not meet your needs, you may write your own.
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

A number of legacy deploy scripts are included with the release tarball. None
of them are as functional or complete as Salt Bootstrap, and are still included
for academic purposes.


Other Generic Deploy Scripts
============================
If you want to be assured of always using the latest Salt Bootstrap script,
there are a few generic templates available in the deploy directory of your
saltcloud source tree:

.. code-block::

    curl-bootstrap
    curl-bootstrap-git
    python-bootstrap
    wget-bootstrap
    wget-bootstrap-git

These are example scripts which were designed to be customized, adapted, and
refit to meet your needs. One important use of them is to pass options to
the salt-bootstrap script, such as updating to specific git tags.


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

In the profile, you may also set the script option to None:

.. code-block:: yaml

    script: None

This is the slowest option, since it still uploads the None deploy script and executes it.

Updating Salt Bootstrap
=======================
Salt Bootstrap can be updated automatically with salt-cloud:

.. code-block:: bash

    salt-cloud -u
    salt-cloud --update-bootstrap

Bear in mind that this updates to the latest (unstable) version, so use with
caution.

Keeping /tmp/ Files
===================
When Salt Cloud deploys an instance, it uploads temporary files to /tmp/ for
salt-bootstrap to put in place. After the script has run, they are deleted. To
keep these files around (mostly for debugging purposes), the --keep-tmp option
can be added:

.. code-block:: bash

    salt-cloud -p myprofile mymachine --keep-tmp

For those wondering why /tmp/ was used instead of /root/, this had to be done
for images which require the use of sudo, and therefore do not allow remote
root logins, even for file transfers (which makes /root/ unavailable).

Deploy Script Arguments
=======================
Custom deploy scripts are unlikely to need custom arguments to be passed to
them, but salt-bootstrap has been extended quite a bit, and this may be
necessary. script_args can be specified in either the profile or the map
file, to pass arguments to the deploy script:

.. code-block:: yaml

    aws-amazon:
        provider: aws
        image: ami-1624987f
        size: Micro Instance
        ssh_username: ec2-user
        script: bootstrap-salt
        script_args: -c /tmp/

This has also been tested to work with pipes, if needed:

.. code-block:: yaml

    script_args: | head

