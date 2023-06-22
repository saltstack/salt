# Set up Salt-specific environment variables
#
# Drop this into /etc/profile.d to add the neede /opt paths to your environment
# on login
#

export PATH=$PATH:/opt/bin

# Hard-code the python version (major and minor, i.e. 2.6 or 2.7) here if you
# don't trust the logic below.
#
#pyver=2.6
#

if test -z "$pyver"; then
    # Detect RHEL 5 and Arch, operating systems for which "/usr/bin/env python"
    # refers to a python version <2.6 or >=3.0.
    if test -f /etc/redhat-release; then
        osmajor=`egrep -o '[0-9]+\.[0-9]+' /etc/redhat-release | cut -f1 -d.`
        test "$osmajor" -eq 5 && pyver=2.6
    elif test -f /etc/arch-release; then
        python=python2
    fi

    if test -z "$pyver"; then
        test -z "$python" && python=python
        pyver=`/usr/bin/env $python -V 2>&1 | cut -f2 -d' ' | cut -f1,2 -d.`
    fi
fi

# Only add directories to PYTHONPATH if we were able to determine the python
# version.
test -n "$pyver" && export PYTHONPATH=$PYTHONPATH:/opt/lib/python${pyver}/site-packages:/opt/lib64/python${pyver}/site-packages

# Make MAN pages installed within /opt/share/man accessible
export MANPATH=$MANPATH:/opt/share/man
