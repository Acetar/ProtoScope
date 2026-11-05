# -*- coding: utf-8 -*-
"""校验设计文档的结构完整性：代码围栏配平、标题层级、表格列数、残留措辞。"""
import io
import re
import sys

P = 'docs/设计文档.md'
lines = io.open(P, encoding='utf-8').read().split('\n')

problems = []

# 1. 代码围栏必须成对，且 ``` 行数应为偶数
fences = [i + 1 for i, ln in enumerate(lines) if ln.lstrip().startswith('```')]
if len(fences) % 2:
    problems.append(f'代码围栏数量为奇数：{len(fences)}')

# 2. 标题层级：h2 不跳级，h3 必须在某个 h2 之下
levels = []
for i, ln in enumerate(lines):
    m = re.match(r'^(#{2,4}) ', ln)
    if m:
        levels.append((i + 1, len(m.group(1)), ln.strip()))
prev = 2
for no, lv, text in levels:
    if lv > prev + 1:
        problems.append(f'第 {no} 行标题跳级 h{prev} -> h{lv}: {text}')
    prev = lv

# 3. 表格：同一张表内列数应一致（跳过代码块内）
in_code = False
table_cols = None
table_start = 0
for i, ln in enumerate(lines):
    if ln.lstrip().startswith('```'):
        in_code = not in_code
        table_cols = None
        continue
    if in_code:
        continue
    if ln.strip().startswith('|') and ln.strip().endswith('|'):
        cols = len(re.findall(r'(?<!\\)\|', ln)) - 1
        if table_cols is None:
            table_cols = cols
            table_start = i + 1
        elif cols != table_cols:
            problems.append(f'第 {i+1} 行表格列数 {cols} != 表头 {table_cols}（表起始 {table_start}）')
    else:
        table_cols = None

# 4. 残留的旧口径措辞
residue = [
    ('四视图联动', '应改为三视图'),
    ('/healthz', '实际路径是 /api/health'),
    ('教师看板', '教师端已取消'),
]
# 这些词允许出现在"解释为什么取消"的语境里，只做提示不做失败
hints = ['教师端', '班级看板', '教师审核']
body = '\n'.join(
    ln for ln in lines
)  # 含代码块，便于发现代码注释里的残留
for word, why in residue:
    hits = [i + 1 for i, ln in enumerate(lines) if word in ln]
    if hits:
        problems.append(f'残留「{word}」（{why}）：行 {hits[:8]}')

# 5. 必备章节存在性
required = [
    '## 摘要', '## 1 项目概述', '### 1.4 范围边界', '### 1.6 本期真实交付',
    '## 2 需求分析', '### 2.1 用户角色',
    '### 3.0 信息架构', '### 3.2', '## 4 ', '### 4.5 ', '### 4.6 ',
    '### 4.7 ', '### 4.8 ', '### 4.9 ',
    '## 5 数据设计', '### 5.4 ', '### 6.2 接口清单',
    '## 11 答辩演示脚本', '### 11.1 ', '## 12 创新点与难点',
    '## 13 风险与应对', '## 14 附录', '### 14.5 ', '## 15 已实现原型（代码对照）',
    '## 附：文档修订记录',
]
for r in required:
    if r not in body:
        problems.append(f'缺少章节：{r}')

print(f'总行数 {len(lines)}，代码围栏 {len(fences)} 个，mermaid {body.count("```mermaid")} 个')
for w in hints:
    hits = [i + 1 for i, ln in enumerate(lines) if w in ln]
    if hits:
        print(f'提示：「{w}」出现在行 {hits[:10]}（确认都在"为什么取消"的语境里）')
if problems:
    print('发现 %d 处问题：' % len(problems))
    for p_ in problems:
        print(' -', p_)
    sys.exit(1)
print('结构检查通过')
