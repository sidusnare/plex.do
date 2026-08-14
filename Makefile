# Makefile for plex.do (plexdo)
#
# Common targets:
#   make install              install the package and the bash completion
#   make uninstall            remove both again
#   make develop              editable install with the dev extras
#   make check                lint, build, and validate the distribution
#
# Useful variables:
#   PREFIX=/usr/local         install completion system-wide instead of per-user
#   PIP_FLAGS=--user          extra flags forwarded to pip install
#   COMPLETION_DIR=<path>     override the completion destination outright
#   DESTDIR=<path>            staging root, for distribution packaging

PYTHON        ?= python3
PIP           ?= $(PYTHON) -m pip
PIP_FLAGS     ?=
PACKAGE       := plexdo
MAN_PAGE        := man/plex.do.1
BASH_COMPLETION := completions/plex.do.bash
ZSH_COMPLETION  := completions/_plex.do
FISH_COMPLETION := completions/plex.do.fish

# Per-user by default; PREFIX switches to system-wide locations.
XDG_DATA_HOME   ?= $(HOME)/.local/share
XDG_CONFIG_HOME ?= $(HOME)/.config
ifeq ($(strip $(PREFIX)),)
MAN_DIR             ?= $(XDG_DATA_HOME)/man
COMPLETION_DIR      ?= $(XDG_DATA_HOME)/bash-completion/completions
ZSH_COMPLETION_DIR  ?= $(XDG_DATA_HOME)/zsh/site-functions
FISH_COMPLETION_DIR ?= $(XDG_CONFIG_HOME)/fish/completions
else
MAN_DIR             ?= $(PREFIX)/share/man
COMPLETION_DIR      ?= $(PREFIX)/share/bash-completion/completions
ZSH_COMPLETION_DIR  ?= $(PREFIX)/share/zsh/site-functions
FISH_COMPLETION_DIR ?= $(PREFIX)/share/fish/vendor_completions.d
endif

MAN_TARGET  := $(DESTDIR)$(MAN_DIR)/man1/plex.do.1
BASH_TARGET := $(DESTDIR)$(COMPLETION_DIR)/plex.do
ZSH_TARGET  := $(DESTDIR)$(ZSH_COMPLETION_DIR)/_plex.do
FISH_TARGET := $(DESTDIR)$(FISH_COMPLETION_DIR)/plex.do.fish

.PHONY: help install uninstall reinstall develop install-completion \
        uninstall-completion install-completion-bash install-completion-zsh \
        install-completion-fish install-man uninstall-man check-version \
        build check lint dist-check clean distclean

# ---------------------------------------------------------------------------

help:
	@echo "plex.do - available targets:"
	@echo ""
	@echo "  install               pip install the package + install completion"
	@echo "  uninstall             pip uninstall the package + remove completion"
	@echo "  reinstall             uninstall then install"
	@echo "  develop               editable install with dev extras (.[dev])"
	@echo "  install-man           install the man page only"
	@echo "  install-completion    install completions for bash, zsh, and fish"
	@echo "  uninstall-completion  remove all installed completion scripts"
	@echo "  build                 build the sdist and wheel into dist/"
	@echo "  lint                  run pylint over src/plexdo"
	@echo "  dist-check            twine check the built artifacts"
	@echo "  check                 lint + build + dist-check"
	@echo "  clean                 remove build artifacts and caches"
	@echo "  distclean             clean, and remove dist/ as well"
	@echo ""
	@echo "  bash completion:      $(BASH_TARGET)"
	@echo "  zsh completion:       $(ZSH_TARGET)"
	@echo "  fish completion:      $(FISH_TARGET)"
	@echo "  man page:             $(MAN_TARGET)"
	@echo ""
	@echo "Set SHELLS to limit which are installed, e.g. SHELLS=\"bash zsh\""

# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

install: install-completion install-man
	$(PIP) install $(PIP_FLAGS) .
	@echo ""
	@echo "Installed. Try: plex.do --help"
	@echo "Then:          plex.do write-config-example && plex.do login"

develop: install-completion install-man
	$(PIP) install $(PIP_FLAGS) -e ".[dev]"

uninstall: uninstall-completion uninstall-man
	-$(PIP) uninstall -y $(PACKAGE)

reinstall:
	$(MAKE) uninstall
	$(MAKE) install

install-man: $(MAN_PAGE)
	@install -d "$(DESTDIR)$(MAN_DIR)/man1"
	@install -m 644 "$(MAN_PAGE)" "$(MAN_TARGET)"
	@echo "Installed man page       -> $(MAN_TARGET)"

uninstall-man:
	@if [ -f "$(MAN_TARGET)" ]; then \
		rm -f "$(MAN_TARGET)"; \
		echo "Removed $(MAN_TARGET)"; \
	else \
		echo "Not installed: $(MAN_TARGET)"; \
	fi

# Which shells to install completions for; override to limit.
SHELLS ?= bash zsh fish

install-completion: $(addprefix install-completion-,$(SHELLS))

install-completion-bash: $(BASH_COMPLETION)
	@install -d "$(DESTDIR)$(COMPLETION_DIR)"
	@install -m 644 "$(BASH_COMPLETION)" "$(BASH_TARGET)"
	@echo "Installed bash completion -> $(BASH_TARGET)"

install-completion-zsh: $(ZSH_COMPLETION)
	@install -d "$(DESTDIR)$(ZSH_COMPLETION_DIR)"
	@install -m 644 "$(ZSH_COMPLETION)" "$(ZSH_TARGET)"
	@echo "Installed zsh completion  -> $(ZSH_TARGET)"
	@echo "  (ensure $(ZSH_COMPLETION_DIR) is in \$$fpath, then run: compinit)"

install-completion-fish: $(FISH_COMPLETION)
	@install -d "$(DESTDIR)$(FISH_COMPLETION_DIR)"
	@install -m 644 "$(FISH_COMPLETION)" "$(FISH_TARGET)"
	@echo "Installed fish completion -> $(FISH_TARGET)"

# Only ever removes the exact files this Makefile installs; never a directory.
uninstall-completion:
	@for target in "$(BASH_TARGET)" "$(ZSH_TARGET)" "$(FISH_TARGET)"; do \
		if [ -f "$$target" ]; then \
			rm -f "$$target"; \
			echo "Removed $$target"; \
		else \
			echo "Not installed: $$target"; \
		fi; \
	done

# ---------------------------------------------------------------------------
# Build / quality
# ---------------------------------------------------------------------------

build: clean
	$(PYTHON) -m build

lint:
	$(PYTHON) -m pylint src/$(PACKAGE)

dist-check:
	$(PYTHON) -m twine check dist/*

# The version appears in three places; drift is silent otherwise.
check-version:
	@v=$$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/$(PACKAGE)/__init__.py); \
	p=$$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1); \
	m=$$(sed -n 's/^\.TH .* "plexdo \([^"]*\)".*/\1/p' $(MAN_PAGE)); \
	if [ "$$v" = "$$p" ] && [ "$$v" = "$$m" ]; then \
		echo "version $$v consistent across __init__.py, pyproject.toml, and the man page"; \
	else \
		echo "version mismatch: __init__=$$v pyproject=$$p man=$$m" >&2; exit 1; \
	fi

check: check-version lint build dist-check
	@echo ""
	@echo "All checks passed."

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean:
	rm -rf build/ src/*.egg-info/ .pytest_cache/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete

distclean: clean
	rm -rf dist/
