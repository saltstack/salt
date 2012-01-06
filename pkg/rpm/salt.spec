%if ! (0%{?rhel} >= 6 || 0%{?fedora} > 12)
%global with_python26 1
%define pybasever 2.6
%define __python_ver 26
%define __python %{_bindir}/python%{?pybasever}
%endif

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

%{!?%_unitdir: %global _unitdir /lib/systemd/system}

Name: salt
Version: 0.9.4
Release: 3%{?dist}
Summary: A parallel remote execution system

Group:   System/Utilities
License: ASL 2.0
URL:     https://github.com/thatch45/salt
# http://saltstack.org/
Source0: https://github.com/downloads/saltstack/%{name}/%{name}-%{version}.tar.gz
Source1: %{name}-master
Source2: %{name}-syndic
Source3: %{name}-minion
Source4: %{name}-master.service
Source5: %{name}-syndic.service
Source6: %{name}-minion.service
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch

Requires: python(abi) >= 2.6

%if 0%{?with_python26}
BuildRequires: python26-zmq
BuildRequires: python26-crypto
BuildRequires: python26-devel
BuildRequires: python26-PyYAML
BuildRequires: python26-m2crypto

Requires: python26-crypto
Requires: python26-zmq
Requires: python26-jinja2
Requires: python26-PyYAML
Requires: python26-m2crypto

%else

BuildRequires: python-zmq
BuildRequires: python-crypto
BuildRequires: python-devel
BuildRequires: PyYAML
BuildRequires: m2crypto

Requires: python-crypto
Requires: python-zmq
Requires: python-jinja2
Requires: PyYAML
Requires: m2crypto

%endif


%description
Salt is a distributed remote execution system used to execute commands and 
query data. It was developed in order to bring the best solutions found in 
the world of remote execution together and make them better, faster and more 
malleable. Salt accomplishes this via its ability to handle larger loads of 
information, and not just dozens, but hundreds or even thousands of individual 
servers, handle them quickly and through a simple and manageable interface.

%package -n salt-master
Group:   System/Utilities
Summary: Management component for salt, a parallel remote execution system 
Requires: salt >= 0.9.4-3

%description -n salt-master 
Salt is a distributed remote execution system used to execute commands and 
query data. It was developed in order to bring the best solutions found in 
the world of remote execution together and make them better, faster and more 
malleable. Salt accomplishes this via its ability to handle larger loads of 
information, and not just dozens, but hundreds or even thousands of individual 
servers, handle them quickly and through a simple and manageable interface.
Summary: A parallel remote execution system

%package -n salt-minion
Group:   System/Utilities
Summary: Client tools for salt, a parallel remote execution system 
Requires: salt >= 0.9.4-3

%description -n salt-minion
Salt is a distributed remote execution system used to execute commands and 
query data. It was developed in order to bring the best solutions found in 
the world of remote execution together and make them better, faster and more 
malleable. Salt accomplishes this via its ability to handle larger loads of 
information, and not just dozens, but hundreds or even thousands of individual 
servers, handle them quickly and through a simple and manageable interface.
Summary: Client utilities for Salt, a parallel remote execution system

%prep
%setup -q

%build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --root $RPM_BUILD_ROOT

%if (0%{?rhel} || 0%{?fedora} < 15)
mkdir -p $RPM_BUILD_ROOT%{_initrddir}
install -p -m 0775 %{SOURCE1} $RPM_BUILD_ROOT%{_initrddir}/
install -p -m 0775 %{SOURCE2} $RPM_BUILD_ROOT%{_initrddir}/
install -p -m 0775 %{SOURCE3} $RPM_BUILD_ROOT%{_initrddir}/
%else
mkdir -p $RPM_BUILD_ROOT%{_unitdir}
install -p -m 0775 %{SOURCE4} $RPM_BUILD_ROOT%{_unitdir}/
install -p -m 0775 %{SOURCE5} $RPM_BUILD_ROOT%{_unitdir}/
install -p -m 0775 %{SOURCE6} $RPM_BUILD_ROOT%{_unitdir}/
%endif
 
%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc %{_defaultdocdir}/salt*
%{python_sitelib}/*
%doc %{_mandir}/man7/salt.7.*
#{_initrddir}/*

%files -n salt-minion
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-call.1.*
%doc %{_mandir}/man1/salt-minion.1.*
%{_bindir}/salt-minion
%{_bindir}/salt-call
%if (0%{?rhel} || 0%{?fedora} < 15)
%{_initrddir}/salt-minion
%else
%{_unitdir}/salt-minion.service
%endif
%config(noreplace) /etc/salt/minion

%files -n salt-master
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-master.1.*
%doc %{_mandir}/man1/salt.1.*
%doc %{_mandir}/man1/salt-cp.1.*
%doc %{_mandir}/man1/salt-key.1.*
%doc %{_mandir}/man1/salt-run.1.*
%doc %{_mandir}/man1/salt-syndic.1.*
%{_bindir}/salt
%{_bindir}/salt-master
%{_bindir}/salt-syndic
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-run
%if (0%{?rhel} || 0%{?fedora} < 15)
%{_initrddir}/salt-master
%{_initrddir}/salt-syndic
%else
%{_unitdir}/salt-master.service
%{_unitdir}/salt-syndic.service
%endif
%config(noreplace) /etc/salt/master

%changelog
* Thu Jan 5 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-3
- Updating for systemd on Fedora 15+

* Thu Dec 1 2011 Clint Savage <herlo1@gmail.com> - 0.9.4-2
- Removing requirement for Cython. Optional only for salt-minion

* Thu Nov 30 2011 Clint Savage <herlo1@gmail.com> - 0.9.4-1
- New upstream release with new features and bugfixes

* Thu Nov 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.3-1
- New upstream release with new features and bugfixes

* Sat Sep 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.2-1
- Bugfix release from upstream to fix python2.6 issues

* Fri Sep 09 2011 Clint Savage <herlo1@gmail.com> - 0.9.1-1
- Initial packages
