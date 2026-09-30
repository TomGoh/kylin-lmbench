# 多代理调查与核查的原始报告

本目录是调查过程的记录，不是结论。结论见上一级目录的 `memlat-rootcause.zh-CN.md`。

## 做法

1. **调查**：六个互相独立的调查代理，各自只拿到问题、数据和代码的位置，从不同角度核查。
   报告是英文原文，文件名 `investigate-<角度>.md`。每条发现带有类别：
   MEASURED（自己从原始数据算出来的）、DOCUMENTED（某份文档或源码这么写）、INFERRED（推断）。
2. **核查**：调查的每一条发现、以及在 N80 上的测量结论和综合结论草稿，再交给独立的核查代理。
   每组结论由两个视角不同的核查者分别处理：一个抛开原有依据、从原始数据或源码重新推导；
   另一个专门找反例和别的解释。另有两个审计者检查测量程序本身有没有缺陷、独立重算设备日志。
   报告文件名 `verify-*.md`。
3. 只有核查通过的内容才写进结论文档；被推翻或无法核实的条目在结论文档里单独列出。

## 调查角度

| 文件 | 角度 |
| --- | --- |
| `investigate-host-stats.md` | N90 宿主机四模式原始数据的统计 |
| `investigate-guest-fig8.md` | x-kernel 客户机内数据（图 8） |
| `investigate-kernel-mechanism.md` | 内核与监视器源码里的机制 |
| `investigate-arch-literature.md` | Arm 体系结构规范与文献 |
| `investigate-lmbench-semantics.md` | lmbench 这两个指标到底测的是什么 |
| `investigate-prior-docs.md` | 仓库里已有分析文档的梳理与交叉检查 |

报告里的 `<scratch>/` 是调查时的临时目录，其中的脚本没有随仓库保存；
能复现全部表格的脚本在 `experiments/memlat-probe/`。
报告中与调查内容无关的会话说明已删去，其余照录。
