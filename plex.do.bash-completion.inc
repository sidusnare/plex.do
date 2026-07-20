#!/usr/bin/env bash
# Bash completion for plex.do — with cached ID / name completion.
#
# Requires: bash 4.0+, python3 (already required by plex.do itself)
#
# Installation:
#   Single session:  source plex.do.bash-completion
#   Permanent:       cp plex.do.bash-completion \
#                      ~/.local/share/bash-completion/completions/plex.do

# ---------------------------------------------------------------------------
# Cache helpers (15-minute TTL, written by the Python script as a side effect
# of running any list-* command — completion triggers background refresh when
# a cache file is stale or absent)
# ---------------------------------------------------------------------------

_PLEXDO_CACHE="${HOME}/.cache/plex.do"
_PLEXDO_TTL=900   # seconds (15 minutes)

# Return 0 if cache file exists and is younger than $_PLEXDO_TTL seconds.
_plexdo_cache_is_fresh() {
    local file="$1"
    [[ -f "$file" ]] || return 1
    local mtime now
    now=$(date +%s)
    # stat syntax differs between Linux (-c) and macOS (-f)
    if ! mtime=$(stat -c %Y "$file" 2>/dev/null); then
        mtime=$(stat -f %m "$file" 2>/dev/null) || return 1
    fi
    (( now - mtime < _PLEXDO_TTL ))
}

# Run a plex.do sub-command in the background so its cache side-effect fires
# without blocking the completion prompt.  All output is suppressed.
_plexdo_bg_refresh() {
    local plexdo="${words[0]}"
    "$plexdo" "$@" >/dev/null 2>&1 &
    disown $! 2>/dev/null || true
}

# Emit one completion candidate per line from a JSON cache file.
#   $1  cache file path
#   $2  JSON key whose value becomes the completion word (e.g. "id", "title")
# Filters to entries whose value starts with $cur; passed as argv to avoid
# shell-quoting pitfalls.
_plexdo_json_candidates() {
    local file="$1" field="$2"
    [[ -f "$file" ]] || return
    python3 - "$cur" "$field" "$file" 2>/dev/null << 'PYEOF'
import json, sys
cur, field, path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    for r in json.load(open(path, encoding="utf-8")):
        v = str(r.get(field, ""))
        if v.startswith(cur):
            print(v)
except Exception:
    pass
PYEOF
}

# ---------------------------------------------------------------------------
# Per-argument completion helpers
# ---------------------------------------------------------------------------

# user_id — "0" (admin) plus IDs from the users cache
_plexdo_complete_user_id() {
    local cache="$_PLEXDO_CACHE/users.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-users
    mapfile -t COMPREPLY < <(
        { echo "0"; _plexdo_json_candidates "$cache" "id"; } \
        | grep -x "$(printf '%q' "${cur}").*" 2>/dev/null \
        | sort -u \
        || compgen -W "0" -- "$cur"
    )
    # Simpler fallback using compgen for the "0" entry and cache entries merged
    local raw_ids
    mapfile -t raw_ids < <( _plexdo_json_candidates "$cache" "id" )
    mapfile -t COMPREPLY < <( compgen -W "0 ${raw_ids[*]}" -- "$cur" )
}

# library_id — IDs from the libraries cache
_plexdo_complete_library_id() {
    local cache="$_PLEXDO_CACHE/libraries.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-libraries
    mapfile -t COMPREPLY < <( _plexdo_json_candidates "$cache" "id" )
}

# rating_key — ratingKeys aggregated from all titles.*.json cache files;
# triggers per-library background refresh for any stale file, and kicks off
# list-titles for each known library if no title cache exists at all.
_plexdo_complete_rating_key() {
    local found=0
    for f in "$_PLEXDO_CACHE"/titles.*.json; do
        [[ -f "$f" ]] || continue
        found=1
        if ! _plexdo_cache_is_fresh "$f"; then
            local lib_id="${f##*/titles.}"
            lib_id="${lib_id%.json}"
            _plexdo_bg_refresh list-titles "$lib_id"
        fi
        mapfile -t -O "${#COMPREPLY[@]}" COMPREPLY < <(
            _plexdo_json_candidates "$f" "ratingKey"
        )
    done
    if (( ! found )); then
        local lib_cache="$_PLEXDO_CACHE/libraries.json"
        if [[ -f "$lib_cache" ]]; then
            local lib_id
            while IFS= read -r lib_id; do
                _plexdo_bg_refresh list-titles "$lib_id"
            done < <( _plexdo_json_candidates "$lib_cache" "id" )
        else
            _plexdo_bg_refresh list-libraries
        fi
    fi
}

# Complete a playlist by title OR ratingKey for a given user_id.
_plexdo_complete_playlist_id_or_name() {
    local user_id="$1"
    local cache="$_PLEXDO_CACHE/playlists.${user_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-playlists "$user_id"
    mapfile -t COMPREPLY < <(
        { _plexdo_json_candidates "$cache" "ratingKey"
          _plexdo_json_candidates "$cache" "title"; } | sort -u
    )
}

# playlist title for a given user_id (string, may contain spaces)
_plexdo_complete_playlist() {
    local user_id="$1"
    local cache="$_PLEXDO_CACHE/playlists.${user_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-playlists "$user_id"
    mapfile -t COMPREPLY < <( _plexdo_json_candidates "$cache" "title" )
}

# ---------------------------------------------------------------------------
# Positional-argument introspection helpers
# ---------------------------------------------------------------------------

_plexdo_commands() {
    echo "list-libraries list-titles list-users list-playlists list-playlist \
list-show show-metadata search build-interleaved build-chronological build-randomize \
copy-playlist-all-users copy-playlist-to-user export-playlist remove-playlist \
append-playlist export-titles write-config-example"
}

_plexdo_global_flags() {
    echo "--json --verbose --debug --dry-run --help"
}

# Find the first non-flag positional word after the program name (= the sub-command).
_plexdo_find_cmd() {
    local i
    for (( i=1; i < cword; i++ )); do
        case "${words[$i]}" in
            --json|--verbose|--debug|--dry-run|--help) ;;
            -*) ;;
            *) echo "${words[$i]}"; return ;;
        esac
    done
}

# Count non-flag positional arguments typed so far after the sub-command.
# --m3u consumes its following PATH token so it doesn't inflate the count.
_plexdo_positional_count() {
    local cmd="$1"
    local found_cmd=0 count=0 skip_next=0 i word
    for (( i=1; i < cword; i++ )); do
        word="${words[$i]}"
        if (( skip_next )); then skip_next=0; continue; fi
        if [[ "$word" == "--m3u" ]]; then skip_next=1; continue; fi
        if [[ "$word" == -* ]]; then continue; fi
        if (( ! found_cmd )); then
            [[ "$word" == "$cmd" ]] && found_cmd=1
            continue
        fi
        (( count++ ))
    done
    echo "$count"
}

# Return the Nth (0-based) non-flag positional argument after the sub-command.
_plexdo_nth_positional() {
    local cmd="$1" n="$2"
    local found_cmd=0 count=0 skip_next=0 i word
    for (( i=1; i < cword; i++ )); do
        word="${words[$i]}"
        if (( skip_next )); then skip_next=0; continue; fi
        if [[ "$word" == "--m3u" ]]; then skip_next=1; continue; fi
        if [[ "$word" == -* ]]; then continue; fi
        if (( ! found_cmd )); then
            [[ "$word" == "$cmd" ]] && found_cmd=1
            continue
        fi
        if (( count == n )); then echo "$word"; return; fi
        (( count++ ))
    done
}

# ---------------------------------------------------------------------------
# Main completion function
# ---------------------------------------------------------------------------

_plexdo_complete() {
    local cur prev words cword
    words=( "${COMP_WORDS[@]}" )
    cword=$COMP_CWORD
    cur="${words[$cword]}"
    prev="${words[$cword-1]}"

    local cmd pos uid
    cmd="$(_plexdo_find_cmd)"

    # --m3u PATH → file path
    if [[ "$prev" == "--m3u" ]]; then
        COMPREPLY=( $(compgen -f -- "$cur") )
        return
    fi

    # Flag completion
    if [[ "$cur" == --* ]]; then
        case "$cmd" in
            list-playlist|list-show|build-interleaved|build-chronological|build-randomize)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --m3u" -- "$cur") ) ;;
            *)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags)" -- "$cur") ) ;;
        esac
        return
    fi

    # No sub-command typed yet
    if [[ -z "$cmd" ]]; then
        COMPREPLY=( $(compgen -W "$(_plexdo_commands)" -- "$cur") )
        return
    fi

    pos="$(_plexdo_positional_count "$cmd")"

    case "$cmd" in

        list-libraries|list-users|write-config-example)
            COMPREPLY=() ;;

        # <library_id>
        list-titles)
            case $pos in
                0) _plexdo_complete_library_id ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id>
        list-playlists)
            case $pos in
                0) _plexdo_complete_user_id ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist|ratingKey> [--m3u]
        list-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <rating_key> [--m3u]
        list-show|show-metadata)
            case $pos in
                0) _plexdo_complete_rating_key ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <name> <ratingKey...> [--m3u]
        build-interleaved|build-chronological)
            case $pos in
                0) COMPREPLY=() ;;
                *) _plexdo_complete_rating_key ;;
            esac ;;

        # <user_id> <source> <dest> [--m3u]
        build-randomize)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <source_user_id> <source_playlist>
        copy-playlist-all-users)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <source_user_id> <source_playlist> <user_id> <dest>
        copy-playlist-to-user)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist "$uid" ;;
                2) _plexdo_complete_user_id ;;
                3) uid="$(_plexdo_nth_positional "$cmd" 2)"
                   _plexdo_complete_playlist "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist>
        remove-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist> <path>
        export-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist "$uid" ;;
                2) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist> <ratingKey...>
        append-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist "$uid" ;;
                *) _plexdo_complete_rating_key ;;
            esac ;;

        # <user_id> <query> [--media-type TYPE] [--library-id ID]
        search)
            if [[ "$prev" == "--media-type" ]]; then
                COMPREPLY=( $(compgen -W "movie show episode track photo album artist" -- "$cur") )
            elif [[ "$prev" == "--library-id" ]]; then
                _plexdo_complete_library_id
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --media-type --library-id" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_user_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <library_id> <path> [--sort alpha|date|random]
        export-titles)
            if [[ "$prev" == "--sort" ]]; then
                COMPREPLY=( $(compgen -W "alpha date random" -- "$cur") )
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --sort" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    1) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        *)
            COMPREPLY=( $(compgen -W "$(_plexdo_commands)" -- "$cur") ) ;;
    esac
}

complete -F _plexdo_complete plex.do
complete -F _plexdo_complete plex_do
