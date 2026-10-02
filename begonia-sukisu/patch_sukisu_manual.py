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


def replace_between(path, start, end, replacement, label):
    p = Path(path)
    s = p.read_text()
    a = s.find(start)
    if a < 0:
        raise SystemExit(f'[error] start anchor not found for {label} in {path}')
    b = s.find(end, a)
    if b < 0:
        raise SystemExit(f'[error] end anchor not found for {label} in {path}')
    p.write_text(s[:a] + replacement + s[b:])
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

# ---------------------------------------------------------------------------
# Legacy Android SELinux policydb compatibility for Xiaomi Begonia 4.14.
# This tree uses struct filename_trans and flex_array for type maps.
# ---------------------------------------------------------------------------
sepolicy_path = 'KernelSU/kernel/selinux/sepolicy.c'
p = Path(sepolicy_path)
s = p.read_text()
if '#include <linux/flex_array.h>' not in s:
    s = s.replace('#include <linux/gfp.h>\n', '#include <linux/gfp.h>\n#include <linux/flex_array.h>\n', 1)
    p.write_text(s)
    print('[ok] legacy sepolicy flex_array include')

legacy_filename = r'''static bool add_filename_trans(struct policydb *db, const char *s,
                               const char *t, const char *c, const char *d,
                               const char *o)
{
    struct type_datum *src, *tgt, *def;
    struct class_datum *cls;
    struct filename_trans key;
    struct filename_trans_datum *trans;
    struct filename_trans *new_key;

    src = symtab_search(&db->p_types, s);
    tgt = symtab_search(&db->p_types, t);
    cls = symtab_search(&db->p_classes, c);
    def = symtab_search(&db->p_types, d);
    if (!src || !tgt || !cls || !def)
        return false;

    key.stype = src->value;
    key.ttype = tgt->value;
    key.tclass = cls->value;
    key.name = o;

    trans = hashtab_search(db->filename_trans, &key);
    if (!trans) {
        trans = kzalloc(sizeof(*trans), GFP_ATOMIC);
        new_key = kzalloc(sizeof(*new_key), GFP_ATOMIC);
        if (!trans || !new_key) {
            kfree(trans);
            kfree(new_key);
            return false;
        }
        *new_key = key;
        new_key->name = kstrdup(key.name, GFP_ATOMIC);
        if (!new_key->name) {
            kfree(new_key);
            kfree(trans);
            return false;
        }
        trans->otype = def->value;
        if (hashtab_insert(db->filename_trans, new_key, trans)) {
            kfree((char *)new_key->name);
            kfree(new_key);
            kfree(trans);
            return false;
        }
    } else {
        trans->otype = def->value;
    }

    return ebitmap_set_bit(&db->filename_trans_ttypes, tgt->value - 1, 1) == 0;
}

'''
replace_between(sepolicy_path,
                'static bool add_filename_trans(struct policydb *db,',
                'static bool add_genfscon(struct policydb *db,',
                legacy_filename,
                'legacy add_filename_trans')

legacy_add_type = r'''static bool add_type(struct policydb *db, const char *type_name, bool attr)
{
    struct type_datum *type;
    struct flex_array *new_type_attr_map_array;
    struct flex_array *new_type_val_to_struct;
    struct flex_array *new_val_to_name_types;
    struct flex_array *old_fa;
    char *key;
    void *old_elem;
    u32 value;
    int i;

    type = symtab_search(&db->p_types, type_name);
    if (type)
        return true;

    value = ++db->p_types.nprim;
    type = kzalloc(sizeof(*type), GFP_ATOMIC);
    key = kstrdup(type_name, GFP_ATOMIC);
    if (!type || !key)
        return false;

    type->primary = 1;
    type->value = value;
    type->attribute = attr;
    if (symtab_insert(&db->p_types, key, type))
        return false;

    new_type_attr_map_array = flex_array_alloc(sizeof(struct ebitmap), value,
                                                GFP_ATOMIC | __GFP_ZERO);
    new_type_val_to_struct = flex_array_alloc(sizeof(struct type_datum *), value,
                                               GFP_ATOMIC | __GFP_ZERO);
    new_val_to_name_types = flex_array_alloc(sizeof(char *), value,
                                              GFP_ATOMIC | __GFP_ZERO);
    if (!new_type_attr_map_array || !new_type_val_to_struct || !new_val_to_name_types)
        return false;

    if (flex_array_prealloc(new_type_attr_map_array, 0, value,
                            GFP_ATOMIC | __GFP_ZERO) ||
        flex_array_prealloc(new_type_val_to_struct, 0, value,
                            GFP_ATOMIC | __GFP_ZERO) ||
        flex_array_prealloc(new_val_to_name_types, 0, value,
                            GFP_ATOMIC | __GFP_ZERO))
        return false;

    if (db->type_attr_map_array) {
        for (i = 0; i < db->type_attr_map_array->total_nr_elements; i++) {
            old_elem = flex_array_get(db->type_attr_map_array, i);
            if (old_elem)
                flex_array_put(new_type_attr_map_array, i, old_elem,
                               GFP_ATOMIC | __GFP_ZERO);
        }
    }
    if (db->type_val_to_struct_array) {
        for (i = 0; i < db->type_val_to_struct_array->total_nr_elements; i++) {
            old_elem = flex_array_get_ptr(db->type_val_to_struct_array, i);
            if (old_elem)
                flex_array_put_ptr(new_type_val_to_struct, i, old_elem,
                                   GFP_ATOMIC | __GFP_ZERO);
        }
    }
    if (db->sym_val_to_name[SYM_TYPES]) {
        for (i = 0; i < db->sym_val_to_name[SYM_TYPES]->total_nr_elements; i++) {
            old_elem = flex_array_get_ptr(db->sym_val_to_name[SYM_TYPES], i);
            if (old_elem)
                flex_array_put_ptr(new_val_to_name_types, i, old_elem,
                                   GFP_ATOMIC | __GFP_ZERO);
        }
    }

    old_fa = db->type_attr_map_array;
    db->type_attr_map_array = new_type_attr_map_array;
    if (old_fa)
        flex_array_free(old_fa);
    ebitmap_init(flex_array_get(db->type_attr_map_array, value - 1));
    ebitmap_set_bit(flex_array_get(db->type_attr_map_array, value - 1), value - 1, 1);

    old_fa = db->type_val_to_struct_array;
    db->type_val_to_struct_array = new_type_val_to_struct;
    if (old_fa)
        flex_array_free(old_fa);
    flex_array_put_ptr(db->type_val_to_struct_array, value - 1, type,
                       GFP_ATOMIC | __GFP_ZERO);

    old_fa = db->sym_val_to_name[SYM_TYPES];
    db->sym_val_to_name[SYM_TYPES] = new_val_to_name_types;
    if (old_fa)
        flex_array_free(old_fa);
    flex_array_put_ptr(db->sym_val_to_name[SYM_TYPES], value - 1, key,
                       GFP_ATOMIC | __GFP_ZERO);

    for (i = 0; i < db->p_roles.nprim; i++)
        ebitmap_set_bit(&db->role_val_to_struct[i]->types, value - 1, 1);

    return true;
}

'''
replace_between(sepolicy_path,
                'static bool add_type(struct policydb *db,',
                'static bool set_type_state(struct policydb *db,',
                legacy_add_type,
                'legacy add_type flex_array')

legacy_typeattr = r'''static void add_typeattribute_raw(struct policydb *db, struct type_datum *type,
                                  struct type_datum *attr)
{
    struct ebitmap *sattr;
    struct hashtab_node *node;
    struct constraint_node *n;
    struct constraint_expr *e;

    sattr = flex_array_get(db->type_attr_map_array, type->value - 1);
    if (!sattr)
        return;
    ebitmap_set_bit(sattr, attr->value - 1, 1);

    ksu_hashtab_for_each(db->p_classes.table, node)
    {
        struct class_datum *cls = (struct class_datum *)node->datum;
        for (n = cls->constraints; n; n = n->next) {
            for (e = n->expr; e; e = e->next) {
                if (e->expr_type == CEXPR_NAMES &&
                    ebitmap_get_bit(&e->type_names->types, attr->value - 1))
                    ebitmap_set_bit(&e->names, type->value - 1, 1);
            }
        }
    };
}

'''
replace_between(sepolicy_path,
                'static void add_typeattribute_raw(struct policydb *db,',
                'static bool add_typeattribute(struct policydb *db,',
                legacy_typeattr,
                'legacy add_typeattribute_raw')
