# pylint: disable=W1401
'''
This module renders highstate configuration into a more human readable format.

How it works:

`highstate or lowstate` data is parsed with a `processor` this defaults to `highstate_doc.processor_markdown`.
The processed data is passed to a `jinja` template that builds up the document content.


configuration: Pillar

.. code-block:: none

    # the following defaults can be overridden
    highstate_doc.config:

        # list of regex of state names to ignore in `highstate_doc.process_lowstates`
        filter_id_regex:
            - '.*!doc_skip$'

        # list of regex of state functions to ignore in `highstate_doc.process_lowstates`
        filter_state_function_regex:
            - 'file.accumulated'

        # dict of regex to replace text after `highstate_doc.render`. (remove passwords)
        text_replace_regex:
            'password:.*^': '[PASSWORD]'

        # limit size of files that can be included in doc (10000 bytes)
        max_render_file_size: 10000

        # advanced option to set a custom lowstate processor
        processor: highstate_doc.processor_markdown


State example

.. code-block:: yaml

    {{sls}} note:
        highstate_doc.note:
            - name: example
            - order: 0
            - contents: |
                example `highstate_doc.note`
                ------------------
                This state does not do anything to the system! It is only used by a `processor`
                you can use `requisites` and `order` to move your docs around the rendered file.

    {{sls}} a file we don't want in the doc !doc_skip:
        file.managed:
            - name: /root/passwords
            - contents: 'password: sadefgq34y45h56q'
            # also could use `highstate_doc.config: text_replace_regex` to replace
            # password string. `password:.*^': '[PASSWORD]`


To create the help document build a State that uses `highstate_doc.render`.
For performance it's advised to not included this state in your `top.sls` file.

.. code-block:: yaml

    # example `salt://makereadme.sls`
    make helpfile:
        file.managed:
            - name: /root/README.md
            - contents: {{salt.highstate_doc.render()|json}}
            - show_diff: {{opts['test']}}
            - mode: '0640'
            - order: last

Run our `makereadme.sls` state to create `/root/README.md`.

.. code-block:: bash

    # first ensure `highstate` return without errors or changes
    salt-call state.highstate
    salt-call state.apply makereadme
    # or if you don't want the extra `make helpfile` state
    salt-call --out=newline_values_only salt.highstate_doc.render > /root/README.md ; chmod 0600 /root/README.md


Creating a document collection
------------------------------

From the master we can run the following script to
creates a collection of all your minion documents.

.. code-block:: bash

    salt '*' state.apply makereadme

.. code-block:: python

    #!/bin/python
    import os
    import salt.client
    s = salt.client.LocalClient()
    # NOTE: because of issues with `cp.push` use `highstate_doc.read_file`
    o = s.cmd('*', 'highstate_doc.read_file', ['/root/README.md'])
    for m in o:
        d = o.get(m)
        if d and not d.endswith('is not available.'):
            # mkdir m
            #directory = os.path.dirname(file_path)
            if not os.path.exists(m):
                os.makedirs(m)
            with open(m + '/README.md','wb') as f:
                f.write(d)
            print('ADDED: ' + m + '/README.md')


Once the master has a collection of all the README files.
You can use pandoc to create HTML versions of the markdown.

.. code-block:: bash

    # process all the readme.md files to readme.html
    if which pandoc; then echo "Found pandoc"; else echo "** Missing pandoc"; exit 1; fi
    if which gs; then echo "Found gs"; else echo "** Missing gs(ghostscript)"; exit 1; fi
    readme_files=$(find $dest -type f -path "*/README.md" -print)
    for f in $readme_files ; do
        ff=${f#$dest/}
        minion=${ff%%/*}
        echo "process: $dest/${minion}/$(basename $f)"
        cat $dest/${minion}/$(basename $f) | \
            pandoc --standalone --from markdown_github --to html \
            --include-in-header $dest/style.html \
            > $dest/${minion}/$(basename $f).html
    done

It is also nice to put the help files in source control.

    # git init
    git add -A
    git commit -am 'updated docs'
    git push -f


Other hints
-----------

If you wish to customize the document format:

.. code-block:: none

    # you could also create a new `processor` for perhaps reStructuredText
    # highstate_doc.config:
    #     processor: doc_custom.processor_rst

    # example `salt://makereadme.jinja`
    """
    {{opts['id']}}
    ==========================================

    {# lowstates is set from highstate_doc.render() #}
    {# if lowstates is missing use salt.highstate_doc.process_lowstates() #}
    {% for s in lowstates %}
    {{s.id}}
    -----------------------------------------------------------------
    {{s.function}}

    {{s.markdown.requisite}}
    {{s.markdown.details}}

    {%- endfor %}
    """

    # example `salt://makereadme.sls`
    {% import_text "makereadme.jinja" as makereadme %}
    {{sls}} or:
        file.managed:
            - name: /root/README_other.md
            - contents: {{salt.highstate_doc.render(jinja_template_text=makereadme)|json}}
            - mode: '0640'


Some `replace_text_regex` values that might be helpful::

    CERTS
    -----

    ``'-----BEGIN RSA PRIVATE KEY-----[\\r\\n\\t\\f\\S]{0,2200}': 'XXXXXXX'``
    ``'-----BEGIN CERTIFICATE-----[\\r\\n\\t\\f\\S]{0,2200}': 'XXXXXXX'``
    ``'-----BEGIN DH PARAMETERS-----[\\r\\n\\t\\f\\S]{0,2200}': 'XXXXXXX'``
    ``'-----BEGIN PRIVATE KEY-----[\\r\\n\\t\\f\\S]{0,2200}': 'XXXXXXX'``
    ``'-----BEGIN OPENSSH PRIVATE KEY-----[\\r\\n\\t\\f\\S]{0,2200}': 'XXXXXXX'``
    ``'ssh-rsa .* ': 'ssh-rsa XXXXXXX '``
    ``'ssh-dss .* ': 'ssh-dss XXXXXXX '``

    DB
    --

    ``'DB_PASS.*': 'DB_PASS = XXXXXXX'``
    ``'5432:*:*:.*': '5432:*:XXXXXXX'``
    ``"'PASSWORD': .*": "'PASSWORD': 'XXXXXXX',"``
    ``" PASSWORD '.*'": " PASSWORD 'XXXXXXX'"``
    ``'PGPASSWORD=.* ': 'PGPASSWORD=XXXXXXX'``
    ``"_replication password '.*'":  "_replication password 'XXXXXXX'"``

    OTHER
    -----

    ``'EMAIL_HOST_PASSWORD =.*': 'EMAIL_HOST_PASSWORD =XXXXXXX'``
    ``"net ads join -U '.*@MFCFADS.MATH.EXAMPLE.CA.* ": "net ads join -U '.*@MFCFADS.MATH.EXAMPLE.CA%XXXXXXX "``
    ``"net ads join -U '.*@NEXUS.EXAMPLE.CA.* ": "net ads join -U '.*@NEXUS.EXAMPLE.CA%XXXXXXX "``
    ``'install-uptrack .* --autoinstall': 'install-uptrack XXXXXXX --autoinstall'``
    ``'accesskey = .*': 'accesskey = XXXXXXX'``
    ``'auth_pass .*': 'auth_pass XXXXXXX'``
    ``'PSK "0x.*': 'PSK "0xXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'``
    ``'SECRET_KEY.*': 'SECRET_KEY = XXXXXXX'``
    ``"password=.*": "password=XXXXXXX"``
    ``'<password>.*</password>': '<password>XXXXXXX</password>'``
    ``'<salt>.*</salt>': '<salt>XXXXXXX</salt>'``
    ``'application.secret = ".*"': 'application.secret = "XXXXXXX"'``
    ``'url = "postgres://.*"': 'url = "postgres://XXXXXXX"'``
    ``'PASS_.*_PASS': 'PASS_XXXXXXX_PASS'``

    HTACCESS
    --------

    ``':{PLAIN}.*': ':{PLAIN}XXXXXXX'``

'''


import logging
import re

import salt.utils.files
import salt.utils.stringutils
import salt.utils.templates as tpl
import salt.utils.yaml

__virtualname__ = "highstate_doc"

log = logging.getLogger(__name__)


markdown_basic_jinja_template_txt = """
{% for s in lowstates %}
`{{s.id_full}}`
-----------------------------------------------------------------
 * state: {{s.state_function}}
 * name: `{{s.name}}`

{{s.markdown.requisites}}
{{s.markdown.details}}

{%- endfor %}
"""

markdown_default_jinja_template_txt = (
    """
Configuration Managment
===============================================================================

```
####################################################
fqdn: {{grains.get('fqdn')}}
os: {{grains.get('os')}}
osfinger: {{grains.get('osfinger')}}
mem_total: {{grains.get('mem_total')}}MB
num_cpus: {{grains.get('num_cpus')}}
ipv4: {{grains.get('ipv4')}}
master: {{opts.get('master')}}
####################################################
```

This system is fully or partly managed using Salt.

The following sections are a rendered view of what the configuration management system
controlled on this system. Each item is handled in order from top to bottom unless some
requisites like `require` force other ordering.

"""
    + markdown_basic_jinja_template_txt
)


markdown_advanced_jinja_template_txt = (
    markdown_default_jinja_template_txt
    + r"""

{% if vars.get('doc_other', True) -%}
Other information
=====================================================================================

```

salt grain: ip_interfaces
-----------------------------------------------------------------
{{grains['ip_interfaces']|dictsort}}


salt grain: hwaddr_interfaces
-----------------------------------------------------------------
{{grains['hwaddr_interfaces']|dictsort}}

{% if not grains['os'] == 'Windows' %}

{% if salt['cmd.has_exec']('ip') -%}
# ip address show
-----------------------------------------------------------------
{{salt['cmd.run']('ip address show | sed "/valid_lft/d"')}}


# ip route list table all
-----------------------------------------------------------------
{{salt['cmd.run']('ip route list table all')}}
{% endif %}

{% if salt['cmd.has_exec']('iptables') %}
{%- if salt['cmd.has_exec']('iptables-save') -%}
# iptables-save
-----------------------------------------------------------------
{{salt['cmd.run']("iptables --list > /dev/null; iptables-save | \grep -v -F '#' | sed '/^:/s@\[[0-9]\{1,\}:[0-9]\{1,\}\]@[0:0]@g'")}}


# ip6tables-save
-----------------------------------------------------------------
{{salt['cmd.run']("ip6tables --list > /dev/null; ip6tables-save | \grep -v -F '#' | sed '/^:/s@\[[0-9]\{1,\}:[0-9]\{1,\}\]@[0:0]@g'")}}
{%- else -%}
# iptables --list-rules
-----------------------------------------------------------------
{{salt['cmd.run']('iptables --list-rules')}}


# ip6tables --list-rules
-----------------------------------------------------------------
{{salt['cmd.run']('ip6tables --list-rules')}}
{% endif %}
{% endif %}

{% if salt['cmd.has_exec']('firewall-cmd') -%}
# firewall-cmd --list-all
-----------------------------------------------------------------
{{salt['cmd.run']('firewall-cmd --list-all')}}
{% endif %}

# mount
-----------------------------------------------------------------
{{salt['cmd.run']('mount')}}

{% endif %}
"""
)


def markdown_basic_jinja_template(**kwargs):
    """
    Return text for a simple markdown jinja template

    This function can be used from the `highstate_doc.render` modules `jinja_template_function` option.
    """
    return markdown_basic_jinja_template_txt


def markdown_default_jinja_template(**kwargs):
    """
    Return text for a markdown jinja template that included a header

    This function can be used from the `highstate_doc.render` modules `jinja_template_function` option.
    """
    return markdown_default_jinja_template_txt


def markdown_full_jinja_template(**kwargs):
    """
    Return text for an advanced markdown jinja template

    This function can be used from the `highstate_doc.render` modules `jinja_template_function` option.
    """
    return markdown_advanced_jinja_template_txt


def _get_config(**kwargs):
    """
    Return configuration
    """
    config = {
        "filter_id_regex": [".*!doc_skip"],
        "filter_function_regex": [],
        "replace_text_regex": {},
        "processor": "highstate_doc.processor_markdown",
        "max_render_file_size": 10000,
        "note": None,
    }
    if "__salt__" in globals():
        config_key = f"{__virtualname__}.config"
        config.update(__salt__["config.get"](config_key, {}))
    # pylint: disable=C0201
    for k in set(config.keys()) & set(kwargs.keys()):
        config[k] = kwargs[k]
    return config


def read_file(name):
    """
    output the contents of a file:

    this is a workaround if the cp.push module does not work.
    https://github.com/saltstack/salt/issues/37133

    help the master output the contents of a document
    that might be saved on the minions filesystem.

    .. code-block:: python

        #!/bin/python
        import os
        import salt.client
        s = salt.client.LocalClient()
        o = s.cmd('*', 'highstate_doc.read_file', ['/root/README.md'])
        for m in o:
            d = o.get(m)
            if d and not d.endswith('is not available.'):
                # mkdir m
                #directory = os.path.dirname(file_path)
                if not os.path.exists(m):
                    os.makedirs(m)
                with open(m + '/README.md','wb') as fin:
                    fin.write(d)
                print('ADDED: ' + m + '/README.md')
    """
    out = ""
    try:
        with salt.utils.files.fopen(name, "r") as f:
            out = salt.utils.stringutils.to_unicode(f.read())
    except Exception as ex:  # pylint: disable=broad-except
        log.error(ex)
        return None
    return out


def render(
    jinja_template_text=None,
    jinja_template_function="highstate_doc.markdown_default_jinja_template",
    **kwargs,
):
    """
    Render highstate to a text format (default Markdown)

    if `jinja_template_text` is not set, `jinja_template_function` is used.

    jinja_template_text: jinja text that the render uses to create the document.
    jinja_template_function: a salt module call that returns template text.

    :options:
        highstate_doc.markdown_basic_jinja_template
        highstate_doc.markdown_default_jinja_template
        highstate_doc.markdown_full_jinja_template

    """
    config = _get_config(**kwargs)
    lowstates = process_lowstates(**kwargs)
    # TODO: __env__,
    context = {
        "saltenv": None,
        "config": config,
        "lowstates": lowstates,
        "salt": __salt__,
        "pillar": __pillar__,
        "grains": __grains__,
        "opts": __opts__,
        "kwargs": kwargs,
    }
    template_text = jinja_template_text
    if template_text is None and jinja_template_function:
        template_text = __salt__[jinja_template_function](**kwargs)
    if template_text is None:
        raise Exception("No jinja template text")

    txt = tpl.render_jinja_tmpl(template_text, context, tmplpath=None)
    # after processing the template replace passwords or other data.
    rt = config.get("replace_text_regex")
    for r in rt:
        txt = re.sub(r, rt[r], txt)
    return txt


def _blacklist_filter(s, config):
    ss = s["state"]
    sf = s["fun"]
    state_function = "{}.{}".format(s["state"], s["fun"])
    for b in config["filter_function_regex"]:
        if re.match(b, state_function):
            return True
    for b in config["filter_id_regex"]:
        if re.match(b, s["__id__"]):
            return True
    return False


def process_lowstates(**kwargs):
    """
    return processed lowstate data that was not blacklisted

    render_module_function is used to provide your own.
    defaults to from_lowstate
    """
    states = []
    config = _get_config(**kwargs)
    processor = config.get("processor")
    ls = __salt__["state.show_lowstate"]()

    if not isinstance(ls, list):
        raise Exception(
            "ERROR: to see details run: [salt-call state.show_lowstate]"
            " <-----***-SEE-***"
        )
    else:
        if ls:
            if not isinstance(ls[0], dict):
                raise Exception(
                    "ERROR: to see details run: [salt-call state.show_lowstate]"
                    " <-----***-SEE-***"
                )

    for s in ls:
        if _blacklist_filter(s, config):
            continue
        doc = __salt__[processor](s, config, **kwargs)
        states.append(doc)
    return states


def _state_data_to_yaml_string(data, whitelist=None, blacklist=None):
    """
    return a data dict in yaml string format.
    """
    y = {}
    if blacklist is None:
        # TODO: use salt defined STATE_REQUISITE_IN_KEYWORDS  STATE_RUNTIME_KEYWORDS  STATE_INTERNAL_KEYWORDS
        blacklist = [
            "__env__",
            "__id__",
            "__sls__",
            "fun",
            "name",
            "context",
            "order",
            "state",
            "require",
            "require_in",
            "watch",
            "watch_in",
        ]
    kset = set(data.keys())
    if blacklist:
        kset -= set(blacklist)
    if whitelist:
        kset &= set(whitelist)
    for k in kset:
        y[k] = data[k]
    if not y:
        return None
    return salt.utils.yaml.safe_dump(y, default_flow_style=False)


def _md_fix(text):
    """
    sanitize text data that is to be displayed in a markdown code block
    """
    return text.replace("```", "``[`][markdown parse fix]")


def _format_markdown_system_file(filename, config):
    ret = ""
    file_stats = __salt__["file.stats"](filename)
    y = _state_data_to_yaml_string(
        file_stats, whitelist=["user", "group", "mode", "uid", "gid", "size"]
    )
    if y:
        ret += f"file stat {filename}\n```\n{y}```\n"
    file_size = file_stats.get("size")
    if file_size <= config.get("max_render_file_size"):
        is_binary = True
        try:
            # TODO: this is linux only should find somthing portable
            file_type = __salt__["cmd.shell"](f"\\file -i '{filename}'")
            if "charset=binary" not in file_type:
                is_binary = False
        except Exception as ex:  # pylint: disable=broad-except
            # likely on a windows system, set as not binary for now.
            is_binary = False
        if is_binary:
            file_data = "[[skipped binary data]]"
        else:
            with salt.utils.files.fopen(filename, "r") as f:
                file_data = salt.utils.stringutils.to_unicode(f.read())
        file_data = _md_fix(file_data)
        ret += f"file data {filename}\n```\n{file_data}\n```\n"
    else:
        ret += "```\n{}\n```\n".format(
            "SKIPPED LARGE FILE!\nSet {}:max_render_file_size > {} to render.".format(
                f"{__virtualname__}.config", file_size
            )
        )
    return ret


def _format_markdown_link(name):
    link = name
    symbals = "~`!@#$%^&*()+={}[]:;\"<>,.?/|'\\"
    for s in symbals:
        link = link.replace(s, "")
    link = link.replace(" ", "-")
    return link


def _format_markdown_requisite(state, stateid, makelink=True):
    """
    format requisite as a link users can click
    """
    fmt_id = f"{state}: {stateid}"
    if makelink:
        return f" * [{fmt_id}](#{_format_markdown_link(fmt_id)})\n"
    else:
        return f" * `{fmt_id}`\n"


def processor_markdown(lowstate_item, config, **kwargs):
    """
    Takes low state data and returns a dict of processed data
    that is by default used in a jinja template when rendering a markdown highstate_doc.

    This `lowstate_item_markdown` given a lowstate item, returns a dict like:

    .. code-block:: none

        vars:       # the raw lowstate_item that was processed
        id:         # the 'id' of the state.
        id_full:    # combo of the state type and id "state: id"
        state:      # name of the salt state module
        function:   # name of the state function
        name:       # value of 'name:' passed to the salt state module
        state_function:    # the state name and function name
        markdown:          # text data to describe a state
            requisites:    # requisite like [watch_in, require_in]
            details:       # state name, parameters and other details like file contents

    """
    # TODO: switch or ... ext call.
    s = lowstate_item
    state_function = "{}.{}".format(s["state"], s["fun"])
    id_full = "{}: {}".format(s["state"], s["__id__"])

    # TODO: use salt defined STATE_REQUISITE_IN_KEYWORDS
    requisites = ""
    for comment, key in (
        ("run or update after changes in:\n", "watch"),
        ("after changes, run or update:\n", "watch_in"),
        ("require:\n", "require"),
        ("required in:\n", "require_in"),
    ):
        reqs = s.get(key, [])
        if reqs:
            requisites += comment
            for w in reqs:
                requisites += _format_markdown_requisite(*next(iter(w.items())))

    details = ""

    if state_function == "highstate_doc.note":
        if "contents" in s:
            details += "\n{}\n".format(s["contents"])
        if "source" in s:
            text = __salt__["cp.get_file_str"](s["source"])
            if text:
                details += f"\n{text}\n"
            else:
                details += "\n{}\n".format("ERROR: opening {}".format(s["source"]))

    if state_function == "pkg.installed":
        pkgs = s.get("pkgs", s.get("name"))
        details += f"\n```\ninstall: {pkgs}\n```\n"

    if state_function == "file.recurse":
        details += """recurse copy of files\n"""
        y = _state_data_to_yaml_string(s)
        if y:
            details += f"```\n{y}\n```\n"
        if "!doc_recurse" in id_full:
            findfiles = __salt__["file.find"](path=s.get("name"), type="f")
            if len(findfiles) < 10 or "!doc_recurse_force" in id_full:
                for f in findfiles:
                    details += _format_markdown_system_file(f, config)
            else:
                details += """ > Skipping because more than 10 files to display.\n"""
                details += (
                    """ > HINT: to force include !doc_recurse_force in state id.\n"""
                )
        else:
            details += """ > For more details review logs and Salt state files.\n\n"""
            details += """ > HINT: for improved docs use multiple file.managed states or file.archive, git.latest. etc.\n"""
            details += """ > HINT: to force doc to show all files in path add !doc_recurse .\n"""

    if state_function == "file.blockreplace":
        if s.get("content"):
            details += "ensure block of content is in file\n```\n{}\n```\n".format(
                _md_fix(s["content"])
            )
        if s.get("source"):
            text = "** source: " + s.get("source")
            details += "ensure block of content is in file\n```\n{}\n```\n".format(
                _md_fix(text)
            )

    if state_function == "file.managed":
        details += _format_markdown_system_file(s["name"], config)

    # if no state doc is created use default state as yaml
    if not details:
        y = _state_data_to_yaml_string(s)
        if y:
            details += f"```\n{y}```\n"

    r = {
        "vars": lowstate_item,
        "state": s["state"],
        "name": s["name"],
        "function": s["fun"],
        "id": s["__id__"],
        "id_full": id_full,
        "state_function": state_function,
        "markdown": {
            "requisites": requisites.decode("utf-8"),
            "details": details.decode("utf-8"),
        },
    }
    return r
