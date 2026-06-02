# Title-Family Matching Rules

When `distill` extracts artifacts, multiple iterations of the same thing usually appear under slightly different names. These must be collapsed into one "family" so retention (latest + prev) works correctly.

## The algorithm

1. Take the artifact's title (or filename without extension).
2. Lowercase it.
3. Replace `_` and `-` with spaces.
4. Remove version markers using the patterns below.
5. Collapse multiple spaces to one.
6. Trim leading/trailing whitespace.
7. The result is the family key (stored in the `Slug` column).

## Patterns to strip (in order)

| Pattern | Examples |
|---|---|
| `\bv\d+[a-z]?\b` | `v1`, `v2`, `v3b`, `V1` |
| `\bversion \d+\b` | `version 1`, `version 12` |
| `\b(final|FINAL)\b` | `final`, `FINAL` |
| `\b(actually|really|truly|new|updated|revised|fixed|improved)\b` | the "FINAL-FINAL-actually-new" suffix circus |
| `\b(draft|wip|test|temp)\b` | `draft`, `wip` |
| `\b\d{4}[-/]\d{2}[-/]\d{2}\b` | dates like `2026-05-11` |
| `\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b` | dates like `5/11/26` |
| `\b(rev|revision) \d+\b` | `rev 2`, `revision 3` |
| trailing standalone digits | `landing 2` → `landing` (but `top 10 list` stays — only strip if preceded by other text AND at the very end) |

If after stripping the remaining string is empty or only stopwords, **don't collapse** — keep the original. Better to over-version than to merge unrelated artifacts.

## Examples

| Input | Slug |
|---|---|
| `landing-v1.html` | `landing` |
| `landing-v2.html` | `landing` |
| `landing-FINAL.html` | `landing` |
| `landing-FINAL-actually.html` | `landing` |
| `Landing Page Final v3.html` | `landing page` |
| `pricing-table-v2.html` | `pricing table` |
| `audit-report-2026-05-11.md` | `audit report` |
| `top 10 list.md` | `top 10 list` |
| `email-draft.md` | `email` |
| `email-v1-draft.md` | `email` |

## Row title format for artifacts

The `Row` (title) field for an ARTIFACT row is: `{Project} · ARTIFACT · {Slug} · {Version}`

Examples:
- `Acme HVAC · ARTIFACT · landing · latest`
- `Acme HVAC · ARTIFACT · landing · prev`
- `Beacon Capital · ARTIFACT · pricing table · latest`

**Note:** The skill never *queries* by row title — only by the `Project + Type + Slug + Version` columns. Row titles are for humans browsing Notion. Users may rename them without breaking anything.

## Version transitions

When a new artifact comes in for an existing family:

1. Query rows: `Project=X AND Type=ARTIFACT AND Slug=Y`.
2. If a `latest` row exists for that family:
   - If a `prev` row ALSO exists, overwrite its Content with the current `latest`'s Content. (The old `prev` is gone — Notion's page history preserves it if needed.)
   - If no `prev` row exists, create one with the current `latest`'s Content.
   - Then overwrite the `latest` row's Content with the new artifact.
3. If no `latest` row exists, just create one. No `prev` until version 2.

## Edge cases

- **Multiple new versions in one chat**: Only the FINAL version of each family becomes the new `latest`. Don't write intermediate versions.
- **Title shift mid-stream**: If you started with `landing-v1` and renamed to `homepage-v2`, treat as different families. The user can manually merge in Notion.
- **Same content, different title**: Don't deduplicate by content hash. Trust the title.
- **No content extraction available**: If you can only see an artifact's title but not its content (rare), still write the row — leave Content with a placeholder note "Content not captured" and the user can fix it.
- **Artifact too large**: If Content exceeds 90,000 characters, split into `<slug>-part-1`, `<slug>-part-2`, etc. Each part is its own family.
