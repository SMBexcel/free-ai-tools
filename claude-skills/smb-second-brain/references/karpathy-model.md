# The Karpathy LLM-wiki model

The architecture this skill implements. Source: Andrej Karpathy's LLM-wiki
writeup — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

The premise: an LLM is a brilliant reader with no memory and no library. Give
it a library it maintains itself, and the memory problem stops mattering.

## Three layers

**1. Raw sources.** The curated documents. Immutable. The LLM reads them and
never edits them. Transcripts, contracts, PDFs, exports. Keep them in
`sources/` and keep them out of anything you share — they are usually the
part with names, numbers, and other people's confidential material in it.

**2. The wiki.** LLM-generated interlinked markdown: summaries, entity pages,
concept pages, cross-references. The agent owns this layer completely. It
rewrites pages freely as new sources arrive. If you find yourself hand-editing
wiki pages constantly, your schema is wrong — fix layer 3 instead.

**3. The schema.** A `SCHEMA.md` config defining note types, link rules, and
conventions. This is what turns a chatty assistant into a disciplined wiki
maintainer. It is the highest-leverage file in the vault and the only one the
human really owns.

## Three operations

**Ingest.** New source arrives → synthesize it into a note → update the 5–15
related pages so the links go both ways. The neighbour update is the step that
separates a knowledge graph from a folder of summaries, and it is the step
that makes ingest expensive at scale.

**Query.** Search the wiki → synthesize an answer → cite the pages. Valuable
answers get filed back as new notes, so the brain compounds instead of
repeating work.

**Lint.** Periodic health check: contradictions, stale claims, orphaned pages,
missing cross-references. Lint is what stops the wiki rotting the way every
hand-maintained wiki in history has rotted.

## Where the model is vague, and what we do about it

Karpathy's **Query** step says "the LLM searches the wiki" without saying
how. That first hop — question to entry node — is the actual retrieval
problem, and it is where a naive implementation falls back to reading
everything.

**Our fix: the index file is part of the schema.** `index.md` carries one line
per note. The LLM reads the index, interprets the question, picks an entry
node, and traverses from there. No embeddings, no vector store, no chunking.

Two places the index eventually snaps:

1. **Context ceiling.** The index grows with the corpus. Eventually it no
   longer fits in context, or you compress it so hard the one-liners stop
   being discriminating.
2. **Buried needles.** The index indexes the *summary*. A question can match a
   throwaway sentence inside a page that the title never hints at. Long
   transcripts are full of buried gold, so you hit this sooner with speech
   than with documents.

Lint keeps the index honest against drift. It cannot fix either ceiling.

## When to add machinery (and not before)

**Let the failure justify the complexity.** Ship the wiki. Add nothing until
the user watches it miss an answer they know is in there. In practice you feel
it within about 20 real questions, or never.

**Vector embeddings** — when the answer lives in one specific buried passage,
or the library is too big to hand over whole. Embeddings turn each chunk into
a numeric fingerprint of its meaning, so "how do I not get screwed when the
old owner sticks around" finds the seller-transition passage that never uses
those words. Complete coverage, fuzzy precision.

**A graph database (Neo4j)** — when the *connections themselves* are the
question and there are too many to eyeball. "Every path from this broker to a
closed HVAC deal in Texas." The wiki is a corkboard with pins and string; a
graph database is the same corkboard that can trace every string instantly at
a million pins.

Most vaults never need either. The two are also not substitutes: wikilinks are
hand-drawn roads (sparse, precise, browsable), embeddings are a GPS
(complete, fuzzy, unbrowsable). If you add embeddings, you are adding the
search box, not replacing the map.
