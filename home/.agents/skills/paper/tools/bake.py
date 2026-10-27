# 編集用HTMLの src="IMG:ファイル名" を base64 に置き換えて、単体で開けるHTMLを書き出す。
#
#   python $env:USERPROFILE\.agents\skills\paper\tools\bake.py <論文フォルダ> <入力html> <出力html>
#   例: python $env:USERPROFILE\.agents\skills\paper\tools\bake.py "未処理_浦幌層群の凝灰岩のU-Pb年代" 作業\解説_src.html 解説.html
#
# 画像は <論文フォルダ>\挿し絵 と <論文フォルダ>\作業\表示用（表示用に縮小した図）から探す。
import base64, io, os, re, sys

if len(sys.argv) != 4:
    sys.exit(__doc__ or 'usage: bake.py <論文フォルダ> <入力html> <出力html>')

paper = os.path.abspath(sys.argv[1])
src   = sys.argv[2] if os.path.isabs(sys.argv[2]) else os.path.join(paper, sys.argv[2])
out   = sys.argv[3] if os.path.isabs(sys.argv[3]) else os.path.join(paper, sys.argv[3])
dirs  = [os.path.join(paper, '挿し絵'), os.path.join(paper, '作業', '表示用')]

html = io.open(src, encoding='utf-8').read()
missing = []

def rep(m):
    name = m.group(1)
    for d in dirs:
        p = os.path.join(d, name)
        if os.path.exists(p):
            mime = 'image/jpeg' if name.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
            b64 = base64.b64encode(io.open(p, 'rb').read()).decode('ascii')
            return 'src="data:%s;base64,%s"' % (mime, b64)
    missing.append(name)
    return m.group(0)

# 図の欄（3カラム目）を差し込む。中身は figpane.html
figpane = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figpane.html'), encoding='utf-8').read()
if '</body>' in html and 'figpane.html' not in html:
    html = html.replace('</body>', figpane + '</body>', 1)

baked = re.sub(r'src="IMG:([^"]+)"', rep, html)
if missing:
    sys.exit('画像が見つからない: ' + ', '.join(missing))

# 焼き込み後に外部参照が残っていないか検査する（他人のPC・オフラインで図が出ない事故を防ぐ）。
# CSS・HTMLのコメントには読み方の説明として src="..." が書いてあるので、先に落としてから見る
checked = re.sub(r'/\*.*?\*/|<!--.*?-->', '', baked, flags=re.S)
leftover = [s for s in re.findall(r'src="([^"]{0,60})', checked) if not s.startswith('data:')]
if leftover:
    sys.exit('data: 以外の src が残っている: ' + ', '.join(leftover))

io.open(out, 'w', encoding='utf-8').write(baked)
print('%s  %d KB' % (out, os.path.getsize(out) // 1024))
