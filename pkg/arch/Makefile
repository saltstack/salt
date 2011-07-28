# Convenience targets for building and installing Arch packages
# prior to committing changes to git.

local:
	makepkg -f -p PKGBUILD-local --asroot
	rm -rf pkg

install: local
	-yes | pacman -R salt-local
	-yes | pacman -R salt-git
	-yes | pacman -R salt
	yes | pacman -U salt-local-*

