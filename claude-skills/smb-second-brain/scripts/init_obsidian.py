#!/usr/bin/env python3
"""
init_obsidian.py — make a vault open cleanly in Obsidian, colour-matched to
the atlas site.

    python3 init_obsidian.py --vault ./my-brain

Writes .obsidian/ (app, appearance, core-plugins, graph) with one graph
colour group per note type, using the same palette as build_atlas.py — so the
Obsidian graph and the atlas site look like the same product.

Safe to re-run: only .obsidian/graph.json colour groups are rewritten;
existing files are left alone unless --force.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_atlas import load_schema, PALETTE, DEFAULT_PRIVATE, plural   # noqa: E402


def rgb_int(hex_color):
    """Obsidian stores graph colours as a decimal int."""
    return int(hex_color.lstrip('#'), 16)


CORE_PLUGINS = {
    "file-explorer": True, "global-search": True, "switcher": True,
    "graph": True, "backlink": True, "outgoing-link": True,
    "tag-pane": True, "properties": True, "page-preview": True,
    "templates": True, "note-composer": True, "command-palette": True,
    "editor-status": True, "bookmarks": True, "outline": True,
    "word-count": True, "file-recovery": True, "canvas": True,
}


def main(vault, force=False):
    if not os.path.isdir(vault):
        sys.exit(f'No such vault: {vault}')
    cfg = load_schema(vault)
    private = set(cfg.get('private', DEFAULT_PRIVATE) or []) | {'.obsidian', '.git'}

    # note types = declared order, then any other top-level folder
    folders = sorted(d for d in os.listdir(vault)
                     if os.path.isdir(os.path.join(vault, d))
                     and d not in private and not d.startswith('.'))
    declared = cfg.get('types', []) or []
    colors = cfg.get('colors', {}) or {}

    ordered, seen = [], set()
    for t in declared:                       # schema order wins
        for f in folders:
            if f == t or f.rstrip('s') == t or plural(t) == f:
                ordered.append((t, f)); seen.add(f); break
    for f in folders:
        if f not in seen:
            ordered.append((f.rstrip('s') or f, f))

    groups = [{"query": f"path:{folder}/",
               "color": {"a": 1, "rgb": rgb_int(colors.get(t) or PALETTE[i % len(PALETTE)])}}
              for i, (t, folder) in enumerate(ordered)]

    graph = {
        "collapse-filter": True, "search": "", "showTags": False,
        "showAttachments": False, "hideUnresolved": False, "showOrphans": True,
        "collapse-color-groups": False, "colorGroups": groups,
        "collapse-display": True, "showArrow": False, "textFadeMultiplier": -0.6,
        "nodeSizeMultiplier": 1.1, "lineSizeMultiplier": 0.8,
        "collapse-forces": True, "centerStrength": 0.52, "repelStrength": 10,
        "linkStrength": 1, "linkDistance": 250, "scale": 0.75, "close": False,
    }

    d = os.path.join(vault, '.obsidian')
    os.makedirs(d, exist_ok=True)
    files = {
        'app.json': {"attachmentFolderPath": "sources", "alwaysUpdateLinks": True,
                     "newLinkFormat": "shortest", "useMarkdownLinks": False},
        'appearance.json': {"accentColor": "#b8421a"},
        'core-plugins.json': CORE_PLUGINS,
        'graph.json': graph,
    }
    for name, body in files.items():
        path = os.path.join(d, name)
        if os.path.exists(path) and not force and name != 'graph.json':
            print(f'  · kept existing {name}')
            continue
        json.dump(body, open(path, 'w'), indent=2)
        print(f'  ✓ wrote .obsidian/{name}')

    print(f'\nObsidian ready → open "{os.path.abspath(vault)}" as a vault.')
    print('Colour groups:')
    for (t, folder), g in zip(ordered, groups):
        print(f'    #{g["color"]["rgb"]:06x}  {folder}/')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--vault', required=True)
    p.add_argument('--force', action='store_true', help='overwrite existing .obsidian files')
    a = p.parse_args()
    main(a.vault, a.force)
