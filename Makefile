include config.mk
PYTHON_VERSION ?= 3.8.13
PY_SUFFIX ?= $(shell echo $(PYTHON_VERSION) | sed -r 's/([0-9]+)(\.[0-9]+)(\.[0-9]+)/\1\2/')
TARGET_DIRNAME := $(shell dirname $(TARGET_DIR))
TARGET_BASENAME := $(shell basename $(TARGET_DIR))

SALT_VERSION = $(shell $(TARGET_DIR)/salt --version | awk '{ print $$2 }')
ARCH := $(shell uname -m)


.PHONY: all requirements onedir clean $(SCRIPTS)

all: $(SCRIPTS_DIR)/salt

clean:
	rm -rf $(TARGET_DIRNAME)


onedir: salt-$(SALT_VERSION)_$(ARCH).tar.xz
	echo $(SALT_VERSION)

$(TARGET_DIR):
	mkdir -p $(TARGET_DIR)

$(TARGET_DIRNAME)/Python-$(PYTHON_VERSION).tar.xz: $(TARGET_DIR)
	curl https://www.python.org/ftp/python/$(PYTHON_VERSION)/Python-$(PYTHON_VERSION).tar.xz -o $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION).tar.xz
	touch $@

$(TARGET_DIRNAME)/Python-$(PYTHON_VERSION): $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION).tar.xz
	cd $(TARGET_DIRNAME); \
	tar xvf Python-$(PYTHON_VERSION).tar.xz; \
	touch $@; \
	cd $(PWD)

$(TARGET_DIR)/bin/python$(PY_SUFFIX):  $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION)
	cd $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION); \
	./configure --prefix=$(TARGET_DIR) ; \
	make -j4; \
	make install; \
	cd $(TARGET_DIR)/bin; \
	ln -sf python$(PY_SUFFIX) python; \
	ln -sf pip$(PY_SUFFIX) pip; \
	cd $(PWD);

$(SCRIPTS_DIR)/salt-pip: $(TARGET_DIR)/bin/python$(PY_SUFFIX) $(TARGET_DIR)/.onedir
	cp $(PWD)/scripts/salt-pip $(SCRIPTS_DIR)/salt-pip
	sed -i 's/^#!.*$$/#!\/bin\/sh\n"exec" "`dirname $$0`\/$(PYBIN)" "$$0" "$$@"/' $@;

$(SCRIPTS_DIR)/salt: $(SCRIPTS_DIR)/salt-pip $(DYNLOAD) $(DYNLIB)
	$(SCRIPTS_DIR)/salt-pip install .
	$(SCRIPTS_DIR)/salt-pip install -r $(PWD)/requirements/static/pkg/py$(PY_SUFFIX)/linux.txt

$(SCRIPTS): $(SCRIPTS_DIR)/salt
	mv $(TARGET_DIR)/bin/$@ $(SCRIPTS_DIR);
	sed -i 's/^#!.*$$/#!\/bin\/sh\n"exec" "`dirname $$0`\/$(PYBIN)" "$$0" "$$@"/' $(SCRIPTS_DIR)/$@;


$(TARGET_DIR)/.onedir:
	touch $(TARGET_DIR)/.onedir

fixlibs:
	pkg/fixlibs.sh $(TARGET_DIR)/lib

$(TARGET_DIR)/install-salt:
	cp $(PWD)/scripts/install-salt $(SCRIPTS_DIR)/install-salt

$(TARGET_DIR)/uninstall-salt: fixlibs
	cp $(PWD)/scripts/uninstall-salt $(SCRIPTS_DIR)/uninstall-salt

salt-$(SALT_VERSION)_$(ARCH).tar.xz: $(SCRIPTS) $(TARGET_DIR)/install-salt $(TARGET_DIR)/uninstall-salt
	sh -c "find $(TARGET_DIR) -name '__pycache__' -type d -print0 |xargs -0 -n1 rm -rf --"
	# Remove Python Headers
	# rm -rf $(TARGET_DIR)/include
	# Remove man pages
	rm -rf $(TARGET_DIR)/share
	tar cJvf salt-$(SALT_VERSION)_$(ARCH).tar.xz -C $(TARGET_DIRNAME) $(TARGET_BASENAME);
