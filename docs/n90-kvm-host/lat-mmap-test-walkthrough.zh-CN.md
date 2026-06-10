# lmbench `lat_mmap` 测试内容详解

**日期**：2026-06-10
**适用上下文**：N90 Phytium FTC862 主机侧 `kvm-arm.mode=none/vhe/nvhe/protected` 对照实验
**相关代码**：[src/lat_mmap.c](../../src/lat_mmap.c)、[src/lat_mmap_precise.c](../../src/lat_mmap_precise.c)、[src/lib_timing.c](../../src/lib_timing.c)

本文解释 lmbench 的 `lat_mmap` 到底测了什么，为什么它在 pKVM 开启的宿主机上表现出明显额外开销，以及为什么不能把这个结果简单理解为“pKVM 下所有内存访问都慢”。

## 1. 结论先行

`lat_mmap` 测的不是已经建立好映射之后的普通内存访问速度，也不是 mmap 区域的持续读写带宽。它测的是反复执行以下序列的平均延迟：

```text
mmap 一个 file-backed shared 区域
写触摸这段映射中的一部分地址
munmap 拆掉整段映射
```

也就是说，`lat_mmap` 的计时区包含：

1. 建立虚拟地址区域和文件之间的映射关系。
2. 首次访问部分映射页面，触发缺页处理和页表建立。
3. 拆除映射，清理 VMA、页表项和相关 TLB 状态。

因此，`lat_mmap` 更接近“建映射和拆映射路径”的测试，而不是“映射建立后访问内存”的测试。

在 N90 主机侧精测结果中，pKVM 相对 VHE 的 `lat_mmap` 开销随映射大小增加而上升：

| mmap size | VHE | pKVM | pKVM 相对 VHE |
|---:|---:|---:|---:|
| 0.5 MB | 7.763 us | 9.224 us | +18.8% |
| 1 MB | 11.760 us | 14.812 us | +25.9% |
| 2 MB | 21.068 us | 27.593 us | +31.0% |
| 4 MB | 36.088 us | 49.105 us | +36.1% |
| 8 MB | 66.117 us | 92.243 us | +39.5% |
| 16 MB | 123.651 us | 175.340 us | +41.8% |
| 64 MB | 498.398 us | 709.236 us | +42.3% |

这个现象说明：pKVM 宿主机在“反复建立 file-backed shared mapping、首次触摸页面、再拆除 mapping”的路径上明显更慢。它不说明“pKVM 下所有普通内存 load/store 都慢 42%”。

## 2. 基础概念

### 2.1 进程看到的是虚拟地址

用户态程序访问的地址通常不是内存条上的真实物理地址，而是虚拟地址。例如程序里有一个指针：

```c
char *p;
```

程序读写 `*p` 时，CPU 看到的是一个虚拟地址。真正访问内存前，CPU 和操作系统需要把这个虚拟地址翻译成物理地址。

可以粗略理解为：

```text
用户程序使用的地址：虚拟地址
内存条上的真实位置：物理地址
```

这层抽象允许每个进程拥有自己的地址空间。两个进程可以都认为自己有地址 `0x400000`，但它们最终可能映射到完全不同的物理页。

### 2.2 页是虚拟内存管理的基本单位

Linux 通常按“页”管理内存。常见基础页大小是 4 KB。也就是说，内核不是为每一个字节单独维护映射关系，而是按页维护：

```text
虚拟页 A -> 物理页 X
虚拟页 B -> 物理页 Y
虚拟页 C -> 尚未建立映射
```

程序可能只写一个字节：

```c
*p = c;
```

但这一次写操作会让 CPU 访问 `p` 所在的整个虚拟页。如果这个虚拟页还没有有效映射，内核就需要介入。

### 2.3 页表记录虚拟页到物理页的翻译关系

页表可以理解成一张地址翻译表：

```text
虚拟页 0x1000 -> 物理页 0x5000，可读可写
虚拟页 0x1001 -> 物理页 0x5001，可读可写
虚拟页 0x1002 -> 没有当前可用的翻译关系
```

CPU 访问内存时会查页表。如果翻译关系存在且权限允许，访问就可以继续。如果页表中没有对应关系，或者权限不满足，就会触发异常，由内核处理。

### 2.4 page fault 不一定是错误

“page fault”直译是缺页异常，但它不一定表示程序出错。在 mmap、匿名内存按需分配等路径中，page fault 经常是正常机制的一部分。

当程序第一次访问某个尚未建立页表项的虚拟地址时，CPU 会触发 page fault。内核接管后，大致会做：

1. 判断这个地址是否属于进程的合法虚拟地址区域。
2. 如果合法，找到这个地址应该对应的文件页、匿名页或其他 backing object。
3. 准备物理页或 page cache 页。
4. 建立页表项。
5. 返回用户态，让刚才那条访存指令重新执行。

所以，对 mmap 出来的文件区域来说，第一次访问某个页面时出现 page fault 是常见行为。它是“按需建立映射”的一部分。

### 2.5 VMA 描述一段虚拟地址区域

Linux 内核用 VMA，也就是 Virtual Memory Area，描述进程地址空间中的一段连续虚拟地址区域。例如：

```text
0x00400000 - 0x00500000  程序代码，只读可执行
0x00600000 - 0x00700000  程序数据，可读写
0x7f000000 - 0x7f400000  mmap 文件，可读写
0x7fff0000 - 0x80000000  用户栈，可读写
```

执行 `mmap()` 时，内核至少要为进程建立或调整 VMA。执行 `munmap()` 时，内核要删除、缩短或切分 VMA。

因此，`mmap()` 和 `munmap()` 即使不触发大量真实数据读写，也有内核数据结构管理成本。

### 2.6 TLB 是地址翻译缓存

页表在内存中，完整查页表也需要时间。CPU 会缓存最近用过的地址翻译关系，这个缓存叫 TLB，Translation Lookaside Buffer。

可以粗略理解为：

```text
页表：完整地址翻译字典
TLB：最近常用翻译项的高速缓存
```

当 `munmap()` 拆掉一段映射后，原先的虚拟地址到物理地址翻译不能继续使用。内核通常需要让相关 TLB 项失效，避免 CPU 继续使用旧翻译。

TLB 失效、页表拆除、VMA 维护都可能进入 `lat_mmap` 的计时结果。

### 2.7 “触摸内存”是什么意思

benchmark 里常说的“touch memory”不是特殊系统调用，而是普通地读或写某个地址。它的目的不是为了处理大量数据，而是为了逼操作系统真的为这个地址建立可用映射。

在 `lat_mmap` 中，“触摸”就是这一句：

```c
*p = c;
```

这行代码只写一个字节。但是，如果 `p` 所在页面还没有页表项，这一次写会触发 page fault。内核随后建立页表项，然后这条写指令才能成功完成。

因此，“触摸”可以理解为：

```text
访问某个地址一次，让它背后的页面从“只是有一条 VMA 规则”变成“已经实际可访问”。
```

## 3. `mmap()` 做了什么

普通文件读写常见写法是：

```c
read(fd, buf, size);
write(fd, buf, size);
```

这类接口显式地在文件和用户 buffer 之间搬数据。

`mmap()` 是另一种方式。它把文件的一段内容映射到进程虚拟地址空间里。调用成功后，程序拿到一个指针，可以像访问内存一样访问文件内容：

```c
char *where = mmap(..., fd, 0);
where[0] = 'x';
where[4096] = 'y';
```

`lat_mmap` 使用的是 file-backed shared mapping：

```c
where = mmap(0, size, PROT_READ|PROT_WRITE, MAP_FILE|MAP_SHARED, fd, 0);
```

这个调用的含义是：

```text
把文件 fd 从 offset 0 开始的 size 字节，映射到当前进程的一段虚拟地址。
这段地址允许读写。
这是共享映射，写入会影响该文件映射对应的共享页状态。
```

需要注意的是，`mmap()` 返回成功并不意味着这 `size` 字节对应的每个页面都已经建立好了页表项。很多系统会采用按需策略：先建立 VMA 规则，等程序第一次访问某个页面时再真正处理该页面。

## 4. `lat_mmap.c` 的整体结构

`lat_mmap` 的入口在 `main()` 中。它主要做四件事：

1. 解析命令行参数。
2. 保存测试状态，例如映射大小、文件名、是否随机触摸。
3. 调用 lmbench 的 `benchmp()` harness 运行测试。
4. 用 `micromb()` 输出每次 iteration 的平均延迟。

核心调用如下：

```c
benchmp(init, domapping, cleanup, 0, parallel,
    warmup, repetitions, &state);

if (gettime() > 0) {
    micromb(state.size, get_n());
}
```

这里的三个函数分工是：

| 函数 | 是否在主要计时区 | 作用 |
|---|---:|---|
| `init` | 否 | 打开 backing file，检查文件大小 |
| `domapping` | 是 | 反复执行 `mmap + 触摸 + munmap` |
| `cleanup` | 否 | 关闭文件描述符 |

真正要分析的是 `domapping()`，因为它是被计时的 workload。

## 5. 参数解析和测试状态

`lat_mmap` 支持以下参数：

```text
mmap [-r] [-C] [-P <parallelism>] [-W <warmup>] [-N <repetitions>] size file
```

关键参数含义如下：

| 参数 | 含义 |
|---|---|
| `size` | 每次 `mmap()` 的映射长度 |
| `file` | 被映射的 backing file |
| `-r` | 使用随机/稀疏触摸模式 |
| `-C` | 并发时为子进程复制 backing file |
| `-P` | 并发进程数 |
| `-W` | warmup 时间 |
| `-N` | repetition 次数 |

测试状态保存在 `state_t` 中：

```c
typedef struct _state {
    size_t  size;
    int     fd;
    int     random;
    int     clone;
    char    *name;
} state_t;
```

对于本文讨论的 N90 主机侧测试，最重要的是：

```text
size：每次映射大小
fd：被 mmap 的文件
random：默认是 0，也就是顺序触摸模式
```

## 6. `init()` 阶段

`init()` 负责打开文件并检查文件足够大：

```c
CHK(state->fd = open(state->name, O_RDWR));
if (seekto(state->fd, 0, SEEK_END) < state->size) {
    fprintf(stderr, "Input file too small\n");
    exit(1);
}
```

这说明 `lat_mmap` 不是匿名映射测试。它要求有一个实际 backing file，并且文件大小至少等于本轮要测试的映射大小。

如果传入 `-C`，代码会为进程复制一份 backing file。常规单进程测试不依赖这个路径。

## 7. `domapping()` 阶段

`domapping()` 是核心计时函数：

```c
void
domapping(iter_t iterations, void *cookie)
{
    state_t *state = (state_t *) cookie;
    register int fd = state->fd;
    register size_t size = state->size;
    register int random = state->random;
    register char *p, *where, *end;
    register char c = size & 0xff;

    while (iterations-- > 0) {
        where = mmap(0, size, PROT_READ|PROT_WRITE,
            MAP_FILE|MAP_SHARED, fd, 0);
        if ((long)where == -1) {
            perror("mmap");
            exit(1);
        }
        if (random) {
            end = where + size;
            for (p = where; p < end; p += STRIDE) {
                *p = c;
            }
        } else {
            end = where + (size / N);
            for (p = where; p < end; p += PSIZE) {
                *p = c;
            }
        }
        munmap(where, size);
    }
}
```

可以把一次 `while` 循环理解为一个 iteration。每个 iteration 包含：

```text
1. mmap()
2. 写触摸若干地址
3. munmap()
```

`lat_mmap` 最终输出的平均延迟就是一次 iteration 的平均耗时。

## 8. 默认顺序触摸模式

默认不带 `-r` 时，走这个分支：

```c
end = where + (size / N);
for (p = where; p < end; p += PSIZE) {
    *p = c;
}
```

相关常量是：

```c
#define PSIZE   (16<<10)
#define N       10
```

所以默认行为是：

```text
只触摸映射区域的前 1/10
每隔 16 KB 写 1 个字节
```

不同 size 下的默认触摸规模大致如下：

| mmap size | 触摸范围 size/10 | 步长 | 触摸次数约 |
|---:|---:|---:|---:|
| 0.5 MB | 0.05 MB | 16 KB | 4 |
| 1 MB | 0.1 MB | 16 KB | 7 |
| 2 MB | 0.2 MB | 16 KB | 13 |
| 4 MB | 0.4 MB | 16 KB | 26 |
| 8 MB | 0.8 MB | 16 KB | 52 |
| 16 MB | 1.6 MB | 16 KB | 103 |
| 64 MB | 6.4 MB | 16 KB | 410 |

这里的“触摸次数”不是精确到边界条件的规范值，而是帮助理解工作量随映射大小增长的近似值。

需要特别注意：`PSIZE` 是 lmbench 自己定义的 16 KB 触摸步长，不一定等于系统基础页大小。如果系统基础页是 4 KB，那么每隔 16 KB 写一次，意味着每次触摸会落在相隔 4 个基础页的位置上。

## 9. `-r` 随机/稀疏模式

如果命令带 `-r`，代码走这个分支：

```c
end = where + size;
for (p = where; p < end; p += STRIDE) {
    *p = c;
}
```

其中：

```c
#define STRIDE (10*PSIZE)
```

也就是每隔 160 KB 写一个字节，并覆盖整个映射范围。

本文和 N90 pKVM 主机侧结论主要讨论默认路径，也就是不带 `-r` 的顺序触摸模式。

## 10. 一个 64 MB 例子

假设测试的是 64 MB 映射，默认顺序模式下，一次 iteration 大致是：

```text
1. 调用 mmap，建立 64 MB file-backed shared VMA。
2. 从映射起始地址开始，到前 6.4 MB 为止，每隔 16 KB 写一个字节。
3. 调用 munmap，拆掉整个 64 MB 映射。
```

写触摸地址类似：

```text
where + 0 KB
where + 16 KB
where + 32 KB
where + 48 KB
...
where + 6.4 MB 附近
```

每个写触摸都可能导致该虚拟地址所在页面从“只有 VMA 规则”进入“页表项已经建立、CPU 可以完成访问”的状态。

所以 64 MB 结果中的 `709.236 us`，不是“读写 64 MB 用了 709.236 us”。更准确的解释是：

```text
平均每次 mmap 64 MB 文件区域、触摸前 6.4 MB 中的稀疏地址、再 munmap 64 MB 区域，一共耗时 709.236 us。
```

## 11. lmbench harness 如何计时

`lat_mmap` 自己不直接在 `domapping()` 前后写计时调用，而是使用 lmbench 的 `benchmp()`。

`benchmp()` 的职责包括：

1. 创建测试子进程。
2. 做 warmup。
3. 根据耗时动态调整 iteration 数。
4. 执行若干 repetition。
5. 保存总耗时和 iteration 数。

在 child 侧，harness 会反复调用：

```c
(*benchmark)(benchmp_interval(&_benchmp_child_state), cookie);
```

其中 `benchmark` 对 `lat_mmap` 来说就是 `domapping()`。

每轮计时结束后，harness 会保存：

```c
save_n(state->iterations);
settime(result);
```

最后 `lat_mmap` 通过：

```c
micromb(state.size, get_n());
```

输出平均值。

## 12. 原版 `micromb()` 的输出口径

`micromb()` 的核心逻辑是：

```c
micro = total_time_us / n;
mb = sz / MB;
if (micro >= 10) {
    fprintf(ftiming, "%.6f %.0f\n", mb, micro);
} else {
    fprintf(ftiming, "%.6f %.3f\n", mb, micro);
}
```

所以原版 `lat_mmap` 输出两列：

```text
映射大小_MB 平均每次_iteration_微秒
```

例如：

```text
64.000000 697
```

含义是：

```text
映射大小约 64 MB。
平均每次 mmap + 触摸 + munmap 是 697 us。
```

原版输出的一个限制是：当平均耗时大于等于 10 us 时，`micromb()` 用整数微秒输出。这会掩盖小数部分。因此仓库中增加了 `lat_mmap_precise.c`，只改变计时和输出精度，不改变测试语义。

## 13. precise 版本为什么必要

`src/lat_mmap_precise.c` 明确说明其语义和原版一致：

```text
file-backed MAP_SHARED
PSIZE = 16 KB
N = 10
顺序触摸 size/N 字节
每次 iter 都 mmap + 触摸 + munmap
```

区别是：

```text
原版：gettimeofday 体系 + micromb 整数微秒输出
precise：clock_gettime(CLOCK_MONOTONIC) + 纳秒级 per_iter 输出
```

precise 版本的核心循环是：

```c
for (int i = 0; i < iters; i++) {
    char *p = mmap(NULL, size, PROT_READ|PROT_WRITE,
        MAP_FILE|MAP_SHARED, fd, 0);
    char c = (char)(size & 0xff);
    char *end = p + (size / N);
    for (char *q = p; q < end; q += PSIZE) {
        *q = c;
    }
    munmap(p, size);
}
```

这让我们能够确认 pKVM 的开销不是整数微秒输出造成的舍入假象，而是在每个 size 上都稳定存在。

## 14. 为什么这个测试对 pKVM 敏感

普通 ARM64 KVM VHE/NVHE 主机和 pKVM 主机的关键区别之一是：pKVM 为宿主机额外维护 host stage-2 地址转换。

简化理解如下：

```text
普通主机：
用户虚拟地址 -> 主机 stage-1 翻译 -> 物理地址

pKVM 宿主机：
用户虚拟地址 -> 主机 stage-1 翻译 -> host stage-2 翻译 -> 物理地址
```

当映射已经建立好、TLB 状态稳定时，额外 stage-2 的影响可能较小，因为硬件和 TLB 会缓存大量翻译结果。

但 `lat_mmap` 的工作负载不是稳定访问，而是不断：

```text
新建映射
首次访问部分页面
拆除映射
再新建
再首次访问
再拆除
```

这类路径会频繁触发：

1. VMA 建立和拆除。
2. stage-1 页表项建立和回收。
3. page fault 处理。
4. TLB invalidation。
5. 在 pKVM 下，还可能涉及 host stage-2 相关检查、权限或映射状态维护。

因此，pKVM 的额外成本会集中出现在 `lat_mmap` 这种“建映射和首次触摸”测试中。

## 15. 为什么不能把它等同于普通内存访问变慢

`lat_mem_rd`、`bw_mem` 等测试通常在计时前已经把工作集初始化并 first-touch 完成。正式计时区主要是：

```text
读已经建立好映射的内存
写已经建立好映射的内存
拷贝已经建立好映射的内存
```

而 `lat_mmap` 的正式计时区是：

```text
mmap
首次触摸
munmap
```

两者测量对象不同：

| 测试 | 主要测量对象 |
|---|---|
| `lat_mmap` | 建立映射、首次访问、拆除映射 |
| `lat_mem_rd` | 映射建立后的读访问延迟 |
| `bw_mem` | 映射建立后的连续读写吞吐 |
| `bw_mmap_rd` | mmap 后读文件内容的带宽 |

所以，pKVM 在 `lat_mmap` 上慢约 42%，不能外推为所有内存访问都慢约 42%。更准确的表述是：

```text
pKVM 宿主机在 lmbench `lat_mmap` 所代表的 file-backed shared mapping 建立、首次触摸和拆除路径上有明显额外开销。
```

## 16. 对结果表述的建议

推荐表述：

```text
在 N90 主机侧受控实验中，pKVM 最明显的额外开销出现在 lmbench `lat_mmap`。
该测试每轮执行 file-backed MAP_SHARED 的 mmap、按 16 KB 步长写触摸前 size/10 的映射范围、再 munmap。
因此该结果主要反映映射建立、首次访问缺页处理和映射拆除路径的成本。
64 MB 精测下，pKVM 相对 VHE 从 498.398 us 增至 709.236 us，开销约 +42.3%。
```

不推荐表述：

```text
pKVM 下 mmap 后的内存访问都慢 42%。
```

原因是这会把 `lat_mmap` 的“建映射和首次触摸”成本误写成“已建映射上的持续访问”成本。

## 17. 一句话概括

`lat_mmap` 可以用一句白话概括：

```text
反复把文件挂到进程地址空间里，碰一部分页面让系统真的建好映射，再把它拆掉，最后计算平均每轮耗时。
```

在 pKVM 宿主机上，这条路径比 VHE/NVHE/KVM-off 明显更慢，因为它更频繁暴露出 host stage-2 和相关映射维护路径的成本。
