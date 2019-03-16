#
# spec file for package salt-api
#
# Copyright (c) 2012 SUSE LINUX Products GmbH, Nuernberg, Germany.
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

Name:           salt-api
Version:        0.8.3
Release:        0
License:        Apache-2.0
Summary:        The api for Salt a parallel remote execution system
Url:            http://saltstack.org/
Group:          System/Monitoring
Source0:        http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz
Source1:		salt-api
Source2:		salt-api.service
BuildRoot:      %{_tmppath}/%{name}-%{version}-build

%if 0%{?suse_version} && 0%{?suse_version} <= 1110
%{!?python_sitelib: %global python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%else
BuildArch:      noarch
%endif

BuildRequires:  fdupes
BuildRequires:  python-devel
BuildRequires:	salt >= 0.15.9
BuildRequires:	salt-master

Requires:       salt
Requires:       salt-master
Recommends:     python-CherryPy
%if 0%{?suse_version} >= 1210
BuildRequires:	systemd
%{?systemd_requires}
%else
Requires(pre): %insserv_prereq
Requires(pre): %fillup_prereq
%endif

%description
salt-api is a modular interface on top of Salt that can provide a variety of entry points into a running Salt system.

%prep
%setup -q

%build
python setup.py build

%install
python setup.py install --prefix=%{_prefix} --root=%{buildroot}
%fdupes %{buildroot}%{_prefix}
#
##missing directories
%if 0%{?suse_version} < 1210
mkdir -p %{buildroot}%{_sysconfdir}/init.d
mkdir -p %{buildroot}/%{_sbindir}
%endif
mkdir -p %{buildroot}%{_localstatedir}/log/salt
#
##init scripts
%if 0%{?suse_version} < 1210
install -Dpm 0755 %{SOURCE1} %{buildroot}%{_sysconfdir}/init.d/salt-api
ln -sf /etc/init.d/salt-api %{buildroot}%{_sbindir}/rcsalt-api
%else
install -Dpm 644  %{SOURCE2} %{buildroot}%_unitdir/salt-api.service
%endif

%preun
%if 0%{?_unitdir:1}
%service_del_preun salt-api.service
%else
%stop_on_removal
%endif

%post
%if 0%{?_unitdir:1}
%service_add_post salt-api.service
%else
%fillup_and_insserv
%endif

%postun
%if 0%{?_unitdir:1}
%service_del_postun salt-api.service
%else
%insserv_cleanup
%restart_on_update
%endif


%files
%defattr(-,root,root)
%doc LICENSE
%if 0%{?_unitdir:1}
%_unitdir
%else
%{_sysconfdir}/init.d/salt-api
%{_sbindir}/rcsalt-api
%endif
%{_mandir}/man1/salt-api.1.*
%{_mandir}/man7/salt-api.7.*
%{_bindir}/salt-api
%{python_sitelib}/*


%changelog
