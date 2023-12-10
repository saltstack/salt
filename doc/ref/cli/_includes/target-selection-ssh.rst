Target Selection
----------------

The default matching that Salt utilizes is shell-style globbing around the
minion id. See https://docs.python.org/3/library/fnmatch.html#module-fnmatch.

.. option:: -E, --pcre

    The target expression will be interpreted as a PCRE regular expression
    rather than a shell glob.
