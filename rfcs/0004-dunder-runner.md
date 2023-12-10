- Feature Name: Rename ``__salt__`` to ``__runner__`` in the Runner functions
- Start Date: 2019-01-02
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

As [this](https://github.com/saltstack/salt/blob/develop/salt/loader.py#L933) 4
years old TODO states, we are indeed overloading ``__salt__`` too much.
In the recent releases, we have added the ``salt.cmd`` Runner function to
be able to invoke Execution Functions on the Master side, however the usage is
counter-intuitive and often misleading. Additionally, this prevents a drawbacks
when it comes to whatever template rendering on the Master side.

# Motivation
[motivation]: #motivation

One of the main arguments is solving that 4-years old TODO mentioned in the
Summary. I can potentially understand what were the reasons back then, when the
``__salt__`` dunder has been added to be available on the Master side, however I
believe these reasons are now obsolete: Salt has evolved and still has much to
grow in terms of glueing different parts together; for a very long time it felt
like the Execution Modules, Runners, et. al., are separate entities, completely
decoupled from the rest. But more recently, the modern Salt, feels much more
like a whole, and not separate conglomerates. Renaming the ``__salt__`` object
to, e.g., ``__runner__``, and re-mapping ``__salt__`` to the Execution Functions
on the Minion side, would be a step forward in this direction.

Historically, from a Runner, we didn't have native support for accessing
arbitrary Execution Functions. In the recent releases, we have a new Runner
``salt.cmd`` as a workaround, however the usage is not particularly
straight forward, e.g., ``__salt__['salt.cmd']('system.get_system_date')``.
Renaming the existing ``__salt__`` to ``__runner__`` and re-mapping ``__salt__``
to the Minion modules, the usage becomes: ``__salt__['system.get_system_date']``
just like on the Minion side, by re-using the existing code, and executing it
on the Master.

This equally has an impact on the template rendering pipeline, for anything that
is rendered on the Master side (anything SLS rendered on the Master). A good
example is Reactor SLS files: when I firstly used in a Reactor
``salt.<module>.<function>`` I wasn't sure whether I should call an Execution
Function or a Runner Function. Few years later, I still need to double check
that. For this reason, overloading ``__salt__`` on the Master side becomes
misleading, while having a separate object would make it self-explanatory and
expand the capabilities.

Besides all of these, the biggest issue I hit was in the context of network
automation: without diving into too many details beyond the current scope, I
managed to have network devices managed from the Master only (i.e., without any
Minions or Proxy Minions). The implementation is based on a simple Runner, it
works very well, except when trying to invoke States. For more context, when
working with network devices, we usually aren't able to install the regular Salt
Minion on the devices we target, and typically we use the Proxy Minion which is
installed on whatever server. In other words, the State system doesn't care
where it's executed from (i.e., from what physical machine). For this reason, a
"proxyless" implementation is literally blocked by a simple object naming.

# Design
[design]: #detailed-design

The basic implementation is as simple as renaming the ``__salt__`` dunder to
``__runner__`` into the Lazy Loader. To resolve also the second part of the
problem, have ``__salt__`` point to the Minion modules. In code, this change is
as simple as:

```diff
 diff --git a/salt/loader.py b/salt/loader.py
 index e046b449a5..b4bd45472b 100644
 --- a/salt/loader.py
 +++ b/salt/loader.py
 @@ -915,7 +915,7 @@ def call(fun, **kwargs):
      return funcs[fun](*args)


 -def runner(opts, utils=None, context=None, whitelist=None):
 +def runner(opts, functions=None, utils=None, context=None, whitelist=None, proxy=None):
      '''
      Directly call a function inside a loader directory
      '''
 @@ -927,16 +927,18 @@ def runner(opts, utils=None, context=None, whitelist=None, proxy=None):
          _module_dirs(opts, 'runners', 'runner', ext_type_dirs='runner_dirs'),
          opts,
          tag='runners',
 -        pack={'__utils__': utils, '__context__': context},
 +        pack={'__utils__': utils, '__context__': context, '__proxy__': proxy},
          whitelist=whitelist,
      )
 +    if functions is None:
 +        functions = minion_mods(opts,
 +                                utils=utils,
 +                                context=context,
 +                                whitelist=whitelist,
 +                                proxy=proxy)
 -    ret.pack['__salt__'] = ret
 +    ret.pack['__salt__'] = functions
 +    ret.pack['__runner__'] = ret
      return ret
```

While testing, I've noticed that the time to load the Minion functions is quite
considerable (a few seconds), so I thought about adding a new option:
``runner_load_minion_mods`` defaulting to ``False`` which can be used to request
whether the Minion modules should always available in the Runners.

A more extensive change can be followed at:
https://github.com/saltstack/salt/compare/develop...mirceaulinic:mircea/dunder-runner?expand=1#diff-f6777cb7fca1276c97cd4b4a6b9f085a
which should cover most of the core changes required for this. Another step
required together with the change linked above is replacing ``__salt__`` with
``__runner__`` in all the Runner modules, e.g.,
``sed -i 's/__salt__/__runner__/g' salt/runners/``.

Even though in code that's a very simple change, it is breaking backwards
compatibility and the users would need to execute the above rename command in
their Runner extension directory ``salt://_runners/``.

To help with this transition, for a couple of major releases, we can pack both
``__salt__`` and ``__runner__``:

```python
ret.pack['__salt__'] = ret
ret.pack['__runner__'] = ret
```

This wouldn't change anything, but allow the users to prepare in advance the
handover to the new variable name. At the same time, we may add a warning to
mention that they should no longer use ``__salt__`` to invoke Runner functions
from a Runner, and switch to using ``__runner__``. I would be tempted to suggest
adding these two changes (the duplicate packing and the warning) straight away
into the develop branch to be included in the very next major release, Neon,
and targeting the whole change for Magnesium.

Nevertheless, I am going to handle the documentation for these changes before
and after the releases mentioned.

# Drawbacks
[drawbacks]: #drawbacks

The drawback I'm seeing here is the breaking change for the users, and I have
elaborated under the Design paragraph on how to approach this.
