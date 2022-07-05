include config.mk
PYTHON_VERSION ?= 3.8.13
PY_SUFFIX ?= $(shell echo $(PYTHON_VERSION) | sed -r 's/([0-9]+)(\.[0-9]+)(\.[0-9]+)/\1\2/')
TARGET_DIRNAME := $(shell dirname $(TARGET_DIR))
TARGET_BASENAME := $(shell basename $(TARGET_DIR))
DYNLOAD = $(TARGET_DIR)/lib/python$(PY_SUFFIX)/lib-dynload/*.so
DYNLIB := libssl.so.10 libcrypto.so.10 libcrypt.so libffi.so.6 libpthread.so.0 libc.so.6 libm.so libutil.so


.PHONY: all $(SCRIPTS) $(DYNLOAD)

all: $(SCRIPTS_DIR)/salt

clean: ;
	rm -rf $(TARGET_DIRNAME)


onedir: salt.tar.xz

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
	./configure --prefix=$(TARGET_DIR) ; \ #--enable-optimizations; \
	make -j4; make install; \

$(TARGET_DIR)/.onedir:
	touch $(TARGET_DIR)/.onedir

$(SCRIPTS_DIR)/salt-pip: $(TARGET_DIR)/bin/python$(PY_SUFFIX) $(TARGET_DIR)/.onedir
	cp $(PWD)/scripts/salt-pip $(SCRIPTS_DIR)/salt-pip
	sed -i 's/^#!.*$$/#!\/bin\/sh\n"exec" "`dirname $$0`\/$(PYBIN)" "$$0" "$$@"/' $@;

$(DYNLOAD):
	patchelf --set-rpath '$$ORIGIN/' $@


$(DYNLIB):
	cp $(realpath /lib64/$@) $(TARGET_DIR)/lib/python$(PY_SUFFIX)/lib-dynload/$@


$(SCRIPTS_DIR)/salt: $(SCRIPTS_DIR)/salt-pip $(DYNLOAD) $(DYNLIB)
	$(SCRIPTS_DIR)/salt-pip install .
	patchelf --set-rpath '$$ORIGIN/' $(TARGET_DIR)/lib/python$(PY_SUFFIX)/site-packages/pyzmq.libs/libzmq-68c212d3.so.5.2.4


$(SCRIPTS): $(SCRIPTS_DIR)/salt
	mv $(TARGET_DIR)/bin/$@ $(SCRIPTS_DIR);
	sed -i 's/^#!.*$$/#!\/bin\/sh\n"exec" "`dirname $$0`\/$(PYBIN)" "$$0" "$$@"/' $(SCRIPTS_DIR)/$@;


salt.tar.xz: $(SCRIPTS)
	find $(TARGET_DIR) -name '*.pyc' -exec rm -f {} \;
	# XXX: Should we keep this?
	rm -rf $(TARGET_DIR)/include $(TARGET_DIR)/share
	tar cJvf salt.tar.xz -C $(TARGET_DIRNAME) $(TARGET_BASENAME);
