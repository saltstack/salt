%global __brp_check_rpaths %{nil}

%bcond_with tests
%bcond_with docs

# Disable build-id symlinks
%define _build_id_links none
%undefine _missing_build_ids_terminate_build
%define __brp_mangle_shebangs /usr/bin/true
%define __brp_python_hardlink /usr/bin/true

# Disable private libraries from showing in provides
%global __to_exclude .*\\.so.*
%global __provides_exclude_from ^.*$
%global __requires_exclude_from ^.*$
%define _source_payload w2.gzdio
%define _binary_payload w2.gzdio
%global _SALT_GROUP salt
%global _SALT_USER salt
%global _SALT_NAME Salt
%global _SALT_HOME /opt/saltstack/salt

# salt-master current user and group
%global _MS_CUR_USER %{_SALT_USER}
%global _MS_CUR_GROUP %{_SALT_GROUP}

# salt-minion current user and group
%global _MN_CUR_USER %{_SALT_USER}
%global _MN_CUR_GROUP %{_SALT_GROUP}

# Disable debugsource template
%define _debugsource_template %{nil}

# Needed for packages built from source.
%define _unpackaged_files_terminate_build 0

# Disable python bytecompile for MANY reasons
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

%define fish_dir %{_datadir}/fish/vendor_functions.d

Name:    salt
Version: 3008.2
Release: 0
Summary: A parallel remote execution system
Group:   System Environment/Daemons
License: ASL 2.0
URL:     https://saltproject.io/

Provides:  salt = %{version}
Obsoletes: salt3 < 3006
Obsoletes: salt3006

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%ifarch %{ix86} x86_64
Requires: dmidecode
%endif

Requires: pciutils
Requires: which
Requires: openssl
Requires: /usr/sbin/usermod
Requires: /usr/sbin/groupadd
Requires: /usr/sbin/useradd

BuildRequires: python3
BuildRequires: python3-pip
BuildRequires: openssl
BuildRequires: git

# rhel is not defined on all rpm based distros.
%if %{?rhel:1}%{!?rhel:0}
%if %{rhel} >= 9
BuildRequires: libxcrypt-compat
%endif
%endif

# Build debuginfo package
%debug_package
%_no_recompute_build_ids 1

%description
Salt is a distributed remote execution system used to execute commands and
query data. It was developed in order to bring the best solutions found in
the world of remote execution together and make them better, faster and more
malleable. Salt accomplishes this via its ability to handle larger loads of
information, and not just dozens, but hundreds or even thousands of individual
servers, handle them quickly and through a simple and manageable interface.


%package    master
Summary:    Management component for salt, a parallel remote execution system
Group:      System Environment/Daemons
Requires:   %{name} = %{version}-%{release}
Provides:   salt-master = %{version}
Obsoletes:  salt3-master < 3006
Obsoletes:  salt3006-master

%description master
The Salt master is the central server to which all minions connect.


%package    minion
Summary:    Client component for Salt, a parallel remote execution system
Group:      System Environment/Daemons
Requires:   %{name} = %{version}-%{release}
Provides:   salt-minion = %{version}
Obsoletes:  salt3-minion < 3006
Obsoletes:  salt3006-minion

%description minion
The Salt minion is the agent component of Salt. It listens for instructions
from the master, runs jobs, and returns results back to the master.


%package    syndic
Summary:    Master-of-master component for Salt, a parallel remote execution system
Group:      System Environment/Daemons
Requires:   %{name}-master = %{version}-%{release}
Provides:   salt-syndic = %{version}
Obsoletes:  salt3-syndic < 3006
Obsoletes:  salt3006-syndic

%description syndic
The Salt syndic is a master daemon which can receive instruction from a
higher-level master, allowing for tiered organization of your Salt
infrastructure.


%package    api
Summary:    REST API for Salt, a parallel remote execution system
Group:      Applications/System
Requires:   %{name}-master = %{version}-%{release}
Provides:   salt-api = %{version}
Obsoletes:  salt3-api < 3006
Obsoletes:  salt3006-api

%description api
salt-api provides a REST interface to the Salt master.


%package    cloud
Summary:    Cloud provisioner for Salt, a parallel remote execution system
Group:      Applications/System
Requires:   %{name}-master = %{version}-%{release}
Provides:   salt-cloud = %{version}
Obsoletes:  salt3-cloud < 3006
Obsoletes:  salt3006-cloud

%description cloud
The salt-cloud tool provisions new cloud VMs, installs salt-minion on them, and
adds them to the master's collection of controllable minions.


%package    ssh
Summary:    Agentless SSH-based version of Salt, a parallel remote execution system
Group:      Applications/System
Requires:   %{name} = %{version}-%{release}
Provides:   salt-ssh = %{version}
Obsoletes:  salt3-ssh < 3006
Obsoletes:  salt3006-ssh

%description ssh
The salt-ssh tool can run remote execution functions and states without the use
of an agent (salt-minion) service.


%build
unset CC
unset CXX
unset CPPFLAGS
unset CXXFLAGS
unset CFLAGS
unset LDFLAGS
unset RUSTFLAGS
rm -rf $RPM_BUILD_DIR
mkdir -p $RPM_BUILD_DIR/build
cd $RPM_BUILD_DIR

%if "%{getenv:SALT_ONEDIR_ARCHIVE}" == ""
  export RELENV_DATA=${HOME:-%{getenv:HOME}}/.local/relenv
  export PIP_CONSTRAINT=%{_salt_src}/requirements/constraints.txt
  export FETCH_RELENV_VERSION=${SALT_RELENV_VERSION}
  python3 -m venv --clear --copies build/venv
  build/venv/bin/python3 -m pip install relenv==${SALT_RELENV_VERSION}
  export FETCH_RELENV_VERSION=${SALT_RELENV_VERSION}
  export PY=$(build/venv/bin/python3 -c 'import sys; sys.stdout.write("{}.{}".format(*sys.version_info)); sys.stdout.flush()')
  build/venv/bin/python3 -m pip install -r %{_salt_src}/requirements/static/ci/py${PY}/tools.lock
  build/venv/bin/relenv fetch --python=${SALT_PYTHON_VERSION}
  build/venv/bin/pip install ppbt
  pushd %{_salt_src}
	$RPM_BUILD_DIR/build/venv/bin/tools pkg build onedir-dependencies --arch ${SALT_PACKAGE_ARCH} --relenv-version=${SALT_RELENV_VERSION} --python-version ${SALT_PYTHON_VERSION} --package-name $RPM_BUILD_DIR/build/salt --platform linux

  # Fix any hardcoded paths to the relenv python binary on any of the scripts installed in
  # the <onedir>/bin directory
  find $RPM_BUILD_DIR/build/salt/bin/ -type f -exec sed -i 's:#!/\(.*\)salt/bin/python3:#!/bin/sh\n"exec" "$(dirname $(readlink -f $0))/python3" "$0" "$@":g' {} \;

  $RPM_BUILD_DIR/build/venv/bin/tools pkg build salt-onedir . --package-name $RPM_BUILD_DIR/build/salt --platform linux
  $RPM_BUILD_DIR/build/venv/bin/tools pkg pre-archive-cleanup --pkg $RPM_BUILD_DIR/build/salt
  popd
  build/venv/bin/python3 -m pip uninstall -y ppbt

  # Generate man pages for source builds
  pushd %{_salt_src}
  export PY=$($RPM_BUILD_DIR/build/venv/bin/python3 -c 'import sys; sys.stdout.write("{}.{}".format(*sys.version_info)); sys.stdout.flush()')
  $RPM_BUILD_DIR/build/venv/bin/python3 -m pip install -r requirements/static/ci/py${PY}/docs.lock
  export LATEST_RELEASE=%{version}
  export SALT_ON_SALTSTACK=1
  make -C doc man SPHINXBUILD=$RPM_BUILD_DIR/build/venv/bin/sphinx-build
  # Copy generated man pages to doc/man
  mkdir -p doc/man
  cp -f doc/_build/man/*.1 doc/_build/man/*.7 doc/man/ 2>/dev/null || true
  popd

  # Generate master config
  sed 's/#user: root/user: salt/g' %{_salt_src}/conf/master > $RPM_BUILD_DIR/build/master

%else
  # The relenv onedir is being provided, all setup up until Salt is installed
  # is expected to be done
  cd build
  tar xf ${SALT_ONEDIR_ARCHIVE}

  # Fix any hardcoded paths to the relenv python binary on any of the scripts installed in the <onedir>/bin directory
  find salt/bin/ -type f -exec sed -i 's:#!/\(.*\)salt/bin/python3:#!/bin/sh\n"exec" "$$(dirname $$(readlink -f $$0))/python3" "$$0" "$$@":g' {} \;

  # Generate master config
  sed 's/#user: root/user: salt/g' %{_salt_src}/conf/master > $RPM_BUILD_DIR/build/master

  cd $RPM_BUILD_DIR
%endif


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/saltstack
cp -R $RPM_BUILD_DIR/build/salt %{buildroot}/opt/saltstack/

# Add some directories
install -d -m 0755 %{buildroot}%{_var}/log/salt
install -d -m 0755 %{buildroot}%{_var}/run/salt
install -d -m 0755 %{buildroot}%{_var}/run/salt/master
install -d -m 0755 %{buildroot}%{_var}/cache/salt
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/master
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/minion
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/master/jobs
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/master/proc
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/master/queues
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/master/roots
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/master/syndics
install -Dd -m 0750 %{buildroot}%{_var}/cache/salt/master/tokens
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/master.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/minion.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/pki
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/pki/master
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_autosign
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_denied
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_pre
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_rejected
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/pki/minion
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/cloud.conf.d
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/cloud.deploy.d
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/cloud.maps.d
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/cloud.profiles.d
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/cloud.providers.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/proxy.d
install -d -m 0755 %{buildroot}%{_bindir}

install -m 0755 %{buildroot}/opt/saltstack/salt/salt %{buildroot}%{_bindir}/salt
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-call %{buildroot}%{_bindir}/salt-call
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-master %{buildroot}%{_bindir}/salt-master
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-minion %{buildroot}%{_bindir}/salt-minion
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-api %{buildroot}%{_bindir}/salt-api
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-cp %{buildroot}%{_bindir}/salt-cp
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-key %{buildroot}%{_bindir}/salt-key
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-run %{buildroot}%{_bindir}/salt-run
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-cloud %{buildroot}%{_bindir}/salt-cloud
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-ssh %{buildroot}%{_bindir}/salt-ssh
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-syndic %{buildroot}%{_bindir}/salt-syndic
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-proxy %{buildroot}%{_bindir}/salt-proxy
install -m 0755 %{buildroot}/opt/saltstack/salt/spm %{buildroot}%{_bindir}/spm
install -m 0755 %{buildroot}/opt/saltstack/salt/salt-pip %{buildroot}%{_bindir}/salt-pip

# Add the config files
install -p -m 0640 %{_salt_src}/conf/minion %{buildroot}%{_sysconfdir}/salt/minion
install -p -m 0640 $RPM_BUILD_DIR/build/master %{buildroot}%{_sysconfdir}/salt/master
install -p -m 0640 %{_salt_src}/conf/cloud %{buildroot}%{_sysconfdir}/salt/cloud
install -p -m 0640 %{_salt_src}/conf/roster %{buildroot}%{_sysconfdir}/salt/roster
install -p -m 0640 %{_salt_src}/conf/proxy %{buildroot}%{_sysconfdir}/salt/proxy

# Add the unit files
mkdir -p %{buildroot}%{_unitdir}
install -p -m 0644 %{_salt_src}/pkg/common/salt-master.service %{buildroot}%{_unitdir}/
install -p -m 0644 %{_salt_src}/pkg/common/salt-minion.service %{buildroot}%{_unitdir}/
install -p -m 0644 %{_salt_src}/pkg/common/salt-api.service %{buildroot}%{_unitdir}/
install -p -m 0644 %{_salt_src}/pkg/common/salt-syndic.service %{buildroot}%{_unitdir}/
install -p -m 0644 %{_salt_src}/pkg/common/salt-proxy@.service %{buildroot}%{_unitdir}/

# Logrotate
#install -p %{SOURCE10} .
mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d/
install -p -m 0644 %{_salt_src}/pkg/common/logrotate/salt-common %{buildroot}%{_sysconfdir}/logrotate.d/salt

# Bash completion
mkdir -p %{buildroot}%{_sysconfdir}/bash_completion.d/
install -p -m 0644 %{_salt_src}/pkg/rpm/salt.bash %{buildroot}%{_sysconfdir}/bash_completion.d/salt.bash

# Fish completion (TBD remove -v)
mkdir -p %{buildroot}%{fish_dir}
install -p -m 0644 %{_salt_src}/pkg/common/fish-completions/*.fish  %{buildroot}%{fish_dir}/

# Man files
mkdir -p %{buildroot}%{_mandir}/man1
mkdir -p %{buildroot}%{_mandir}/man7
install -p -m 0644 %{_salt_src}/doc/man/spm.1 %{buildroot}%{_mandir}/man1/spm.1
install -p -m 0644 %{_salt_src}/doc/man/spm.1 %{buildroot}%{_mandir}/man1/spm.1
install -p -m 0644 %{_salt_src}/doc/man/salt.1 %{buildroot}%{_mandir}/man1/salt.1
install -p -m 0644 %{_salt_src}/doc/man/salt-cp.1 %{buildroot}%{_mandir}/man1/salt-cp.1
install -p -m 0644 %{_salt_src}/doc/man/salt-key.1 %{buildroot}%{_mandir}/man1/salt-key.1
install -p -m 0644 %{_salt_src}/doc/man/salt-master.1 %{buildroot}%{_mandir}/man1/salt-master.1
install -p -m 0644 %{_salt_src}/doc/man/salt-run.1 %{buildroot}%{_mandir}/man1/salt-run.1
install -p -m 0644 %{_salt_src}/doc/man/salt-call.1 %{buildroot}%{_mandir}/man1/salt-call.1
install -p -m 0644 %{_salt_src}/doc/man/salt-minion.1 %{buildroot}%{_mandir}/man1/salt-minion.1
install -p -m 0644 %{_salt_src}/doc/man/salt-proxy.1 %{buildroot}%{_mandir}/man1/salt-proxy.1
install -p -m 0644 %{_salt_src}/doc/man/salt-syndic.1 %{buildroot}%{_mandir}/man1/salt-syndic.1
install -p -m 0644 %{_salt_src}/doc/man/salt-api.1 %{buildroot}%{_mandir}/man1/salt-api.1
install -p -m 0644 %{_salt_src}/doc/man/salt-cloud.1 %{buildroot}%{_mandir}/man1/salt-cloud.1
install -p -m 0644 %{_salt_src}/doc/man/salt-ssh.1 %{buildroot}%{_mandir}/man1/salt-ssh.1


%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%{_sysconfdir}/logrotate.d/salt
%{_sysconfdir}/bash_completion.d/salt.bash
%config(noreplace) %{fish_dir}/salt*.fish
%dir %{_var}/cache/salt
%dir %{_var}/run/salt
%dir %{_var}/log/salt
%doc %{_mandir}/man1/spm.1*
%{_bindir}/spm
%{_bindir}/salt-pip
/opt/saltstack/salt
%dir %{_sysconfdir}/salt
%dir %{_sysconfdir}/salt/pki


%files master
%defattr(-,root,root)
%doc %{_mandir}/man1/salt.1*
%doc %{_mandir}/man1/salt-cp.1*
%doc %{_mandir}/man1/salt-key.1*
%doc %{_mandir}/man1/salt-master.1*
%doc %{_mandir}/man1/salt-run.1*
%{_bindir}/salt
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-master
%{_bindir}/salt-run
%{_unitdir}/salt-master.service
%config(noreplace) %{_sysconfdir}/salt/master
%dir %{_sysconfdir}/salt/master.d
%config(noreplace) %{_sysconfdir}/salt/pki/master
%dir %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/
%dir %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions/
%dir %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_autosign/
%dir %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_denied/
%dir %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_pre/
%dir %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_rejected/
%dir %attr(0750, salt, salt) %{_var}/run/salt/master/
%dir %attr(0750, salt, salt) %{_var}/cache/salt/master/
%dir %attr(0750, salt, salt) %{_var}/cache/salt/master/jobs/
%dir %attr(0750, salt, salt) %{_var}/cache/salt/master/proc/
%dir %attr(0750, salt, salt) %{_var}/cache/salt/master/queues/
%dir %attr(0750, salt, salt) %{_var}/cache/salt/master/roots/
%dir %attr(0750, salt, salt) %{_var}/cache/salt/master/syndics/
%dir %attr(0750, salt, salt) %{_var}/cache/salt/master/tokens/


%files minion
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-call.1*
%doc %{_mandir}/man1/salt-minion.1*
%doc %{_mandir}/man1/salt-proxy.1*
%{_bindir}/salt-minion
%{_bindir}/salt-call
%{_bindir}/salt-proxy
%{_unitdir}/salt-minion.service
%{_unitdir}/salt-proxy@.service
%config(noreplace) %{_sysconfdir}/salt/minion
%config(noreplace) %{_sysconfdir}/salt/proxy
%config(noreplace) %{_sysconfdir}/salt/pki/minion
%dir %{_sysconfdir}/salt/minion.d
%dir %attr(0750, root, root) %{_var}/cache/salt/minion/


%files syndic
%doc %{_mandir}/man1/salt-syndic.1*
%{_bindir}/salt-syndic
%{_unitdir}/salt-syndic.service


%files api
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-api.1*
%{_bindir}/salt-api
%{_unitdir}/salt-api.service


%files cloud
%doc %{_mandir}/man1/salt-cloud.1*
%{_bindir}/salt-cloud
%{_sysconfdir}/salt/cloud.conf.d
%{_sysconfdir}/salt/cloud.deploy.d
%{_sysconfdir}/salt/cloud.maps.d
%{_sysconfdir}/salt/cloud.profiles.d
%{_sysconfdir}/salt/cloud.providers.d
%config(noreplace) %{_sysconfdir}/salt/cloud


%files ssh
%doc %{_mandir}/man1/salt-ssh.1*
%{_bindir}/salt-ssh
%config(noreplace) %{_sysconfdir}/salt/roster


%pre
# Source setup configuration if present so SALT_USER/SALT_GROUP/
# SALT_HOME/SALT_NAME from /etc/sysconfig/salt-minion-setup override
# the rpm-built-in defaults. The shell variables (when set) win over
# the macro-expanded defaults below.
if [ -f /etc/sysconfig/salt-minion-setup ]; then
    . /etc/sysconfig/salt-minion-setup
fi
[ -n "$SALT_USER" ] || SALT_USER=%{_SALT_USER}
[ -n "$SALT_GROUP" ] || SALT_GROUP=%{_SALT_GROUP}
[ -n "$SALT_HOME" ] || SALT_HOME=%{_SALT_HOME}
[ -n "$SALT_NAME" ] || SALT_NAME=%{_SALT_NAME}

# create user to avoid running server as root
# 1. create group if not existing
if ! getent group $SALT_GROUP; then
   groupadd --system $SALT_GROUP 2>/dev/null ||true
fi
# 2. create homedir if not existing
test -d $SALT_HOME || mkdir -p $SALT_HOME
# 3. create user if not existing
#         -g $SALT_GROUP \
if ! getent passwd | grep -q "^$SALT_USER:"; then
  useradd --system \
          --no-create-home \
          -s /sbin/nologin \
          -g $SALT_GROUP \
          $SALT_USER 2>/dev/null || true
fi
# 4. adjust passwd entry
usermod -c "$SALT_NAME" \
        -d $SALT_HOME   \
        -g $SALT_GROUP  \
         $SALT_USER

%pre master
if [ $1 -gt 1 ] ; then
    # Determine the current master user. The configured user in
    # /etc/salt/master (or a drop-in under /etc/salt/master.d) is the
    # authoritative source; only fall back to filesystem ownership if no
    # user is configured. Without this, upgrades reset state directory
    # ownership to whatever happened to own /run/salt/master at upgrade
    # time, which for systemd-managed installs is often root. The old
    # `%%global _MS_CUR_USER ...` lines were dead code: `%%global` is an
    # rpm parse-time directive and the macros referenced were never
    # defined as rpm macros.
    CFG_USER=""
    if [ -f /etc/salt/master ]; then
        CFG_USER=$(grep -E "^[[:space:]]*user:" /etc/salt/master 2>/dev/null \
            | head -1 | cut -d ':' -f 2 | tr -d '[:space:]')
    fi
    if [ -z "$CFG_USER" ] && [ -d /etc/salt/master.d ]; then
        CFG_USER=$(grep -r -h -E "^[[:space:]]*user:" /etc/salt/master.d/ 2>/dev/null \
            | head -1 | cut -d ':' -f 2 | tr -d '[:space:]')
    fi

    if [ -n "$CFG_USER" ]; then
        CUR_USER=$CFG_USER
        CUR_GROUP=$(id -gn "$CFG_USER" 2>/dev/null || echo "$CFG_USER")
    elif [ -d /run/salt/master ]; then
        CUR_USER=$(ls -dl /run/salt/master | cut -d ' ' -f 3)
        CUR_GROUP=$(ls -dl /run/salt/master | cut -d ' ' -f 4)
    fi
fi

%pre syndic
if [ $1 -gt 1 ] ; then
    # Reset permissions to match previous installs - performing upgrade
    _MS_LCUR_USER=$(ls -dl /run/salt/master | cut -d ' ' -f 3)
    _MS_LCUR_GROUP=$(ls -dl /run/salt/master | cut -d ' ' -f 4)
    %global _MS_CUR_USER  %{_MS_LCUR_USER}
    %global _MS_CUR_GROUP %{_MS_LCUR_GROUP}
fi

%pre minion

# Source setup configuration if present
if [ -f /etc/sysconfig/salt-minion-setup ]; then
    . /etc/sysconfig/salt-minion-setup
fi

if [ $1 -gt 1 ] ; then
    # Upgrade: detect and save current ownership.
    #
    # Record whether the unit was active *before* we stop it so the
    # %posttrans scriptlet can bring it back up. ``systemctl try-restart``
    # is a no-op for an inactive unit, so the historical %post/%posttrans
    # try-restart calls cannot recover from the stop below on their own
    # (see issue #69605).
    if /bin/systemctl is-active --quiet salt-minion.service 2>/dev/null; then
        touch /tmp/.salt-minion-upgrade-was-active
    fi
    /bin/systemctl stop salt-minion.service >/dev/null 2>&1 || :

    # Check if minion config specifies a non-root user. The configured
    # user in /etc/salt/minion (or a drop-in under /etc/salt/minion.d)
    # is the authoritative source; filesystem ownership is only used as
    # a fallback when no user is configured. The state transfer to
    # %%post minion happens via the marker file at
    # /tmp/.salt-minion-upgrade-ownership.
    MINION_USER=""
    if [ -f "/etc/salt/minion" ]; then
        MINION_USER=$(grep -E "^[[:space:]]*user:" /etc/salt/minion 2>/dev/null | head -1 | cut -d ':' -f 2 | tr -d '[:space:]')
    fi
    if [ -z "$MINION_USER" ] && [ -d "/etc/salt/minion.d" ]; then
        MINION_USER=$(grep -r -h -E "^[[:space:]]*user:" /etc/salt/minion.d/ 2>/dev/null | head -1 | cut -d ':' -f 2 | tr -d '[:space:]' || true)
    fi

    if [ -n "$MINION_USER" ] && [ "$MINION_USER" != "root" ]; then
        MINION_GROUP=$(id -gn "$MINION_USER" 2>/dev/null || echo "$MINION_USER")
        echo "$MINION_USER:$MINION_GROUP" > /tmp/.salt-minion-upgrade-ownership
    else
        # Fallback to checking multiple directories for ownership
        if [ -d "/run/salt/minion" ]; then
            _MN_LCUR_USER=$(ls -dl /run/salt/minion | cut -d ' ' -f 3)
            _MN_LCUR_GROUP=$(ls -dl /run/salt/minion | cut -d ' ' -f 4)
            if [ "$_MN_LCUR_USER" != "root" ]; then
                echo "$_MN_LCUR_USER:$_MN_LCUR_GROUP" > /tmp/.salt-minion-upgrade-ownership
            fi
        elif [ -d "/etc/salt/pki/minion" ]; then
            _MN_LCUR_USER=$(ls -dl /etc/salt/pki/minion | cut -d ' ' -f 3)
            _MN_LCUR_GROUP=$(ls -dl /etc/salt/pki/minion | cut -d ' ' -f 4)
            if [ "$_MN_LCUR_USER" != "root" ]; then
                echo "$_MN_LCUR_USER:$_MN_LCUR_GROUP" > /tmp/.salt-minion-upgrade-ownership
            fi
        elif [ -d "/var/cache/salt/minion" ]; then
            _MN_LCUR_USER=$(ls -dl /var/cache/salt/minion | cut -d ' ' -f 3)
            _MN_LCUR_GROUP=$(ls -dl /var/cache/salt/minion | cut -d ' ' -f 4)
            if [ "$_MN_LCUR_USER" != "root" ]; then
                echo "$_MN_LCUR_USER:$_MN_LCUR_GROUP" > /tmp/.salt-minion-upgrade-ownership
            fi
        fi
    fi
fi


%pre cloud
if [ $1 -gt 1 ] ; then
    # Reset permissions to match previous installs - performing upgrade
    _MS_LCUR_USER=$(ls -dl /etc/salt/cloud.deploy.d | cut -d ' ' -f 3)
    _MS_LCUR_GROUP=$(ls -dl /etc/salt/cloud.deploy.d | cut -d ' ' -f 4)
    %global _MS_CUR_USER  %{_MS_LCUR_USER}
    %global _MS_CUR_GROUP %{_MS_LCUR_GROUP}
fi

# assumes systemd for RHEL 7 & 8 & 9
# foregoing %systemd_* scriptlets due to RHEL 7/8 vs. RHEL 9 incompatibilities
## - Using hardcoded scriptlet definitions from RHEL 7/8 that are forward-compatible
%preun master
# RHEL 9 is giving warning msg if syndic is not installed, supress it
# %%systemd_preun salt-syndic.service > /dev/null 2>&1
if [ $1 -eq 0 ] ; then
  # Package removal, not upgrade
  /bin/systemctl --no-reload disable salt-syndic.service > /dev/null 2>&1 || :
  /bin/systemctl stop salt-syndic.service > /dev/null 2>&1 || :
fi

%preun syndic
# %%systemd_preun salt-syndic.service
if [ $1 -eq 0 ] ; then
  # Package removal, not upgrade
  /bin/systemctl --no-reload disable salt-syndic.service > /dev/null 2>&1 || :
  /bin/systemctl stop salt-syndic.service > /dev/null 2>&1 || :
fi

%preun minion
# %%systemd_preun salt-minion.service
if [ $1 -eq 0 ] ; then
  # Package removal, not upgrade
  /bin/systemctl --no-reload disable salt-minion.service > /dev/null 2>&1 || :
  /bin/systemctl stop salt-minion.service > /dev/null 2>&1 || :
fi

%preun api
# %%systemd_preun salt-api.service
if [ $1 -eq 0 ] ; then
  # Package removal, not upgrade
  /bin/systemctl --no-reload disable salt-api.service > /dev/null 2>&1 || :
  /bin/systemctl stop salt-api.service > /dev/null 2>&1 || :
fi


%post
ln -s -f /opt/saltstack/salt/spm %{_bindir}/spm
ln -s -f /opt/saltstack/salt/salt-pip %{_bindir}/salt-pip


%post cloud
ln -s -f /opt/saltstack/salt/salt-cloud %{_bindir}/salt-cloud


%post master
ln -s -f /opt/saltstack/salt/salt %{_bindir}/salt
ln -s -f /opt/saltstack/salt/salt-cp %{_bindir}/salt-cp
ln -s -f /opt/saltstack/salt/salt-key %{_bindir}/salt-key
ln -s -f /opt/saltstack/salt/salt-master %{_bindir}/salt-master
ln -s -f /opt/saltstack/salt/salt-run %{_bindir}/salt-run
if [ $1 -lt 2 ]; then
  # install
  # ensure hmac are up to date, master or minion, rest install one or the other
  # key used is from openssl/crypto/fips/fips_standalone_hmac.c openssl 1.1.1k
  if [ $(cat /etc/os-release | grep VERSION_ID | cut -d '=' -f 2 | sed  's/\"//g' | cut -d '.' -f 1) = "8" ]; then
    if [ -e /opt/saltstack/salt/lib/libssl.so.1.1 ]; then
      /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/lib/libssl.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/lib/.libssl.so.1.1.hmac || :
    fi
    if [ -e /opt/saltstack/salt/lib/libcrypto.so.1.1 ]; then
      /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/lib/libcrypto.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/lib/.libcrypto.so.1.1.hmac || :
    fi
  fi
fi
# %%systemd_post salt-master.service
if [ $1 -gt 1 ] ; then
  # Upgrade
  /bin/systemctl try-restart salt-master.service >/dev/null 2>&1 || :
else
  # Initial installation
  /bin/systemctl preset salt-master.service >/dev/null 2>&1 || :
fi

%post syndic
ln -s -f /opt/saltstack/salt/salt-syndic %{_bindir}/salt-syndic
# %%systemd_post salt-syndic.service
if [ $1 -gt 1 ] ; then
  # Upgrade
  /bin/systemctl try-restart salt-syndic.service >/dev/null 2>&1 || :
else
  # Initial installation
  /bin/systemctl preset salt-syndic.service >/dev/null 2>&1 || :
fi

%post minion
# Source setup configuration if present
if [ -f /etc/sysconfig/salt-minion-setup ]; then
    . /etc/sysconfig/salt-minion-setup
fi

ln -s -f /opt/saltstack/salt/salt-minion %{_bindir}/salt-minion
ln -s -f /opt/saltstack/salt/salt-call %{_bindir}/salt-call
ln -s -f /opt/saltstack/salt/salt-proxy %{_bindir}/salt-proxy
if [ $1 -lt 2 ]; then
  # install
  # ensure hmac are up to date, master or minion, rest install one or the other
  # key used is from openssl/crypto/fips/fips_standalone_hmac.c openssl 1.1.1k
  if [ $(cat /etc/os-release | grep VERSION_ID | cut -d '=' -f 2 | sed  's/\"//g' | cut -d '.' -f 1) = "8" ]; then
    if [ -e /opt/saltstack/salt/lib/libssl.so.1.1 ]; then
      /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/lib/libssl.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/lib/.libssl.so.1.1.hmac || :
    fi
    if [ -e /opt/saltstack/salt/lib/libcrypto.so.1.1 ]; then
      /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/lib/libcrypto.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/lib/.libcrypto.so.1.1.hmac || :
    fi
  fi
fi
# %%systemd_post salt-minion.service
if [ $1 -gt 1 ] ; then
  # Upgrade
  # Restore ownership before restarting service
  if [ -f "/tmp/.salt-minion-upgrade-ownership" ]; then
    OWNERSHIP=$(cat /tmp/.salt-minion-upgrade-ownership)
    USER_GROUP=${OWNERSHIP%:*}
    chown $OWNERSHIP /etc/salt
    chown $OWNERSHIP /etc/salt/pki
    chown $OWNERSHIP /var/run/salt
    chown -R $OWNERSHIP /etc/salt/pki/minion
    chown -R $OWNERSHIP /etc/salt/minion.d
    chown -R $OWNERSHIP /var/cache/salt/minion
    chown -R $OWNERSHIP /var/run/salt/minion
    chown $OWNERSHIP /var/log/salt/minion
    # Also restore parent directories that are commonly owned by salt user
    chown $OWNERSHIP /var/log/salt
    chown -R $OWNERSHIP /var/cache/salt

    # Pre-create proc directory to ensure ownership (fixes PermissionError)
    mkdir -p /var/cache/salt/minion/proc
    chown $OWNERSHIP /var/cache/salt/minion/proc
    chmod 750 /var/cache/salt/minion/proc

    # Restore ownership of the main installation directory for salt-pip access
    chown -R $OWNERSHIP /opt/saltstack/salt
    # Also restore ownership of extras directory if it exists. Honor an
    # explicit SALT_EXTRAS_DIR override (from /etc/sysconfig/salt-minion-setup)
    # so packagers can relocate the extras dir; otherwise discover any
    # extras-* directories under the install root.
    if [ -n "$SALT_EXTRAS_DIR" ] && [ -d "$SALT_EXTRAS_DIR" ]; then
        chown -R $OWNERSHIP "$SALT_EXTRAS_DIR"
    else
        # Use find to handle wildcard expansion safely in scriptlet
        find /opt/saltstack/salt -maxdepth 1 -name "extras-*" -exec chown -R $OWNERSHIP {} +
    fi

    # Create marker file to tell %posttrans this was an upgrade
    touch /tmp/.salt-minion-upgrade-ownership.done
  fi
  /bin/systemctl try-restart salt-minion.service >/dev/null 2>&1 || :
else
  # Initial installation
  /bin/systemctl preset salt-minion.service >/dev/null 2>&1 || :
fi

%post ssh
ln -s -f /opt/saltstack/salt/salt-ssh %{_bindir}/salt-ssh

%post api
ln -s -f /opt/saltstack/salt/salt-api %{_bindir}/salt-api
# %%systemd_post salt-api.service
if [ $1 -gt 1 ] ; then
  # Upgrade
  /bin/systemctl try-restart salt-api.service >/dev/null 2>&1 || :
else
  # Initial installation
  /bin/systemctl preset salt-api.service >/dev/null 2>&1 || :
fi


%posttrans
# (Re)generate pycache in posttrans, so we're sure any old libraries have been uninstalled.
find /opt/saltstack/salt/lib -type f -name '*.pyc' -delete
find /opt/saltstack/salt/lib -type d -name __pycache__ -empty -delete
/opt/saltstack/salt/bin/python3 -m compileall -qq /opt/saltstack/salt/lib


%posttrans cloud
# Honor SALT_USER/SALT_GROUP overrides from /etc/sysconfig/salt-minion-setup
# so the chown below matches the user/group that %pre created.
if [ -f /etc/sysconfig/salt-minion-setup ]; then
    . /etc/sysconfig/salt-minion-setup
fi
[ -n "$SALT_USER" ] || SALT_USER=%{_SALT_USER}
[ -n "$SALT_GROUP" ] || SALT_GROUP=%{_SALT_GROUP}
PY_VER=$(/opt/saltstack/salt/bin/python3 -c "import sys; sys.stdout.write('{}.{}'.format(*sys.version_info)); sys.stdout.flush();")
if [ ! -e "/var/log/salt/cloud" ]; then
  touch /var/log/salt/cloud
  chmod 640 /var/log/salt/cloud
fi
if [ $1 -gt 1 ] ; then
    # Upgrade: preserve existing ownership, don't reset to defaults
    :
else
        chown -R $SALT_USER:$SALT_GROUP /etc/salt/cloud.deploy.d /var/log/salt/cloud /opt/saltstack/salt/lib/python${PY_VER}/site-packages/salt/cloud/deploy /opt/saltstack/salt
    fi

    %posttrans master
    # Honor SALT_USER/SALT_GROUP overrides; same rationale as %posttrans cloud.
    if [ -f /etc/sysconfig/salt-minion-setup ]; then
        . /etc/sysconfig/salt-minion-setup
    fi
    [ -n "$SALT_USER" ] || SALT_USER=%{_SALT_USER}
    [ -n "$SALT_GROUP" ] || SALT_GROUP=%{_SALT_GROUP}
    if [ ! -e "/var/log/salt/master" ]; then
      touch /var/log/salt/master
      chmod 640 /var/log/salt/master
    fi
    if [ ! -e "/var/log/salt/key" ]; then
      touch /var/log/salt/key
      chmod 640 /var/log/salt/key
    fi
    if [ $1 -gt 1 ] ; then
        # Upgrade: preserve existing ownership, don't reset to defaults
        :
    else
        chown -R $SALT_USER:$SALT_GROUP /etc/salt/pki/master /etc/salt/master.d /var/log/salt/master /var/log/salt/key /var/cache/salt/master /var/run/salt/master /opt/saltstack/salt
    fi


    %posttrans syndic
    # Honor SALT_USER/SALT_GROUP overrides; same rationale as %posttrans cloud.
    if [ -f /etc/sysconfig/salt-minion-setup ]; then
        . /etc/sysconfig/salt-minion-setup
    fi
    [ -n "$SALT_USER" ] || SALT_USER=%{_SALT_USER}
    [ -n "$SALT_GROUP" ] || SALT_GROUP=%{_SALT_GROUP}
    if [ ! -e "/var/log/salt/syndic" ]; then
      touch /var/log/salt/syndic
      chmod 640 /var/log/salt/syndic
    fi
    if [ $1 -gt 1 ] ; then
        # Upgrade: preserve existing ownership, don't reset to defaults
        :
    else
        chown -R $SALT_USER:$SALT_GROUP /var/log/salt/syndic /opt/saltstack/salt
    fi


    %posttrans api
    # Honor SALT_USER/SALT_GROUP overrides; same rationale as %posttrans cloud.
    if [ -f /etc/sysconfig/salt-minion-setup ]; then
        . /etc/sysconfig/salt-minion-setup
    fi
    [ -n "$SALT_USER" ] || SALT_USER=%{_SALT_USER}
    [ -n "$SALT_GROUP" ] || SALT_GROUP=%{_SALT_GROUP}
    if [ ! -e "/var/log/salt/api" ]; then
      touch /var/log/salt/api
      chmod 640 /var/log/salt/api
    fi
    if [ $1 -gt 1 ] ; then
        # Upgrade: preserve existing ownership, don't reset to defaults
        :
    else
        chown -R $SALT_USER:$SALT_GROUP /var/log/salt/api /opt/saltstack/salt
    fi

%posttrans minion

if [ ! -e "/var/log/salt/minion" ]; then
  touch /var/log/salt/minion
  chmod 640 /var/log/salt/minion
fi
if [ ! -e "/var/log/salt/key" ]; then
  touch /var/log/salt/key
  chmod 640 /var/log/salt/key
fi

# Check for preserved ownership marker (from %pre)
if [ -f "/tmp/.salt-minion-upgrade-ownership" ]; then
    # Upgrade case where we detected previous user
    OWNERSHIP=$(cat /tmp/.salt-minion-upgrade-ownership)

    # Apply ownership restoration
    chown $OWNERSHIP /etc/salt
    chown $OWNERSHIP /etc/salt/pki
    chown $OWNERSHIP /var/run/salt
    chown -R $OWNERSHIP /etc/salt/pki/minion
    chown -R $OWNERSHIP /etc/salt/minion.d
    chown -R $OWNERSHIP /var/cache/salt/minion
    chown -R $OWNERSHIP /var/run/salt/minion
    chown $OWNERSHIP /var/log/salt/minion
    # Also restore parent directories that are commonly owned by salt user
    chown $OWNERSHIP /var/log/salt
    chown -R $OWNERSHIP /var/cache/salt

    # Pre-create proc directory to ensure ownership (fixes PermissionError)
    mkdir -p /var/cache/salt/minion/proc
    chown $OWNERSHIP /var/cache/salt/minion/proc
    chmod 750 /var/cache/salt/minion/proc

    # Restore ownership of the main installation directory for salt-pip access
    chown -R $OWNERSHIP /opt/saltstack/salt

    # Clean up
    rm -f /tmp/.salt-minion-upgrade-ownership
    rm -f /tmp/.salt-minion-upgrade-ownership.done

else
    # Fresh install or upgrade from root

    # Check for configuration file in /etc/sysconfig/salt-minion-setup
    if [ -f /etc/sysconfig/salt-minion-setup ]; then
        . /etc/sysconfig/salt-minion-setup
    fi

    # SALT_MINION_USER is the historical minion-specific knob; SALT_USER
    # is the new generic knob from issue #69402. Either may be set in
    # /etc/sysconfig/salt-minion-setup; the minion-specific knob wins so
    # operators who already used SALT_MINION_USER keep their behavior.
    _MN_USER=${SALT_MINION_USER:-${SALT_USER:-}}
    _MN_GROUP=${SALT_MINION_GROUP:-${SALT_GROUP:-$_MN_USER}}

    # For fresh installs, set ownership based on environment variables or defaults
    if [ -n "$_MN_USER" ] && [ "$_MN_USER" != "root" ]; then
        chown -R $_MN_USER:$_MN_GROUP /etc/salt/pki/minion /etc/salt/minion.d /var/log/salt/minion /var/cache/salt/minion /var/run/salt/minion /var/log/salt /var/cache/salt
        # Ensure the main installation directory is also owned by the salt user for salt-pip
        chown -R $_MN_USER:$_MN_GROUP /opt/saltstack/salt
        # Also chown an explicitly relocated extras dir if set.
        if [ -n "$SALT_EXTRAS_DIR" ] && [ -d "$SALT_EXTRAS_DIR" ]; then
            chown -R $_MN_USER:$_MN_GROUP "$SALT_EXTRAS_DIR"
        fi
    fi
fi

# Restart, or start, the minion service.
#
# ``%pre minion`` unconditionally stops the unit on upgrade so the
# ownership-restoration chown calls above don't race a running minion.
# ``try-restart`` is a no-op for an inactive unit, so on upgrade we
# must use ``start`` (not ``try-restart``) when we detected that the
# unit was previously active. The marker file is dropped in ``%pre
# minion`` only when ``is-active`` was true at the start of the
# upgrade transaction. See issue #69605.
if [ -f /tmp/.salt-minion-upgrade-was-active ]; then
    /bin/systemctl start salt-minion.service >/dev/null 2>&1 || :
    rm -f /tmp/.salt-minion-upgrade-was-active
else
    /bin/systemctl try-restart salt-minion.service >/dev/null 2>&1 || :
fi


%preun
if [ $1 -eq 0 ]; then
  # Uninstall
  find /opt/saltstack/salt -type f -name '*.pyc' -delete
  find /opt/saltstack/salt -type d -name __pycache__ -empty -delete
fi

%postun master
# %%systemd_postun_with_restart salt-master.service
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
  # Package upgrade, not uninstall
  /bin/systemctl try-restart salt-master.service >/dev/null 2>&1 || :
fi
if [ $1 -eq 0 ]; then
  if [ $(cat /etc/os-release | grep VERSION_ID | cut -d '=' -f 2 | sed  's/\"//g' | cut -d '.' -f 1) = "8" ]; then
    if [ -z "$(rpm -qi salt-minion | grep Name | grep salt-minion)" ]; then
      # uninstall and no minion running
      if [ -e  /opt/saltstack/salt/lib/.libssl.so.1.1.hmac ]; then
        /bin/rm -f /opt/saltstack/salt/lib/.libssl.so.1.1.hmac || :
      fi
      if [ -e /opt/saltstack/salt/lib/.libcrypto.so.1.1.hmac ]; then
        /bin/rm -f /opt/saltstack/salt/lib/.libcrypto.so.1.1.hmac || :
      fi
    fi
  fi
fi

%postun syndic
# %%systemd_postun_with_restart salt-syndic.service
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
  # Package upgrade, not uninstall
  /bin/systemctl try-restart salt-syndic.service >/dev/null 2>&1 || :
fi

%postun minion
# %%systemd_postun_with_restart salt-minion.service
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
  # Package upgrade, not uninstall
  /bin/systemctl try-restart salt-minion.service >/dev/null 2>&1 || :
fi
if [ $1 -eq 0 ]; then
  if [ $(cat /etc/os-release | grep VERSION_ID | cut -d '=' -f 2 | sed  's/\"//g' | cut -d '.' -f 1) = "8" ]; then
    if [ -z "$(rpm -qi salt-master | grep Name | grep salt-master)" ]; then
      # uninstall and no master running
      if [ -e /opt/saltstack/salt/lib/.libssl.so.1.1.hmac ]; then
        /bin/rm -f /opt/saltstack/salt/lib/.libssl.so.1.1.hmac || :
      fi
      if [ -e /opt/saltstack/salt/lib/.libcrypto.so.1.1.hmac ]; then
        /bin/rm -f /opt/saltstack/salt/lib/.libcrypto.so.1.1.hmac || :
      fi
    fi
  fi
fi

%postun api
# %%systemd_postun_with_restart salt-api.service
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
  # Package upgrade, not uninstall
  /bin/systemctl try-restart salt-api.service >/dev/null 2>&1 || :
fi

%changelog
* Wed Jul 01 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3008.2

# Removed

- Removed 11 stale `.txt` files under `requirements/static/{pkg,ci}/py*/` that were missed by the `.txt` -> `.lock` migration. Three are true orphans from dropped Python 3.8 support; eight shadowed current `.lock` siblings which are the authoritative artifacts. [#69488](https://github.com/saltstack/salt/issues/69488)

# Changed

- Upgrade the bundled onedir Python from 3.10.20 to 3.11.15 on the 3006.x branch. Python 3.10 reaches end of security support in October 2026, while Salt 3006.x must ship security fixes through July 2027. Users upgrading from a previous 3006.x package will need to reinstall any Salt extensions installed via `salt-pip` because the onedir `extras-3.10` directory is replaced by `extras-3.11`. [#69526](https://github.com/saltstack/salt/issues/69526)

# Fixed

- Fixed ``salt-ssh`` ``TemplateNotFound`` when a managed Jinja template imports from another template (e.g. ``{% from "formula/map.jinja" import x with context %}``). ``SaltCacheLoader`` now prefers ``opts["_caller_cachedir"]`` (the master's cachedir, where the master-side fileclient caches requested files) over ``opts["cachedir"]`` (the thin minion's remote path) for its Jinja search path. Backport of the 3007.x/3008.x fix. [#31531](https://github.com/saltstack/salt/issues/31531)
- Fixed the ``mysql`` returner ignoring the configured ``mysql.user`` from salt-ssh and other contexts where ``__salt__`` lacks ``config.option``. ``get_returner_options`` fell back to ``__opts__`` and looked up bare attribute names in it, so the master's top-level ``user`` opt (the system user salt runs as, typically ``root``) masked the configured database user and the returner connected as the wrong user. The mysql returner now passes a scoped view of ``__opts__`` containing only ``mysql.*`` keys so the lookup cannot collide. [#32567](https://github.com/saltstack/salt/issues/32567)
- Fixed non-deterministic pillar rendering when multiple ``pillar_roots`` environments matched the same minion. ``Pillar.get_tops`` collected saltenvs into a ``set`` and iterated them in hash order, so top-file processing order depended on ``PYTHONHASHSEED`` and varied per ``salt-call`` invocation. An earlier change made ``_get_envs`` return an ordered list, but the caller wrapped the result back into a ``set``. ``get_tops`` now uses an insertion-ordered dict so iteration follows ``pillar_roots`` config order. [#44937](https://github.com/saltstack/salt/issues/44937)
- Documented the supported approaches for relocating Salt's runtime directories when running rootless: `SALT_HOME`/`SALT_EXTRAS_DIR` at install time, `root_dir` for relative relocation, and the per-key (`pki_dir`, `cachedir`, `log_file`, `pidfile`, `sock_dir`) overrides. [#55971](https://github.com/saltstack/salt/issues/55971)
- Rewrote the non-root / unprivileged user configuration page for onedir packaging, consolidating the older overlapping pages and documenting `SALT_USER`/`SALT_HOME`/`SALT_EXTRAS_DIR`, `root_dir` relocation, and systemd drop-ins. [#59955](https://github.com/saltstack/salt/issues/59955)
- Fixed a race in ``tests/pytests/integration/cli/test_salt.py::test_interrupt_on_long_running_job`` that intermittently failed on slow CI hosts (Photon OS 5 Arm64, both tcp(fips) and zeromq(fips)). The test used a fixed ``time.sleep(2)`` before sending ``SIGINT``, but on slow hosts the salt CLI had not yet published its job (``pub_data["jid"]`` was still unset), so the signal handler emitted only ``Exiting gracefully on Ctrl-c`` without a jid and the ``This job's jid is`` assertion failed. The test now waits on the master's ``salt/job/*/new`` event via ``event_listener`` to guarantee the job has been published before interrupting the CLI. [#60963](https://github.com/saltstack/salt/issues/60963)
- Rewrote the FAQ entry on restarting the minion after upgrade for the onedir packaging era. Removed the broken `policy-rc.d`/`prereq` workaround and documented the supported patterns based on `KillMode=process` in the shipped systemd unit. [#61078](https://github.com/saltstack/salt/issues/61078)
- Updated the packaging docs to explain how to install modules' optional Python dependencies into an onedir install via `salt-pip`. [#64160](https://github.com/saltstack/salt/issues/64160)
- Documented `salt-pip` for installing optional Python dependencies into a onedir Salt install, including the extras directory layout, `SALT_EXTRAS_DIR` relocation, and non-root behavior. [#64291](https://github.com/saltstack/salt/issues/64291)
- Fixed the EC2/cloud metadata grain crashing with ``KeyError: 'headers'`` when ``salt.utils.http.query`` returns an error response (4xx/5xx with a body, e.g. when the IMDS rejects a recursive sub-path lookup). Since 3006.3 the tornado backend has populated ``body`` on HTTPError without also populating ``headers``; the grain now treats the missing ``headers`` key as "no Content-Type information" instead of letting the lookup blow up the whole grain load. [#65184](https://github.com/saltstack/salt/issues/65184)
- Updated the non-root user docs for the onedir-era directory layout (`/opt/saltstack/salt`, `extras-3.N`, package-managed `salt` user) and explained how to switch an existing install over to a different account. [#65243](https://github.com/saltstack/salt/issues/65243)
- Expanded the packaging test guide with single-test invocations, environment variables, common failures, and CI parity notes. [#65253](https://github.com/saltstack/salt/issues/65253)
- Fixed master-initiated jobs failing on Python 3.12+ with "There is no current event loop in thread 'Thread-N (_target)'" by installing an asyncio event loop on the SyncWrapper worker thread. [#65702](https://github.com/saltstack/salt/issues/65702)
- Fixed ``TypeError: a coroutine was expected, got None`` (Python 3.10) / ``object NoneType can't be used in 'await' expression`` raised repeatedly by ``salt-api`` and ``salt-master`` from ``salt.transport.tcp.PublishClient.on_recv_handler``. The salt-api ``EventListener._handle_event_socket_recv`` callback was a plain function returning ``None`` and is now an ``async`` coroutine, so the TCP IPC publish client can schedule it via ``asyncio.create_task`` without errors and events are no longer silently dropped. [#66177](https://github.com/saltstack/salt/issues/66177)
- Fixed master 4505 publish port becoming unresponsive under load: TCP `PubServer` now broadcasts to subscribers concurrently so a single slow subscriber no longer stalls the event publisher loop, and the ZeroMQ master PUB socket now enables ZMTP heartbeats so dead subscribers are reaped within seconds instead of waiting for the kernel TCP keepalive. [#66282](https://github.com/saltstack/salt/issues/66282)
- Refreshed the "running as a non-root user" page; replaced outdated 0.9.10-era guidance and added the onedir-aware steps for changing the runtime user. [#66353](https://github.com/saltstack/salt/issues/66353)
- Documented how to install Salt Extensions (`saltext.<name>`) into an onedir install with `salt-pip`, and pointed the developer extensions doc at the install instructions. [#66524](https://github.com/saltstack/salt/issues/66524)
- Fixed ``salt.utils.vmware`` to use the supported ``token``/``tokenType`` arguments instead of the deprecated ``b64token``/``mechanism`` arguments when calling ``pyVim.connect.SmartConnect``. pyvmomi 9 raises an exception when either deprecated argument is truthy, which broke salt-cloud, the ``vsphere`` execution module, and other VMware integrations as soon as pyvmomi was upgraded. [#68211](https://github.com/saltstack/salt/issues/68211)
- Fixed `state.event` (and `salt-run state.event`) crashing with `UnicodeDecodeError`
    when an event payload contains raw binary bytes such as the DER-encoded certificate
    returned by `x509.sign_remote_certificate`. Undecodable bytes are now base64-encoded
    in the JSON output instead of aborting the runner. [#68411](https://github.com/saltstack/salt/issues/68411)
- Fixed ``salt.utils.url.create`` so ``salt://`` URLs built from relative paths round-trip correctly on Python 3.13+, where ``urllib.parse.urlunparse`` no longer emits a ``file:///`` prefix for relative paths. salt-ssh ``file.managed`` ``source: salt://...`` references now resolve as expected on newer-Python targets (e.g. Debian trixie). [#68421](https://github.com/saltstack/salt/issues/68421)
- Fix `set_locale` on Debian 13/14 where systemd-localed is unavailable; fall back to /etc/default/locale update. [#68425](https://github.com/saltstack/salt/issues/68425)
- Fixed a prereq chain bug where a state at the head of a chain (e.g. `state1 -prereq-> state2 -prereq-> state3`) would always run when an intermediate state in the chain always produced changes in test mode (e.g. `test.succeed_with_changes`, `module.run`), even though the tail state of the chain produced no changes. [#68438](https://github.com/saltstack/salt/issues/68438)
- Fixed descriptor leaking in salt.utils.http.query [#68456](https://github.com/saltstack/salt/issues/68456)
- Fixed Debian ``salt-minion`` package failing to upgrade from a non-onedir release. The ``salt-minion.preinst`` script assigned an unused ``PY_VER`` variable by exec'ing ``/opt/saltstack/salt/bin/python3``, which does not exist when upgrading from a pre-onedir Debian package (e.g. ``3006.0+ds-1+240.1``). Under ``set -e`` this aborted the upgrade with ``subprocess returned error exit status 127``. The unused assignment is removed. [#68460](https://github.com/saltstack/salt/issues/68460)
- Fixed master cluster event forwarding when a clustered master has no explicit `id` configured. `apply_master_config` appends `_master` to the auto-detected id, but `cluster_peers` and the on-the-wire `data["peers"]` dict are keyed by the bare names. The shared peer pubkey path written by `MasterKeys` and the lookup in `MasterPubServerChannel.handle_pool_publish` now strip the suffix so peers can decrypt forwarded events instead of failing with `KeyError: '<host>_master'`. [#68462](https://github.com/saltstack/salt/issues/68462)
- Fixed salt-master package upgrades resetting state directory ownership and the debconf `salt-master/user` value when the master was configured to run as a non-root user. [#68577](https://github.com/saltstack/salt/issues/68577)
- Don't insert local paths before standard library paths in LazyLoader, preventing sys.path reordering when loader modules are already importable. [#68755](https://github.com/saltstack/salt/issues/68755)
- Fixed Salt minion package upgrades when the minion is configured to run as a non-root user via ``user:`` in ``/etc/salt/minion`` or ``/etc/salt/minion.d/*.conf``. The Debian preinst now reads the configured user before falling back to filesystem ownership, and the rpm pre-minion scriptlet no longer relies on rpm macro directives inside its shell body to communicate the chosen user to the post-minion scriptlet. [#68793](https://github.com/saltstack/salt/issues/68793)
- Fixed a file descriptor leak in the Salt minion: when the single-master sign-in path in ``Minion.eval_master`` raised any exception other than ``SaltClientError`` (for example ``OSError`` from the underlying transport), or when ``transport: detect`` rejected a candidate transport because it could not authenticate, the ``AsyncPubChannel`` that had been created was not closed, leaking its socket. Minions with unstable network connectivity could exhaust the per-process file descriptor limit. The channel is now always closed on failure via a ``try/finally``. [#68901](https://github.com/saltstack/salt/issues/68901)
- Fix `docker_container.running` destroying the original container on the
    `force=True` / `skip_comparison` path by passing the temp container's dict
    instead of its name to `_replace`. `docker.rename` then failed after
    `docker.rm` had already removed the original, leaving the minion with the
    temp container stranded under its generated name. `_replace` now receives
    `temp_container_name` on both call sites, matching the non-force path. [#68959](https://github.com/saltstack/salt/issues/68959)
- Restore the ``reclass`` ext_pillar adapter (``salt.pillar.reclass_adapter``)
    that was dropped when community extensions were purged from the 3008 tree.
    Existing ``ext_pillar: - reclass:`` master configurations work again on
    3008.x without downgrading. [#69018](https://github.com/saltstack/salt/issues/69018)
- Fixed `salt.utils.cache.ContextCache.cache_context` writing the
    serialized pillar context to disk with whatever mode the process
    umask happened to allow (typically `0o644` on default Linux installs)
    inside a `0o755` parent directory. Pillar context can carry
    credentials (passwords, vault tokens, API keys), so any local user
    could read them; even with the file mode tightened, the directory
    mode let any local user `ls` the cache and learn which modules and
    external-pillar backends were in use. The cache file is now written
    through `tempfile.mkstemp` (creates with `0o600` by default) followed
    by atomic `os.replace`, and the parent `context/` directory is
    created with `stat.S_IRWXU` (`0o700`). [#69069](https://github.com/saltstack/salt/issues/69069)
- Fixed `kernelpkg.upgrade` on Debian 13 (trixie) and other distros that ship a kernelrelease containing characters outside `[\d.-]` (for example `6.12.86+deb13-amd64`). `kernelpkg_linux_apt._kernel_type` now parses such releases instead of raising `AttributeError: 'NoneType' object has no attribute 'group'`. [#69131](https://github.com/saltstack/salt/issues/69131)
- Added a regression test covering the `TypeError: string indices must be integers` crash in `AsyncReqChannel.crypted_transfer_decode_dictentry` when the master returns a bare-string error payload for a pillar request. The crash itself was already fixed on master by the layered `isinstance(ret, dict)` guards in `salt/channel/client.py`; the test pins that behavior. [#69228](https://github.com/saltstack/salt/issues/69228)
- Fix PAM authentication always returning 401 on relenv/onedir installs by preferring `sys.executable` over `/usr/bin/python3` when launching the PAM helper subprocess. [#69303](https://github.com/saltstack/salt/issues/69303)
- Fixed auth tokens being deleted from the `localfs` cache driver within one master `loop_interval` (default 60s) of being minted: `Cache.clean_expired`'s fallback path now consults the cache-level `_expires` envelope instead of file mtime, and `LoadAuth.mk_token` passes a relative duration to `Cache.store(expires=...)` rather than an absolute epoch. [#69307](https://github.com/saltstack/salt/issues/69307)
- Fixed `salt -b` (sync batch mode) failing with `SaltClientError: Some exception handling minion payload` when the salt-master runs as a non-root user (e.g. `salt`).  The sync CLI batch driver had been writing batch-state persistence files (`.batch.p`, `batch_active.p`) under the master's `cachedir` from the CLI process — pre-creating the JID directory with root ownership and tripping a `PermissionError` in `local_cache.prep_jid` on the master.

    The sync CLI driver no longer writes anything under the master's `cachedir` itself.  Instead it ships every state transition to the master-side `BatchManager` as `salt/batch/<jid>/{new,progress,complete,halted}` events; the manager — already running as the master daemon's user — persists `.batch.p` and maintains the active-batch index on the CLI's behalf.  `salt-run batch.status <jid>`, `salt-run batch.list_active`, and `salt-run batch.stop <jid>` now work for sync batches in the same deployment shape (non-root master, root CLI) where the original feature was broken.  Event-bus failures degrade gracefully: the batch still completes, just without visibility from the runner commands. [#69418](https://github.com/saltstack/salt/issues/69418)
- Added a new opt-in `auth_retries` minion option that caps the `AsyncAuth._authenticate()` outer retry loop, so a minion that keeps getting `retry` responses from `sign_in()` can bail out with `SaltClientError` instead of looping silently forever. The default is `0` (unlimited), which preserves the existing 3006.x LTS behavior on upgrade; operators who want the new safety cap set `auth_retries` explicitly to a positive integer. [#69442](https://github.com/saltstack/salt/issues/69442)
- Fixed Photon OS Arm64 FIPS CI by re-enabling the OpenSSL default provider after installing openssl-fips-provider, working around the disabled-default-provider bug in `openssl-fips-provider <= 3.1.2-3.ph5` on the lagging Photon aarch64 mirror. [#69448](https://github.com/saltstack/salt/issues/69448)
- Fixed `AESFuncs._register_resources` to fire a `minion_data_cache_events` notification on the master event bus when resource grains are written to the cache, mirroring the existing notification fired by `_pillar` for ordinary minion grains. [#69451](https://github.com/saltstack/salt/issues/69451)
- Fixed the towncrier changelog template splitting every multi-line fragment into separate top-level bullets with a duplicate `[#NNNN]` link on each. Multi-line fragments now render as a single bullet with continuation lines indented under it, and the issue link is appended exactly once. [#69454](https://github.com/saltstack/salt/issues/69454)
- Fixed ``salt.utils.url.parse`` so ``salt:///path`` (three-slash URLs with an empty authority) resolves the same as ``salt://path``. Restores ``cp.get_file salt:///path/to/file`` and similar fileclient calls that previously failed because the surplus leading slash was rejected by the master fileserver's absolute-path guard. [#69472](https://github.com/saltstack/salt/issues/69472)
- Fixed ``saltutil.runner``/``saltutil.wheel`` failing git-backed master functions (e.g. ``git_pillar.update``) with ``failed to stat '/root/.gitconfig'`` when the master runs as a non-root user. Dropping to the master user with ``chugid`` left ``HOME``/``USER``/``LOGNAME`` pointing at the invoking (root) user; these are now aligned with the runas user, and pygit2's cached global-config search path is refreshed. [#69569](https://github.com/saltstack/salt/issues/69569)
- Stopped logging a spurious ``random_master is True but there is only one master specified. Ignoring.`` warning once per master at startup for an all-hot multi-master minion. The warning now fires only for a genuinely single-master configuration. [#69571](https://github.com/saltstack/salt/issues/69571)
- Fix OpenNebula salt-cloud documentation to clarify that VM attributes (memory, cpu, vcpu, etc.) must be specified in the profile configuration, not as command-line arguments to ``salt-cloud -p``. [#69573](https://github.com/saltstack/salt/issues/69573)
- Removed bundled MD5/SHA-1 references that tripped FIPS-compliance scanners against the Salt onedir. The cryptography sdist's top-level ``docs/`` directory (which contains Java/Rust test-vector sources naming weak algorithms, e.g. ``VerifyRSAOAEPSHA2.java``) is now pruned from the onedir during ``pre-archive-cleanup``, and the unused ``__fetch_verify`` helper in the vendored ``bootstrap-salt.sh`` now uses ``sha256sum`` instead of ``md5sum``. [#69575](https://github.com/saltstack/salt/issues/69575)
- Replace deprecated `asyncio.iscoroutinefunction` with `inspect.iscoroutinefunction` in `salt/utils/event.py` and `salt/cluster/consensus/raft/scheduler.py` to avoid DeprecationWarning on Python 3.12+ (slated for removal in Python 3.16). [#69580](https://github.com/saltstack/salt/issues/69580)
- Fixed ``salt-run manage.status``/``manage.up``/``manage.down`` reporting every targeted minion as up because synthesized ``no_return`` rows from ``LocalClient.get_cli_event_returns`` were being counted as successful returns. [#69582](https://github.com/saltstack/salt/issues/69582)
- Fixed `salt.utils.atomicfile.atomic_open` to fsync the temp file before the atomic rename so a crash after the rename cannot expose a truncated or partial file. [#69583](https://github.com/saltstack/salt/issues/69583)
- Fixed RPM upgrades leaving a previously-running ``salt-minion`` service stopped. The ``%pre minion`` scriptlet stops the unit so the ownership-restoration chowns don't race a live minion, but the ``%post`` / ``%posttrans`` scriptlets only called ``systemctl try-restart`` - a no-op for an inactive unit. The scriptlets now record the pre-upgrade active state and start the unit unconditionally in ``%posttrans`` when the minion was running at the start of the upgrade transaction. [#69605](https://github.com/saltstack/salt/issues/69605)
- * Relenv 0.22.16
      - 0.22.15: apply cpython#104135 workaround to bundled ssl.py on Windows
      - 0.22.15: send relenv runtime debug/warning output to stderr (unblocks
        maturin/pyo3 subprocess consumers)
      - 0.22.16: pin libffi to cpython-bin-deps on Windows [#69612](https://github.com/saltstack/salt/issues/69612)
- Restore Rocky Linux 9 ``unit zeromq 4`` CI green after the 3006.x→3007.x merge-forward pulled in 3006.x-only regression tests that don't fit the 3007.x runtime APIs. Adapt the ``test_verify_master_*``, ``test_authenticate_*_69442``, ``test_maintenance_duration``, ``test_minion_manager_stop_unblocks_resolve_dns_69466``, and ``test_event_unpack_with_SaltDeserializationError`` tests to the 3007.x ``crypt.write_keys()`` / ``MasterKeys.gen_signature`` / ``io_loop.create_task`` / ``LoadAuth`` init / debug-log-on-skip contracts; skip the ``test_gen_signature_signs_clean_key`` variants because the 3007.x cache-refactored ``MasterKeys.gen_signature`` signs ``pub.public_bytes()`` and cannot exhibit the #68930 whitespace-drift bug. [#69624](https://github.com/saltstack/salt/issues/69624)

# Added

- Added `tools/audit_doc_links.py` and a weekly `doc-linkcheck` workflow that wrap Sphinx linkcheck, strip the catch-all ignore, and emit a CSV report so external URL regressions in the docs can be tracked without gating PR CI. [#60720](https://github.com/saltstack/salt/issues/60720)
- added conditional X functionality to linux_acl [#62852](https://github.com/saltstack/salt/issues/62852)
- Added ``unmask`` parameter to ``pillar.ls``, ``pillar.raw``, ``pillar.ext``, ``pillar.keys``, and ``pillar.obfuscate`` for API consistency with ``pillar.get`` / ``pillar.items`` / ``pillar.item`` / ``pillar.data``. Default masking behavior is unchanged. [#69453](https://github.com/saltstack/salt/issues/69453)
- Documented the ``gitcli`` GitFS provider (added in 3008.0) which shells out to the system ``git`` binary, auto-detected after ``pygit2`` and ``gitpython`` and used as a silent fallback when neither Python library is installed. Documented the ``cluster_isolated_filesystem`` master option (added in 3008.0) which lets master clusters run without a shared filesystem; keys, denied keys, ``file_roots`` and ``pillar_roots`` are sync'd in-band over the cluster transport, with ``keys.cache_driver: mmap_key`` as the recommended companion. [#69494](https://github.com/saltstack/salt/issues/69494)


* Wed Jun 24 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.26

# Removed

- Removed the unmaintained `linode-python` package dependency to stop SyntaxWarnings during install for retired Linode API v3. [#68992](https://github.com/saltstack/salt/issues/68992)

# Changed

- Changed `salt.returners.redis_return` to enumerate the Redis keyspace
    with `SCAN` instead of the blocking `KEYS pattern` command in both
    `get_jids` and `clean_old_jobs`. `KEYS` walks the entire keyspace
    synchronously and stalls the Redis server for the duration; on a
    master with hundreds of thousands of jobs this can block all clients
    of that Redis instance for seconds. `SCAN` is incremental and
    non-blocking. Order of returned keys is no longer guaranteed (the
    returner does not rely on order); operators with custom scripts that
    read `ret:*` or `load:*` directly may see them in a different order. [#69037](https://github.com/saltstack/salt/issues/69037)

# Fixed

- Fixed multi-line scalar variables loaded via `import_yaml` (or `load_yaml`) being rendered as literal `\n` instead of actual newlines when the loaded data is interpolated into a YAML state file (e.g. `- context: {{ data }}`). `PrintableDict.__str__`/`__repr__` now emit string values containing newlines as YAML-safe double-quoted scalars rather than Python `repr()` so they round-trip correctly through the subsequent YAML render pass. [#30690](https://github.com/saltstack/salt/issues/30690)
- Handle requisites correctly for empty SLS files [#30971](https://github.com/saltstack/salt/issues/30971)
- Fixed ``win_pkg`` functions ignoring the ``saltenv`` setting in minion configuration. All public functions (``refresh_db``, ``genrepo``, ``install``, ``remove``, ``list_pkgs``, ``latest_version``, ``upgrade_available``, ``list_upgrades``, ``list_available``, ``version``, ``get_repo_data``, ``get_package_info``) now fall back to ``__opts__["saltenv"]`` when ``saltenv`` is not passed explicitly, instead of always defaulting to ``base``. [#38551](https://github.com/saltstack/salt/issues/38551)
- ``dpkg_lowpkg`` no longer reads ``/var/lib/dpkg/available`` or ``/var/lib/dpkg/info/<package>.list`` directly. It now uses ``dpkg-query`` exclusively, addressing the lintian ``uses-dpkg-database-directly`` warning reported in #52605. ``lowpkg.info`` derives the package install time from dpkg's ``${db-fsys:Last-Modified}`` field instead of the ``.list`` file mtime. [#52605](https://github.com/saltstack/salt/issues/52605)
- Added ``encoding`` parameter to ``file.replace`` execution module and state to support UTF-16, UTF-32, and other multi-byte encoded files that would otherwise be incorrectly treated as binary. [#52793](https://github.com/saltstack/salt/issues/52793)
- Fixed `postgres._find_pg_binary` ignoring `postgres.bins_dir` when a `psql` binary is also present on the system PATH, ensuring the configured `bins_dir` is always preferred over the system PATH. [#53190](https://github.com/saltstack/salt/issues/53190)
- Percent-encode the user and password when adding HTTP basic auth to a URL so reserved characters no longer corrupt the result [#55561](https://github.com/saltstack/salt/issues/55561)
- Fixed a ``SaltCacheError`` ("maximum recursion depth exceeded") raised by the
    etcd data cache when listing an empty folder, which etcd reports as a child of
    itself. The directory walk now stops at the self-referential entry instead of
    recursing indefinitely. [#57377](https://github.com/saltstack/salt/issues/57377)
- Fixed `timezone.system` state always returning `result=False` with "Failed to set UTC to True" on Windows. The hardware clock on Windows is always localtime and cannot be changed, so the UTC/hwclock block is now skipped entirely on Windows. [#57754](https://github.com/saltstack/salt/issues/57754)
- Fixed `archive.tar` placing the `-C <dest>` option after the source/member operands, where tar ignores it. The directory-change option is now emitted before the operands so it takes effect in both create and extract modes. [#57847](https://github.com/saltstack/salt/issues/57847)
- Fixed `OSError: The operation completed successfully` raised by `CreateProcessWithTokenW` on Windows when the underlying advapi32 call fails. The error code is now read from `ctypes.get_last_error()` (the ctypes-saved slot) instead of `win32api.GetLastError()` (the live Windows slot, which may be reset to 0 before it is read). [#57848](https://github.com/saltstack/salt/issues/57848)
- Improved documentation for the `runas` and `password` parameters in `cmd.run`, `cmd.script`, and all `salt.modules.cmdmod` execution functions on Windows. The docs now accurately describe when a password is required: only when the salt-minion is **not** running as SYSTEM or as an elevated Administrator. Removed the inaccurate claim that the target user account must be in the Administrators group. Also changed `cmd.script` to log a warning instead of hard-failing when `runas` is used without a password on Windows, since a password is not always required. [#57951](https://github.com/saltstack/salt/issues/57951)
- Fixed ``pkg.group_installed``/``pkg.group_info`` failing to expand a dnf environment group whose member groups have multi-word names (e.g. ``Group '@Common NetworkManager submodules' not found`` when installing ``Workstation`` on RHEL/AlmaLinux 8, 9 and 10). The member group is now resolved by its bare name when the ``@``-prefixed lookup fails. This affects dnf4 only; dnf5 group handling is unchanged. [#60276](https://github.com/saltstack/salt/issues/60276)
- Fix `tls.create_csr` log message path to use `os.path.join` instead of f-string interpolation so paths render correctly when csr_path has a trailing slash. [#60877](https://github.com/saltstack/salt/issues/60877)
- Fixed the LDAP eauth group-membership lookup re-binding the user on every job
    payload when ``auth.ldap.freeipa`` is enabled. The user is now only re-bound on
    the first payload of a job, matching the standard LDAP code path, so single-use
    2FA credentials (such as a FreeIPA OTP) are no longer consumed more than once. [#61974](https://github.com/saltstack/salt/issues/61974)
- Fixed `SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC` errors in the VMware cloud driver by reconnecting when a cached vCenter service instance is found to be stale or corrupted (for example when inherited across a fork by salt-cloud's parallel provider queries). [#61983](https://github.com/saltstack/salt/issues/61983)
- Fix metadata grain so EC2 ``user-data`` is returned verbatim instead of being mangled by the ``=`` line-splitter, which previously corrupted any user-data payload containing ``=`` (e.g. cloud-init ``#cloud-config`` blocks). [#62061](https://github.com/saltstack/salt/issues/62061)
- Fixed LGPO ``get_policy_info`` incorrectly returning a "multiple policies" error when duplicate ADMX policy definitions (e.g. ``TerminalServer.admx`` and ``TerminalServer-Server.admx``) resolve to the same full path. [#62732](https://github.com/saltstack/salt/issues/62732)
- Re-enable test_interrupt_on_long_running_job by removing the initial-onedir-rollout skip marker. [#63627](https://github.com/saltstack/salt/issues/63627)
- Fix missing `dns_plugin_propagate_seconds` arg in acme state/module so DNS propagation timeout is actually forwarded to certbot. [#63700](https://github.com/saltstack/salt/issues/63700)
- Improve PAM eauth diagnostics when ``salt-master`` runs as a non-root user. Previously, ``salt-master``/``salt-api`` running as the ``salt`` user (the 3006.x packaging default) silently failed every PAM authentication with only ``Pam auth failed for <user>:`` in the log; the cause is that the helper subprocess inherits the master's uid and PAM's ``unix_chkpwd`` refuses to validate other users without ``/etc/shadow`` access. The master now emits a one-shot CRITICAL log entry that names the cause and the two standard remediations (run as ``root``, or add the master user to the ``shadow`` group on Debian-derived distributions), and the module documentation describes the constraint. [#64275](https://github.com/saltstack/salt/issues/64275)
- Fixed incorrect minion presence events being sent out on hourly ``Maintenance`` process restarts [#64505](https://github.com/saltstack/salt/issues/64505)
- Catch StrictUndefined in salt jinja custom filters. [#64915](https://github.com/saltstack/salt/issues/64915)
- Stopped logging the misleading "An extra return was detected from minion ... this could be a replay attack" ERROR for benign duplicate returns (also fixes #65516). The local_cache returner now compares a duplicate return to the cached one and logs at DEBUG when the payloads match (the common retry-after-timeout or syndic re-forward case) and at WARNING -- without the "replay attack" wording -- when the payloads differ. [#65301](https://github.com/saltstack/salt/issues/65301)
- Fixed non-root salt CLI access when ``publisher_acl`` or ``external_auth`` is configured. Since 3006.3 the master defaults to running as the ``salt`` user, which left ``sock_dir`` and ``cachedir`` mode ``0o750`` and blocked authorised non-root users from traversing into them to reach ``master_event_pub.ipc`` / ``publish_pull.ipc`` and their per-user ``.<user>_key``. The master now adds the world-execute bit to those two directories when ACLs are configured, without exposing directory listings. [#65317](https://github.com/saltstack/salt/issues/65317)
- Fixed ``salt.ext.tornado.netutil`` import on Python 3.12+ where ``ssl.match_hostname`` was removed and the unmaintained ``backports.ssl_match_hostname`` package is unavailable, which previously broke any Salt master-initiated job (e.g. ``test.ping``, ``state.apply``) on Fedora 39+/Ubuntu 24.04 masters. [#65360](https://github.com/saltstack/salt/issues/65360)
- See #65301 -- the same fix to ``salt/returners/local_cache.py`` quiets the spurious "extra return ... replay attack" ERROR that appeared in multimaster and master-of-masters/syndic setups when the same return arrived more than once. [#65516](https://github.com/saltstack/salt/issues/65516)
- Fix deadlock in parallel `cmd.script` states when the script is served by the master.

    Same fork-inherited ZeroMQ socket race as the `file.managed` fix: a
    `cmd.script` state with `parallel: True` downloads the script via
    `cp.cache_file` in a forked child that inherited the parent's ZeroMQ
    REQ socket, deadlocking the asyncio loop at ~100% CPU. Resolved by the
    same `os.register_at_fork` handlers that drop inherited channel/socket
    references in forked children. [#65709](https://github.com/saltstack/salt/issues/65709)
- Fixed pip.uninstall rejecting the extra_args keyword argument, matching the behavior of pip.install. [#65870](https://github.com/saltstack/salt/issues/65870)
- Fixed salt-ssh failing to fetch ``gitfs_remotes``. ``salt.config.master_config``
    sets ``__fs_update = True`` to suppress fileserver refreshes done by ``FSChan``
    (the master daemon's maintenance thread handles them). salt-ssh inherits the
    master config but has no maintenance thread, so its ``FSClient`` never refreshed
    the fileserver backends and wrappers such as ``cp.list_states`` saw no gitfs
    content until the user ran ``salt-run fileserver.update`` or manually
    ``git fetch``ed the cached repos. ``salt.client.ssh.SSH.__init__`` now removes
    the suppression flag before instantiating ``FSClient`` so gitfs is refreshed
    once at startup. [#66148](https://github.com/saltstack/salt/issues/66148)
- Fixed ``salt/version.py`` reporting the wrong major version on the 3006.x branch when built from a checkout that has no ``salt/_version.txt`` and no usable ``.git`` directory. ``SaltVersionsInfo.current_release()`` now returns the branch's own codename (``Sulfur``) instead of the next un-released codename in the table, so source builds and other tooling no longer leak ``3007.0`` into the reported version. [#67061](https://github.com/saltstack/salt/issues/67061)
- Fixed ``saltutil.runner`` and ``saltutil.wheel`` running master-side functions
    as the minion's user (typically ``root``) instead of the master's configured
    user (the packaged default since 3006 is ``salt``). Running as the wrong user
    left root-owned files in, and tripped git's ``safe.directory`` check on, the
    salt-owned master cache -- breaking, for example, ``git_pillar.update`` invoked
    via ``saltutil.runner``. These functions now drop to the master's configured
    user before executing when invoked from a more-privileged process. [#67716](https://github.com/saltstack/salt/issues/67716)
- Fixed `LocalClient.cmd_subset` raising `TypeError: argument of type 'bool' is not iterable` when one or more targeted minions failed to respond to the `sys.list_functions` probe. Failed minions are now skipped during subset selection. [#68103](https://github.com/saltstack/salt/issues/68103)
- Fixed ``slack_bolt`` engine crashing with ``UnboundLocalError`` when a Slack workflow or other bot posts a message to a monitored channel. Bot messages (``subtype: bot_message``) carry ``bot_id`` and ``username`` instead of a ``user`` field, and these are now used as fallbacks so the engine continues running. [#68105](https://github.com/saltstack/salt/issues/68105)
- Fixed `user.present` to not fail with `result: False` in test mode when a referenced group does not yet exist; the state now reports the pending changes so users can preview states that depend on groups created by a `group.present` requisite in the same run. [#68110](https://github.com/saltstack/salt/issues/68110)
- Fixed ``salt-minion`` and ``salt-proxy`` leaving a privileged (root) keepalive supervisor process at the head of an otherwise unprivileged minion process tree when ``user`` is set to a non-root account. The supervisor now drops privileges to the configured user once the keepalive child has been spawned. [#68115](https://github.com/saltstack/salt/issues/68115)
- Fixed ``ValueError: Formatting field not found in record: 'colorlevel'`` errors when ``log_fmt_console`` uses custom color attributes such as ``%(colorlevel)s`` or ``%(colormsg)s``. ``SaltLogRecord`` now always provides the ``color*`` attributes (uncolored by default) so that log records buffered by the temporary deferred stream handler can be formatted by a colorized console formatter once it is installed. [#68129](https://github.com/saltstack/salt/issues/68129)
- Fixed ``salt-call`` silently ignoring ``--file-root``, ``--pillar-root``, and ``--states-dir`` when ``--local`` was not passed. These overrides only affect the local minion config and are clobbered by the master's values via the remote file client, so ``salt-call`` now emits a warning explaining that ``--local`` is required for the override to take effect. [#68137](https://github.com/saltstack/salt/issues/68137)
- Fixed event signature verification failing under ``minion_sign_messages``. The minion was signing the return load before ``salt.channel.client.AsyncReqChannel._package_load`` attached transport metadata (``nonce``, ``ts``, ``tok``, ``id``), so the bytes the master re-serialized to verify did not match what was signed and every signed return was dropped. Signing is now performed inside ``_package_load`` after the metadata is attached, against the same bytes the master verifies. [#68181](https://github.com/saltstack/salt/issues/68181)
- Fixed ``pkgrepo.managed`` honouring ``clean_file: True`` when the desired
    repo line is already present in the managed file alongside unrelated stale
    lines. Previously the state returned "already configured" and silently
    skipped both the file truncation and the re-write, leaving the stale
    entries (for example an obsolete ``bullseye-backports`` line in a file
    managed for ``bookworm-backports``) in place. The clean + reconfigure
    path now runs whenever the managed file contains any non-comment,
    non-blank content other than the desired repo line; when the file already
    contains only the desired line the state remains idempotent. [#68208](https://github.com/saltstack/salt/issues/68208)
- Fixed ``pkg.group_installed`` reporting failure on RPM-based systems when a package group's default or optional members are not available in any enabled repository. The state now only considers mandatory group members and explicitly requested ``include`` packages when checking for install failures, matching the behavior of ``yum/dnf group install`` (which reports "No match for group package" but still exits 0). [#68210](https://github.com/saltstack/salt/issues/68210)
- Pass ``--disable-pip-version-check`` when ``pip.list``, ``pip.freeze``, ``pip.list_upgrades``, ``pip.upgrade``, and ``pip.list_all_versions`` invoke pip, so these calls no longer hang for ~20s per invocation on airgapped minions while pip tries to reach PyPI for its self-version check. [#68214](https://github.com/saltstack/salt/issues/68214)
- Fixed ``archive.extracted`` failing to enforce ``user``/``group`` ownership on archives whose tar/zip members include no explicit directory entries (e.g. Oracle's GraalVM JDK tarballs). ``archive.list`` now derives the top-level directory from the common prefix of file and link members in addition to dir members, so ownership is applied to the extracted top-level directory in all cases. [#68227](https://github.com/saltstack/salt/issues/68227)
- Fixed deltaproxy sub-proxies returning identical grain data for every controlled minion. ``subproxy_post_master_init`` now re-packs each sub-proxy's freshly loaded per-minion grains into its execution-module, returner, executor and proxy LazyLoaders so ``__grains__`` inside loaded modules reflects that sub-proxy's device instead of the placeholder values captured during the first-pass grains load through the control proxy. [#68248](https://github.com/saltstack/salt/issues/68248)
- Fixed the salt-minion (and salt-api, salt-cloud, salt-master, salt-syndic) Debian postinst scripts hanging or erroring with "Bad file descriptor" when run from a non-interactive Debian preseed late_command chroot, by tearing down the debconf protocol with ``db_stop`` and explicitly closing file descriptor 3 before the auto-generated ``#DEBHELPER#`` section runs. [#68269](https://github.com/saltstack/salt/issues/68269)
- Fixed ``file.managed`` failing with ``WinError 123`` on Windows when caching a remote URL whose path embeds another URL (e.g. an archive.org snapshot of an ``https://...`` resource). The URL-path portion of the ``extrn_files`` cache path is now sanitised the same way the network location already is. [#68273](https://github.com/saltstack/salt/issues/68273)
- Fixed ``logrotate.set`` dropping the second ``endscript`` (and turning
    embedded shell commands into bogus setting keys) when a stanza contained
    multiple script blocks such as both ``prerotate`` and ``postrotate``. Script
    directives are now parsed as opaque multi-line bodies and round-trip with
    their own ``endscript`` terminator each. [#68293](https://github.com/saltstack/salt/issues/68293)
- Fixed the `salt.state` orchestrate state silently reporting only `Run failed on minions: <minion>` when a targeted minion returned `False`, no return at all, or a list of error strings. The orchestrate comment now includes the per-minion failure detail (the minion's actual return value or "did not return a state result") so operators can diagnose `salt-run state.orchestrate` failures without re-running with extra logging. [#68326](https://github.com/saltstack/salt/issues/68326)
- Fixed worker process crash when salt is used outside CLI tools. [#68332](https://github.com/saltstack/salt/issues/68332)
- Fixed ``clean_old_jobs`` in the default local job cache returner to use the jid file's modification time (``st_mtime``) instead of the inode change time (``st_ctime``). A package upgrade's ``chown -R /var/cache/salt/master`` resets ``st_ctime`` on every existing jid file, which previously made the maintenance process treat every pre-upgrade job as freshly created and prevented cleanup until ``keep_jobs_seconds`` had elapsed. On busy masters this exhausted the partition's inodes within a day. [#68351](https://github.com/saltstack/salt/issues/68351)
- Fixed the ``proxmox`` salt-cloud driver raising ``Could not determine an IP address to use`` before the VM was created and started. The IP address is now determined after the VM is running, and the running VM's address reported by Proxmox is used as a fallback when neither a static ``ip_address`` nor ``agent_get_ip`` is configured. [#68353](https://github.com/saltstack/salt/issues/68353)
- Changed ``KillMode`` in the shipped ``salt-minion.service`` systemd unit from ``process`` to ``mixed`` so that ``systemctl stop`` / ``systemctl restart salt-minion`` no longer leaves orphaned ``Minion._thread_return`` worker processes outside the cgroup. SIGTERM is still sent only to the main PID (so the job return scheduled by ``service.restart salt-minion`` from #68183 has time to finish), but any remaining children are reaped with SIGKILL after the main process exits or ``TimeoutStopSec`` elapses. [#68406](https://github.com/saltstack/salt/issues/68406)
- Fixed `task.edit_task` on Windows rejecting `restart_count=999` even though the documented and error-message-stated maximum is 999. The validation now accepts the full 1..999 range. [#68419](https://github.com/saltstack/salt/issues/68419)
- Fixed ``win_task.add_trigger`` so that ``repeat_duration="Indefinitely"`` actually produces an indefinite repetition pattern. Previously the empty string from the internal duration lookup was assigned to ``Repetition.Duration``, which the Windows Task Scheduler treats as "0 seconds" and silently disables repetition. The Duration property is now left at its default for the "Indefinitely" case, which is the documented way to repeat forever. [#68420](https://github.com/saltstack/salt/issues/68420)
- Fixed ``user.setpassword`` on Windows reporting success (``retcode: 0``) when the target user does not exist. The execution module now returns ``False`` and logs an error in that case, so callers and the ``user.present`` state correctly detect the failure instead of swallowing the Win32 "user name could not be found" message as a successful return. [#68428](https://github.com/saltstack/salt/issues/68428)
- Fixed ``user.present`` on Windows so it actually updates a user's password
    when the existing password differs from the one specified in the state.
    Previously the state reported "User is already present and up to date" and
    left the password unchanged. [#68429](https://github.com/saltstack/salt/issues/68429)
- Stop salt-ssh state runs from clobbering the master-side fileclient ``cachedir`` with the on-target ``thin_dir`` cachedir. The state fileserver cache for salt-ssh state runs is now written under the configured master ``cachedir`` (e.g. ``/var/cache/salt/master/``) instead of under the minion's thin_dir path on the master filesystem. [#68458](https://github.com/saltstack/salt/issues/68458)
- Fixed ``pkg.add_repo_key`` and ``pkgrepo.managed`` so APT keyring files that target an ``.asc`` destination keep their ASCII armor instead of being dearmored, matching the apt-secure(8) convention and allowing armored keyfiles that bundle multiple keys to be installed even when the ``gpg`` binary is not available on the minion. [#68464](https://github.com/saltstack/salt/issues/68464)
- Fixed ``jobs.list_jobs search_metadata`` so it matches jobs whose metadata
    was passed as a CLI keyword argument (e.g. ``state.apply metadata={...}``)
    and is therefore carried inside the job's ``Arguments`` rather than at the
    top of the job payload. [#68481](https://github.com/saltstack/salt/issues/68481)
- Fixed `lgpo.set` state reporting "Failed to set the following policies" on subsequent runs of policies with sub-elements (e.g. Storage Sense thresholds). The state compared a user-supplied dict keyed by element id with a current dict keyed by the ADML display name; both forms now normalize to the canonical element id before comparison so the state is idempotent. [#68489](https://github.com/saltstack/salt/issues/68489)
- Fixed minion rejecting the master with "Invalid master key" after restart when the cached `minion_master.pub` differs from the master's payload pub_key only in trailing whitespace. `AsyncAuth.verify_master` now normalizes both sides through `clean_key` before comparing and caches the normalized form on first contact. [#68493](https://github.com/saltstack/salt/issues/68493)
- Fixed ``TypeError: 'NoneType' object is not iterable`` raised from ``AsyncReqMessageClient._send_recv`` when a per-message timeout completes the future before the send/receive coroutine catches a transient transport exception, which aborted the minion's connect loop and prevented it from connecting to the master. [#68506](https://github.com/saltstack/salt/issues/68506)
- Fixed ``docker_network.present`` recreating networks on every run against Docker 29+. Docker 29 added an empty ``IPRange`` field to every IPAM Config entry; ``docker.compare_networks`` now drops empty/None placeholder values before comparing pools, and the state's default-pool short-circuit treats the empty field as absent. [#68518](https://github.com/saltstack/salt/issues/68518)
- Fixed `pkg.installed` verification on x86_64 hosts that mix `x86_64` and `x86_64_v2` packages (e.g. AlmaLinux 10.1). `salt.utils.pkg.rpm.resolve_name` and `salt.modules.yumpkg.normalize_name` now treat `x86_64_v2` as compatible with `x86_64` instead of appending the arch suffix, so installed packages match the names Salt records. [#68540](https://github.com/saltstack/salt/issues/68540)
- Fixed ``mysql_grants.present`` reporting "Failed to execute" when granting ``ALL PRIVILEGES`` on ``*.*`` against MySQL 8.4+, where the server's privilege set drifted from Salt's hard-coded list (``SET_USER_ID`` removed, many dynamic privileges added). ``grant_exists`` now derives the expected privilege set from the connected server's ``SHOW PRIVILEGES`` output instead of a static list. [#68567](https://github.com/saltstack/salt/issues/68567)
- Fixed ``cp.get_template`` raising ``AttributeError: 'NoneType' object has no attribute 'get'`` when the Jinja template uses ``{% from '...' import ... with context %}``. The cp module's loader-backed ``__opts__`` is now unwrapped to a plain dict before the SaltCacheLoader instantiates the file client and channel that fetch the imported template. [#68572](https://github.com/saltstack/salt/issues/68572)
- Fixed `ImportError: cannot import name 'wait' from partially initialized module 'multiprocessing.connection'` raised during salt-master/minion shutdown when a reentrant SIGTERM hit `ProcessManager.kill_children()` mid `Process.join(0)`. `salt.utils.process` now eagerly imports `multiprocessing.connection` so the module is fully initialised before any signal handler can trigger its lazy import. [#68573](https://github.com/saltstack/salt/issues/68573)
- Fixed `cmd.script` on Windows raising `Invalid user: <runas>` when `runas` is a domain account (`DOMAIN\user`, `user@DOMAIN`, or a SID). The pre-execution `user.info` check is backed by `NetUserGetInfo` which only resolves local-machine accounts and returns empty for many valid domain users; the missing lookup is now logged as a warning and execution continues so the underlying `win_runas` machinery can authenticate the account. [#68578](https://github.com/saltstack/salt/issues/68578)
- Fixed `pkg.install` on Windows silently downgrading the salt-minion when a numeric `version=` argument was passed (e.g. `version=3007.10` was YAML-parsed to the float `3007.1` and then matched the wrong winrepo entry). When the numeric version uniquely matches a string-keyed winrepo entry it is now resolved to that entry; when it is ambiguous (e.g. both `3007.1` and `3007.10` are in the winrepo) the install is refused with a clear error pointing the user at the quoted-version syntax. [#68620](https://github.com/saltstack/salt/issues/68620)
- Fixed the loader masking failure reasons when multiple modules declare the same `__virtualname__` and each `__virtual__()` returns False, so users now see every reason (e.g. both x509 v1's "Superseded, using x509_v2" and x509_v2's "Could not load cryptography") instead of only the first one recorded. [#68625](https://github.com/saltstack/salt/issues/68625)
- Fix `NetapiClient.runner` raising `TypeError` when `timeout` arrives as a string from the salt-api HTTP form. [#68653](https://github.com/saltstack/salt/issues/68653)
- Fixed `master_job_cache: redis_return` raising `KeyError: 'redis_return.prep_jid'` by registering the `redis` returner under both `redis` and `redis_return` virtual names, matching the documented `--return redis_return` usage and the module's file name. [#68663](https://github.com/saltstack/salt/issues/68663)
- Fixed ``ini.options_present`` with ``strict: True`` to remove sections that are present in the ini file but absent from the supplied ``sections`` mapping. [#68673](https://github.com/saltstack/salt/issues/68673)
- Handle `SaltDeserializationError` in grains cache loading so a corrupted cache file no longer propagates as CRITICAL during minion startup. [#68678](https://github.com/saltstack/salt/issues/68678)
- Fixed ``network.interfaces`` on Windows systems falling back to WMI (i.e. .NET older than 4.7.2): the default gateway is now reported under ``gateway`` instead of being mistakenly emitted as ``broadcast``. [#68692](https://github.com/saltstack/salt/issues/68692)
- Fixed ``file.managed`` (and other template-rendering callers) silently overwriting user-supplied ``slspath``, ``sls_path``, ``slsdotpath`` and ``slscolonpath`` values in ``defaults``/``context`` with values regenerated from the caller's ``sls`` key. [#68754](https://github.com/saltstack/salt/issues/68754)
- Fixed ``env_order`` not being honored when merging pillar data across environments. ``Pillar.render_pillar`` now iterates matched environments in the configured ``env_order`` so that, with ``top_file_merging_strategy: merge_all``, the last environment in ``env_order`` wins on conflicting pillar keys instead of the result depending on dict insertion order. [#68785](https://github.com/saltstack/salt/issues/68785)
- Improved the "Malformed topfile" error from ``HighState.verify_tops`` to name the saltenv and the matcher whose state declarations were not formed as a list, so users can locate the offending entry in their ``top.sls``. [#68792](https://github.com/saltstack/salt/issues/68792)
- Removed orphaned GnuPG dotlock files (``.#lk<addr>.<host>.<pid>``) from ``gpg_keydir`` before each decrypt in the ``gpg`` renderer so they no longer accumulate when a gpg subprocess is killed mid-operation. [#68869](https://github.com/saltstack/salt/issues/68869)
- Fix `pkg.installed` idempotency on FreeBSD when `with_origin=True` causes
    `pkg.list_pkgs` to return per-package dicts instead of version lists; extract
    the version list before version-string comparison so a second state run no
    longer falsely reports packages as changed. [#68886](https://github.com/saltstack/salt/issues/68886)
- Fix gen_signature() signing raw pub key content instead of clean_key'd content, causing master_use_pubkey_signature verification to always fail. [#68930](https://github.com/saltstack/salt/issues/68930)
- Fixed spurious ``FileLockError: lock_fn ... exists and is not a file`` raised by ``salt.utils.files.wait_lock`` and ``salt.utils.files.await_lock`` (and therefore by ``state.apply`` queue locking) when another process removed the lock file between the two separate ``os.path.exists`` / ``os.path.isfile`` stats. The pre-check now uses a single ``os.stat`` call so a transient regular-file lock no longer trips the "not a file" branch. [#68931](https://github.com/saltstack/salt/issues/68931)
- Fixed pkg.installed(update_holds=True) for APT multiarch packages by preserving arch-qualified package names through install target parsing and verification. [#68932](https://github.com/saltstack/salt/issues/68932)
- Fix deadlock in parallel `file.managed` states when source is served by the master.

    Forked parallel-state children previously inherited the parent's ZeroMQ
    REQ socket and asyncio loop from `salt.fileclient.RemoteClient`,
    `salt.crypt.AsyncAuth/SAuth`, and `salt.utils.event.SaltEvent`.  Multiple
    sibling children racing those handles deadlocked the asyncio loop with
    ~98% CPU and never completed.  Salt now registers `os.register_at_fork`
    handlers on those classes that drop inherited channel/socket references
    in any forked child; the next use rebuilds them fresh. [#68940](https://github.com/saltstack/salt/issues/68940)
- Fixed grain and pillar targeting matching minions whose data cache entry was missing. ``CkMinions._check_cache_minions`` now excludes accepted minions that have no cached grains/pillar data from greedy target results, instead of silently including them as candidates. [#68976](https://github.com/saltstack/salt/issues/68976)
- Avoid AttributeError on a closed IPCClient when the connect coroutine resolves after close(). [#68993](https://github.com/saltstack/salt/issues/68993)
- Fixed `salt.utils.network.sanitize_host` stripping colons from IPv6 addresses, which broke `network.ping` and any other caller that passed an IPv6 host. [#68995](https://github.com/saltstack/salt/issues/68995)
- Added support for MAINTAIN (m) privilege introduced in PostgreSQL 17 to salt.modules.postgres and salt.states.postgres_privileges [#69003](https://github.com/saltstack/salt/issues/69003)
- Fixed `redis.get_master_ip` silently dropping the `password` argument. The
    function was forwarding its arguments positionally to `_connect`, but
    `_connect`'s third positional slot is `db`, not `password`, so the
    caller's password landed in the database-index argument and the actual
    password fell through to `config.option("redis.password")`. Arguments
    are now passed by keyword. [#69029](https://github.com/saltstack/salt/issues/69029)
- Fixed `salt.modules.redismod._connect` rejecting valid `db=0`. The helper
    used a truthy check (`if not db`) to decide whether to fall back to
    `config.option("redis.db")`, but `not 0` is `True`, so an explicitly
    supplied `db=0` was silently replaced by the configured value. The check
    is now `if db is None`, matching the pattern already used by the sibling
    `_sconnect` helper in the same module. Other arguments keep their
    truthy-check semantics on purpose. [#69030](https://github.com/saltstack/salt/issues/69030)
- Fixed two distinct bugs in the `salt.engines.redis_sentinel` engine that
    together prevented it from being usable. `start()` no longer raises
    `AttributeError: 'dict_values' object has no attribute 'pop'` on Python 3
    (the dict.values() result is now wrapped in `list(...)`). `Listener` and
    `start()` now accept an optional `password` argument and forward it to
    the redis client, allowing the engine to authenticate against a Sentinel
    that requires AUTH; the default of `None` keeps existing configurations
    working unchanged. [#69031](https://github.com/saltstack/salt/issues/69031)
- Fixed `salt.returners.redis_return` silently ignoring the documented
    `redis.password` configuration option. The returner now reads
    `redis.password` from config (in both regular and proxy modes) and
    forwards it to both the single-server `redis.StrictRedis` and the
    `StrictRedisCluster` constructors. Operators with auth-protected Redis
    no longer lose every job return to a hidden `NOAUTH Authentication
    required` failure; deployments without a password are unaffected. [#69032](https://github.com/saltstack/salt/issues/69032)
- Fixed three closely-related bugs in `salt.cache.redis_cache` that
    together broke hierarchical-bank semantics:
    `_build_bank_hier` now registers each child bank name in both the
    parent's `$BANK_` set (consumed by `flush()` tree traversal) and the
    parent's `$BANKEYS_` set (consumed by `list_()`); `_get_banks_to_remove`
    now decodes the bytes returned by `smembers` and skips the `"."`
    placeholder, so recursive `flush()` of a parent bank actually descends
    into sub-banks instead of corrupting the path; and `flush(bank)` of a
    sub-bank now removes the flushed bank's own reference from its
    parent's index sets so `list_(parent)` no longer reports it as
    present. Together these fixes restore `cache.list("minions")`,
    `salt-run manage.present` and `salt-run manage.up` for masters
    configured with `cache: redis`. [#69033](https://github.com/saltstack/salt/issues/69033)
- Fixed `salt.tokens.rediscluster` being unable to retrieve any eauth
    token. The cluster client was created with `decode_responses=True`,
    which caused `redis_client.get()` to return `str` and broke
    `salt.payload.loads` (msgpack rejects `str`); it also caused
    `redis_client.keys()` to return `str` and broke
    `[k.decode("utf8") for k in ...]` (`str` has no `.decode`). Both
    errors were swallowed by broad `except Exception` handlers, so eauth
    appeared to silently reject every token. `decode_responses=True` is
    removed; values now round-trip as bytes through msgpack as the rest
    of the module already expected. [#69035](https://github.com/saltstack/salt/issues/69035)
- Fixed `salt.returners.redis_return` leaking `<minion>:<fun>` last-jid
    pointer keys indefinitely. The pointer was written with `pipeline.set`
    and no `ex=` TTL, so any (minion, fun) pair that stopped running stuck
    in Redis forever -- O(minions × distinct funcs) keys accumulating over
    the lifetime of the master. The pointer now expires on the same TTL
    as the rest of the returner data (`keep_jobs_seconds`). Operators with
    external scripts reading these keys directly may observe them
    expiring; the documentation never promised they would not. [#69038](https://github.com/saltstack/salt/issues/69038)
- Fixed `salt.returners.redis_return.get_fun` always returning an
    empty dict. The function read return data from a `<minion>:<jid>`
    key that no other code in the module ever wrote -- a leftover from
    an older storage schema. It now reads from the canonical
    `ret:<jid>` hash via `HGET ret:<jid> <minion>`, matching the
    storage layout that `returner` actually produces and the read
    pattern that `get_jid` already uses. [#69039](https://github.com/saltstack/salt/issues/69039)
- Fixed `salt.returners.pgjsonb` writing database errors to `sys.stderr`
    instead of Salt's logger. Errors from `_get_serv`, `_purge_jobs` and
    `_archive_jobs` are now reported via `log.exception`, so they reach
    the configured `log_file` / syslog destination on a daemonized master,
    including a full traceback. The unused `import sys` is also dropped. [#69048](https://github.com/saltstack/salt/issues/69048)
- Fixed `salt.returners.pgjsonb.returner` letting any non-connection
    `psycopg2.DatabaseError` propagate to the caller — including the
    syndic-aggregate publish path in `salt/master.py` which had no outer
    catch — so a single bad row could escape into a master subprocess.
    `event_return` had no error handling at all and a database failure
    during a flush propagated similarly. Both functions now catch
    `SaltMasterError` and `psycopg2.DatabaseError` locally, log a
    contextual message (jid/id for returns, batch size for events), and
    drop the affected payload. While here, fix `event_return` passing
    the events list as the positional `ret` argument to `_get_serv`,
    which was a copy-paste leftover from `returner(ret)`. [#69058](https://github.com/saltstack/salt/issues/69058)
- Fixed `salt-api`'s `/events` endpoint accepting eauth tokens via query
    string (``?token=...`` or ``?salt_token=...``). Tokens supplied that
    way end up in HTTP access logs, the browser ``Referer`` header, log-
    aggregation systems and shell history; the token retains validity for
    ``token_expire`` (12h by default), so any party reading those logs can
    replay the token. The endpoint now rejects query-string tokens with a
    400 error pointing at the ``X-Auth-Token`` header (for non-browser
    clients) or the session cookie established by ``/login`` (for browser
    ``EventSource`` clients) as the supported channels. ``X-Auth-Token``
    header support is added; cookie-based auth continues to work
    unchanged. [#69071](https://github.com/saltstack/salt/issues/69071)
- ``LoadAuth.get_tok`` now distinguishes between corrupt token blobs (removed from the store) and transient backend errors such as Redis connection drops or NFS hangs (token kept, request treated as not-authenticated). Previously a single backend hiccup could log every authenticated user out by deleting valid tokens. [#69073](https://github.com/saltstack/salt/issues/69073)
- ``cmd.run`` and friends no longer include the ``env`` and ``stdin`` arguments in the ``CommandExecutionError`` raised when the underlying subprocess fails to start (typically ``ENOENT`` / binary not found). Both fields routinely carry credentials passed in by the caller (``env={"DB_PASSWORD": "..."}``, password piped via ``stdin``), and the error message ends up in master/minion logs and in event-bus return data visible to the API caller. [#69075](https://github.com/saltstack/salt/issues/69075)
- Lowered the "Cache version mismatch clearing" log message in ``salt.utils.cache.verify_cache_version`` from ``WARNING`` to ``DEBUG``; the cache is rebuilt as part of normal operation after upgrades or when an ephemeral cache directory has been removed, and does not warrant user attention. [#69106](https://github.com/saltstack/salt/issues/69106)
- * Relenv 0.22.14
      - Update sqlite to 3.53.2.0
      - Update openssl to 3.5.7 [#69129](https://github.com/saltstack/salt/issues/69129)
- Surface the real cause of a proxymodule load failure in salt-proxy's abort message. The misleading "Proxymodule X is missing an init() or a shutdown() or both" wording is now only used when init/shutdown really are missing from a loaded module; if the module failed to load (for example because its ``__virtual__`` returned False), the underlying reason is included in the error. [#69139](https://github.com/saltstack/salt/issues/69139)
- Fixed ``pkg.hold`` and ``pkg.list_holds`` on dnf5 systems (e.g. Fedora 42+):
    ``pkg.hold`` now calls ``dnf5 versionlock add <pkg>`` (the bare
    ``versionlock <pkg>`` form was rejected by dnf5), and ``pkg.list_holds``
    reads ``/etc/dnf/versionlock.toml`` directly so ``pkg.installed`` with
    ``hold: true`` is again idempotent. [#69181](https://github.com/saltstack/salt/issues/69181)
- Fixed Salt-SSH syncing internal modules as extmods [#69199](https://github.com/saltstack/salt/issues/69199)
- Fixed ``lgpo_reg.value_absent`` failing when the Registry.pol entry was already absent but the registry value still existed. ``lgpo_reg.delete_value`` was returning early before reaching the registry cleanup code, causing the state to see no changes and report failure. The registry value is now removed regardless of whether the pol entry was present. [#69203](https://github.com/saltstack/salt/issues/69203)
- Fixed `postgres_local_cache.save_load` raising `psycopg2.errors.UniqueViolation` when more than one master in an active-active multi-master cluster persists the same JID; the INSERT is now idempotent via `ON CONFLICT (jid) DO NOTHING` on PostgreSQL >= 9.5, and the duplicate is tolerated on older servers. [#69214](https://github.com/saltstack/salt/issues/69214)
- Fixed Windows MSI self-upgrade via ``pkg.install`` failing with error 1603. The old product's ``DeleteConfig_DECAC`` custom action was unconditionally deleting ``ROOTDIR\var`` during ``RemoveExistingProducts``, destroying the MSI that ``pkg.install`` had cached to ``ROOTDIR\var\cache`` before launching the upgrade. Users who had ``REMOVE_CONFIG=1`` persisted in the registry (from checking "On uninstall" at install time) hit a worse variant where the entire ``ROOTDIR`` was deleted. The fix checks ``UPGRADINGPRODUCTCODE`` — set by Windows Installer whenever an uninstall is triggered by a major upgrade — and skips all ``ROOTDIR`` deletion during upgrades, matching the behaviour of the NSIS installer which has always preserved ``ROOTDIR`` during upgrades. [#69219](https://github.com/saltstack/salt/issues/69219)
- Fixed `TypeError: string indices must be integers` in the minion when the master returns a bare string error response (e.g. `"bad load"`, `"Some exception handling minion payload"`) for a pillar request. The minion now raises a clean `AuthenticationError` instead of crashing, allowing the caller to retry or fail gracefully. [#69228](https://github.com/saltstack/salt/issues/69228)
- pkg.list_patches in yumpkg.py parses tdnf output on Photon OS [#69229](https://github.com/saltstack/salt/issues/69229)
- Fix `git.tag` so that the documented `message` argument is actually forwarded to `git tag`, creating an annotated tag with the supplied message instead of silently producing a lightweight tag. [#69298](https://github.com/saltstack/salt/issues/69298)
- Fixed `salt.auth.pam` conversation callback so it answers `PAM_PROMPT_ECHO_ON` prompts with the supplied username; previously only `PAM_PROMPT_ECHO_OFF` prompts were answered, which caused `pam_authenticate` to silently fail (and salt-api to return 401) against PAM stacks that re-prompt for the user. [#69304](https://github.com/saltstack/salt/issues/69304)
- Ensure multiple masters have their own job/state queues [#69308](https://github.com/saltstack/salt/issues/69308)
- Fixed loading private keys from PKCS#12 containers with x509_v2 [#69312](https://github.com/saltstack/salt/issues/69312)
- Fixed creating self-signed PKCS#12-encoded certificates [#69319](https://github.com/saltstack/salt/issues/69319)
- Fixed minion state queue replacing the master-assigned JID on queued state runs, so returns now come back tagged with the JID the master actually published. [#69386](https://github.com/saltstack/salt/issues/69386)
- Made the salt user's home directory and the relenv ``extras-<py-ver>`` directory configurable in the Linux packaging. The DEB preinst scripts now source ``/etc/default/salt-setup`` (and ``/etc/sysconfig/salt-minion-setup`` for cross-distro parity with RPM) before applying the ``SALT_HOME``/``SALT_USER``/``SALT_GROUP``/``SALT_NAME`` defaults, mirroring the long-standing RPM behavior. A new ``SALT_EXTRAS_DIR`` override is honored by both stacks so the extras tree can be relocated outside ``/opt/saltstack/salt`` and its ownership is correctly restored on upgrade. [#69402](https://github.com/saltstack/salt/issues/69402)
- Fixed minion worker threads hanging or crashing when returning job results
    to the master. The main process now fires an error event back to the worker
    when ``req_channel.send()`` times out, so workers wake up immediately rather
    than waiting out their full timeout. Replaced the bare ``TimeoutError`` raised
    in ``_send_req_sync`` with ``SaltReqTimeoutError`` so ``_return_pub``'s existing
    handler catches it correctly. The worker's wait timeout is now derived from
    ``return_retry_timer_max * return_retry_tries`` to ensure it always outlasts
    the main process's retry budget. [#69416](https://github.com/saltstack/salt/issues/69416)
- Fixed zsh completion by using the proper python3 instead of python2. [#69419](https://github.com/saltstack/salt/issues/69419)
- Fixed Photon OS Arm64 FIPS CI by re-enabling the OpenSSL default provider after installing openssl-fips-provider, working around the disabled-default-provider bug in `openssl-fips-provider <= 3.1.2-3.ph5` on the lagging Photon aarch64 mirror. [#69449](https://github.com/saltstack/salt/issues/69449)
- Add regression test for changelog template multi-line rendering and harden template with indent filter so continuation lines are correctly indented under the bullet (defensive backport of #69458 to 3006.x). [#69454](https://github.com/saltstack/salt/issues/69454)
- Fixed minion not honoring SIGTERM while stuck in the master DNS retry loop, which caused systemd to escalate to SIGKILL after 90 seconds. [#69466](https://github.com/saltstack/salt/issues/69466)
- Fixed ``lgpo_reg`` module and state functions failing on Windows Domain Controllers with ``Access is denied`` when writing to ``HKLM\SOFTWARE\Policies\`` subkeys. The ``set_value``, ``disable_value``, and ``delete_value`` execution module functions now accept a ``write_registry`` parameter (default ``None``) that auto-detects Domain Controllers via the ``ProductType`` registry key and skips the direct registry write when one is detected, instead relying on the Group Policy engine to apply the policy on the next refresh. An explicit ``True`` or ``False`` overrides auto-detection. A ``refresh_policy`` parameter (default ``False``) has been added to all three functions to trigger an in-process ``userenv.RefreshPolicy`` call immediately after the ``Registry.pol`` file is updated. The corresponding state functions ``value_present``, ``value_disabled``, and ``value_absent`` expose the same parameters. A standalone ``lgpo_reg.refresh_policy`` execution function and ``lgpo_reg.refresh_policy`` state have been added to allow a single Group Policy refresh to be issued after a batch of policy writes. ``is_domain_controller`` has been added to ``salt.utils.win_functions`` and ``refresh_policy`` has been added to ``salt.utils.win_lgpo_reg``. [#69468](https://github.com/saltstack/salt/issues/69468)
- Fixed 3006.x Windows nightly CI by pinning the runner-host Python to 3.14.6 (OpenSSL 3.5.7); the setup-python default `3.14` was resolving to a cached 3.14.5 build whose OpenSSL 3.0.20 rejected the cert pypi.org currently serves. [#69486](https://github.com/saltstack/salt/issues/69486)
- Fixed 3006.x Windows nightly CI Deps by dropping a sitecustomize hook into the salt onedir's `Lib/site-packages` that applies the cpython#104135 iter-and-skip patch before pip touches TLS; the prior runner-host Python pin in #69486 targeted the wrong interpreter (the failing pip runs in a venv created from the relenv-bundled Python 3.10) and is reverted. [#69490](https://github.com/saltstack/salt/issues/69490)
- Fixed ``lgpo_reg`` failures on Windows when ``Registry.pol`` is temporarily locked by the Group Policy service or other processes. Salt now uses ``EnterCriticalPolicySection`` / ``LeaveCriticalPolicySection`` from ``userenv.dll`` — the same synchronization primitive used by the GP engine — to serialize read-modify-write access to ``Registry.pol``. A retry loop with configurable attempts and delay is also applied for non-GP lockers such as antivirus scanners or VSS snapshots that do not participate in the GP critical section handshake. [#69492](https://github.com/saltstack/salt/issues/69492)

# Added

- Added ``shadow.verify_password`` to ``salt.modules.win_shadow``, which
    validates a Windows user's password via ``LogonUser`` with
    ``LOGON32_LOGON_NETWORK`` (Microsoft's recommended approach per
    `KB180548 <https://support.microsoft.com/en-us/help/180548>`_) without
    creating an interactive session. If the check causes an account lockout,
    the account is automatically unlocked. Updated ``user.present`` on Windows
    to use ``shadow.verify_password`` so the password is only changed when it
    differs from the current value, matching the idempotent behaviour on other
    platforms. [#41347](https://github.com/saltstack/salt/issues/41347)
- Added ability to configure the pillar destination for the `netbox` ext_pillar via `destination_pillar_key` [#65531](https://github.com/saltstack/salt/issues/65531)
- Migrate Salt documentation to the PyData Sphinx theme. This update modernizes the documentation UI, improves navigation with a persistent sidebar tree, and fixes issues with embedded video playback. [#69185](https://github.com/saltstack/salt/issues/69185)
- fix etcdv3 module authentification when using etcd3-py lib [#69202](https://github.com/saltstack/salt/issues/69202)
- Added ``lgpo_reg.get_rsop_value`` to query the Resultant Set of Policy (RSoP) for a registry key/value and detect whether it is managed by a Domain Group Policy Object. The ``lgpo_reg`` module functions ``set_value``, ``disable_value``, and ``delete_value`` now log a warning when a Domain GPO is detected for the target value. The ``lgpo_reg`` state functions ``value_present``, ``value_disabled``, and ``value_absent`` append the same warning to the state comment so it is visible in state output. [#69205](https://github.com/saltstack/salt/issues/69205)


* Thu Jun 11 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3008.1

# Changed

- Changed `salt.returners.redis_return` to enumerate the Redis keyspace
  with `SCAN` instead of the blocking `KEYS pattern` command in both
  `get_jids` and `clean_old_jobs`. `KEYS` walks the entire keyspace
  synchronously and stalls the Redis server for the duration; on a
  master with hundreds of thousands of jobs this can block all clients
  of that Redis instance for seconds. `SCAN` is incremental and
  non-blocking. Order of returned keys is no longer guaranteed (the
  returner does not rely on order); operators with custom scripts that
  read `ret:*` or `load:*` directly may see them in a different order. [#69037](https://github.com/saltstack/salt/issues/69037)

# Fixed

- Fixed ``win_pkg`` functions ignoring the ``saltenv`` setting in minion configuration. All public functions (``refresh_db``, ``genrepo``, ``install``, ``remove``, ``list_pkgs``, ``latest_version``, ``upgrade_available``, ``list_upgrades``, ``list_available``, ``version``, ``get_repo_data``, ``get_package_info``) now fall back to ``__opts__["saltenv"]`` when ``saltenv`` is not passed explicitly, instead of always defaulting to ``base``. [#38551](https://github.com/saltstack/salt/issues/38551)
- Added ``encoding`` parameter to ``file.replace`` execution module and state to support UTF-16, UTF-32, and other multi-byte encoded files that would otherwise be incorrectly treated as binary. [#52793](https://github.com/saltstack/salt/issues/52793)
- Improved documentation for the `runas` and `password` parameters in `cmd.run`, `cmd.script`, and all `salt.modules.cmdmod` execution functions on Windows. The docs now accurately describe when a password is required: only when the salt-minion is **not** running as SYSTEM or as an elevated Administrator. Removed the inaccurate claim that the target user account must be in the Administrators group. Also changed `cmd.script` to log a warning instead of hard-failing when `runas` is used without a password on Windows, since a password is not always required. [#57951](https://github.com/saltstack/salt/issues/57951)
- Fixed `SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC` errors in the VMware cloud driver by reconnecting when a cached vCenter service instance is found to be stale or corrupted (for example when inherited across a fork by salt-cloud's parallel provider queries). [#61983](https://github.com/saltstack/salt/issues/61983)
- Fixed event signature verification failing under ``minion_sign_messages``. The minion was signing the return load before ``salt.channel.client.AsyncReqChannel._package_load`` attached transport metadata (``nonce``, ``ts``, ``tok``, ``id``), so the bytes the master re-serialized to verify did not match what was signed and every signed return was dropped. Signing is now performed inside ``_package_load`` after the metadata is attached, against the same bytes the master verifies. [#68181](https://github.com/saltstack/salt/issues/68181)
- Fixed two distinct bugs in the `salt.engines.redis_sentinel` engine that
  together prevented it from being usable. `start()` no longer raises
  `AttributeError: 'dict_values' object has no attribute 'pop'` on Python 3
  (the dict.values() result is now wrapped in `list(...)`). `Listener` and
  `start()` now accept an optional `password` argument and forward it to
  the redis client, allowing the engine to authenticate against a Sentinel
  that requires AUTH; the default of `None` keeps existing configurations
  working unchanged. [#69031](https://github.com/saltstack/salt/issues/69031)
- Fixed `salt.returners.redis_return` silently ignoring the documented
  `redis.password` configuration option. The returner now reads
  `redis.password` from config (in both regular and proxy modes) and
  forwards it to both the single-server `redis.StrictRedis` and the
  `StrictRedisCluster` constructors. Operators with auth-protected Redis
  no longer lose every job return to a hidden `NOAUTH Authentication
  required` failure; deployments without a password are unaffected. [#69032](https://github.com/saltstack/salt/issues/69032)
- Fixed three closely-related bugs in `salt.cache.redis_cache` that
  together broke hierarchical-bank semantics:
  `_build_bank_hier` now registers each child bank name in both the
  parent's `$BANK_` set (consumed by `flush()` tree traversal) and the
  parent's `$BANKEYS_` set (consumed by `list_()`); `_get_banks_to_remove`
  now decodes the bytes returned by `smembers` and skips the `"."`
  placeholder, so recursive `flush()` of a parent bank actually descends
  into sub-banks instead of corrupting the path; and `flush(bank)` of a
  sub-bank now removes the flushed bank's own reference from its
  parent's index sets so `list_(parent)` no longer reports it as
  present. Together these fixes restore `cache.list("minions")`,
  `salt-run manage.present` and `salt-run manage.up` for masters
  configured with `cache: redis`. [#69033](https://github.com/saltstack/salt/issues/69033)
- Fixed `salt.tokens.rediscluster` being unable to retrieve any eauth
  token. The cluster client was created with `decode_responses=True`,
  which caused `redis_client.get()` to return `str` and broke
  `salt.payload.loads` (msgpack rejects `str`); it also caused
  `redis_client.keys()` to return `str` and broke
  `[k.decode("utf8") for k in ...]` (`str` has no `.decode`). Both
  errors were swallowed by broad `except Exception` handlers, so eauth
  appeared to silently reject every token. `decode_responses=True` is
  removed; values now round-trip as bytes through msgpack as the rest
  of the module already expected. [#69035](https://github.com/saltstack/salt/issues/69035)
- Fixed `salt.returners.redis_return` leaking `<minion>:<fun>` last-jid
  pointer keys indefinitely. The pointer was written with `pipeline.set`
  and no `ex=` TTL, so any (minion, fun) pair that stopped running stuck
  in Redis forever -- O(minions × distinct funcs) keys accumulating over
  the lifetime of the master. The pointer now expires on the same TTL
  as the rest of the returner data (`keep_jobs_seconds`). Operators with
  external scripts reading these keys directly may observe them
  expiring; the documentation never promised they would not. [#69038](https://github.com/saltstack/salt/issues/69038)
- Fixed `salt.returners.redis_return.get_fun` always returning an
  empty dict. The function read return data from a `<minion>:<jid>`
  key that no other code in the module ever wrote -- a leftover from
  an older storage schema. It now reads from the canonical
  `ret:<jid>` hash via `HGET ret:<jid> <minion>`, matching the
  storage layout that `returner` actually produces and the read
  pattern that `get_jid` already uses. [#69039](https://github.com/saltstack/salt/issues/69039)
- ``cmd.run`` and friends no longer include the ``env`` and ``stdin`` arguments in the ``CommandExecutionError`` raised when the underlying subprocess fails to start (typically ``ENOENT`` / binary not found). Both fields routinely carry credentials passed in by the caller (``env={"DB_PASSWORD": "..."}``, password piped via ``stdin``), and the error message ends up in master/minion logs and in event-bus return data visible to the API caller. [#69075](https://github.com/saltstack/salt/issues/69075)
- * Relenv 0.22.14
  - Update python 3.14 to 3.14.6
  - Update sqlite to 3.53.2.0
  - Update openssl to 3.5.7 [#69129](https://github.com/saltstack/salt/issues/69129)
- Fix pillar masking leaking ``**********`` into rendered pillar and state values. ``MaskedDict`` / ``MaskedList`` ``__repr__`` / ``__str__`` now consult the ``salt.utils.secret.mask_pillar`` ContextVar, so ``{{ pillar['list_or_dict_value'] }}`` interpolations on the minion return plain values inside a render bracket. Hoist the ``mask_pillar=False`` bracket from ``render_pillar`` to ``compile_pillar`` so ``ext_pillar`` handlers and the rest of the master-side pillar build also run unmasked. [#69160](https://github.com/saltstack/salt/issues/69160)
- Fixed Windows MSI self-upgrade via ``pkg.install`` failing with error 1603. The old product's ``DeleteConfig_DECAC`` custom action was unconditionally deleting ``ROOTDIR\var`` during ``RemoveExistingProducts``, destroying the MSI that ``pkg.install`` had cached to ``ROOTDIR\var\cache`` before launching the upgrade. Users who had ``REMOVE_CONFIG=1`` persisted in the registry (from checking "On uninstall" at install time) hit a worse variant where the entire ``ROOTDIR`` was deleted. The fix checks ``UPGRADINGPRODUCTCODE`` — set by Windows Installer whenever an uninstall is triggered by a major upgrade — and skips all ``ROOTDIR`` deletion during upgrades, matching the behaviour of the NSIS installer which has always preserved ``ROOTDIR`` during upgrades. [#69219](https://github.com/saltstack/salt/issues/69219)
- Fixed `TypeError: string indices must be integers` in the minion when the master returns a bare string error response (e.g. `"bad load"`, `"Some exception handling minion payload"`) for a pillar request. The minion now raises a clean `AuthenticationError` instead of crashing, allowing the caller to retry or fail gracefully. [#69228](https://github.com/saltstack/salt/issues/69228)
- pkg.list_patches in yumpkg.py parses tdnf output on Photon OS [#69229](https://github.com/saltstack/salt/issues/69229)
- Restore Python dependencies in the PyPI sdist by including ``requirements/*.in`` and ``requirements/**/*.lock`` in ``MANIFEST.in``. After the requirements ``.txt`` → ``.in`` rename, the sdist no longer shipped the files that ``setup.py`` reads to populate ``install_requires``, so ``pip install salt`` produced an installation with no dependencies. [#69244](https://github.com/saltstack/salt/issues/69244)
- Fix `salt-cloud` failing to start with `AttributeError: module 'salt' has no attribute 'minion'` by importing `salt.minion` in `salt.cloud`. [#69281](https://github.com/saltstack/salt/issues/69281)
- Ensure multiple masters have their own job/state queues [#69308](https://github.com/saltstack/salt/issues/69308)
- Fixed minion state queue replacing the master-assigned JID on queued state runs, so returns now come back tagged with the JID the master actually published. [#69386](https://github.com/saltstack/salt/issues/69386)
- Made the salt user's home directory and the relenv ``extras-<py-ver>`` directory configurable in the Linux packaging. The DEB preinst scripts now source ``/etc/default/salt-setup`` (and ``/etc/sysconfig/salt-minion-setup`` for cross-distro parity with RPM) before applying the ``SALT_HOME``/``SALT_USER``/``SALT_GROUP``/``SALT_NAME`` defaults, mirroring the long-standing RPM behavior. A new ``SALT_EXTRAS_DIR`` override is honored by both stacks so the extras tree can be relocated outside ``/opt/saltstack/salt`` and its ownership is correctly restored on upgrade. [#69402](https://github.com/saltstack/salt/issues/69402)

# Added

- Added ``dsc_resource`` execution module and state module for invoking individual
  PowerShell DSC resources directly via ``Invoke-DscResource``, without compiling
  a MOF file or involving the Local Configuration Manager. The
  ``dsc_resource.managed`` state provides idiomatic Salt state management for any
  installed DSC resource module. [#43718](https://github.com/saltstack/salt/issues/43718)
- fix etcdv3 module authentification when using etcd3-py lib [#69202](https://github.com/saltstack/salt/issues/69202)


* Wed Apr 29 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.14

# Fixed

- Fix `mac_brew_pkg.list_pkgs` crashing or producing incorrect results when
  Homebrew returns `null` values for cask metadata:

  - When the installed version of a cask is `null` (e.g. Homebrew cannot
    determine the installed version), it is now reported as `"unknown"`
    instead of raising an error.
  - When `full_token` is `null`, it is now filtered out so that `None`
    is never used as a package name key in the returned dictionary. [#68763](https://github.com/saltstack/salt/issues/68763)


* Wed Feb 11 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.13

# Fixed

- Fix user.info when querying domain users. Uses DsGetDcName for more
  dependable domain controller lookup. [#68612](https://github.com/saltstack/salt/issues/68612)
- Fixed minion instability and resource exhaustion under high load by implementing resource-aware job queuing and backpressure. Added `process_count_max` enforcement and disk-based queuing to prevent unbounded process spawning and file descriptor exhaustion. [#68703](https://github.com/saltstack/salt/issues/68703)


* Wed May 13 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.25

# Fixed

- Fixed multiline powershell -Command { } blocks failing with "Missing closing
  '}'" when used in a cmd.run state on Windows. Salt now collapses embedded
  newlines and re-encodes the script block as -EncodedCommand, ensuring correct
  execution and suppressing CLIXML noise from stderr. [#68397](https://github.com/saltstack/salt/issues/68397)
- Quote cmd.exe /c payloads on Windows so compound commands (e.g. cd ... & dir) work with runas; with cmd.exe, that wrapping is applied whenever runas is set, not only when python_shell is true [#68448](https://github.com/saltstack/salt/issues/68448)
- Reduced salt-api memory growth on busy installations by stopping the ZeroMQ
  REQ client's send/recv coroutine before tearing down the IOLoop and sockets: on
  close, queue a shutdown marker and run the ILOop once via run_sync so
  Tornado Queue.get waiters unwind cleanly while retaining the Tornado Queue for
  low-latency wakeups. [#68637](https://github.com/saltstack/salt/issues/68637)
- Fixed a regression in win_pkg where msiexec install flags containing
  Windows-style quoting (e.g. ``MYPROPERTY="C:\some file.txt"``) were
  mangled into ``"MYPROPERTY=C:\some file.txt"`` causing msiexec to hang.
  Restored the pre-regression behaviour where ``shlex_split`` is not applied
  to command strings on Windows, preserving Windows-style argument quoting
  when the command is passed directly to ``CreateProcess``. [#68950](https://github.com/saltstack/salt/issues/68950)
- Fixed `salt.returners.pgjsonb.save_load` silently swallowing all
  `psycopg2.IntegrityError`s. The catch is now narrowed to
  `psycopg2.errors.UniqueViolation` only — the legacy duplicate-jid
  case from #22171 on PostgreSQL < 9.5 — and emits a warning. Other
  integrity errors (foreign-key, NOT NULL, CHECK violations) now
  surface to the caller instead of being dropped. [#69046](https://github.com/saltstack/salt/issues/69046)
- Fixed `salt.returners.pgjsonb` mutating a module-global SQL string
  (`PG_SAVE_LOAD_SQL`) inside `_get_serv` on every connection. The
  SQL form is now chosen per-call inside `save_load` from the actual
  connection's `server_version`, so a master that talks to PostgreSQL
  clusters with mixed versions (e.g. through a failover) no longer
  sends UPSERT syntax to a pre-9.5 server after the first 9.5+
  connection. [#69052](https://github.com/saltstack/salt/issues/69052)
- Fix pip install -e salt [#69101](https://github.com/saltstack/salt/issues/69101)

# Added

- Added support for the ``AdministratorLockout`` (Allow Administrator account
  lockout) policy in ``salt.modules.win_lgpo``, allowing the built-in
  Administrator account lockout behaviour to be enabled or disabled via
  Local Group Policy on Windows. [#69132](https://github.com/saltstack/salt/issues/69132)


* Thu Apr 23 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.24

# Fixed

- Fixed inotify file descriptor leak in beacons. When beacons are refreshed
  (e.g. during module refresh or pillar refresh), the old beacon modules are now
  properly closed before creating new ones, preventing exhaustion of the inotify
  instance limit. Also fixed beacon delete not calling the beacon's close
  function, causing resource leaks and CPU spin after deleting beacons at runtime
  via ``beacons.delete``. [#66449](https://github.com/saltstack/salt/issues/66449)
- Fixed x509_v2.certificate_managed state fails if another state.apply is queued [#66929](https://github.com/saltstack/salt/issues/66929)
- Fixed x509_v2 private_key_managed failing on Windows due to default `mode` argument [#66942](https://github.com/saltstack/salt/issues/66942)
- Windows LGPO / audit policy: Advanced audit policy is now read and applied through the Windows security API (AuditQuerySystemPolicy / AuditSetSystemPolicy) instead of parsing auditpol.exe output, so behavior no longer depends on the system locale. [#68354](https://github.com/saltstack/salt/issues/68354)
- Decouple the pub timeout from opts timeout. Programatic useage of client now has a 30 second timeout. [#68597](https://github.com/saltstack/salt/issues/68597)
- Fix salt-call and salt-pip to honor configured user for privilege dropping [#68684](https://github.com/saltstack/salt/issues/68684)
- Fix `mac_brew_pkg.list_pkgs` crashing or producing incorrect results when
  Homebrew returns `null` values for cask metadata:

  - When the installed version of a cask is `null` (e.g. Homebrew cannot
    determine the installed version), it is now reported as `"unknown"`
    instead of raising an error.
  - When `full_token` is `null`, it is now filtered out so that `None`
    is never used as a package name key in the returned dictionary. [#68763](https://github.com/saltstack/salt/issues/68763)
- - Prevented generation of spurious ppbt toolchain in /root/.local on RPM upgrade
  - Stale pycache files now get cleaned up on RPM upgrade [#68781](https://github.com/saltstack/salt/issues/68781)
- Ensure Salt file and directory ownership is correctly detected and preserved when upgrading RPM and Debian packages, particularly when running Salt as a non-root user. [#68793](https://github.com/saltstack/salt/issues/68793)
- Upgrade relenv to 0.22.5 which pin's openssl to an LTS version (3.5.x) [#68803](https://github.com/saltstack/salt/issues/68803)
- Patch the vendored tornado version to account for CVE patches that have been applied. [#68820](https://github.com/saltstack/salt/issues/68820)
- Made x509_v2 certificate_managed respect `copypath` and `prepend_cn` parameters [#68828](https://github.com/saltstack/salt/issues/68828)
- Upgrade pyopenssl to >= 26.0.0
   - CVE-2026-27459
   - CVE-2026-27448 [#68832](https://github.com/saltstack/salt/issues/68832)
- Patch tornado for BDSA-2025-60810 [#68853](https://github.com/saltstack/salt/issues/68853)
- Patch tornado for BDSA-2026-3867 [#68854](https://github.com/saltstack/salt/issues/68854)
- Fixed source package builds (DEB/RPM) failing with ``LookupError: hatchling is already being built`` by adding ``hatchling`` to the ``--only-binary`` allow-list so pip uses its universal wheel instead of attempting a circular source build. [#68858](https://github.com/saltstack/salt/issues/68858)
- Upgrade relenv to 0.22.7

  * Upgread Python Versions 3.12.13, 3.11.15, 3.10.20
    - CVE-2024-6923: Header injection in email module
    - CVE-2026-24515, CVE-2026-25210, CVE-2025-59375: XML memory amplification and libexpat vulnerabilities
  * SQLite 3.51.3.0
    - CVE-2025-70873: Heap memory disclosure in zipfile extension
    - CVE-2025-7709: Integer overflow in FTS5 extension
    - Fixes WAL-reset bug preventing database corruption
  * XZ Utils 5.8.3
    - CVE-2026-34743: Buffer overflow in lzma_index_append()
  * Expat 2.7.5
    - CVE-2026-32776: NULL pointer dereference in external parameter entities
    - CVE-2026-32777: Infinite loop in entityValueProcessor
    - CVE-2026-32778: NULL pointer dereference during OOM recovery [#68884](https://github.com/saltstack/salt/issues/68884)
- Minion properly closes pub channel when authentication to the master failes,
  prevents leaking file handles. [#68901](https://github.com/saltstack/salt/issues/68901)
- Patch tornado for BDSA-2026-6522 [#68920](https://github.com/saltstack/salt/issues/68920)
- Perl 5.42.2.1
      CVE-2026-4176: Memory corruption in Compress::Raw::Zlib core module
      CVE-2026-3381 / CVE-2026-27171: zlib vulnerabilities within compression capabilities
  OpenSSL 3.5.6
      CVE-2026-31790: Leakage from uninitialized memory in RSA KEM RSASVE
      CVE-2026-2673: Loss of key agreement group tuple structure
      CVE-2026-28387: Potential use-after-free in DANE client code
      CVE-2026-28388: DoS via NULL pointer dereference in delta CRL processing
      CVE-2026-31789: Heap buffer overflow in hexadecimal conversion
      CVE-2026-28389 / CVE-2026-28390: NULL pointer dereferences in CMS processing
  SQLite 3.53.0.0
      CVE-2025-6965: High-severity memory corruption flaw in aggregate terms [#68986](https://github.com/saltstack/salt/issues/68986)


* Mon Feb 23 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.23
No significant changes.


* Sat Feb 21 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.22

# Fixed

- Fix nftables module check function doesn't understand that braces are optional [#67078](https://github.com/saltstack/salt/issues/67078)
- Fix issue with upstream Netbox API which changed api/ipam/prefixes output to use "scope" FK instead of "site" [#68375](https://github.com/saltstack/salt/issues/68375)
- Fixed SyntaxWarning for invalid escape sequence '\d' in salt/ext/tornado/util.py
  on Python 3.12+ by converting the re_unescape docstring to a raw string. [#68568](https://github.com/saltstack/salt/issues/68568)
- Raise exception if systemd-run is not found when scope is enabled

  Instead of returning None when the systemd-run command is not found
  — which causes the command to fail with an unclear error —
  an exception is now raised, helping to identify the real issue. [#68720](https://github.com/saltstack/salt/issues/68720)
- Remove bundled wheels from virtualenv [#68740](https://github.com/saltstack/salt/issues/68740)

# Added

- Add an option in the chocolatey state and module so that the viruscheck flag can be controlled. [#68558](https://github.com/saltstack/salt/issues/68558)


* Wed Feb 11 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.21

# Fixed

- Fix user.info when querying domain users. Uses DsGetDcName for more
  dependable domain controller lookup. [#68612](https://github.com/saltstack/salt/issues/68612)
- Fixed minion instability and resource exhaustion under high load by implementing resource-aware job queuing and backpressure. Added `process_count_max` enforcement and disk-based queuing to prevent unbounded process spawning and file descriptor exhaustion. [#68703](https://github.com/saltstack/salt/issues/68703)


* Thu Feb 05 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.12

# Fixed

- Support attrlist in ldap.managed [#53364](https://github.com/saltstack/salt/issues/53364)
- Fix a stacktrace that happens then the minion fails to connect to a master. [#62780](https://github.com/saltstack/salt/issues/62780)
- Add virtualenv to package dependencies so venv module can work without ensurepip. [#68388](https://github.com/saltstack/salt/issues/68388)
- Preserve interval_map on beacon refresh to ensure beacons are still fired when we refresh beacons. [#68548](https://github.com/saltstack/salt/issues/68548)
- Fixed Arista EOS Napalm driver to return json data, by allowing to pass cli kwargs to driver. [#68550](https://github.com/saltstack/salt/issues/68550)
- Fix an issue with Value names that contain periods, such as scrnsave.exe [#68565](https://github.com/saltstack/salt/issues/68565)
- Fixed output of lgpo_reg states. Comments and result are now correct. [#68566](https://github.com/saltstack/salt/issues/68566)
- Update bootstrap-salt.sh to v2026-01-15 [#68640](https://github.com/saltstack/salt/issues/68640)
- Update bootstrap to v2026-01-22 [#68656](https://github.com/saltstack/salt/issues/68656)
- Upgrade relenv to 0.22.3
  * Upgrade OpenSSL to 3.6.1 - Fixes CVE-2025-15467
  * Upgrade SQLite to 3.51.2.0
  * Upgrade XZ to 5.8.2
  * Upgrade ncurses to6.6
  * Upgrade expat to2.7.4 [#68682](https://github.com/saltstack/salt/issues/68682)


* Fri Jan 09 2026 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.11

# Fixed

- Fixed a typo in salt.util.cloud to detect the version of winrm [#68561](https://github.com/saltstack/salt/issues/68561)
- Patched tornado for BDSA-2025-60811 and BDSA-2025-60812 [#68594](https://github.com/saltstack/salt/issues/68594)
- Increase pub and pub_async timeouts on LocalClient from 5 to 15 for better
  handling of network delays. This change only affects programatic usage of
  LocalClient. [#68597](https://github.com/saltstack/salt/issues/68597)
- Added `lazy_loader_strict_matching` minion configuration option to reduce memory usage by skipping the expensive fallback search that scans through every module file. [#68606](https://github.com/saltstack/salt/issues/68606)
- Upgrade relenv to 0.22.2:
  * Remove RPATH from shared libraries that do not link to any other libraries in
    our environment.
  * Ensure we always return a proper and consistang default python version for
    create, fetch, build commands. [#68607](https://github.com/saltstack/salt/issues/68607)
- Mitigate CVE-2025-13836 in nxos utils [#68618](https://github.com/saltstack/salt/issues/68618)


* Thu Dec 18 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.10

# Fixed

- Fixed an issue with how existing entries are tracked in grains.list_present. Previous entries were only considered if
  the grain previously existed. If not then the state would not "see" the duplicates. Removed the dubious tracking via
  "context" and focused on using checking for existance in the live grains. [#31427](https://github.com/saltstack/salt/issues/31427)
- Fixed issue with complex objects in grains.list_present. Original fix #52710 did not fully address the problem. [#39875](https://github.com/saltstack/salt/issues/39875)
- Fixed ssh_auth.present to respect provided `options` when read keys from source file [#60769](https://github.com/saltstack/salt/issues/60769)
- Fixed ssh_auth regexp to handle key types with @ or . [#61299](https://github.com/saltstack/salt/issues/61299)
- Fixed a TypeError exception thrown by ssh_known_hosts.present when the specified user account does not exist [#62049](https://github.com/saltstack/salt/issues/62049)
- Fixed false identification of text as binary in salt.utils.file.is_binary if utf-8 multibyte character is truncated at end of 2048 bytes sample. [#62214](https://github.com/saltstack/salt/issues/62214)
- Fix runtime error on OpenBSD by adding support for the osfullname grain [#64189](https://github.com/saltstack/salt/issues/64189)
- Fix closing of TCP transport channels and avoid additional errors [#66568](https://github.com/saltstack/salt/issues/66568)
- Fixed false negative "is not text" in salt.utils.files.is_text if an utf-8 multibyte character is truncated at end of 512 bytes sample. [#66706](https://github.com/saltstack/salt/issues/66706)
- fixes salt runner mine.get not returning value if allow_tgt is defined in mine function [#68188](https://github.com/saltstack/salt/issues/68188)
- Forward minion list events in Syndic cluster mode to enable proper job completion detection [#68319](https://github.com/saltstack/salt/issues/68319)
- Fixes issue with asyncio logger not using SaltLoggingClass and causing exceptions when "%(jid)s" is used in a log format. [#68400](https://github.com/saltstack/salt/issues/68400)
- Fixed ssh_auth.present and ssh.absent to report changes if some key was added or removed when reading keys from a source file [#68403](https://github.com/saltstack/salt/issues/68403)
- Test loader now prevents .pyc files from being written during test run using
  sys.dont_write_bytecode = True. This results in 3x faster test execution and
  reduced IO operations [#68412](https://github.com/saltstack/salt/issues/68412)
- Fixes a issue where variable names were reversed when detecting domain and
  username from a username. [#68450](https://github.com/saltstack/salt/issues/68450)
- Changed the glob pattern for APT sources from `**/*.list` to `*.list`, in line
  with APT's default pattern in sources.list.d [#68475](https://github.com/saltstack/salt/issues/68475)
- Remove unwanted error log from aptpkg [#68485](https://github.com/saltstack/salt/issues/68485)
- Use the packaging library instead of the deprecated pkg_resources library for
  working with version to avoid a deprecation warning when running salt
  commands [#68487](https://github.com/saltstack/salt/issues/68487)
- Fixes issue with disk.tune passing incorrect args for read-only and read-write
  to blockdev.
  Improves argument and error handling in blockdev. [#68490](https://github.com/saltstack/salt/issues/68490)
- Enhance mod_data to Use Global Loader Extensions in salt-ssh [#68496](https://github.com/saltstack/salt/issues/68496)
- Fix race condition in Salt Syndic when multiple Syndic Masters return at the same time and the Master of Masters tries to write to the same file in the job cache. [#68508](https://github.com/saltstack/salt/issues/68508)
- Patch tornado for CVE-2023-28370 [#68529](https://github.com/saltstack/salt/issues/68529)
- Fixed some of the commands in the Contributing guide. [#68538](https://github.com/saltstack/salt/issues/68538)
- Fix check for non-blockdev devices in blockdev.tuned. Check always returned True
  previously, now actually checks with file.is_blkdev. [#68541](https://github.com/saltstack/salt/issues/68541)
- Added documentation and CLI help text for the --disable-keepalive option for
  salt-minion and salt-proxy, which disables the automatic restart mechanism
  when external process managers like systemd handle daemon restarts. [#68544](https://github.com/saltstack/salt/issues/68544)
- Upgrade relenv to 0.22.1 and fix Python 3.13 support

  - Updated relenv from 0.21.2 to 0.22.1
  - Fixed backports module import for Python 3.13 compatibility
  - Fixed RUSTFLAGS conflicts when compiling cryptography package
  - Fixed toolchain cache location for relenv 0.22.1
  - Added Obsoletes directives to prevent EPEL salt3006 package conflicts on Rocky 9 [#68552](https://github.com/saltstack/salt/issues/68552)
- Fixed minion process name pollution when multiprocessing is disabled [#68553](https://github.com/saltstack/salt/issues/68553)


* Thu Nov 20 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.9

# Fixed

- Render post/pre up/down and hwaddr options for debian-ip. See #58210 and #57820. [#58210](https://github.com/saltstack/salt/issues/58210)
- Fix event flood by ensuring we do not retry sending the event indefinitely to the Master of Masters. [#61845](https://github.com/saltstack/salt/issues/61845)
- Prevent `_pygit2.GitError: error loading known_hosts` with certain pygit2/libgit2 versions. [#64121](https://github.com/saltstack/salt/issues/64121)
- - salt-ssh now supports `state.sls_exists` (#66893) [#66893](https://github.com/saltstack/salt/issues/66893)
- Allows file.symlink to pass a string to cmd_check [#66939](https://github.com/saltstack/salt/issues/66939)
- Simplied and sped up `utils.json.find_json` function [#68258](https://github.com/saltstack/salt/issues/68258)
- Improved runtime performance of chocolatey.installed [#68308](https://github.com/saltstack/salt/issues/68308)
- Add check for vault in __opts__ var [#68312](https://github.com/saltstack/salt/issues/68312)
- Fixed user.present not having capability to persist home directory by adding persist_home flag. [#68322](https://github.com/saltstack/salt/issues/68322)
- Fixed pkg.installed state from showing warning if python rpm package not installed.
  Fixed pkg.installed state from showing warning and using slow process fork for version comparison when rpmdevtools is installed [#68341](https://github.com/saltstack/salt/issues/68341)
- Update pre-commit version used in github workflows to 4.3.0 [#68349](https://github.com/saltstack/salt/issues/68349)
- Fixed issue with network grains in interfaces that don't support ip4 or ip6 [#68355](https://github.com/saltstack/salt/issues/68355)
- Patch tornado for BDSA-2024-3438 [#68377](https://github.com/saltstack/salt/issues/68377)
- Patch tornado for BDSA-2024-3439 [#68379](https://github.com/saltstack/salt/issues/68379)
- Patch tornado for BDSA-2025-4215 [#68381](https://github.com/saltstack/salt/issues/68381)
- Patch tornado for BDSA-2024-9026 [#68383](https://github.com/saltstack/salt/issues/68383)
- * Update LZMA to 5.8.2
  * Update ncurses to 6.5
  * Update openssl to 3.5.4
  * Fix shebang creating to work with pip >=25.2
  * Fix python source hash checking
  * Update to recent python versions: 3.12.12, 3.11.14, 3.10.19 and 3.9.24. [#68385](https://github.com/saltstack/salt/issues/68385)
- Fixed the lgpo_reg error when reading REG_BINARY type data in the registry.pol
  file. [#68387](https://github.com/saltstack/salt/issues/68387)
- Fix gnupghome directory translation for some versions of git for windows, e.g. 2.51.0.windows.2 [#68392](https://github.com/saltstack/salt/issues/68392)
- Fix leak in SaltMessageServer where the unpacker was re-used on a stream disconnect. [#68394](https://github.com/saltstack/salt/issues/68394)
- * Upgrade relenv to 0.21.2:
    * We refresh the ensurepip bundle during every build so new runtimes ship with pip 25.2 and setuptools 80.9.0.
    * Windows builds now pull newer SQLite (3.50.4.0) and XZ (5.6.2) sources, copy in a missing XZ config file, and tweak SBOM metadata; the libexpat update is prepared but only runs on older maintenance releases.
    * Our downloader helpers log more clearly, know about more archive formats, and retry cleanly on transient errors.
    * pip’s changing install API is handled by runtime wrappers that adapt to all of the current signatures.
    * Linux verification tests install pip 25.2/25.3 before building setuptools to make sure that flow keeps working. [#68431](https://github.com/saltstack/salt/issues/68431)
- salt/utils/odict.py has been deprecated and will be removed in 3009. Use the standard library implementation instead. [#68440](https://github.com/saltstack/salt/issues/68440)
- Fixed issue in cmd execution module that always return "Invalid user" for domain users. [#68450](https://github.com/saltstack/salt/issues/68450)
- Fixed authentication protocol version downgrade vulnerability (CVE-2025-62349) by adding `minimum_auth_version` configuration option (default: 3) to prevent minions from bypassing security features through protocol downgrade attacks.

  **BREAKING CHANGE:** The default value enforces authentication protocol version 3 or higher. If upgrading a deployment with older minions that do not support protocol v3, you must temporarily set `minimum_auth_version: 0` in the master configuration before upgrading the master, then upgrade all minions before removing this override. [#68467](https://github.com/saltstack/salt/issues/68467)
- Fixed unsafe YAML loader usage in junos execution module (CVE-2025-62348) [#68469](https://github.com/saltstack/salt/issues/68469)
- Fixed ssh_auth regexp to handle key types with @ or . [#61299](https://github.com/saltstack/salt/issues/61299)
- Fixed a TypeError exception thrown by ssh_known_hosts.present when the specified user account does not exist [#62049](https://github.com/saltstack/salt/issues/62049)
- Fix runtime error on OpenBSD by adding support for the osfullname grain [#64189](https://github.com/saltstack/salt/issues/64189)
- Forward minion list events in Syndic cluster mode to enable proper job completion detection [#68319](https://github.com/saltstack/salt/issues/68319)
- Fixed ssh_auth.present and ssh.absent to report changes if some key was added or removed when reading keys from a source file [#68403](https://github.com/saltstack/salt/issues/68403)
- Test loader now prevents .pyc files from being written during test run using
  sys.dont_write_bytecode = True. This results in 3x faster test execution and
  reduced IO operations [#68412](https://github.com/saltstack/salt/issues/68412)
- Fixes a issue where variable names were reversed when detecting domain and
  username from a username. [#68450](https://github.com/saltstack/salt/issues/68450)
- Changed the glob pattern for APT sources from `**/*.list` to `*.list`, in line
  with APT's default pattern in sources.list.d [#68475](https://github.com/saltstack/salt/issues/68475)
- Remove unwanted error log from aptpkg [#68485](https://github.com/saltstack/salt/issues/68485)
- Use the packaging library instead of the deprecated pkg_resources library for
  working with version to avoid a deprecation warning when running salt
  commands [#68487](https://github.com/saltstack/salt/issues/68487)
- Fixes issue with disk.tune passing incorrect args for read-only and read-write
  to blockdev.
  Improves argument and error handling in blockdev. [#68490](https://github.com/saltstack/salt/issues/68490)
- Enhance mod_data to Use Global Loader Extensions in salt-ssh [#68496](https://github.com/saltstack/salt/issues/68496)
- Fix race condition in Salt Syndic when multiple Syndic Masters return at the same time and the Master of Masters tries to write to the same file in the job cache. [#68508](https://github.com/saltstack/salt/issues/68508)
- Patch tornado for CVE-2023-28370 [#68529](https://github.com/saltstack/salt/issues/68529)
- Fixed some of the commands in the Contributing guide. [#68538](https://github.com/saltstack/salt/issues/68538)
- Fix check for non-blockdev devices in blockdev.tuned. Check always returned True
  previously, now actually checks with file.is_blkdev. [#68541](https://github.com/saltstack/salt/issues/68541)
- Added documentation and CLI help text for the --disable-keepalive option for
  salt-minion and salt-proxy, which disables the automatic restart mechanism
  when external process managers like systemd handle daemon restarts. [#68544](https://github.com/saltstack/salt/issues/68544)
- Upgrade relenv to 0.22.1 and fix Python 3.13 support

  - Updated relenv from 0.21.2 to 0.22.1
  - Fixed backports module import for Python 3.13 compatibility
  - Fixed RUSTFLAGS conflicts when compiling cryptography package
  - Fixed toolchain cache location for relenv 0.22.1
  - Added Obsoletes directives to prevent EPEL salt3006 package conflicts on Rocky 9 [#68552](https://github.com/saltstack/salt/issues/68552)
- Fixed minion process name pollution when multiprocessing is disabled [#68553](https://github.com/saltstack/salt/issues/68553)


* Thu Nov 20 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.17

# Fixed

- Render post/pre up/down and hwaddr options for debian-ip. See #58210 and #57820. [#58210](https://github.com/saltstack/salt/issues/58210)
- Fix event flood by ensuring we do not retry sending the event indefinitely to the Master of Masters. [#61845](https://github.com/saltstack/salt/issues/61845)
- Prevent `_pygit2.GitError: error loading known_hosts` with certain pygit2/libgit2 versions. [#64121](https://github.com/saltstack/salt/issues/64121)
- - salt-ssh now supports `state.sls_exists` (#66893) [#66893](https://github.com/saltstack/salt/issues/66893)
- Allows file.symlink to pass a string to cmd_check [#66939](https://github.com/saltstack/salt/issues/66939)
- Simplied and sped up `utils.json.find_json` function [#68258](https://github.com/saltstack/salt/issues/68258)
- Improved runtime performance of chocolatey.installed [#68308](https://github.com/saltstack/salt/issues/68308)
- Add check for vault in __opts__ var [#68312](https://github.com/saltstack/salt/issues/68312)
- Fixed user.present not having capability to persist home directory by adding persist_home flag. [#68322](https://github.com/saltstack/salt/issues/68322)
- Fixed pkg.installed state from showing warning if python rpm package not installed.
  Fixed pkg.installed state from showing warning and using slow process fork for version comparison when rpmdevtools is installed [#68341](https://github.com/saltstack/salt/issues/68341)
- Update pre-commit version used in github workflows to 4.3.0 [#68349](https://github.com/saltstack/salt/issues/68349)
- Fixed issue with network grains in interfaces that don't support ip4 or ip6 [#68355](https://github.com/saltstack/salt/issues/68355)
- Patch tornado for BDSA-2024-3438 [#68377](https://github.com/saltstack/salt/issues/68377)
- Patch tornado for BDSA-2024-3439 [#68379](https://github.com/saltstack/salt/issues/68379)
- Patch tornado for BDSA-2025-4215 [#68381](https://github.com/saltstack/salt/issues/68381)
- Patch tornado for BDSA-2024-9026 [#68383](https://github.com/saltstack/salt/issues/68383)
- * Update LZMA to 5.8.2
  * Update ncurses to 6.5
  * Update openssl to 3.5.4
  * Fix shebang creating to work with pip >=25.2
  * Fix python source hash checking
  * Update to recent python versions: 3.12.12, 3.11.14, 3.10.19 and 3.9.24. [#68385](https://github.com/saltstack/salt/issues/68385)
- Fixed the lgpo_reg error when reading REG_BINARY type data in the registry.pol
  file. [#68387](https://github.com/saltstack/salt/issues/68387)
- Fix leak in SaltMessageServer where the unpacker was re-used on a stream disconnect. [#68394](https://github.com/saltstack/salt/issues/68394)
- * Upgrade relenv to 0.21.2:
    * We refresh the ensurepip bundle during every build so new runtimes ship with pip 25.2 and setuptools 80.9.0.
    * Windows builds now pull newer SQLite (3.50.4.0) and XZ (5.6.2) sources, copy in a missing XZ config file, and tweak SBOM metadata; the libexpat update is prepared but only runs on older maintenance releases.
    * Our downloader helpers log more clearly, know about more archive formats, and retry cleanly on transient errors.
    * pip’s changing install API is handled by runtime wrappers that adapt to all of the current signatures.
    * Linux verification tests install pip 25.2/25.3 before building setuptools to make sure that flow keeps working. [#68431](https://github.com/saltstack/salt/issues/68431)
- salt/utils/odict.py has been deprecated and will be removed in 3009. Use the standard library implementation instead. [#68440](https://github.com/saltstack/salt/issues/68440)
- Fixed issue in cmd execution module that always return "Invalid user" for domain users. [#68450](https://github.com/saltstack/salt/issues/68450)
- Fixed authentication protocol version downgrade vulnerability (CVE-2025-62349) by adding `minimum_auth_version` configuration option (default: 3) to prevent minions from bypassing security features through protocol downgrade attacks.

  **BREAKING CHANGE:** The default value enforces authentication protocol version 3 or higher. If upgrading a deployment with older minions that do not support protocol v3, you must temporarily set `minimum_auth_version: 0` in the master configuration before upgrading the master, then upgrade all minions before removing this override. [#68467](https://github.com/saltstack/salt/issues/68467)
- Fixed unsafe YAML loader usage in junos execution module (CVE-2025-62348) [#68469](https://github.com/saltstack/salt/issues/68469)


* Thu Sep 18 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.8

# Fixed

- Fixed an issue with the win_network salt.util to select interfaces
  by name instead of description. [#58138](https://github.com/saltstack/salt/issues/58138)
- Fixes debug logging for master AES and session keys to be consistent across crypt.AsyncAuth._authenticate() and crypt.SAuth.authenticate(). Now differentiates between master key rotation and session key rotation. [#68113](https://github.com/saltstack/salt/issues/68113)
- Fix filedescriptor out of range problem in tcp.py by replacing select.sect() with the higher-level selectors API [#68136](https://github.com/saltstack/salt/issues/68136)
- Fixed loader handling of already loaded modules, thereby fixed an interaction between the `x509_v2` state module and any following state having a `prereq` on a `file` state [#68281](https://github.com/saltstack/salt/issues/68281)
- Fix potential race conditions an memory usage in zeromq request client
  tranport. [#68297](https://github.com/saltstack/salt/issues/68297)
- Revert change to store cargo home as a temporary directory [#68311](https://github.com/saltstack/salt/issues/68311)
- Update openssl FIPS provider to 3.1.2 (certified until 2030) [#68317](https://github.com/saltstack/salt/issues/68317)

# Added

- Added the ability to pass the context to pyobjects renderer [#68224](https://github.com/saltstack/salt/issues/68224)


* Thu Aug 28 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.7

# Changed

- cmdmod: invoke a shell only with cmd.shell or when using the shell parameter
  cmdmod: run PowerShell scripts via -File instead of -Command
  cmdmod: allow passing args as a list for cmd.script
  cmdmod: return an error when running a bad command with cmd.powershell [#68156](https://github.com/saltstack/salt/issues/68156)

# Fixed

- Fixes issue with the `minion.restart` function not working with systemd. Will
  now detect if the system is using systemd or is a Windows system and use
  `service.restart` instead. [#46255](https://github.com/saltstack/salt/issues/46255)
- Fixed max_depth not respected in file.directory state [#55306](https://github.com/saltstack/salt/issues/55306)
- Updated CLI examples in docs to conform to bash syntax. Standardized
  documentation on Windows modules to Google Style Python Docstrings. [#63856](https://github.com/saltstack/salt/issues/63856)
- Ensure the right HOME environment value is set during Pygit2 remote initialization. [#64121](https://github.com/saltstack/salt/issues/64121)
- Fix sync_renderers failure when the custom renderer is specified via config [#66453](https://github.com/saltstack/salt/issues/66453)
- modules.aptpkg: correct handling of foreign-arch packages [#66940](https://github.com/saltstack/salt/issues/66940)
- Ensure network connections are cleanly closed in ipc and tcp transports [#67076](https://github.com/saltstack/salt/issues/67076)
- cmdmod: fix special character handling on Windows [#68096](https://github.com/saltstack/salt/issues/68096)
- cmdmod: fix quotation handling with Windows and Powershell [#68118](https://github.com/saltstack/salt/issues/68118)
- Fix `test mode` causing unintended execution when non-boolean values are passed. [#68121](https://github.com/saltstack/salt/issues/68121)
- Fixed ssh_known_hosts.present failure when ssh host keys changed [#68132](https://github.com/saltstack/salt/issues/68132)
- Revert 'ipc_write_timeout' change (3006.13) due to multiple reports of this change causing instability [#68151](https://github.com/saltstack/salt/issues/68151)
- cmdmod: handle cases where the temp script is not removed with cmd.script [#68156](https://github.com/saltstack/salt/issues/68156)
- win_runas: fix output decoding exceptions
  win_runas: ensure opened handles are closed [#68157](https://github.com/saltstack/salt/issues/68157)
- Fixed MinionManager.stop() to allow processing of minion event bus when called, to allow jobs returns from `service.restart salt-minion no_block=True` to reach
  master. [#68183](https://github.com/saltstack/salt/issues/68183)
- grains.disks: fix exception with incompatible output of Get-PhysicalDisk [#68184](https://github.com/saltstack/salt/issues/68184)
- Log a useful error if the minion's key is overwritten with bad data; instead of a traceback. [#68190](https://github.com/saltstack/salt/issues/68190)
- win_lgpo_reg only applies user settings to the registry.pol file. It no longer
  applies those same settings to the user registry. Those settings will be applied
  to all users the next time they log in. [#68191](https://github.com/saltstack/salt/issues/68191)
- salt.crypt.AsyncAuth and salt.crypt.SAuth read the private key from the
  filesystem a single time. [#68195](https://github.com/saltstack/salt/issues/68195)
- Modifies systemd_service.{restart,stop} to default to using no_block=True when the service being stopped or restarted is the salt-minion. [#68212](https://github.com/saltstack/salt/issues/68212)
- Upgrade onedir relenv to 0.20.5:
    - Update gdbm from 1.25 to 1.26
    - Update libffi from 3.5.1 to 3.5.2
    - Update readline from 8.2.13 to 8.3
    - Update sqlite from 3.50.2 to 3.50.4
    - Update sqlite on windows from 3.40.1 to 0.35.4 (CVE-2025-6965) [#68291](https://github.com/saltstack/salt/issues/68291)

# Added

- Added a new `force` option to pkg.install on Windows to force the installer
  to run even if the package is already installed [#68102](https://github.com/saltstack/salt/issues/68102)
- win_runas: support cmdmod parameters bg, env, redirect_stderr, timeout [#68157](https://github.com/saltstack/salt/issues/68157)
- Adds support for creating a scheduled job to restart the minion if the initial
  attempt at restarting it via `minion.restart` has failed. [#68225](https://github.com/saltstack/salt/issues/68225)


* Thu Jul 10 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.6

# Fixed

- Onedir packages include relenv 0.19.4.
  - Update sqlite to 3500200
  - Update libffi to 3.5.1
  - Update python 3.13 to 3.13.5
  - Load default openssl modules when no system openssl binary exists [#68014](https://github.com/saltstack/salt/issues/68014)
- pkgrepo.managed not applying changes / account for 'name' attr being part of the state [#68107](https://github.com/saltstack/salt/issues/68107)
- Fix `test mode` causing unintended execution when non-boolean values are passed. [#68121](https://github.com/saltstack/salt/issues/68121)


* Thu Jun 26 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.5

# Fixed

- Zeromq RequestServer continues to serve requests after encountering an
  un-handled exception [#66519](https://github.com/saltstack/salt/issues/66519)
- * Added support for `icmpv6-type` to salt.modules.nftables [#67882](https://github.com/saltstack/salt/issues/67882)


* Thu Aug 28 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.15

# Changed

- cmdmod: invoke a shell only with cmd.shell or when using the shell parameter
  cmdmod: run PowerShell scripts via -File instead of -Command
  cmdmod: allow passing args as a list for cmd.script
  cmdmod: return an error when running a bad command with cmd.powershell [#68156](https://github.com/saltstack/salt/issues/68156)

# Fixed

- Fixes issue with the `minion.restart` function not working with systemd. Will
  now detect if the system is using systemd or is a Windows system and use
  `service.restart` instead. [#46255](https://github.com/saltstack/salt/issues/46255)
- Fixed max_depth not respected in file.directory state [#55306](https://github.com/saltstack/salt/issues/55306)
- Updated CLI examples in docs to conform to bash syntax. Standardized
  documentation on Windows modules to Google Style Python Docstrings. [#63856](https://github.com/saltstack/salt/issues/63856)
- Ensure the right HOME environment value is set during Pygit2 remote initialization. [#64121](https://github.com/saltstack/salt/issues/64121)
- Ensure network connections are cleanly closed in ipc and tcp transports [#67076](https://github.com/saltstack/salt/issues/67076)
- cmdmod: fix special character handling on Windows [#68096](https://github.com/saltstack/salt/issues/68096)
- cmdmod: fix quotation handling with Windows and Powershell [#68118](https://github.com/saltstack/salt/issues/68118)
- Fixed ssh_known_hosts.present failure when ssh host keys changed [#68132](https://github.com/saltstack/salt/issues/68132)
- Revert 'ipc_write_timeout' change (3006.13) due to multiple reports of this change causing instability [#68151](https://github.com/saltstack/salt/issues/68151)
- cmdmod: handle cases where the temp script is not removed with cmd.script [#68156](https://github.com/saltstack/salt/issues/68156)
- Fixed MinionManager.stop() to allow processing of minion event bus when called, to allow jobs returns from `service.restart salt-minion no_block=True` to reach
  master. [#68183](https://github.com/saltstack/salt/issues/68183)
- grains.disks: fix exception with incompatible output of Get-PhysicalDisk [#68184](https://github.com/saltstack/salt/issues/68184)
- Log a useful error if the minion's key is overwritten with bad data; instead of a traceback. [#68190](https://github.com/saltstack/salt/issues/68190)
- win_lgpo_reg only applies user settings to the registry.pol file. It no longer
  applies those same settings to the user registry. Those settings will be applied
  to all users the next time they log in. [#68191](https://github.com/saltstack/salt/issues/68191)
- salt.crypt.AsyncAuth and salt.crypt.SAuth read the private key from the
  filesystem a single time. [#68195](https://github.com/saltstack/salt/issues/68195)
- Modifies systemd_service.{restart,stop} to default to using no_block=True when the service being stopped or restarted is the salt-minion. [#68212](https://github.com/saltstack/salt/issues/68212)
- Upgrade onedir relenv to 0.20.5:
    - Update gdbm from 1.25 to 1.26
    - Update libffi from 3.5.1 to 3.5.2
    - Update readline from 8.2.13 to 8.3
    - Update sqlite from 3.50.2 to 3.50.4
    - Update sqlite on windows from 3.40.1 to 0.35.4 (CVE-2025-6965) [#68291](https://github.com/saltstack/salt/issues/68291)

# Added

- Added a new `force` option to pkg.install on Windows to force the installer
  to run even if the package is already installed [#68102](https://github.com/saltstack/salt/issues/68102)
- Adds support for creating a scheduled job to restart the minion if the initial
  attempt at restarting it via `minion.restart` has failed. [#68225](https://github.com/saltstack/salt/issues/68225)


* Thu Jul 10 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.14

# Fixed

- Onedir packages include relenv 0.19.4.
  - Update sqlite to 3500200
  - Update libffi to 3.5.1
  - Update python 3.13 to 3.13.5
  - Load default openssl modules when no system openssl binary exists [#68014](https://github.com/saltstack/salt/issues/68014)
- pkgrepo.managed not applying changes / account for 'name' attr being part of the state [#68107](https://github.com/saltstack/salt/issues/68107)
- Fix `test mode` causing unintended execution when non-boolean values are passed. [#68121](https://github.com/saltstack/salt/issues/68121)


* Thu Jun 26 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.13

# Fixed

- Return target path for symlinks and junctions on Windows [#54484](https://github.com/saltstack/salt/issues/54484)
- Fixed `Pillar payload signature failed to validate` error on master failover [#62318](https://github.com/saltstack/salt/issues/62318)
- Fixes an issue running powershell commands that begin with parenthesis or
  other commands that do not require an ampersand [#67190](https://github.com/saltstack/salt/issues/67190)
- Make x509 module compatible with M2Crypto 0.44.0. [#67782](https://github.com/saltstack/salt/issues/67782)
- Fix syndic event forwarding [#67936](https://github.com/saltstack/salt/issues/67936)
- Fix cp.push module function and its integration test [#67941](https://github.com/saltstack/salt/issues/67941)
- logging regression: fix loglines/findCaller introspection [#68057](https://github.com/saltstack/salt/issues/68057)
- Handle git@github.com:saltstack/salt style remotes in remote url validation [#68069](https://github.com/saltstack/salt/issues/68069)
- Fix GitFS file_find for file in sub-directories [#68072](https://github.com/saltstack/salt/issues/68072)
- Fix install in Ubuntu 24.04 noble Docker by using groupadd rather than addgroup. [#68073](https://github.com/saltstack/salt/issues/68073)
- Token validation removes token from request handler payload [#68076](https://github.com/saltstack/salt/issues/68076)
- Fix minion connectivity issues by ensuring auth notices refreshed session token [#68079](https://github.com/saltstack/salt/issues/68079)
- Fix file_recv path verification to allow subdirs used by cp.push [#68087](https://github.com/saltstack/salt/issues/68087)
- Fixes an issue on Windows where cmd.run wasn't handling commands sent as a
  list [#68095](https://github.com/saltstack/salt/issues/68095)
- Disconnect ipc clients that stop consuming [#68114](https://github.com/saltstack/salt/issues/68114)


* Thu Jun 12 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.4

# Fixed

- CVE-2024-38822
  Multiple methods in the salt master skip minion token validation. Therefore a misbehaving minion can impersonate another minion.

  CVSS 2.7 V:N/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N

  CVE-2024-38823
  Salt's request server is vulnerable to replay attacks when not using a TLS encrypted transport.

  CVSS Score 2.7 AV:N/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N

  CVE-2024-38824
  Directory traversal vulnerability in recv_file method allows arbitrary files to be written to the master cache directory.

  CVSS Score 9.6 AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N

  CVE-2024-38825
  The salt.auth.pki module does not properly authenticate callers. The "password" field contains a public certificate which is validated against a CA certificate by the module. This is not pki authentication, as the caller does not need access to the corresponding private key for the authentication attempt to be accepted.

  CVSS Score 6.4 AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:L/A:N

  CVE-2025-22236
  Minion event bus authorization bypass. An attacker with access to a minion key can craft a message which may be able to execute a job on other minions (>= 3007.0).

  CVSS 8.1 AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:L

  CVE-2025-22237
  An attacker with access to a minion key can exploit the 'on demand' pillar functionality with a specially crafted git url which could cause and arbitrary command to be run on the master with the same privileges as the master process.

  CVSS 6.7 AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H

  CVE-2025-22238
  Directory traversal attack in minion file cache creation. The master's default cache is vulnerable to a directory traversal attack. Which could be leveraged to write or overwrite 'cache' files outside of the cache directory.

  CVSS 4.2 AV:L/AC:L/PR:H/UI:R/S:U/C:N/I:H/A:N

  CVE-2025-22239
  Arbitrary event injection on Salt Master. The master's "_minion_event" method can be used by and authorized minion to send arbitrary events onto the master's event bus.

  CVSS 8.1 AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:L

  CVE-2025-22240
  Arbitrary directory creation or file deletion. In the find_file method of the GitFS class, a path is created using os.path.join using unvalidated input from the “tgt_env” variable. This can be exploited by an attacker to delete any file on the Master's process has permissions to

  CVSS 6.3 AV:L/AC:H/PR:H/UI:R/S:U/C:H/I:H/A:H

  CVE-2025-22241
  File contents overwrite the VirtKey class is called when “on-demand pillar” data is requested and uses un-validated input to create paths to the “pki directory”. The functionality is used to auto-accept Minion authentication keys based on a pre-placed “authorization file” at a specific location and is present in the default configuration.

  CVSS 5.6 AV:L/AC:H/PR:H/UI:R/S:U/C:H/I:H/A:N

  CVE-2025-22242
  Worker process denial of service through file read operation. .A vulnerability exists in the Master's “pub_ret” method which is exposed to all minions. The un-sanitized input value “jid” is used to construct a path which is then opened for reading. An attacker could exploit this vulnerabilities by attempting to read from a filename that will not return any data, e.g. by targeting a pipe node on the proc file system.

  CVSS 5.6 AV:L/AC:H/PR:H/UI:R/S:U/C:H/I:N/A:H

  This release also includes sqlite 3.50.1 to address CVE-2025-29087 [#68033](https://github.com/saltstack/salt/issues/68033)


* Thu Jun 12 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.12

# Fixed

- CVE-2024-38822
  Multiple methods in the salt master skip minion token validation. Therefore a misbehaving minion can impersonate another minion.

  CVSS 2.7 V:N/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N

  CVE-2024-38823
  Salt's request server is vulnerable to replay attacks when not using a TLS encrypted transport.

  CVSS Score 2.7 AV:N/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N

  CVE-2024-38824
  Directory traversal vulnerability in recv_file method allows arbitrary files to be written to the master cache directory.

  CVSS Score 9.6 AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N

  CVE-2024-38825
  The salt.auth.pki module does not properly authenticate callers. The "password" field contains a public certificate which is validated against a CA certificate by the module. This is not pki authentication, as the caller does not need access to the corresponding private key for the authentication attempt to be accepted.

  CVSS Score 6.4 AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:L/A:N

  CVE-2025-22236
  Minion event bus authorization bypass. An attacker with access to a minion key can craft a message which may be able to execute a job on other minions (>= 3007.0).

  CVSS 8.1 AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:L

  CVE-2025-22237
  An attacker with access to a minion key can exploit the 'on demand' pillar functionality with a specially crafted git url which could cause and arbitrary command to be run on the master with the same privileges as the master process.

  CVSS 6.7 AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H

  CVE-2025-22238
  Directory traversal attack in minion file cache creation. The master's default cache is vulnerable to a directory traversal attack. Which could be leveraged to write or overwrite 'cache' files outside of the cache directory.

  CVSS 4.2 AV:L/AC:L/PR:H/UI:R/S:U/C:N/I:H/A:N

  CVE-2025-22239
  Arbitrary event injection on Salt Master. The master's "_minion_event" method can be used by and authorized minion to send arbitrary events onto the master's event bus.

  CVSS 8.1 AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:L

  CVE-2025-22240
  Arbitrary directory creation or file deletion. In the find_file method of the GitFS class, a path is created using os.path.join using unvalidated input from the “tgt_env” variable. This can be exploited by an attacker to delete any file on the Master's process has permissions to

  CVSS 6.3 AV:L/AC:H/PR:H/UI:R/S:U/C:H/I:H/A:H

  CVE-2025-22241
  File contents overwrite the VirtKey class is called when “on-demand pillar” data is requested and uses un-validated input to create paths to the “pki directory”. The functionality is used to auto-accept Minion authentication keys based on a pre-placed “authorization file” at a specific location and is present in the default configuration.

  CVSS 5.6 AV:L/AC:H/PR:H/UI:R/S:U/C:H/I:H/A:N

  CVE-2025-22242
  Worker process denial of service through file read operation. .A vulnerability exists in the Master's “pub_ret” method which is exposed to all minions. The un-sanitized input value “jid” is used to construct a path which is then opened for reading. An attacker could exploit this vulnerabilities by attempting to read from a filename that will not return any data, e.g. by targeting a pipe node on the proc file system.

  CVSS 5.6 AV:L/AC:H/PR:H/UI:R/S:U/C:H/I:N/A:H

  This release also includes sqlite 3.50.1 to address CVE-2025-29087 [#68033](https://github.com/saltstack/salt/issues/68033)


* Wed Jun 04 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.3

# Added

- Added the ability to configure the cluster event port and added documentation for it [#66627](https://github.com/saltstack/salt/issues/66627)


* Mon Jun 02 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.11

# Fixed

- Fixes an issue with cmd.run where the command is a built-in command and must be
  run with cmd. [#54821](https://github.com/saltstack/salt/issues/54821)
- Show a better error when running cmd.* commands using runas and the
  runas user does not exist [#56680](https://github.com/saltstack/salt/issues/56680)
- Make sure the comment field is populated when test=True for the reg state [#65514](https://github.com/saltstack/salt/issues/65514)
- Fixed result detection of module.run from returned dict [#65842](https://github.com/saltstack/salt/issues/65842)
- Fix an issue with the osrelease_info grain that was displaying empty strings [#66936](https://github.com/saltstack/salt/issues/66936)
- support retry: True as per docs [#67049](https://github.com/saltstack/salt/issues/67049)
- Fixed if arguments are passed to the key delete all, -D, it will throw an error [#67903](https://github.com/saltstack/salt/issues/67903)
- Set virtual grain for docker using systemd and virt-what [#67905](https://github.com/saltstack/salt/issues/67905)
- Remove broken salt-common bash-completion links in root filesystem [#67915](https://github.com/saltstack/salt/issues/67915)
- Fix refresh of osrelease and related grains on Python 3.10+ [#67932](https://github.com/saltstack/salt/issues/67932)
- Re-add -oProxyCommand to ssh gateway arguments when ssh_gateway is present. [#67934](https://github.com/saltstack/salt/issues/67934)
- Repair Git state comment formatting [#67944](https://github.com/saltstack/salt/issues/67944)
- Use a Jscript Custom Action to stop the salt-minion service on Windows instead
  of a VBscript Custom Action due to future deprecation and security issues [#67982](https://github.com/saltstack/salt/issues/67982)


* Tue May 13 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.2

# Fixed

- Fixed `salt.*.get` shorthand via Salt-SSH [#41794](https://github.com/saltstack/salt/issues/41794)
- Show a better error when running cmd.* commands using runas and the
  runas user does not exist [#56680](https://github.com/saltstack/salt/issues/56680)
- Await on zmq monitor socket's poll method to fix publish server reliability in
  environment's with a large amount of minions. [#65265](https://github.com/saltstack/salt/issues/65265)
- Fixed result detection of module.run from returned dict [#65842](https://github.com/saltstack/salt/issues/65842)
- Fix vault module doesn't respect `server.verify` option during unwrap if verify is set to `False` or CA file on the disk [#66213](https://github.com/saltstack/salt/issues/66213)
- Make sure the master_event_pub.ipc file has correct reed/write permissions for salt group. [#66228](https://github.com/saltstack/salt/issues/66228)
- fix #66194: Exchange HTTPClient by AsyncHTTPClient in salt.utils.http [#66330](https://github.com/saltstack/salt/issues/66330)
- Fixed `salt.*.*` attribute syntax for non-Jinja renderers via Salt-SSH [#66376](https://github.com/saltstack/salt/issues/66376)
- Add integration tests for startup_states [#66592](https://github.com/saltstack/salt/issues/66592)
- Fixed accessing wrapper modules in Salt-SSH Jinja templates via attribute syntax [#66600](https://github.com/saltstack/salt/issues/66600)
- Fixed Salt-SSH crash when key deploy is skipped manually [#66610](https://github.com/saltstack/salt/issues/66610)
- Fixed gpp module trust level reporting/crash with python-gnupg>=0.5.1 [#66685](https://github.com/saltstack/salt/issues/66685)
- Update master cluster tutorial haproxy config with proper timeouts for publish port [#66888](https://github.com/saltstack/salt/issues/66888)
- transports.tcp: ensure pull path is being used before attempting chmod.
  The fix prevents an unnecessary traceback when the TCP transport is
  not using unix sockets. No functionaly has changed as the traceback
  occurs when an async task was about to exit anyway. [#66931](https://github.com/saltstack/salt/issues/66931)
- Fix an issue with the osrelease_info grain that was displaying empty strings [#66936](https://github.com/saltstack/salt/issues/66936)
- Added support for MAINTAIN (m) privilege to salt.modules.postgres [#66962](https://github.com/saltstack/salt/issues/66962)
- make file.symlink/_symlink_check() respect follow_symlinks [#66980](https://github.com/saltstack/salt/issues/66980)
- Salt master waits for publish servers while starting up. [#66993](https://github.com/saltstack/salt/issues/66993)
- Fix a stacktrace on Windows with pkg.installed and test=True. The
  `pkg.list_repo_pkgs` function does not exist on Windows. This uses the
  `pkg.list_available` function instead for Windows. [#67171](https://github.com/saltstack/salt/issues/67171)
- Made the correct PKI directory available for key_cache use [#67185](https://github.com/saltstack/salt/issues/67185)
- Removed support for end of life Python 3.8 from pre-commit and requirements [#67730](https://github.com/saltstack/salt/issues/67730)
- Fixed if arguments are passed to the key delete all, -D, it will throw an error [#67903](https://github.com/saltstack/salt/issues/67903)
- Set virtual grain for docker using systemd and virt-what [#67905](https://github.com/saltstack/salt/issues/67905)
- Remove broken salt-common bash-completion links in root filesystem [#67915](https://github.com/saltstack/salt/issues/67915)
- Fix refresh of osrelease and related grains on Python 3.10+ [#67932](https://github.com/saltstack/salt/issues/67932)
- Re-add -oProxyCommand to ssh gateway arguments when ssh_gateway is present. [#67934](https://github.com/saltstack/salt/issues/67934)
- Repair Git state comment formatting [#67944](https://github.com/saltstack/salt/issues/67944)
- Use a Jscript Custom Action to stop the salt-minion service on Windows instead
  of a VBscript Custom Action due to future deprecation and security issues [#67982](https://github.com/saltstack/salt/issues/67982)


* Wed Mar 19 2025 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.10

# Removed

- Remove psutil_compat.py file, which should have been removed when RHEL 6 EOL [#66467](https://github.com/saltstack/salt/issues/66467)
- Removed dependency on bsdmainutils package for Debian and Ubuntu [#67184](https://github.com/saltstack/salt/issues/67184)

# Deprecated

- Drop Arch Linux support [#66886](https://github.com/saltstack/salt/issues/66886)
- Removed support for end of life Python 3.7 and 3.8 from pre-commit and requirements [#67729](https://github.com/saltstack/salt/issues/67729)

# Fixed

- Commands on Windows are now prefixed with ``cmd /c`` so that compound
  commands (commands separated by ``&&``) run properly when using ``runas`` [#44736](https://github.com/saltstack/salt/issues/44736)
- Issue 58969: Fixes an issue with `saltclass.expand_classes_in_order`
  function where it was losing nested classes states during class
  expansion. The logic now use `salt.utils.odict.OrderedDict` to keep
  the inclusion ordering. [#58969](https://github.com/saltstack/salt/issues/58969)
- Fix issue with RunAs on Windows so that usernames of all numeric characters
  are handled as strings [#59344](https://github.com/saltstack/salt/issues/59344)
- Fixed an issue on Windows where checking success_retcodes when using the
  runas parameter would fail. Now success_retcodes are checked correctly [#59977](https://github.com/saltstack/salt/issues/59977)
- Fix an issue with cmd.script in Windows so that the exit code from a script will
  be passed through to the retcode of the state [#60884](https://github.com/saltstack/salt/issues/60884)
- Fixed an issue uninstalling packages on Windows using pkg.removed where there
  are multiple versions of the same software installed [#61001](https://github.com/saltstack/salt/issues/61001)
- Ensure file clients for runner, wheel, local and caller are available from the client_cache if called upon. [#61416](https://github.com/saltstack/salt/issues/61416)
- Convert stdin string to bytes regardless of stdin_raw_newlines [#62501](https://github.com/saltstack/salt/issues/62501)
- Issue 63933: Fixes an issue with `saltclass.expanded_dict_from_minion`
  function where it was passing a reference to minion `dict` which was
  overridden by nested classes during class expansion. Copy the node
  definition with `copy.deepcopy` instead of passing a reference. [#63933](https://github.com/saltstack/salt/issues/63933)
- Fixed an intermittent issue with file.recurse where the state would
  report failure even on success. Makes sure symlinks are created
  after the target file is created [#64630](https://github.com/saltstack/salt/issues/64630)
- The 'profile' outputter does not crash with incorrectly formatted data [#65104](https://github.com/saltstack/salt/issues/65104)
- Updating version comparison for rpm and removed obsolete comparison methods for rpms [#65443](https://github.com/saltstack/salt/issues/65443)
- Fix batch mode hang indefinitely in some scenarios [#66249](https://github.com/saltstack/salt/issues/66249)
- Applying `selinux.fcontext_policy_present` to a shorter path than an existing entry now works [#66252](https://github.com/saltstack/salt/issues/66252)
- Correct bash-completion for Debian / Ubuntu [#66560](https://github.com/saltstack/salt/issues/66560)
- Fix minion config option startup_states [#66592](https://github.com/saltstack/salt/issues/66592)
- Fixed an issue with cmd.run with requirements when the shell is not the
  default [#66596](https://github.com/saltstack/salt/issues/66596)
- Fixes an issue when getting account names using the get_name function in the
  win_dacl.py salt util. Capability SIDs return ``None``. SIDs for deleted
  accounts return the SID. SIDs for domain accounts where the system is not
  connected to the domain return the SID. [#66637](https://github.com/saltstack/salt/issues/66637)
- Fixed an issue where ``status.master`` wasn't detecting a connection to the
  specified master properly [#66716](https://github.com/saltstack/salt/issues/66716)
- Fixed ``win_wua.available`` when some of the update objects are empty CDispatch
  objects. The ``available`` function no longer crashes [#66718](https://github.com/saltstack/salt/issues/66718)
- Clean up multiprocessing file handles on minion [#66726](https://github.com/saltstack/salt/issues/66726)
- Fixed nacl.keygen for not yet existing sk_file or pk_file [#66772](https://github.com/saltstack/salt/issues/66772)
- fix yaml output [#66783](https://github.com/saltstack/salt/issues/66783)
- Fixed an issue where enabling `grain_opts` in the minion config would cause
  some core grains to be overwritten. [#66784](https://github.com/saltstack/salt/issues/66784)
- Fix an issue where files created using `salt.utils.atomicile.atomic_open()`
  were created with restrictive permissions instead of respecting the umask. [#66786](https://github.com/saltstack/salt/issues/66786)
- Fix bad async_method name on AsyncPubClient class [#66789](https://github.com/saltstack/salt/issues/66789)
- Ensure Manjaro ARM reports the correct os_family of Arch. [#66796](https://github.com/saltstack/salt/issues/66796)
- Removed ``salt.utils.data.decode`` usage from the fileserver. This function was
  necessary to support Python 2. This speeds up loading the list cache by 80-90x. [#66835](https://github.com/saltstack/salt/issues/66835)
- Issue 66837: Fixes an issue with the `network.local_port_tcp` function
  where it was not parsing the IPv4 mapped IPv6 address correctly. The
  ``::ffff:`` is now removed and only the IP address is returned. [#66837](https://github.com/saltstack/salt/issues/66837)
- Better handling output of `systemctl --version` with salt.grains.core._systemd [#66856](https://github.com/saltstack/salt/issues/66856)
- Upgrade relenv to 0.17.3. This release includes python 3.10.15, openssl 3.2.3,
  and fixes for pip 24.2. [#66858](https://github.com/saltstack/salt/issues/66858)
- Remove caching of 'systemctl status' in systemd_service to fix automatic daemon-reload for repeated invocations. [#66864](https://github.com/saltstack/salt/issues/66864)
- Added cryptogrpahy back to base.in requirements as a dependency [#66883](https://github.com/saltstack/salt/issues/66883)
- Remove "perms" from `linux_acl.list_absent()` documentation [#66891](https://github.com/saltstack/salt/issues/66891)
- Ensure minion start event coroutines are run [#66932](https://github.com/saltstack/salt/issues/66932)
- Allow for secure-boot efivars directory having SecureBoot-xxx files, not directories with a data file [#66955](https://github.com/saltstack/salt/issues/66955)
- Removed the usage of wmic to get the disk and iscsi grains for Windows. The wmic
  binary is being deprecated. [#66959](https://github.com/saltstack/salt/issues/66959)
- Fixes an issue with the LGPO module when trying to parse ADMX/ADML files
  that have a space in the XMLNS url in the policyDefinitionsResources header. [#66992](https://github.com/saltstack/salt/issues/66992)
- Ensured global dunders like __env__ are defined in state module that are run in parallel on spawning platforms [#66996](https://github.com/saltstack/salt/issues/66996)
- Filtered unpicklable objects from the context dict when invoking states in parallel on spawning platforms to avoid a crash [#66999](https://github.com/saltstack/salt/issues/66999)
- Update for deprecation of hex in pygit2 1.15.0 and above [#67017](https://github.com/saltstack/salt/issues/67017)
- Fixed blob path for salt.ufw in the firewall tutorial documentation [#67019](https://github.com/saltstack/salt/issues/67019)
- Update locations for bootstrap scripts, to new infrastructure, GitHub releases for bootstrap [#67020](https://github.com/saltstack/salt/issues/67020)
- Constrained the localfs module to operations inside the specified cachedir [#67031](https://github.com/saltstack/salt/issues/67031)
- Added support for dnf5 (backport from 3007) and update to its new command syntax changes since 2023 [#67057](https://github.com/saltstack/salt/issues/67057)
- Recognise newer AMD GPU devices [#67058](https://github.com/saltstack/salt/issues/67058)
- Fix yumpkg module for Python<3.8 [#67091](https://github.com/saltstack/salt/issues/67091)
- Fixed an issue with making changes to the Windows Firewall when the
  AllowInboundRules setting is set to True [#67122](https://github.com/saltstack/salt/issues/67122)
- Added support and tests for dnf5 to services_need_restart for yum packages [#67177](https://github.com/saltstack/salt/issues/67177)
- Use os.walk to traverse git branches, and no longer replace slash '/' in git branch names [#67722](https://github.com/saltstack/salt/issues/67722)
- Set correct virtual grain in systemd based Podman containers [#67733](https://github.com/saltstack/salt/issues/67733)
- Corrected option --upgrades for dnf[5] for function list_upgrades [#67743](https://github.com/saltstack/salt/issues/67743)
- Fix salt-ssh for hosts that use password as the SSH password [#67754](https://github.com/saltstack/salt/issues/67754)
- Corrected dnf5 option --downloadonly for dnf5 install [#67769](https://github.com/saltstack/salt/issues/67769)
- Upgrade relenv to 0.18.1. Which includes python 3.10.16 and openssl 3.2.4.
  Openssl 3.2.4 fixes CVE-2024-12797 and CVE-2024-13176 [#67792](https://github.com/saltstack/salt/issues/67792)
- Update jinja2 to 3.1.5, advisories GHSA-q2x7-8rv6-6q7h and GHSA-gmj6-6f8f-6699
  Update urllib3 to 1.26.18 advisories GHSA-34jh-p97f-mpxf [#67794](https://github.com/saltstack/salt/issues/67794)
- Ensure salt-cloud has salt-master dependency on Debian and Ubuntu [#67810](https://github.com/saltstack/salt/issues/67810)
- Fix traceback from _send_req_sync method on minion by raising proper timeout error. [#67891](https://github.com/saltstack/salt/issues/67891)

# Added

- Issue #33669: Fixes an issue with the ``ini_managed`` execution module
  where it would always wrap the separator with spaces. Adds a new parameter
  named ``no_spaces`` that will not warp the separator with spaces. [#33669](https://github.com/saltstack/salt/issues/33669)
- Enhance json.find_json to return json even when it contains text on the same line of the last closing parenthesis [#67023](https://github.com/saltstack/salt/issues/67023)


* Sun May 19 2024 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.1

# Removed

- The ``salt.utils.psutil_compat`` was deprecated and now removed in Salt 3008. Please use the ``psutil`` module directly. [#66160](https://github.com/saltstack/salt/issues/66160)

# Fixed

- Fixes multiple issues with the cmd module on Windows. Scripts are called using
  the ``-File`` parameter to the ``powershell.exe`` binary. ``CLIXML`` data in
  stderr is now removed (only applies to encoded commands). Commands can now be
  sent to ``cmd.powershell`` as a list. Makes sure JSON data returned is valid.
  Strips whitespace from the return when using ``runas``. [#61166](https://github.com/saltstack/salt/issues/61166)
- Fixed the win_lgpo_netsh salt util to handle non-English systems. This was a
  rewrite to use PowerShell instead of netsh to make the changes on the system [#61534](https://github.com/saltstack/salt/issues/61534)
- Fix typo in nftables module to ensure unique nft family values [#65295](https://github.com/saltstack/salt/issues/65295)
- Corrected x509_v2 CRL creation `last_update` and `next_update` values when system timezone is not UTC [#65837](https://github.com/saltstack/salt/issues/65837)
- Fix for NoneType can't be used in 'await' expression error. [#66177](https://github.com/saltstack/salt/issues/66177)
- Log "Publish server binding pub to" messages to debug instead of error level. [#66179](https://github.com/saltstack/salt/issues/66179)
- Fix syndic startup by making payload handler a coroutine [#66237](https://github.com/saltstack/salt/issues/66237)
- Fixed `aptpkg.remove` "unable to locate package" error for non-existent package [#66260](https://github.com/saltstack/salt/issues/66260)
- Fixed pillar.ls doesn't accept kwargs [#66262](https://github.com/saltstack/salt/issues/66262)
- Fix cache directory setting in Master Cluster tutorial [#66264](https://github.com/saltstack/salt/issues/66264)
- Change log level of successful master cluster key exchange from error to info. [#66266](https://github.com/saltstack/salt/issues/66266)
- Made `file.managed` skip download of a remote source if the managed file already exists with the correct hash [#66342](https://github.com/saltstack/salt/issues/66342)
- Fixed nftables.build_rule breaks ipv6 rules by using the wrong syntax for source and destination addresses [#66382](https://github.com/saltstack/salt/issues/66382)

# Added

- Added the ability to pass a version of chocolatey to install to the
  chocolatey.bootstrap function. Also added states to bootstrap and
  unbootstrap chocolatey. [#64722](https://github.com/saltstack/salt/issues/64722)
- Add Ubuntu 24.04 support [#66180](https://github.com/saltstack/salt/issues/66180)
- Add Fedora 40 support, replacing Fedora 39 [#66300](https://github.com/saltstack/salt/issues/66300)

# Security

- Bump to `pydantic==2.6.4` due to https://github.com/advisories/GHSA-mr82-8j83-vxmv [#66433](https://github.com/saltstack/salt/issues/66433)
- Bump to ``jinja2==3.1.4`` due to https://github.com/advisories/GHSA-h75v-3vvj-5mfj [#66488](https://github.com/saltstack/salt/issues/66488)


* Mon Jul 29 2024 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.9

# Deprecated

- Drop CentOS 7 support [#66623](https://github.com/saltstack/salt/issues/66623)
- No longer build RPM packages with CentOS Stream 9 [#66624](https://github.com/saltstack/salt/issues/66624)

# Fixed

- Made slsutil.renderer work with salt-ssh [#50196](https://github.com/saltstack/salt/issues/50196)
- Fixed defaults.merge is not available when using salt-ssh [#51605](https://github.com/saltstack/salt/issues/51605)
- Fixed config.get does not support merge option with salt-ssh [#56441](https://github.com/saltstack/salt/issues/56441)
- Update to include croniter in pkg requirements [#57649](https://github.com/saltstack/salt/issues/57649)
- Fixed state.test does not work with salt-ssh [#61100](https://github.com/saltstack/salt/issues/61100)
- Made slsutil.findup work with salt-ssh [#61143](https://github.com/saltstack/salt/issues/61143)
- Fixes multiple issues with the cmd module on Windows. Scripts are called using
  the ``-File`` parameter to the ``powershell.exe`` binary. ``CLIXML`` data in
  stderr is now removed (only applies to encoded commands). Commands can now be
  sent to ``cmd.powershell`` as a list. Makes sure JSON data returned is valid.
  Strips whitespace from the return when using ``runas``. [#61166](https://github.com/saltstack/salt/issues/61166)
- Fixed the win_lgpo_netsh salt util to handle non-English systems. This was a
  rewrite to use PowerShell instead of netsh to make the changes on the system [#61534](https://github.com/saltstack/salt/issues/61534)
- file.replace and file.search work properly with /proc files [#63102](https://github.com/saltstack/salt/issues/63102)
- Fix utf8 handling in 'pass' renderer [#64300](https://github.com/saltstack/salt/issues/64300)
- Fixed incorrect version argument will be ignored for multiple package targets warning when using pkgs argument to yumpkg module. [#64563](https://github.com/saltstack/salt/issues/64563)
- salt-cloud honors root_dir config setting for log_file location and fixes for root_dir locations on windows. [#64728](https://github.com/saltstack/salt/issues/64728)
- Fixed slsutil.update with salt-ssh during template rendering [#65067](https://github.com/saltstack/salt/issues/65067)
- Fix config.items when called on minion [#65251](https://github.com/saltstack/salt/issues/65251)
- Ensure on rpm and deb systems, that user and group for existing Salt, is maintained on upgrade [#65264](https://github.com/saltstack/salt/issues/65264)
- Fix typo in nftables module to ensure unique nft family values [#65295](https://github.com/saltstack/salt/issues/65295)
- pkg.installed state aggregate does not honors requires requisite [#65304](https://github.com/saltstack/salt/issues/65304)
- Added SSH wrapper for logmod [#65630](https://github.com/saltstack/salt/issues/65630)
- Fix for GitFS failure to unlock lock file, and resource cleanup for process SIGTERM [#65816](https://github.com/saltstack/salt/issues/65816)
- Corrected x509_v2 CRL creation `last_update` and `next_update` values when system timezone is not UTC [#65837](https://github.com/saltstack/salt/issues/65837)
- Make sure the root minion process handles SIGUSR1 and emits a traceback like it's child processes [#66095](https://github.com/saltstack/salt/issues/66095)
- Replaced pyvenv with builtin venv for virtualenv_mod [#66132](https://github.com/saltstack/salt/issues/66132)
- Made `file.managed` skip download of a remote source if the managed file already exists with the correct hash [#66342](https://github.com/saltstack/salt/issues/66342)
- Fix win_task ExecutionTimeLimit and result/error code interpretation [#66347](https://github.com/saltstack/salt/issues/66347), [#66441](https://github.com/saltstack/salt/issues/66441)
- Fixed nftables.build_rule breaks ipv6 rules by using the wrong syntax for source and destination addresses [#66382](https://github.com/saltstack/salt/issues/66382)
- Fixed x509_v2 certificate.managed crash for locally signed certificates if the signing policy defines signing_private_key [#66414](https://github.com/saltstack/salt/issues/66414)
- Fixed parallel state execution with Salt-SSH [#66514](https://github.com/saltstack/salt/issues/66514)
- Fix support for FIPS approved encryption and signing algorithms. [#66579](https://github.com/saltstack/salt/issues/66579)
- Fix relative file_roots paths [#66588](https://github.com/saltstack/salt/issues/66588)
- Fixed an issue with cmd.run with requirements when the shell is not the
  default [#66596](https://github.com/saltstack/salt/issues/66596)
- Fix RPM package provides [#66604](https://github.com/saltstack/salt/issues/66604)
- Upgrade relAenv to 0.16.1. This release fixes several package installs for salt-pip [#66632](https://github.com/saltstack/salt/issues/66632)
- Upgrade relenv to 0.17.0 (https://github.com/saltstack/relenv/blob/v0.17.0/CHANGELOG.md) [#66663](https://github.com/saltstack/salt/issues/66663)
- Upgrade dependencies due to security issues:
  - pymysql>=1.1.1
  - requests>=2.32.0
  - docker>=7.1.0 [#66666](https://github.com/saltstack/salt/issues/66666)
- Corrected missed line in branch 3006.x when backporting from PR 61620 and 65044 [#66683](https://github.com/saltstack/salt/issues/66683)
- Remove debug output from shell scripts for packaging [#66747](https://github.com/saltstack/salt/issues/66747)

# Added

- Add Ubuntu 24.04 support [#66180](https://github.com/saltstack/salt/issues/66180)
- Add Fedora 40 support, replacing Fedora 39 [#66300](https://github.com/saltstack/salt/issues/66300)
- Build RPM packages with Rocky Linux 9 (instead of CentOS Stream 9) [#66624](https://github.com/saltstack/salt/issues/66624)

# Security

- Bump to ``jinja2==3.1.4`` due to https://github.com/advisories/GHSA-h75v-3vvj-5mfj [#66488](https://github.com/saltstack/salt/issues/66488)
- CVE-2024-37088 salt-call will fail with exit code 1 if bad pillar data is
  encountered. [#66702](https://github.com/saltstack/salt/issues/66702)


* Mon Apr 29 2024 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.8

# Removed

- Removed deprecated code scheduled to be removed on 2024-01-01:

  * ``TemporaryLoggingHandler`` and ``QueueHandler`` in ``salt/_logging/handlers.py``
  * All of the ``salt/log`` package.
  * The ``salt/modules/cassandra_mod.py`` module.
  * The ``salt/returners/cassandra_return.py`` returner.
  * The ``salt/returners/django_return.py`` returner. [#66147](https://github.com/saltstack/salt/issues/66147)

# Deprecated

- Drop Fedora 37 and Fedora 38 support [#65860](https://github.com/saltstack/salt/issues/65860)
- Drop CentOS Stream 8 and 9 from CI/CD [#66104](https://github.com/saltstack/salt/issues/66104)
- Drop Photon OS 3 support [#66105](https://github.com/saltstack/salt/issues/66105)
- The ``salt.utils.psutil_compat`` module has been deprecated and will be removed in Salt 3008. Please use the ``psutil`` module directly. [#66139](https://github.com/saltstack/salt/issues/66139)

# Fixed

- ``user.add`` on Windows now allows you to add user names that contain all
  numeric characters [#53363](https://github.com/saltstack/salt/issues/53363)
- Fix an issue with the win_system module detecting established connections on
  non-Windows systems. Uses psutils instead of parsing the return of netstat [#60508](https://github.com/saltstack/salt/issues/60508)
- pkg.refresh_db on Windows now honors saltenv [#61807](https://github.com/saltstack/salt/issues/61807)
- Fixed an issue with adding new machine policies and applying those same
  policies in the same state by adding a ``refresh_cache`` option to the
  ``lgpo.set`` state. [#62734](https://github.com/saltstack/salt/issues/62734)
- file.managed correctly handles file path with '#' [#63060](https://github.com/saltstack/salt/issues/63060)
- Fix master ip detection when DNS records change [#63654](https://github.com/saltstack/salt/issues/63654)
- Fix user and group management on Windows to handle the Everyone group [#63667](https://github.com/saltstack/salt/issues/63667)
- Fixes an issue in pkg.refresh_db on Windows where new package definition
  files were not being picked up on the first run [#63848](https://github.com/saltstack/salt/issues/63848)
- Display a proper error when pki commands fail in the win_pki module [#64933](https://github.com/saltstack/salt/issues/64933)
- Prevent full system upgrade on single package install for Arch Linux [#65200](https://github.com/saltstack/salt/issues/65200)
- When using s3fs, if files are deleted from the bucket, they were not deleted in
  the master or minion local cache, which could lead to unexpected file copies or
  even state applications. This change makes the local cache consistent with the
  remote bucket by deleting files locally that are deleted from the bucket.

  **NOTE** this could lead to **breakage** on your affected systems if it was
  inadvertently depending on previously deleted files. [#65611](https://github.com/saltstack/salt/issues/65611)
- Fixed an issue with file.directory state where paths would be modified in test
  mode if backupname is used. [#66049](https://github.com/saltstack/salt/issues/66049)
- Execution modules have access to regular fileclient durring pillar rendering. [#66124](https://github.com/saltstack/salt/issues/66124)
- Fixed a issue with server channel where a minion's public key
  would be rejected if it contained a final newline character. [#66126](https://github.com/saltstack/salt/issues/66126)
- Fix content type backwards compatablity with http proxy post requests in the http utils module. [#66127](https://github.com/saltstack/salt/issues/66127)
- Fix systemctl with "try-restart" instead of "retry-restart" within the RPM spec, properly restarting upgraded services [#66143](https://github.com/saltstack/salt/issues/66143)
- Auto discovery of ssh, scp and ssh-keygen binaries. [#66205](https://github.com/saltstack/salt/issues/66205)
- Add leading slash to salt helper file paths as per dh_links requirement [#66280](https://github.com/saltstack/salt/issues/66280)
- Fixed x509.certificate_managed - ca_server did not return a certificate [#66284](https://github.com/saltstack/salt/issues/66284)
- removed log line that did nothing. [#66289](https://github.com/saltstack/salt/issues/66289)
- Chocolatey: Make sure the return dictionary from ``chocolatey.version``
  contains lowercase keys [#66290](https://github.com/saltstack/salt/issues/66290)
- fix cacheing inline pillar, by not rendering inline pillar during cache save function. [#66292](https://github.com/saltstack/salt/issues/66292)
- The file module correctly perserves file permissions on link target. [#66400](https://github.com/saltstack/salt/issues/66400)
- Upgrade relenv to 0.16.0 and python to 3.10.14 [#66402](https://github.com/saltstack/salt/issues/66402)
- backport the fix from #66164 to fix #65703. use OrderedDict to fix bad indexing. [#66705](https://github.com/saltstack/salt/issues/66705)

# Added

- Add Fedora 39 support [#65859](https://github.com/saltstack/salt/issues/65859)

# Security

- Upgrade to `cryptography==42.0.5` due to a few security issues:

  * https://github.com/advisories/GHSA-9v9h-cgj8-h64p
  * https://github.com/advisories/GHSA-3ww4-gg4f-jr7f
  * https://github.com/advisories/GHSA-6vqw-3v5j-54x4 [#66141](https://github.com/saltstack/salt/issues/66141)
- Bump to `idna==3.7` due to https://github.com/advisories/GHSA-jjg7-2v4v-x38h [#66377](https://github.com/saltstack/salt/issues/66377)
- Bump to `aiohttp==3.9.4` due to https://github.com/advisories/GHSA-7gpw-8wmc-pm8g [#66411](https://github.com/saltstack/salt/issues/66411)


* Sun Mar 03 2024 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.0

# Removed

- Removed RHEL 5 support since long since end-of-lifed [#62520](https://github.com/saltstack/salt/issues/62520)
- Removing Azure-Cloud modules from the code base. [#64322](https://github.com/saltstack/salt/issues/64322)
- Dropped Python 3.7 support since it's EOL in 27 Jun 2023 [#64417](https://github.com/saltstack/salt/issues/64417)
- Remove salt.payload.Serial [#64459](https://github.com/saltstack/salt/issues/64459)
- Remove netmiko_conn and pyeapi_conn from salt.modules.napalm_mod [#64460](https://github.com/saltstack/salt/issues/64460)
- Removed 'transport' arg from salt.utils.event.get_event [#64461](https://github.com/saltstack/salt/issues/64461)
- Removed the usage of retired Linode API v3 from Salt Cloud [#64517](https://github.com/saltstack/salt/issues/64517)

# Deprecated

- Deprecate all Proxmox cloud modules [#64224](https://github.com/saltstack/salt/issues/64224)
- Deprecate all the Vault modules in favor of the Vault Salt Extension https://github.com/salt-extensions/saltext-vault. The Vault modules will be removed in Salt core in 3009.0. [#64893](https://github.com/saltstack/salt/issues/64893)
- Deprecate all the Docker modules in favor of the Docker Salt Extension https://github.com/saltstack/saltext-docker. The Docker modules will be removed in Salt core in 3009.0. [#64894](https://github.com/saltstack/salt/issues/64894)
- Deprecate all the Zabbix modules in favor of the Zabbix Salt Extension https://github.com/salt-extensions/saltext-zabbix. The Zabbix modules will be removed in Salt core in 3009.0. [#64896](https://github.com/saltstack/salt/issues/64896)
- Deprecate all the Apache modules in favor of the Apache Salt Extension https://github.com/salt-extensions/saltext-apache. The Apache modules will be removed in Salt core in 3009.0. [#64909](https://github.com/saltstack/salt/issues/64909)
- Deprecation warning for Salt's backport of ``OrderedDict`` class which will be removed in 3009 [#65542](https://github.com/saltstack/salt/issues/65542)
- Deprecate Kubernetes modules for move to saltext-kubernetes in version 3009 [#65565](https://github.com/saltstack/salt/issues/65565)
- Deprecated all Pushover modules in favor of the Salt Extension at https://github.com/salt-extensions/saltext-pushover. The Pushover modules will be removed from Salt core in 3009.0 [#65567](https://github.com/saltstack/salt/issues/65567)
- Removed deprecated code:

  * All of ``salt/log/`` which has been on a deprecation path for a long time.
  * Some of the logging handlers found in ``salt/_logging/handlers`` have been removed since the standard library provides
    them.
  * Removed the deprecated ``salt/modules/cassandra_mod.py`` module and any tests for it.
  * Removed the deprecated ``salt/returners/cassandra_return.py`` module and any tests for it.
  * Removed the deprecated ``salt/returners/django_return.py`` module and any tests for it. [#65986](https://github.com/saltstack/salt/issues/65986)

# Changed

- Masquerade property will not default to false turning off masquerade if not specified. [#53120](https://github.com/saltstack/salt/issues/53120)
- Addressed Python 3.11 deprecations:

  * Switch to `FullArgSpec` since Py 3.11 no longer has `ArgSpec`, deprecated since Py 3.0
  * Stopped using the deprecated `cgi` module.
  * Stopped using the deprecated `pipes` module
  * Stopped using the deprecated `imp` module [#64457](https://github.com/saltstack/salt/issues/64457)
- changed 'gpg_decrypt_must_succeed' default from False to True [#64462](https://github.com/saltstack/salt/issues/64462)

# Fixed

- When an NFS or FUSE mount fails to unmount when mount options have changed, try again with a lazy umount before mounting again. [#18907](https://github.com/saltstack/salt/issues/18907)
- fix autoaccept gpg keys by supporting it in refresh_db module [#42039](https://github.com/saltstack/salt/issues/42039)
- Made cmd.script work with files from the fileserver via salt-ssh [#48067](https://github.com/saltstack/salt/issues/48067)
- Made slsutil.renderer work with salt-ssh [#50196](https://github.com/saltstack/salt/issues/50196)
- Fixed defaults.merge is not available when using salt-ssh [#51605](https://github.com/saltstack/salt/issues/51605)
- Fix extfs.mkfs missing parameter handling for -C, -d, and -e [#51858](https://github.com/saltstack/salt/issues/51858)
- Fixed Salt master does not renew token [#51986](https://github.com/saltstack/salt/issues/51986)
- Fixed salt-ssh continues state/pillar rendering with incorrect data when an exception is raised by a module on the target [#52452](https://github.com/saltstack/salt/issues/52452)
- Fix extfs.tune has 'reserved' documented twice and is missing the 'reserved_percentage' keyword argument [#54426](https://github.com/saltstack/salt/issues/54426)
- Fix the ability of the 'selinux.port_policy_present' state to modify. [#55687](https://github.com/saltstack/salt/issues/55687)
- Fixed config.get does not support merge option with salt-ssh [#56441](https://github.com/saltstack/salt/issues/56441)
- Removed an unused assignment in file.patch [#57204](https://github.com/saltstack/salt/issues/57204)
- Fixed vault module fetching more than one secret in one run with single-use tokens [#57561](https://github.com/saltstack/salt/issues/57561)
- Use brew path from which in mac_brew_pkg module and rely on _homebrew_bin() everytime [#57946](https://github.com/saltstack/salt/issues/57946)
- Fixed Vault verify option to work on minions when only specified in master config [#58174](https://github.com/saltstack/salt/issues/58174)
- Fixed vault command errors configured locally [#58580](https://github.com/saltstack/salt/issues/58580)
- Fixed issue with basic auth causing invalid header error and 401 Bad Request, by using HTTPBasicAuthHandler instead of header. [#58936](https://github.com/saltstack/salt/issues/58936)
- Make the LXD module work with pyLXD > 2.10 [#59514](https://github.com/saltstack/salt/issues/59514)
- Return error if patch file passed to state file.patch is malformed. [#59806](https://github.com/saltstack/salt/issues/59806)
- Handle failure and error information from tuned module/state [#60500](https://github.com/saltstack/salt/issues/60500)
- Fixed sdb.get_or_set_hash with Vault single-use tokens [#60779](https://github.com/saltstack/salt/issues/60779)
- Fixed state.test does not work with salt-ssh [#61100](https://github.com/saltstack/salt/issues/61100)
- Made slsutil.findup work with salt-ssh [#61143](https://github.com/saltstack/salt/issues/61143)
- Allow all primitive grain types for autosign_grains [#61416](https://github.com/saltstack/salt/issues/61416), [#63708](https://github.com/saltstack/salt/issues/63708)
- `ipset.new_set` no longer fails when creating a set type that uses the `family` create option [#61620](https://github.com/saltstack/salt/issues/61620)
- Fixed Vault session storage to allow unlimited use tokens [#62380](https://github.com/saltstack/salt/issues/62380)
- fix the efi grain on FreeBSD [#63052](https://github.com/saltstack/salt/issues/63052)
- Fixed gpg.receive_keys returns success on failed import [#63144](https://github.com/saltstack/salt/issues/63144)
- Fixed GPG state module always reports success without changes [#63153](https://github.com/saltstack/salt/issues/63153)
- Fixed GPG state module does not respect test mode [#63156](https://github.com/saltstack/salt/issues/63156)
- Fixed gpg.absent with gnupghome/user, fixed gpg.delete_key with gnupghome [#63159](https://github.com/saltstack/salt/issues/63159)
- Fixed service module does not handle enable/disable if systemd service is an alias [#63214](https://github.com/saltstack/salt/issues/63214)
- Made x509_v2 compound match detection use new runner instead of peer publishing [#63278](https://github.com/saltstack/salt/issues/63278)
- Need to make sure we update __pillar__ during a pillar refresh to ensure that process_beacons has the updated beacons loaded from pillar. [#63583](https://github.com/saltstack/salt/issues/63583)
- This implements the vpc_uuid parameter when creating a droplet. This parameter selects the correct virtual private cloud (private network interface). [#63714](https://github.com/saltstack/salt/issues/63714)
- pkg.installed no longer reports failure when installing packages that are installed via the task manager [#63767](https://github.com/saltstack/salt/issues/63767)
- mac_xattr.list and mac_xattr.read will replace undecode-able bytes to avoid raising CommandExecutionError. [#63779](https://github.com/saltstack/salt/issues/63779) [#63779](https://github.com/saltstack/salt/issues/63779)
- Fix aptpkg.latest_version performance, reducing number of times to 'shell out' [#63982](https://github.com/saltstack/salt/issues/63982)
- Added option to use a fresh connection for mysql cache [#63991](https://github.com/saltstack/salt/issues/63991)
- [lxd] Fixed a bug in `container_create` which prevented devices which are not of type `disk` to be correctly created and added to the container when passed via the `devices` parameter. [#63996](https://github.com/saltstack/salt/issues/63996)
- Skipped the `isfile` check to greatly increase speed of reading minion keys for systems with a large number of minions on slow file storage [#64260](https://github.com/saltstack/salt/issues/64260)
- Fix utf8 handling in 'pass' renderer [#64300](https://github.com/saltstack/salt/issues/64300)
- Upgade tornado to 6.3.2 [#64305](https://github.com/saltstack/salt/issues/64305)
- Prevent errors due missing 'transactional_update.apply' on SLE Micro and MicroOS. [#64369](https://github.com/saltstack/salt/issues/64369)
- Fix 'unable to unmount' failure to return False result instead of None [#64420](https://github.com/saltstack/salt/issues/64420)
- Fixed issue uninstalling duplicate packages in ``win_appx`` execution module [#64450](https://github.com/saltstack/salt/issues/64450)
- Clean up tech debt, IPC now uses tcp transport. [#64488](https://github.com/saltstack/salt/issues/64488)
- Made salt-ssh more strict when handling unexpected situations and state.* wrappers treat a remote exception as failure, excluded salt-ssh error returns from mine [#64531](https://github.com/saltstack/salt/issues/64531)
- Fix flaky test for LazyLoader with isolated mocking of threading.RLock [#64567](https://github.com/saltstack/salt/issues/64567)
- Fix possible `KeyError` exceptions in `salt.utils.user.get_group_dict`
  while reading improper duplicated GID assigned for the user. [#64599](https://github.com/saltstack/salt/issues/64599)
- changed vm_config() to deep-merge vm_overrides of specific VM, instead of simple-merging the whole vm_overrides [#64610](https://github.com/saltstack/salt/issues/64610)
- Fix the way Salt tries to get the Homebrew's prefix

  The first attempt to get the Homebrew's prefix is to look for
  the `HOMEBREW_PREFIX` environment variable. If it's not set, then
  Salt tries to get the prefix from the `brew` command. However, the
  `brew` command can fail. So a last attempt is made to get the
  prefix by guessing the installation path. [#64924](https://github.com/saltstack/salt/issues/64924)
- Add missing MySQL Grant SERVICE_CONNECTION_ADMIN to mysql module. [#64934](https://github.com/saltstack/salt/issues/64934)
- Fixed slsutil.update with salt-ssh during template rendering [#65067](https://github.com/saltstack/salt/issues/65067)
- Keep track when an included file only includes sls files but is a requisite. [#65080](https://github.com/saltstack/salt/issues/65080)
- Fixed `gpg.present` succeeds when the keyserver is unreachable [#65169](https://github.com/saltstack/salt/issues/65169)
- Fix typo in nftables module to ensure unique nft family values [#65295](https://github.com/saltstack/salt/issues/65295)
- Dereference symlinks to set proper __cli opt [#65435](https://github.com/saltstack/salt/issues/65435)
- Made salt-ssh merge master top returns for the same environment [#65480](https://github.com/saltstack/salt/issues/65480)
- Account for situation where the metadata grain fails because the AWS environment requires an authentication token to query the metadata URL. [#65513](https://github.com/saltstack/salt/issues/65513)
- Improve the condition of overriding target for pip with VENV_PIP_TARGET environment variable. [#65562](https://github.com/saltstack/salt/issues/65562)
- Added SSH wrapper for logmod [#65630](https://github.com/saltstack/salt/issues/65630)
- Include changes in the results when schedule.present state is run with test=True. [#65652](https://github.com/saltstack/salt/issues/65652)
- Fix extfs.tune doesn't pass retcode to module.run [#65686](https://github.com/saltstack/salt/issues/65686)
- Return an error message when the DNS plugin is not supported [#65739](https://github.com/saltstack/salt/issues/65739)
- Execution modules have access to regular fileclient durring pillar rendering. [#66124](https://github.com/saltstack/salt/issues/66124)
- Fixed a issue with server channel where a minion's public key
  would be rejected if it contained a final newline character. [#66126](https://github.com/saltstack/salt/issues/66126)

# Added

- Allowed publishing to regular minions from the SSH wrapper [#40943](https://github.com/saltstack/salt/issues/40943)
- Added syncing of custom salt-ssh wrappers [#45450](https://github.com/saltstack/salt/issues/45450)
- Made salt-ssh sync custom utils [#53666](https://github.com/saltstack/salt/issues/53666)
- Add ability to use file.managed style check_cmd in file.serialize [#53982](https://github.com/saltstack/salt/issues/53982)
- Revised use of deprecated net-tools and added support for ip neighbour with IPv4 ip_neighs, IPv6 ip_neighs6 [#57541](https://github.com/saltstack/salt/issues/57541)
- Added password support to Redis returner. [#58044](https://github.com/saltstack/salt/issues/58044)
- Added a state (win_task) for managing scheduled tasks on Windows [#59037](https://github.com/saltstack/salt/issues/59037)
- Added keyring param to gpg modules [#59783](https://github.com/saltstack/salt/issues/59783)
- Added new grain to detect the Salt package type: onedir, pip or system [#62589](https://github.com/saltstack/salt/issues/62589)
- Added Vault AppRole and identity issuance to minions [#62823](https://github.com/saltstack/salt/issues/62823)
- Added Vault AppRole auth mount path configuration option [#62825](https://github.com/saltstack/salt/issues/62825)
- Added distribution of Vault authentication details via response wrapping [#62828](https://github.com/saltstack/salt/issues/62828)
- Add salt package type information. Either onedir, pip or system. [#62961](https://github.com/saltstack/salt/issues/62961)
- Added signature verification to file.managed/archive.extracted [#63143](https://github.com/saltstack/salt/issues/63143)
- Added signed_by_any/signed_by_all parameters to gpg.verify [#63166](https://github.com/saltstack/salt/issues/63166)
- Added match runner [#63278](https://github.com/saltstack/salt/issues/63278)
- Added Vault token lifecycle management [#63406](https://github.com/saltstack/salt/issues/63406)
- adding new call for openscap xccdf eval supporting new parameters [#63416](https://github.com/saltstack/salt/issues/63416)
- Added Vault lease management utility [#63440](https://github.com/saltstack/salt/issues/63440)
- implement removal of ptf packages in zypper pkg module [#63442](https://github.com/saltstack/salt/issues/63442)
- add JUnit output for saltcheck [#63463](https://github.com/saltstack/salt/issues/63463)
- Add ability for file.keyvalue to create a file if it doesn't exist [#63545](https://github.com/saltstack/salt/issues/63545)
- added cleanup of temporary mountpoint dir for macpackage installed state [#63905](https://github.com/saltstack/salt/issues/63905)
- Add pkg.installed show installable version in test mode [#63985](https://github.com/saltstack/salt/issues/63985)
- Added patch option to Vault SDB driver [#64096](https://github.com/saltstack/salt/issues/64096)
- Added flags to create local users and groups [#64256](https://github.com/saltstack/salt/issues/64256)
- Added inline specification of trusted CA root certificate for Vault [#64379](https://github.com/saltstack/salt/issues/64379)
- Add ability to return False result in test mode of configurable_test_state [#64418](https://github.com/saltstack/salt/issues/64418)
- Switched Salt's onedir Python version to 3.11 [#64457](https://github.com/saltstack/salt/issues/64457)
- Added support for dnf5 and its new command syntax [#64532](https://github.com/saltstack/salt/issues/64532)
- Adding a new decorator to indicate when a module is deprecated in favor of a Salt extension. [#64569](https://github.com/saltstack/salt/issues/64569)
- Add jq-esque to_entries and from_entries functions [#64600](https://github.com/saltstack/salt/issues/64600)
- Added ability to use PYTHONWARNINGS=ignore to silence deprecation warnings. [#64660](https://github.com/saltstack/salt/issues/64660)
- Add follow_symlinks to file.symlink exec module to switch to os.path.lexists when False [#64665](https://github.com/saltstack/salt/issues/64665)
- Strenghten Salt's HA capabilities with master clustering. [#64939](https://github.com/saltstack/salt/issues/64939)
- Added win_appx state and execution modules for managing Microsoft Store apps and deprovisioning them from systems [#64978](https://github.com/saltstack/salt/issues/64978)
- Add support for show_jid to salt-run

  Adds support for show_jid master config option to salt-run, so its behaviour matches the salt cli command. [#65008](https://github.com/saltstack/salt/issues/65008)
- Add ability to remove packages by wildcard via apt execution module [#65220](https://github.com/saltstack/salt/issues/65220)
- Added support for master top modules on masterless minions [#65479](https://github.com/saltstack/salt/issues/65479)
- Allowed accessing the regular mine from the SSH wrapper [#65645](https://github.com/saltstack/salt/issues/65645)
- Allow enabling backup for Linode in Salt Cloud [#65697](https://github.com/saltstack/salt/issues/65697)
- Add a backup schedule setter fFunction for Linode VMs [#65713](https://github.com/saltstack/salt/issues/65713)
- Add acme support for manual plugin hooks [#65744](https://github.com/saltstack/salt/issues/65744)

# Security

- Upgrade to `tornado>=6.3.3` due to https://github.com/advisories/GHSA-qppv-j76h-2rpx [#64989](https://github.com/saltstack/salt/issues/64989)
- Update to `gitpython>=3.1.35` due to https://github.com/advisories/GHSA-wfm5-v35h-vwf4 and https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65137](https://github.com/saltstack/salt/issues/65137)


* Tue Feb 20 2024 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.7

# Deprecated

- Deprecate and stop using ``salt.features`` [#65951](https://github.com/saltstack/salt/issues/65951)

# Changed

- Change module search path priority, so Salt extensions can be overridden by syncable modules and module_dirs. You can switch back to the old logic by setting features.enable_deprecated_module_search_path_priority to true, but it will be removed in Salt 3008. [#65938](https://github.com/saltstack/salt/issues/65938)

# Fixed

- Fix issue with ownership on upgrade of master and minion files
- Fix an issue with mac_shadow that was causing a command execution error when
  retrieving values that were not yet set. For example, retrieving last login
  before the user had logged in. [#34658](https://github.com/saltstack/salt/issues/34658)
- Fixed an issue when keys didn't match because of line endings [#52289](https://github.com/saltstack/salt/issues/52289)
- Corrected encoding of credentials for use with Artifactory [#63063](https://github.com/saltstack/salt/issues/63063)
- Use `send_multipart` instead of `send` when sending multipart message. [#65018](https://github.com/saltstack/salt/issues/65018)
- Fix an issue where the minion would crash on Windows if some of the grains
  failed to resolve [#65154](https://github.com/saltstack/salt/issues/65154)
- Fix issue with openscap when the error was outside the expected scope. It now
  returns failed with the error code and the error [#65193](https://github.com/saltstack/salt/issues/65193)
- Upgrade relenv to 0.15.0 to fix namespaced packages installed by salt-pip [#65433](https://github.com/saltstack/salt/issues/65433)
- Fix regression of fileclient re-use when rendering sls pillars and states [#65450](https://github.com/saltstack/salt/issues/65450)
- Fixes the s3fs backend computing the local cache's files with the wrong hash type [#65589](https://github.com/saltstack/salt/issues/65589)
- Fixed Salt-SSH pillar rendering and state rendering with nested SSH calls when called via saltutil.cmd or in an orchestration [#65670](https://github.com/saltstack/salt/issues/65670)
- Fix boto execution module loading [#65691](https://github.com/saltstack/salt/issues/65691)
- Removed PR 65185 changes since incomplete solution [#65692](https://github.com/saltstack/salt/issues/65692)
- catch only ret/ events not all returning events. [#65727](https://github.com/saltstack/salt/issues/65727)
- Fix nonsensical time in fileclient timeout error. [#65752](https://github.com/saltstack/salt/issues/65752)
- Fixes an issue when reading/modifying ini files that contain unicode characters [#65777](https://github.com/saltstack/salt/issues/65777)
- added https proxy to the list of proxies so that requests knows what to do with https based proxies [#65824](https://github.com/saltstack/salt/issues/65824)
- Ensure minion channels are closed on any master connection error. [#65932](https://github.com/saltstack/salt/issues/65932)
- Fixed issue where Salt can't find libcrypto when pip installed from a cloned repo [#65954](https://github.com/saltstack/salt/issues/65954)
- Fix RPM package systemd scriptlets to make RPM packages more universal [#65987](https://github.com/saltstack/salt/issues/65987)
- Fixed an issue where fileclient requests during Pillar rendering cause
  fileserver backends to be needlessly refreshed. [#65990](https://github.com/saltstack/salt/issues/65990)
- Fix exceptions being set on futures that are already done in ZeroMQ transport [#66006](https://github.com/saltstack/salt/issues/66006)
- Use hmac compare_digest method in hashutil module to mitigate potential timing attacks [#66041](https://github.com/saltstack/salt/issues/66041)
- Fix request channel default timeout regression. In 3006.5 it was changed from
  60 to 30 and is now set back to 60 by default. [#66061](https://github.com/saltstack/salt/issues/66061)
- Upgrade relenv to 0.15.1 to fix debugpy support. [#66094](https://github.com/saltstack/salt/issues/66094)

# Security

- Bump to ``cryptography==42.0.0`` due to https://github.com/advisories/GHSA-3ww4-gg4f-jr7f

  In the process, we were also required to update to ``pyOpenSSL==24.0.0`` [#66004](https://github.com/saltstack/salt/issues/66004)
- Bump to `cryptography==42.0.3` due to https://github.com/advisories/GHSA-3ww4-gg4f-jr7f [#66090](https://github.com/saltstack/salt/issues/66090)


* Fri Jan 26 2024 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.6

# Changed

- Salt no longer time bombs user installations on code using `salt.utils.versions.warn_until_date` [#665924](https://github.com/saltstack/salt/issues/665924)

# Fixed

- Fix un-closed transport in tornado netapi [#65759](https://github.com/saltstack/salt/issues/65759)

# Security

- CVE-2024-22231 Prevent directory traversal when creating syndic cache directory on the master
  CVE-2024-22232 Prevent directory traversal attacks in the master's serve_file method.
  These vulerablities were discovered and reported by:
  Yudi Zhao(Huawei Nebula Security Lab),Chenwei Jiang(Huawei Nebula Security Lab) [#565](https://github.com/saltstack/salt/issues/565)
- Update some requirements which had some security issues:

  * Bump to `pycryptodome==3.19.1` and `pycryptodomex==3.19.1` due to https://github.com/advisories/GHSA-j225-cvw7-qrx7
  * Bump to `gitpython==3.1.41` due to https://github.com/advisories/GHSA-2mqj-m65w-jghx
  * Bump to `jinja2==3.1.3` due to https://github.com/advisories/GHSA-h5c8-rqwp-cp95 [#65830](https://github.com/saltstack/salt/issues/65830)


* Tue Jan 02 2024 Salt Project Packaging <saltproject-packaging@vmware.com> - 3007.0~rc1

# Removed

- Removed RHEL 5 support since long since end-of-lifed [#62520](https://github.com/saltstack/salt/issues/62520)
- Removing Azure-Cloud modules from the code base. [#64322](https://github.com/saltstack/salt/issues/64322)
- Dropped Python 3.7 support since it's EOL in 27 Jun 2023 [#64417](https://github.com/saltstack/salt/issues/64417)
- Remove salt.payload.Serial [#64459](https://github.com/saltstack/salt/issues/64459)
- Remove netmiko_conn and pyeapi_conn from salt.modules.napalm_mod [#64460](https://github.com/saltstack/salt/issues/64460)
- Removed 'transport' arg from salt.utils.event.get_event [#64461](https://github.com/saltstack/salt/issues/64461)
- Removed the usage of retired Linode API v3 from Salt Cloud [#64517](https://github.com/saltstack/salt/issues/64517)

# Deprecated

- Deprecate all Proxmox cloud modules [#64224](https://github.com/saltstack/salt/issues/64224)
- Deprecate all the Vault modules in favor of the Vault Salt Extension https://github.com/salt-extensions/saltext-vault. The Vault modules will be removed in Salt core in 3009.0. [#64893](https://github.com/saltstack/salt/issues/64893)
- Deprecate all the Docker modules in favor of the Docker Salt Extension https://github.com/saltstack/saltext-docker. The Docker modules will be removed in Salt core in 3009.0. [#64894](https://github.com/saltstack/salt/issues/64894)
- Deprecate all the Zabbix modules in favor of the Zabbix Salt Extension https://github.com/salt-extensions/saltext-zabbix. The Zabbix modules will be removed in Salt core in 3009.0. [#64896](https://github.com/saltstack/salt/issues/64896)
- Deprecate all the Apache modules in favor of the Apache Salt Extension https://github.com/salt-extensions/saltext-apache. The Apache modules will be removed in Salt core in 3009.0. [#64909](https://github.com/saltstack/salt/issues/64909)
- Deprecation warning for Salt's backport of ``OrderedDict`` class which will be removed in 3009 [#65542](https://github.com/saltstack/salt/issues/65542)
- Deprecate Kubernetes modules for move to saltext-kubernetes in version 3009 [#65565](https://github.com/saltstack/salt/issues/65565)
- Deprecated all Pushover modules in favor of the Salt Extension at https://github.com/salt-extensions/saltext-pushover. The Pushover modules will be removed from Salt core in 3009.0 [#65567](https://github.com/saltstack/salt/issues/65567)

# Changed

- Masquerade property will not default to false turning off masquerade if not specified. [#53120](https://github.com/saltstack/salt/issues/53120)
- Addressed Python 3.11 deprecations:

  * Switch to `FullArgSpec` since Py 3.11 no longer has `ArgSpec`, deprecated since Py 3.0
  * Stopped using the deprecated `cgi` module.
  * Stopped using the deprecated `pipes` module
  * Stopped using the deprecated `imp` module [#64457](https://github.com/saltstack/salt/issues/64457)
- changed 'gpg_decrypt_must_succeed' default from False to True [#64462](https://github.com/saltstack/salt/issues/64462)

# Fixed

- When an NFS or FUSE mount fails to unmount when mount options have changed, try again with a lazy umount before mounting again. [#18907](https://github.com/saltstack/salt/issues/18907)
- fix autoaccept gpg keys by supporting it in refresh_db module [#42039](https://github.com/saltstack/salt/issues/42039)
- Made cmd.script work with files from the fileserver via salt-ssh [#48067](https://github.com/saltstack/salt/issues/48067)
- Made slsutil.renderer work with salt-ssh [#50196](https://github.com/saltstack/salt/issues/50196)
- Fixed defaults.merge is not available when using salt-ssh [#51605](https://github.com/saltstack/salt/issues/51605)
- Fix extfs.mkfs missing parameter handling for -C, -d, and -e [#51858](https://github.com/saltstack/salt/issues/51858)
- Fixed Salt master does not renew token [#51986](https://github.com/saltstack/salt/issues/51986)
- Fixed salt-ssh continues state/pillar rendering with incorrect data when an exception is raised by a module on the target [#52452](https://github.com/saltstack/salt/issues/52452)
- Fix extfs.tune has 'reserved' documented twice and is missing the 'reserved_percentage' keyword argument [#54426](https://github.com/saltstack/salt/issues/54426)
- Fix the ability of the 'selinux.port_policy_present' state to modify. [#55687](https://github.com/saltstack/salt/issues/55687)
- Fixed config.get does not support merge option with salt-ssh [#56441](https://github.com/saltstack/salt/issues/56441)
- Removed an unused assignment in file.patch [#57204](https://github.com/saltstack/salt/issues/57204)
- Fixed vault module fetching more than one secret in one run with single-use tokens [#57561](https://github.com/saltstack/salt/issues/57561)
- Use brew path from which in mac_brew_pkg module and rely on _homebrew_bin() everytime [#57946](https://github.com/saltstack/salt/issues/57946)
- Fixed Vault verify option to work on minions when only specified in master config [#58174](https://github.com/saltstack/salt/issues/58174)
- Fixed vault command errors configured locally [#58580](https://github.com/saltstack/salt/issues/58580)
- Fixed issue with basic auth causing invalid header error and 401 Bad Request, by using HTTPBasicAuthHandler instead of header. [#58936](https://github.com/saltstack/salt/issues/58936)
- Make the LXD module work with pyLXD > 2.10 [#59514](https://github.com/saltstack/salt/issues/59514)
- Return error if patch file passed to state file.patch is malformed. [#59806](https://github.com/saltstack/salt/issues/59806)
- Handle failure and error information from tuned module/state [#60500](https://github.com/saltstack/salt/issues/60500)
- Fixed sdb.get_or_set_hash with Vault single-use tokens [#60779](https://github.com/saltstack/salt/issues/60779)
- Fixed state.test does not work with salt-ssh [#61100](https://github.com/saltstack/salt/issues/61100)
- Made slsutil.findup work with salt-ssh [#61143](https://github.com/saltstack/salt/issues/61143)
- Allow all primitive grain types for autosign_grains [#61416](https://github.com/saltstack/salt/issues/61416), [#63708](https://github.com/saltstack/salt/issues/63708)
- `ipset.new_set` no longer fails when creating a set type that uses the `family` create option [#61620](https://github.com/saltstack/salt/issues/61620)
- Fixed Vault session storage to allow unlimited use tokens [#62380](https://github.com/saltstack/salt/issues/62380)
- fix the efi grain on FreeBSD [#63052](https://github.com/saltstack/salt/issues/63052)
- Fixed gpg.receive_keys returns success on failed import [#63144](https://github.com/saltstack/salt/issues/63144)
- Fixed GPG state module always reports success without changes [#63153](https://github.com/saltstack/salt/issues/63153)
- Fixed GPG state module does not respect test mode [#63156](https://github.com/saltstack/salt/issues/63156)
- Fixed gpg.absent with gnupghome/user, fixed gpg.delete_key with gnupghome [#63159](https://github.com/saltstack/salt/issues/63159)
- Fixed service module does not handle enable/disable if systemd service is an alias [#63214](https://github.com/saltstack/salt/issues/63214)
- Made x509_v2 compound match detection use new runner instead of peer publishing [#63278](https://github.com/saltstack/salt/issues/63278)
- Need to make sure we update __pillar__ during a pillar refresh to ensure that process_beacons has the updated beacons loaded from pillar. [#63583](https://github.com/saltstack/salt/issues/63583)
- This implements the vpc_uuid parameter when creating a droplet. This parameter selects the correct virtual private cloud (private network interface). [#63714](https://github.com/saltstack/salt/issues/63714)
- pkg.installed no longer reports failure when installing packages that are installed via the task manager [#63767](https://github.com/saltstack/salt/issues/63767)
- mac_xattr.list and mac_xattr.read will replace undecode-able bytes to avoid raising CommandExecutionError. [#63779](https://github.com/saltstack/salt/issues/63779) [#63779](https://github.com/saltstack/salt/issues/63779)
- Fix aptpkg.latest_version performance, reducing number of times to 'shell out' [#63982](https://github.com/saltstack/salt/issues/63982)
- Added option to use a fresh connection for mysql cache [#63991](https://github.com/saltstack/salt/issues/63991)
- [lxd] Fixed a bug in `container_create` which prevented devices which are not of type `disk` to be correctly created and added to the container when passed via the `devices` parameter. [#63996](https://github.com/saltstack/salt/issues/63996)
- Skipped the `isfile` check to greatly increase speed of reading minion keys for systems with a large number of minions on slow file storage [#64260](https://github.com/saltstack/salt/issues/64260)
- Fix utf8 handling in 'pass' renderer [#64300](https://github.com/saltstack/salt/issues/64300)
- Upgade tornado to 6.3.2 [#64305](https://github.com/saltstack/salt/issues/64305)
- Prevent errors due missing 'transactional_update.apply' on SLE Micro and MicroOS. [#64369](https://github.com/saltstack/salt/issues/64369)
- Fix 'unable to unmount' failure to return False result instead of None [#64420](https://github.com/saltstack/salt/issues/64420)
- Fixed issue uninstalling duplicate packages in ``win_appx`` execution module [#64450](https://github.com/saltstack/salt/issues/64450)
- Clean up tech debt, IPC now uses tcp transport. [#64488](https://github.com/saltstack/salt/issues/64488)
- Made salt-ssh more strict when handling unexpected situations and state.* wrappers treat a remote exception as failure, excluded salt-ssh error returns from mine [#64531](https://github.com/saltstack/salt/issues/64531)
- Fix flaky test for LazyLoader with isolated mocking of threading.RLock [#64567](https://github.com/saltstack/salt/issues/64567)
- Fix possible `KeyError` exceptions in `salt.utils.user.get_group_dict`
  while reading improper duplicated GID assigned for the user. [#64599](https://github.com/saltstack/salt/issues/64599)
- changed vm_config() to deep-merge vm_overrides of specific VM, instead of simple-merging the whole vm_overrides [#64610](https://github.com/saltstack/salt/issues/64610)
- Fix the way Salt tries to get the Homebrew's prefix

  The first attempt to get the Homebrew's prefix is to look for
  the `HOMEBREW_PREFIX` environment variable. If it's not set, then
  Salt tries to get the prefix from the `brew` command. However, the
  `brew` command can fail. So a last attempt is made to get the
  prefix by guessing the installation path. [#64924](https://github.com/saltstack/salt/issues/64924)
- Add missing MySQL Grant SERVICE_CONNECTION_ADMIN to mysql module. [#64934](https://github.com/saltstack/salt/issues/64934)
- Fixed slsutil.update with salt-ssh during template rendering [#65067](https://github.com/saltstack/salt/issues/65067)
- Keep track when an included file only includes sls files but is a requisite. [#65080](https://github.com/saltstack/salt/issues/65080)
- Fixed `gpg.present` succeeds when the keyserver is unreachable [#65169](https://github.com/saltstack/salt/issues/65169)
- Fix issue with openscap when the error was outside the expected scope. It now
  returns failed with the error code and the error [#65193](https://github.com/saltstack/salt/issues/65193)
- Fix typo in nftables module to ensure unique nft family values [#65295](https://github.com/saltstack/salt/issues/65295)
- Dereference symlinks to set proper __cli opt [#65435](https://github.com/saltstack/salt/issues/65435)
- Made salt-ssh merge master top returns for the same environment [#65480](https://github.com/saltstack/salt/issues/65480)
- Account for situation where the metadata grain fails because the AWS environment requires an authentication token to query the metadata URL. [#65513](https://github.com/saltstack/salt/issues/65513)
- Improve the condition of overriding target for pip with VENV_PIP_TARGET environment variable. [#65562](https://github.com/saltstack/salt/issues/65562)
- Added SSH wrapper for logmod [#65630](https://github.com/saltstack/salt/issues/65630)
- Include changes in the results when schedule.present state is run with test=True. [#65652](https://github.com/saltstack/salt/issues/65652)
- Fixed Salt-SSH pillar rendering and state rendering with nested SSH calls when called via saltutil.cmd or in an orchestration [#65670](https://github.com/saltstack/salt/issues/65670)
- Fix extfs.tune doesn't pass retcode to module.run [#65686](https://github.com/saltstack/salt/issues/65686)
- Fix boto execution module loading [#65691](https://github.com/saltstack/salt/issues/65691)
- Removed PR 65185 changes since incomplete solution [#65692](https://github.com/saltstack/salt/issues/65692)
- Return an error message when the DNS plugin is not supported [#65739](https://github.com/saltstack/salt/issues/65739)

# Added

- Allowed publishing to regular minions from the SSH wrapper [#40943](https://github.com/saltstack/salt/issues/40943)
- Added syncing of custom salt-ssh wrappers [#45450](https://github.com/saltstack/salt/issues/45450)
- Made salt-ssh sync custom utils [#53666](https://github.com/saltstack/salt/issues/53666)
- Add ability to use file.managed style check_cmd in file.serialize [#53982](https://github.com/saltstack/salt/issues/53982)
- Revised use of deprecated net-tools and added support for ip neighbour with IPv4 ip_neighs, IPv6 ip_neighs6 [#57541](https://github.com/saltstack/salt/issues/57541)
- Added password support to Redis returner. [#58044](https://github.com/saltstack/salt/issues/58044)
- Added keyring param to gpg modules [#59783](https://github.com/saltstack/salt/issues/59783)
- Added new grain to detect the Salt package type: onedir, pip or system [#62589](https://github.com/saltstack/salt/issues/62589)
- Added Vault AppRole and identity issuance to minions [#62823](https://github.com/saltstack/salt/issues/62823)
- Added Vault AppRole auth mount path configuration option [#62825](https://github.com/saltstack/salt/issues/62825)
- Added distribution of Vault authentication details via response wrapping [#62828](https://github.com/saltstack/salt/issues/62828)
- Add salt package type information. Either onedir, pip or system. [#62961](https://github.com/saltstack/salt/issues/62961)
- Added signature verification to file.managed/archive.extracted [#63143](https://github.com/saltstack/salt/issues/63143)
- Added signed_by_any/signed_by_all parameters to gpg.verify [#63166](https://github.com/saltstack/salt/issues/63166)
- Added match runner [#63278](https://github.com/saltstack/salt/issues/63278)
- Added Vault token lifecycle management [#63406](https://github.com/saltstack/salt/issues/63406)
- adding new call for openscap xccdf eval supporting new parameters [#63416](https://github.com/saltstack/salt/issues/63416)
- Added Vault lease management utility [#63440](https://github.com/saltstack/salt/issues/63440)
- implement removal of ptf packages in zypper pkg module [#63442](https://github.com/saltstack/salt/issues/63442)
- add JUnit output for saltcheck [#63463](https://github.com/saltstack/salt/issues/63463)
- Add ability for file.keyvalue to create a file if it doesn't exist [#63545](https://github.com/saltstack/salt/issues/63545)
- added cleanup of temporary mountpoint dir for macpackage installed state [#63905](https://github.com/saltstack/salt/issues/63905)
- Add pkg.installed show installable version in test mode [#63985](https://github.com/saltstack/salt/issues/63985)
- Added patch option to Vault SDB driver [#64096](https://github.com/saltstack/salt/issues/64096)
- Added flags to create local users and groups [#64256](https://github.com/saltstack/salt/issues/64256)
- Added inline specification of trusted CA root certificate for Vault [#64379](https://github.com/saltstack/salt/issues/64379)
- Add ability to return False result in test mode of configurable_test_state [#64418](https://github.com/saltstack/salt/issues/64418)
- Switched Salt's onedir Python version to 3.11 [#64457](https://github.com/saltstack/salt/issues/64457)
- Added support for dnf5 and its new command syntax [#64532](https://github.com/saltstack/salt/issues/64532)
- Adding a new decorator to indicate when a module is deprecated in favor of a Salt extension. [#64569](https://github.com/saltstack/salt/issues/64569)
- Add jq-esque to_entries and from_entries functions [#64600](https://github.com/saltstack/salt/issues/64600)
- Added ability to use PYTHONWARNINGS=ignore to silence deprecation warnings. [#64660](https://github.com/saltstack/salt/issues/64660)
- Add follow_symlinks to file.symlink exec module to switch to os.path.lexists when False [#64665](https://github.com/saltstack/salt/issues/64665)
- Added win_appx state and execution modules for managing Microsoft Store apps and deprovisioning them from systems [#64978](https://github.com/saltstack/salt/issues/64978)
- Add support for show_jid to salt-run

  Adds support for show_jid master config option to salt-run, so its behaviour matches the salt cli command. [#65008](https://github.com/saltstack/salt/issues/65008)
- Add ability to remove packages by wildcard via apt execution module [#65220](https://github.com/saltstack/salt/issues/65220)
- Added support for master top modules on masterless minions [#65479](https://github.com/saltstack/salt/issues/65479)
- Allowed accessing the regular mine from the SSH wrapper [#65645](https://github.com/saltstack/salt/issues/65645)
- Allow enabling backup for Linode in Salt Cloud [#65697](https://github.com/saltstack/salt/issues/65697)
- Add a backup schedule setter fFunction for Linode VMs [#65713](https://github.com/saltstack/salt/issues/65713)
- Add acme support for manual plugin hooks [#65744](https://github.com/saltstack/salt/issues/65744)

# Security

- Upgrade to `tornado>=6.3.3` due to https://github.com/advisories/GHSA-qppv-j76h-2rpx [#64989](https://github.com/saltstack/salt/issues/64989)
- Update to `gitpython>=3.1.35` due to https://github.com/advisories/GHSA-wfm5-v35h-vwf4 and https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65137](https://github.com/saltstack/salt/issues/65137)



* Tue Dec 12 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.5

# Removed

- Tech Debt - support for pysss removed due to functionality addition in Python 3.3 [#65029](https://github.com/saltstack/salt/issues/65029)

# Fixed

- Improved error message when state arguments are accidentally passed as a string [#38098](https://github.com/saltstack/salt/issues/38098)
- Allow `pip.install` to create a log file that is passed in if the parent directory is writeable [#44722](https://github.com/saltstack/salt/issues/44722)
- Fixed merging of complex pillar overrides with salt-ssh states [#59802](https://github.com/saltstack/salt/issues/59802)
- Fixed gpg pillar rendering with salt-ssh [#60002](https://github.com/saltstack/salt/issues/60002)
- Made salt-ssh states not re-render pillars unnecessarily [#62230](https://github.com/saltstack/salt/issues/62230)
- Made Salt maintain options in Debian package repo definitions [#64130](https://github.com/saltstack/salt/issues/64130)
- Migrated all [`invoke`](https://www.pyinvoke.org/) tasks to [`python-tools-scripts`](https://github.com/s0undt3ch/python-tools-scripts).

  * `tasks/docs.py` -> `tools/precommit/docs.py`
  * `tasks/docstrings.py` -> `tools/precommit/docstrings.py`
  * `tasks/loader.py` -> `tools/precommit/loader.py`
  * `tasks/filemap.py` -> `tools/precommit/filemap.py` [#64374](https://github.com/saltstack/salt/issues/64374)
- Fix salt user login shell path in Debian packages [#64377](https://github.com/saltstack/salt/issues/64377)
- Fill out lsb_distrib_xxxx (best estimate) grains if problems with retrieving lsb_release data [#64473](https://github.com/saltstack/salt/issues/64473)
- Fixed an issue in the ``file.directory`` state where the ``children_only`` keyword
  argument was not being respected. [#64497](https://github.com/saltstack/salt/issues/64497)
- Move salt.ufw to correct location /etc/ufw/applications.d/ [#64572](https://github.com/saltstack/salt/issues/64572)
- Fixed salt-ssh stacktrace when retcode is not an integer [#64575](https://github.com/saltstack/salt/issues/64575)
- Fixed SSH shell seldomly fails to report any exit code [#64588](https://github.com/saltstack/salt/issues/64588)
- Fixed some issues in x509_v2 execution module private key functions [#64597](https://github.com/saltstack/salt/issues/64597)
- Fixed grp.getgrall() in utils/user.py causing performance issues [#64888](https://github.com/saltstack/salt/issues/64888)
- Fix user.list_groups omits remote groups via sssd, etc. [#64953](https://github.com/saltstack/salt/issues/64953)
- Ensure sync from _grains occurs before attempting pillar compilation in case custom grain used in pillar file [#65027](https://github.com/saltstack/salt/issues/65027)
- Moved gitfs locks to salt working dir to avoid lock wipes [#65086](https://github.com/saltstack/salt/issues/65086)
- Only attempt to create a keys directory when `--gen-keys` is passed to the `salt-key` CLI [#65093](https://github.com/saltstack/salt/issues/65093)
- Fix nonce verification, request server replies do not stomp on eachother. [#65114](https://github.com/saltstack/salt/issues/65114)
- speed up yumpkg list_pkgs by not requiring digest or signature verification on lookup. [#65152](https://github.com/saltstack/salt/issues/65152)
- Fix pkg.latest failing on windows for winrepo packages where the package is already up to date [#65165](https://github.com/saltstack/salt/issues/65165)
- Ensure __kwarg__ is preserved when checking for kwargs.  This change affects proxy minions when used with Deltaproxy, which had kwargs popped when targeting multiple minions id. [#65179](https://github.com/saltstack/salt/issues/65179)
- Fixes traceback when state id is an int in a reactor SLS file. [#65210](https://github.com/saltstack/salt/issues/65210)
- Install logrotate config as /etc/logrotate.d/salt-common for Debian packages
  Remove broken /etc/logrotate.d/salt directory from 3006.3 if it exists. [#65231](https://github.com/saltstack/salt/issues/65231)
- Use ``sha256`` as the default ``hash_type``. It has been the default since Salt v2016.9 [#65287](https://github.com/saltstack/salt/issues/65287)
- Preserve ownership on log rotation [#65288](https://github.com/saltstack/salt/issues/65288)
- Ensure that the correct value of jid_inclue is passed if the argument is included in the passed keyword arguments. [#65302](https://github.com/saltstack/salt/issues/65302)
- Uprade relenv to 0.14.2
   - Update openssl to address CVE-2023-5363.
   - Fix bug in openssl setup when openssl binary can't be found.
   - Add M1 mac support. [#65316](https://github.com/saltstack/salt/issues/65316)
- Fix regex for filespec adding/deleting fcontext policy in selinux [#65340](https://github.com/saltstack/salt/issues/65340)
- Ensure CLI options take priority over Saltfile options [#65358](https://github.com/saltstack/salt/issues/65358)
- Test mode for state function `saltmod.wheel` no longer set's `result` to `(None,)` [#65372](https://github.com/saltstack/salt/issues/65372)
- Client only process events which tag conforms to an event return. [#65400](https://github.com/saltstack/salt/issues/65400)
- Fixes an issue setting user or machine policy on Windows when the Group Policy
  directory is missing [#65411](https://github.com/saltstack/salt/issues/65411)
- Fix regression in file module which was not re-using a file client. [#65450](https://github.com/saltstack/salt/issues/65450)
- pip.installed state will now properly fail when a specified user does not exists [#65458](https://github.com/saltstack/salt/issues/65458)
- Publish channel connect callback method properly closes it's request channel. [#65464](https://github.com/saltstack/salt/issues/65464)
- Ensured the pillar in SSH wrapper modules is the same as the one used in template rendering when overrides are passed [#65483](https://github.com/saltstack/salt/issues/65483)
- Fix file.comment ignore_missing not working with multiline char [#65501](https://github.com/saltstack/salt/issues/65501)
- Warn when an un-closed transport client is being garbage collected. [#65554](https://github.com/saltstack/salt/issues/65554)
- Only generate the HMAC's for ``libssl.so.1.1`` and ``libcrypto.so.1.1`` if those files exist. [#65581](https://github.com/saltstack/salt/issues/65581)
- Fixed an issue where Salt Cloud would fail if it could not delete lingering
  PAexec binaries [#65584](https://github.com/saltstack/salt/issues/65584)

# Added

- Added Salt support for Debian 12 [#64223](https://github.com/saltstack/salt/issues/64223)
- Added Salt support for Amazon Linux 2023 [#64455](https://github.com/saltstack/salt/issues/64455)

# Security

- Bump to `cryptography==41.0.4` due to https://github.com/advisories/GHSA-v8gr-m533-ghj9 [#65268](https://github.com/saltstack/salt/issues/65268)
- Bump to `cryptography==41.0.7` due to https://github.com/advisories/GHSA-jfhm-5ghh-2f97 [#65643](https://github.com/saltstack/salt/issues/65643)


* Mon Oct 16 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.4

# Security

- Fix CVE-2023-34049 by ensuring we do not use a predictable name for the script and correctly check returncode of scp command.
  This only impacts salt-ssh users using the pre-flight option. [#cve-2023-34049](https://github.com/saltstack/salt/issues/cve-2023-34049)
- Update to `gitpython>=3.1.35` due to https://github.com/advisories/GHSA-wfm5-v35h-vwf4 and https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65163](https://github.com/saltstack/salt/issues/65163)
- Bump to `cryptography==41.0.4` due to https://github.com/advisories/GHSA-v8gr-m533-ghj9 [#65268](https://github.com/saltstack/salt/issues/65268)
- Upgrade relenv to 0.13.12 to address CVE-2023-4807 [#65316](https://github.com/saltstack/salt/issues/65316)
- Bump to `urllib3==1.26.17` or `urllib3==2.0.6` due to https://github.com/advisories/GHSA-v845-jxx5-vc9f [#65334](https://github.com/saltstack/salt/issues/65334)
- Bump to `gitpython==3.1.37` due to https://github.com/advisories/GHSA-cwvm-v4w8-q58c [#65383](https://github.com/saltstack/salt/issues/65383)


* Wed Sep 06 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.3

# Removed

- Fedora 36 support was removed because it reached EOL [#64315](https://github.com/saltstack/salt/issues/64315)
- Handle deprecation warnings:

  * Switch to `FullArgSpec` since Py 3.11 no longer has `ArgSpec`, deprecated since Py 3.0
  * Stop using the deprecated `cgi` module
  * Stop using the deprecated `pipes` module
  * Stop using the deprecated `imp` module [#64553](https://github.com/saltstack/salt/issues/64553)

# Changed

- Replace libnacl with PyNaCl [#64372](https://github.com/saltstack/salt/issues/64372)
- Don't hardcode the python version on the Salt Package tests and on the `pkg/debian/salt-cloud.postinst` file [#64553](https://github.com/saltstack/salt/issues/64553)
- Some more deprecated code fixes:

  * Stop using the deprecated `locale.getdefaultlocale()` function
  * Stop accessing deprecated attributes
  * `pathlib.Path.__enter__()` usage is deprecated and not required, a no-op [#64565](https://github.com/saltstack/salt/issues/64565)
- Bump to `pyyaml==6.0.1` due to https://github.com/yaml/pyyaml/issues/601 and address lint issues [#64657](https://github.com/saltstack/salt/issues/64657)

# Fixed

- Fix for assume role when used salt-cloud to create aws ec2. [#52501](https://github.com/saltstack/salt/issues/52501)
- fixes aptpkg module by checking for blank comps. [#58667](https://github.com/saltstack/salt/issues/58667)
- `wheel.file_roots.find` is now able to find files in subdirectories of the roots. [#59800](https://github.com/saltstack/salt/issues/59800)
- pkg.latest no longer fails when multiple versions are reported to be installed (e.g. updating the kernel) [#60931](https://github.com/saltstack/salt/issues/60931)
- Do not update the credentials dictionary in `utils/aws.py` while iterating over it, and use the correct delete functionality [#61049](https://github.com/saltstack/salt/issues/61049)
- fixed runner not having a proper exit code when runner modules throw an exception. [#61173](https://github.com/saltstack/salt/issues/61173)
- `pip.list_all_versions` now works with `index_url` and `extra_index_url` [#61610](https://github.com/saltstack/salt/issues/61610)
- speed up file.recurse by using prefix with cp.list_master_dir and remove an un-needed loop. [#61998](https://github.com/saltstack/salt/issues/61998)
- Preserve test=True condition while running sub states. [#62590](https://github.com/saltstack/salt/issues/62590)
- Job returns are only sent to originating master [#62834](https://github.com/saltstack/salt/issues/62834)
- Fixes an issue with failing subsequent state runs with the lgpo state module.
  The ``lgpo.get_polcy`` function now returns all boolean settings. [#63296](https://github.com/saltstack/salt/issues/63296)
- Fix SELinux get policy with trailing whitespace [#63336](https://github.com/saltstack/salt/issues/63336)
- Fixes an issue with boolean settings not being reported after being set. The
  ``lgpo.get_polcy`` function now returns all boolean settings. [#63473](https://github.com/saltstack/salt/issues/63473)
- Ensure body is returned when salt.utils.http returns something other than 200 with tornado backend. [#63557](https://github.com/saltstack/salt/issues/63557)
- Allow long running pillar and file client requests to finish using request_channel_timeout and request_channel_tries minion config. [#63824](https://github.com/saltstack/salt/issues/63824)
- Fix state_queue type checking to allow int values [#64122](https://github.com/saltstack/salt/issues/64122)
- Call global logger when catching pip.list exceptions in states.pip.installed
  Rename global logger `log` to `logger` inside pip_state [#64169](https://github.com/saltstack/salt/issues/64169)
- Fixes permissions created by the Debian and RPM packages for the salt user.

  The salt user created by the Debian and RPM packages to run the salt-master process, was previously given ownership of various directories in a way which compromised the benefits of running the salt-master process as a non-root user.

  This fix sets the salt user to only have write access to those files and
  directories required for the salt-master process to run. [#64193](https://github.com/saltstack/salt/issues/64193)
- Fix user.present state when groups is unset to ensure the groups are unchanged, as documented. [#64211](https://github.com/saltstack/salt/issues/64211)
- Fixes issue with MasterMinion class loading configuration from `/etc/salt/minion.d/*.conf.

  The MasterMinion class (used for running orchestraions on master and other functionality) was incorrectly loading configuration from `/etc/salt/minion.d/*.conf`, when it should only load configuration from `/etc/salt/master` and `/etc/salt/master.d/*.conf`. [#64219](https://github.com/saltstack/salt/issues/64219)
- Fixed issue in mac_user.enable_auto_login that caused the user's keychain to be reset at each boot [#64226](https://github.com/saltstack/salt/issues/64226)
- Fixed KeyError in logs when running a state that fails. [#64231](https://github.com/saltstack/salt/issues/64231)
- Fixed x509_v2 `create_private_key`/`create_crl` unknown kwargs: __pub_fun... [#64232](https://github.com/saltstack/salt/issues/64232)
- remove the hard coded python version in error. [#64237](https://github.com/saltstack/salt/issues/64237)
- `salt-pip` now properly errors out when being called from a non `onedir` environment. [#64249](https://github.com/saltstack/salt/issues/64249)
- Ensure we return an error when adding the key fails in the pkgrepo state for debian hosts. [#64253](https://github.com/saltstack/salt/issues/64253)
- Fixed file client private attribute reference on `SaltMakoTemplateLookup` [#64280](https://github.com/saltstack/salt/issues/64280)
- Fix pkgrepo.absent failures on apt-based systems when repo either a) contains a
  trailing slash, or b) there is an arch mismatch. [#64286](https://github.com/saltstack/salt/issues/64286)
- Fix detection of Salt codename by "salt_version" execution module [#64306](https://github.com/saltstack/salt/issues/64306)
- Ensure selinux values are handled lowercase [#64318](https://github.com/saltstack/salt/issues/64318)
- Remove the `clr.AddReference`, it is causing an `Illegal characters in path` exception [#64339](https://github.com/saltstack/salt/issues/64339)
- Update `pkg.group_installed` state to support repo options [#64348](https://github.com/saltstack/salt/issues/64348)
- Fix salt user login shell path in Debian packages [#64377](https://github.com/saltstack/salt/issues/64377)
- Allow for multiple user's keys presented when authenticating, for example: root, salt, etc. [#64398](https://github.com/saltstack/salt/issues/64398)
- Fixed an issue with ``lgpo_reg`` where existing entries for the same key in
  ``Registry.pol`` were being overwritten in subsequent runs if the value name in
  the subesequent run was contained in the existing value name. For example, a
  key named ``SetUpdateNotificationLevel`` would be overwritten by a subsequent
  run attempting to set ``UpdateNotificationLevel`` [#64401](https://github.com/saltstack/salt/issues/64401)
- Add search for %ProgramData%\Chocolatey\choco.exe to determine if Chocolatey is installed or not [#64427](https://github.com/saltstack/salt/issues/64427)
- Fix regression for user.present on handling groups with dupe GIDs [#64430](https://github.com/saltstack/salt/issues/64430)
- Fix inconsistent use of args in ssh_auth.managed [#64442](https://github.com/saltstack/salt/issues/64442)
- Ensure we raise an error when the name argument is invalid in pkgrepo.managed state for systems using apt. [#64451](https://github.com/saltstack/salt/issues/64451)
- Fix file.symlink will not replace/update existing symlink [#64477](https://github.com/saltstack/salt/issues/64477)
- Fixed salt-ssh state.* commands returning retcode 0 when state/pillar rendering fails [#64514](https://github.com/saltstack/salt/issues/64514)
- Fix pkg.install when using a port in the url. [#64516](https://github.com/saltstack/salt/issues/64516)
- `win_pkg` Fixes an issue runing `pkg.install` with `version=latest` where the
  new installer would not be cached if there was already an installer present
  with the same name. [#64519](https://github.com/saltstack/salt/issues/64519)
- Added a `test:full` label in the salt repository, which, when selected, will force a full test run. [#64539](https://github.com/saltstack/salt/issues/64539)
- Syndic's async_req_channel uses the asynchornous version of request channel [#64552](https://github.com/saltstack/salt/issues/64552)
- Ensure runners properly save information to job cache. [#64570](https://github.com/saltstack/salt/issues/64570)
- Added salt.ufw to salt-master install on Debian and Ubuntu [#64572](https://github.com/saltstack/salt/issues/64572)
- Added support for Chocolatey 2.0.0+ while maintaining support for older versions [#64622](https://github.com/saltstack/salt/issues/64622)
- Updated semanage fcontext to use --modify if context already exists when adding context [#64625](https://github.com/saltstack/salt/issues/64625)
- Preserve request client socket between requests. [#64627](https://github.com/saltstack/salt/issues/64627)
- Show user friendly message when pillars timeout [#64651](https://github.com/saltstack/salt/issues/64651)
- File client timeouts durring jobs show user friendly errors instead of tracbacks [#64653](https://github.com/saltstack/salt/issues/64653)
- SaltClientError does not log a traceback on minions, we expect these to happen so a user friendly log is shown. [#64729](https://github.com/saltstack/salt/issues/64729)
- Look in location salt is running from, this accounts for running from an unpacked onedir file that has not been installed. [#64877](https://github.com/saltstack/salt/issues/64877)
- Preserve credentials on spawning platforms, minions no longer re-authenticate
  with every job when using `multiprocessing=True`. [#64914](https://github.com/saltstack/salt/issues/64914)
- Fixed uninstaller to not remove the `salt` directory by default. This allows
  the `extras-3.##` folder to persist so salt-pip dependencies are not wiped out
  during an upgrade. [#64957](https://github.com/saltstack/salt/issues/64957)
- fix msteams by adding the missing header that Microsoft is now enforcing. [#64973](https://github.com/saltstack/salt/issues/64973)
- Fix __env__ and improve cache cleaning see more info at pull #65017. [#65002](https://github.com/saltstack/salt/issues/65002)
- Better error message on inconsistent decoded payload [#65020](https://github.com/saltstack/salt/issues/65020)
- Handle permissions access error when calling `lsb_release` with the salt user [#65024](https://github.com/saltstack/salt/issues/65024)
- Allow schedule state module to update schedule when the minion is offline. [#65033](https://github.com/saltstack/salt/issues/65033)
- Fixed creation of wildcard DNS in SAN in `x509_v2` [#65072](https://github.com/saltstack/salt/issues/65072)
- The macOS installer no longer removes the extras directory [#65073](https://github.com/saltstack/salt/issues/65073)

# Added

- Added a script to automate setting up a 2nd minion in a user context on Windows [#64439](https://github.com/saltstack/salt/issues/64439)
- Several fixes to the CI workflow:

  * Don't override the `on` Jinja block on the `ci.yaml` template. This enables reacting to labels getting added/removed
    to/from pull requests.
  * Switch to using `tools` and re-use the event payload available instead of querying the GH API again to get the pull
    request labels
  * Concentrate test selection by labels to a single place
  * Enable code coverage on pull-requests by setting the `test:coverage` label [#64547](https://github.com/saltstack/salt/issues/64547)

# Security

- Upgrade to `cryptography==41.0.3`(and therefor `pyopenssl==23.2.0` due to https://github.com/advisories/GHSA-jm77-qphf-c4w8)

  This only really impacts pip installs of Salt and the windows onedir since the linux and macos onedir build every package dependency from source, not from pre-existing wheels.

  Also resolves the following cryptography advisories:

  Due to:
    * https://github.com/advisories/GHSA-5cpq-8wj7-hf2v
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r [#64595](https://github.com/saltstack/salt/issues/64595)
- Bump to `aiohttp==3.8.5` due to https://github.com/advisories/GHSA-45c4-8wx5-qw6w [#64687](https://github.com/saltstack/salt/issues/64687)
- Bump to `certifi==2023.07.22` due to https://github.com/advisories/GHSA-xqr8-7jwr-rhp7 [#64718](https://github.com/saltstack/salt/issues/64718)
- Upgrade `relenv` to `0.13.2` and Python to `3.10.12`

  Addresses multiple CVEs in Python's dependencies: https://docs.python.org/release/3.10.12/whatsnew/changelog.html#python-3-10-12 [#64719](https://github.com/saltstack/salt/issues/64719)
- Update to `gitpython>=3.1.32` due to https://github.com/advisories/GHSA-pr76-5cm5-w9cj [#64988](https://github.com/saltstack/salt/issues/64988)


* Wed Aug 09 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.2

# Fixed

- In scenarios where PythonNet fails to load, Salt will now fall back to WMI for
  gathering grains information [#64897](https://github.com/saltstack/salt/issues/64897)

# Security

- fix CVE-2023-20897 by catching exception instead of letting exception disrupt connection [#cve-2023-20897](https://github.com/saltstack/salt/issues/cve-2023-20897)
- Fixed gitfs cachedir_basename to avoid hash collisions. Added MP Lock to gitfs. These changes should stop race conditions. [#cve-2023-20898](https://github.com/saltstack/salt/issues/cve-2023-20898)
- Upgrade to `requests==2.31.0`

  Due to:
    * https://github.com/advisories/GHSA-j8r2-6x86-q33q [#64336](https://github.com/saltstack/salt/issues/64336)
- Upgrade to `cryptography==41.0.3`(and therefor `pyopenssl==23.2.0` due to https://github.com/advisories/GHSA-jm77-qphf-c4w8)

  This only really impacts pip installs of Salt and the windows onedir since the linux and macos onedir build every package dependency from source, not from pre-existing wheels.

  Also resolves the following cryptography advisories:

  Due to:
    * https://github.com/advisories/GHSA-5cpq-8wj7-hf2v
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r

  There is no security upgrade available for Py3.5 [#64595](https://github.com/saltstack/salt/issues/64595)
- Bump to `certifi==2023.07.22` due to https://github.com/advisories/GHSA-xqr8-7jwr-rhp7 [#64718](https://github.com/saltstack/salt/issues/64718)
- Upgrade `relenv` to `0.13.2` and Python to `3.10.12`

  Addresses multiple CVEs in Python's dependencies: https://docs.python.org/release/3.10.12/whatsnew/changelog.html#python-3-10-12 [#64719](https://github.com/saltstack/salt/issues/64719)


* Fri May 05 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.1

# Fixed

- Check that the return data from the cloud create function is a dictionary before attempting to pull values out. [#61236](https://github.com/saltstack/salt/issues/61236)
- Ensure NamedLoaderContext's have their value() used if passing to other modules [#62477](https://github.com/saltstack/salt/issues/62477)
- add documentation note about reactor state ids. [#63589](https://github.com/saltstack/salt/issues/63589)
- Added support for ``test=True`` to the ``file.cached`` state module [#63785](https://github.com/saltstack/salt/issues/63785)
- Updated `source_hash` documentation and added a log warning when `source_hash` is used with a source other than `http`, `https` and `ftp`. [#63810](https://github.com/saltstack/salt/issues/63810)
- Fixed clear pillar cache on every highstate and added clean_pillar_cache=False to saltutil functions. [#64081](https://github.com/saltstack/salt/issues/64081)
- Fix dmsetup device names with hyphen being picked up. [#64082](https://github.com/saltstack/salt/issues/64082)
- Update all the scheduler functions to include a fire_event argument which will determine whether to fire the completion event onto the event bus.
  This event is only used when these functions are called via the schedule execution modules.
  Update all the calls to the schedule related functions in the deltaproxy proxy minion to include fire_event=False, as the event bus is not available when these functions are called. [#64102](https://github.com/saltstack/salt/issues/64102), [#64103](https://github.com/saltstack/salt/issues/64103)
- Default to a 0 timeout if none is given for the terraform roster to avoid `-o ConnectTimeout=None` when using `salt-ssh` [#64109](https://github.com/saltstack/salt/issues/64109)
- Disable class level caching of the file client on `SaltCacheLoader` and properly use context managers to take care of initialization and termination of the file client. [#64111](https://github.com/saltstack/salt/issues/64111)
- Fixed several file client uses which were not properly terminating it by switching to using it as a context manager
  whenever possible or making sure `.destroy()` was called when using a context manager was not possible. [#64113](https://github.com/saltstack/salt/issues/64113)
- Fix running setup.py when passing in --salt-config-dir and --salt-cache-dir arguments. [#64114](https://github.com/saltstack/salt/issues/64114)
- Moved /etc/salt/proxy and /lib/systemd/system/salt-proxy@.service to the salt-minion DEB package [#64117](https://github.com/saltstack/salt/issues/64117)
- Stop passing `**kwargs` and be explicit about the keyword arguments to pass, namely, to `cp.cache_file` call in `salt.states.pkg` [#64118](https://github.com/saltstack/salt/issues/64118)
- lgpo_reg.set_value now returns ``True`` on success instead of ``None`` [#64126](https://github.com/saltstack/salt/issues/64126)
- Make salt user's home /opt/saltstack/salt [#64141](https://github.com/saltstack/salt/issues/64141)
- Fix cmd.run doesn't output changes in test mode [#64150](https://github.com/saltstack/salt/issues/64150)
- Move salt user and group creation to common package [#64158](https://github.com/saltstack/salt/issues/64158)
- Fixed issue in salt-cloud so that multiple masters specified in the cloud
  are written to the minion config properly [#64170](https://github.com/saltstack/salt/issues/64170)
- Make sure the `salt-ssh` CLI calls it's `fsclient.destroy()` method when done. [#64184](https://github.com/saltstack/salt/issues/64184)
- Stop using the deprecated `salt.transport.client` imports. [#64186](https://github.com/saltstack/salt/issues/64186)
- Add a `.pth` to the Salt onedir env to ensure packages in extras are importable. Bump relenv to 0.12.3. [#64192](https://github.com/saltstack/salt/issues/64192)
- Fix ``lgpo_reg`` state to work with User policy [#64200](https://github.com/saltstack/salt/issues/64200)
- Cloud deployment directories are owned by salt user and group [#64204](https://github.com/saltstack/salt/issues/64204)
- ``lgpo_reg`` state now enforces and reports changes to the registry [#64222](https://github.com/saltstack/salt/issues/64222)


* Tue Apr 18 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.0

# Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)
- Removed `SixRedirectImporter` from Salt. Salt hasn't shipped `six` since Salt 3004. [#63874](https://github.com/saltstack/salt/issues/63874)

# Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)

# Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)
- Upgraded to `relenv==0.9.0` [#63883](https://github.com/saltstack/salt/issues/63883)

# Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Remove mako as a dependency in Windows and macOS. [#62785](https://github.com/saltstack/salt/issues/62785)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- User responsible for the runner is now correctly reported in the events on the event bus for the runner. [#63148](https://github.com/saltstack/salt/issues/63148)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Fix rpm_lowpkg version comparison logic when using rpm-vercmp and only one version has a release number. [#63317](https://github.com/saltstack/salt/issues/63317)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- ``service.status`` on Windows does no longer throws a CommandExecutionError if
  the service is not found on the system. It now returns "Not Found" instead. [#63577](https://github.com/saltstack/salt/issues/63577)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- Fixed the ability to set a scheduled task to auto delete if not scheduled to run again (``delete_after``) [#63650](https://github.com/saltstack/salt/issues/63650)
- When a job is disabled only increase it's _next_fire_time value if the job would have run at the current time, eg. the current _next_fire_time == now. [#63699](https://github.com/saltstack/salt/issues/63699)
- have salt.template.compile_template_str cleanup its temp files. [#63724](https://github.com/saltstack/salt/issues/63724)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)
- Fixed an issue with generating fingerprints for public keys with different line endings [#63742](https://github.com/saltstack/salt/issues/63742)
- Add `fileserver_interval` and `maintenance_interval` master configuration options. These options control how often to restart the FileServerUpdate and Maintenance processes. Some file server and pillar configurations are known to cause memory leaks over time. A notable example of this are configurations that use pygit2. Salt can not guarantee dependency libraries like pygit2 won't leak memory. Restarting any long running processes that use pygit2 guarantees we can keep the master's memory usage in check. [#63747](https://github.com/saltstack/salt/issues/63747)
- mac_xattr.list and mac_xattr.read will replace undecode-able bytes to avoid raising CommandExecutionError. [#63779](https://github.com/saltstack/salt/issues/63779) [#63779](https://github.com/saltstack/salt/issues/63779)
- Change default GPG keyserver from pgp.mit.edu to keys.openpgp.org. [#63806](https://github.com/saltstack/salt/issues/63806)
- fix cherrypy 400 error output to be less generic. [#63835](https://github.com/saltstack/salt/issues/63835)
- Ensure kwargs is passed along to _call_apt when passed into install function. [#63847](https://github.com/saltstack/salt/issues/63847)
- remove eval and update logging to be more informative on bad config [#63879](https://github.com/saltstack/salt/issues/63879)
- add linux_distribution to util to stop dep warning [#63904](https://github.com/saltstack/salt/issues/63904)
- Fix valuerror when trying to close fileclient. Remove usage of __del__ and close the filclient properly. [#63920](https://github.com/saltstack/salt/issues/63920)
- Handle the situation when a sub proxy minion does not init properly, eg. an exception happens, and the sub proxy object is not available. [#63923](https://github.com/saltstack/salt/issues/63923)
- Clarifying documentation for extension_modules configuration option. [#63929](https://github.com/saltstack/salt/issues/63929)
- Windows pkg module now properly handles versions containing strings [#63935](https://github.com/saltstack/salt/issues/63935)
- Handle the scenario when the check_cmd requisite is used with a state function when the state has a local check_cmd function but that function isn't used by that function. [#63948](https://github.com/saltstack/salt/issues/63948)
- Issue #63981: Allow users to pass verify_ssl to pkg.install/pkg.installed on Windows [#63981](https://github.com/saltstack/salt/issues/63981)
- Hardened permissions on workers.ipc and master_event_pub.ipc. [#64063](https://github.com/saltstack/salt/issues/64063)

# Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Fix running fast tests twice and add git labels to suite. [#63081](https://github.com/saltstack/salt/issues/63081)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)
- Include the version of `relenv` in the versions report. [#63827](https://github.com/saltstack/salt/issues/63827)
- Added debug log messages displaying the command being run when removing packages on Windows [#63866](https://github.com/saltstack/salt/issues/63866)
- Adding the ability to exclude arguments from a state that end up passed to cmd.retcode when requisites such as onlyif or unless are used. [#63956](https://github.com/saltstack/salt/issues/63956)
- Add --next-release argument to salt/version.py, which prints the next upcoming release. [#64023](https://github.com/saltstack/salt/issues/64023)

# Security

- Upgrade Requirements Due to Security Issues.

  * Upgrade to `cryptography>=39.0.1` due to:
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r
  * Upgrade to `pyopenssl==23.0.0` due to the cryptography upgrade.
  * Update to `markdown-it-py==2.2.0` due to:
    * https://github.com/advisories/GHSA-jrwr-5x3p-hvc3
    * https://github.com/advisories/GHSA-vrjv-mxr7-vjf8 [#63882](https://github.com/saltstack/salt/issues/63882)


* Wed Mar 29 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.0~rc3

# Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)
- Removed `SixRedirectImporter` from Salt. Salt hasn't shipped `six` since Salt 3004. [#63874](https://github.com/saltstack/salt/issues/63874)

# Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)

# Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)
- Upgraded to `relenv==0.9.0` [#63883](https://github.com/saltstack/salt/issues/63883)

# Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Fix rpm_lowpkg version comparison logic when using rpm-vercmp and only one version has a release number. [#63317](https://github.com/saltstack/salt/issues/63317)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- Fixed the ability to set a scheduled task to auto delete if not scheduled to run again (``delete_after``) [#63650](https://github.com/saltstack/salt/issues/63650)
- When a job is disabled only increase it's _next_fire_time value if the job would have run at the current time, eg. the current _next_fire_time == now. [#63699](https://github.com/saltstack/salt/issues/63699)
- have salt.template.compile_template_str cleanup its temp files. [#63724](https://github.com/saltstack/salt/issues/63724)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)
- Fixed an issue with generating fingerprints for public keys with different line endings [#63742](https://github.com/saltstack/salt/issues/63742)
- Change default GPG keyserver from pgp.mit.edu to keys.openpgp.org. [#63806](https://github.com/saltstack/salt/issues/63806)
- fix cherrypy 400 error output to be less generic. [#63835](https://github.com/saltstack/salt/issues/63835)
- Ensure kwargs is passed along to _call_apt when passed into install function. [#63847](https://github.com/saltstack/salt/issues/63847)
- remove eval and update logging to be more informative on bad config [#63879](https://github.com/saltstack/salt/issues/63879)
- add linux_distribution to util to stop dep warning [#63904](https://github.com/saltstack/salt/issues/63904)
- Handle the situation when a sub proxy minion does not init properly, eg. an exception happens, and the sub proxy object is not available. [#63923](https://github.com/saltstack/salt/issues/63923)
- Clarifying documentation for extension_modules configuration option. [#63929](https://github.com/saltstack/salt/issues/63929)
- Windows pkg module now properly handles versions containing strings [#63935](https://github.com/saltstack/salt/issues/63935)
- Handle the scenario when the check_cmd requisite is used with a state function when the state has a local check_cmd function but that function isn't used by that function. [#63948](https://github.com/saltstack/salt/issues/63948)
- Issue #63981: Allow users to pass verify_ssl to pkg.install/pkg.installed on Windows [#63981](https://github.com/saltstack/salt/issues/63981)

# Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)
- Include the version of `relenv` in the versions report. [#63827](https://github.com/saltstack/salt/issues/63827)
- Added debug log messages displaying the command being run when removing packages on Windows [#63866](https://github.com/saltstack/salt/issues/63866)

# Security

- Upgrade Requirements Due to Security Issues.

  * Upgrade to `cryptography>=39.0.1` due to:
    * https://github.com/advisories/GHSA-x4qr-2fvf-3mr5
    * https://github.com/advisories/GHSA-w7pp-m8wf-vj6r
  * Upgrade to `pyopenssl==23.0.0` due to the cryptography upgrade.
  * Update to `markdown-it-py==2.2.0` due to:
    * https://github.com/advisories/GHSA-jrwr-5x3p-hvc3
    * https://github.com/advisories/GHSA-vrjv-mxr7-vjf8 [#63882](https://github.com/saltstack/salt/issues/63882)


* Sun Mar 19 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.0~rc2

# Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)
- Removed `SixRedirectImporter` from Salt. Salt hasn't shipped `six` since Salt 3004. [#63874](https://github.com/saltstack/salt/issues/63874)

# Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)

# Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)

# Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Fix rpm_lowpkg version comparison logic when using rpm-vercmp and only one version has a release number. [#63317](https://github.com/saltstack/salt/issues/63317)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- When a job is disabled only increase it's _next_fire_time value if the job would have run at the current time, eg. the current _next_fire_time == now. [#63699](https://github.com/saltstack/salt/issues/63699)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)
- fix cherrypy 400 error output to be less generic. [#63835](https://github.com/saltstack/salt/issues/63835)
- remove eval and update logging to be more informative on bad config [#63879](https://github.com/saltstack/salt/issues/63879)

# Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)
- Include the version of `relenv` in the versions report. [#63827](https://github.com/saltstack/salt/issues/63827)
- Added debug log messages displaying the command being run when removing packages on Windows [#63866](https://github.com/saltstack/salt/issues/63866)


* Wed Mar 01 2023 Salt Project Packaging <saltproject-packaging@vmware.com> - 3006.0~rc1

# Removed

- Remove and deprecate the __orchestration__ key from salt.runner and salt.wheel return data. To get it back, set features.enable_deprecated_orchestration_flag master configuration option to True. The flag will be completely removed in Salt 3008 Argon. [#59917](https://github.com/saltstack/salt/issues/59917)
- Removed distutils and replaced with setuptools, given distutils is deprecated and removed in Python 3.12 [#60476](https://github.com/saltstack/salt/issues/60476)
- Removed ``runtests`` targets from ``noxfile.py`` [#62239](https://github.com/saltstack/salt/issues/62239)
- Removed the PyObjC dependency.

  This addresses problems with building a one dir build for macOS.
  It became problematic because depending on the macOS version, it pulls different dependencies, and we would either have to build a macos onedir for each macOS supported release, or ship a crippled onedir(because it would be tied to the macOS version where the onedir was built).
  Since it's currently not being used, it's removed. [#62432](https://github.com/saltstack/salt/issues/62432)

# Deprecated

- renamed `keep_jobs`, specifying job cache TTL in hours, to `keep_jobs_seconds`, specifying TTL in seconds.
  `keep_jobs` will be removed in the Argon release [#55295](https://github.com/saltstack/salt/issues/55295)
- Removing all references to napalm-base which is no longer supported. [#61542](https://github.com/saltstack/salt/issues/61542)
- The 'ip_bracket' function has been moved from salt/utils/zeromq.py in salt/utils/network.py [#62009](https://github.com/saltstack/salt/issues/62009)
- The `expand_repo_def` function in `salt.modules.aptpkg` is now deprecated. It's only used in `salt.states.pkgrepo` and it has no use of being exposed to the CLI. [#62485](https://github.com/saltstack/salt/issues/62485)
- Deprecated defunct Django returner [#62644](https://github.com/saltstack/salt/issues/62644)
- Deprecate core ESXi and associated states and modules, vcenter and vsphere support in favor of Salt VMware Extensions [#62754](https://github.com/saltstack/salt/issues/62754)
- Removing manufacture grain which has been deprecated. [#62914](https://github.com/saltstack/salt/issues/62914)
- Removing deprecated utils/boto3_elasticsearch.py [#62915](https://github.com/saltstack/salt/issues/62915)
- Removing support for the now deprecated _ext_nodes from salt/master.py. [#62917](https://github.com/saltstack/salt/issues/62917)
- Deprecating the Salt Slack engine in favor of the Salt Slack Bolt Engine. [#63095](https://github.com/saltstack/salt/issues/63095)
- `salt.utils.version.StrictVersion` is now deprecated and it's use should be replaced with `salt.utils.version.Version`. [#63383](https://github.com/saltstack/salt/issues/63383)

# Changed

- More intelligent diffing in changes of file.serialize state. [#48609](https://github.com/saltstack/salt/issues/48609)
- Move deprecation of the neutron module to Argon. Please migrate to the neutronng module instead. [#49430](https://github.com/saltstack/salt/issues/49430)
- ``umask`` is now a global state argument, instead of only applying to ``cmd``
  states. [#57803](https://github.com/saltstack/salt/issues/57803)
- Update pillar.obfuscate to accept kwargs in addition to args.  This is useful when passing in keyword arguments like saltenv that are then passed along to pillar.items. [#58971](https://github.com/saltstack/salt/issues/58971)
- Improve support for listing macOS brew casks [#59439](https://github.com/saltstack/salt/issues/59439)
- Add missing MariaDB Grants to mysql module.
  MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating.
  Also improved exception handling in `grant_add` which did not log the original error message and replaced it with a generic error. [#61409](https://github.com/saltstack/salt/issues/61409)
- Use VENV_PIP_TARGET environment variable as a default target for pip if present. [#62089](https://github.com/saltstack/salt/issues/62089)
- Disabled FQDNs grains on macOS by default [#62168](https://github.com/saltstack/salt/issues/62168)
- Replaced pyroute2.IPDB with pyroute2.NDB, as the former is deprecated [#62218](https://github.com/saltstack/salt/issues/62218)
- Enhance capture of error messages for Zypper calls in zypperpkg module. [#62346](https://github.com/saltstack/salt/issues/62346)
- Removed GPG_1_3_1 check [#62895](https://github.com/saltstack/salt/issues/62895)
- Requisite state chunks now all consistently contain `__id__`, `__sls__` and `name`. [#63012](https://github.com/saltstack/salt/issues/63012)
- netapi_enable_clients option to allow enabling/disabling of clients in salt-api.
  By default all clients will now be disabled. Users of salt-api will need
  to update their master config to enable the clients that they use. Not adding
  the netapi_enable_clients option with required clients to the master config will
  disable salt-api. [#63050](https://github.com/saltstack/salt/issues/63050)
- Stop relying on `salt/_version.py` to write Salt's version. Instead use `salt/_version.txt` which only contains the version string. [#63383](https://github.com/saltstack/salt/issues/63383)
- Set enable_fqdns_grains to be False by default. [#63595](https://github.com/saltstack/salt/issues/63595)
- Changelog snippet files must now have a `.md` file extension to be more explicit on what type of rendering is done when they are included in the main `CHANGELOG.md` file. [#63710](https://github.com/saltstack/salt/issues/63710)

# Fixed

- Add kwargs to handle extra parameters for http.query [#36138](https://github.com/saltstack/salt/issues/36138)
- Fix mounted bind mounts getting active mount options added [#39292](https://github.com/saltstack/salt/issues/39292)
- Fix `sysctl.present` converts spaces to tabs. [#40054](https://github.com/saltstack/salt/issues/40054)
- Fixes state pkg.purged to purge removed packages on Debian family systems [#42306](https://github.com/saltstack/salt/issues/42306)
- Fix fun_args missing from syndic returns [#45823](https://github.com/saltstack/salt/issues/45823)
- Fix mount.mounted with 'mount: False' reports unmounted file system as unchanged when running with test=True [#47201](https://github.com/saltstack/salt/issues/47201)
- Issue #49310: Allow users to touch a file with Unix date of birth [#49310](https://github.com/saltstack/salt/issues/49310)
- Do not raise an exception in pkg.info_installed on nonzero return code [#51620](https://github.com/saltstack/salt/issues/51620)
- Passes the value of the force parameter from file.copy to its call to file.remove so that files with the read-only attribute are handled. [#51739](https://github.com/saltstack/salt/issues/51739)
- Fixed x509.certificate_managed creates new certificate every run in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#52167](https://github.com/saltstack/salt/issues/52167)
- Don't check for cached pillar errors on state.apply [#52354](https://github.com/saltstack/salt/issues/52354), [#57180](https://github.com/saltstack/salt/issues/57180), [#59339](https://github.com/saltstack/salt/issues/59339)
- Swapping out args and kwargs for arg and kwarg respectively in the Slack engine when the command passed is a runner. [#52400](https://github.com/saltstack/salt/issues/52400)
- Ensure when we're adding chunks to the rules when running aggregation with the iptables state module we use a copy of the chunk otherwise we end up with a recursive mess. [#53353](https://github.com/saltstack/salt/issues/53353)
- When user_create or user_remove fail, return False instead of returning the error. [#53377](https://github.com/saltstack/salt/issues/53377)
- Include sync_roster when sync_all is called. [#53914](https://github.com/saltstack/salt/issues/53914)
- Avoid warning noise in lograte.get [#53988](https://github.com/saltstack/salt/issues/53988)
- Fixed listing revoked keys with gpg.list_keys [#54347](https://github.com/saltstack/salt/issues/54347)
- Fix mount.mounted does not handle blanks properly [#54508](https://github.com/saltstack/salt/issues/54508)
- Fixed grain num_cpus get wrong CPUs count in case of inconsistent CPU numbering. [#54682](https://github.com/saltstack/salt/issues/54682)
- Fix spelling error for python_shell argument in dpkg_lower module [#54907](https://github.com/saltstack/salt/issues/54907)
- Cleaned up bytes response data before sending to non-bytes compatible returners (postgres, mysql) [#55226](https://github.com/saltstack/salt/issues/55226)
- Fixed malformed state return when testing file.managed with unavailable source file [#55269](https://github.com/saltstack/salt/issues/55269)
- Included stdout in error message for Zypper calls in zypperpkg module. [#56016](https://github.com/saltstack/salt/issues/56016)
- Fixed pillar.filter_by with salt-ssh [#56093](https://github.com/saltstack/salt/issues/56093)
- Fix boto_route53 issue with (multiple) VPCs. [#57139](https://github.com/saltstack/salt/issues/57139)
- Remove log from mine runner which was not used. [#57463](https://github.com/saltstack/salt/issues/57463)
- Fixed x509.read_certificate error when reading a Microsoft CA issued certificate in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#57535](https://github.com/saltstack/salt/issues/57535)
- Updating Slack engine to use slack_bolt library. [#57842](https://github.com/saltstack/salt/issues/57842)
- Fixed warning about replace=True with x509.certificate_managed in the new cryptography x509 module. [#58165](https://github.com/saltstack/salt/issues/58165)
- Fix salt.modules.pip:is_installed doesn't handle locally installed packages [#58202](https://github.com/saltstack/salt/issues/58202)
- Add missing MariaDB Grants to mysql module. MariaDB has added some grants in 10.4.x and 10.5.x that are not present here, which results in an error when creating. [#58297](https://github.com/saltstack/salt/issues/58297)
- linux_shadow: Fix cases where malformed shadow entries cause `user.present`
  states to fail. [#58423](https://github.com/saltstack/salt/issues/58423)
- Fixed salt.utils.compat.cmp to work with dictionaries [#58729](https://github.com/saltstack/salt/issues/58729)
- Fixed formatting for terse output mode [#58953](https://github.com/saltstack/salt/issues/58953)
- Fixed RecursiveDictDiffer with added nested dicts [#59017](https://github.com/saltstack/salt/issues/59017)
- Fixed x509.certificate_managed has DoS effect on master in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59169](https://github.com/saltstack/salt/issues/59169)
- Fixed saltnado websockets disconnecting immediately [#59183](https://github.com/saltstack/salt/issues/59183)
- Fixed x509.certificate_managed rolls certificates every now and then in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#59315](https://github.com/saltstack/salt/issues/59315)
- Fix postgres_privileges.present not idempotent for functions [#59585](https://github.com/saltstack/salt/issues/59585)
- Fixed influxdb_continuous_query.present state to provide the client args to the underlying module on create. [#59766](https://github.com/saltstack/salt/issues/59766)
- Warn when using insecure (http:// based) key_urls for apt-based systems in pkgrepo.managed, and add a kwarg that determines the validity of such a url. [#59786](https://github.com/saltstack/salt/issues/59786)
- add load balancing policy default option and ensure the module can be executed with arguments from CLI [#59909](https://github.com/saltstack/salt/issues/59909)
- Fix salt-ssh when using imports with extra-filerefs. [#60003](https://github.com/saltstack/salt/issues/60003)
- Fixed cache directory corruption startup error [#60170](https://github.com/saltstack/salt/issues/60170)
- Update docs remove dry_run in docstring of file.blockreplace state. [#60227](https://github.com/saltstack/salt/issues/60227)
- Adds Parrot to OS_Family_Map in grains. [#60249](https://github.com/saltstack/salt/issues/60249)
- Fixed stdout and stderr being empty sometimes when use_vt=True for the cmd.run[*] functions [#60365](https://github.com/saltstack/salt/issues/60365)
- Use return code in iptables --check to verify rule exists. [#60467](https://github.com/saltstack/salt/issues/60467)
- Fix regression pip.installed does not pass env_vars when calling pip.list [#60557](https://github.com/saltstack/salt/issues/60557)
- Fix xfs module when additional output included in mkfs.xfs command. [#60853](https://github.com/saltstack/salt/issues/60853)
- Fixed parsing new format of terraform states in roster.terraform [#60915](https://github.com/saltstack/salt/issues/60915)
- Fixed recognizing installed ARMv7 rpm packages in compatible architectures. [#60994](https://github.com/saltstack/salt/issues/60994)
- Fixing changes dict in pkg state to be consistent when installing and test=True. [#60995](https://github.com/saltstack/salt/issues/60995)
- Fix cron.present duplicating entries when changing timespec to special. [#60997](https://github.com/saltstack/salt/issues/60997)
- Made salt-ssh respect --wipe again [#61083](https://github.com/saltstack/salt/issues/61083)
- state.orchestrate_single only passes a pillar if it is set to the state
  function. This allows it to be used with state functions that don't accept a
  pillar keyword argument. [#61092](https://github.com/saltstack/salt/issues/61092)
- Fix ipset state when the comment kwarg is set. [#61122](https://github.com/saltstack/salt/issues/61122)
- Fix issue with archive.unzip where the password was not being encoded for the extract function [#61422](https://github.com/saltstack/salt/issues/61422)
- Some Linux distributions (like AlmaLinux, Astra Linux, Debian, Mendel, Linux
  Mint, Pop!_OS, Rocky Linux) report different `oscodename`, `osfullname`,
  `osfinger` grains if lsb-release is installed or not. They have been changed to
  only derive these OS grains from `/etc/os-release`. [#61618](https://github.com/saltstack/salt/issues/61618)
- Pop!_OS uses the full version (YY.MM) in the osfinger grain now, not just the year. This allows differentiating for example between 20.04 and 20.10. [#61619](https://github.com/saltstack/salt/issues/61619)
- Fix ssh config roster to correctly parse the ssh config files that contain spaces. [#61650](https://github.com/saltstack/salt/issues/61650)
- Fix SoftLayer configuration not raising an exception when a domain is missing [#61727](https://github.com/saltstack/salt/issues/61727)
- Allow the minion to start or salt-call to run even if the user doesn't have permissions to read the root_dir value from the registry [#61789](https://github.com/saltstack/salt/issues/61789)
- Need to move the creation of the proxy object for the ProxyMinion further down in the initialization for sub proxies to ensure that all modules, especially any custom proxy modules, are available before attempting to run the init function. [#61805](https://github.com/saltstack/salt/issues/61805)
- Fixed malformed state return when merge-serializing to an improperly formatted file [#61814](https://github.com/saltstack/salt/issues/61814)
- Made cmdmod._run[_all]_quiet work during minion startup on MacOS with runas specified (which fixed mac_service) [#61816](https://github.com/saltstack/salt/issues/61816)
- When deleting the vault cache, also delete from the session cache [#61821](https://github.com/saltstack/salt/issues/61821)
- Ignore errors on reading license info with dpkg_lowpkg to prevent tracebacks on getting package information. [#61827](https://github.com/saltstack/salt/issues/61827)
- win_lgpo: Display conflicting policy names when more than one policy is found [#61859](https://github.com/saltstack/salt/issues/61859)
- win_lgpo: Fixed intermittent KeyError when getting policy setting using lgpo.get_policy [#61860](https://github.com/saltstack/salt/issues/61860)
- Fixed listing minions on OpenBSD [#61966](https://github.com/saltstack/salt/issues/61966)
- Make Salt to return an error on "pkg" modules and states when targeting duplicated package names [#62019](https://github.com/saltstack/salt/issues/62019)
- Fix return of REST-returned permissions when auth_list is set [#62022](https://github.com/saltstack/salt/issues/62022)
- Normalize package names once on using pkg.installed/removed with yum to make it possible to install packages with the name containing a part similar to a name of architecture. [#62029](https://github.com/saltstack/salt/issues/62029)
- Fix inconsitency regarding name and pkgs parameters between zypperpkg.upgrade() and yumpkg.upgrade() [#62030](https://github.com/saltstack/salt/issues/62030)
- Fix attr=all handling in pkg.list_pkgs() (yum/zypper). [#62032](https://github.com/saltstack/salt/issues/62032)
- Fixed the humanname being ignored in pkgrepo.managed on openSUSE Leap [#62053](https://github.com/saltstack/salt/issues/62053)
- Fixed issue with some LGPO policies having whitespace at the beginning or end of the element alias [#62058](https://github.com/saltstack/salt/issues/62058)
- Fix ordering of args to libcloud_storage.download_object module [#62074](https://github.com/saltstack/salt/issues/62074)
- Ignore extend declarations in sls files that are excluded. [#62082](https://github.com/saltstack/salt/issues/62082)
- Remove leftover usage of impacket [#62101](https://github.com/saltstack/salt/issues/62101)
- Pass executable path from _get_path_exec() is used when calling the program.
  The $HOME env is no longer modified globally.
  Only trailing newlines are stripped from the fetched secret.
  Pass process arguments are handled in a secure way. [#62120](https://github.com/saltstack/salt/issues/62120)
- Ignore some command return codes in openbsdrcctl_service to prevent spurious errors [#62131](https://github.com/saltstack/salt/issues/62131)
- Fixed extra period in filename output in tls module. Instead of "server.crt." it will now be "server.crt". [#62139](https://github.com/saltstack/salt/issues/62139)
- Make sure lingering PAexec-*.exe files in the Windows directory are cleaned up [#62152](https://github.com/saltstack/salt/issues/62152)
- Restored Salt's DeprecationWarnings [#62185](https://github.com/saltstack/salt/issues/62185)
- Fixed issue with forward slashes on Windows with file.recurse and clean=True [#62197](https://github.com/saltstack/salt/issues/62197)
- Recognize OSMC as Debian-based [#62198](https://github.com/saltstack/salt/issues/62198)
- Fixed Zypper module failing on RPM lock file being temporarily unavailable. [#62204](https://github.com/saltstack/salt/issues/62204)
- Improved error handling and diagnostics in the proxmox salt-cloud driver [#62211](https://github.com/saltstack/salt/issues/62211)
- Added EndeavourOS to the Arch os_family. [#62220](https://github.com/saltstack/salt/issues/62220)
- Fix salt-ssh not detecting `platform-python` as a valid interpreter on EL8 [#62235](https://github.com/saltstack/salt/issues/62235)
- Fix pkg.version_cmp on openEuler and a few other os flavors. [#62248](https://github.com/saltstack/salt/issues/62248)
- Fix localhost detection in glusterfs.peers [#62273](https://github.com/saltstack/salt/issues/62273)
- Fix Salt Package Manager (SPM) exception when calling spm create_repo . [#62281](https://github.com/saltstack/salt/issues/62281)
- Fix matcher slowness due to loader invocation [#62283](https://github.com/saltstack/salt/issues/62283)
- Fixes the Puppet module for non-aio Puppet packages for example running the Puppet module on FreeBSD. [#62323](https://github.com/saltstack/salt/issues/62323)
- Issue 62334: Displays a debug log message instead of an error log message when the publisher fails to connect [#62334](https://github.com/saltstack/salt/issues/62334)
- Fix pyobjects renderer access to opts and sls [#62336](https://github.com/saltstack/salt/issues/62336)
- Fix use of random shuffle and sample functions as Jinja filters [#62372](https://github.com/saltstack/salt/issues/62372)
- Fix groups with duplicate GIDs are not returned by get_group_list [#62377](https://github.com/saltstack/salt/issues/62377)
- Fix the "zpool.present" state when enabling zpool features that are already active. [#62390](https://github.com/saltstack/salt/issues/62390)
- Fix ability to execute remote file client methods in saltcheck [#62398](https://github.com/saltstack/salt/issues/62398)
- Update all platforms to use pycparser 2.21 or greater for Py 3.9 or higher, fixes fips fault with openssl v3.x [#62400](https://github.com/saltstack/salt/issues/62400)
- Due to changes in the Netmiko library for the exception paths, need to check the version of Netmiko python library and then import the exceptions from different locations depending on the result. [#62405](https://github.com/saltstack/salt/issues/62405)
- When using preq on a state, then prereq state will first be run with test=True to determine if there are changes.  When there are changes, the state with the prereq option will be run prior to the prereq state.  If this state fails then the prereq state will not run and the state output uses the test=True run.  However, the proposed changes are included for the prereq state are included from the test=True run.  We should pull those out as there weren't actually changes since the prereq state did not run. [#62408](https://github.com/saltstack/salt/issues/62408)
- Added directory mode for file.copy with makedirs [#62426](https://github.com/saltstack/salt/issues/62426)
- Provide better error handling in the various napalm proxy minion functions when the device is not accessible. [#62435](https://github.com/saltstack/salt/issues/62435)
- When handling aggregation, change the order to ensure that the requisites are aggregated first and then the state functions are aggregated.  Caching whether aggregate functions are available for particular states so we don't need to attempt to load them everytime. [#62439](https://github.com/saltstack/salt/issues/62439)
- The patch allows to boostrap kubernetes clusters in the version above 1.13 via salt module [#62451](https://github.com/saltstack/salt/issues/62451)
- sysctl.persist now updates the in-memory value on FreeBSD even if the on-disk value was already correct. [#62461](https://github.com/saltstack/salt/issues/62461)
- Fixed parsing CDROM apt sources [#62474](https://github.com/saltstack/salt/issues/62474)
- Update sanitizing masking for Salt SSH to include additional password like strings. [#62483](https://github.com/saltstack/salt/issues/62483)
- Fix user/group checking on file state functions in the test mode. [#62499](https://github.com/saltstack/salt/issues/62499)
- Fix user.present to allow removing groups using optional_groups parameter and enforcing idempotent group membership. [#62502](https://github.com/saltstack/salt/issues/62502)
- Fix possible tracebacks if there is a package with '------' or '======' in the description is installed on the Debian based minion. [#62519](https://github.com/saltstack/salt/issues/62519)
- Fixed the omitted "pool" parameter when cloning a VM with the proxmox salt-cloud driver [#62521](https://github.com/saltstack/salt/issues/62521)
- Fix rendering of pyobjects states in saltcheck [#62523](https://github.com/saltstack/salt/issues/62523)
- Fixes pillar where a corrupted CacheDisk file forces the pillar to be rebuilt [#62527](https://github.com/saltstack/salt/issues/62527)
- Use str() method instead of repo_line for when python3-apt is installed or not in aptpkg.py. [#62546](https://github.com/saltstack/salt/issues/62546)
- Remove the connection_timeout from netmiko_connection_args before netmiko_connection_args is added to __context__["netmiko_device"]["args"] which is passed along to the Netmiko library. [#62547](https://github.com/saltstack/salt/issues/62547)
- Fix order specific mount.mounted options for persist [#62556](https://github.com/saltstack/salt/issues/62556)
- Fixed salt-cloud cloning a proxmox VM with a specified new vmid. [#62558](https://github.com/saltstack/salt/issues/62558)
- Fix runas with cmd module when using the onedir bundled packages [#62565](https://github.com/saltstack/salt/issues/62565)
- Update setproctitle version for all platforms [#62576](https://github.com/saltstack/salt/issues/62576)
- Fixed missing parameters when cloning a VM with the proxmox salt-cloud driver [#62580](https://github.com/saltstack/salt/issues/62580)
- Handle PermissionError when importing crypt when FIPS is enabled. [#62587](https://github.com/saltstack/salt/issues/62587)
- Correctly reraise exceptions in states.http [#62595](https://github.com/saltstack/salt/issues/62595)
- Fixed syndic eauth. Now jobs will be published when a valid eauth user is targeting allowed minions/functions. [#62618](https://github.com/saltstack/salt/issues/62618)
- updated rest_cherry/app to properly detect arg sent as a string as curl will do when only one arg is supplied. [#62624](https://github.com/saltstack/salt/issues/62624)
- Prevent possible tracebacks in core grains module by ignoring non utf8 characters in /proc/1/environ, /proc/1/cmdline, /proc/cmdline [#62633](https://github.com/saltstack/salt/issues/62633)
- Fixed vault ext pillar return data for KV v2 [#62651](https://github.com/saltstack/salt/issues/62651)
- Fix saltcheck _get_top_states doesn't pass saltenv to state.show_top [#62654](https://github.com/saltstack/salt/issues/62654)
- Fix groupadd.* functions hard code relative command name [#62657](https://github.com/saltstack/salt/issues/62657)
- Fixed pdbedit.create trying to use a bytes-like hash as string. [#62670](https://github.com/saltstack/salt/issues/62670)
- Fix depenency on legacy boto module in boto3 modules [#62672](https://github.com/saltstack/salt/issues/62672)
- Modified "_get_flags" function so that it returns regex flags instead of integers [#62676](https://github.com/saltstack/salt/issues/62676)
- Change startup ReqServer log messages from error to info level. [#62728](https://github.com/saltstack/salt/issues/62728)
- Fix kmod.* functions hard code relative command name [#62772](https://github.com/saltstack/salt/issues/62772)
- Fix mac_brew_pkg to work with null taps [#62793](https://github.com/saltstack/salt/issues/62793)
- Fixing a bug when listing the running schedule if "schedule.enable" and/or "schedule.disable" has been run, where the "enabled" items is being treated as a schedule item. [#62795](https://github.com/saltstack/salt/issues/62795)
- Prevent annoying RuntimeWarning message about line buffering (buffering=1) not being supported in binary mode [#62817](https://github.com/saltstack/salt/issues/62817)
- Include UID and GID checks in modules.file.check_perms as well as comparing
  ownership by username and group name. [#62818](https://github.com/saltstack/salt/issues/62818)
- Fix presence events on TCP transport by removing a client's presence when minion disconnects from publish channel correctly [#62826](https://github.com/saltstack/salt/issues/62826)
- Remove Azure deprecation messages from functions that always run w/ salt-cloud [#62845](https://github.com/saltstack/salt/issues/62845)
- Use select instead of iterating over entrypoints as a dictionary for importlib_metadata>=5.0.0 [#62854](https://github.com/saltstack/salt/issues/62854)
- Fixed master job scheduler using when [#62858](https://github.com/saltstack/salt/issues/62858)
- LGPO: Added support for missing domain controller policies: VulnerableChannelAllowList and LdapEnforceChannelBinding [#62873](https://github.com/saltstack/salt/issues/62873)
- Fix unnecessarily complex gce metadata grains code to use googles metadata service more effectively. [#62878](https://github.com/saltstack/salt/issues/62878)
- Fixed dockermod version_info function for docker-py 6.0.0+ [#62882](https://github.com/saltstack/salt/issues/62882)
- Moving setting the LOAD_BALANCING_POLICY_MAP dictionary into the try except block that determines if the cassandra_cql module should be made available. [#62886](https://github.com/saltstack/salt/issues/62886)
- Updating various MongoDB module functions to work with latest version of pymongo. [#62900](https://github.com/saltstack/salt/issues/62900)
- Restored channel for Syndic minions to send job returns to the Salt master. [#62933](https://github.com/saltstack/salt/issues/62933)
- removed _resolve_deps as it required a library that is not generally avalible. and switched to apt-get for everything as that can auto resolve dependencies. [#62934](https://github.com/saltstack/salt/issues/62934)
- Updated pyzmq to version 22.0.3 on Windows builds because the old version was causing salt-minion/salt-call to hang [#62937](https://github.com/saltstack/salt/issues/62937)
- Allow root user to modify crontab lines for non-root users (except AIX and Solaris). Align crontab line changes with the file ones and also with listing crontab. [#62940](https://github.com/saltstack/salt/issues/62940)
- Fix systemd_service.* functions hard code relative command name [#62942](https://github.com/saltstack/salt/issues/62942)
- Fix file.symlink backupname operation can copy remote contents to local disk [#62953](https://github.com/saltstack/salt/issues/62953)
- Issue #62968: Fix issue where cloud deployments were putting the keys in the wrong location on Windows hosts [#62968](https://github.com/saltstack/salt/issues/62968)
- Fixed gpg_passphrase issue with gpg decrypt/encrypt functions [#62977](https://github.com/saltstack/salt/issues/62977)
- Fix file.tidied FileNotFoundError [#62986](https://github.com/saltstack/salt/issues/62986)
- Fixed bug where module.wait states were detected as running legacy module.run syntax [#62988](https://github.com/saltstack/salt/issues/62988)
- Fixed issue with win_wua module where it wouldn't load if the CryptSvc was set to Manual start [#62993](https://github.com/saltstack/salt/issues/62993)
- The `__opts__` dunder dictionary is now added to the loader's `pack` if not
  already present, which makes it accessible via the
  `salt.loader.context.NamedLoaderContext` class. [#63013](https://github.com/saltstack/salt/issues/63013)
- Issue #63024: Fix issue where grains and config data were being place in the wrong location on Windows hosts [#63024](https://github.com/saltstack/salt/issues/63024)
- Fix btrfs.subvolume_snapshot command failing [#63025](https://github.com/saltstack/salt/issues/63025)
- Fix file.retention_schedule always reports changes [#63033](https://github.com/saltstack/salt/issues/63033)
- Fix mongo authentication for mongo ext_pillar and mongo returner

  This fix also include the ability to use the mongo connection string for mongo ext_pillar [#63058](https://github.com/saltstack/salt/issues/63058)
- Fixed x509.create_csr creates invalid CSR by default in the new cryptography x509 module. [#63103](https://github.com/saltstack/salt/issues/63103)
- TCP transport documentation now contains proper master/minion-side filtering information [#63120](https://github.com/saltstack/salt/issues/63120)
- Fixed gpg.verify does not respect gnupghome [#63145](https://github.com/saltstack/salt/issues/63145)
- Made pillar cache pass extra minion data as well [#63208](https://github.com/saltstack/salt/issues/63208)
- Fix serious performance issues with the file.tidied module [#63231](https://github.com/saltstack/salt/issues/63231)
- Import StrictVersion and LooseVersion from setuptools.distutils.verison or setuptools._distutils.version, if first not available [#63350](https://github.com/saltstack/salt/issues/63350)
- When the shell is passed as powershell or pwsh, only wrapper the shell in quotes if cmd.run is running on Windows.  When quoted on Linux hosts, this results in an error when the keyword arguments are appended. [#63590](https://github.com/saltstack/salt/issues/63590)
- LGPO: Added support for "Relax minimum password length limits" [#63596](https://github.com/saltstack/salt/issues/63596)
- Check file is not empty before attempting to read pillar disk cache file [#63729](https://github.com/saltstack/salt/issues/63729)

# Added

- Introduce a `LIB_STATE_DIR` syspaths variable which defaults to `CONFIG_DIR`,
  but can be individually customized during installation by specifying
  `--salt-lib-state-dir` during installation. Change the default `pki_dir` to
  `<LIB_STATE_DIR>/pki/master` (for the master) and `<LIB_STATE_DIR>/pki/minion`
  (for the minion). [#3396](https://github.com/saltstack/salt/issues/3396)
- Allow users to enable 'queue=True' for all state runs via config file [#31468](https://github.com/saltstack/salt/issues/31468)
- Added pillar templating to vault policies [#43287](https://github.com/saltstack/salt/issues/43287)
- Add support for NVMeF as a transport protocol for hosts in a Pure Storage FlashArray [#51088](https://github.com/saltstack/salt/issues/51088)
- A new salt-ssh roster that generates a roster by parses a known_hosts file. [#54679](https://github.com/saltstack/salt/issues/54679)
- Added Windows Event Viewer support [#54713](https://github.com/saltstack/salt/issues/54713)
- Added the win_lgpo_reg state and execution modules which will allow registry based group policy to be set directly in the Registry.pol file [#56013](https://github.com/saltstack/salt/issues/56013)
- Added resource tagging functions to boto_dynamodb execution module [#57500](https://github.com/saltstack/salt/issues/57500)
- Added `openvswitch_db` state module and functions `bridge_to_parent`,
  `bridge_to_vlan`, `db_get`, and `db_set` to the `openvswitch` execution module.
  Also added optional `parent` and `vlan` parameters to the
  `openvswitch_bridge.present` state module function and the
  `openvswitch.bridge_create` execution module function. [#58986](https://github.com/saltstack/salt/issues/58986)
- State module to manage SysFS attributes [#60154](https://github.com/saltstack/salt/issues/60154)
- Added ability for `salt.wait_for_event` to handle `event_id`s that have a list value. [#60430](https://github.com/saltstack/salt/issues/60430)
- Added suport for Linux ppc64le core grains (cpu_model, virtual, productname, manufacturer, serialnumber) and arm core grains (serialnumber, productname) [#60518](https://github.com/saltstack/salt/issues/60518)
- Added autostart option to virt.defined and virt.running states, along with virt.update execution modules. [#60700](https://github.com/saltstack/salt/issues/60700)
- Added .0 back to our versioning scheme for future versions (e.g. 3006.0) [#60722](https://github.com/saltstack/salt/issues/60722)
- Initial work to allow parallel startup of proxy minions when used as sub proxies with Deltaproxy. [#61153](https://github.com/saltstack/salt/issues/61153)
- Added node label support for GCE [#61245](https://github.com/saltstack/salt/issues/61245)
- Support the --priority flag when adding sources to Chocolatey. [#61319](https://github.com/saltstack/salt/issues/61319)
- Add namespace option to ext_pillar.http_json [#61335](https://github.com/saltstack/salt/issues/61335)
- Added a filter function to ps module to get a list of processes on a minion according to their state. [#61420](https://github.com/saltstack/salt/issues/61420)
- Add postgres.timeout option to postgres module for limiting postgres query times [#61433](https://github.com/saltstack/salt/issues/61433)
- Added new optional vault option, ``config_location``. This can be either ``master`` or ``local`` and defines where vault will look for connection details, either requesting them from the master or using the local config. [#61857](https://github.com/saltstack/salt/issues/61857)
- Add ipwrap() jinja filter to wrap IPv6 addresses with brackets. [#61931](https://github.com/saltstack/salt/issues/61931)
- 'tcp' transport is now available in ipv6-only network [#62009](https://github.com/saltstack/salt/issues/62009)
- Add `diff_attr` parameter to pkg.upgrade() (zypper/yum). [#62031](https://github.com/saltstack/salt/issues/62031)
- Config option pass_variable_prefix allows to distinguish variables that contain paths to pass secrets.
  Config option pass_strict_fetch allows to error out when a secret cannot be fetched from pass.
  Config option pass_dir allows setting the PASSWORD_STORE_DIR env for pass.
  Config option pass_gnupghome allows setting the $GNUPGHOME env for pass. [#62120](https://github.com/saltstack/salt/issues/62120)
- Add file.pruned state and expanded file.rmdir exec module functionality [#62178](https://github.com/saltstack/salt/issues/62178)
- Added "dig.PTR" function to resolve PTR records for IPs, as well as tests and documentation [#62275](https://github.com/saltstack/salt/issues/62275)
- Added the ability to remove a KB using the DISM state/execution modules [#62366](https://github.com/saltstack/salt/issues/62366)
- Add "<tiamat> python" subcommand to allow execution or arbitrary scripts via bundled Python runtime [#62381](https://github.com/saltstack/salt/issues/62381)
- Add ability to provide conditions which convert normal state actions to no-op when true [#62446](https://github.com/saltstack/salt/issues/62446)
- Added debug log messages displaying the command being run when installing packages on Windows [#62480](https://github.com/saltstack/salt/issues/62480)
- Add biosvendor grain [#62496](https://github.com/saltstack/salt/issues/62496)
- Add ifelse Jinja function as found in CFEngine [#62508](https://github.com/saltstack/salt/issues/62508)
- Implementation of Amazon EC2 instance detection and setting `virtual_subtype` grain accordingly including the product if possible to identify. [#62539](https://github.com/saltstack/salt/issues/62539)
- Adds __env__substitution to ext_pillar.stack; followup of #61531, improved exception handling for stacked template (jinja) template rendering and yaml parsing in ext_pillar.stack [#62578](https://github.com/saltstack/salt/issues/62578)
- Increase file.tidied flexibility with regard to age and size [#62678](https://github.com/saltstack/salt/issues/62678)
- Added "connected_devices" feature to netbox pillar module. It contains extra information about devices connected to the minion [#62761](https://github.com/saltstack/salt/issues/62761)
- Add atomic file operation for symlink changes [#62768](https://github.com/saltstack/salt/issues/62768)
- Add password/account locking/unlocking in user.present state on supported operating systems [#62856](https://github.com/saltstack/salt/issues/62856)
- Added onchange configuration for script engine [#62867](https://github.com/saltstack/salt/issues/62867)
- Added output and bare functionality to export_key gpg module function [#62978](https://github.com/saltstack/salt/issues/62978)
- Add keyvalue serializer for environment files [#62983](https://github.com/saltstack/salt/issues/62983)
- Add ability to ignore symlinks in file.tidied [#63042](https://github.com/saltstack/salt/issues/63042)
- salt-cloud support IMDSv2 tokens when using 'use-instance-role-credentials' [#63067](https://github.com/saltstack/salt/issues/63067)
- Add ability for file.symlink to not set ownership on existing links [#63093](https://github.com/saltstack/salt/issues/63093)
- Restore the previous slack engine and deprecate it, rename replace the slack engine to slack_bolt until deprecation [#63095](https://github.com/saltstack/salt/issues/63095)
- Add functions that will return the underlying block device, mount point, and filesystem type for a given path [#63098](https://github.com/saltstack/salt/issues/63098)
- Add ethtool execution and state module functions for pause [#63128](https://github.com/saltstack/salt/issues/63128)
- Add boardname grain [#63131](https://github.com/saltstack/salt/issues/63131)
- Added management of ECDSA/EdDSA private keys with x509 modules in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63248](https://github.com/saltstack/salt/issues/63248)
- Added x509 modules support for different output formats in the new cryptography x509 module. Please migrate to the new cryptography x509 module for this improvement. [#63249](https://github.com/saltstack/salt/issues/63249)
- Added deprecation_warning test state for ensuring that deprecation warnings are correctly emitted. [#63315](https://github.com/saltstack/salt/issues/63315)
- Adds a state_events option to state.highstate, state.apply, state.sls, state.sls_id.
  This allows users to enable state_events on a per use basis rather than having to
  enable them globally for all state runs. [#63316](https://github.com/saltstack/salt/issues/63316)
- Allow max queue size setting for state runs to prevent performance problems from queue growth [#63356](https://github.com/saltstack/salt/issues/63356)
- Add support of exposing meta_server_grains for Azure VMs [#63606](https://github.com/saltstack/salt/issues/63606)


* Tue Nov 01 2022 SaltStack Packaging Team <packaging@saltstack.com> - 3005-2
- Generate HMAC files post-install in case FIPS mode used only if libraries exist

* Tue Sep 27 2022 SaltStack Packaging Team <packaging@saltstack.com> - 3005-1
- Generate HMAC files post-install in case FIPS mode used
- Added MAN pages

* Fri Apr 10 2020 SaltStack Packaging Team <packaging@frogunder.com> - 3001
- Update to use pop-build

* Mon Feb 03 2020 SaltStack Packaging Team <packaging@frogunder.com> - 3000-1
- Update to feature release 3000-1  for Python 3

## - Removed Torando since salt.ext.tornado, add dependencies for Tornado

* Wed Jan 22 2020 SaltStack Packaging Team <packaging@garethgreenaway.com> - 3000.0.0rc2-1
- Update to Neon Release Candidate 2 for Python 3
- Updated spec file to not use py3_build  due to '-s' preventing pip installs
- Updated patch file to support Tornado4

* Wed Jan 08 2020 SaltStack Packaging Team <packaging@frogunder.com> - 2019.2.3-1
- Update to feature release 2019.2.3-1  for Python 3

* Tue Oct 15 2019 SaltStack Packaging Team <packaging@frogunder.com> - 2019.2.2-1
- Update to feature release 2019.2.2-1  for Python 3

* Thu Sep 12 2019 SaltStack Packaging Team <packaging@frogunder.com> - 2019.2.1-1
- Update to feature release 2019.2.1-1  for Python 3

* Tue Sep 10 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-10
- Support for point release, added distro as a requirement

* Tue Jul 02 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-9
- Support for point release, only rpmsign and tornado4 patches

* Thu Jun 06 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-8
- Support for Redhat 7 need for PyYAML and tornado 4 patch since Tornado < v5.x

* Thu May 23 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-7
- Patching in support for gpg-agent and passphrase preset

* Wed May 22 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-6
- Patching in fix for rpmsign

* Thu May 16 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-5
- Patching in fix for gpg str/bytes to to_unicode/to_bytes

* Tue May 14 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-4
- Patching in support for Tornado 4

* Mon May 13 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-3
- Added support for Redhat 8, and removed support for Python 2 packages

* Mon Apr 08 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-2
- Update to support Python 3.6

* Mon Apr 08 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2018.3.4-2
- Update to allow for Python 3.6

* Sat Feb 16 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-1
- Update to feature release 2019.2.0-1  for Python 3

* Sat Feb 16 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2018.3.4-1
- Update to feature release 2018.3.4-1  for Python 3

* Wed Jan 09 2019 SaltStack Packaging Team <packaging@saltstack.com> - 2019.2.0-0
- Update to feature release branch 2019.2.0-0 for Python 2
- Revised acceptable versions of cherrypy, futures

* Tue Oct 09 2018 SaltStack Packaging Team <packaging@saltstack.com> - 2018.3.3-1
- Update to feature release 2018.3.3-1  for Python 3
- Revised versions of cherrypy acceptable

* Mon Jun 11 2018 SaltStack Packaging Team <packaging@saltstack.com> - 2018.3.1-1
- Update to feature release 2018.3.1-1  for Python 3
- Revised minimum msgpack version >= 0.4

* Mon Apr 02 2018 SaltStack Packaging Team <packaging@saltstack.com> - 2018.3.0-1
- Development build for Python 3 support

* Tue Jan 30 2018 SaltStack Packaging Team <packaging@Ch3LL.com> - 2017.7.3-1
- Update to feature release 2017.7.3-1

* Mon Sep 18 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2017.7.2-1
- Update to feature release 2017.7.2

* Tue Aug 15 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2017.7.1-1
- Update to feature release 2017.7.1
- Altered dependency for dnf-utils instead of yum-utils if Fedora 26 or greater

* Wed Jul 12 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2017.7.0-1
- Update to feature release 2017.7.0
- Added python-psutil as a requirement, disabled auto enable for Redhat 6

* Thu Jun 22 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.6-1
- Update to feature release 2016.11.6

* Thu Apr 27 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.5-1
- Update to feature release 2016.11.5
- Altered to use pycryptodomex if 64 bit and Redhat 6 and greater otherwise pycrypto
- Addition of salt-proxy@.service

* Wed Apr 19 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.4-1
- Update to feature release 2016.11.4 and use of pycryptodomex

* Mon Mar 20 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.3-2
- Updated to allow for pre and post processing for salt-syndic and salt-api

* Wed Feb 22 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.3-1
- Update to feature release 2016.11.3

* Tue Jan 17 2017 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.2-1
- Update to feature release 2016.11.2

* Tue Dec 13 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.1-1
- Update to feature release 2016.11.1

* Wed Nov 30 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.0-2
- Adjust for single spec for Redhat family and fish-completions

* Tue Nov 22 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.0-1
- Update to feature release 2016.11.0

* Wed Nov  2 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.0-0.rc2
- Update to feature release 2016.11.0 Release Candidate 2

* Wed Oct 26 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.11.0-0.rc1
- Update to feature release 2016.11.0 Release Candidate 1

* Fri Oct 14 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.3-4
- Ported to build on Amazon Linux 2016.09 natively

* Mon Sep 12 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.3-3
- Adjust spec file for Fedora 24 support

* Tue Aug 30 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.3-2
- Fix systemd update of existing installation

* Fri Aug 26 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.3-1
- Update to feature release 2016.3.3

* Fri Jul 29 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.2-1
- Update to feature release 2016.3.2

* Fri Jun 10 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.1-1
- Update to feature release 2016.3.1

* Mon May 23 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.0-1
- Update to feature release 2016.3.0

* Wed Apr  6 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2016.3.0-rc2
- Update to bugfix release 2016.3.0 Release Candidate 2

* Fri Mar 25 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.8-2
- Patched fixes 32129, 32023, 32117

* Wed Mar 16 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.8-1
- Update to bugfix release 2015.8.8

* Tue Feb 16 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.7-1
- Update to bugfix release 2015.8.7

* Mon Jan 25 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.4-1
- Update to bugfix release 2015.8.4

* Thu Jan 14 2016 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.3-3
- Add systemd environment files

* Mon Dec  7 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.3-2
- Additional salt configuration directories on install

* Tue Dec  1 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.3-1
- Update to bugfix release 2015.8.3

* Fri Nov 13 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.2-1
- Update to bugfix release 2015.8.2

* Fri Oct 30 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.1-2
- Update for pre-install direcories

* Wed Oct  7 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.1-1
- Update to feature release 2015.8.1

* Wed Sep 30 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.0-3
- Update include python-uinttest2

* Wed Sep  9 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.0-2
- Update include testing

* Fri Sep  4 2015 SaltStack Packaging Team <packaging@saltstack.com> - 2015.8.0-1
- Update to feature release 2015.8.0

* Fri Jul 10 2015 Erik Johnson <erik@saltstack.com> - 2015.5.3-4
- Patch tests

* Fri Jul 10 2015 Erik Johnson <erik@saltstack.com> - 2015.5.3-3
- Patch init grain

* Fri Jul 10 2015 Erik Johnson <erik@saltstack.com> - 2015.5.3-2
- Update to bugfix release 2015.5.3, add bash completion

* Thu Jun  4 2015 Erik Johnson <erik@saltstack.com> - 2015.5.2-3
- Mark salt-ssh roster as a config file to prevent replacement

* Thu Jun  4 2015 Erik Johnson <erik@saltstack.com> - 2015.5.2-2
- Update skipped tests

* Thu Jun  4 2015 Erik Johnson <erik@saltstack.com> - 2015.5.2-1
- Update to bugfix release 2015.5.2

* Mon Jun  1 2015 Erik Johnson <erik@saltstack.com> - 2015.5.1-2
- Add missing dependency on which (RH #1226636)

* Wed May 27 2015 Erik Johnson <erik@saltstack.com> - 2015.5.1-1
- Update to bugfix release 2015.5.1

* Mon May 11 2015 Erik Johnson <erik@saltstack.com> - 2015.5.0-1
- Update to feature release 2015.5.0

* Fri Apr 17 2015 Erik Johnson <erik@saltstack.com> - 2014.7.5-1
- Update to bugfix release 2014.7.5

* Tue Apr  7 2015 Erik Johnson <erik@saltstack.com> - 2014.7.4-4
- Fix RH bug #1210316 and Salt bug #22003

* Tue Apr  7 2015 Erik Johnson <erik@saltstack.com> - 2014.7.4-2
- Update to bugfix release 2014.7.4

* Tue Feb 17 2015 Erik Johnson <erik@saltstack.com> - 2014.7.2-1
- Update to bugfix release 2014.7.2

* Mon Jan 19 2015 Erik Johnson <erik@saltstack.com> - 2014.7.1-1
- Update to bugfix release 2014.7.1

* Fri Nov  7 2014 Erik Johnson <erik@saltstack.com> - 2014.7.0-3
- Make salt-api its own package

* Thu Nov  6 2014 Erik Johnson <erik@saltstack.com> - 2014.7.0-2
- Fix changelog

* Thu Nov  6 2014 Erik Johnson <erik@saltstack.com> - 2014.7.0-1
- Update to feature release 2014.7.0

* Fri Oct 17 2014 Erik Johnson <erik@saltstack.com> - 2014.1.13-1
- Update to bugfix release 2014.1.13

* Mon Sep 29 2014 Erik Johnson <erik@saltstack.com> - 2014.1.11-1
- Update to bugfix release 2014.1.11

* Sun Aug 10 2014 Erik Johnson <erik@saltstack.com> - 2014.1.10-4
- Fix incorrect conditional

* Tue Aug  5 2014 Erik Johnson <erik@saltstack.com> - 2014.1.10-2
- Deploy cachedir with package

* Mon Aug  4 2014 Erik Johnson <erik@saltstack.com> - 2014.1.10-1
- Update to bugfix release 2014.1.10

* Thu Jul 10 2014 Erik Johnson <erik@saltstack.com> - 2014.1.7-3
- Add logrotate script

* Thu Jul 10 2014 Erik Johnson <erik@saltstack.com> - 2014.1.7-1
- Update to bugfix release 2014.1.7

* Wed Jun 11 2014 Erik Johnson <erik@saltstack.com> - 2014.1.5-1
- Update to bugfix release 2014.1.5

* Tue May  6 2014 Erik Johnson <erik@saltstack.com> - 2014.1.4-1
- Update to bugfix release 2014.1.4

* Thu Feb 20 2014 Erik Johnson <erik@saltstack.com> - 2014.1.0-1
- Update to feature release 2014.1.0

* Mon Jan 27 2014 Erik Johnson <erik@saltstack.com> - 0.17.5-1
- Update to bugfix release 0.17.5

* Thu Dec 19 2013 Erik Johnson <erik@saltstack.com> - 0.17.4-1
- Update to bugfix release 0.17.4

* Tue Nov 19 2013 Erik Johnson <erik@saltstack.com> - 0.17.2-2
- Patched to fix pkgrepo.managed regression

* Mon Nov 18 2013 Erik Johnson <erik@saltstack.com> - 0.17.2-1
- Update to bugfix release 0.17.2

* Thu Oct 17 2013 Erik Johnson <erik@saltstack.com> - 0.17.1-1
- Update to bugfix release 0.17.1

* Thu Sep 26 2013 Erik Johnson <erik@saltstack.com> - 0.17.0-1
- Update to feature release 0.17.0

* Wed Sep 11 2013 David Anderson <dave@dubkat.com>
- Change sourcing order of init functions and salt default file

* Sat Sep 07 2013 Erik Johnson <erik@saltstack.com> - 0.16.4-1
- Update to patch release 0.16.4

* Sun Aug 25 2013 Florian La Roche <Florian.LaRoche@gmx.net>
- fixed preun/postun scripts for salt-minion

* Thu Aug 15 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.16.3-1
- Update to patch release 0.16.3

* Thu Aug 8 2013 Clint Savage <herlo1@gmail.com> - 0.16.2-1
- Update to patch release 0.16.2

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.16.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Tue Jul 9 2013 Clint Savage <herlo1@gmail.com> - 0.16.0-1
- Update to feature release 0.16.0

* Sat Jun 1 2013 Clint Savage <herlo1@gmail.com> - 0.15.3-1
- Update to patch release 0.15.3
- Removed OrderedDict patch

* Fri May 31 2013 Clint Savage <herlo1@gmail.com> - 0.15.2-1
- Update to patch release 0.15.2
- Patch OrderedDict for failed tests (SaltStack#4912)

* Wed May 8 2013 Clint Savage <herlo1@gmail.com> - 0.15.1-1
- Update to patch release 0.15.1

* Sat May 4 2013 Clint Savage <herlo1@gmail.com> - 0.15.0-1
- Update to upstream feature release 0.15.0

* Fri Apr 19 2013 Clint Savage <herlo1@gmail.com> - 0.14.1-1
- Update to upstream patch release 0.14.1

* Sat Mar 23 2013 Clint Savage <herlo1@gmail.com> - 0.14.0-1
- Update to upstream feature release 0.14.0

* Fri Mar 22 2013 Clint Savage <herlo1@gmail.com> - 0.13.3-1
- Update to upstream patch release 0.13.3

* Wed Mar 13 2013 Clint Savage <herlo1@gmail.com> - 0.13.2-1
- Update to upstream patch release 0.13.2

* Fri Feb 15 2013 Clint Savage <herlo1@gmail.com> - 0.13.1-1
- Update to upstream patch release 0.13.1
- Add unittest support

* Sat Feb 02 2013 Clint Savage <herlo1@gmail.com> - 0.12.1-1
- Remove patches and update to upstream patch release 0.12.1

* Thu Jan 17 2013 Wendall Cada <wendallc@83864.com> - 0.12.0-2
- Added unittest support

* Wed Jan 16 2013 Clint Savage <herlo1@gmail.com> - 0.12.0-1
- Upstream release 0.12.0

* Fri Dec 14 2012 Clint Savage <herlo1@gmail.com> - 0.11.1-1
- Upstream patch release 0.11.1
- Fixes security vulnerability (https://github.com/saltstack/salt/issues/2916)

* Fri Dec 14 2012 Clint Savage <herlo1@gmail.com> - 0.11.0-1
- Moved to upstream release 0.11.0

* Wed Dec 05 2012 Mike Chesnut <mchesnut@gmail.com> - 0.10.5-2
- moved to upstream release 0.10.5
- removing references to minion.template and master.template, as those files
  have been removed from the repo

* Sun Nov 18 2012 Clint Savage <herlo1@gmail.com> - 0.10.5-1
- Moved to upstream release 0.10.5
- Added pciutils as Requires

* Wed Oct 24 2012 Clint Savage <herlo1@gmail.com> - 0.10.4-1
- Moved to upstream release 0.10.4
- Patched jcollie/systemd-service-status (SALT@GH#2335) (RHBZ#869669)

* Tue Oct 2 2012 Clint Savage <herlo1@gmail.com> - 0.10.3-1
- Moved to upstream release 0.10.3
- Added systemd scriplets (RHBZ#850408)

* Thu Aug 2 2012 Clint Savage <herlo1@gmail.com> - 0.10.2-2
- Fix upstream bug #1730 per RHBZ#845295

* Tue Jul 31 2012 Clint Savage <herlo1@gmail.com> - 0.10.2-1
- Moved to upstream release 0.10.2
- Removed PyXML as a dependency

* Sat Jun 16 2012 Clint Savage <herlo1@gmail.com> - 0.10.1-1
- Moved to upstream release 0.10.1

* Sat Apr 28 2012 Clint Savage <herlo1@gmail.com> - 0.9.9.1-1
- Moved to upstream release 0.9.9.1

* Tue Apr 17 2012 Peter Robinson <pbrobinson@fedoraproject.org> - 0.9.8-2
- dmidecode is x86 only

* Wed Mar 21 2012 Clint Savage <herlo1@gmail.com> - 0.9.8-1
- Moved to upstream release 0.9.8

* Thu Mar 8 2012 Clint Savage <herlo1@gmail.com> - 0.9.7-2
- Added dmidecode as a Requires

* Thu Feb 16 2012 Clint Savage <herlo1@gmail.com> - 0.9.7-1
- Moved to upstream release 0.9.7

* Tue Jan 24 2012 Clint Savage <herlo1@gmail.com> - 0.9.6-2
- Added README.fedora and removed deps for optional modules

* Sat Jan 21 2012 Clint Savage <herlo1@gmail.com> - 0.9.6-1
- New upstream release

* Sun Jan 8 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-6
- Missed some critical elements for SysV and rpmlint cleanup

* Sun Jan 8 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-5
- SysV clean up in post

* Sat Jan 7 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-4
- Cleaning up perms, group and descriptions, adding post scripts for systemd

* Thu Jan 5 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-3
- Updating for systemd on Fedora 15+

* Thu Dec 1 2011 Clint Savage <herlo1@gmail.com> - 0.9.4-2
- Removing requirement for Cython. Optional only for salt-minion

* Wed Nov 30 2011 Clint Savage <herlo1@gmail.com> - 0.9.4-1
- New upstream release with new features and bugfixes

* Thu Nov 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.3-1
- New upstream release with new features and bugfixes

* Sat Sep 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.2-1
- Bugfix release from upstream to fix python2.6 issues

* Fri Sep 09 2011 Clint Savage <herlo1@gmail.com> - 0.9.1-1
- Initial packages
