{% set minion = '*' %}
{% set mine = salt.saltutil.runner('mine.get',
        tgt=minion,
        fun='test.ping') %}

{% if mine %}
test.ping:
  salt.function:
    - tgt: "{{ minion }}"
{% endif %}
