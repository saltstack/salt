{% from "states/defaults.yaml" import rawmap with context %}
{%- set config = salt['grains.filter_by'](rawmap, grain='os_family', merge=salt['config.get']('wordpress:lookup')) %}

download wordpress archive:
  pkg.latest:
    - name: tar

  archive.extracted:
    - name: {{config.dir}}
    - source_hash: a99115b3b6d6d7a1eb6c5617d4e8e704ed50f450
    - source: https://wordpress.org/wordpress-4.8.2.tar.gz
    - options: --strip-components=1
    - enforce_toplevel: false
  grains.present:
    - name: wordpressdir
    - value: {{config.dir}}

configure wordpress:
  file.managed:
    - name: {{config.dir}}/wp-config.php
    - source: salt://states/wp-config.php.j2
    - user: {{config.user}}
    - group: {{config.group}}
    - template: jinja

{%- if grains.os_family in ('Suse',) %}
suse setup:
  pkg.latest:
    - pkgs:
      - php5-phar
      - apache2-mod_php5
    - listen_in:
      - service: apache
  file.managed:
    - name: /etc/apache2/conf.d/mod_php.conf
    - contents: |
        LoadModule php5_module /usr/lib64/apache2/mod_php5.so
    - listen_in:
      - service: apache
{%- elif grains.os_family in ('Debian',) %}
remove default index.html:
  file.absent:
    - name: /var/www/html/index.html
{%- endif %}

get wp manager script:

  file.managed:
    - name: /usr/local/bin/wp
    - user: root
    - group: root
    - mode: 755
    - source: salt://states/wp-cli.phar
    - source_hash: a647367c1e6c34c7357e380515d59e15fbc86fa2
    - reload_modules: True

do install:
  wordpress.installed:
    - path: {{config.dir}}
    - user: {{config.user}}
    - admin_user: {{config.admin_user}}
    - admin_password: "{{config.admin_password}}"
    - admin_email: "{{config.admin_email}}"
    - title: "{{config.title}}"
    - url: "{{config.url}}"
    - retry:
        attempts: 5

  file.directory:
    - name: {{config.dir}}
    - user: {{config.user}}
    - group: {{config.group}}
    - file_mode: 644
    - dir_mode: 2775
    - recurse:
      - user
      - group
      - mode
