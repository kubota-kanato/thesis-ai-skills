# -*- coding: utf-8 -*-
"""読む資料の「地の文」の読解負荷を測る。自分の下書きの自己点検専用。

目で見て気づきにくいもの（一文の長さ・漢字の連続・「の」の連鎖・対比構文の反復）
だけを測る。標準ライブラリだけで動く。

**測らないもの: 文長の分散・語彙の多様性・語尾の反復。**
これらは「AIが書いたように見えるか」の指標であって、読みやすさの指標ではない。
文の長さを揃えないために文を伸ばすと、かえって読みにくくなる。
他人の文章がAI生成かどうかの判定にも使わない（文体判定は簡潔に書く書き手を不当に疑う）。

**適用範囲**: 地の文が続く文章（読む資料の説明・考察、報告の本文）。
手順書・チェックリスト・実験プロトコル・仕様は、同じ形の指示が同じ長さで並ぶことに
機能があるので当てない。スライドは本文が文でないので当てない。

使い方:
    python reading-load.py draft.md
    python reading-load.py draft.html     # <p> の中身だけを測る
"""
import html
import re
import sys

SENTENCE_MAX_CHARS = 90    # これを超える文を指さす
KANJI_RUN_MAX = 6          # 漢字がこれを超えて連続する（7字以上）
NO_CHAIN_MIN = 3           # 「の」がこの回数以上連鎖する
ANTITHESIS_MAX = 2         # 「ではなく」が全文でこの回数を超える

KANJI_RUN = re.compile(r'[一-鿿々]{%d,}' % (KANJI_RUN_MAX + 1))
NO_CHAIN = re.compile(r'(?:[^\s、。，．「」（）]{1,10}の){%d,}' % NO_CHAIN_MIN)
SENT_END = re.compile(r'(?<=[。！？])')
TAG = re.compile(r'<[^>]+>')
CODEBLOCK = re.compile(r'```.*?```', re.S)

# 冗長表現・重言・中身のない抽象語（antipatterns.md C-1 / C-2 / C-3 / C-9）
PHRASES = [
    ('することができ', '「〜することができる」', '「〜できる」に'),
    (r'を行(う|い|った|います)', '「〜を行う」', '動詞に戻す（「検討を行う」→「検討する」）'),
    ('まず最初に', '「まず最初に」', '「まず」に'),
    (r'約[0-9０-９]+[割％%]程度', '「約〜割程度」', '「約」と「程度」の重複'),
    ('過半数を超え', '「過半数を超える」', '重言'),
    (r'(・・・|、、、|\.\.\.)', '三点リーダ', '「……」にする（C-9）'),
    ('最適化', '「最適化」', '中身のない抽象語（C-1）。何を最大化し何を制約とするか書く'),
    ('効率化', '「効率化」', '中身のない抽象語（C-1）'),
    ('の実現', '「〜の実現」', '動詞に戻す（C-2）'),
]


def load(path):
    """地の文だけを取り出す。見出し・箇条書き・表は測定対象外（揃っているほうが正しい）。"""
    with open(path, encoding='utf-8') as f:
        t = f.read()
    t = CODEBLOCK.sub('', t)

    if path.lower().endswith(('.html', '.htm')):
        # HTMLは <p> の中身だけを抜く。タグごと文として数えると誤検出だらけになる
        # （実測: 786件中782件がタグ由来）。li・td・見出しはそもそも測定対象外
        t = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', t, flags=re.S | re.I)
        keep = []
        # <p(\s...)?> だけを拾う。<p[^>]*> だと <pre> にも当たってコードを地の文として数える
        for para in re.findall(r'<p(?:\s[^>]*)?>(.*?)</p>', t, flags=re.S | re.I):
            para = html.unescape(TAG.sub('', para)).strip()
            if para:
                keep.append(para)
        return '\n'.join(keep)

    keep = []
    for line in t.splitlines():
        st = line.strip()
        if not st or st.startswith(('#', '-', '*', '|', '>', '![')):
            continue
        keep.append(st)
    return '\n'.join(keep)


def sentences(text):
    out = []
    for para in [p for p in text.split('\n') if p.strip()]:
        out.extend(s.strip() for s in SENT_END.split(para) if s.strip())
    return out


def main(path):
    text = load(path)
    flat = sentences(text)
    if len(flat) < 5:
        print('地の文が5文未満。測っても意味がないので中止する。')
        return

    found = 0

    print('=== sentence_too_long（一文が長い。切る）===')
    n = 0
    for i, s in enumerate(flat, 1):
        if len(s) > SENTENCE_MAX_CHARS:
            n += 1
            print('  第%d文 %d字: %s…' % (i, len(s), s[:45]))
    print('  なし' if not n else '  %d件' % n)
    found += n

    print('=== kanji_run（漢字の連続。語の切れ目が読めるか）===')
    n = 0
    for i, s in enumerate(flat, 1):
        for m in KANJI_RUN.finditer(s):
            n += 1
            print('  第%d文: %s（%d字）' % (i, m.group(0), len(m.group(0))))
    print('  なし' if not n else '  %d件' % n)
    found += n

    print('=== no_chain（「の」の連鎖。係り受けが追いにくい）===')
    n = 0
    for i, s in enumerate(flat, 1):
        for m in NO_CHAIN.finditer(s):
            n += 1
            print('  第%d文: %s' % (i, m.group(0)))
    print('  なし' if not n else '  %d件' % n)
    found += n

    print('=== antithesis_repetition（「AではなくB」の反復）===')
    n = len(re.findall('ではなく', text))
    if n > ANTITHESIS_MAX:
        print('  「ではなく」×%d回。「Bです」で足りないか見る' % n)
        found += n
    else:
        print('  %d回（%d回までは許容）' % (n, ANTITHESIS_MAX))

    print('=== 冗長表現・抽象語 ===')
    n = 0
    for pat, label, why in PHRASES:
        c = len(re.findall(pat, text))
        if c:
            n += c
            print('  %s ×%d — %s' % (label, c, why))
    print('  なし' if not n else '  %d件' % n)
    found += n

    print()
    if not found:
        print('指摘なし。')
    print('指摘は「エラー」ではなく「疑いの提示」。直さないと決めたら理由を持って残す。')


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
