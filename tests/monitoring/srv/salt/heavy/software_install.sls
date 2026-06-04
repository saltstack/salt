{% set pkgs = ['ed', 'bc', 'jq', 'tree', 'zip', 'unzip', 'less'] %}

install_pkgs:
  pkg.installed:
    - pkgs: {{ pkgs }}
