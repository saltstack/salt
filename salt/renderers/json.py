from __future__ import absolute_import
import json

def render(json_data, env='', sls='', **kws):
    if not isinstance(json_data, basestring):
        json_data = json_data.read()

    if json_data.startswith('#!'):
        json_data = json_data[json_data.find('\n')+1:]
    if not json_data.strip():
        return {}
    return json.loads(json_data)

