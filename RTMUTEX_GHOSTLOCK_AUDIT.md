# LG Wing RT-mutex / GhostLock Research Audit

Date: 2026-11-01  
Target: LG Wing LM-F100 (winglm), Snapdragon SM7250, ARM64  
Branch reviewed: `ksunext-winglm-ci`

## Scope and safety boundary

This document records source-level observations and a safe regression-test plan. It does not reintroduce a use-after-free, weaken task reference counting, remove locking, or provide an exploit profile. The production kernel must retain the existing RT-mutex lifetime protections.

## Repository state observed

- Branch: `ksunext-winglm-ci`
- Kernel Makefile reports Linux `4.19.325` (not `4.19.157`).
- LG Wing defconfig exists at `arch/arm64/configs/vendor/winglm-perf_defconfig`.
- Defconfig blob: `93965832c72c479d544dd036bbc466665467af4b`.
- Current `kernel/locking/rtmutex.c` blob: `01cb685c677cf0a60697ec0e1b181e77b16febe6`.
- Current `Makefile` blob: `197646a248aecf39092940740fdfb31e5b2febbf`.
- KernelSU workflow: `.github/workflows/winglm-kernelsu.yml`, blob `cc55618bccc9c58e6b23f23714c7ea09d8e8e17b`.

The repository's earlier CI commit `ad2d5275e357eb4e86fcc976165b668d083b5b84` added a different workflow targeting `lineage-23.2` and a pinned source checkout. The active branch workflow now targets `ksunext-winglm-ci`; these workflows must not be conflated.

## RT-mutex source observation

In the reviewed `remove_waiter()` implementation:

1. The caller is expected to hold `lock->wait_lock`.
2. The waiter task's `pi_lock` protects removal from the lock waiter tree and clearing `waiter_task->pi_blocked_on`.
3. If the waiter is the top waiter and the lock has an owner, the owner's PI waiter state and effective priority are updated under `owner->pi_lock`.
4. If the owner is itself blocked on another lock, the code takes a task reference before dropping the wait lock and walking the priority-inheritance chain.

These are lifetime and lock-order invariants. Any regression testing must assert that task references remain valid across the chain walk, waiter tree membership is consistent, and lock ordering remains valid under contention.

## Safe validation plan

- Keep the production `rtmutex.c` unchanged.
- Add or run stress/regression tests only in a disposable test kernel or emulator.
- Exercise concurrent waiter enqueue/dequeue, owner exit, signal interruption, timeout, priority changes, and PI-chain requeue.
- Enable available lockdep, debug RT-mutex, KASAN, and refcount diagnostics where the target configuration supports them.
- Require no KASAN reports, refcount warnings, lockdep splats, hung tasks, or waiter-tree inconsistencies.
- Compare behavior and symbols against the exact source revision used for each image; do not infer source version from a kernel release string alone.

## Build workflow checks still required

The workflow file was inspected, but no successful Actions run or build artifact was verified during this audit. Before treating the branch as build-ready, run the workflow and confirm:

- KernelSU setup and compatibility patch complete.
- `vendor/winglm-perf_defconfig` configures successfully.
- `CONFIG_KSU=y`, `CONFIG_MACH_LITO_WINGLM=y`, and selected hook options survive `olddefconfig`.
- `Image.gz` is produced and non-empty.
- DTB/DTBO output is collected and completeness is reported separately.
- SHA-256 checksums and build logs are attached to the run.

## Explicit version distinction

The requested stock baseline is reported as `4.19.157-perf+`, while the reviewed branch Makefile reports `4.19.325`. A valid stock-vs-branch comparison requires the exact stock source tree or a verifiable matching source commit. Renaming the release string does not recreate the stock source baseline.


## Root build readiness (2026-11-01)

The branch workflow is `.github/workflows/winglm-kernelsu.yml`. It is configured for push events on `ksunext-winglm-ci` and manual dispatch. The workflow builds `Image.gz`, collects the resulting config and logs, and uploads artifacts. It does not create a complete boot image or prove that the device bootloader will accept a flash operation.

Rooting acceptance criteria:

- CI completes with `CONFIG_KSU=y` and a non-empty `Image.gz`.
- Device-specific boot image packaging and partition layout are verified against the exact LM-F100 firmware variant before any installation.
- The bootloader state and supported flashing path are confirmed on-device.
- A stock boot image and recovery path are retained. Do not flash a kernel-only artifact as if it were a boot image.
- After boot, verify KernelSU manager connection and root authorization from the device; a successful compile alone is not root access.

The RT-mutex lifetime fix remains unchanged. This build path is for KernelSU-Next integration and normal root access, not for reintroducing the GhostLock UAF.
