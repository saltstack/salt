:orphan:

======================================
Salt Release Notes - Codename Fluorine
======================================

New Docker Proxy Minion
-----------------------

Docker containers can now be treated as actual minions without installing salt
in the container, using the new :py:mod:`docker proxy minion <salt.proxy.docker>`.

This proxy minion uses the :py:mod:`docker executor <salt.executors.docker>` to
pass commands to the docker container using :py:func:`docker.call
<salt.modules.dockermod.call>`.  Any state module calls are passed through the
corresponding function from the :py:mod:`docker <salt.modules.dockermod>`
module.

.. code-block:: yaml

    proxy:
      proxytype: docker
      name: keen_proskuriakova


Grains Dictionary Passed into Custom Grains
-------------------------------------------

Starting in this release, if a custom grains function accepts a variable named
``grains``, the Grains dictionary of the already compiled grains will be passed
in.  Because of the non-deterministic order that grains are rendered in, the
only grains that can be relied upon to be passed in are ``core.py`` grains,
since those are compiled first.


"Virtual Package" Support Dropped for APT
-----------------------------------------

In APT, some packages have an associated list of packages which they provide.
This allows one to do things like run ``apt-get install foo`` when the real
package name is ``foo1.0``, and get the right package installed.

Salt has traditionally designated as "virtual packages" those which are
provided by an installed package, but for which there is no real package by
that name installed. Given the above example, if one were to run a
:py:func:`pkg.installed <salt.states.pkg.installed>` state for a package named
``foo``, then :py:func:`pkg.list_pkgs <salt.modules.aptpkg.list_pkgs>` would
show a package version of simply ``1`` for package ``foo``, denoting that it is
a virtual package.

However, while this makes certain aspects of package management convenient,
there are issues with this approach that make relying on "virtual packages"
problematic. For instance, Ubuntu has four different mutually-conflicting
packages for ``nginx``:

- nginx-core_
- nginx-full_
- nginx-light_
- nginx-extras_

All four of these provide ``nginx``. Yet there is an nginx_ package as well,
which has no actual content and merely has dependencies on any one of the above
four packages. If one used ``nginx`` in a :py:func:`pkg.installed
<salt.states.pkg.installed>` state, and none of the above four packages were
installed, then the nginx_ metapackage would be installed, which would pull in
`nginx-core_`.  Later, if ``nginx`` were used in a :py:func:`pkg.removed
<salt.states.pkg.removed>` state, the nginx_ metapackage would be removed,
leaving nginx-core_ installed. The result would be that, since `nginx-core_`
provides `nginx_`, Salt would now see nginx_ as an installed virtual package,
and the :py:func:`pkg.removed <salt.states.pkg.removed>` state would fail.
Moreover, *nginx would not actually have been removed*, since nginx-core_ would
remain installed.

.. _nginx-core: https://packages.ubuntu.com/xenial/nginx-core
.. _nginx-full: https://packages.ubuntu.com/xenial/nginx-full
.. _nginx-light: https://packages.ubuntu.com/xenial/nginx-light
.. _nginx-extras: https://packages.ubuntu.com/xenial/nginx-extras
.. _nginx: https://packages.ubuntu.com/xenial/nginx

Starting with this release, Salt will no longer support using "virtual package"
names in ``pkg`` states, and package names will need to be specified using the
proper package name. The :py:func:`pkg.list_repo_pkgs
<salt.modules.aptpkg.list_repo_pkgs>` function can be used to find matching
package names in the repositories, given a package name (or glob):

.. code-block:: bash

    # salt myminion pkg.list_repo_pkgs 'nginx*'
    myminion:
        ----------
        nginx:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-common:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-core:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-core-dbg:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-doc:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-extras:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-extras-dbg:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-full:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-full-dbg:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-light:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1
        nginx-light-dbg:
            - 1.10.3-0ubuntu0.16.04.2
            - 1.9.15-0ubuntu1

Alternatively, the newly-added :py:func:`pkg.show <salt.modules.aptpkg.show>`
function can be used to get more detailed information about a given package and
help determine what package name is correct:

.. code-block:: bash

    # salt myminion pkg.show 'nginx*' filter=description,provides
    myminion:
        ----------
        nginx:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    small, powerful, scalable web/proxy server
            1.9.15-0ubuntu1:
                ----------
                Description:
                    small, powerful, scalable web/proxy server
        nginx-common:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    small, powerful, scalable web/proxy server - common files
            1.9.15-0ubuntu1:
                ----------
                Description:
                    small, powerful, scalable web/proxy server - common files
        nginx-core:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (core version)
                Provides:
                    httpd, httpd-cgi, nginx
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (core version)
                Provides:
                    httpd, httpd-cgi, nginx
        nginx-core-dbg:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (core version) - debugging symbols
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (core version) - debugging symbols
        nginx-doc:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    small, powerful, scalable web/proxy server - documentation
            1.9.15-0ubuntu1:
                ----------
                Description:
                    small, powerful, scalable web/proxy server - documentation
        nginx-extras:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (extended version)
                Provides:
                    httpd, httpd-cgi, nginx
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (extended version)
                Provides:
                    httpd, httpd-cgi, nginx
        nginx-extras-dbg:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (extended version) - debugging symbols
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (extended version) - debugging symbols
        nginx-full:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (standard version)
                Provides:
                    httpd, httpd-cgi, nginx
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (standard version)
                Provides:
                    httpd, httpd-cgi, nginx
        nginx-full-dbg:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (standard version) - debugging symbols
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (standard version) - debugging symbols
        nginx-light:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (basic version)
                Provides:
                    httpd, httpd-cgi, nginx
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (basic version)
                Provides:
                    httpd, httpd-cgi, nginx
        nginx-light-dbg:
            ----------
            1.10.3-0ubuntu0.16.04.2:
                ----------
                Description:
                    nginx web/proxy server (basic version) - debugging symbols
            1.9.15-0ubuntu1:
                ----------
                Description:
                    nginx web/proxy server (basic version) - debugging symbols


Minion Startup Events
---------------------

When a minion starts up it sends a notification on the event bus with a tag
that looks like this: ``salt/minion/<minion_id>/start``. For historical reasons
the minion also sends a similar event with an event tag like this:
``minion_start``. This duplication can cause a lot of clutter on the event bus
when there are many minions. Set ``enable_legacy_startup_events: False`` in the
minion config to ensure only the ``salt/minion/<minion_id>/start`` events are
sent.

The new :conf_minion:`enable_legacy_startup_events` minion config option
defaults to ``True``, but will be set to default to ``False`` beginning with
the Neon release of Salt.

The Salt Syndic currently sends an old style ``syndic_start`` event as well. The
syndic respects :conf_minion:`enable_legacy_startup_events` as well.


Failhard changes
----------------

It is now possible to override a global failhard setting with a state-level
failhard setting. This is most useful in case where global failhard is set to
``True`` and you want the execution not to stop for a specific state that
could fail, by setting the state level failhard to ``False``.
This also allows for the use of ``onfail*``-requisites, which would previously
be ignored when a global failhard was set to ``True``.
This is a deviation from previous behavior, where the global failhard setting
always resulted in an immediate stop whenever any state failed (regardless
of whether the failing state had a failhard setting of its own, or whether
any ``onfail*``-requisites were used).


Pass Through Options to :py:func:`file.serialize <salt.states.file.serialize>` State
------------------------------------------------------------------------------------

This allows for more granular control over the way in which the dataset is
serialized. See the documentation for the new ``serializer_opts`` option in the
:py:func:`file.serialize <salt.states.file.serialize>` state for more
information.


:py:func:`file.patch <salt.sates.file.patch>` State Rewritten
-------------------------------------------------------------

The :py:func:`file.patch <salt.sates.file.patch>` state has been rewritten with
several new features:

- Patch sources can now be remote files instead of only ``salt://`` URLs
- Multi-file patches are now supported
- Patch files can be templated

In addition, it is no longer necessary to specify what the hash of the patched
file should be.


Deprecations
------------

API Deprecations
================

Support for :ref:`LocalClient <local-client>`'s ``expr_form`` argument has
been removed. Please use ``tgt_type`` instead. This change was made due to
numerous reports of confusion among community members, since the targeting
method is published to minions as ``tgt_type``, and appears as ``tgt_type``
in the job cache as well.

Those who are using the :ref:`LocalClient <local-client>` (either directly,
or implicitly via a :ref:`netapi module <all-netapi-modules>`) need to update
their code to use ``tgt_type``.

.. code-block:: python

    >>> import salt.client
    >>> local = salt.client.LocalClient()
    >>> local.cmd('*', 'cmd.run', ['whoami'], tgt_type='glob')
    {'jerry': 'root'}

Module Deprecations
===================

The ``napalm_network`` module had the following changes:

- Support for the ``template_path`` has been removed in the ``load_template``
  function. This is because support for NAPALM native templates has been
  dropped.

The ``trafficserver`` module had the following changes:

- Support for the ``match_var`` function was removed. Please use the
  ``match_metric`` function instead.
- Support for the ``read_var`` function was removed. Please use the
  ``read_config`` function instead.
- Support for the ``set_var`` function was removed. Please use the
  ``set_config`` function instead.

The ``win_update`` module has been removed. It has been replaced by ``win_wua``
module.

The ``win_wua`` module had the following changes:

- Support for the ``download_update`` function has been removed. Please use the
  ``download`` function instead.
- Support for the ``download_updates`` function has been removed. Please use the
  ``download`` function instead.
- Support for the ``install_update`` function has been removed. Please use the
  ``install`` function instead.
- Support for the ``install_updates`` function has been removed. Please use the
  ``install`` function instead.
- Support for the ``list_update`` function has been removed. Please use the
  ``get`` function instead.
- Support for the ``list_updates`` function has been removed. Please use the
  ``list`` function instead.

Pillar Deprecations
===================

The ``vault`` pillar had the following changes:

- Support for the ``profile`` argument was removed. Any options passed up until
  and following the first ``path=`` are discarded.

Roster Deprecations
===================

The ``cache`` roster had the following changes:

- Support for ``roster_order`` as a list or tuple has been removed. As of the
  ``Fluorine`` release, ``roster_order`` must be a dictionary.
- The ``roster_order`` option now includes IPv6 in addition to IPv4 for the
  ``private``, ``public``, ``global`` or ``local`` settings. The syntax for these
  settings has changed to ``ipv4-*`` or ``ipv6-*``, respectively.

State Deprecations
==================

The ``docker`` state has been removed. The following functions should be used
instead.

- The ``docker.running`` function was removed. Please update applicable SLS files
  to use the ``docker_container.running`` function instead.
- The ``docker.stopped`` function was removed. Please update applicable SLS files
  to use the ``docker_container.stopped`` function instead.
- The ``docker.absent`` function was removed. Please update applicable SLS files
  to use the ``docker_container.absent`` function instead.
- The ``docker.absent`` function was removed. Please update applicable SLS files
  to use the ``docker_container.absent`` function instead.
- The ``docker.network_present`` function was removed. Please update applicable
  SLS files to use the ``docker_network.present`` function instead.
- The ``docker.network_absent`` function was removed. Please update applicable
  SLS files to use the ``docker_network.absent`` function instead.
- The ``docker.image_present`` function was removed. Please update applicable SLS
  files to use the ``docker_image.present`` function instead.
- The ``docker.image_absent`` function was removed. Please update applicable SLS
  files to use the ``docker_image.absent`` function instead.
- The ``docker.volume_present`` function was removed. Please update applicable SLS
  files to use the ``docker_volume.present`` function instead.
- The ``docker.volume_absent`` function was removed. Please update applicable SLS
  files to use the ``docker_volume.absent`` function instead.

The ``docker_network`` state had the following changes:

- Support for the ``driver`` option has been removed from the ``absent`` function.
  This option had no functionality in ``docker_network.absent``.

The ``git`` state had the following changes:

- Support for the ``ref`` option in the ``detached`` state has been removed.
  Please use the ``rev`` option instead.

The ``k8s`` state has been removed. The following functions should be used
instead:

- The ``k8s.label_absent`` function was removed. Please update applicable SLS
  files to use the ``kubernetes.node_label_absent`` function instead.
- The ``k8s.label_present`` function was removed. Please updated applicable SLS
  files to use the ``kubernetes.node_label_present`` function instead.
- The ``k8s.label_folder_absent`` function was removed. Please update applicable
  SLS files to use the ``kubernetes.node_label_folder_absent`` function instead.

The ``netconfig`` state had the following changes:

- Support for the ``template_path`` option in the ``managed`` state has been
  removed. This is because support for NAPALM native templates has been dropped.

The ``trafficserver`` state had the following changes:

- Support for the ``set_var`` function was removed. Please use the ``config``
  function instead.

The ``win_update`` state has been removed. Please use the ``win_wua`` state instead.

Utils Deprecations
==================

The ``vault`` utils module had the following changes:

- Support for specifying Vault connection data within a 'profile' has been removed.
  Please see the :mod:`vault execution module <salt.modules.vault>` documentation for
  details on the new configuration schema.

=====================
SaltSSH major updates
=====================

SaltSSH now works across different major Python versions. Python 2.7 ~ Python 3.x
are now supported transparently. Requirement is, however, that the SaltMaster should
have installed Salt, including all related dependencies for Python 2 and Python 3.
Everything needs to be importable from the respective Python environment.

SaltSSH can bundle up an arbitrary version of Salt. If there would be an old box for
example, running an outdated and unsupported Python 2.6, it is still possible from
a SaltMaster with Python 3.5 or newer to access it. This feature requires an additional
configuration in /etc/salt/master as follows:


.. code-block:: yaml

       ssh_ext_alternatives:
           2016.3:                     # Namespace, can be actually anything.
               py-version: [2, 6]      # Constraint to specific interpreter version
               path: /opt/2016.3/salt  # Main Salt installation
               dependencies:           # List of dependencies and their installation paths
                 jinja2: /opt/jinja2
                 yaml: /opt/yaml
                 tornado: /opt/tornado
                 msgpack: /opt/msgpack
                 certifi: /opt/certifi
                 singledispatch: /opt/singledispatch.py
                 singledispatch_helpers: /opt/singledispatch_helpers.py
                 markupsafe: /opt/markupsafe
                 backports_abc: /opt/backports_abc.py

It is also possible to use several alternative versions of Salt. You can for instance generate
a minimal tarball using runners and include that. But this is only possible, when such specific
Salt version is also available on the Master machine, although does not need to be directly
installed together with the older Python interpreter.

SaltSSH now support private key's passphrase. You can configure it by:

* `--priv-passwd` for salt-ssh cli
* `salt_priv_passwd` for salt master configure file
* `priv_passwd` for salt roster file


========================
Salt-Cloud major updates
========================


Dependency Deprecations
=======================

Salt-Cloud has been updated to use the ``pypsexec`` Python library instead of the
``winexe`` executable. Both ``winexe`` and ``pypsexec`` run remote commands
against Windows OSes. Since ``winexe`` is not packaged for every system, it has
been deprecated in favor of ``pypsexec``.

Salt-Cloud has deprecated the use ``impacket`` in favor of ``smbprotocol``.
This changes was made because ``impacket`` is not compatible with Python 3.


====================
State Module Changes
====================

states.saltmod
--------------
The 'test' option now defaults to None. A value of True or False set here is
passed to the state being run and can be used to override a ``test:True`` option
set in the minion's config file. In previous releases the minion's config option
would take precedence and it would be impossible to run an orchestration on a
minion with test mode set to True in the config file.

If a minion is not in permanent test mode due to the config file and the 'test'
argument here is left as None then a value of ``test=True`` on the command-line is
passed correctly to the minion to run an orchestration in test mode. At present
it is not possible to pass ``test=False`` on the command-line to override a
minion in permanent test mode and so the ``test:False`` option must still be set
in the orchestration file.

states.event
--------------
The :ref:`event.send <salt.states.event.send>` state does not know the results of 
the sent event, so returns changed every state run.  It can now be set to 
return changed or unchanged.

============================
LDAP External Authentication
============================

freeipa 'groupattribute' support
--------------------------------
Previously, if Salt was using external authentication against a freeipa LDAP system
it could only search for users via the 'accountattributename' field. This release
add an additional search using the 'groupattribute' field as well. The original
'accountattributename' search is done first then the 'groupattribute' allowing for
backward compatibility with previous Salt releases.
