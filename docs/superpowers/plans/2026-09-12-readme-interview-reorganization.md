# README Interview Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将仓库首页整理为北大软微推免复试老师可快速理解的项目主页，并只将必要源码、配置和当前文档提交到 GitHub。

**Architecture:** README 先呈现研究问题、技术路线、结果与边界，再提供按职责划分的目录地图和最短复现命令。Git 收录通过 `.gitignore` 明确隔离原始数据、派生数据、训练输出和本机 Codex 配置，同时保留数据目录占位文件。

**Tech Stack:** Markdown、Git、Python unittest、PowerShell

---

### Task 1: 重写复试展示型 README

**Files:**
- Modify: `README.md`

- [x] **Step 1: 将 README 改成面试优先的信息结构**

按以下顺序编排：项目摘要、复试速览、研究问题与方法、数据流、物理模型、PINN 实现、确定性 PDE 验证、结果、目录结构、复现命令、局限、复试阅读路径。

- [x] **Step 2: 校正技术表述**

明确写出：Thermal-90 SDK 输出逐像素温度；OpenCV 只做显示；ROI 由 NumPy 处理；PINN 学习 `alpha` 并由 `k = rho * cp * alpha` 换算；真实数据正式结论优先采用确定性子域估计器。

- [x] **Step 3: 检查 README 引用文件存在**

Run:

```powershell
$links = Select-String -LiteralPath README.md -Pattern '\]\(([^)#]+)' -AllMatches
$paths = foreach ($line in $links) { foreach ($match in $line.Matches) { $match.Groups[1].Value } }
$paths | Where-Object { $_ -notmatch '^(https?://|#)' } | ForEach-Object { if (-not (Test-Path -LiteralPath $_)) { "MISSING: $_" } }
```

Expected: no `MISSING` output.

### Task 2: 收紧 Git 文件边界

**Files:**
- Modify: `.gitignore`

- [x] **Step 1: 忽略本机配置和生成资产**

加入规则：

```gitignore
.codex/
data/raw/*
!data/raw/.gitkeep
data/derived/*
!data/derived/.gitkeep
outputs/
```

- [x] **Step 2: 核对必要未跟踪文件**

Run:

```powershell
git -c core.quotepath=false status --short --untracked-files=all
```

Expected: 大量 `data/` 和 `outputs/` 文件不再出现；必要的配置、文档和计划仍可见。

### Task 3: 验证并暂存必要文件

**Files:**
- Modify: `README.md`
- Modify: `.gitignore`
- Add: `configs/synthetic_pinn_304_noise0p1.json`
- Modify: `docs/05-实验复现操作手册.md`
- Modify: `docs/09-新数据参数记录.md`
- Add: `docs/14-结课presentation初稿.md`
- Add: `docs/superpowers/plans/2026-09-12-readme-interview-reorganization.md`

- [x] **Step 1: 运行完整测试**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: 现有可发现测试全部通过，退出码为 0。

- [x] **Step 2: 仅暂存必要文件**

Run:

```powershell
git add README.md .gitignore configs/synthetic_pinn_304_noise0p1.json "docs/05-实验复现操作手册.md" "docs/09-新数据参数记录.md" "docs/14-结课presentation初稿.md" "docs/superpowers/plans/2026-09-12-readme-interview-reorganization.md"
```

- [x] **Step 3: 复核暂存区**

Run:

```powershell
git -c core.quotepath=false diff --cached --name-status
git diff --cached --check
```

Expected: 暂存区只包含上述文件，不包含 `data/`、`outputs/`、`.codex/` 或 `tests/test_extract_rod_profile.py` 删除操作。

### Task 4: 提交并推送

**Files:**
- No additional file changes

- [x] **Step 1: 创建提交**

Run:

```powershell
git commit -m "整理复试项目说明与必要文档"
```

Expected: commit succeeds and lists only reviewed files.

- [x] **Step 2: 推送当前分支**

Run:

```powershell
git push origin codex/real-data-pde-estimator
```

Expected: remote branch advances to the new commit.

- [x] **Step 3: 核对远端与剩余本地改动**

Run:

```powershell
git status -sb
git log -2 --oneline --decorate
```

Expected: 当前分支与远端同步；剩余未提交项只有明确排除的用户工作树改动。
