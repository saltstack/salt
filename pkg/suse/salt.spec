#
# spec file for package salt
#
# Copyright (c) 2015 SUSE LINUX GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#


%if 0%{?suse_version} > 1210
%bcond_without systemd
%else
%bcond_with    systemd
%endif
%{!?python_sitelib: %global python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%if 0%{?suse_version} > 1110
%bcond_without bash_completion
%bcond_without fish_completion
%bcond_without zsh_completion
%else
%bcond_with    bash_completion
%bcond_with    fish_completion
%bcond_with    zsh_completion
%endif
%bcond_with    test
%bcond_with    raet
%bcond_without docs

Name:           salt
Version:        2015.8.1
Release:        0
Summary:        A parallel remote execution system
License:        Apache-2.0
Group:          System/Monitoring
Url:            http://saltstack.org/
Source0:        http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz
Source1:        README.SUSE
Source2:        salt-tmpfiles.d
# PATCH-FIX-OPENSUSE use-forking-daemon.patch tserong@suse.com -- We don't have python-systemd, so notify can't work
Patch1:         use-forking-daemon.patch
# PATCH-OPENSUSE use-salt-user-for-master.patch -- Run salt master as dedicated salt user
Patch2:         use-salt-user-for-master.patch
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
BuildRequires:  logrotate
BuildRequires:  python
BuildRequires:  python-devel
# requirements/base.txt
BuildRequires:  python-Jinja2
BuildRequires:  python-futures >= 2.0
BuildRequires:  python-markupsafe
BuildRequires:  python-msgpack-python > 0.3
BuildRequires:  python-psutil
BuildRequires:  python-requests >= 1.0.0
BuildRequires:  python-tornado >= 4.2.1
BuildRequires:  python-yaml
# requirements/opt.txt (not all)
# BuildRequires:  python-MySQL-python
# BuildRequires:  python-timelib
# BuildRequires:  python-gnupg
# BuildRequires:  python-cherrypy >= 3.2.2
%if %{with raet}
# requirements/raet.txt
BuildRequires:  python-libnacl >= 1.0.0
BuildRequires:  python-ioflo >= 1.1.7
BuildRequires:  python-raet >= 0.6.0
%endif
# requirements/zeromq.txt
BuildRequires:  pycryptodomex >= 3.9.7
BuildRequires:  python-pyzmq >= 2.2.0
%if %{with test}
# requirements/dev_python27.txt
BuildRequires:  python-boto >= 2.32.1
BuildRequires:  python-mock
BuildRequires:  python-moto >= 0.3.6
BuildRequires:  python-pip
BuildRequires:  python-salt-testing >= 2015.2.16
BuildRequires:  python-unittest2
BuildRequires:  python-xml
%endif
%if %{with docs}
#for docs
BuildRequires:  python-sphinx
%endif

Requires(pre):  %{_sbindir}/groupadd
Requires(pre):  %{_sbindir}/useradd
%if 0%{?suse_version}
Requires(pre):  %fillup_prereq
Requires(pre):  pwdutils
%endif
Requires:       logrotate
Requires:       python
#
%if ! 0%{?suse_version} > 1110
Requires:       python-certifi
%endif
# requirements/base.txt
Requires:       python-Jinja2
Requires:       python-futures >= 2.0
Requires:       python-markupsafe
Requires:       python-msgpack-python > 0.3
Requires:       python-psutil
Requires:       python-requests >= 1.0.0
Requires:       python-tornado >= 4.2.1
Requires:       python-yaml
%if 0%{?suse_version}
# requirements/opt.txt (not all)
Recommends:     python-MySQL-python
Recommends:     python-timelib
Recommends:     python-gnupg
# requirements/raet.txt
# Recommends:     salt-raet
# requirements/zeromq.txt
%endif
Requires:       pycryptodomex >= 3.9.7
Requires:       python-pyzmq >= 2.2.0
#
%if 0%{?suse_version}
# python-xml is part of python-base in all rhel versions
Requires:       python-xml
Recommends:     python-Mako
Recommends:     python-netaddr
%endif

%if %{with systemd}
BuildRequires:  systemd
%{?systemd_requires}
%else
%if 0%{?suse_version}
Requires(pre): %insserv_prereq
%endif
%endif

%if %{with fish_completion}
%define fish_dir %{_datadir}/fish/
%define fish_completions_dir %{_datadir}/fish/completions/
%endif

%if %{with bash_completion}
%if 0%{?suse_version} >= 1140
BuildRequires:  bash-completion
%else
BuildRequires:  bash
%endif
%endif

%if %{with zsh_completion}
BuildRequires:  zsh
%endif

%description
Salt is a distributed remote execution system used to execute commands and
query data. It was developed in order to bring the best solutions found in
the world of remote execution together and make them better, faster and more
malleable. Salt accomplishes this via its ability to handle larger loads of
information, and not just dozens, but hundreds or even thousands of individual
servers, handle them quickly and through a simple and manageable interface.

%package api
Summary:        The api for Salt a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       %{name}-master = %{version}
Requires:       python-CherryPy >= 3.2.2

%description api
salt-api is a modular interface on top of Salt that can provide a variety of entry points into a running Salt system.

%package cloud
Summary:        Generic cloud provisioning tool for Saltstack
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       %{name}-master = %{version}
Requires:       python-apache-libcloud
%if 0%{?suse_version}
Recommends:     python-botocore
Recommends:     python-netaddr
%endif

%description cloud
public cloud VM management system
provision virtual machines on various public clouds via a cleanly
controlled profile and mapping system.

%if %{with docs}
%package doc
Summary:        Documentation for salt, a parallel remote execution system
Group:          Documentation/HTML
Requires:       %{name} = %{version}

%description doc
This contains the documentation of salt, it is an offline version of https://docs.saltproject.io.
%endif

%package master
Summary:        The management component of Saltstack both protocols zmq and raet supported
Group:          System/Monitoring
Requires:       %{name} = %{version}
%if 0%{?suse_version}
Recommends:     python-pygit2 >= 0.20.3
%endif
%ifarch %{ix86} x86_64
%if 0%{?suse_version}
Requires:       dmidecode
%endif
%endif
%if %{with systemd}
%{?systemd_requires}
%else
%if 0%{?suse_version}
Requires(pre):  %insserv_prereq
%endif
%endif
%if 0%{?suse_version}
Requires(pre):  %fillup_prereq
%endif

%description master
The Salt master is the central server to which all minions connect.
Enabled commands to remote systems to be called in parallel rather
than serially.

%package minion
Summary:        The client component for Saltstack
Group:          System/Monitoring
Requires:       %{name} = %{version}
%if %{with systemd}
%{?systemd_requires}
%else
%if 0%{?suse_version}
Requires(pre):  %insserv_prereq
%endif
%endif
%if 0%{?suse_version}
Requires(pre):  %fillup_prereq
%endif

%description minion
Salt minion is queried and controlled from the master.
Listens to the salt master and execute the commands.

%package raet
Summary:        Raet Support for Saltstack
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       python-enum34
Requires:       python-ioflo >= 1.1.7
Requires:       python-libnacl >= 1.0.0
Requires:       python-raet >= 0.6.0

%description raet
The Reliable Asynchronous Event Transport, or RAET, is an alternative transport
medium developed specifically with Salt in mind. It has been developed to allow
queuing to happen up on the application layer and comes with socket layer
encryption. It also abstracts a great deal of control over the socket layer and
makes it easy to bubble up errors and exceptions.

RAET also offers very powerful message routing capabilities, allowing for
messages to be routed between processes on a single machine all the way up to
processes on multiple machines. Messages can also be restricted, allowing
processes to be sent messages of specific types from specific sources allowing
for trust to be established.

%package proxy
Summary:        Component for salt that enables controlling arbitrary devices
Group:          System/Monitoring
Requires:       %{name} = %{version}
%if %{with systemd}
%{?systemd_requires}
%else
%if 0%{?suse_version}
Requires(pre):  %insserv_prereq
%endif
%endif
%if 0%{?suse_version}
Requires(pre):  %fillup_prereq
%endif

%description proxy
Proxy minions are a developing Salt feature that enables controlling devices that,
for whatever reason, cannot run a standard salt-minion.
Examples include network gear that has an API but runs a proprietary OS,
devices with limited CPU or memory, or devices that could run a minion, but for
security reasons, will not.


%package syndic
Summary:        The syndic component for saltstack
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       %{name}-master = %{version}
%if %{with systemd}
%{?systemd_requires}
%else
%if 0%{?suse_version}
Requires(pre):  %insserv_prereq
%endif
%endif
%if 0%{?suse_version}
Requires(pre):  %fillup_prereq
%endif

%description syndic
Salt syndic is the master-of-masters for salt
The master of masters for salt-- it enables
the management of multiple masters at a time..

%package ssh
Summary:        Management component for Saltstack with ssh protocol
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       %{name}-master = %{version}
%if 0%{?suse_version}
Recommends:     sshpass
%endif
%if %{with systemd}
%{?systemd_requires}
%else
%if 0%{?suse_version}
Requires(pre):  %insserv_prereq
%endif
%endif
%if 0%{?suse_version}
Requires(pre):  %fillup_prereq
%endif

%description ssh
Salt ssh is a master running without zmq.
it enables the management of minions over a ssh connection.

%if %{with bash_completion}
%package bash-completion
Summary:        Bash Completion for %{name}
Group:          System/Management
Requires:       %{name} = %{version}
Requires:       bash-completion
%if 0%{?suse_version} > 1110
BuildArch:      noarch
%endif

%description bash-completion
Bash command line completion support for %{name}.

%endif

%if %{with fish_completion}
%package fish-completion
Summary:        Fish Completion for %{name}
Group:          System/Management
Requires:       %{name} = %{version}

%if 0%{?suse_version} > 1110
BuildArch:      noarch
%endif

%description fish-completion
Fish command line completion support for %{name}.
%endif

%if %{with zsh_completion}
%package zsh-completion
Summary:        Zsh Completion for %{name}
Group:          System/Management
Requires:       %{name} = %{version}
Requires:       zsh
%if 0%{?suse_version} > 1110
BuildArch:      noarch
%endif

%description zsh-completion
Zsh command line completion support for %{name}.

%endif

%prep
%setup -q -n salt-%{version}
cp %{S:1} .
%patch1 -p1
%patch2 -p1

%build
python setup.py --salt-transport=both build

%if %{with docs}
## documentation
cd doc && make html && rm _build/html/.buildinfo && rm _build/html/_images/proxy_minions.png && cd _build/html && chmod -R -x+X *
%endif

%install
python setup.py --salt-transport=both install --prefix=%{_prefix} --root=%{buildroot}
## create missing directories
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/master.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/minion.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/cloud.maps.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/cloud.profiles.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/cloud.providers.d
install -Dd -m 0750 %{buildroot}%{_localstatedir}/log/salt
install -Dd -m 0755 %{buildroot}%{_sysconfdir}/logrotate.d/
install -Dd -m 0755 %{buildroot}%{_sbindir}
install -Dd -m 0750 %{buildroot}%{_localstatedir}/log/salt
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/minion/extmod
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/master
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/master/jobs
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/master/proc
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/master/queues
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/master/roots
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/master/syndics
install -Dd -m 0750 %{buildroot}%{_localstatedir}/cache/salt/master/tokens
install -Dd -m 0750 %{buildroot}/srv/salt
install -Dd -m 0750 %{buildroot}/srv/pillar
install -Dd -m 0750 %{buildroot}/srv/spm
install -Dd -m 0755 %{buildroot}%{_docdir}/salt
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/cloud.maps.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/cloud.profiles.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/cloud.providers.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/master.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/minion.d
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_autosign
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_denied
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_pre
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/master/minions_rejected
install -Dd -m 0750 %{buildroot}%{_sysconfdir}/salt/pki/minion

## install init and systemd scripts
%if %{with systemd}
install -Dpm 0644 pkg/salt-master.service %{buildroot}%{_unitdir}/salt-master.service
install -Dpm 0644 pkg/salt-minion.service %{buildroot}%{_unitdir}/salt-minion.service
install -Dpm 0644 pkg/salt-syndic.service %{buildroot}%{_unitdir}/salt-syndic.service
install -Dpm 0644 pkg/salt-api.service    %{buildroot}%{_unitdir}/salt-api.service
ln -s service %{buildroot}%{_sbindir}/rcsalt-master
ln -s service %{buildroot}%{_sbindir}/rcsalt-syndic
ln -s service %{buildroot}%{_sbindir}/rcsalt-minion
ln -s service %{buildroot}%{_sbindir}/rcsalt-api
install -Dpm 644 %{S:2}                   %{buildroot}/usr/lib/tmpfiles.d/salt.conf
%else
mkdir -p %{buildroot}%{_initddir}
## install init scripts
install -Dpm 0755 pkg/suse/salt-master %{buildroot}%{_initddir}/salt-master
install -Dpm 0755 pkg/suse/salt-syndic %{buildroot}%{_initddir}/salt-syndic
install -Dpm 0755 pkg/suse/salt-minion %{buildroot}%{_initddir}/salt-minion
install -Dpm 0755 pkg/suse/salt-api %{buildroot}%{_initddir}/salt-api
ln -sf %{_initddir}/salt-master %{buildroot}%{_sbindir}/rcsalt-master
ln -sf %{_initddir}/salt-syndic %{buildroot}%{_sbindir}/rcsalt-syndic
ln -sf %{_initddir}/salt-minion %{buildroot}%{_sbindir}/rcsalt-minion
ln -sf %{_initddir}/salt-api %{buildroot}%{_sbindir}/rcsalt-api
%endif

#
## install config files
install -Dpm 0640 conf/minion %{buildroot}%{_sysconfdir}/salt/minion
install -Dpm 0640 /dev/null   %{buildroot}%{_sysconfdir}/salt/minion_id
install -Dpm 0640 conf/master %{buildroot}%{_sysconfdir}/salt/master
install -Dpm 0640 conf/roster %{buildroot}%{_sysconfdir}/salt/roster
install -Dpm 0640 conf/cloud %{buildroot}%{_sysconfdir}/salt/cloud
install -Dpm 0640 conf/cloud.profiles %{buildroot}%{_sysconfdir}/salt/cloud.profiles
install -Dpm 0640 conf/cloud.providers %{buildroot}%{_sysconfdir}/salt/cloud.providers
#
## install logrotate file
install -Dpm 0644  pkg/salt-common.logrotate %{buildroot}%{_sysconfdir}/logrotate.d/salt
#
## install SuSEfirewall2 rules
install -Dpm 0644  pkg/suse/salt.SuSEfirewall2 %{buildroot}%{_sysconfdir}/sysconfig/SuSEfirewall2.d/services/salt
#
## install completion scripts
%if %{with bash_completion}
install -Dpm 0644 pkg/salt.bash %{buildroot}%{_sysconfdir}/bash_completion.d/salt
%endif
%if %{with zsh_completion}
install -Dpm 0644 pkg/salt.zsh %{buildroot}%{_sysconfdir}/zsh_completion.d/salt
%endif

%if %{with fish_completion}
mkdir -p %{buildroot}%{fish_completions_dir}
install -Dpm 0644 pkg/fish-completions/* %{buildroot}%{fish_completions_dir}
%endif

# raet transport config
echo "transport: raet" > %{buildroot}%{_sysconfdir}/salt/master.d/transport-raet.conf
echo "transport: raet" > %{buildroot}%{_sysconfdir}/salt/minion.d/transport-raet.conf

%check
%if %{with test}
python setup.py test --runtests-opts=-u
%endif

%pre
getent group salt >/dev/null || %{_sbindir}/groupadd -r salt
getent passwd salt >/dev/null || %{_sbindir}/useradd -r -g salt -d /srv/salt -s /bin/false -c "salt-master daemon" salt

%if %{with systemd}
%post
systemd-tmpfiles --create /usr/lib/tmpfiles.d/salt.conf || true
%endif

%preun syndic
%if %{with systemd}
%service_del_preun salt-syndic.service
%else
%if 0%{?suse_version}
%stop_on_removal salt-syndic
%else
  if [ $1 -eq 0 ] ; then
      /sbin/service salt-syndic stop >/dev/null 2>&1
      /sbin/chkconfig --del salt-syndic
  fi
%endif
%endif

%pre syndic
%if %{with systemd}
%service_add_pre salt-syndic.service
%endif

%post syndic
%if %{with systemd}
%service_add_post salt-syndic.service
%fillup_only
%else
%if 0%{?suse_version}
%fillup_and_insserv
%endif
%endif

%postun syndic
%if %{with systemd}
%service_del_postun salt-syndic.service
%else
%if 0%{?suse_version}
%insserv_cleanup
%restart_on_update salt-syndic
%endif
%endif

%preun master
%if %{with systemd}
%service_del_preun salt-master.service
%else
%if 0%{?suse_version}
%stop_on_removal salt-master
%else
  if [ $1 -eq 0 ] ; then
      /sbin/service salt-master stop >/dev/null 2>&1
      /sbin/chkconfig --del salt-master
  fi
%endif
%endif

%pre master
%if %{with systemd}
%service_add_pre salt-master.service
%endif

%post master
%if %{with systemd}
%service_add_post salt-master.service
%fillup_only
%else
%if 0%{?suse_version}
%fillup_and_insserv
%else
  /sbin/chkconfig --add salt-master
%endif
%endif

%postun master
%if %{with systemd}
%service_del_postun salt-master.service
%else
%if 0%{?suse_version}
%restart_on_update salt-master
%insserv_cleanup
%else
  if [ "$1" -ge "1" ] ; then
      /sbin/service salt-master condrestart >/dev/null 2>&1 || :
  fi
%endif
%endif

%preun minion
%if %{with systemd}
%service_del_preun salt-minion.service
%else
%if 0%{?suse_version}
%stop_on_removal salt-minion
%else
  if [ $1 -eq 0 ] ; then
      /sbin/service salt-minion stop >/dev/null 2>&1
      /sbin/chkconfig --del salt-minion
  fi
%endif
%endif

%pre minion
%if %{with systemd}
%service_add_pre salt-minion.service
%endif

%post minion
%if %{with systemd}
%service_add_post salt-minion.service
%fillup_only
%else
%if 0%{?suse_version}
%fillup_and_insserv
%else
  /sbin/chkconfig --add salt-minion
%endif
%endif

%postun minion
%if %{with systemd}
%service_del_postun salt-minion.service
%else
%if 0%{?suse_version}
%insserv_cleanup
%restart_on_update salt-minion
%else
  if [ "$1" -ge "1" ] ; then
      /sbin/service salt-minion condrestart >/dev/null 2>&1 || :
  fi
%endif
%endif

%preun api
%if %{with systemd}
%service_del_preun salt-api.service
%else
%stop_on_removal
%endif

%pre api
%if %{with systemd}
%service_add_pre salt-api.service
%endif

%post api
%if %{with systemd}
%service_add_post salt-api.service
%else
%if 0%{?suse_version}
%fillup_and_insserv
%endif
%endif

%postun api
%if %{with systemd}
%service_del_postun salt-api.service
%else
%if 0%{?suse_version}
%insserv_cleanup
%restart_on_update
%endif
%endif

%files api
%defattr(-,root,root)
%{_bindir}/salt-api
%{_sbindir}/rcsalt-api
%if %{with systemd}
%{_unitdir}/salt-api.service
%else
%{_initddir}/salt-api
%endif
%{_mandir}/man1/salt-api.1.*

%files cloud
%defattr(-,root,root)
%{_bindir}/salt-cloud
%dir               %attr(0750, root, salt) %{_sysconfdir}/salt/cloud.maps.d
%dir               %attr(0750, root, salt) %{_sysconfdir}/salt/cloud.profiles.d
%dir               %attr(0750, root, salt) %{_sysconfdir}/salt/cloud.providers.d
%config(noreplace) %attr(0640, root, salt) %{_sysconfdir}/salt/cloud
%config(noreplace) %attr(0640, root, salt) %{_sysconfdir}/salt/cloud.profiles
%config(noreplace) %attr(0640, root, salt) %{_sysconfdir}/salt/cloud.providers
%{_mandir}/man1/salt-cloud.1.*

%files ssh
%defattr(-,root,root)
%{_bindir}/salt-ssh
%{_mandir}/man1/salt-ssh.1.gz

%files syndic
%defattr(-,root,root)
%{_bindir}/salt-syndic
%{_mandir}/man1/salt-syndic.1.gz
%{_sbindir}/rcsalt-syndic
%if %{with systemd}
%{_unitdir}/salt-syndic.service
%else
%{_initddir}/salt-syndic
%endif

%files minion
%defattr(-,root,root)
%{_bindir}/salt-minion
%{_mandir}/man1/salt-minion.1.gz
%config(noreplace) %attr(0640, root, root) %{_sysconfdir}/salt/minion
%config(noreplace) %attr(0640, root, root) %ghost %{_sysconfdir}/salt/minion_id
%dir               %attr(0750, root, root) %{_sysconfdir}/salt/minion.d/
%dir               %attr(0750, root, root) %{_sysconfdir}/salt/pki/minion/
%dir               %attr(0750, root, root) %{_localstatedir}/cache/salt/minion/
%{_sbindir}/rcsalt-minion
%if %{with systemd}
%{_unitdir}/salt-minion.service
%else
%config(noreplace) %{_initddir}/salt-minion
%endif

%files proxy
%defattr(-,root,root)
%{_bindir}/salt-proxy
%{_mandir}/man1/salt-proxy.1.gz

%files master
%defattr(-,root,root)
%{_bindir}/salt
%{_bindir}/salt-master
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-run
%{_mandir}/man1/salt-master.1.gz
%{_mandir}/man1/salt-cp.1.gz
%{_mandir}/man1/salt-key.1.gz
%{_mandir}/man1/salt-run.1.gz
%{_mandir}/man7/salt.7.gz
%config(noreplace) %{_sysconfdir}/sysconfig/SuSEfirewall2.d/services/salt
%{_sbindir}/rcsalt-master
%if %{with systemd}
%{_unitdir}/salt-master.service
%else
%config(noreplace) %{_initddir}/salt-master
%endif
#
%config(noreplace) %attr(0640, root, salt) %{_sysconfdir}/salt/master
%config(noreplace) %attr(0640, root, salt) %{_sysconfdir}/salt/roster
%dir               %attr(0755, root, salt) %{_sysconfdir}/salt/master.d/
%dir               %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/
%dir               %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions/
%dir               %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_autosign/
%dir               %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_denied/
%dir               %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_pre/
%dir               %attr(0750, salt, salt) %{_sysconfdir}/salt/pki/master/minions_rejected/
%dir               %attr(0755, root, salt) /srv/salt
%dir               %attr(0755, root, salt) /srv/pillar
%dir               %attr(0750, salt, salt) %{_localstatedir}/cache/salt/master/
%dir               %attr(0750, salt, salt) %{_localstatedir}/cache/salt/master/jobs/
%dir               %attr(0750, salt, salt) %{_localstatedir}/cache/salt/master/proc/
%dir               %attr(0750, salt, salt) %{_localstatedir}/cache/salt/master/queues/
%dir               %attr(0750, salt, salt) %{_localstatedir}/cache/salt/master/roots/
%dir               %attr(0750, salt, salt) %{_localstatedir}/cache/salt/master/syndics/
%dir               %attr(0750, salt, salt) %{_localstatedir}/cache/salt/master/tokens/

%files raet
%defattr(-,root,root,-)
%config(noreplace) %attr(0640, root, salt) %{_sysconfdir}/salt/master.d/transport-raet.conf
%config(noreplace) %attr(0640, root, root) %{_sysconfdir}/salt/minion.d/transport-raet.conf

%files
%defattr(-,root,root,-)
%{_bindir}/spm
%{_bindir}/salt-call
%{_mandir}/man1/salt-call.1.gz
%config(noreplace) %{_sysconfdir}/logrotate.d/salt
%{python_sitelib}/*
%exclude %{python_sitelib}/salt/cloud/deploy/*.sh
%attr(755,root,root)%{python_sitelib}/salt/cloud/deploy/*.sh
%doc LICENSE AUTHORS README.rst HACKING.rst README.SUSE
#
%dir %attr(0750, root, salt) %{_sysconfdir}/salt
%dir %attr(0750, root, salt) %{_sysconfdir}/salt/pki
%dir %attr(0750, salt, salt) %{_localstatedir}/log/salt
%dir %attr(0750, root, salt) %{_localstatedir}/cache/salt
%dir %attr(0750, root, salt) /srv/spm
%if %{with systemd}
/usr/lib/tmpfiles.d/salt.conf
%endif

%if %{with docs}
%files doc
%defattr(-,root,root)
%doc doc/_build/html
%endif

%if %{with bash_completion}
%files bash-completion
%defattr(-,root,root)
%dir %{_sysconfdir}/bash_completion.d/
%config %{_sysconfdir}/bash_completion.d/%{name}
%endif

%if %{with zsh_completion}
%files zsh-completion
%defattr(-,root,root)
%dir %{_sysconfdir}/zsh_completion.d/
%config %{_sysconfdir}/zsh_completion.d/%{name}
%endif

%if %{with fish_completion}
%files fish-completion
%defattr(-,root,root)
%{fish_completions_dir}/salt*
%dir %{fish_completions_dir}
%dir %{fish_dir}
%endif

%changelog
