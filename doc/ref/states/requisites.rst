==========
Requisites
==========

The Salt requisite system is used to create relationships between states. The
core idea being, that when one state it dependent somehow on another that
interdependency can be easily defined.

Requisites come in two types. Direct requisites, and requisite_ins. The
relationships are directional, so a requisite statement makes the requiring
state declaration depend on the required state declaration:

.. code-block:: yaml

    vim:
      pkg.installed

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc
        - require:
          - pkg: vim

So in this example, the file ``/etc/vimrc`` depends on the vim package.

Requisite_in statements are the opposite, instead of saying "I depend on
something", requisite_ins say "Someone depends on me":

.. code-block:: yaml

    vim:
      pkg.installed:
        - require_in:
          - file: /etc/vimrc

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc

So here, with a requisite_in, the same thing is accomplished, but just from
the other way around. The vim package is saying "/etc/vimrc depends on me".

In the end a single dependency map is created and everything is executed in a
finite and predictable order.

Requisite and Requisite in types
================================

There are three requisite statements that can be used in Salt. the ``require``,
``watch`` and ``use`` requisites. Each requisite also has a corresponding
requisite_in: ``require_in``, ``watch_in`` and ``use_in``. All of the
requisites define specific relationships and always work with the dependency
logic defined above.

Require
-------

The most basic requisite statement is ``require``. The behavior of require is
simple. Make sure that the dependent state is executed before the depending
state, and it the dependent state fails, don't run the depending state. So in
the above examples the file ``/etc/vimrc`` will only be applied after the vim
package is installed and only if the vim package is installed successfully.

Watch
-----

The watch statement does everything the require statement does, but with a
little more. The watch statement looks into the state modules for a function
called ``mod_watch``. If this function is not available in the corresponding
state module, then watch does the same thing as require. If the ``mod_watch``
function is in the state module, then the watched state is checked to see if
it made any changes to the system, if it has, then ``mod_watch`` is called.

Perhaps the best example of using watch is with a service, when a service
watches other states, then when the other states make changes on the system
the service is reloaded or restarted.

Use
---

# This needs to be filled in
