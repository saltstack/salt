- Feature Name: adding_minion_id_to_fileserver_calls
- Start Date: 2018-09-13
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

Add minion id to all fileserver events sent to request server and optionally sign the payload as well.

# Motivation
[motivation]: #motivation

Currently there is no possibility to determine on master which minion requested particular fileserver operation (file list, file request, etc.), which makes it impossible to implement any minion-based permissions level onto fileserver.

Implementing this RFC would make it possible to implement custom fileservers that support various layers of security, allowing to restrict access for particular minions to environments/files and achieving some level of fileserver multitenancy.

# Design
[design]: #detailed-design

Proposed design is to add `id` key to all fileserver-related payloads in `RemoteClient`, optionally allowing to also sign the messages similarly as it's done via [minion_sign_messages](https://github.com/saltstack/salt/blob/cb172352340bf8da34cd128dbddf1abfc4995bb5/salt/minion.py#L1380) (either reusing same configuration option or introducing new one).

After master can receive minion identity and signature, custom fileserver modules can be implemented or existing modules can be extended with the functionality (out of scope for this RFC).

To actually propagate that load data to custom fileserver, appropriate changes need to be done to [Fileserver](https://github.com/saltstack/salt/blob/cb172352340bf8da34cd128dbddf1abfc4995bb5/salt/fileserver/__init__.py#L515) because not all methods propagate full load to underlying modules ([envs](https://github.com/saltstack/salt/blob/cb172352340bf8da34cd128dbddf1abfc4995bb5/salt/fileserver/__init__.py#L515), [find_file](https://github.com/saltstack/salt/blob/cb172352340bf8da34cd128dbddf1abfc4995bb5/salt/fileserver/__init__.py#L610)). To avoid issue when all existing fileserver modules would have to be refactored to support new function arguments, similar usage of `_argspec` can be used as for `envs` method.


## Alternatives
[alternatives]: #alternatives

Include id/signature automatically to everything going through `channel.send` so every function in [RemoteFuncs](https://github.com/saltstack/salt/blob/cb172352340bf8da34cd128dbddf1abfc4995bb5/salt/daemons/masterapi.py#L404)/[AESFuncs](https://github.com/saltstack/salt/blob/cb172352340bf8da34cd128dbddf1abfc4995bb5/salt/master.py#L1833) can verify minion validity. This would however either require necessary validations for every master request - for some calls this would be unnecessary and others are already validating this via [tok key](https://github.com/saltstack/salt/blob/cb172352340bf8da34cd128dbddf1abfc4995bb5/salt/master.py#L1313), or just sending unnecessary data to masters.


## Unresolved questions
[unresolved]: #unresolved-questions

Reuse `minion_sign_messages` configuration option or introduce new option such as `minion_sign_fileserver_messages`?

# Drawbacks
[drawbacks]: #drawbacks

When this gets introduced, every fileserver payload will be larger by minion id and signature, increasing traffic slightly. Also additional load can be introduced to minions when payload signature is computed (only applicable if enabled).

As there will be no default processing for the id/signature, no additional load should be placed on masters and existing functionality should be preserved.
