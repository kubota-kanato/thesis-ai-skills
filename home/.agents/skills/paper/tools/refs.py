"""DOI から書誌を引いて論文フォルダに保存し、地質学雑誌の書式で引用文献リストを作る。

    python refs.py fetch <DOI> [<DOI> ...]          書誌を引き、論文フォルダを作って 書誌.json を置く
    python refs.py list  <DOI> [<DOI> ...]          引用文献リストを書き出す（フォルダは作らない）
    python refs.py list  --all                      論文フォルダにある書誌すべてで作る
    python refs.py index                            文献一覧.md を作り直し、フォルダ名の状態をそろえる

オプション
    --root <パス>    論文フォルダを置く場所。既定は C:\\dev\\卒論\\論文。文献一覧.md はその1つ上に置く
    --text           list の出力を飾りなしの文字にする（既定は Markdown。誌名を *斜体*、巻を **太字**）
    -o <パス>        list の出力をファイルに書く（UTF-8）

書誌の引き方
    1. JaLC の API（J-STAGE の論文。日本語と英語の両方の書誌が取れる）
    2. 1で見つからなければ doi.org（Crossref・DataCite。英語の書誌）
論文フォルダの名前は {状態}_{題名}。状態は中のファイルで決まり、index のたびにそろえる。
    未入手：論文.pdf が無い / 未処理：論文.pdf はある / 処理済み：解説.html まで作った
中の 書誌.json で DOI を探すので、題名の部分は改名してよい。
API キーは要らない。料金はかからない。
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

DEFAULT_ROOT = r'C:\dev\卒論\論文'
UA = 'thesis-ai-skills/1.0 (refs.py; geology student reference tool)'

# 地質学雑誌の細則4の例に出てくる誌名だけを、略記を確かめたものとして持つ。
# ここに無い誌名は正式名のまま出し、UBC の略記表で確かめるよう警告する。
ABBR_EN = {
    'journal of the geological society of japan': 'J. Geol. Soc. Japan',
    'the journal of the geological society of japan': 'J. Geol. Soc. Japan',
    'earth science (chikyu kagaku)': 'Earth Sci. (Chikyu Kagaku)',
    'journal of geophysical research': 'J. Geophys. Res.',
    'geophysical research letters': 'Geophys. Res. Lett.',
    'annales geophysicae': 'Ann. Geophys.',
    'journal of the geological society of korea': 'J. Geol. Soc. Korea',
}
ABBR_JA = {'地質学雑誌': '地質雑'}


# ---------------------------------------------------------------- 取得

def norm_doi(s):
    s = s.strip()
    s = re.sub(r'^(https?://(dx\.)?doi\.org/|doi:\s*)', '', s, flags=re.I)
    return s.strip().rstrip('.')


def http_json(url, accept='application/json'):
    req = urllib.request.Request(url, headers={'Accept': accept, 'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except json.JSONDecodeError:
        return None


def from_jalc(doi):
    j = http_json('https://api.japanlinkcenter.org/dois/' + urllib.parse.quote(doi, safe=''))
    if not j or j.get('status') != 'OK':
        return None
    d = j['data']
    titles = {t.get('lang'): t.get('title') for t in d.get('title_list', [])}
    authors = []
    for c in sorted(d.get('creator_list', []), key=lambda c: int(c.get('sequence', 0) or 0)):
        names = {n.get('lang'): n for n in c.get('names', [])}
        ja, en = names.get('ja', {}), names.get('en', {})
        authors.append({'ja_family': ja.get('last_name', ''), 'ja_given': ja.get('first_name', ''),
                        'family': en.get('last_name', ''), 'given': en.get('first_name', '')})
    jt = d.get('journal_title_name_list', [])
    def pick(lang, typ):
        for x in jt:
            if x.get('lang') == lang and x.get('type') == typ:
                return x.get('journal_title_name', '')
        return ''
    fp, lp = d.get('first_page', ''), d.get('last_page', '')
    pub = d.get('publication_date', {}) or {}
    return {
        'doi': doi, 'source': 'JaLC', 'type': 'journal-article',
        'year': str(pub.get('publication_year', '')),
        'title_ja': titles.get('ja', ''), 'title_en': titles.get('en', ''),
        'authors': authors,
        'journal_ja': pick('ja', 'full'), 'journal_en': pick('en', 'full'),
        'volume': d.get('volume', ''), 'issue': d.get('issue', ''),
        'pages': fp + ('–' + lp if lp and lp != fp else ''), 'article_number': '',
        'publisher': '', 'container': '', 'editors': [],
    }


def from_doiorg(doi):
    j = http_json('https://doi.org/' + doi, accept='application/vnd.citationstyles.csl+json')
    if not j:
        return None
    def first(v):
        return (v[0] if v else '') if isinstance(v, list) else (v or '')
    year = ''
    for k in ('published-print', 'issued', 'published-online', 'published'):
        dp = (j.get(k) or {}).get('date-parts')
        if dp and dp[0] and dp[0][0]:
            year = str(dp[0][0]); break
    authors = [{'ja_family': '', 'ja_given': '', 'family': a.get('family', a.get('literal', '')),
                'given': a.get('given', '')} for a in j.get('author', [])]
    editors = [{'family': a.get('family', a.get('literal', '')), 'given': a.get('given', '')} for a in j.get('editor', [])]
    typ = j.get('type', '')
    return {
        'doi': doi, 'source': 'doi.org', 'type': typ, 'year': year,
        'title_ja': '', 'title_en': first(j.get('title')),
        'authors': authors,
        'journal_ja': '', 'journal_en': first(j.get('container-title')) if typ == 'journal-article' else '',
        'volume': str(j.get('volume', '') or ''), 'issue': str(j.get('issue', '') or ''),
        'pages': (j.get('page') or '').replace('-', '–'), 'article_number': str(j.get('article-number', '') or ''),
        'publisher': j.get('publisher', ''),
        'container': first(j.get('container-title')) if typ != 'journal-article' else '',
        'editors': editors,
    }


BIB = '書誌.json'


def saved(root):
    """論文\\*\\書誌.json を読み、{DOIの小文字: (フォルダ, 書誌)} を返す。フォルダを改名しても見つかる"""
    found = {}
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name, BIB)
            if os.path.isfile(p):
                rec = json.load(io.open(p, encoding='utf-8'))
                found[rec['doi'].lower()] = (os.path.join(root, name), rec)
    return found


def lookup(doi):
    rec = from_jalc(doi)
    if rec is None or not (rec['title_ja'] or rec['title_en']):
        time.sleep(0.5)
        rec = from_doiorg(doi)
    if rec is not None:
        rec['fetched'] = date.today().isoformat()
    time.sleep(0.5)
    return rec


INDEX = '文献一覧.md'
INDEX_HEAD = ['フォルダ', '状態', '著者', '年', '題名', 'DOI', '位置づけ', 'メモ']
STATES = ('未入手', '未処理', '処理済み')
PDF = '論文.pdf'
DONE = '解説.html'


def index_path(root):
    return os.path.join(os.path.dirname(os.path.abspath(root)), INDEX)


def safe_title(rec):
    """フォルダ名に使える題名。Windows で使えない記号を外し、40字で切る"""
    t = rec.get('title_ja') or rec.get('title_en') or 'untitled'
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'[\\/:*?"<>|]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip().rstrip('.')
    if len(t) > 40:
        cut = t[:40]
        # 英語の題名は単語の途中で切らない
        t = cut[:cut.rfind(' ')] if ' ' in cut[20:] else cut
    return t.rstrip() or 'untitled'


def state_of(folder):
    if not os.path.isfile(os.path.join(folder, PDF)):
        return '未入手'
    return '処理済み' if os.path.isfile(os.path.join(folder, DONE)) else '未処理'


def sync_name(folder, rec):
    """フォルダ名の頭の状態を、中のファイルに合わせて付け替える。題名の部分は残す"""
    base = os.path.basename(folder)
    body = base
    for st in STATES:
        if base.startswith(st + '_'):
            body = base[len(st) + 1:]
            break
    want = '%s_%s' % (state_of(folder), body or safe_title(rec))
    if want == base:
        return folder
    parent = os.path.dirname(folder)
    p, n = os.path.join(parent, want), 2
    while os.path.exists(p):
        p, n = os.path.join(parent, '%s (%d)' % (want, n)), n + 1
    os.rename(folder, p)
    print('改名した: %s → %s' % (base, os.path.basename(p)))
    return p


def md_cell(s):
    return str(s or '').replace('|', '／').replace('\n', ' ').strip()


def read_index(root):
    """文献一覧.md の表を読む。DOI のある行は {DOI: 行}、DOI の無い行はそのまま並びで返す"""
    p = index_path(root)
    by_doi, no_doi = {}, []
    if not os.path.isfile(p):
        return by_doi, no_doi
    for line in io.open(p, encoding='utf-8'):
        line = line.strip()
        if not line.startswith('|') or set(line) <= set('|-: '):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if cells[:2] == INDEX_HEAD[:2]:
            continue
        row = dict(zip(INDEX_HEAD, cells + [''] * (len(INDEX_HEAD) - len(cells))))
        doi = row['DOI'].strip('`').lower()
        if doi:
            by_doi[doi] = row
        else:
            no_doi.append(row)
    return by_doi, no_doi


def write_index(root):
    """論文フォルダの 書誌.json から 文献一覧.md を作り直す。位置づけとメモは前の一覧から引き継ぐ"""
    old, no_doi = read_index(root)
    rows = []
    for doi, (folder, rec) in saved(root).items():
        prev = old.get(doi, {})
        folder = sync_name(folder, rec)
        state = state_of(folder)
        au = rec['authors']
        jp = any(a.get('ja_family') for a in au)
        fam = (lambda a: a.get('ja_family', '')) if jp else (lambda a: a.get('family', ''))
        if len(au) > 2:
            who = fam(au[0]) + ('ほか' if jp else ' et al.')
        elif len(au) == 2:
            who = fam(au[0]) + ('・' if jp else ' and ') + fam(au[1])
        else:
            who = fam(au[0]) if au else ''
        name = os.path.basename(folder)
        rows.append({'フォルダ': '[%s](<論文/%s/>)' % (name, name), '状態': state, '著者': who, '年': rec['year'],
                     '題名': rec['title_ja'] or rec['title_en'], 'DOI': rec['doi'],
                     '位置づけ': prev.get('位置づけ', ''), 'メモ': prev.get('メモ', '')})
    order = {st: i for i, st in enumerate(STATES)}
    rows.sort(key=lambda r: (order.get(r['状態'], 9), r['フォルダ'].lower()))
    rows += no_doi
    out = ['# 文献一覧', '',
           '状態は `未入手`（論文.pdf が無い）、`未処理`（論文.pdf はある）、`処理済み`（解説.html まで作った）の3つ。フォルダの中身から自動で決まる。',
           '位置づけ（支持する・反する・手法の参考・背景）とメモの列は手で書き換えてよい。ほかの列は `refs.py index` で作り直される。DOI の無い文献は、行を手で足す。', '',
           '| ' + ' | '.join(INDEX_HEAD) + ' |', '|' + '---|' * len(INDEX_HEAD)]
    for r in rows:
        out.append('| ' + ' | '.join(md_cell(r.get(h)) for h in INDEX_HEAD) + ' |')
    io.open(index_path(root), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    return len(rows)


def new_folder(root, rec):
    """論文フォルダを 未入手_{題名} で作る。同じ名前があれば (2), (3) を付ける"""
    base = '未入手_' + safe_title(rec)
    p, n = os.path.join(root, base), 2
    while os.path.exists(p):
        p, n = os.path.join(root, '%s (%d)' % (base, n)), n + 1
    os.makedirs(p)
    return p


# ---------------------------------------------------------------- 書式（地質学雑誌 細則4）

def has_cjk(s):
    return bool(re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', s or ''))


def initials(given):
    # "Joseph K." → "J. K."、"Ji-Hoon" → "J.-H."
    out = []
    for part in given.replace('.', ' ').split():
        out.append('-'.join(p[0].upper() + '.' for p in part.split('-') if p))
    return ' '.join(out)


def en_name(a):
    g = initials(a.get('given', ''))
    return a.get('family', '') + (', ' + g if g else '')


def ja_name(a):
    f, g = a.get('ja_family', ''), a.get('ja_given', '')
    return f + (' ' if len(f) == 1 or len(g) == 1 else '') + g if g else f


def join_en(names):
    if len(names) > 7:
        return ', '.join(names[:6]) + ',...' + names[-1]
    if len(names) == 1:
        return names[0]
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def join_ja(names):
    if len(names) > 7:
        return '・'.join(names[:6]) + '......' + names[-1]
    return '・'.join(names)


def journal_abbr(name, warn):
    k = name.lower().strip()
    if k in ABBR_EN:
        return ABBR_EN[k]
    if name:
        warn.add(name)
    return name


def tail(r, md, journal):
    j = ('*%s*' % journal) if md and journal else journal
    vol = ('**%s**' % r['volume']) if md and r['volume'] else r['volume']
    parts = [p for p in (j, vol) if p]
    if r['pages']:
        parts.append(r['pages'])
    elif r['article_number']:
        parts.append(r['article_number'] + ', doi:' + r['doi'])
    else:
        parts.append('doi:' + r['doi'])
    return ', '.join(parts) + '.'


def entry(r, md, warn):
    names_en = [en_name(a) for a in r['authors'] if a.get('family')]
    authors_en = join_en(names_en) if names_en else '著者不明'
    t = r['type']
    if t in ('book', 'monograph', 'edited-book'):
        return '%s, %s, %s. %s.' % (authors_en, r['year'], r['title_en'], r['publisher'] or '出版社不明'), ['書籍：総ページ数（例：615p.）と、海外の出版社なら所在地を手で足す']
    if t in ('book-chapter', 'chapter'):
        eds = join_en([en_name(e) for e in r['editors']])
        ed = ('In %s, eds., ' % eds) if eds else 'In '
        return '%s, %s, %s. %s%s, %s, %s.' % (authors_en, r['year'], r['title_en'], ed, r['container'], r['publisher'], r['pages']), []
    notes = []
    jp = any(a.get('ja_family') for a in r['authors']) or has_cjk(r['title_ja'])
    en_journal = journal_abbr(r['journal_en'], warn)
    en_part = '%s, %s, %s. %s' % (authors_en, r['year'], r['title_en'] or '【英語の題名が無い。英訳して末尾に*を付ける】', tail(r, md, en_journal))
    if not jp:
        return en_part, notes
    ja_journal = ABBR_JA.get(r['journal_ja'], r['journal_ja'])
    authors_ja = join_ja([ja_name(a) for a in r['authors']])
    ja_part = '%s, %s, %s. %s' % (authors_ja, r['year'], r['title_ja'], tail(r, False, ja_journal))
    return '%s [%s]' % (ja_part, en_part), notes


def sort_key(r):
    au = r['authors'] or [{}]
    fam = lambda a: (a.get('family') or a.get('ja_family') or '').lower()
    # 著者名のアルファベット順。同じ第1著者なら単独論文を先に年代順、続けて第2著者の順、同じ組なら年代順
    second = fam(au[1]) if len(au) > 1 else ''
    return (fam(au[0]), 0 if len(au) == 1 else 1, second, r['year'])


def intext(r):
    au = r['authors']
    jp = any(a.get('ja_family') for a in au)
    f = (lambda a: a.get('ja_family')) if jp else (lambda a: a.get('family'))
    if not au:
        return '（著者不明，%s）' % r['year']
    if len(au) == 1:
        who = f(au[0])
    elif len(au) == 2:
        who = ('%s・%s' if jp else '%s and %s') % (f(au[0]), f(au[1]))
    else:
        who = f(au[0]) + ('ほか' if jp else ' et al.')
    return '%s（%s）／（%s，%s）' % (who, r['year'], who, r['year'])


# ---------------------------------------------------------------- 本体

def main(argv):
    if len(argv) < 2 or argv[1] not in ('fetch', 'list', 'index'):
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding='utf-8')
    if argv[1] == 'index':
        root = argv[argv.index('--root') + 1] if '--root' in argv else DEFAULT_ROOT
        n = write_index(root)
        print('文献一覧.md を作り直した（%d 件）: %s' % (n, index_path(root)))
        return 0
    cmd, args = argv[1], argv[2:]
    root, out, md, all_ = DEFAULT_ROOT, None, True, False
    dois = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--root':
            root = args[i + 1]; i += 2; continue
        if a == '-o':
            out = args[i + 1]; i += 2; continue
        if a == '--text':
            md = False; i += 1; continue
        if a == '--all':
            all_ = True; i += 1; continue
        dois.append(norm_doi(a)); i += 1
    os.makedirs(root, exist_ok=True)
    have = saved(root)
    if all_:
        dois += [rec['doi'] for _, rec in have.values()]
    seen, uniq = set(), []
    for x in dois:
        if x and x.lower() not in seen:
            seen.add(x.lower()); uniq.append(x)
    if not uniq:
        sys.exit('DOI が1つも無い')

    recs, missing = [], []
    for x in uniq:
        if x.lower() in have:
            folder, r = have[x.lower()]
            if cmd == 'fetch':
                print('すでにある: %s' % folder)
            recs.append(r)
            continue
        try:
            r = lookup(x)
        except Exception as e:  # 通信の失敗は DOI ごとに報告して続ける
            r = None
            print('通信に失敗: %s（%s）' % (x, e), file=sys.stderr)
        if r is None:
            missing.append(x)
            continue
        recs.append(r)
        if cmd == 'fetch':
            folder = new_folder(root, r)
            json.dump(r, io.open(os.path.join(folder, BIB), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('作った: %s\\%s（%s, %s）' % (folder, BIB, r['title_ja'] or r['title_en'], r['year']))

    if cmd == 'fetch':
        n = write_index(root)
        print('文献一覧.md を更新した（%d 件）' % n)
        print('論文PDFを手に入れたら、そのフォルダに 論文.pdf の名前で置き、index で文献一覧.md を作り直す')
    else:
        warn, notes = set(), []
        lines, cites = [], []
        for r in sorted(recs, key=sort_key):
            e, n = entry(r, md, warn)
            lines.append(e); notes += ['%s: %s' % (r['doi'], x) for x in n]
            cites.append('- %s　%s' % (intext(r), r['doi']))
        text = '## 引用文献\n\n' + '\n\n'.join(lines) + '\n\n## 本文中の引用の形\n\n' + '\n'.join(cites) + '\n'
        if out:
            io.open(out, 'w', encoding='utf-8').write(text)
            print('書き出した: %s' % out)
        else:
            print(text)
        for w in sorted(warn):
            print('確認：誌名の略記を UBC の表で確かめて置き換える: %s' % w, file=sys.stderr)
        for n in notes:
            print('確認：%s' % n, file=sys.stderr)
        print('確認：題名の大文字・小文字は原典のまま。論文の題名は文頭と固有名詞だけ大文字にする', file=sys.stderr)

    for x in missing:
        print('見つからない DOI: %s（打ち間違いか、DOI の無い文献）' % x, file=sys.stderr)
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
