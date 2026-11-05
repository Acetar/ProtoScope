# -*- coding: utf-8 -*-
"""Markdown → DocxXML 转换器（针对 docs/设计文档.md 用到的子集）。

支持：标题、段落、无序/有序列表（含两级嵌套）、任务列表、表格、围栏代码块、
引用块、分隔线；mermaid 围栏替换成已渲染的 PNG（<img path=.../>）。
行内：**加粗**、`代码`、[文字](链接)。
"""
import io
import os
import re
import sys

SRC = 'docs/设计文档.md'
DST = '.tmp/doc.xml'
FIG_DIR = './.tmp/mm/out'


def esc(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def inline(s: str) -> str:
    """行内元素 → DocxXML 片段。先保护行内代码，再转义，再套标签。"""
    slots = []

    def stash(m):
        slots.append(esc(m.group(1)))
        return f'\x00{len(slots) - 1}\x00'

    s = re.sub(r'`([^`]+)`', stash, s)
    s = esc(s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\x00(\d+)\x00', lambda m: f'<code>{slots[int(m.group(1))]}</code>', s)
    return s


def split_row(line: str):
    """按未转义的 | 切分表格行，去掉首尾空串。"""
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|') and not line.endswith('\\|'):
        line = line[:-1]
    cells, cur, i = [], '', 0
    while i < len(line):
        if line[i] == '\\' and i + 1 < len(line) and line[i + 1] == '|':
            cur += '|'
            i += 2
            continue
        if line[i] == '|':
            cells.append(cur.strip())
            cur = ''
            i += 1
            continue
        cur += line[i]
        i += 1
    cells.append(cur.strip())
    return cells


CJK = re.compile(r'[\u3000-\u9fff\uff00-\uffef]')


def join_lines(lines):
    out = ''
    for idx, ln in enumerate(lines):
        hard = ln.endswith('  ')
        ln = ln.rstrip()
        if idx == 0:
            out = ln
            continue
        prev = out[-1:] if out else ''
        cur = ln[:1]
        if CJK.match(prev or 'a') or CJK.match(cur or 'a'):
            out += ln
        else:
            out += ' ' + ln
    return out


def convert(md: str) -> str:
    lines = md.split('\n')
    out = []
    i = 0
    n = len(lines)
    fig = 0
    cur_head = ''     # 当前所在小节标题，用于图片图注
    list_stack = []   # [(kind, indent)]

    def close_lists(to_indent=-1):
        while list_stack and list_stack[-1][1] > to_indent:
            kind = list_stack.pop()[0]
            out.append(f'</{kind}>')

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # ---- 围栏代码块 ----
        if stripped.startswith('```'):
            close_lists()
            lang = stripped[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1
            body = '\n'.join(buf)
            if lang == 'mermaid':
                fig += 1
                heads = re.findall(r'^#{1,4} .+$', '\n'.join(out[-400:]) or '', flags=re.M)
                cap = re.sub(r'^#+\s*', '', heads[-1]).strip() if heads else f'图 {fig}'
                out.append(f'<img path="@{FIG_DIR}/m{fig}.png" caption="{esc(cap)}"/>')
            else:
                lang_attr = f' lang="{esc(lang)}"' if lang else ''
                out.append(f'<pre{lang_attr}><code>{esc(body)}</code></pre>')
            continue

        # ---- 空行 ----
        if not stripped:
            close_lists()
            i += 1
            continue

        # ---- 分隔线 ----
        if re.fullmatch(r'-{3,}|\*{3,}', stripped):
            close_lists()
            out.append('<hr/>')
            i += 1
            continue

        # ---- 标题 ----
        m = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if m:
            close_lists()
            level = max(1, min(len(m.group(1)) - 1, 6))   # 文档标题由 --title 承担，层级整体上提一级
            cur_head = m.group(2).strip()
            out.append(f'<h{level}>{inline(cur_head)}</h{level}>')
            i += 1
            continue

        # ---- 表格 ----
        if stripped.startswith('|') and i + 1 < n and re.match(r'^\|[\s\-:|]+\|?$', lines[i + 1].strip()):
            close_lists()
            header = split_row(stripped)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append(split_row(lines[i].strip()))
                i += 1
            th = ''.join(f'<th><p>{inline(c)}</p></th>' for c in header)
            tb = ''.join(
                '<tr>' + ''.join(f'<td><p>{inline(c)}</p></td>' for c in r) + '</tr>'
                for r in rows
            )
            out.append(f'<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>')
            continue

        # ---- 引用块 ----
        if stripped.startswith('>'):
            close_lists()
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(re.sub(r'^>\s?', '', lines[i].strip()))
                i += 1
            out.append(f'<blockquote><p>{inline(join_lines(buf))}</p></blockquote>')
            continue

        # ---- 任务列表 ----
        mt = re.match(r'^(\s*)[-*+]\s+\[( |x|X)\]\s+(.*)$', line)
        if mt:
            indent = len(mt.group(1))
            close_lists(indent)
            done = 'true' if mt.group(2).lower() == 'x' else 'false'
            out.append(f'<checkbox done="{done}">{inline(mt.group(3))}</checkbox>')
            i += 1
            continue

        # ---- 无序列表 ----
        mb = re.match(r'^(\s*)[-*+]\s+(.*)$', line)
        if mb:
            indent = len(mb.group(1))
            close_lists(indent)
            if not list_stack or list_stack[-1][1] < indent:
                out.append('<ul>')
                list_stack.append(('ul', indent))
            out.append(f'<li><p>{inline(mb.group(2))}</p>')
            i += 1
            # 允许紧跟的下一行是普通文本时并入本项
            while i < n and lines[i].strip() and not re.match(r'^(\s*)([-*+]|\d+\.)\s', lines[i]) \
                    and not lines[i].strip().startswith(('|', '#', '>', '```')):
                out[-1] = out[-1][:-4] + inline(lines[i].strip()) + '</p>'
                i += 1
            out[-1] = out[-1] + '</li>'
            continue

        # ---- 有序列表 ----
        mo = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line)
        if mo:
            indent = len(mo.group(1))
            close_lists(indent)
            if not list_stack or list_stack[-1][1] < indent:
                out.append('<ol>')
                list_stack.append(('ol', indent))
            out.append(f'<li><p>{inline(mo.group(3))}</p></li>')
            i += 1
            continue

        # ---- 普通段落 ----
        close_lists()
        buf = []
        while i < n and lines[i].strip() and not re.match(
                r'^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|\||```|-{3,}$|\*{3,}$)', lines[i]):
            buf.append(lines[i])
            i += 1
        if not buf:          # 兜底，避免死循环
            buf.append(lines[i])
            i += 1
        out.append(f'<p>{inline(join_lines(buf))}</p>')

    close_lists()
    return '\n'.join(out)


def main():
    md = io.open(SRC, encoding='utf-8').read()
    lines = md.split('\n')
    # 去掉首行一级标题 + 空行 + "## 设计文档" + 空行（标题通过 --title 传入）
    body = '\n'.join(lines[4:])
    xml = convert(body)
    io.open(DST, 'w', encoding='utf-8', newline='\n').write(xml)
    print('xml chars:', len(xml))
    print('h1:', xml.count('<h1>'), 'h2:', xml.count('<h2>'), 'h3:', xml.count('<h3>'), 'h4:', xml.count('<h4>'))
    print('table:', xml.count('<table>'), 'pre:', xml.count('<pre'), 'img:', xml.count('<img'),
          'checkbox:', xml.count('<checkbox'), 'ul:', xml.count('<ul>'), 'ol:', xml.count('<ol>'))


if __name__ == '__main__':
    main()
