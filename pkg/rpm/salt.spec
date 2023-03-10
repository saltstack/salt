%global __brp_check_rpaths %{nil}

%bcond_with tests
%bcond_with docs

# Disable build-id symlinks
%define _build_id_links none
%undefine _missing_build_ids_terminate_build
%define __brp_mangle_shebangs /usr/bin/true
%define __brp_python_hardlink /usr/bin/true

# Disable private libraries from showing in provides
%global __provides_exclude_from ^.*\\.so.*$
%global __requires_exclude_from ^.*\\.so.*$
%define _source_payload w2.gzdio
%define _binary_payload w2.gzdio

# Disable python bytecompile for MANY reasons
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

%define fish_dir %{_datadir}/fish/vendor_functions.d

Name:    salt
Version: 3006.0~rc1
Release: 0
Summary: A parallel remote execution system
Group:   System Environment/Daemons
License: ASL 2.0
URL:     https://saltproject.io/


BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%ifarch %{ix86} x86_64
Requires: dmidecode
%endif

Requires: pciutils
Requires: which
Requires: openssl


%if 0%{?systemd_preun:1}
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
%endif

BuildRequires: systemd-units
BuildRequires: python3
BuildRequires: python3-pip
BuildRequires: openssl
BuildRequires: git
%if %{rhel} >= 9
BuildRequires: libxcrypt-compat
%endif

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

%description master
The Salt master is the central server to which all minions connect.


%package    minion
Summary:    Client component for Salt, a parallel remote execution system
Group:      System Environment/Daemons
Requires:   %{name} = %{version}-%{release}

%description minion
The Salt minion is the agent component of Salt. It listens for instructions
from the master, runs jobs, and returns results back to the master.


%package    syndic
Summary:    Master-of-master component for Salt, a parallel remote execution system
Group:      System Environment/Daemons
Requires:   %{name}-master = %{version}-%{release}

%description syndic
The Salt syndic is a master daemon which can receive instruction from a
higher-level master, allowing for tiered organization of your Salt
infrastructure.


%package    api
Summary:    REST API for Salt, a parallel remote execution system
Group:      Applications/System
Requires:   %{name}-master = %{version}-%{release}

%description api
salt-api provides a REST interface to the Salt master.


%package    cloud
Summary:    Cloud provisioner for Salt, a parallel remote execution system
Group:      Applications/System
Requires:   %{name}-master = %{version}-%{release}

%description cloud
The salt-cloud tool provisions new cloud VMs, installs salt-minion on them, and
adds them to the master's collection of controllable minions.


%package    ssh
Summary:    Agentless SSH-based version of Salt, a parallel remote execution system
Group:      Applications/System
Requires:   %{name} = %{version}-%{release}

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
rm -rf $RPM_BUILD_DIR
mkdir -p $RPM_BUILD_DIR/build
cd $RPM_BUILD_DIR

%if "%{getenv:SALT_ONEDIR_ARCHIVE}" == ""
  python3 -m venv --clear --copies build/venv
  build/venv/bin/python3 -m pip install relenv
  build/venv/bin/relenv fetch
  build/venv/bin/relenv toolchain fetch
  build/venv/bin/relenv create build/salt
  build/salt/bin/python3 -m pip install "pip>=22.3.1,<23.0" "setuptools>=65.6.3,<66" "wheel"
  export PY=$(build/salt/bin/python3 -c 'import sys; sys.stdout.write("{}.{}".format(*sys.version_info)); sys.stdout.flush()')
  build/salt/bin/python3 -m pip install -r %{_salt_src}/requirements/static/pkg/py${PY}/linux.txt

  # Fix any hardcoded paths to the relenv python binary on any of the scripts installed in
  # the <onedir>/bin directory
  find build/salt/bin/ -type f -exec sed -i 's:#!/\(.*\)salt/bin/python3:#!/bin/sh\n"exec" "$(dirname $(readlink -f $0))/python3" "$0" "$@":g' {} \;

  export USE_STATIC_REQUIREMENTS=1
  export RELENV_PIP_DIR=1
  build/salt/bin/python3 -m pip install --no-warn-script-location %{_salt_src}

  build/salt/bin/python3 -m venv --clear --copies build/tools
  build/tools/bin/python3 -m pip install -r %{_salt_src}/requirements/static/ci/py${PY}/tools.txt
  cd %{_salt_src}
  $RPM_BUILD_DIR/build/tools/bin/tools pkg pre-archive-cleanup --pkg $RPM_BUILD_DIR/build/salt
%else
  # The relenv onedir is being provided, all setup up until Salt is installed
  # is expected to be done
  cd build
  tar xf ${SALT_ONEDIR_ARCHIVE}

  # Fix any hardcoded paths to the relenv python binary on any of the scripts installed in the <onedir>/bin directory
  find salt/bin/ -type f -exec sed -i 's:#!/\(.*\)salt/bin/python3:#!/bin/sh\n"exec" "$$(dirname $$(readlink -f $$0))/python3" "$$0" "$$@":g' {} \;

  cd $RPM_BUILD_DIR
%endif


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/saltstack
cp -R $RPM_BUILD_DIR/build/salt %{buildroot}/opt/saltstack/

# Add some directories
install -d -m 0755 %{buildroot}%{_var}/log/salt
install -d -m 0755 %{buildroot}%{_var}/cache/salt
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/master.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/minion.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/pki
install -d -m 0700 %{buildroot}%{_sysconfdir}/salt/pki/master
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
install -p -m 0640 %{_salt_src}/conf/master %{buildroot}%{_sysconfdir}/salt/master
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
install -p -m 0644 %{_salt_src}/pkg/common/salt-common.logrotate %{buildroot}%{_sysconfdir}/logrotate.d/salt

# Bash completion
mkdir -p %{buildroot}%{_sysconfdir}/bash_completion.d/
install -p -m 0644 %{_salt_src}/pkg/common/salt.bash %{buildroot}%{_sysconfdir}/bash_completion.d/salt.bash

# Fish completion (TBD remove -v)
mkdir -p %{buildroot}%{fish_dir}
install -p -m 0644 %{_salt_src}/pkg/common/fish-completions/*.fish  %{buildroot}%{fish_dir}/

# Man files
mkdir -p %{buildroot}%{_mandir}/man1
mkdir -p %{buildroot}%{_mandir}/man7
install -p -m 0644 %{_salt_src}/doc/man/spm.1 %{buildroot}%{_mandir}/man1/spm.1
install -p -m 0644 %{_salt_src}/doc/man/spm.1 %{buildroot}%{_mandir}/man1/spm.1
install -p -m 0644 %{_salt_src}/doc/man/salt.1 %{buildroot}%{_mandir}/man1/salt.1
install -p -m 0644 %{_salt_src}/doc/man/salt.7 %{buildroot}%{_mandir}/man7/salt.7
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
%dir %{_var}/log/salt
%doc %{_mandir}/man1/spm.1*
%{_bindir}/spm
%{_bindir}/salt-pip
/opt/saltstack/salt
%dir %{_sysconfdir}/salt
%dir %{_sysconfdir}/salt/pki




%files master
%defattr(-,root,root)
%doc %{_mandir}/man7/salt.7*
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


# assumes systemd for RHEL 7 & 8 & 9
%preun master
# RHEL 9 is giving warning msg if syndic is not installed, supress it
%systemd_preun salt-syndic.service > /dev/null 2>&1

%preun minion
%systemd_preun salt-minion.service

%preun api
%systemd_preun salt-api.service

%post
ln -s -f /opt/saltstack/salt/spm %{_bindir}/spm
ln -s -f /opt/saltstack/salt/salt-pip %{_bindir}/salt-pip

%post cloud
ln -s -f /opt/saltstack/salt/salt-cloud %{_bindir}/salt-cloud

%post master
%systemd_post salt-master.service
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
    /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/run/libssl.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/run/.libssl.so.1.1.hmac || :
    /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/run/libcrypto.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/run/.libcrypto.so.1.1.hmac || :
  fi
fi

%post syndic
%systemd_post salt-syndic.service
ln -s -f /opt/saltstack/salt/salt-syndic %{_bindir}/salt-syndic

%post minion
%systemd_post salt-minion.service
ln -s -f /opt/saltstack/salt/salt-minion %{_bindir}/salt-minion
ln -s -f /opt/saltstack/salt/salt-call %{_bindir}/salt-call
ln -s -f /opt/saltstack/salt/salt-proxy %{_bindir}/salt-proxy
if [ $1 -lt 2 ]; then
  # install
  # ensure hmac are up to date, master or minion, rest install one or the other
  # key used is from openssl/crypto/fips/fips_standalone_hmac.c openssl 1.1.1k
  if [ $(cat /etc/os-release | grep VERSION_ID | cut -d '=' -f 2 | sed  's/\"//g' | cut -d '.' -f 1) = "8" ]; then
    /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/run/libssl.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/run/.libssl.so.1.1.hmac || :
    /bin/openssl sha256 -r -hmac orboDeJITITejsirpADONivirpUkvarP /opt/saltstack/salt/run/libcrypto.so.1.1 | cut -d ' ' -f 1 > /opt/saltstack/salt/run/.libcrypto.so.1.1.hmac || :
  fi
fi

%post ssh
ln -s -f /opt/saltstack/salt/salt-ssh %{_bindir}/salt-ssh

%post api
%systemd_post salt-api.service
ln -s -f /opt/saltstack/salt/salt-api %{_bindir}/salt-api

%postun master
%systemd_postun_with_restart salt-master.service
if [ $1 -eq 0 ]; then
  if [ $(cat /etc/os-release | grep VERSION_ID | cut -d '=' -f 2 | sed  's/\"//g' | cut -d '.' -f 1) = "8" ]; then
    if [ -z "$(rpm -qi salt-minion | grep Name | grep salt-minion)" ]; then
      # uninstall and no minion running
      /bin/rm -f /opt/saltstack/salt/run/.libssl.so.1.1.hmac || :
      /bin/rm -f /opt/saltstack/salt/run/.libcrypto.so.1.1.hmac || :
    fi
  fi
fi

%postun syndic
%systemd_postun_with_restart salt-syndic.service

%postun minion
%systemd_postun_with_restart salt-minion.service
if [ $1 -eq 0 ]; then
  if [ $(cat /etc/os-release | grep VERSION_ID | cut -d '=' -f 2 | sed  's/\"//g' | cut -d '.' -f 1) = "8" ]; then
    if [ -z "$(rpm -qi salt-master | grep Name | grep salt-master)" ]; then
      # uninstall and no master running
      /bin/rm -f /opt/saltstack/salt/run/.libssl.so.1.1.hmac || :
      /bin/rm -f /opt/saltstack/salt/run/.libcrypto.so.1.1.hmac || :
    fi
  fi
fi

%postun api
%systemd_postun_with_restart salt-api.service


%changelog
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
