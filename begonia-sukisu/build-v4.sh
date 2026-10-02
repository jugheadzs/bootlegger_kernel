#!/usr/bin/env bash
set -euo pipefail

ROOT="$PWD"
KERNEL="$ROOT/kernel"
OUT="$ROOT/out"
TC="$ROOT/toolchains"

sudo apt-get update
sudo apt-get install -y bc bison build-essential cpio curl flex git libelf-dev libssl-dev python3 rsync unzip wget xz-utils zip gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi

rm -rf "$KERNEL" "$OUT" "$TC" "$ROOT/artifacts"
mkdir -p "$TC/clang"

git clone --depth=1 --branch begonia-q-oss https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git "$KERNEL"

curl -fL --retry 10 --retry-all-errors --retry-delay 2 \
  "https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+archive/refs/heads/android10-release/clang-r353983c.tar.gz" \
  | tar -xz -C "$TC/clang"

export PATH="$TC/clang/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export CC=clang
export CLANG_TRIPLE=aarch64-linux-gnu-
export CROSS_COMPILE=aarch64-linux-gnu-
export CROSS_COMPILE_ARM32=arm-linux-gnueabi-
export KBUILD_BUILD_USER=jugheadzs
export KBUILD_BUILD_HOST=github-actions

cd "$KERNEL"

echo "== source/toolchain =="
git rev-parse HEAD
head -n 6 Makefile
clang --version | head -n 2
${CROSS_COMPILE}ld --version | head -n 1

# Old 4.14 DTC fix for modern host GCC (-fno-common).
sed -i 's/^YYLTYPE yylloc;$/extern YYLTYPE yylloc;/' scripts/dtc/dtc-lexer.l
sed -i 's/^YYLTYPE yylloc;$/extern YYLTYPE yylloc;/' scripts/dtc/dtc-lexer.lex.c_shipped

git clone --depth=1 --branch v3.2.0 https://github.com/SukiSU-Ultra/SukiSU-Ultra.git KernelSU
printf 'SukiSU tag commit: '; git -C KernelSU rev-parse HEAD
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
    p.write_text(s[:idx] + line + '\n\n' + s[idx:])
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
./scripts/config --file "$OUT/.config" -d LOCALVERSION_AUTO --set-str LOCALVERSION "-sukisu-miui12-test4"
make O="$OUT" olddefconfig

echo "== final KSU config =="
grep -E 'CONFIG_(KSU|KPM|KPROBES|LOCALVERSION|OVERLAY_FS)' "$OUT/.config" || true

# Deliberately build only Image.gz. The stock boot image already supplies the
# exact begonia appended DTB and header-v2 DTB; rebuilding Xiaomi's missing
# proprietary cust.dtsi overlay is unnecessary and less safe for this test.
make -j"$(nproc)" O="$OUT" \
  ARCH=arm64 CC=clang CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE="$CROSS_COMPILE" CROSS_COMPILE_ARM32="$CROSS_COMPILE_ARM32" \
  Image.gz

mkdir -p "$ROOT/artifacts"
cp -v "$OUT/arch/arm64/boot/Image.gz" "$ROOT/artifacts/"
cp "$OUT/.config" "$ROOT/artifacts/kernel.config"
file "$ROOT/artifacts/Image.gz"
sha256sum "$ROOT/artifacts"/* | tee "$ROOT/artifacts/SHA256SUMS.txt"
