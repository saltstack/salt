DIVERGENCES TO KEEP AT ALL COSTS:
----------------------------------

- [protect VT logs from unicode strings / 9484b3a6bb37539fe03ee65a3ff0c25cca617eec](https://github.com/makinacorpus/salt/commit/9484b3a6bb37539fe03ee65a3ff0c25cca617eec)

    - Upstream did not accepted this trivial changeset, even as a later changeable changeset, issue is pending for more than a while here:

        - https://github.com/saltstack/salt/issues/21441
        - https://github.com/saltstack/salt/pull/20918

- zcbuildout now living in [makina-states/salt_fork](https://github.com/makinacorpus/makina-states/tree/master/salt_fork).

    - [module](https://github.com/makinacorpus/makina-states/blob/master/salt_fork/modules/zcbuildout.py)
    - [state](https://github.com/makinacorpus/makina-states/blob/master/salt_fork/states/zcbuildout.py)


- [raise appropriate AttributeEror for certain collectionmapping attributes / a1fde4c120261517c036a708adf2f33850f1cad3](https://github.com/makinacorpus/salt/commit/a1fde4c120261517c036a708adf2f33850f1cad3)

    - for tests reasons only, but in spirit the loader doesnt respect without the patch that much a dict-like interface toward the copy method.
    - https://github.com/saltstack/salt/pull/22940#issuecomment-95259610
    - proposed as fix but unrelated: https://github.com/saltstack/salt/pull/22950
    - tried to rediscuss on https://github.com/saltstack/salt/issues/23317

- [environ hotfix / 337ed10cfc9f53724e653e9d3ccef317005d9817](https://github.com/makinacorpus/salt/commit/337ed10cfc9f53724e653e9d3ccef317005d9817)

       - See https://github.com/saltstack/salt/issues/24480

- iptables needs sync, currently this is a mix from stable/develop, waiting again a bit
