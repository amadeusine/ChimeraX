# need absolute directory for build_prefix
build_prefix = $(shell (cd "$(TOP)"; pwd))/build
bindir = $(build_prefix)/bin
includedir = $(build_prefix)/include
libdir = $(build_prefix)/lib
datadir = $(build_prefix)/share
shlibdir = $(libdir)
tmpdir = $(build_prefix)/tmp
webdir = $(build_prefix)/webapp

# by default, don't do anything
all:

# version numbers that leak out of prerequisites

PYTHON_VERSION = 3.4
PYTHON_ABI = m
# Windows uses python22.dll instead of libpython2.2.so
PYVER_NODOT = $(subst .,,$(PYTHON_VERSION))

include $(TOP)/mk/os.make

ifdef USE_MAC_FRAMEWORKS
frameworkdir = $(build_prefix)/Library/Frameworks
endif

ifndef WIN32
RSYNC = rsync -rltWv --executability
else
RSYNC = $(bindir)/rsync.convert -rlptWv
endif

ifdef WIN32
PYTHON_INCLUDE_DIRS = -I'$(shell cygpath -m '$(includedir)/python$(PYTHON_VERSION)$(PYTHON_ABI)')'
PYTHON_LIBRARY_DIR = $(bindir)/Lib
else ifdef USE_MAC_FRAMEWORKS
PYTHON_INCLUDE_DIRS = $(shell $(bindir)/python$(PYTHON_VERSION)$(PYTHON_ABI)-config --includes)
PYTHON_FRAMEWORK = $(frameworkdir)/Python.framework/Versions/$(PYTHON_VERSION)
PYTHON_LIBRARY_DIR = $(PYTHON_FRAMEWORK)/lib/python$(PYTHON_VERSION)
else
PYTHON_INCLUDE_DIRS = -I$(includedir)/python$(PYTHON_VERSION)$(PYTHON_ABI)
PYTHON_LIBRARY_DIR = $(libdir)/python$(PYTHON_VERSION)
endif
PYSITEDIR = $(PYTHON_LIBRARY_DIR)/site-packages

pkg_dir:
	if [ ! -d "$(PKG_DIR)" ]; then mkdir $(PKG_DIR); fi
