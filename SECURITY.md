# Security

## Reporting a vulnerability

Please report security issues through
[GitHub's private vulnerability reporting](https://github.com/sidusnare/plexdo/security/advisories/new)
rather than a public issue.

## What this program handles

`plexdo` stores Plex authentication tokens, and optionally Plex account
passwords, on disk. Both files are created with mode `0600` and are checked at
startup; a warning is printed if either is readable by group or other.

- **Configuration** (`~/.local/etc/plexdo.ini`) may hold plaintext passwords
  for `plexdo login` and for per-user sections. It is only needed if you want
  automatic re-authentication; otherwise omit the credentials and log in
  interactively.
- **Token store** (`token_path`, by default `$XDG_RUNTIME_DIR/.plex.token`)
  holds a JSON object of username to Plex token. A Plex token grants access to
  that account's libraries, so treat it as a password.

## Known limitations

- `--password` on the command line is recorded in shell history and is briefly
  visible to `ps`. The value is scrubbed from the process title as early as
  possible and a warning is printed, but the exposure before that point cannot
  be eliminated. Prefer the configuration file or the interactive prompt.
- On Windows the scrubbing has no effect, because the technique that rewrites
  the process title has no Windows equivalent. File permissions are also not
  enforced there, as `chmod` cannot restrict access; place the token file
  somewhere only your account can read.
- `XDG_RUNTIME_DIR` is a user-private tmpfs on most Linux systems, which suits
  a secret, but it is cleared at logout. Pointing `token_path` somewhere
  persistent trades that protection for convenience.
