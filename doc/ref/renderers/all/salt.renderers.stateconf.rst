salt.renderers.stateconf
========================

.. py:module:: salt.renderers.stateconf

:maintainer: Jack Kuan <kjkuan@gmail.com>
:maturity: new
:platform: all

This module provides a custom renderer that processes a salt file with a
specified templating engine (e.g. Jinja) and a chosen data renderer (e.g. YAML),
extracts arguments for any ``stateconf.set`` state, and provides the extracted
arguments (including Salt-specific args, such as ``require``, etc) as template
context. The goal is to make writing reusable/configurable/parameterized
salt files easier and cleaner.

To use this renderer, either set it as the default renderer via the
``renderer`` option in master/minion's config, or use the shebang line in each
individual sls file, like so: ``#!stateconf``. Note, due to the way this
renderer works, it must be specified as the first renderer in a render
pipeline. That is, you cannot specify ``#!mako|yaml|stateconf``, for example.
Instead, you specify them as renderer arguments: ``#!stateconf mako . yaml``.

Here's a list of features enabled by this renderer.

- Prefixes any state id (declaration or reference) that starts with a dot (``.``)
  to avoid duplicated state ids when the salt file is included by other salt
  files.

  For example, in the `salt://some/file.sls`, a state id such as ``.sls_params``
  will be turned into ``some.file::sls_params``. Example:

  .. code-block:: yaml

      #!stateconf yaml . jinja

      .vim:
        pkg.installed

  Above will be translated into:

  .. code-block:: yaml

      some.file::vim:
        pkg.installed:
          - name: vim

  Notice how that if a state under a dot-prefixed state id has no ``name``
  argument then one will be added automatically by using the state id with
  the leading dot stripped off.

  The leading dot trick can be used with extending state ids as well,
  so you can include relatively and extend relatively. For example, when
  extending a state in `salt://some/other_file.sls`, e.g.:

  .. code-block:: yaml

      #!stateconf yaml . jinja

      include:
        - .file

      extend:
        .file::sls_params:
          stateconf.set:
            - name1: something

  Above will be pre-processed into:

  .. code-block:: yaml

      include:
        - some.file

      extend:
        some.file::sls_params:
          stateconf.set:
            - name1: something

- Adds a ``sls_dir`` context variable that expands to the directory containing
  the rendering salt file. So, you can write ``salt://{{sls_dir}}/...`` to
  reference templates files used by your salt file.

- Recognizes the special state function, ``stateconf.set``, that configures a
  default list of named arguments usable within the template context of
  the salt file. Example:

  .. code-block:: yaml

      #!stateconf yaml . jinja

      .sls_params:
        stateconf.set:
          - name1: value1
          - name2: value2
          - name3:
            - value1
            - value2
            - value3
          - require_in:
            - cmd: output

      # --- end of state config ---

      .output:
        cmd.run:
          - name: |
              echo 'name1={{sls_params.name1}}
                    name2={{sls_params.name2}}
                    name3[1]={{sls_params.name3[1]}}
              '

  This even works with ``include`` + ``extend`` so that you can override
  the default configured arguments by including the salt file and then
  ``extend`` the ``stateconf.set`` states that come from the included salt
  file. (*IMPORTANT: Both the included and the extending sls files must use the
  stateconf renderer for this ``extend`` to work!*)

  Notice that the end of configuration marker (``# --- end of state config --``)
  is needed to separate the use of 'stateconf.set' form the rest of your salt
  file. The regex that matches such marker can be configured via the
  ``stateconf_end_marker`` option in your master or minion config file.

  Sometimes, it is desirable to set a default argument value that's based on
  earlier arguments in the same ``stateconf.set``. For example, it may be
  tempting to do something like this:

  .. code-block:: yaml

      #!stateconf yaml . jinja

      .apache:
        stateconf.set:
          - host: localhost
          - port: 1234
          - url: 'http://{{host}}:{{port}}/'

      # --- end of state config ---

      .test:
        cmd.run:
          - name: echo '{{apache.url}}'
          - cwd: /

  However, this won't work. It can however be worked around like so:

  .. code-block:: yaml

      #!stateconf yaml . jinja

      .apache:
        stateconf.set:
          - host: localhost
          - port: 1234
      {#  - url: 'http://{{host}}:{{port}}/' #}

      # --- end of state config ---
      # {{ apache.setdefault('url', "http://%(host)s:%(port)s/" % apache) }}

      .test:
        cmd.run:
          - name: echo '{{apache.url}}'
          - cwd: /

- Adds support for relative include and exclude of .sls files. Example:

  .. code-block:: yaml

      #!stateconf yaml . jinja

      include:
        - .apache
        - .db.mysql
        - ..app.django

      exclude:
        - sls: .users

  If the above is written in a salt file at `salt://some/where.sls` then
  it will include `salt://some/apache.sls`, `salt://some/db/mysql.sls` and
  `salt://app/django.sls`, and exclude `salt://some/users.ssl`. Actually,
  it does that by rewriting the above ``include`` and ``exclude`` into:

  .. code-block:: yaml

      include:
        - some.apache
        - some.db.mysql
        - app.django

      exclude:
        - sls: some.users


- Optionally (enabled by default, *disable* via the `-G` renderer option,
  e.g. in the shebang line: ``#!stateconf -G``), generates a
  ``stateconf.set`` goal state (state id named as ``.goal`` by default,
  configurable via the master/minion config option, ``stateconf_goal_state``)
  that requires all other states in the salt file. Note, the ``.goal``
  state id is subject to dot-prefix rename rule mentioned earlier.

  Such goal state is intended to be required by some state in an including
  salt file. For example, in your webapp salt file, if you include a
  sls file that is supposed to setup Tomcat, you might want to make sure that
  all states in the Tomcat sls file will be executed before some state in
  the webapp sls file.

- Optionally (enable via the `-o` renderer option, e.g. in the shebang line:
  ``#!stateconf -o``), orders the states in a sls file by adding a
  ``require`` requisite to each state such that every state requires the
  state defined just before it. The order of the states here is the order
  they are defined in the sls file. (Note: this feature is only available
  if your minions are using Python >= 2.7. For Python2.6, it should also
  work if you install the `ordereddict` module from PyPI)

  By enabling this feature, you are basically agreeing to author your sls
  files in a way that gives up the explicit (or implicit?) ordering imposed
  by the use of ``require``, ``watch``, ``require_in`` or ``watch_in``
  requisites, and instead, you rely on the order of states you define in
  the sls files. This may or may not be a better way for you. However, if
  there are many states defined in a sls file, then it tends to be easier
  to see the order they will be executed with this feature.

  You are still allowed to use all the requisites, with a few restrictions.
  You cannot ``require`` or ``watch`` a state defined *after* the current
  state. Similarly, in a state, you cannot ``require_in`` or ``watch_in``
  a state defined *before* it. Breaking any of the two restrictions above
  will result in a state loop. The renderer will check for such incorrect
  uses if this feature is enabled.

  Additionally, ``names`` declarations cannot be used with this feature
  because the way they are compiled into low states make it impossible to
  guarantee the order in which they will be executed. This is also checked
  by the renderer. As a workaround for not being able to use ``names``,
  you can achieve the same effect, by generate your states with the
  template engine available within your sls file.

  Finally, with the use of this feature, it becomes possible to easily make
  an included sls file execute all its states *after* some state (say, with
  id ``X``) in the including sls file.  All you have to do is to make state,
  ``X``, ``require_in`` the first state defined in the included sls file.


When writing sls files with this renderer, one should avoid using what can be
defined in a ``name`` argument of a state as the state's id. That is, avoid
writing states like this:

.. code-block:: yaml

    /path/to/some/file:
      file.managed:
        - source: salt://some/file

    cp /path/to/some/file file2:
      cmd.run:
        - cwd: /
        - require:
          - file: /path/to/some/file

Instead, define the state id and the ``name`` argument separately for each
state. Also, the ID should be something meaningful and easy to reference within
a requisite (which is a good habit anyway, and such extra indirection would
also makes the sls file easier to modify later). Thus, the above states should
be written like this:

.. code-block:: yaml

    add-some-file:
      file.managed:
        - name: /path/to/some/file
        - source: salt://some/file

    copy-files:
      cmd.run:
        - name: cp /path/to/some/file file2
        - cwd: /
        - require:
          - file: add-some-file

Moreover, when referencing a state from a requisite, you should reference the
state's id plus the state name rather than the state name plus its ``name``
argument. (Yes, in the above example, you can actually ``require`` the
``file: /path/to/some/file``, instead of the ``file: add-some-file``). The
reason is that this renderer will re-write or rename state id's and their
references for state id's prefixed with ``.``. So, if you reference ``name``
then there's no way to reliably rewrite such reference.
