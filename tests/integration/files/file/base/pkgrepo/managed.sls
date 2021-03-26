{% if grains['os'] == 'CentOS' %}

# START CentOS pkgrepo tests
{% if grains['osmajorrelease'] == 8 %}
epel-salttest:
  pkgrepo.managed:
    - humanname: Extra Packages for Enterprise Linux 8 - $basearch (salttest)
    - comments:
      - '#baseurl=http://download.fedoraproject.org/pub/epel/8/$basearch'
    - mirrorlist: https://mirrors.fedoraproject.org/metalink?repo=epel-8&arch=$basearch
    - failovermethod: priority
    - enabled: 1
    - gpgcheck: 1
    - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8-salttest
    - require:
      - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8-salttest

/etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8-salttest:
  file.managed:
    - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-8-salttest
    - user: root
    - group: root
    - mode: 644
{% elif grains['osmajorrelease'] == 7 %}
epel-salttest:
  pkgrepo.managed:
    - humanname: Extra Packages for Enterprise Linux 7 - $basearch (salttest)
    - comments:
      - '#baseurl=http://download.fedoraproject.org/pub/epel/7/$basearch'
    - mirrorlist: https://mirrors.fedoraproject.org/metalink?repo=epel-7&arch=$basearch
    - failovermethod: priority
    - enabled: 1
    - gpgcheck: 1
    - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7-salttest
    - require:
      - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7-salttest

/etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7-salttest:
  file.managed:
    - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-7-salttest
    - user: root
    - group: root
    - mode: 644
{% elif grains['osrelease'].startswith('6.') %}
epel-salttest:
  pkgrepo.managed:
    - humanname: Extra Packages for Enterprise Linux 6 - $basearch (salttest)
    - comments:
      - '#baseurl=http://download.fedoraproject.org/pub/epel/6/$basearch'
    - mirrorlist: https://mirrors.fedoraproject.org/metalink?repo=epel-6&arch=$basearch
    - failovermethod: priority
    - enabled: 1
    - gpgcheck: 1
    - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-6-salttest
    - require:
      - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-6-salttest

/etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-6-salttest:
  file.managed:
    - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-6-salttest
    - user: root
    - group: root
    - mode: 644
{% elif grains['osrelease'].startswith('5.') %}
epel-salttest:
  pkgrepo.managed:
    - humanname: Extra Packages for Enterprise Linux 5 - $basearch (salttest)
    - comments:
      - '#baseurl=http://download.fedoraproject.org/pub/epel/5/$basearch'
    - mirrorlist: http://mirrors.fedoraproject.org/mirrorlist?repo=epel-5&arch=$basearch
    - failovermethod: priority
    - enabled: 1
    - gpgcheck: 1
    - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-5-salttest
    - require:
      - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-5-salttest

/etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-5-salttest:
  file.managed:
    - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-5-salttest
    - user: root
    - group: root
    - mode: 644
{% endif %}
# END CentOS pkgrepo tests

{% elif grains['os'] == 'Ubuntu' %}

# START Ubuntu pkgrepo tests
{% set codename = grains['oscodename'] %}
{% set ubuntu_repos = [] %}
{% set beta = grains['oscodename'] in ['xenial', 'bionic', 'eoan', 'focal', 'groovy'] %}
{% set backports = grains['oscodename'] in ['xenial', 'bionic', 'eoan', 'focal'] %}

{%- if beta %}{%- do ubuntu_repos.append('firefox-beta') %}
firefox-beta:
  pkgrepo.managed:
    - name: deb http://ppa.launchpad.net/mozillateam/firefox-next/ubuntu {{ codename }} main
    - dist: {{ codename }}
    - file: /etc/apt/sources.list.d/firefox-beta.list
    - keyid: CE49EC21
    - keyserver: keyserver.ubuntu.com
{%- endif %}

{%- if backports %}{%- do ubuntu_repos.append('kubuntu-ppa') %}
kubuntu-ppa:
  pkgrepo.managed:
    - ppa: kubuntu-ppa/backports
{%- endif %}

pkgrepo-deps:
  pkg.installed:
    - pkgs:
      - python-apt
      - software-properties-common
{%- for repo in ubuntu_repos -%}
{% if loop.first %}
    - require_in:{%- endif %}
      - pkgrepo: {{ repo }}
{%- endfor %}
# END Ubuntu pkgrepo tests

{% else %}

# No matching OS grain for pkgrepo management, just run something that will
# return a True result
date:
  cmd:
    - run

{% endif %}
