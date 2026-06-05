# Patches to upstream lmbench

The initial git commit is the unmodified upstream 3.0-a9 tarball. The second
commit (containing all local additions) also modifies **two** upstream files.
This page documents what changed and why.

## `scripts/build` — libtirpc detection

```diff
+# Modern Linux (glibc >= 2.26) ships Sun RPC headers in libtirpc,
+# under /usr/include/tirpc instead of /usr/include. Detect and adapt.
+if [ -f /usr/include/tirpc/rpc/rpc.h ]; then
+       CFLAGS="${CFLAGS} -I/usr/include/tirpc"
+       LDLIBS="${LDLIBS} -ltirpc"
+fi
```

**Why**: lmbench 3.0-a9 (2007) predates the glibc 2.26 split that moved Sun RPC
out of glibc into the separate `libtirpc` package. On modern distributions
without this patch, `lat_rpc.c` and friends fail to find `rpc/rpc.h` and the
build dies.

**Detection logic**: probe for the `tirpc` header — if present, add the include
path and link `-ltirpc`. On older distros (e.g. Kylin V10 used here, which
still ships the legacy header in `/usr/include/rpc/`), the probe fails and we
fall through to the unmodified build — zero behavior change.

## `scripts/os` — aarch64 fallback for OS string

```diff
+    FALLBACK_OS="$OS"
     if [ -f ../scripts/gnu-os ]
-    then       OS=`../scripts/gnu-os | sed s/unknown-//`
+    then       OS=`../scripts/gnu-os 2>/dev/null | sed s/unknown-//`
     fi
     if [ -f ../../scripts/gnu-os ]
-    then       OS=`../../scripts/gnu-os | sed s/unknown-//`
+    then       OS=`../../scripts/gnu-os 2>/dev/null | sed s/unknown-//`
     fi
+    # gnu-os (2004 config.guess) doesn't recognize newer arches like
+    # aarch64 and returns empty; fall back to uname-derived name.
+    if [ "X$OS" = "X" ]; then OS="$FALLBACK_OS"; fi
 fi
```

**Why**: `scripts/gnu-os` is an old (~2004 vintage) GNU `config.guess`. It
doesn't know about `aarch64`/`arm64` and exits with empty output. lmbench then
uses an empty `$OS` everywhere, which makes `bin/$OS/` and `results/$OS/`
collapse to `bin/` and `results/` — all binaries land at the wrong path and
build/run logic breaks subtly.

**Fix**: stash the uname-derived OS string ("aarch64-Linux") before calling
`gnu-os`, and fall back to it if `gnu-os` returns empty. Also silence stderr
from `gnu-os` so the empty-OS isn't masked by warning spam.

**Side effect**: zero. If `gnu-os` *does* produce output (it works for
recognized old architectures), the original value wins. The fallback only
fires when `gnu-os` is broken.

## What's NOT patched

A few things one might be tempted to "fix" in upstream that we deliberately
leave alone:

- **Warnings about ignored `write()` return values** in `lat_fcntl.c`,
  `lat_unix_connect.c`. These are benign — silencing them would touch every
  benchmark file with no semantic change. Easier to ignore the warnings.
- **`lat_proc` hardcoding `/tmp/hello`**. Adjusting paths would diverge our
  fork further from upstream. The upstream `scripts/lmbench` wrapper copies
  the binary into `/tmp/hello` during setup, so `bench.sh` (which invokes
  `scripts/lmbench`) inherits that fix for free.
- **`stream` getting shadowed by ImageMagick's `stream`** in `$PATH`. lmbench
  works around this by putting `.` first in `PATH`. Our `bench.sh` correctly
  `cd`s to `bin/aarch64-Linux/` before invocation so this isn't an issue. If
  you invoke `scripts/lmbench` manually from elsewhere, you'll hit the
  ImageMagick collision — `cd` first.
