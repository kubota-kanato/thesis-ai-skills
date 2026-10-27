# 図\*.png（フル解像度）を、HTMLに埋め込む用に長辺1500pxのJPEGへ縮小して 作業\表示用 に置く。
# フル解像度のまま base64 にすると HTML が数十MBになって開くのが重くなるため。
#
#   python $env:USERPROFILE\.agents\skills\paper\tools\webfigs.py <論文フォルダ>
import os, sys
from PIL import Image

if len(sys.argv) != 2:
    sys.exit('usage: webfigs.py <論文フォルダ>')

paper = os.path.abspath(sys.argv[1])
src   = os.path.join(paper, '図')
dst   = os.path.join(paper, '作業', '表示用')
os.makedirs(dst, exist_ok=True)

for f in sorted(os.listdir(src)):
    if not f.lower().endswith('.png'):
        continue
    im = Image.open(os.path.join(src, f)).convert('RGB')
    w, h = im.size
    scale = 1500 / max(w, h)
    if scale < 1:
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    o = os.path.join(dst, os.path.splitext(f)[0] + '.jpg')
    im.save(o, 'JPEG', quality=82, optimize=True)
    print('%-14s %4d KB' % (f, os.path.getsize(o) // 1024))
