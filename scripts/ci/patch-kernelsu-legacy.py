#!/usr/bin/env python3
"""Apply compatibility fixes for KernelSU-Next on the LG Wing Linux 4.19 tree."""
from pathlib import Path
import re

patch_memory = Path("drivers/kernelsu/hook/patch_memory.c")
if patch_memory.exists():
    source = patch_memory.read_text()
    pattern = r"// copy_to_kernel_nofault.*?^#endif\s*\n"
    updated, count = re.subn(
        pattern,
        "/* LG's Linux 4.19 tree already provides copy_to_kernel_nofault(). */\n",
        source,
        count=1,
        flags=re.M | re.S,
    )
    if count != 1:
        raise SystemExit("Could not locate KernelSU probe_kernel_write compatibility block")
    patch_memory.write_text(updated)
    print("Using the existing copy_to_kernel_nofault() implementation")

namespace = Path("fs/namespace.c")
source = namespace.read_text()
marker = "SYSCALL_DEFINE2(umount"
if "int path_umount(struct path *path, int flags)" not in source:
    position = source.find(marker)
    if position < 0:
        raise SystemExit("Could not locate umount syscall insertion point")
    helper = r'''
/*
 * path_umount() compatibility backport for KernelSU on Linux 4.19.
 * The caller supplies a referenced path and validates the flags.
 */
static int ksu_can_umount_path(const struct path *path, int flags)
{
    struct mount *mnt = real_mount(path->mnt);

    if (!may_mount())
        return -EPERM;
    if (path->dentry != path->mnt->mnt_root)
        return -EINVAL;
    if (!check_mnt(mnt))
        return -EINVAL;
    if (mnt->mnt.mnt_flags & MNT_LOCKED)
        return -EINVAL;
    if ((flags & MNT_FORCE) && !capable(CAP_SYS_ADMIN))
        return -EPERM;
    return 0;
}

int path_umount(struct path *path, int flags)
{
    struct mount *mnt = real_mount(path->mnt);
    int ret = ksu_can_umount_path(path, flags);

    if (!ret)
        ret = do_umount(mnt, flags);

    /* Do not call path_put(): it clears mnt_expiry_mark. */
    dput(path->dentry);
    mntput_no_expire(mnt);
    return ret;
}

'''
    namespace.write_text(source[:position] + helper + source[position:])
    print("Backported path_umount() into fs/namespace.c")

internal = Path("fs/internal.h")
source = internal.read_text()
prototype = "extern int path_umount(struct path *path, int flags);"
if prototype not in source:
    marker = "extern int finish_automount(struct vfsmount *, struct path *);"
    if marker not in source:
        raise SystemExit("Could not locate fs/internal.h namespace declarations")
    internal.write_text(source.replace(marker, marker + "\n" + prototype, 1))
    print("Added path_umount() declaration")
