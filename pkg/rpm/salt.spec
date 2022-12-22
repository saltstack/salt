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

# Disable python bytecompile for MANY reasons
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

%define fish_dir %{_datadir}/fish/vendor_functions.d

Name:    salt
Version: 3006
Release: 0
Summary: A parallel remote execution system
Group:   System Environment/Daemons
License: ASL 2.0
URL:     https://saltproject.io/


BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch: x86_64

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
BuildRequires: libxcrypt-compat

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
mkdir -p $RPM_BUILD_DIR/opt/saltstack
mkdir -p $RPM_BUILD_DIR/usr/bin
cd $RPM_BUILD_DIR
python3 -m pip install relenv
relenv fetch
relenv toolchain fetch
relenv create $RPM_BUILD_DIR/opt/saltstack/salt
env RELENV_PIP_DIR=yes $RPM_BUILD_DIR/opt/saltstack/salt/bin/pip3 install --no-cache -v %{_salt_src}
# jmsepath doesn't use pip scripts
rm $RPM_BUILD_DIR/opt/saltstack/salt/jp.py


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/saltstack
cp -R $RPM_BUILD_DIR/* %{buildroot}/
mkdir -p %{buildroot}/opt/saltstack/salt
# pip installs directory
mkdir -p %{buildroot}/opt/saltstack/salt/pypath/

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
%{_unitdir}/salt-master.service
%config(noreplace) %{_sysconfdir}/salt/master
%dir %{_sysconfdir}/salt/master.d
%config(noreplace) %{_sysconfdir}/salt/pki/master

%files minion
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-call.1*
%doc %{_mandir}/man1/salt-minion.1*
%doc %{_mandir}/man1/salt-proxy.1*
%{_unitdir}/salt-minion.service
%{_unitdir}/salt-proxy@.service
%config(noreplace) %{_sysconfdir}/salt/minion
%config(noreplace) %{_sysconfdir}/salt/proxy
%config(noreplace) %{_sysconfdir}/salt/pki/minion
%dir %{_sysconfdir}/salt/minion.d

%files syndic
%doc %{_mandir}/man1/salt-syndic.1*
%{_unitdir}/salt-syndic.service

%files api
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-api.1*
%{_unitdir}/salt-api.service

%files cloud
%doc %{_mandir}/man1/salt-cloud.1*
%{_sysconfdir}/salt/cloud.conf.d
%{_sysconfdir}/salt/cloud.deploy.d
%{_sysconfdir}/salt/cloud.maps.d
%{_sysconfdir}/salt/cloud.profiles.d
%{_sysconfdir}/salt/cloud.providers.d
%config(noreplace) %{_sysconfdir}/salt/cloud

%files ssh
%doc %{_mandir}/man1/salt-ssh.1*
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
