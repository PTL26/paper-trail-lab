#!/bin/sh
# Assemble the static site: the landing page at the root, the T1 explorer under t1-explorer/.
#   sh tools/build_site.sh [output dir, default _site]
set -eu
cd "$(dirname "$0")/.."
out="${1:-_site}"
rm -rf "$out"
mkdir -p "$out/t1-explorer"
cp site/index.html "$out/index.html"
cp t1-explorer/index.html "$out/t1-explorer/index.html"
touch "$out/.nojekyll"
echo "site assembled in $out"
