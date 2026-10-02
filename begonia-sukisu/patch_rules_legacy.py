from pathlib import Path

p = Path('KernelSU/kernel/selinux/rules.c')
s = p.read_text()

old_get = '''static struct policydb *get_policydb(void)\n{\n\tstruct policydb *db;\n\tstruct selinux_policy *policy = selinux_state.policy;\n\tdb = &policy->policydb;\n\treturn db;\n}\n'''
new_get = '''static struct policydb *get_policydb(void)\n{\n\t/* Begonia 4.14 exports the active policydb directly from services.c. */\n\treturn &policydb;\n}\n'''
if old_get not in s:
    raise SystemExit('[error] rules.c get_policydb anchor not found')
s = s.replace(old_get, new_get, 1)

old_reset = '''static void reset_avc_cache()\n{\n#if (LINUX_VERSION_CODE >= KERNEL_VERSION(6, 4, 0))\n\tavc_ss_reset(0);\n\tselnl_notify_policyload(0);\n\tselinux_status_update_policyload(0);\n#else\n\tstruct selinux_avc *avc = selinux_state.avc;\n\tavc_ss_reset(avc, 0);\n\tselnl_notify_policyload(0);\n\tselinux_status_update_policyload(&selinux_state, 0);\n#endif\n\tselinux_xfrm_notify_policyload();\n}\n'''
new_reset = '''static void reset_avc_cache()\n{\n\t/* Legacy SELinux API used by Xiaomi's 4.14 tree. */\n\tavc_ss_reset(0);\n\tselnl_notify_policyload(0);\n\tselinux_status_update_policyload(0);\n\tselinux_xfrm_notify_policyload();\n}\n'''
if old_reset not in s:
    raise SystemExit('[error] rules.c reset_avc_cache anchor not found')
s = s.replace(old_reset, new_reset, 1)

p.write_text(s)
print('[ok] rules.c legacy policydb/AVC compatibility')
