Target Selection
----------------

The default matching that Salt utilizes is shell-style globbing around the
minion id. See https://docs.python.org/3/library/fnmatch.html#module-fnmatch.

.. option:: -E, --pcre

    The target expression will be interpreted as a PCRE regular expression
    rather than a shell glob.

.. option:: -L, --list

    The target expression will be interpreted as a comma-delimited list;
    example: server1.foo.bar,server2.foo.bar,example7.quo.qux

.. option:: -G, --grain

    The target expression matches values returned by the Salt grains system on
    the minions. The target expression is in the format of '<grain value>:<glob
    expression>'; example: 'os:Arch*'

    This was changed in version 0.9.8 to accept glob expressions instead of
    regular expression. To use regular expression matching with grains, use
    the --grain-pcre option.

.. option:: --grain-pcre

    The target expression matches values returned by the Salt grains system on
    the minions. The target expression is in the format of '<grain value>:<
    regular expression>'; example: 'os:Arch.*'

.. option:: -N, --nodegroup

    Use a predefined compound target defined in the Salt master configuration
    file.

.. option:: -R, --range

    Instead of using shell globs to evaluate the target, use a range expression
    to identify targets. Range expressions look like %cluster.

    Using the Range option requires that a range server is set up and the
    location of the range server is referenced in the master configuration
    file.
