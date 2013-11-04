#
# spec file for package salt-cloud
#
# Copyright (c) 2013 SUSE LINUX Products GmbH, Nuernberg, Germany.
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


Name:           salt-cloud
Version:        0.8.9
Release:        0
Summary:        Salt Cloud is a generic cloud provisioning tool
License:        Apache-2.0
Group:          System/Monitoring
Url:            http://saltstack.org
Source0:        http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz
BuildRequires:  fdupes
BuildRequires:  python-PyYAML
BuildRequires:  python-apache-libcloud >= 0.12.1
BuildRequires:  python-setuptools
BuildRequires:  salt >= 0.13.0
Requires:       python-PyYAML
Requires:       python-apache-libcloud
Requires:       salt >= 0.13.0
Recommends:     sshpass
Recommends:     python-botocore
Recommends:     python-netaddr
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
%if 0%{?suse_version} && 0%{?suse_version} > 1110
BuildArch:      noarch
%endif

%description
public cloud VM management system
provision virtual machines on various public clouds via a cleanly
controlled profile and mapping system.

%prep
%setup -q

%build
python setup.py build

%install
python setup.py install --prefix=%{_prefix} -O1 --root=%{buildroot}
%fdupes %{buildroot}%{_prefix}

%files
%defattr(-,root,root)
%doc LICENSE
%{_bindir}/salt-cloud
%{_mandir}/man1/salt-cloud.1.*
%{_mandir}/man7/salt-cloud.7.*
%{python_sitelib}/*
%attr(755,root,root)%{python_sitelib}/saltcloud/deploy/*.sh

%changelog
