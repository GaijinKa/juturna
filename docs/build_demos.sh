#!/usr/bin/env bash
# Build the juturna-browser demos into a folder of the documentation site.
#
# Usage: docs/build_demos.sh JUTURNA_BROWSER_DIR JUTURNA_NODES_DIR OUT_DIR
# Run from the root of the juturna checkout, which is the library the demos get.
set -euo pipefail

browser=$(realpath "$1")
nodes=$(realpath "$2")
out=$(realpath -m "$3")
juturna=$PWD

kroko=https://github.com/meetecho/juturna-browser/releases/download/demo-assets-kroko-en-2025-08-06
coi=https://cdn.jsdelivr.net/npm/coi-serviceworker@0.1.7/coi-serviceworker.min.js
plugins=(
    examples/video-blur/plugins
    examples/noise-suppression/plugins
    examples/live-translation/plugins
    examples/plugins
)

cd "$browser"
python3 build/vendor.py "${plugins[@]}"
python3 build/build.py --juturna "$juturna" --nodes "$nodes" \
    "${plugins[@]/#/--plugins=}"

mkdir -p vendor/transcriber_kroko_wasm
(
    cd vendor/transcriber_kroko_wasm
    for f in sherpa-onnx-asr.js sherpa-onnx-wasm-main-asr.js \
        sherpa-onnx-wasm-main-asr.wasm sherpa-onnx-wasm-main-asr.data; do
        [ -f "$f" ] || curl -sSfL "$kroko/$f" -o "$f"
    done
    sha256sum -c --quiet <<'EOF'
d51ae8e8b756ee5e53423ffada0c9702973f154f561aca7984fe0b12f4060178  sherpa-onnx-asr.js
416f9c570969b6e869506421931f873f289ab6820a9f1a9adceb48a1daf39c89  sherpa-onnx-wasm-main-asr.js
813b17e10077059307ed471af6a956735a0a93ff81532a578b900a18e3e8496e  sherpa-onnx-wasm-main-asr.wasm
084d3850172fb12e76dba707b62906d79b8916f2d084965e950320247168c557  sherpa-onnx-wasm-main-asr.data
EOF
)

rm -rf "$out"
mkdir -p "$out"
cp -r src examples dist vendor "$out"
# examples/standalone needs its own build (npm package), it is not a demo
rm -rf "$out/examples/standalone"
# the pages read the transformers.js models from Hugging Face, not vendor/
rm -rf "$out"/vendor/*/models
# the demos link back to their index: the demos page of the documentation
echo '<meta http-equiv="refresh" content="0; url=../browser/demos.html">' \
    >"$out/index.html"

curl -sSfL "$coi" -o "$out/coi-serviceworker.js"
echo "03d2f35be3249f5eeb4e214c5daf2be8067e2b24630aaef26a1247b723f2d05d  $out/coi-serviceworker.js" |
    sha256sum -c --quiet

# GitHub Pages cannot send COOP/COEP: the service worker adds them, and each
# page loads it from the root of the demos
find "$out/examples" -name '*.html' | while read -r page; do
    root=$(realpath --relative-to="$(dirname "$page")" "$out")
    sed -i "0,/<head>/s||<head><script src=\"$root/coi-serviceworker.js\"></script>|" "$page"
done
# a page without a bare <head> would ship without isolation
! grep -rL --include='*.html' coi-serviceworker "$out/examples" | grep .
