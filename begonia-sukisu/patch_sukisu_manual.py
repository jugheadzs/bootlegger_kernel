from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text()
    if new in s:
        print(f'[skip] {label} already applied')
        return
    if old not in s:
        raise SystemExit(f'[error] anchor not found for {label} in {path}')
    p.write_text(s.replace(old, new, 1))
    print(f'[ok] {label}')

# fs/exec.c
replace_once(
    'fs/exec.c',
    '/*\n * sys_execve() executes a new program.\n */\nstatic int do_execveat_common(int fd, struct filename *filename,',
    '''#ifdef CONFIG_KSU\nextern bool ksu_execveat_hook __read_mostly;\nextern int ksu_handle_execveat(int *fd, struct filename **filename_ptr, void *argv,\n\t\t\t\tvoid *envp, int *flags);\nextern int ksu_handle_execveat_sucompat(int *fd, struct filename **filename_ptr,\n\t\t\t\t\t void *argv, void *envp, int *flags);\n#endif\n\n/*\n * sys_execve() executes a new program.\n */\nstatic int do_execveat_common(int fd, struct filename *filename,''',
    'exec declarations')
replace_once(
    'fs/exec.c',
    '''static int do_execveat_common(int fd, struct filename *filename,\n\t\t\t      struct user_arg_ptr argv,\n\t\t\t      struct user_arg_ptr envp,\n\t\t\t      int flags)\n{\n\tchar *pathbuf = NULL;''',
    '''static int do_execveat_common(int fd, struct filename *filename,\n\t\t\t      struct user_arg_ptr argv,\n\t\t\t      struct user_arg_ptr envp,\n\t\t\t      int flags)\n{\n#ifdef CONFIG_KSU\n\tif (unlikely(ksu_execveat_hook))\n\t\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n\telse\n\t\tksu_handle_execveat_sucompat(&fd, &filename, &argv, &envp, &flags);\n#endif\n\tchar *pathbuf = NULL;''',
    'exec hook')

# fs/open.c
replace_once(
    'fs/open.c',
    '''/*\n * access() needs to use the real uid/gid, not the effective uid/gid.''',
    '''#ifdef CONFIG_KSU\nextern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,\n\t\t\t\tint *mode, int *flags);\n#endif\n\n/*\n * access() needs to use the real uid/gid, not the effective uid/gid.''',
    'faccessat declarations')
replace_once(
    'fs/open.c',
    '''\tint res;\n\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n\tif (mode & ~S_IRWXO)''',
    '''\tint res;\n\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n#ifdef CONFIG_KSU\n\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n#endif\n\n\tif (mode & ~S_IRWXO)''',
    'faccessat hook')

# fs/read_write.c
replace_once(
    'fs/read_write.c',
    '''ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)\n{\n\tssize_t ret;''',
    '''#ifdef CONFIG_KSU\nextern bool ksu_vfs_read_hook __read_mostly;\nextern int ksu_handle_vfs_read(struct file **file_ptr, char __user **buf_ptr,\n\t\t\t\tsize_t *count_ptr, loff_t **pos);\n#endif\nssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)\n{\n\tssize_t ret;\n#ifdef CONFIG_KSU\n\tif (unlikely(ksu_vfs_read_hook))\n\t\tksu_handle_vfs_read(&file, &buf, &count, &pos);\n#endif''',
    'vfs_read hook')

# fs/stat.c
replace_once(
    'fs/stat.c',
    '''int vfs_statx(int dfd, const char __user *filename, int flags,\n\t      struct kstat *stat, u32 request_mask)\n{\n\tstruct path path;\n\tint error = -EINVAL;\n\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;''',
    '''#ifdef CONFIG_KSU\nextern int ksu_handle_stat(int *dfd, const char __user **filename_user, int *flags);\n#endif\nint vfs_statx(int dfd, const char __user *filename, int flags,\n\t      struct kstat *stat, u32 request_mask)\n{\n\tstruct path path;\n\tint error = -EINVAL;\n\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n#ifdef CONFIG_KSU\n\tksu_handle_stat(&dfd, &filename, &flags);\n#endif''',
    'stat hook')

# drivers/input/input.c safe-mode hook
p = Path('drivers/input/input.c')
s = p.read_text()
if 'ksu_handle_input_handle_event' not in s:
    marker = '''static void input_handle_event(struct input_dev *dev,\n\t\t\t       unsigned int type, unsigned int code, int value)\n{\n\tint disposition = input_get_disposition(dev, type, code, &value);'''
    repl = '''#ifdef CONFIG_KSU\nextern bool ksu_input_hook __read_mostly;\nextern int ksu_handle_input_handle_event(unsigned int *type, unsigned int *code, int *value);\n#endif\n\nstatic void input_handle_event(struct input_dev *dev,\n\t\t\t       unsigned int type, unsigned int code, int value)\n{\n#ifdef CONFIG_KSU\n\tif (unlikely(ksu_input_hook))\n\t\tksu_handle_input_handle_event(&type, &code, &value);\n#endif\n\tint disposition = input_get_disposition(dev, type, code, &value);'''
    if marker not in s:
        raise SystemExit('[error] input_handle_event anchor not found')
    p.write_text(s.replace(marker, repl, 1))
    print('[ok] input safe-mode hook')
else:
    print('[skip] input safe-mode hook already applied')

# devpts hook
p = Path('fs/devpts/inode.c')
s = p.read_text()
if 'ksu_handle_devpts' not in s:
    marker = '''void *devpts_get_priv(struct dentry *dentry)\n{\n\tif (dentry->d_sb->s_magic != DEVPTS_SUPER_MAGIC)'''
    repl = '''#ifdef CONFIG_KSU\nextern int ksu_handle_devpts(struct inode *inode);\n#endif\nvoid *devpts_get_priv(struct dentry *dentry)\n{\n#ifdef CONFIG_KSU\n\tksu_handle_devpts(dentry->d_inode);\n#endif\n\tif (dentry->d_sb->s_magic != DEVPTS_SUPER_MAGIC)'''
    if marker in s:
        p.write_text(s.replace(marker, repl, 1))
        print('[ok] devpts hook')
    else:
        print('[warn] devpts anchor not found; continuing')
else:
    print('[skip] devpts hook already applied')
