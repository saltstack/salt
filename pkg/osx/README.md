===============================
Building Native Packages on OSX
===============================

Salt runs well on the Mac, but does have some limitations.

In this directory you will find scripts and collateral to build an OSX
.pkg-style package that uses a custom-built Python.  This process has
been tested on Mac OSX Lion (10.7) and following.

In addition, because of changes in launchd from version
to version of the OS, a simpler approach is taken for
the launchd plist files.

This approach enables Salt users to potentially
add items to their Salt install via 'pip install' without
interfering with the rest of their system's Python packages.

To build a native package you will need the following installed:

- xCode, or the xCode command line tools
- git

The native package will install package files into /opt/salt.
Configuration files will be installed to /etc, but will have
'.dist' appended to them.

Launchd plists will be placed in /Library/LaunchDaemons.  By default
salt-minion will NOT be enabled or started.

The process has been automated via the ``build.sh`` script
in the directory with this README file.  Checkout the Salt repo from
GitHub, chdir into the base repo directory, and run

    ./build.sh


References:

http://crushbeercrushcode.org/2014/01/using-pkgbuild-and-productbuild-on-os-x-10-7/
http://stackoverflow.com/questions/11487596/making-os-x-installer-packages-like-a-pro-xcode-developer-id-ready-pkg


