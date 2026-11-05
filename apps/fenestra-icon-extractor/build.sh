#!/usr/bin/env bash
# Builds Fenestra Icon Extractor on Linux:
#   out/portable/FenestraIconExtractor.exe   self-contained single-file win-x64 app
#   out/FenestraIconExtractorSetup.exe       Inno Setup installer (ISCC run under Wine)
# Needs: curl, wine. The .NET 8 SDK and Inno Setup 6 are fetched into ~/.dotnet and
# ~/.cache/fenestra-build on first run. Set NO_INSTALLER=1 to skip the installer.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CACHE="${FENESTRA_BUILD_CACHE:-$HOME/.cache/fenestra-build}"
INNO_VERSION=6.7.4
INNO_SHA256=a549929319f9120716677c685535ca4671e4b937b5fdc87e2585f32d8eb30e8c
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
mkdir -p "$CACHE/dl"

# --- .NET 8 SDK -------------------------------------------------------------
DOTNET="$(command -v dotnet || true)"
if [ -z "$DOTNET" ] || ! "$DOTNET" --list-sdks | grep -q '^8\.'; then
    DOTNET="$HOME/.dotnet/dotnet"
    if [ ! -x "$DOTNET" ] || ! "$DOTNET" --list-sdks | grep -q '^8\.'; then
        curl -fsSLo "$CACHE/dl/dotnet-install.sh" https://dot.net/v1/dotnet-install.sh
        bash "$CACHE/dl/dotnet-install.sh" --channel 8.0 --install-dir "$HOME/.dotnet"
    fi
fi

# --- app ---------------------------------------------------------------------
rm -rf "$HERE/out"
"$DOTNET" publish "$HERE/FenestraIconExtractor.csproj" -c Release -o "$HERE/out/portable" -nologo
ls -l "$HERE/out/portable/FenestraIconExtractor.exe"
[ "${NO_INSTALLER:-0}" = 1 ] && exit 0

# --- installer (Inno Setup under Wine) --------------------------------------
export WINEPREFIX="$CACHE/wine-inno" WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
ISCC="$WINEPREFIX/drive_c/InnoSetup6/ISCC.exe"
if [ ! -f "$ISCC" ]; then
    setup="$CACHE/dl/innosetup-$INNO_VERSION.exe"
    [ -f "$setup" ] || curl -fsSLo "$setup" "https://github.com/jrsoftware/issrc/releases/download/is-${INNO_VERSION//./_}/innosetup-$INNO_VERSION.exe"
    echo "$INNO_SHA256  $setup" | sha256sum -c -
    wine "$setup" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /DIR='C:\InnoSetup6'
fi
wine "$ISCC" /Q "/DSourceExe=$(winepath -w "$HERE/out/portable/FenestraIconExtractor.exe")" \
    "/DOutputDir=$(winepath -w "$HERE/out")" "$(winepath -w "$HERE/installer/FenestraIconExtractor.iss")"
ls -l "$HERE/out/FenestraIconExtractorSetup.exe"
(cd "$HERE/out" && sha256sum FenestraIconExtractorSetup.exe portable/FenestraIconExtractor.exe > SHA256SUMS)
