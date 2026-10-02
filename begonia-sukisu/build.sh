#!/usr/bin/env bash
set -euo pipefail

ROOT="$PWD"
KERNEL="$ROOT/kernel"
OUT="$ROOT/out"
TC="$ROOT/toolchains"

sudo apt-get update
sudo apt-get install -y bc bison build-essential cpio curl flex git libelf-dev libssl-dev python3 rsync unzip wget xz-utils zip gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi

rm -rf "$KERNEL" "$OUT" "$TC"
mkdir -p "$TC"

git clone --depth=1 --branch begonia-q-oss https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git "$KERNEL"

mkdir -p "$TC/clang"
curl -fL --retry 3 "https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+archive/refs/heads/android10-release/clang-r353983c.tar.gz" | tar -xz -C "$TC/clang"

mkdir -p "$TC/gcc64" "$TC/gcc32"
curl -fL --retry 3 "https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9/+archive/refs/heads/android10-release.tar.gz" | tar -xz -C "$TC/gcc64"
curl -fL --retry 3 "https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9/+archive/refs/heads/android10-release.tar.gz" | tar -xz -C "$TC/gcc32"

export PATH="$TC/clang/bin:$TC/gcc64/bin:$TC/gcc32/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export CC=clang
export CLANG_TRIPLE=aarch64-linux-gnu-
export CROSS_COMPILE="$TC/gcc64/bin/aarch64-linux-android-"
export CROSS_COMPILE_ARM32="$TC/gcc32/bin/arm-linux-androideabi-"
export KBUILD_BUILD_USER=jugheadzs
export KBUILD_BUILD_HOST=github-actions

cd "$KERNEL"

echo "== source =="
git rev-parse HEAD
head -n 6 Makefile
clang --version | head -n 2

git clone --depth=1 --branch v3.2.0 https://github.com/SukiSU-Ultra/SukiSU-Ultra.git KernelSU
ln -s ../KernelSU/kernel drivers/kernelsu
printf '\nobj-$(CONFIG_KSU) += kernelsu/\n' >> drivers/Makefile
python3 - <<'PY'
from pathlib import Path
p=Path('drivers/Kconfig')
s=p.read_text()
line='source "drivers/kernelsu/Kconfig"'
if line not in s:
    idx=s.rfind('endmenu')
    if idx < 0: raise SystemExit('drivers/Kconfig: endmenu not found')
    s=s[:idx] + line + '\n\n' + s[idx:]
    p.write_text(s)
PY

cp "$ROOT/patch_sukisu_manual.py" .
python3 patch_sukisu_manual.py

mkdir -p "$OUT"
make O="$OUT" ARCH=arm64 begonia_user_defconfig

./scripts/config --file "$OUT/.config" \
  -e KSU \
  -e KSU_MANUAL_HOOK \
  -d KSU_KPROBES_HOOK \
  -d KSU_TRACEPOINT_HOOK \
  -d KPM \
  -d KPROBES \
  -d KPROBE_EVENTS

./scripts/config --file "$OUT/.config" -d LOCALVERSION_AUTO --set-str LOCALVERSION "-sukisu-miui12-test1"

make O="$OUT" olddefconfig

echo "== final KSU config =="
grep -E 'CONFIG_(KSU|KPM|KPROBES|LOCALVERSION|OVERLAY_FS)' "$OUT/.config" || true

make -j"$(nproc)" O="$OUT" \
  ARCH=arm64 \
  CC=clang \
  CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE="$CROSS_COMPILE" \
  CROSS_COMPILE_ARM32="$CROSS_COMPILE_ARM32"

mkdir -p "$ROOT/artifacts"
for f in \
  "$OUT/arch/arm64/boot/Image" \
  "$OUT/arch/arm64/boot/Image.gz" \
  "$OUT/arch/arm64/boot/Image.gz-dtb" \
  "$OUT/arch/arm64/boot/dtbo.img"; do
  if [ -f "$f" ]; then cp -v "$f" "$ROOT/artifacts/"; fi
done
cp "$OUT/.config" "$ROOT/artifacts/kernel.config"

if [ ! -f "$ROOT/artifacts/Image.gz-dtb" ]; then
  echo "ERROR: Image.gz-dtb was not generated"
  find "$OUT/arch/arm64/boot" -maxdepth 3 -type f -printf '%p %s bytes\n' | sort | tail -n 100
  exit 2
fi
sha256sum "$ROOT/artifacts"/* | tee "$ROOT/artifacts/SHA256SUMS.txt"
