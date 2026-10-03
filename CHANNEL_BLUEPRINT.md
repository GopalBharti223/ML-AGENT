# 🏆 CHANNEL BLUEPRINT — From Content Mill to Brand

> Your pipeline already produces the videos. This document turns it
> into a **channel people subscribe to**. The machine is built;
> this is the operator manual.

---

## 1. The One-Line Identity

**"Data races in under 30 seconds."**

Every video is a RACE with a winner, a loser, and a plot twist.
Not "charts", not "statistics" — RACES. Races have fandoms,
fandoms argue, arguments become comments, comments become reach.

---

## 2. Channel Name Options

| Name | Vibe | Best if you lean into... |
|---|---|---|
| **The Data Race** 🏁 | Sporty, series-feel | F1 + sports points races |
| **Ranked in 30** | Punchy, format-promise | World rankings, quick hits |
| **PlotStat** | Drama + data | Twist-driven stories |
| **Bar Race Daily** | Literal, searchable | Pure bar-race visuals |
| **Who's #1?** | Question = infinite titles | Broad curiosity content |

Pick ONE. Put it in `.env`:
```
CHANNEL_NAME=The Data Race
CHANNEL_TAGLINE=new races daily
```
The pipeline now auto-signs every description with it.

---

## 3. Content Pillars (pick 2, max 3)

### 🏁 Pillar A — Sports Points Races (jolpica_f1)
F1 driver/constructor battles, title fights, comeback seasons.
**Why:** fandoms = comments = algorithm fuel.
**Series name:** *"The Points Race"*

### 🌍 Pillar B — Country Rankings (worldbank, owid, imf)
GDP, population, CO2, energy, life expectancy.
**Why:** infinite topics, global audience, evergreen.
**Series name:** *"Country Clash"*

### 🤖 Pillar C — The AI Race (ai_index, openalex)
Which countries lead AI research, talent, investment.
**Why:** trending, advertiser-friendly, news-jacking potential.
**Series name:** *"The AI Race"*

> ⚠️ **Cut the long tail** (anime/NHTSA/SEC) until you have an
> audience. Random niches confuse the algorithm about WHO to show
> your videos to. Identity = distribution.

---

## 4. The Format Bible (already enforced by code)

| Element | Rule | Enforced in |
|---|---|---|
| Hook | First line IS the hook | `script.py` rotation |
| Voice | Contractions, viewer address, no AI phrases | `script.py` VOICE block |
| Length | 18s — story + loop sweet spot | `config.py` |
| Loop | Last phrase flows back into hook | `script.py` LOOP TRICK |
| Delivery | Voice energy matches scene pacing | `tts.py` profiles |
| Cover | Big white Impact text, 3 layouts | `thumbnail.py` |
| Comments | Rotating bait line | `metadata.py` |
| Anti-repeat | Topics/hooks/endings/CTAs rotate | pipeline-wide |

**Never break the format on purpose.** Consistency is the brand.

---

## 5. Upload Cadence — IMPORTANT FIX

Your `DAILY_UPLOADS=4` is **too many for a new channel**.

| Channel age | Cadence | Why |
|---|---|---|
| 0–30 days | **1/day, fixed time** | Algorithm learns your audience |
| 1K–10K subs | 2/day | Test two pillars |
| 10K+ subs | 3–4/day | Scale what retains |

Set in `.env`: `DAILY_UPLOADS=1`

Best windows (US-EU): **14:00–17:00 UTC** and **23:00–01:00 UTC**.
Same time daily — the algorithm rewards predictability.

---

## 6. Shorts Algorithm Cheat Sheet

What ranks a Short, in order:

1. **Swipe-away rate (first 1s)** — hook rotation fixes this
2. **% watched** — 18s videos routinely hit 90%+; loops push past 100%
3. **Loop count** — LOOP TRICK makes rewatches invisible-but-counted
4. **Comments in first hour** — comment bait + pinned question
5. **Shares to chats** — twist endings ("send this to an F1 fan")

**First-hour ritual (manual, 5 min after upload):**
- Pin: *"Be honest — did you guess the ending?"*
- Reply to every comment in hour 1

---

## 7. A/B Testing Workflow (built into the pipeline)

Each run now generates:
- `title` + `title_options` (3-5 variants) in `youtube_metadata.json`
- 12 thumbnail candidates: 4 frames × 3 layouts

**Per video:**
1. Upload with `title` + auto-picked `_titled_bottom` cover
2. Studio → **Test & Compare** → add `_titled_center` + `_titled_top`
3. After 48h YouTube picks the CTR winner — log it
4. Losing title? Swap manually — titles are editable anytime

**Pattern log (spreadsheet):** hook × ending × layout × CTR.
After 30 videos you'll know your audience better than any guru.

---

## 8. 30-Day Launch Calendar

**Week 1 — Identity:** pick name/banner/handle, set `.env` values,
7 videos in ONE pillar (recommend F1 — season is live), daily
upload → pin → reply.

**Week 2 — Double down:** 70% best pillar / 30% second pillar.
Start the A/B log. Kill topic families with <70% watch-through
(check `data/history.db`).

**Week 3 — Series power:** series name in titles (*"The Points
Race: Norris vs Verstappen"*), playlists per pillar, Community
poll: "Which race next?" (engagement + topic research).

**Week 4 — Analyze & lock:** rank all 28 videos by retention/CTR/
comments. Double winners' families, cut losers. Set month-2 KPIs.

---

## 9. KPI Targets

| Metric | Week 2 | Week 4 | Month 3 |
|---|---|---|---|
| Avg % watched | >80% | >90% | >95% |
| Swipe-away (first 3s) | <35% | <25% | <15% |
| CTR (feed) | >3% | >4% | >5% |
| Comments per 1K views | >3 | >6 | >10 |
| Subs per video | 1+ | 5+ | 20+ |

Weekly: join `data/history.db` topics with Studio retention,
feed winners back into topic weights.

---

## 10. Monetization Milestones

1. **1K subs + 10M Shorts views/90d** → Partner Program
2. ~10K subs → monthly long-form compilation (10× RPM)
3. ~50K subs → sponsors (finance, VPN, learning apps)

---

## 11. Division of Labor

**Machine (automated):** topics, facts, scripts, voice, visuals,
covers, metadata, anti-repeat, upload, safety limits.

**You (30 min/day):** pick the cover, pin + seed comments, reply
hour one, log A/B results, read numbers, adjust `.env`.

That 30 minutes is the difference between a channel and a slot
machine.