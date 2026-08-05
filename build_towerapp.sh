#!/bin/bash
# Builds "Tower.app" -- a native macOS bundle that opens the Tower in its own
# window, from the Dock, with no terminal and no port to remember (issue #27).
#
#   ./build_towerapp.sh            -> builds into ./dist/
#   ./build_towerapp.sh --install  -> also copies to /Applications
#
# Like finance-tracker's build_macapp.sh this is a *wrapper* bundle, not a
# frozen binary: it launches bin/tower from this repo, so the app never serves
# a stale copy of the screen sealed in at build time. Unlike that one it ships a
# compiled window shim (tools/tower_window/towerwin.swift), because the Tower is
# deliberately stdlib-Python with no dependencies and pywebview is not
# installed -- a ~200-line AppKit shim adds a window without adding a
# dependency. The Swift source is committed; the binary never is, same
# compile-from-source philosophy as finance-tracker's docr.swift.
#
# What the bundle guarantees, and where each guarantee actually lives:
#
#   one copy      towerwin.swift checks NSRunningApplication for its own bundle
#                 id at startup and activates the existing window instead of
#                 starting a second server.
#   clean quit    the shim spawns bin/tower as its CHILD and kills it in
#                 applicationWillTerminate, so there is no path where the
#                 window closes and the server survives.
#   loopback      bin/tower binds 127.0.0.1 unconditionally and has no host
#                 flag; the shim passes only --port. The wrapper cannot widen
#                 the bind, by construction rather than by policy.
#   its own icon  assets/icon-tower.svg, reserved for this app. Rasterised here
#                 by sips (macOS 26 reads SVG directly), so no PNG is committed
#                 and no third-party renderer is needed.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Tower"
BUNDLE_ID="local.commonrules.tower"
DIST="$REPO/dist"
APP="$DIST/$APP_NAME.app"

if ! PYTHON_BIN="$(command -v python3)"; then
  echo "error: python3 not found on PATH -- bin/tower needs it at launch." >&2
  exit 1
fi
if ! command -v swiftc >/dev/null 2>&1; then
  echo "error: swiftc not found -- the window shim is compiled from source at" \
       "build time. Install the Xcode command line tools and retry." >&2
  exit 1
fi

# --- --install is main-checkout-only ---------------------------------------
# The bundle is a wrapper: it cd's to $REPO and runs bin/tower from there. A
# worktree is deleted when its branch merges, so installing from one puts a
# permanently broken app in /Applications that fails at launch with "bin/tower
# not found" -- exactly the trap finance-tracker's build_macapp.sh refuses for
# its own test builds. Checked before any build work so a refusal wastes
# nothing, and a plain build from a worktree (the normal way to try a
# packaging change) is unaffected.
if [[ "${1:-}" == "--install" && "$REPO" == *"/.worktrees/"* ]]; then
  echo "error: --install refused -- this is a worktree:" >&2
  echo "         $REPO" >&2
  echo "       The bundle runs bin/tower from the repo it was built in, and a" >&2
  echo "       worktree disappears when its branch merges. Build from the main" >&2
  echo "       checkout on main, then --install from there." >&2
  exit 1
fi

echo "Building $APP_NAME.app"
echo "  repo:   $REPO"
echo "  python: $PYTHON_BIN"

# Every prior bundle goes first, so dist/ never holds two things both claiming
# to be current. Scoped to dist/ -- never touches /Applications.
mkdir -p "$DIST"
find "$DIST" -maxdepth 1 -name "$APP_NAME.app" -exec rm -rf {} + 2>/dev/null || true

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# --- icon: SVG -> PNG -> .icns, entirely with macOS's own tools ------------
SRC_ICON="$REPO/assets/icon-tower.svg"
[[ -f "$SRC_ICON" ]] || { echo "error: missing $SRC_ICON" >&2; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
sips -s format png "$SRC_ICON" --out "$TMP/icon-1024.png" >/dev/null 2>&1 \
  || { echo "error: sips could not rasterise $SRC_ICON" >&2; exit 1; }
ICONSET="$TMP/icon.iconset"
mkdir -p "$ICONSET"
for size in 16 32 64 128 256 512; do
  sips -z $size $size "$TMP/icon-1024.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1
  double=$((size * 2))
  sips -z $double $double "$TMP/icon-1024.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null 2>&1
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/icon.icns"
echo "  icon:   $(basename "$SRC_ICON") -> icon.icns"

# --- the window shim -------------------------------------------------------
echo "  swift:  compiling towerwin"
swiftc -O "$REPO/tools/tower_window/towerwin.swift" -o "$APP/Contents/MacOS/tower"
chmod +x "$APP/Contents/MacOS/tower"

# Paths the shim reads at launch. Written as resources rather than compiled in,
# so a built bundle can be inspected to see which checkout it drives.
printf '%s' "$REPO" > "$APP/Contents/Resources/repo_path"
printf '%s' "$PYTHON_BIN" > "$APP/Contents/Resources/python_path"

# --- Info.plist ------------------------------------------------------------
# LSUIElement is absent on purpose: this app has a real window and belongs in
# the Dock and Cmd-Tab, which is the whole point of issue #27.
#
# NSAppTransportSecurity allows local networking only. The window loads
# http://127.0.0.1:<port>; ATS would otherwise block plain HTTP, and the fix
# must not be NSAllowsArbitraryLoads -- that would permit any HTTP anywhere,
# which is a far wider hole than the one loopback needs.
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>              <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>       <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>        <string>$BUNDLE_ID</string>
  <key>CFBundleVersion</key>           <string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key>       <string>APPL</string>
  <key>CFBundleExecutable</key>        <string>tower</string>
  <key>CFBundleIconFile</key>          <string>icon</string>
  <key>NSHighResolutionCapable</key>   <true/>
  <key>LSMinimumSystemVersion</key>    <string>13.0</string>
  <key>NSAppTransportSecurity</key>
  <dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST

touch "$APP"   # nudge Finder/Dock to pick up the new icon
echo "Built: $APP"

if [[ "${1:-}" == "--install" ]]; then
  rm -rf "/Applications/$APP_NAME.app"
  cp -R "$APP" "/Applications/"
  echo "Installed: /Applications/$APP_NAME.app"
  # Two bundles carrying one CFBundleIdentifier is one identity with two
  # bodies, and which one opens is undefined -- the condition bin/appcheck
  # exists to catch. The staged copy goes once the install has succeeded.
  rm -rf "$APP"
  echo "Removed the staged copy at $APP -- one bundle, one identity."
fi
