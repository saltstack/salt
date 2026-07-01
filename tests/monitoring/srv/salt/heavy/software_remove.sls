{% set pkgs = ['ed', 'bc', 'jq', 'tree', 'zip', 'unzip', 'less'] %}

remove_pkgs:
  pkg.removed:
    - pkgs: {{ pkgs }}
