# Convenience targets for building and installing Arch packages
# prior to committing changes to git.

PKGNAME=salt

local:
	-rm -rf ../../build
	-rm $(PKGNAME)-*.pkg.tar.xz
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
	-for script in /etc/rc.d/salt*; \
	 do \
	     "$$script" stop; \
	 done
	-yes | pacman -R $(PKGNAME)
	yes | pacman -U $(PKGNAME)-*.pkg.tar.xz
