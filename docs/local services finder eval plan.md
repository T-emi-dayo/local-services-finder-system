# Local Services Finder: Eval Plan

**Goal:** produce a credible, low-cost before/after evaluation of the Local Services Finder agent that can be published as a case study.

**Headline claim to aim for:** "Correct provider in the top result: X% before, Y% after one targeted fix", measured on frozen data.

---

## 1. Constraints and assumptions

| Item | Value |
|---|---|
| Data API budget | About 5-10 calls in total (**assumption:** this limit is the business/location data API, not Gemini) |
| LLM | Gemini free tier (check current per-minute and per-day limits on the Gemini API rate-limit page) |
| Query set | 50 queries (start with 30 if time is short) |
| Cost target | Near zero |

**Open check:** if the 5-10 call limit is actually on the Gemini side, skip to section 8 and re-budget before anything else.

---

## 2. Design principles

1. **Record once, replay forever.** Pull real data a handful of times, store it, and serve the agent's tools from the local copy.
2. **Separate running from judging.** Run the agent, save every output, then score in a second pass.
3. **Deterministic checks first.** Use SQL and plain Python for the headline metrics. Use an LLM judge only for subjective metrics.
4. **Keep it hard.** The golden set is written independently of the corpus, and includes distractors and unanswerable queries.
5. **Be honest about scope.** This measures the agent's reasoning on frozen data, not live API quality.

---

## 3. Data collection (the 5-10 calls)

**Cells:** 4 categories x 2 areas = 8 calls. Keep 2 calls in reserve.

- Categories: pick four you can defend (e.g. electrician, plumber, mechanic, salon).
- Areas: pick two you genuinely test in.

**Make every call count:**
- Use the largest page size the API allows.
- Request every available field (name, category, address, coordinates, rating, review count, phone, hours, open status).
- Check whether pagination counts as a new call. If it does, one large page beats two small ones.
- **Save the raw JSON to disk before parsing.** Never lose a response.
- Make the first call a plain test so a bug does not burn a cell.

**Reserve calls:** after the first 8 pulls, find thin cells (few results) and spend the reserve there.

**Expected size:** roughly 20 results per call gives about 160 real records (verify the real cap).

---

## 4. Corpus and storage (SQLite)

Store everything in one SQLite database. Suggested tables:

```sql
CREATE TABLE providers (
  id INTEGER PRIMARY KEY,
  name TEXT, category TEXT, area TEXT, address TEXT,
  lat REAL, lng REAL,
  rating REAL, review_count INTEGER,
  phone TEXT, open_now INTEGER, hours TEXT,
  source TEXT CHECK (source IN ('real','synthetic')),
  mutation TEXT          -- NULL for real records
);
CREATE VIRTUAL TABLE providers_fts USING fts5(name, category, address, content='providers', content_rowid='id');
```

The agent's search tool queries this DB by category and area (plus fuzzy text via FTS5). Paraphrased user queries then hit the same data, because the tool arguments are what matter.

Keep the raw JSON and the database local and out of git. Check each provider's terms on storing results. Publish metrics only, not raw data.

---

## 5. Synthetic distractors (no API cost)

Mutate real records with a script and label them `source='synthetic'`:

- Mark some providers closed.
- Drop the phone number from some.
- Change the category on some.
- Add near-duplicates with slightly different names.
- Remove all providers from one category-area combination to create "empty" cells.

State clearly in the case study which records are synthetic and why.

---

## 6. Query set (50 queries from 8 cells)

Same cell, different constraints, about 6 queries per cell:

| Type | Example shape |
|---|---|
| Nearest, open now | "plumber open now near X" |
| Best rated under a threshold | "best rated mechanic in Y" |
| Needs contact info | "salon with a phone number" |
| Ambiguous category | vague phrasing that could mean two categories |
| Multi-constraint | category + area + rating + open |
| Unanswerable | no provider exists in the data |

**Rules:**
- Write the queries independently of the corpus build. Do not generate both with the same process or LLM.
- Include enough unanswerable queries (about 10-15%) to test whether the agent says "none found" instead of inventing a provider.
- Each query gets an **expected-answer SQL filter** stored next to it. That is the ground truth.

---

## 7. Metrics

**Deterministic (no LLM cost):**
- Correct provider in top 1 / top 3 (against SQL ground truth)
- Precision and recall of returned providers
- Correct handling of unanswerable queries (no invented provider)
- Output schema validity
- Correct tool calls and arguments
- Empty-result rate
- Latency per query

**LLM-judged (only these):**
- Answer relevance
- Faithfulness (does the answer match the retrieved data?)

Combine both judged metrics into **one judge call per query** that returns JSON scores.

---

## 8. Gemini free-tier budget

**Rough count:** 30 queries x ~6 agent calls x 2 versions = ~360 calls, plus ~60 judge calls (one combined prompt per query per version). Scale up if you run all 50.

**Tactics:**
- Run the agent on the same Gemini model production uses. Judge with the cheapest model that works.
- Cache every LLM response to disk so a quota stop costs nothing and you can resume the next day.
- Throttle requests and back off on 429 errors.
- Set `MIN_GAP` from your real requests-per-minute limit.

```python
import time, json, hashlib, pathlib, random
CACHE = pathlib.Path("llm_cache"); CACHE.mkdir(exist_ok=True)
MIN_GAP = 6.5   # seconds between calls; set from your RPM limit
_last = 0.0

def llm_call(model, prompt, call_fn, retries=5):
    global _last
    key = hashlib.sha256(f"{model}|{prompt}".encode()).hexdigest()
    p = CACHE / f"{key}.json"
    if p.exists():
        return json.loads(p.read_text())["out"]
    for attempt in range(retries):
        time.sleep(max(0, MIN_GAP - (time.time() - _last)))
        _last = time.time()
        try:
            out = call_fn(prompt)
            p.write_text(json.dumps({"out": out}))
            return out
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                time.sleep(min(60, 5 * 2 ** attempt) + random.random())
            else:
                raise
    raise RuntimeError("rate limited after retries")
```

**Privacy:** free-tier content may be used by the provider to improve its products. The corpus is public business data, so this is fine. Never send private data through the free keys.

---

## 9. Run protocol

1. Run 3-5 test queries end to end to catch bugs cheaply.
2. Run the full query set on **version A (before)**. Save every output and trace.
3. Make **one targeted fix** based on the failures you see.
4. Run the full query set on **version B (after)** against the same frozen data.
5. Score both runs with the same deterministic checks, then the combined judge call.
6. Spot-check 10 judge scores by hand to confirm the judge is sane.

---

## 10. Case study outline

1. **Problem:** finding local service providers from natural-language queries.
2. **How the data was frozen:** the 8 pulls, the schema, the synthetic distractors, and why.
3. **Test design:** query types, independence from the corpus, unanswerable cases.
4. **Results:** before/after chart on the headline metric, plus a short table of the rest.
5. **The fix:** what failed, what you changed, and why.
6. **Limits:** frozen data, small sample, Gemini judging Gemini (state it), synthetic records labelled.

Keep it short: one chart, three paragraphs, and a link to the repo.

---

## 11. Checklist

- [ ] Confirm which API the 5-10 call limit applies to
- [ ] Choose 4 categories and 2 areas
- [ ] First test call; save raw JSON
- [ ] Remaining pulls; save raw JSON
- [ ] Build SQLite DB and FTS index
- [ ] Wire the agent's search tool to the DB
- [ ] Write the synthetic-mutation script
- [ ] Write the 50 queries and their ground-truth SQL
- [ ] Add the LLM cache wrapper
- [ ] Run version A and save outputs
- [ ] Make one fix; run version B
- [ ] Score, spot-check, chart
- [ ] Write the case study and publish it on the portfolio
