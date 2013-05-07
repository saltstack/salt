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
Version:        0.8.1
Release:        1%{?dist}
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
BuildRequires:	salt
BuildRequires:	salt-master

Requires:       salt
Requires:       salt-master
Recommends:     python-CherryPy
%if 0%{?suse_version} >= 1210
BuildRequires:  systemd
%endif
Requires(pre): %fillup_prereq
Requires(pre): %insserv_prereq

%description
salt-api is a modular interface on top of Salt that can provide a variety of entry points into a running Salt system.

%prep
%setup -q

%build
python setup.py build

%install
python setup.py install --prefix=%{_prefix} --root=%{buildroot}
mkdir -p %{buildroot}%{_sysconfdir}/init.d
mkdir -p %{buildroot}%{_localstatedir}/log/salt
%if 0%{?suse_version} >= 1210
mkdir -p %{buildroot}/lib/systemd/system
%endif
mkdir -p %{buildroot}/%{_sbindir}
%if 0%{?sles_version} == 11
install -m0755 %{SOURCE1} %{buildroot}%{_sysconfdir}/init.d/salt-api
%else
install -m0755 %{SOURCE1} %{buildroot}%{_initddir}/salt-api
%endif
ln -sf /etc/init.d/salt-api %{buildroot}%{_sbindir}/rcsalt-api

%if 0%{?suse_version} >= 1210
install -m 644  %{SOURCE2} %{buildroot}/lib/systemd/system/salt-api.service
%endif

%preun
%stop_on_removal

%post
%fillup_and_insserv

%postun
%restart_on_update
%insserv_cleanup


%files
%defattr(-,root,root)
%{_sysconfdir}/init.d/salt-api
%{_sbindir}/rcsalt-api
%doc %{_mandir}/man1/salt-api.1.*
%doc %{_mandir}/man7/salt-api.7.*
%{_bindir}/salt-api
%doc LICENSE
%{python_sitelib}/*
%if 0%{?suse_version} >= 1210
/lib/systemd/system/salt-api.service
%endif

%changelog
