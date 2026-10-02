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

# Linux 4.14 DTC fix for modern host GCC (-fno-common).
sed -i 's/^YYLTYPE yylloc;$/extern YYLTYPE yylloc;/' scripts/dtc/dtc-lexer.l
sed -i 's/^YYLTYPE yylloc;$/extern YYLTYPE yylloc;/' scripts/dtc/dtc-lexer.lex.c_shipped

# Missing FocalTech include placeholders from Xiaomi's public source.
mkdir -p drivers/input/touchscreen/fts8719/include/firmware
: > drivers/input/touchscreen/fts8719/include/firmware/focal_g7_01.i
: > drivers/input/touchscreen/fts8719/include/firmware/fw_sample.i

git clone --depth=1 --branch v3.2.0 https://github.com/SukiSU-Ultra/SukiSU-Ultra.git KernelSU
printf 'SukiSU tag commit: '; git -C KernelSU rev-parse HEAD

python3 - <<'PY'
from pathlib import Path

# Linux 4.14 has no MODULE_IMPORT_NS.
p=Path('KernelSU/kernel/ksu.c')
s=p.read_text()
needle='MODULE_IMPORT_NS(VFS_internal_I_am_really_a_filesystem_and_am_NOT_a_driver);'
if needle in s and '#ifdef MODULE_IMPORT_NS\n' + needle not in s:
    s=s.replace(needle, '#ifdef MODULE_IMPORT_NS\n' + needle + '\n#endif', 1)
    p.write_text(s)
print('[ok] MODULE_IMPORT_NS compatibility')

# proc_ops was introduced in newer kernels. Linux 4.14 proc_create() expects
# struct file_operations and the classic field names.
p=Path('KernelSU/kernel/throne_comm.c')
s=p.read_text()
old='''static const struct proc_ops uid_scanner_proc_ops = {\n    .proc_open = uid_scanner_open,\n    .proc_read = seq_read,\n\t.proc_write = uid_scanner_write,\n    .proc_lseek = seq_lseek,\n    .proc_release = single_release,\n};'''
new='''#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)\nstatic const struct proc_ops uid_scanner_proc_ops = {\n    .proc_open = uid_scanner_open,\n    .proc_read = seq_read,\n    .proc_write = uid_scanner_write,\n    .proc_lseek = seq_lseek,\n    .proc_release = single_release,\n};\n#else\nstatic const struct file_operations uid_scanner_proc_ops = {\n    .open = uid_scanner_open,\n    .read = seq_read,\n    .write = uid_scanner_write,\n    .llseek = seq_lseek,\n    .release = single_release,\n};\n#endif'''
if old not in s:
    raise SystemExit('[error] throne_comm proc_ops anchor not found')
s=s.replace(old,new,1)
p.write_text(s)
print('[ok] throne_comm proc_ops -> file_operations compatibility')

# Xiaomi's 4.14 SELinux predates struct selinux_state. It exposes the legacy
# globals selinux_enforcing/selinux_enabled, and objsec.h already provides
# current_sid(). Adapt SukiSU without changing SELinux policy behavior.
p=Path('KernelSU/kernel/selinux/selinux.c')
s=p.read_text()
anchor='#include "../klog.h" // IWYU pragma: keep\n'
compat='''#include "../klog.h" // IWYU pragma: keep\n\n#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 17, 0)\nextern int selinux_enforcing;\nextern int selinux_enabled;\n#define KSU_COMPAT_HAS_CURRENT_SID\n#endif\n'''
if anchor not in s:
    raise SystemExit('[error] selinux include anchor not found')
s=s.replace(anchor, compat, 1)
old_set='''void setenforce(bool enforce)\n{\n#ifdef CONFIG_SECURITY_SELINUX_DEVELOP\n\tselinux_state.enforcing = enforce;\n#endif\n}\n'''
new_set='''void setenforce(bool enforce)\n{\n#ifdef CONFIG_SECURITY_SELINUX_DEVELOP\n#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 17, 0)\n\tselinux_enforcing = enforce;\n#else\n\tselinux_state.enforcing = enforce;\n#endif\n#endif\n}\n'''
if old_set not in s:
    raise SystemExit('[error] setenforce anchor not found')
s=s.replace(old_set,new_set,1)
old_get='''bool getenforce()\n{\n#ifdef CONFIG_SECURITY_SELINUX_DISABLE\n\tif (selinux_state.disabled) {\n\t\treturn false;\n\t}\n#endif\n\n#ifdef CONFIG_SECURITY_SELINUX_DEVELOP\n\treturn selinux_state.enforcing;\n#else\n\treturn true;\n#endif\n}\n'''
new_get='''bool getenforce()\n{\n#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 17, 0)\n\tif (!selinux_enabled) {\n\t\treturn false;\n\t}\n#ifdef CONFIG_SECURITY_SELINUX_DEVELOP\n\treturn selinux_enforcing;\n#else\n\treturn true;\n#endif\n#else\n#ifdef CONFIG_SECURITY_SELINUX_DISABLE\n\tif (selinux_state.disabled) {\n\t\treturn false;\n\t}\n#endif\n#ifdef CONFIG_SECURITY_SELINUX_DEVELOP\n\treturn selinux_state.enforcing;\n#else\n\treturn true;\n#endif\n#endif\n}\n'''
if old_get not in s:
    raise SystemExit('[error] getenforce anchor not found')
s=s.replace(old_get,new_get,1)
p.write_text(s)
print('[ok] legacy SELinux state/current_sid compatibility')
PY

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
./scripts/config --file "$OUT/.config" -d LOCALVERSION_AUTO --set-str LOCALVERSION "-sukisu-miui12-test8"
make O="$OUT" olddefconfig

echo "== final KSU config =="
grep -E 'CONFIG_(KSU|KPM|KPROBES|LOCALVERSION|OVERLAY_FS)' "$OUT/.config" || true

make -j"$(nproc)" O="$OUT" \
  ARCH=arm64 CC=clang CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE="$CROSS_COMPILE" CROSS_COMPILE_ARM32="$CROSS_COMPILE_ARM32" \
  Image.gz

mkdir -p "$ROOT/artifacts"
cp -v "$OUT/arch/arm64/boot/Image.gz" "$ROOT/artifacts/"
cp "$OUT/.config" "$ROOT/artifacts/kernel.config"
file "$ROOT/artifacts/Image.gz"
sha256sum "$ROOT/artifacts"/* | tee "$ROOT/artifacts/SHA256SUMS.txt"
