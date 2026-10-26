# Apify fixtures

Real actor output captured on 2026-10-20 for one public business (Blue Bottle Coffee,
Hayes Valley, San Francisco), trimmed to the fields the scorer reads. Personal data is
removed: Q&A authors are reduced to a `byOwner` flag and review text is dropped.

| File | Actor | Run |
|---|---|---|
| `serp.json` | apify/google-search-scraper | sgbaYlLWEqf9RJXPm |
| `places__loc0.json` | compass/crawler-google-places | KgLn0ldEIkdecVdJV |
| `reviews__loc0.json` | compass/Google-Maps-Reviews-Scraper | zmNVOAex1ybe5UJ6f |
| `grid__loc0__kw0.json` | fayoussef/geo-grid-local-rank-tracker | yuqNHp7TZ9GeOZNBB |

The grid ran by business name and matched two different Blue Bottle branches (two
`foundPlaceId` values). That is the same-name false match the F1 caveat warns about, kept
here on purpose as a regression case. The grid searched `coffee shop`; the SERP fixture
searched `coffee shop hayes valley san francisco`. Files are matched by run key, not text.
