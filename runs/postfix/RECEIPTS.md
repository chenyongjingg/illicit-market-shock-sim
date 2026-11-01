# runs/postfix/ -- 收据、仪器与两轮修复（服务关闭前最后一窗）

**最终树：`f4328c4a7b0c1b5a`**（`cat /root/mdpi3/code/*.py /root/mdpi3/code/config.yaml | sha256sum | cut -c1-16`）。run-1 的交付树是 `55505a71431cff70`，两者相差两次**单词级**修改，都记在偏差册 D-107 的 STATUS CHANGE 里。

`runs/postfix/stage_*.code.sha` **不覆盖** `runs/stage_*.code.sha`。两个阶段是手工重跑的（`python3 code/s5_analyze.py` / `code/report.py`），没有走 `run_all.sh`，所以 `runs/` 下那两个标记仍是 run-1 的 `55505a71431cff70`，**对 06:56 之后的产物是错的**——这不是可以靠重盖一个 17 字节文件解决的：那个文件是run-1 的历史收据，覆盖它就把历史改掉了。**「哪份代码产生了这份产物」的现行答案在 `MANIFEST.artifacts.jsonl` 的行里**（`extra.code_hash_produced_by`），不在文件名里。

| 收据 | 值 | 管辖的产物 |
|---|---|---|
| `runs/postfix/stage_s5_analyze.code.sha` | `f4328c4a7b0c1b5a` | `runs/analysis.json` |
| `runs/postfix/stage_report.code.sha` | `f4328c4a7b0c1b5a` | `runs/REPORT.md`、`runs/q_checklist.json` |

**两轮冻结件**（都在 `runs/postfix_frozen/`，互不覆盖）：

- `analysis.json` `74f5edd0…` / `REPORT.md` `cb246830…`：**修复前**（run-1 交付态），与 `s5_analyze.py.orig` `2b8052bb…`、`report.py.orig` `b78345f1…` 同时冻结。
- `round2/`：第一轮修复后（`fbc5f6c3`）的 `analysis.json` `dafdda5c…`、`REPORT.md` `902ab48f…`、`s5_analyze.py` `79455cd0…`。

**判据**：`_d107_diff_gate_v2.out`（冻结件 vs 现行）。v1 的 `_d107_diff_gate.out` 保留，它在干净重跑上报 FAIL，原因是 `generated_utc` 被当成 FORBIDDEN（D-113）。

**未随产物更新的标记**：`runs/stage_s5_analyze.ok`、`runs/stage_report.ok`、`runs/PIPELINE_DONE` 的 mtime 仍是 `06:17:35Z`，早于产物。所以**一个后来的 `run_all.sh` 会因为 `.ok` 存在而跳过这两个阶段**，把 06:56 的产物当成已完成——这不是错误状态，但它意味着「`.ok` 存在」不等于「产物是这棵树产出的」。
