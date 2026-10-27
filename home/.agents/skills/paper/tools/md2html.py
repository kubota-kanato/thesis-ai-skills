# 日本語訳.md を、doc-design の read.html と同じ体裁の単体HTMLに変換する。
# 図は 作業\表示用 の縮小版を base64 で埋め込むので、出力は1ファイルで完結する。
#
#   python $env:USERPROFILE\.agents\skills\paper\tools\md2html.py <論文フォルダ>
#
# 扱う記法: # ## ### / 段落 / **太字** / *斜体* / `code` / > 引用 / - 箇条書き / | 表 | / ![alt](図/図N.png) / ---
# 画像行の次の段落は figcaption として <figure> にまとめる。
import base64, io, os, re, sys

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'doc-design', 'read.html')  # CSSと目次スクリプトの供給元

if len(sys.argv) != 2:
    sys.exit('usage: md2html.py <論文フォルダ>')

paper = os.path.abspath(sys.argv[1])
MD    = os.path.join(paper, '日本語訳.md')
WEB   = os.path.join(paper, '作業', '表示用')
OUT   = os.path.join(paper, '日本語訳.html')

def inline(s):
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'`([^`]+?)`', r'<code>\1</code>', s)
    return s

def img_tag(alt, path):
    name = os.path.splitext(os.path.basename(path))[0] + '.jpg'
    b64 = base64.b64encode(io.open(os.path.join(WEB, name), 'rb').read()).decode('ascii')
    return '<img src="data:image/jpeg;base64,%s" alt="%s">' % (b64, alt)

lines = io.open(MD, encoding='utf-8').read().split('\n')
body, nav = [], []
i, n, sec = 0, len(lines), 0
pending_img = None
title = 'ノート'

while i < n:
    ln = lines[i].rstrip()

    if not ln.strip() or ln.strip() == '---':
        i += 1; continue

    m = re.match(r'^(#{1,3}) (.+)$', ln)
    if m:
        lvl, txt = len(m.group(1)), m.group(2)
        if lvl == 1:
            title = re.sub(r'[*`]', '', txt)
            body.append('<h1>%s</h1>' % inline(txt))
        else:
            sec += 1
            sid = 's%d' % sec
            body.append('<h%d id="%s">%s</h%d>' % (lvl, sid, inline(txt), lvl))
            nav.append('<a href="#%s"%s>%s</a>'
                       % (sid, ' class="lv3"' if lvl == 3 else '', re.sub(r'[*`]', '', txt)))
        i += 1; continue

    m = re.match(r'^!\[(.*?)\]\((.+?)\)$', ln)
    if m:
        pending_img = img_tag(m.group(1), m.group(2))
        i += 1; continue

    if ln.startswith('> '):
        buf = []
        while i < n and lines[i].startswith('>'):
            buf.append(lines[i].lstrip('>').strip()); i += 1
        body.append('<blockquote>%s</blockquote>' % inline(' '.join(buf)))
        continue

    if ln.startswith('|'):
        rows = []
        while i < n and lines[i].startswith('|'):
            rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
        rows = [r for r in rows if not all(re.fullmatch(r':?-{2,}:?', c) for c in r)]
        t = ['<table class="grid wide">']
        for k, r in enumerate(rows):
            tag = 'th' if k == 0 else 'td'
            t.append('<tr>' + ''.join('<%s>%s</%s>' % (tag, inline(c), tag) for c in r) + '</tr>')
        t.append('</table>')
        body.append('\n'.join(t))
        continue

    if ln.startswith('- '):
        buf = []
        while i < n and lines[i].startswith('- '):
            buf.append(lines[i][2:].strip()); i += 1
        body.append('<ul>\n%s\n</ul>' % '\n'.join('<li>%s</li>' % inline(b) for b in buf))
        continue

    para = inline(ln)
    if pending_img is not None:
        body.append('<figure>%s<figcaption>%s</figcaption></figure>' % (pending_img, para))
        pending_img = None
    else:
        body.append('<p>%s</p>' % para)
    i += 1

tpl    = io.open(TEMPLATE, encoding='utf-8').read()
css    = tpl[tpl.index('<style>'):tpl.index('</style>') + 8]
script = tpl[tpl.index('<script>'):tpl.index('</script>') + 9]

html = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
%s
</head>
<body>
<div id="wrap">
  <nav id="nav">
    <h1>%s</h1>
    <div class="sub">日本語訳</div>
    <input id="q" type="search" placeholder="見出しを絞り込む" autocomplete="off">
    <div id="hit"></div>
%s
  </nav>
  <main>
%s
  </main>
</div>
%s
</body>
</html>
""" % (title, css, title, '\n'.join('    ' + a for a in nav),
       '\n'.join('    ' + b for b in body), script)

# 図の欄（3カラム目）を差し込む。中身は figpane.html
figpane = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figpane.html'), encoding='utf-8').read()
html = html.replace('</body>', figpane + '</body>', 1)

io.open(OUT, 'w', encoding='utf-8').write(html)
print('%s  %d KB  見出し%d' % (OUT, os.path.getsize(OUT) // 1024, len(nav)))
