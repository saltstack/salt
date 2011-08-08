# Convenience targets for building and installing Arch packages
# prior to committing changes to git.

local:
	-rm -rf ../../build
	-rm salt-*.pkg.tar.xz
	-rm -rf pkg
	if [ "$$(id -u)" -eq 0 ]; \
	then \
	    makepkg -f -p PKGBUILD-local --asroot; \
	else \
	    makepkg -f -p PKGBUILD-local; \
	fi
	rm -rf pkg
	-rm -rf ../../build

install: local
	-/etc/rc.d/salt-monitor stop
	-/etc/rc.d/salt-minion stop
	-/etc/rc.d/salt-master stop
	-yes | pacman -R salt-local
	-yes | pacman -R salt-git
	-yes | pacman -R salt
	yes | pacman -U salt-local-*

