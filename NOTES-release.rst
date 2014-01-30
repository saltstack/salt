* tag
* branch
* merge to master
* upload to pypi
* download tarball from pypi & upload to github (keeps the same checksum)
* email mailing list; tweet, etc

First::

    devpkgs:
      pkg:
        - installed
        - pkgs:
          - build-essential
          - debootstrap
          - devscripts
          - dh-make
          - pbuilder

    pbuilder:
      cmd:
        - run
        - name: pbuilder create
        - unless: test -d /var/cache/pbuilder
        - require:
          - pkg: devpkgs

Next:

1.  Edit the changelog
2.  debuild -S
3.  dput ppa:saltstack/salt ../salt-XXX.X.X_source.changes

(For building a .deb:
4.  debuild)
