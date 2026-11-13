#!/bin/sh
# Install the 64 KB-aligned rebuilt .deb files from a directory over the stock packages and hold them.
#
# Usage: install-aligned-debs.sh DIR
#
# Only packages that are installed in this image are considered. The installed stock source
# version must equal the rebuilt version minus the +octN suffix; otherwise the script fails,
# so a stale or mismatched rebuild never ships silently.
set -eu

dir="${1:?usage: install-aligned-debs.sh DIR}"
list=""
names=""

for deb in "$dir"/*.deb; do
    [ -e "$deb" ] || continue
    name=$(dpkg-deb -f "$deb" Package)
    stock=$(dpkg-query -W -f='${source:Version}' "$name" 2>/dev/null || true)
    [ -n "$stock" ] || continue
    want=$(dpkg-deb -f "$deb" Version | sed 's/+oct[0-9]*$//')
    if [ "$stock" != "$want" ]; then
        echo "ERROR: $name: installed source version $stock differs from rebuilt $want; bump the base image digest or rebuild the aligned-debs stage" >&2
        exit 1
    fi
    list="$list $deb"
    names="$names $name"
done

echo "Installing aligned packages:$names"
if [ -n "$list" ]; then
    # shellcheck disable=SC2086
    dpkg -i --force-confold $list
    # shellcheck disable=SC2086
    apt-mark hold $names
fi
