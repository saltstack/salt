%if ! (0%{?rhel} >= 6 || 0%{?fedora} > 12)
%global with_python26 1
%define pybasever 2.6
%define __python_ver 26
%define __python %{_bindir}/python%{?pybasever}
%endif

%global namespace saltcloud
%global eggspace salt_cloud

%global include_tests 0

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: salt-cloud
Version: 0.8.5
Release: 1%{?dist}
Summary: Generic cloud provisioning tool

Group:   Applications/Internet
License: ASL 2.0
URL:     http://github.com/saltstack/salt-cloud
Source0: http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch

%if 0%{?with_python26}

BuildRequires: salt >= 0.12.1
BuildRequires: python26-PyYAML

Requires: salt >= 0.12.1
Requires: python26-PyYAML

%else

%if ((0%{?rhel} >= 6 || 0%{?fedora} > 12) && 0%{?include_tests})
BuildRequires: python-unittest2
# this BR causes windows tests to happen
# clearly, that's not desired
# https://github.com/saltstack/salt/issues/3749
#BuildRequires: python-mock
BuildRequires: git
%endif

BuildRequires: salt
BuildRequires: PyYAML

Requires: salt
Requires: PyYAML

%endif

%description
Salt cloud allows for cloud based minions to be managed via virtual machine maps and profiles. This means that individual cloud VMs can be created, or large groups of cloud VMs can be created at once or managed. Virtual machines created with Salt cloud install salt on the target virtual machine and assign it to the specified master. While Salt Cloud has been made to work with Salt, it is also a generic cloud management platform and can be used to manage non Salt centric clouds.

%prep
%setup -q

%build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --root $RPM_BUILD_ROOT

%if ((0%{?rhel} >= 6 || 0%{?fedora} > 12) && 0%{?include_tests})
%check
%{__python} setup.py test --runtests-opts=-u
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/%{namespace}/*
%{python_sitelib}/%{eggspace}-%{version}-py?.?.egg-info
%doc %{_mandir}/man1/%{name}.1.*
%doc %{_mandir}/man7/%{name}.7.*
%{_bindir}/salt-cloud

#config(noreplace) %{_sysconfdir}/salt/master

%changelog
* Wed Feb 20 2013 Clint Savage <herlo1@gmail.com> - 0.8.5-1
- Initial rpm package
