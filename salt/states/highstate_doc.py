# -*- coding: utf-8 -*-
"""
To be used with proccessors in module `highstate_doc`.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

__virtualname__ = "highstate_doc"


def note(name, source=None, contents=None, **kwargs):
    """
    Add content to a document generated using `highstate_doc.render`.

    This state does not preform any tasks on the host. It only is used in highstate_doc lowstate proccessers
    to include extra documents.

    .. code-block:: yaml

        {{sls}} example note:
            highstate_doc.note:
                - name: example note
                - require_in:
                    - pkg: somepackage
                - contents: |
                    example `highstate_doc.note`
                    ------------------
                    This state does not do anything to the system! It is only used by a `proccesser`
                    you can use `requisites` and `order` to move your docs around the rendered file.
                    .. this message appare aboce the `pkg: somepackage` state.
                - source: salt://{{tpldir}}/also_include_a_file.md

        {{sls}} extra help:
            highstate_doc.note:
                - name: example
                - order: 0
                - source: salt://{{tpldir}}/HELP.md
    """
    comment = ""
    if source:
        comment += "include file: {0}\n".format(source)
    if contents and len(contents) < 200:
        comment += contents
    return {"name": name, "result": True, "comment": comment, "changes": {}}
