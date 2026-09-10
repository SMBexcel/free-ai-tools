#!/usr/bin/env python3
"""
build_atlas.py — turn any LLM-wiki vault of linked markdown into atlas.json.

Zero dependencies. Python 3.8+.

    python3 build_atlas.py --vault ./my-vault --out ./site/data/atlas.json

What it does
------------
1. Walks the vault for *.md files.
2. Reads each note's frontmatter for `type` (falls back to the folder name).
3. Reads [[wikilinks]] out of the body — those ARE the graph edges.
4. Emits one atlas.json the static site loads: nodes, links, and the note
   bodies for the reader pane.

Config is optional. Drop a SCHEMA.md in the vault root with a ```yaml atlas
fenced block to set the title, type order/colors, and which folders stay
private (raw sources you do NOT want shipped to the browser).
"""
import argparse, json, os, re, sys, collections, datetime

# ---------------------------------------------------------------- palette
# Assigned in declaration order when SCHEMA.md doesn't name a colour.
PALETTE = ['#e6b54e', '#ff7a3c', '#7ec8ff', '#2fb9a3', '#8b6fc9',
           '#ff5c72', '#9fd356', '#f2a2c0', '#5c9ded', '#d4a373']

WIKILINK = re.compile(r'\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|([^\]]+))?\]\]')
H1       = re.compile(r'^#\s+(.+?)\s*$', re.M)

# Karpathy layer 1 = raw sources: the LLM reads them, the browser never gets
# them. Excluded by default so a vault of transcripts/PDFs can't leak into a
# public atlas.json by accident. Override with `private: []` in SCHEMA.md.
DEFAULT_PRIVATE = {'transcripts', 'raw', 'sources', 'source', 'archive',
                   'pipeline', '.obsidian', '.git', 'node_modules', '.trash'}


def link_target(raw):
    """[[episodes/foo|Alias]] / [[foo.md]] / [[Foo Bar]] -> 'foo' / 'foo-bar'."""
    t = raw.split('|')[0].split('#')[0].strip()
    t = t.replace('\\', '/').rstrip('/').split('/')[-1]
    if t.lower().endswith('.md'):
        t = t[:-3]
    return slugify(t)


def slugify(s):
    s = re.sub(r"['’]", '', s.strip().lower())
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def plural(s):
    """industry -> Industries, note -> Notes, class -> Classes."""
    if s.endswith('y') and not s.endswith(('ay', 'ey', 'iy', 'oy', 'uy')):
        return s[:-1] + 'ies'
    if s.endswith(('s', 'x', 'z', 'ch', 'sh')):
        return s + 'es'
    return s + 's'


def unescape(s):
    """Vault writers sometimes json.dumps a string into YAML, leaving a
    literal \\u2014 in the frontmatter. Decode those rather than render them."""
    if isinstance(s, str) and '\\u' in s:
        try:
            return s.encode('utf-8').decode('unicode_escape')
        except Exception:
            return s
    return s


def singular(s):
    """episodes -> episode, concepts -> concept, industries -> industry."""
    if s.endswith('ies'):
        return s[:-3] + 'y'
    if s.endswith('sses') or s.endswith('shes'):
        return s[:-2]
    if s.endswith('s') and not s.endswith('ss'):
        return s[:-1]
    return s


# ------------------------------------------------------- frontmatter parse
def parse_frontmatter(text):
    """Minimal YAML-subset reader: scalars, inline [a, b] lists, and
    dash-lists. Enough for note frontmatter; no external deps."""
    if not text.startswith('---'):
        return {}, text
    end = text.find('\n---', 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end], text[end + 4:]
    fm, key = {}, None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line.lstrip().startswith('- ') and key:
            fm.setdefault(key, [])
            if isinstance(fm[key], list):
                fm[key].append(line.lstrip()[2:].strip().strip('"\''))
            continue
        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        key = k.strip()
        v = v.strip()
        if v.startswith('[') and v.endswith(']'):
            fm[key] = [x.strip().strip('"\'') for x in v[1:-1].split(',') if x.strip()]
        elif v:
            fm[key] = v.strip('"\'')
        else:
            fm[key] = []
    return fm, body


def load_schema(vault):
    """Optional SCHEMA.md -> ```yaml atlas fenced block (json or key: value)."""
    path = os.path.join(vault, 'SCHEMA.md')
    cfg = {}
    if not os.path.exists(path):
        return cfg
    text = open(path, encoding='utf-8').read()
    m = re.search(r'```(?:yaml|json)\s+atlas\s*\n(.*?)```', text, re.S)
    if not m:
        return cfg
    block = m.group(1)
    try:                                    # JSON is the reliable path
        return json.loads(block)
    except Exception:
        pass
    for line in block.splitlines():         # else key: value / key: [a, b]
        if ':' not in line or line.lstrip().startswith('#'):
            continue
        k, _, v = line.partition(':')
        v = v.strip()
        if v.startswith('[') and v.endswith(']'):
            cfg[k.strip()] = [x.strip().strip('"\'') for x in v[1:-1].split(',') if x.strip()]
        else:
            cfg[k.strip()] = v.strip('"\'')
    return cfg


def first_para(body):
    for chunk in re.split(r'\n\s*\n', body.strip()):
        c = chunk.strip()
        if not c or c.startswith('#') or c.startswith('>') or c.startswith('|'):
            continue
        c = WIKILINK.sub(lambda m: m.group(2) or m.group(1), c)
        c = re.sub(r'[*_`]', '', c).replace('\n', ' ')
        return (c[:197] + '…') if len(c) > 200 else c
    return ''


# --------------------------------------------------------------- the build
def build(vault, out, title=None, subtitle=None, disclaimer=None, bodies=True):
    cfg      = load_schema(vault)
    private  = set(cfg.get('private', DEFAULT_PRIVATE) or [])
    private |= {'.obsidian', '.git', 'node_modules', '.trash'}
    hubs     = cfg.get('hubs', []) or []   # fm fields that become hub nodes
    order    = cfg.get('types', []) or []
    colors   = cfg.get('colors', {}) or {}

    notes, unresolved = {}, collections.Counter()
    by_name = collections.defaultdict(list)   # name -> [node id, ...]
    skipped_private = []

    for root, dirs, files in os.walk(vault):
        skipped_private += [d for d in dirs if d in private]
        dirs[:] = [d for d in dirs if d not in private and not d.startswith('.')]
        rel_dir = os.path.relpath(root, vault)
        for fn in sorted(files):
            if not fn.endswith('.md'):
                continue
            stem = fn[:-3]
            if stem.upper() in ('SCHEMA', 'README', 'INDEX', 'CHATBOT-SPEC'):
                continue
            path = os.path.join(root, fn)
            try:
                text = open(path, encoding='utf-8').read()
            except Exception as e:
                print(f'  ! skip {path}: {e}', file=sys.stderr)
                continue
            fm, body = parse_frontmatter(text)

            folder = '' if rel_dir == '.' else rel_dir.split(os.sep)[0]
            ntype  = fm.get('type') or (singular(folder) if folder else 'note')
            if isinstance(ntype, list):
                ntype = ntype[0] if ntype else 'note'
            ntype = slugify(str(ntype)) or 'note'

            h1    = H1.search(body)
            label = fm.get('title') or fm.get('label') or (h1.group(1) if h1 else stem.replace('-', ' ').title())
            if isinstance(label, list):
                label = label[0] if label else stem
            label = unescape(str(label))

            slug = slugify(stem)
            note = {
                'slug': slug, 'type': ntype, 'label': label,
                'one_liner': unescape(fm.get('summary') or fm.get('one_liner') or first_para(body)),
                'fm': {k: v for k, v in fm.items()
                       if k not in ('type', 'title', 'label', 'summary', 'one_liner')},
                '_body': body.strip(), '_path': os.path.relpath(path, vault),
                '_links': [], '_hubs': [],
            }
            for m in WIKILINK.finditer(body):
                note['_links'].append(link_target(m.group(1)))
            # frontmatter list fields may also name other notes
            for k, v in fm.items():
                if isinstance(v, list) and k not in ('tags', 'aliases'):
                    note['_links'].extend(link_target(str(x)) for x in v)
            # declared hub fields become synthetic nodes (industry, buyer, …)
            for h in hubs:
                v = fm.get(h)
                for one in ([v] if isinstance(v, str) else (v or [])):
                    if str(one).strip():
                        note['_hubs'].append((slugify(h), slugify(str(one)), str(one)))

            nid = f'{ntype}:{slug}'
            if nid in notes:
                print(f'  ! duplicate note "{nid}" — keeping first', file=sys.stderr)
                continue
            notes[nid] = note
            by_name[slug].append(nid)
            by_name[slugify(str(label))].append(nid)

    if not notes:
        sys.exit(f'No markdown notes found under {vault} (checked for *.md, skipping {sorted(private)})')

    # ---- resolve edges -------------------------------------------------
    def resolve(name, prefer):
        """A name can match notes in several folders; prefer the note whose
        type the linker already points at, else the first declared type."""
        hits = by_name.get(name) or []
        if not hits:
            return None
        if len(hits) == 1:
            return hits[0]
        same = [h for h in hits if h.split(':', 1)[0] == prefer]
        if same:
            return same[0]
        if order:
            ranked = sorted(hits, key=lambda h: order.index(h.split(':', 1)[0])
                            if h.split(':', 1)[0] in order else 99)
            return ranked[0]
        return sorted(hits)[0]

    seen, links, hub_labels = set(), [], {}
    for nid, n in notes.items():
        for name in n['_links']:
            tgt = resolve(name, n['type'])
            if not tgt:
                unresolved[name] += 1
                continue
            if tgt == nid:
                continue
            key = tuple(sorted((nid, tgt)))
            if key in seen:
                continue
            seen.add(key)
            links.append({'source': nid, 'target': tgt})
        for htype, hslug, hlabel in n['_hubs']:
            hid = f'{htype}:{hslug}'
            hub_labels[hid] = (htype, hlabel.replace('-', ' ').title())
            key = tuple(sorted((nid, hid)))
            if key in seen:
                continue
            seen.add(key)
            links.append({'source': nid, 'target': hid})

    # ---- size nodes by connectedness ------------------------------------
    deg = collections.Counter()
    for l in links:
        deg[l['source']] += 1
        deg[l['target']] += 1

    nodes = []
    for nid, n in notes.items():
        nodes.append({'id': nid, 'type': n['type'], 'label': n['label'],
                      'slug': n['slug'], 'one_liner': n['one_liner'],
                      'val': round(2 + (deg[nid] ** 0.5) * 1.2, 2)})
    for hid, (htype, hlabel) in sorted(hub_labels.items()):
        nodes.append({'id': hid, 'type': htype, 'label': hlabel,
                      'slug': hid.split(':', 1)[1], 'one_liner': '',
                      'val': round(2.5 + (deg[hid] ** 0.5) * 1.3, 2)})

    # ---- type registry (declared order first, then discovered) ----------
    counts = collections.Counter(n['type'] for n in nodes)
    ordered = [t for t in order if t in counts] + \
              [t for t in sorted(counts, key=lambda t: -counts[t]) if t not in order]
    types = [{'key': t,
              'label': colors.get(t + '_label') or plural(t.replace('-', ' ')).title(),
              'color': colors.get(t) or PALETTE[i % len(PALETTE)],
              'count': counts[t]}
             for i, t in enumerate(ordered)]

    out_notes = {}
    for nid, n in notes.items():
        rec = {k: v for k, v in n.items() if not k.startswith('_')}
        if bodies:
            rec['body'] = n['_body']
        rec['path'] = n['_path']
        out_notes[nid] = rec

    bundle = {
        'meta': {
            'title':      title      or cfg.get('title', 'Second Brain'),
            'subtitle':   subtitle   or cfg.get('subtitle', 'An LLM wiki you can explore as a graph.'),
            'disclaimer': disclaimer or cfg.get('disclaimer',
                          'AI summaries can be wrong — always check the source.'),
            'counts': dict(counts), 'notes': len(nodes), 'links': len(links),
            'generated': datetime.date.today().isoformat(),
        },
        'types': types, 'nodes': nodes, 'links': links, 'notes': out_notes,
    }

    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False)

    kb = os.path.getsize(out) / 1024
    print(f'atlas.json  →  {out}  ({kb:,.0f} KB)')
    print(f'  {len(nodes)} notes · {len(links)} links · {len(types)} types')
    for t in types:
        print(f'    {t["color"]}  {t["key"]:<16} {t["count"]}')
    if skipped_private:
        print(f'  · raw-source folders withheld from the browser: '
              f'{", ".join(sorted(set(skipped_private)))}')
    orphans = [n['id'] for n in nodes if deg[n['id']] == 0]
    if orphans:
        print(f'  ! {len(orphans)} orphan notes (no links in or out) — e.g. {", ".join(orphans[:4])}')
    if unresolved:
        top = ', '.join(f'{k} ({v})' for k, v in unresolved.most_common(5))
        print(f'  ! {len(unresolved)} unresolved wikilink targets — e.g. {top}')
    return bundle


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Build atlas.json from a markdown vault.')
    p.add_argument('--vault', required=True)
    p.add_argument('--out', default='site/data/atlas.json')
    p.add_argument('--title'); p.add_argument('--subtitle'); p.add_argument('--disclaimer')
    p.add_argument('--no-bodies', action='store_true',
                   help='omit note bodies (graph only — use when sources are private)')
    a = p.parse_args()
    build(a.vault, a.out, a.title, a.subtitle, a.disclaimer, bodies=not a.no_bodies)
