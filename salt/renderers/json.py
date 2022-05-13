"""
JSON Renderer for Salt
"""


import salt.utils.json

json = salt.utils.json.import_json()


def render(json_data, saltenv="base", sls="", **kws):
    """
    Accepts JSON as a string or as a file object and runs it through the JSON
    parser.

    :rtype: A Python data structure
    """
    if not isinstance(json_data, str):
        json_data = json_data.read()

    if json_data.startswith("#!"):
        json_data = json_data[(json_data.find("\n") + 1) :]
    if not json_data.strip():
        return {}
    return json.loads(json_data)
