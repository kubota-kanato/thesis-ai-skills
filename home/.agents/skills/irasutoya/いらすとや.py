# -*- coding: utf-8 -*-
"""いらすとやの素材を検索して落とす。

    python いらすとや.py 検索 縄文 土器 竪穴住居
    python いらすとや.py 索引 土器                    ← 既に貯めた索引を offline 検索
    python いらすとや.py 取得 img doki_joumon doguu
    python いらすとや.py 取得 img --s800 doki_joumon  ← 大きめが要るとき（既定 s400）

検索するとヒットした素材が、このスクリプトの隣の `_索引.tsv` に貯まる。
取得はその索引から slug を引いて落とすので、先に検索しておく。
索引はプロジェクトをまたいで共有される（叩くほど育つ）。

なぜフィード API を使うか:
いらすとやのサイト内検索（/search?q=...）は JavaScript で描画されるので、
HTML を取っても画像 URL が入っていない。Blogger のフィード API なら
サーバ側で JSON が返ってきて、素材名と画像 URL がそのまま読める。
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
索引 = os.path.join(HERE, '_索引.tsv')
FEED = 'https://www.irasutoya.com/feeds/posts/default?q=%s&alt=json&max-results=%d'
UA = {'User-Agent': 'Mozilla/5.0'}


def 検索(語, 件数=25):
    """(素材名, 画像URL) のリストを返す。"""
    url = FEED % (urllib.parse.quote(語), 件数)
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=30).read().decode('utf-8')
    except Exception as e:
        print('  検索できなかった（%s）: %s' % (語, e))
        return []
    out = []
    for e in json.loads(raw)['feed'].get('entry', []):
        画像 = re.findall(r'https://blogger\.googleusercontent\.com/img/[^"\']+?\.png',
                          e['content']['$t'])
        if 画像:
            out.append((e['title']['$t'], 画像[0]))
    return out


def 索引を読む():
    d = {}
    if os.path.exists(索引):
        for ln in io.open(索引, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t')
            if len(p) >= 3:
                d[p[0]] = (p[1], p[2])      # slug -> (素材名, URL)
    return d


def 索引を書く(d):
    with io.open(索引, 'w', encoding='utf-8', newline='\n') as f:
        for slug in sorted(d):
            f.write('%s\t%s\t%s\n' % (slug, d[slug][0], d[slug][1]))


def cmd検索(語群):
    d = 索引を読む()
    新規 = 0
    for n, 語 in enumerate(語群):
        if n:
            time.sleep(1.5)     # 続けて叩くと弾かれて 0 件が返る
        件 = 検索(語)
        print('=== %s （%d件） ===' % (語, len(件)))
        for 名, url in 件:
            slug = url.rsplit('/', 1)[-1][:-4]
            if slug not in d:
                新規 += 1
            d[slug] = (名, url)
            print('  %-42s %s' % (slug, 名))
    索引を書く(d)
    print('-' * 64)
    print('索引 %d 件（うち新規 %d 件）-> %s' % (len(d), 新規, 索引))


def cmd索引(語群):
    """通信せず、貯めた索引の中だけを引く。"""
    d = 索引を読む()
    for 語 in 語群:
        件 = [(s, d[s][0]) for s in sorted(d) if 語 in d[s][0] or 語.lower() in s.lower()]
        print('=== %s （%d件） ===' % (語, len(件)))
        for slug, 名 in 件:
            print('  %-42s %s' % (slug, 名))


def cmd取得(出力先, slug群, サイズ='s400'):
    d = 索引を読む()
    出力先 = os.path.abspath(出力先)      # 相対パスは呼んだ場所からの相対
    os.makedirs(出力先, exist_ok=True)
    済, 失敗 = 0, []
    for slug in slug群:
        if slug not in d:
            失敗.append(slug + '（索引に無い。先に検索する）')
            continue
        名, url = d[slug]
        url = re.sub(r'/s\d+/', '/%s/' % サイズ, url)
        dst = os.path.join(出力先, slug + '.png')
        try:
            data = urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30).read()
            io.open(dst, 'wb').write(data)
            print('  %-42s %6.1f KB  %s' % (slug, len(data) / 1024, 名))
            済 += 1
        except Exception as e:
            失敗.append('%s（%s）' % (slug, e))
    print('-' * 64)
    print('%d 枚を %s に置いた' % (済, 出力先))
    for f in 失敗:
        print('  取れなかった: %s' % f)


def main():
    引数 = sys.argv[1:]
    サイズ = 's400'
    for a in list(引数):
        if re.match(r'^--s\d+$', a):
            サイズ = a[2:]
            引数.remove(a)
    if len(引数) < 2:
        sys.exit(__doc__)
    cmd, 残り = 引数[0], 引数[1:]
    if cmd == '検索':
        cmd検索(残り)
    elif cmd == '索引':
        cmd索引(残り)
    elif cmd == '取得':
        cmd取得(残り[0], 残り[1:], サイズ)
    else:
        sys.exit('検索 / 索引 / 取得 のどれか')


if __name__ == '__main__':
    main()
