/* Android NDK compatibility shim for building selected unmodified lmbench tools. */
#ifndef KYLIN_LMBENCH_ANDROID_COMPAT_H
#define KYLIN_LMBENCH_ANDROID_COMPAT_H

#include <malloc.h>
#include <stdint.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

#ifndef valloc
#define valloc(sz) memalign((size_t)getpagesize(), (sz))
#endif

#endif
