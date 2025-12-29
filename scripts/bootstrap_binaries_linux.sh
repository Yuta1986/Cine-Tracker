#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TP="${ROOT}/third_party"

mkdir -p "${TP}/bin" "${TP}/src" "${TP}/debs" "${TP}/sysroot"

echo "[1/3] Installing static ffmpeg into third_party/bin ..."
FFMPEG_TAR="${TP}/src/ffmpeg-static.tar.xz"
if [[ ! -f "${FFMPEG_TAR}" ]]; then
  curl -L --retry 3 -o "${FFMPEG_TAR}" \
    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
fi
tar -xf "${FFMPEG_TAR}" -C "${TP}"
FFMPEG_DIR="$(ls -1d "${TP}"/ffmpeg-*-amd64-static | head -n 1)"
ln -sf "../$(basename "${FFMPEG_DIR}")/ffmpeg" "${TP}/bin/ffmpeg"
ln -sf "../$(basename "${FFMPEG_DIR}")/ffprobe" "${TP}/bin/ffprobe"

echo "[2/3] Installing COLMAP (Ubuntu deb extract, no sudo) into third_party/bin ..."
cd "${TP}/debs"
apt-get download colmap >/dev/null
apt-get download \
  libboost-filesystem1.83.0 libboost-program-options1.83.0 \
  libceres4t64 libfreeimage3 libglew2.2 libgoogle-glog0v6t64 libmetis5 libopengl0 \
  libqt5core5t64 libqt5gui5t64 libqt5widgets5t64 >/dev/null
apt-get download \
  libcholmod5 libspqr4 libsuitesparseconfig7 libamd3 libcamd3 libccolamd3 libcolamd3 \
  liblapack3 libblas3 libgfortran5 \
  libgflags2.2 \
  libjxr0t64 libopenjp2-7 libraw23t64 libwebpmux3 libopenexr-3-1-30 libimath-3-1-29t64 \
  libmd4c0 libdouble-conversion3 libpcre2-16-0 >/dev/null
cd "${ROOT}"

for deb in "${TP}/debs/"*.deb; do
  dpkg-deb -x "${deb}" "${TP}/sysroot"
done

cat >"${TP}/bin/colmap" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSROOT="${ROOT}/sysroot"
export LD_LIBRARY_PATH="${SYSROOT}/usr/lib/x86_64-linux-gnu:${SYSROOT}/usr/lib/x86_64-linux-gnu/lapack:${SYSROOT}/usr/lib/x86_64-linux-gnu/blas:${SYSROOT}/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
QT_PLUGINS="${SYSROOT}/usr/lib/x86_64-linux-gnu/qt5/plugins"
if [[ -d "${QT_PLUGINS}" ]]; then
  export QT_PLUGIN_PATH="${QT_PLUGIN_PATH:-${QT_PLUGINS}}"
  export QT_QPA_PLATFORM_PLUGIN_PATH="${QT_QPA_PLATFORM_PLUGIN_PATH:-${QT_PLUGINS}/platforms}"
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
fi
exec "${SYSROOT}/usr/bin/colmap" "$@"
SH
chmod +x "${TP}/bin/colmap"

echo "[3/3] Done."
echo "Paths:"
echo "  ffmpeg: ${TP}/bin/ffmpeg"
echo "  colmap:  ${TP}/bin/colmap"
echo ""
echo "Tip:"
echo "  export FFMPEG_BIN=\"${TP}/bin/ffmpeg\""
echo "  export COLMAP_BIN=\"${TP}/bin/colmap\""
