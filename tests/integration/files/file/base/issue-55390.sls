#!jinja|py

{% from "issue-55390-map.jinja" import defaults with context %}

def run():
    pillar = __salt__['pillar']

    return {'issue-55390': {
        'file.managed': [
            {'name': pillar.get('file_path')},
            {'source': pillar.get('source_path')},
            {'context': {
                 "output": "{{ defaults['outputtext'] }}",
            }},
            {'template': 'py'},
        ]
    }}
