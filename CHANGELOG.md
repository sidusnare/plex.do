# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.6] - 2026-08-14

### Added
- PowerShell completion (`completions/plexdo.ps1`), covering the same values
  as the other shells. It uses no external interpreter, reading the cache with
  `ConvertFrom-Json`, and shows the matching title as a tooltip beside each ID.
  Install with `make install-completion SHELLS="bash zsh fish powershell"`,
  then dot-source it from your profile.

## [1.1.5] - 2026-08-14

### Added
- `cache_dir` in the `[plex]` section relocates the completion cache. The
  platform default appears commented out in the generated config template, and
  all three shell completions read the setting so a custom location does not
  silently break tab completion.

## [1.1.4] - 2026-08-14

### Changed
- Native Windows defaults: the configuration file is now
  `%LOCALAPPDATA%\PlexDo\plexdo.ini`, the completion cache
  `%LOCALAPPDATA%\PlexDo\Cache`, and `token_path` defaults to
  `%TEMP%\plexdo.token`. Linux and macOS are unchanged.
- The config template and its unresolved-variable warning follow the platform,
  accepting and reporting `%VAR%` on Windows as well as `$VAR`.
- All three shell completions read the Windows cache location when
  `LOCALAPPDATA` is set, so completion keeps working under Git Bash.

## [1.1.3] - 2026-08-14

### Added
- Declared support for Python 3.14, and added it to the CI matrix. The suite,
  the CLI, and the build were verified against CPython 3.14.4.

### Fixed
- Suppressed a `no-value-for-parameter` false positive that newer astroid
  raises for `ctypes.c_int()`, so pylint stays at 10.00/10 on 3.14.

## [1.1.2] - 2026-08-14

### Changed
- Attribution set to SidusNare in the package metadata, the GPL notices, and
  the manual page, replacing the "plexdo contributors" placeholder.

## [1.1.1] - 2026-08-14

### Added
- Test suite (126 tests) covering output formats, table alignment and encoding
  fallback, identifier resolution, playlist guards, watched-state selection,
  path rewriting, the token store, config handling, and the command registry.
- `py.typed` marker, so the package's complete type annotations are visible to
  downstream users (PEP 561).
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.gitattributes`.
- Continuous integration across Python 3.11-3.13.
- `make test`, wired into `make check`.
- AUTHORS section in the manual page.

## [1.1.0] - 2026-08-14

### Changed
- **Renamed the project from `plex.do` to `plexdo` throughout.** The console
  script, man page, completion files, configuration file, and cache directory
  all use the new name.
  - The configuration file moves from `~/.local/etc/plex.do.ini` to
    `~/.local/etc/plexdo.ini`. Rename it by hand; nothing reads the old path.
  - The completion cache moves to `~/.cache/plexdo` and regenerates itself.
- The second console script (`plex.do`) and the `plex_do` completion alias are
  gone; there is one command, `plexdo`.

## [1.0.15] - 2026-08-14

### Added
- Project homepage and issue tracker URLs in the package metadata, README, and
  manual page.

### Changed
- Source, completions, manual page, and build files are plain ASCII.
- `check-assets` verifies the packaged copies of the completions and manual
  page match their sources, and that no source file contains non-ASCII.

## [1.0.14] and earlier

Iterative development: the single-file script became a package, gaining
multi-user token handling, watched-state synchronisation, a status report,
photo galleries, YAML/CSV/CLIXML output, shell completions for bash, zsh, and
fish, a manual page, and packaging for PyPI. See the commit history.

[1.1.6]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.6
[1.1.5]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.5
[1.1.4]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.4
[1.1.3]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.3
[1.1.2]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.2
[1.1.1]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.1
[1.1.0]: https://github.com/sidusnare/plexdo/releases/tag/v1.1.0
[1.0.15]: https://github.com/sidusnare/plexdo/releases/tag/v1.0.15
