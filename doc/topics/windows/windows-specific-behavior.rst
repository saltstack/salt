==========================
Windows-specific Behaviour
==========================

Salt is capable of managing Windows systems, however due to various differences
between the operating systems, there are some things you need to keep in mind.

This document will contain any quirks that apply across Salt or generally across
multiple module functions. Any Windows-specific behavior for particular module
functions will be documented in the module function documentation. Therefore
this document should be read in conjunction with the module function
documentation.


Group parameter for files
=========================
Salt was originally written for managing Unix-based systems, and therefore the
file module functions were designed around that security model. Rather than
trying to shoehorn that model on to Windows, Salt ignores these parameters and
makes non-applicable module functions unavailable instead.

One of the commonly ignored parameters is the ``group`` parameter for managing
files. Under Windows, while files do have a 'primary group' property, this is
rarely used.  It generally has no bearing on permissions unless intentionally
configured and is most commonly used to provide Unix compatibility (e.g.
Services For Unix, NFS services).

Because of this, any file module functions that typically require a group, do
not under Windows. Attempts to directly use file module functions that operate
on the group (e.g. ``file.chgrp``) will return a pseudo-value and cause a log
message to appear. No group parameters will be acted on.

If you do want to access and change the 'primary group' property and understand
the implications, use the ``file.get_pgid`` or ``file.get_pgroup`` functions or
the ``pgroup`` parameter on the ``file.chown`` module function.


Dealing with case-insensitive but case-preserving names
=======================================================
Windows is case-insensitive, but however preserves the case of names and it is
this preserved form that is returned from system functions. This causes some
issues with Salt because it assumes case-sensitive names. These issues
generally occur in the state functions and can cause bizarre looking errors.

To avoid such issues, always pretend Windows is case-sensitive and use the right
case for names, e.g. specify ``user=Administrator`` instead of
``user=administrator``.

Follow :issue:`11801` for any changes to this behavior.


Dealing with various username forms
===================================
Salt does not understand the various forms that Windows usernames can come in,
e.g. username, mydomain\\username, username@mydomain.tld can all refer to the
same user. In fact, Salt generally only considers the raw username value, i.e.
the username without the domain or host information.

Using these alternative forms will likely confuse Salt and cause odd errors to
happen. Use only the raw username value in the correct case to avoid problems.

Follow :issue:`11801` for any changes to this behavior.


Specifying the None group
=========================
Each Windows system has built-in _None_ group. This is the default 'primary
group' for files for users not on a domain environment.

Unfortunately, the word _None_ has special meaning in Python - it is a special
value indicating 'nothing', similar to ``null`` or ``nil`` in other languages.

To specify the None group, it must be specified in quotes, e.g.
``./salt '*' file.chpgrp C:\path\to\file "'None'"``.


Symbolic link loops
===================
Under Windows, if any symbolic link loops are detected or if there are too many
levels of symlinks (defaults to 64), an error is always raised.

For some functions, this behavior is different to the behavior on Unix
platforms. In general, avoid symlink loops on either platform.
