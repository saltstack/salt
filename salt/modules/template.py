# -*- coding: utf-8 -*-
'''
Template Utils
==============

.. versionadded:: Fluorine

A collection of helper functions to provide direct access to Salt's template
rendering system (and avoid reinventing wheels).
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt modules
from salt.utils.files import mkstemp
from salt.exceptions import CommandExecutionError


def render(source=None,
           source_string=None,
           template_engine='jinja',
           source_hash=None,
           source_hash_name=None,
           user=None,
           group=None,
           mode=None,
           attrs=None,
           context=None,
           defaults=None,
           skip_verify=True,
           saltenv='base'):
    '''
    Render the remote template file, or the template as string.

    source
        The template source file to be rendered. No need to use this argument
        when passing ``source_string``.

        This can be specified using the absolute path to the file, or using one
        of the following URL schemes:

        - ``salt://``, to fetch the file from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

    source_string
        The template source, as text. No need to use this argument when passing
        ``source``.

    template_engine: ``jinja``
        The template engine to use when rendering the source file. Default:
        ``jinja``. To simply fetch the file without attempting to render, set
        this argument to ``None``.

    source_hash
        The hash of the ``source`` file.

    source_hash_name
        When ``source_hash`` refers to a remote file, this specifies the
        filename to look for in that file.

    user
        Owner of the file.

    group
        Group owner of the file.

    mode
        Permissions of the file.

    attrs
        Attributes of the file.

    context
        Variables to add to the template context.

    defaults
        Default values of the context dictionary.

    skip_verify: ``True``
        If ``True``, hash verification of remote file sources (``http://``,
        ``https://``, ``ftp://``, etc.) will be skipped, and the ``source_hash``
        argument will be ignored.

    CLI Example:

    .. code-block:: bash

        salt '*' template.render source=https://bit.ly/2yuSs2Y context="{'hostname': 'example.com'}"
        salt '*' template.render source=salt://path/to/template.mako context="{'hostname': 'example.com'}"
        salt '*' template.render source_string='hostname {{ hostname }}' context="{'hostname': 'example.com'}"
    '''
    dest_file = mkstemp()
    if source_string:
        source = mkstemp()
        __salt__['file.write'](source, source_string)
    file_mgd = __salt__['file.get_managed'](dest_file,
                                            template_engine,
                                            source,
                                            source_hash,
                                            source_hash_name,
                                            user,
                                            group,
                                            mode,
                                            attrs,
                                            saltenv,
                                            context,
                                            defaults,
                                            skip_verify)
    if not file_mgd[0]:
        raise CommandExecutionError(file_mgd[2])
    file_str = __salt__['file.read'](file_mgd[0])
    # Removing the temporary file(s) created along the way
    __salt__['file.remove'](file_mgd[0])
    if source_string:
        __salt__['file.remove'](source)
    return file_str
