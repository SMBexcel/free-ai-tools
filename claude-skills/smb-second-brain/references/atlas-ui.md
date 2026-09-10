# Customising the atlas viewer

`assets/site/` is three files plus two vendored libraries. No build step, no
package manager, no framework.

```
site/
├─ index.html      layout + copy
├─ atlas.css       design tokens + all styling
├─ app.js          data loading, filters, reader, 3D graph
├─ data/
│  └─ atlas.json   generated — do not hand-edit
└─ vendor/
   ├─ 3d-force-graph.min.js   MIT
   └─ marked.min.js           MIT
```

Both libraries are MIT and vendored locally, so the site works offline and has
no CDN dependency. (Cosmograph was rejected for this: CC-BY-NC, no commercial
use.)

## Common changes

**Colours and type.** All tokens are at the top of `atlas.css` in `:root`.
`--paper`, `--ink`, `--accent` drive the editorial side; `--graph-bg` is the
canvas.

**Fonts.** The template uses system stacks to stay dependency-free. For the
editorial look, drop woff2 files in `fonts/`, add a `fonts.css` with
`@font-face` rules, link it from `index.html`, and point `--serif` / `--body`
/ `--ui` / `--mono` at them.

**Node colours.** Set them in `SCHEMA.md`'s atlas block — do not hardcode
them in `app.js`, or the Obsidian graph and the site will drift apart:
```json
{"colors": {"episode": "#e6b54e", "concept": "#7ec8ff"}}
```

**Node size.** `build_atlas.py` sets `val` from link degree
(`2 + sqrt(degree) * 1.2`). Change it there, not in the viewer.

**Physics.** In `bootGraph()`: `d3Force('charge').strength(-95)` — more
negative spreads the graph out. `cooldownTicks` controls how long it settles.

**Copy.** Title, subtitle, and disclaimer come from `SCHEMA.md` via
`atlas.json`. Edit them there so Obsidian and the site agree.

## Deploying

Any static host. No build command, output directory is `site/`.

- **Cloudflare Pages** — connect the repo, or `wrangler pages deploy site`
- **Netlify** — drag the folder onto the dashboard
- **GitHub Pages** — push `site/` and enable Pages

One caveat that catches people: `atlas.json` embeds every note body, so a big
vault makes a big file. Around 5 MB it is worth acting on — the Acquiring
Minds vault is 163 notes and lands at ~5 MB. Options, cheapest first: add
bulky folders to `private`, or use `--no-bodies` and link out to the source
instead of rendering it.

## Markdown rendering

`app.js` renders note bodies with marked in GFM mode **with strikethrough
disabled** (`tokenizer.del` returns nothing). Notes about money are full of
`~$1M to ~$2M`, and GFM would otherwise read the two tildes as `~~strike~~`.
Tables, autolinks and task lists still work. If you genuinely want
strikethrough, delete the `marked.use({ tokenizer: … })` line at the top of
`app.js` and write approximations as `approx.` instead.

## Accessibility and polish worth keeping

- The disclaimer is not decorative. Any AI-generated corpus needs it visible,
  and every note should link back to its real source.
- The divider is draggable; the split persists only for the session.
- `Esc` clears search. Node click focuses the camera and highlights
  neighbours. Background click clears the highlight.
