.. _pillar:

=================================
Storing Static Data in the Pillar
=================================

Pillar is an interface for Salt designed to offer global values that can be
distributed to minions. Pillar data is managed in a similar way as
the Salt State Tree.

Pillar was added to Salt in version 0.9.8

.. note:: Storing sensitive data

    Pillar data is compiled on the master. Additionally, pillar data for a
    given minion is only accessible by the minion for which it is targeted in
    the pillar configuration. This makes pillar useful for storing sensitive
    data specific to a particular minion.


Declaring the Master Pillar
===========================

The Salt Master server maintains a :conf_master:`pillar_roots` setup that
matches the structure of the :conf_master:`file_roots` used in the Salt file
server. Like :conf_master:`file_roots`, the :conf_master:`pillar_roots` option
maps environments to directories. The pillar data is then mapped to minions
based on matchers in a top file which is laid out in the same way as the state
top file. Salt pillars can use the same matcher types as the standard :ref:`top
file <states-top>`.

conf_master:`pillar_roots` is configured just like :conf_master:`file_roots`.
For example:

.. code-block:: yaml

    pillar_roots:
      base:
        - /srv/pillar

This example configuration declares that the base environment will be located
in the ``/srv/pillar`` directory. It must not be in a subdirectory of the
state tree.

The top file used matches the name of the top file used for States,
and has the same structure:

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      '*':
        - packages

In the above top file, it is declared that in the ``base`` environment, the
glob matching all minions will have the pillar data found in the ``packages``
pillar available to it. Assuming the ``pillar_roots`` value of ``/srv/pillar``
taken from above, the ``packages`` pillar would be located at
``/srv/pillar/packages.sls``.

Any number of matchers can be added to the base environment. For example, here
is an expanded version of the Pillar top file stated above:

/srv/pillar/top.sls:

.. code-block:: yaml

    base:
      '*':
        - packages
      'web*':
        - vim

In this expanded top file, minions that match ``web*`` will have access to the
``/srv/pillar/packages.sls`` file, as well as the ``/srv/pillar/vim.sls`` file.

Another example shows how to use other standard top matching types
to deliver specific salt pillar data to minions with different properties.

Here is an example using the ``grains`` matcher to target pillars to minions
by their ``os`` grain:

.. code-block:: yaml

    dev:
      'os:Debian':
        - match: grain
        - servers

``/srv/pillar/packages.sls``

.. code-block:: jinja

    {% if grains['os'] == 'RedHat' %}
    apache: httpd
    git: git
    {% elif grains['os'] == 'Debian' %}
    apache: apache2
    git: git-core
    {% endif %}

    company: Foo Industries

.. important::
  See :ref:`Is Targeting using Grain Data Secure? <faq-grain-security>` for
  important security information.

The above pillar sets two key/value pairs. If a minion is running RedHat, then
the ``apache`` key is set to ``httpd`` and the ``git`` key is set to the value
of ``git``. If the minion is running Debian, those values are changed to
``apache2`` and ``git-core`` respectively. All minions that have this pillar
targeting to them via a top file will have the key of ``company`` with a value
of ``Foo Industries``.

Consequently this data can be used from within modules, renderers, State SLS
files, and more via the shared pillar :ref:`dict <python2:typesmapping>`:

.. code-block:: jinja

    apache:
      pkg.installed:
        - name: {{ pillar['apache'] }}

.. code-block:: jinja

    git:
      pkg.installed:
        - name: {{ pillar['git'] }}

Finally, the above states can utilize the values provided to them via Pillar.
All pillar values targeted to a minion are available via the 'pillar'
dictionary. As seen in the above example, Jinja substitution can then be
utilized to access the keys and values in the Pillar dictionary.

Note that you cannot just list key/value-information in ``top.sls``. Instead,
target a minion to a pillar file and then list the keys and values in the
pillar. Here is an example top file that illustrates this point:

.. code-block:: yaml

    base:
      '*':
         - common_pillar

And the actual pillar file at '/srv/pillar/common_pillar.sls':

.. code-block:: yaml

    foo: bar
    boo: baz

.. note::
    When working with multiple pillar environments, assuming that each pillar
    environment has its own top file, the jinja placeholder ``{{ saltenv }}``
    can be used in place of the environment name:

    .. code-block:: jinja

        {{ saltenv }}:
          '*':
             - common_pillar

    Yes, this is ``{{ saltenv }}``, and not ``{{ pillarenv }}``. The reason for
    this is because the Pillar top files are parsed using some of the same code
    which parses top files when :ref:`running states <running-highstate>`, so
    the pillar environment takes the place of ``{{ saltenv }}`` in the jinja
    context.


Pillar Namespace Flattening
===========================

The separate pillar SLS files all merge down into a single dictionary of
key-value pairs. When the same key is defined in multiple SLS files, this can
result in unexpected behavior if care is not taken to how the pillar SLS files
are laid out.

For example, given a ``top.sls`` containing the following:

.. code-block:: yaml

    base:
      '*':
        - packages
        - services

with ``packages.sls`` containing:

.. code-block:: yaml

    bind: bind9

and ``services.sls`` containing:

.. code-block:: yaml

    bind: named

Then a request for the ``bind`` pillar key will only return ``named``. The
``bind9`` value will be lost, because ``services.sls`` was evaluated later.

.. note::
    Pillar files are applied in the order they are listed in the top file.
    Therefore conflicting keys will be overwritten in a 'last one wins' manner!
    For example, in the above scenario conflicting key values in ``services``
    will overwrite those in ``packages`` because it's at the bottom of the list.

It can be better to structure your pillar files with more hierarchy. For
example the ``package.sls`` file could be configured like so:

.. code-block:: yaml

    packages:
      bind: bind9

This would make the ``packages`` pillar key a nested dictionary containing a
``bind`` key.

Pillar Dictionary Merging
=========================

If the same pillar key is defined in multiple pillar SLS files, and the keys in
both files refer to nested dictionaries, then the content from these
dictionaries will be recursively merged.

For example, keeping the ``top.sls`` the same, assume the following
modifications to the pillar SLS files:

``packages.sls``:

.. code-block:: yaml

    bind:
      package-name: bind9
      version: 9.9.5

``services.sls``:

.. code-block:: yaml

    bind:
      port: 53
      listen-on: any

The resulting pillar dictionary will be:

.. code-block:: bash

    $ salt-call pillar.get bind
    local:
        ----------
        listen-on:
            any
        package-name:
            bind9
        port:
            53
        version:
            9.9.5

Since both pillar SLS files contained a ``bind`` key which contained a nested
dictionary, the pillar dictionary's ``bind`` key contains the combined contents
of both SLS files' ``bind`` keys.

Including Other Pillars
=======================

.. versionadded:: 0.16.0

Pillar SLS files may include other pillar files, similar to State files. Two
syntaxes are available for this purpose. The simple form simply includes the
additional pillar as if it were part of the same file:

.. code-block:: yaml

    include:
      - users

The full include form allows two additional options -- passing default values
to the templating engine for the included pillar file as well as an optional
key under which to nest the results of the included pillar:

.. code-block:: yaml

    include:
      - users:
          defaults:
              sudo: ['bob', 'paul']
          key: users

With this form, the included file (users.sls) will be nested within the 'users'
key of the compiled pillar. Additionally, the 'sudo' value will be available
as a template variable to users.sls.

.. _pillar-in-memory:

In-Memory Pillar Data vs. On-Demand Pillar Data
===============================================

Since compiling pillar data is computationally expensive, the minion will
maintain a copy of the pillar data in memory to avoid needing to ask the master
to recompile and send it a copy of the pillar data each time pillar data is
requested. This in-memory pillar data is what is returned by the
:py:func:`pillar.item <salt.modules.pillar.item>`, :py:func:`pillar.get
<salt.modules.pillar.get>`, and :py:func:`pillar.raw <salt.modules.pillar.raw>`
functions.

Also, for those writing custom execution modules, or contributing to Salt's
existing execution modules, the in-memory pillar data is available as the
``__pillar__`` dunder dictionary.

The in-memory pillar data is generated on minion start, and can be refreshed
using the :py:func:`saltutil.refresh_pillar
<salt.modules.saltutil.refresh_pillar>` function:

.. code-block:: bash

    salt '*' saltutil.refresh_pillar

This function triggers the minion to asynchronously refresh the in-memory
pillar data and will always return ``None``.

In contrast to in-memory pillar data, certain actions trigger pillar data to be
compiled to ensure that the most up-to-date pillar data is available. These
actions include:

- Running states
- Running :py:func:`pillar.items <salt.modules.pillar.items>`

Performing these actions will *not* refresh the in-memory pillar data. So, if
pillar data is modified, and then states are run, the states will see the
updated pillar data, but :py:func:`pillar.item <salt.modules.pillar.item>`,
:py:func:`pillar.get <salt.modules.pillar.get>`, and :py:func:`pillar.raw
<salt.modules.pillar.raw>` will not see this data unless refreshed using
:py:func:`saltutil.refresh_pillar <salt.modules.saltutil.refresh_pillar>`.

.. _pillar-environments:

How Pillar Environments Are Handled
===================================

When multiple pillar environments are used, the default behavior is for the
pillar data from all environments to be merged together. The pillar dictionary
will therefore contain keys from all configured environments.

The :conf_minion:`pillarenv` minion config option can be used to force the
minion to only consider pillar configuration from a single environment. This
can be useful in cases where one needs to run states with alternate pillar
data, either in a testing/QA environment or to test changes to the pillar data
before pushing them live.

For example, assume that the following is set in the minion config file:

.. code-block:: yaml

    pillarenv: base

This would cause that minion to ignore all other pillar environments besides
``base`` when compiling the in-memory pillar data. Then, when running states,
the ``pillarenv`` CLI argument can be used to override the minion's
:conf_minion:`pillarenv` config value:

.. code-block:: bash

    salt '*' state.apply mystates pillarenv=testing

The above command will run the states with pillar data sourced exclusively from
the ``testing`` environment, without modifying the in-memory pillar data.

.. note::
    When running states, the ``pillarenv`` CLI option does not require a
    :conf_minion:`pillarenv` option to be set in the minion config file. When
    :conf_minion:`pillarenv` is left unset, as mentioned above all configured
    environments will be combined. Running states with ``pillarenv=testing`` in
    this case would still restrict the states' pillar data to just that of the
    ``testing`` pillar environment.

Starting in the Nitrogen release, it is possible to pin the pillarenv to the
effective saltenv, using the :conf_minion:`pillarenv_from_saltenv` minion
config option. When this is set to ``True``, if a specific saltenv is specified
when running states, the ``pillarenv`` will be the same. This essentially makes
the following two commands equivalent:

.. code-block:: bash

    salt '*' state.apply mystates saltenv=dev
    salt '*' state.apply mystates saltenv=dev pillarenv=dev

However, if a pillarenv is specified, it will override this behavior. So, the
following command will use the ``qa`` pillar environment but source the SLS
files from the ``dev`` saltenv:

.. code-block:: bash

    salt '*' state.apply mystates saltenv=dev pillarenv=qa

So, if a ``pillarenv`` is set in the minion config file,
:conf_minion:`pillarenv_from_saltenv` will be ignored, and passing a
``pillarenv`` on the CLI will temporarily override
:conf_minion:`pillarenv_from_saltenv`.


Viewing Pillar Data
===================

To view pillar data, use the :mod:`pillar <salt.modules.pillar>` execution
module. This module includes several functions, each of them with their own
use. These functions include:

- :py:func:`pillar.item <salt.modules.pillar.item>` - Retrieves the value of
  one or more keys from the :ref:`in-memory pillar datj <pillar-in-memory>`.
- :py:func:`pillar.items <salt.modules.pillar.items>` - Compiles a fresh pillar
  dictionary and returns it, leaving the :ref:`in-memory pillar data
  <pillar-in-memory>` untouched. If pillar keys are passed to this function
  however, this function acts like :py:func:`pillar.item
  <salt.modules.pillar.item>` and returns their values from the :ref:`in-memory
  pillar data <pillar-in-memory>`.
- :py:func:`pillar.raw <salt.modules.pillar.raw>` - Like :py:func:`pillar.items
  <salt.modules.pillar.items>`, it returns the entire pillar dictionary, but
  from the :ref:`in-memory pillar data <pillar-in-memory>` instead of compiling
  fresh pillar data.
- :py:func:`pillar.get <salt.modules.pillar.get>` - Described in detail below.


The :py:func:`pillar.get <salt.modules.pillar.get>` Function
============================================================

.. versionadded:: 0.14.0

The :mod:`pillar.get <salt.modules.pillar.get>` function works much in the same
way as the ``get`` method in a python dict, but with an enhancement: nested
dictonaries can be traversed using a colon as a delimiter.

If a structure like this is in pillar:

.. code-block:: yaml

    foo:
      bar:
        baz: qux

Extracting it from the raw pillar in an sls formula or file template is done
this way:

.. code-block:: jinja

    {{ pillar['foo']['bar']['baz'] }}

Now, with the new :mod:`pillar.get <salt.modules.pillar.get>` function the data
can be safely gathered and a default can be set, allowing the template to fall
back if the value is not available:

.. code-block:: jinja

    {{ salt['pillar.get']('foo:bar:baz', 'qux') }}

This makes handling nested structures much easier.

.. note:: ``pillar.get()`` vs ``salt['pillar.get']()``

    It should be noted that within templating, the ``pillar`` variable is just
    a dictionary.  This means that calling ``pillar.get()`` inside of a
    template will just use the default dictionary ``.get()`` function which
    does not include the extra ``:`` delimiter functionality.  It must be
    called using the above syntax (``salt['pillar.get']('foo:bar:baz',
    'qux')``) to get the salt function, instead of the default dictionary
    behavior.

Setting Pillar Data at the Command Line
=======================================

Pillar data can be set at the command line like the following example:

.. code-block:: bash

    salt '*' state.apply pillar='{"cheese": "spam"}'

This will add a pillar key of ``cheese`` with its value set to ``spam``.

.. note::

    Be aware that when sending sensitive data via pillar on the command-line
    that the publication containing that data will be received by all minions
    and will not be restricted to the targeted minions. This may represent
    a security concern in some cases.

.. _pillar-encryption:

Pillar Encryption
=================

Salt's renderer system can be used to decrypt pillar data. This allows for
pillar items to be stored in an encrypted state, and decrypted during pillar
compilation.

Encrypted Pillar SLS
--------------------

.. versionadded:: Nitrogen

Consider the following pillar SLS file:

.. code-block:: yaml

    secrets:
      vault:
        foo: |
          -----BEGIN PGP MESSAGE-----

          hQEMAw2B674HRhwSAQgAhTrN8NizwUv/VunVrqa4/X8t6EUulrnhKcSeb8sZS4th
          W1Qz3K2NjL4lkUHCQHKZVx/VoZY7zsddBIFvvoGGfj8+2wjkEDwFmFjGE4DEsS74
          ZLRFIFJC1iB/O0AiQ+oU745skQkU6OEKxqavmKMrKo3rvJ8ZCXDC470+i2/Hqrp7
          +KWGmaDOO422JaSKRm5D9bQZr9oX7KqnrPG9I1+UbJyQSJdsdtquPWmeIpamEVHb
          VMDNQRjSezZ1yKC4kCWm3YQbBF76qTHzG1VlLF5qOzuGI9VkyvlMaLfMibriqY73
          zBbPzf6Bkp2+Y9qyzuveYMmwS4sEOuZL/PetqisWe9JGAWD/O+slQ2KRu9hNww06
          KMDPJRdyj5bRuBVE4hHkkP23KrYr7SuhW2vpe7O/MvWEJ9uDNegpMLhTWruGngJh
          iFndxegN9w==
          =bAuo
          -----END PGP MESSAGE-----
        bar: this was unencrypted already
        baz: |
          -----BEGIN PGP MESSAGE-----

          hQEMAw2B674HRhwSAQf+Ne+IfsP2IcPDrUWct8sTJrga47jQvlPCmO+7zJjOVcqz
          gLjUKvMajrbI/jorBWxyAbF+5E7WdG9WHHVnuoywsyTB9rbmzuPqYCJCe+ZVyqWf
          9qgJ+oUjcvYIFmH3h7H68ldqbxaAUkAOQbTRHdr253wwaTIC91ZeX0SCj64HfTg7
          Izwk383CRWonEktXJpientApQFSUWNeLUWagEr/YPNFA3vzpPF5/Ia9X8/z/6oO2
          q+D5W5mVsns3i2HHbg2A8Y+pm4TWnH6mTSh/gdxPqssi9qIrzGQ6H1tEoFFOEq1V
          kJBe0izlfudqMq62XswzuRB4CYT5Iqw1c97T+1RqENJCASG0Wz8AGhinTdlU5iQl
          JkLKqBxcBz4L70LYWyHhYwYROJWjHgKAywX5T67ftq0wi8APuZl9olnOkwSK+wrY
          1OZi
          =7epf
          -----END PGP MESSAGE-----
        qux:
          - foo
          - bar
          - |
            -----BEGIN PGP MESSAGE-----

            hQEMAw2B674HRhwSAQgAg1YCmokrweoOI1c9HO0BLamWBaFPTMblOaTo0WJLZoTS
            ksbQ3OJAMkrkn3BnnM/djJc5C7vNs86ZfSJ+pvE8Sp1Rhtuxh25EKMqGOn/SBedI
            gR6N5vGUNiIpG5Tf3DuYAMNFDUqw8uY0MyDJI+ZW3o3xrMUABzTH0ew+Piz85FDA
            YrVgwZfqyL+9OQuu6T66jOIdwQNRX2NPFZqvon8liZUPus5VzD8E5cAL9OPxQ3sF
            f7/zE91YIXUTimrv3L7eCgU1dSxKhhfvA2bEUi+AskMWFXFuETYVrIhFJAKnkFmE
            uZx+O9R9hADW3hM5hWHKH9/CRtb0/cC84I9oCWIQPdI+AaPtICxtsD2N8Q98hhhd
            4M7I0sLZhV+4ZJqzpUsOnSpaGyfh1Zy/1d3ijJi99/l+uVHuvmMllsNmgR+ZTj0=
            =LrCQ
            -----END PGP MESSAGE-----

When the pillar data is compiled, the results will be decrypted:

.. code-block:: bash

    # salt myminion pillar.items
    myminion:
        ----------
        secrets:
            ----------
            vault:
                ----------
                bar:
                    this was unencrypted already
                baz:
                    rosebud
                foo:
                    supersecret
                qux:
                    - foo
                    - bar
                    - baz

Salt must be told what portions of the pillar data to decrypt. This is done
using the :conf_master:`decrypt_pillar` config option:

.. code-block:: yaml

    decrypt_pillar:
      - 'secrets:vault': gpg

The notation used to specify the pillar item(s) to be decrypted is the same as
the one used in :py:func:`pillar.get <salt.modules.pillar.get>` function.

If a different delimiter is needed, it can be specified using the
:conf_master:`decrypt_pillar_delimiter` config option:

.. code-block:: yaml

    decrypt_pillar:
      - 'secrets|vault': gpg

    decrypt_pillar_delimiter: '|'

The name of the renderer used to decrypt a given pillar item can be omitted,
and if so it will fall back to the value specified by the
:conf_master:`decrypt_pillar_default` config option, which defaults to ``gpg``.
So, the first example above could be rewritten as:

.. code-block:: yaml

    decrypt_pillar:
      - 'secrets:vault'

Encrypted Pillar Data on the CLI
--------------------------------

.. versionadded:: 2016.3.0

The following functions support passing pillar data on the CLI via the
``pillar`` argument:

- :py:func:`pillar.items <salt.modules.pillar.items>`
- :py:func:`state.apply <salt.modules.state.apply_>`
- :py:func:`state.highstate <salt.modules.state.highstate>`
- :py:func:`state.sls <salt.modules.state.sls>`

Triggerring decryption of this CLI pillar data can be done in one of two ways:

1. Using the ``pillar_enc`` argument:

   .. code-block:: bash

       # salt myminion pillar.items pillar_enc=gpg pillar='{foo: "-----BEGIN PGP MESSAGE-----\n\nhQEMAw2B674HRhwSAQf+OvPqEdDoA2fk15I5dYUTDoj1yf/pVolAma6iU4v8Zixn\nRDgWsaAnFz99FEiFACsAGDEFdZaVOxG80T0Lj+PnW4pVy0OXmXHnY2KjV9zx8FLS\nQxfvmhRR4t23WSFybozfMm0lsN8r1vfBBjbK+A72l0oxN78d1rybJ6PWNZiXi+aC\nmqIeunIbAKQ21w/OvZHhxH7cnIiGQIHc7N9nQH7ibyoKQzQMSZeilSMGr2abAHun\nmLzscr4wKMb+81Z0/fdBfP6g3bLWMJga3hSzSldU9ovu7KR8rDJI1qOlENj3Wm8C\nwTpDOB33kWIKMqiAjY3JFtb5MCHrafyggwQL7cX1+tI+AbSO6kZpbcDfzetb77LZ\nxc5NWnnGK4pGoqq4MAmZshw98RpecSHKMosto2gtiuWCuo9Zn5cV/FbjZ9CTWrQ=\n=0hO/\n-----END PGP MESSAGE-----"}'

   The newlines in this example are specified using a literal ``\n``. Newlines
   can be replaced with a literal ``\n`` using ``sed``:

   .. code-block:: bash

       $ echo -n bar | gpg --armor --trust-model always --encrypt -r user@domain.tld | sed ':a;N;$!ba;s/\n/\\n/g'

   .. note::
       Using ``pillar_enc`` will perform the decryption minion-side, so for
       this to work it will be necessary to set up the keyring in
       ``/etc/salt/gpgkeys`` on the minion just as one would typically do on
       the master. The easiest way to do this is to first export the keys from
       the master:

       .. code-block:: bash

           # gpg --homedir /etc/salt/gpgkeys --export-secret-key -a user@domain.tld >/tmp/keypair.gpg

       Then, copy the file to the minion, setup the keyring, and import:

       .. code-block:: bash

           # mkdir -p /etc/salt/gpgkeys
           # chmod 0700 /etc/salt/gpgkeys
           # gpg --homedir /etc/salt/gpgkeys --list-keys
           # gpg --homedir /etc/salt/gpgkeys --import --allow-secret-key-import keypair.gpg

       The ``--list-keys`` command is run create a keyring in the newly-created
       directory.

   Pillar data which is decrypted minion-side will still be securely
   transferred to the master, since the data sent between minion and master is
   encrypted with the master's public key.

2. Use the :conf_master:`decrypt_pillar` option. This is less flexible in that
   the pillar key passed on the CLI must be pre-configured on the master, but
   it doesn't require a keyring to be setup on the minion. One other caveat to
   this method is that pillar decryption on the master happens at the end of
   pillar compilation, so if the encrypted pillar data being passed on the CLI
   needs to be referenced by pillar or ext_pillar *during pillar compilation*,
   it *must* be decrypted minion-side.


Adding New Renderers for Decryption
-----------------------------------

Those looking to add new renderers for decryption should look at the :mod:`gpg
<salt.renderers.gpg>` renderer for an example of how to do so. The function
that performs the decryption should be recursive and be able to traverse a
mutable type such as a dictionary, and modify the values in-place.

Once the renderer has been written, :conf_master:`decrypt_pillar_renderers`
should be modified so that Salt allows it to be used for decryption.

If the renderer is being submitted upstream to the Salt project, the renderer
should be added in `salt/renderers/`_. Additionally, the following should be
done:

- Both occurrences of :conf_master:`decrypt_pillar_renderers` in
  `salt/config/__init__.py`_ should be updated to include the name of the new
  renderer so that it is included in the default value for this config option.
- The documentation for the :conf_master:`decrypt_pillar_renderers` config
  option in the `master config file`_ and `minion config file`_ should be
  updated to show the correct new default value.
- The commented example for the :conf_master:`decrypt_pillar_renderers` config
  option in the `master config template`_ should be updated to show the correct
  new default value.

.. _`salt/renderers/`: https://github.com/saltstack/salt/tree/develop/salt/renderers/
.. _`salt/config/__init__.py`: https://github.com/saltstack/salt/tree/develop/salt/config/__init__.py
.. _`master config file`: https://github.com/saltstack/salt/tree/develop/doc/ref/configuration/master.rst
.. _`minion config file`: https://github.com/saltstack/salt/tree/develop/doc/ref/configuration/minion.rst
.. _`master config template`: https://github.com/saltstack/salt/tree/develop/conf/master


Master Config in Pillar
=======================

For convenience the data stored in the master configuration file can be made
available in all minion's pillars. This makes global configuration of services
and systems very easy but may not be desired if sensitive data is stored in the
master configuration. This option is disabled by default.

To enable the master config from being added to the pillar set
:conf_minion:`pillar_opts` to ``True`` in the minion config file:

.. code-block:: yaml

    pillar_opts: True

Minion Config in Pillar
=======================

Minion configuration options can be set on pillars. Any option that you want
to modify, should be in the first level of the pillars, in the same way you set
the options in the config file. For example, to configure the MySQL root
password to be used by MySQL Salt execution module, set the following pillar
variable:

.. code-block:: yaml

    mysql.pass: hardtoguesspassword


Master Provided Pillar Error
============================

By default if there is an error rendering a pillar, the detailed error is
hidden and replaced with:

.. code-block:: bash

    Rendering SLS 'my.sls' failed. Please see master log for details.

The error is protected because it's possible to contain templating data
which would give that minion information it shouldn't know, like a password!

To have the master provide the detailed error that could potentially carry
protected data set ``pillar_safe_render_error`` to ``False``:

.. code-block:: yaml

    pillar_safe_render_error: False

.. toctree::
    ../tutorials/pillar
