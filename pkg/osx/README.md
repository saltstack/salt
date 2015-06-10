===============================
Building Native Packages on OSX
===============================

Salt runs well on the Mac, but does have some limitations.

In this directory you will find scripts and collateral to build an OSX
.pkg-style package that only needs the stock system Python.  This process has
been tested on Mac OSX Lion (10.7) and following. Versions of OSX since
Lion have Python 2.7.

In addition, because of changes in launchd from version
to version of the OS, a simpler approach is taken for
the launchd plist files.

Unlike Salt installs on Linux, all Salt commands are wrapped
in a bash script.  This is because the build process creates
a pseudo-virtualenv as the install directory, and we want to
make sure we have PYTHONPATH set properly before any Salt
command is executed.

If this bothers you, you may consider installing Salt through
MacPorts, Brew, pip, or by hand with 'python setup.py install'.

However, this approach does enable Salt users to potentially
add items to their Salt install via 'pip install' without
interfering with the rest of their system's Python packages.

To build a native package you will need the following installed:

- XCode
- pip (easy_install pip)
- virtualenv (pip install virtualenv)
- git


The native package will install package files into /opt/salt.
Configuration files will be installed to /etc, but will have
'.dist' appended to them.

Launchd plists will be placed in /Library/LaunchDaemons.  By default
salt-minion will be enabled and started.

The process has been automated via the ``build.sh`` script
in the directory with this README file.
