#!/usr/bin/env bash
set -eu

plugin_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output="${1:-$plugin_dir/sp-ha-sync.zip}"

rm -f "$output"
cd "$plugin_dir"
zip -q -j "$output" manifest.json plugin.js index.html
printf 'Created %s\n' "$output"
sha256sum "$output"
