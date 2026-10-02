# Growth playbook

How we find out whether people are finding JARVIS, and what we do about it.
The numbers come from `.github/workflows/traffic.yml`, which runs daily. It
writes `REPORT.md` on the `traffic-data` branch and opens a **Weekly traction
report** issue every Monday. This page covers what to do with them.

## Baseline (first real traffic data, 2026-09-28)

GitHub's traffic numbers lag a few days. This data runs from Sept 10 to Sept 23.

| Signal | Value | Read |
|---|---|---|
| Unique visitors | ~15–25 a day (123 across the week to Sept 23, 116 the week before) | A small but steady audience. Views doubled week over week, but unique visitors didn't, so the extra views came from a few heavy visitors (mostly the maintainer, see below). |
| Stars | 20 (+3 in the last week) | Since early August, about one every 2–3 days. Organic discovery with no launch behind it. |
| Top referrers | github.com 20 uniques, **chatgpt.com 15**, Google 2 | ChatGPT is already recommending JARVIS and sends nearly as many people as all of GitHub. Google sends almost none. |
| Most-visited pages | Repo home 134 uniques, Issues 29, Releases 8 | Visitors look at the landing page and then check Issues to see whether the project is maintained. The PR pages with 1–2 uniques are the maintainer's own review traffic. |
| Clones | 300+ unique a week | Inflated. Every CI run and HACS validation checks out the repo, so clones are not an audience signal. |
| Distribution | Listed in the **HACS default store** | Anyone can find it by searching HACS. Neither HACS nor HA analytics reports an install count for it yet (see Step 0). |
| Forks / watchers | 3 / 2 | Very few people are following along yet. |

What the numbers say: people who find JARVIS stay. They check the issues and
they star it. But most discovery happens where we aren't posting: GitHub
browsing and AI assistants. The plan below leans into the one channel that
already works (AI answers) and opens the community channels we haven't used yet.

### Update 2026-10-01: one user comment beat every channel

On Sept 27 a JARVIS user (not us) described his setup in a "what do you
automate?" thread in the Home Assistant Facebook group and linked the repo:

> "Alot of this is monitored and enabled via Jarvis AIO. It takes a while to
> just monitor your day to day and eventually starts making suggestions based
> off your actions."

That day unique visitors hit ~68, three to four times a normal day. In the 7
days to Sept 29, unique visitors were up **57%** (185 vs 118). The Facebook
referrers (`lm.facebook.com`, `facebook.com`, `l.facebook.com`) brought
~42 uniques, more than github.com (27) and ChatGPT (9). Stars didn't move:
Facebook HA users install through HACS without starring on GitHub, so judge
this channel by unique visitors, not stars.

Two lessons:
- **Users describing real setups convert better than anything we post.** His
  one sentence is the clearest pitch for JARVIS so far, and the launch post
  below now leads with it.
- **Make that easy and reply when it happens** (channel 1 below).

## Step 0: turn the lights on (do this first)

1. ~~**Add `TRAFFIC_TOKEN`.**~~ Done 2026-09-28. The token is a
   fine-grained PAT limited to this repo with **Administration: Read-only**.
   Renew it before it expires, or the traffic rows go blank again.
2. **Fix the repo description.** It currently reads
   `for Home      Assistant` with a run of spaces. GitHub search and social
   cards show that string.
3. **Broaden the topics.** Today they're `haos, home-assistant, integration,
   jarvis, sentinel, voice-assistant`. Add `hacs`, `hacs-integration`,
   `home-automation`, `custom-component`, `llm`, `ai-assistant`, `ollama`,
   `local-llm`, `openai`, `anthropic`, `gemini`, `groq`. People browse
   GitHub topic pages, and each topic is a place JARVIS can show up.
4. **Make installs countable.** This is the only install signal we can get,
   because JARVIS doesn't appear in HA analytics yet. Set `"zip_release": true` and
   `"filename": "jarvis.zip"` in `hacs.json`, and have `release.yml` attach
   that zip. HACS then downloads a release asset, and its download count
   becomes an install counter. This changes the release process, so it's
   worth doing but belongs in its own PR.

## Channels, ranked by expected return

Each channel shows up in the weekly report under **Top referrers**. That's how
we tell which ones actually worked.

1. **Word of mouth in Facebook HA groups.** This is our proven channel
   (see the 2026-10-01 update). The groups ask "what do you automate?" and
   "favorite integration?" all the time, and real answers travel.
   - When a user recommends JARVIS, reply in that thread as the developer
     within a day. Thank them, add one useful detail, and give the install
     path ("search JARVIS AI Assistant in HACS"). It keeps the thread alive
     and makes the recommendation more believable.
   - When we answer those threads ourselves, describe a real automation
     JARVIS suggested, not a feature list. Most groups ban promo posts, so
     never post a standalone ad.
   - Ask for it: the README Support section and release notes invite happy
     users to share their setup.
   Referrers: `lm.facebook.com`, `facebook.com`, `l.facebook.com`.
2. **AI answer engines (ChatGPT, Perplexity, Claude, Gemini).** This is
   already our second-biggest referrer, and nobody pushed it. These tools
   answer questions like "best AI assistant for Home Assistant" by quoting
   whatever explains JARVIS most clearly. Make that easy:
   - Keep the first README paragraph a plain, self-contained answer to
     "what is it, who is it for, how do I install it". The HACS search line
     now sits in the quick start.
   - ~~Add a README FAQ~~ Done 2026-09-28. It answers the literal questions
     people ask ("Does it work with Ollama?", "Can it run offline?", "How is it
     different from Assist / OpenAI Conversation?"). Add new questions as they
     come up in issues and forum threads.
   - Every forum or Reddit post below becomes more text these tools can cite.
   Referrer: `chatgpt.com`, `perplexity.ai` and similar. Watch whether that
   share grows after the FAQ lands.
3. **Home Assistant Community forum → "Share your Projects".** This is the
   usual launch venue for HA integrations. Post one thread and keep it going
   as the changelog: each notable release is a reply, which bumps the thread.
   Referrer: `community.home-assistant.io`.
4. **Reddit.** Pick the angle to fit each sub. Space posts about a week
   apart, and don't cross-post the same text.
   - r/homeassistant: the doorbell and package announcements, plus a
     "what it noticed this week" screenshot.
   - r/LocalLLaMA and r/selfhosted: **the Local Mind**. It keeps reasoning
     offline with Ollama, and no cloud account is required. That audience
     wants exactly this.
   - r/homeautomation: the Cognitive Core and the "suggest, don't act"
     philosophy.
5. **A 60–90 s demo video/GIF at the top of the README.** Every visual in
   the README today is an SVG mockup. The caption even says so. A real
   screen recording of a voice question, the HUD reacting, and a doorbell
   announcement will lift the views → stars conversion on every other
   channel. It's also what gets you a slot in a creator's video.
6. **HA YouTube creators.** Everything Smart Home, Smart Home Junkie,
   BeardedTinker, Home Automation Guy and similar channels regularly cover
   LLM integrations. Send each one a short note with the demo video and
   the 5-minute quick start. One mention can outweigh every other channel
   combined.
7. **Curated lists.** Open a PR to
   [awesome-home-assistant](https://github.com/frenck/awesome-home-assistant)
   and to awesome LLM/agent lists. It's a small but lasting referrer.
8. **Show HN.** Save this for after the demo video. Lead with the Local Mind and the "suggest, don't act" design,
   not the Iron Man theme.

## Reading the weekly report and acting on it

| If the report shows… | Then… |
|---|---|
| Page views jump but unique visitors don't | That's our own activity (reviewing PRs, checking Actions). Judge traction by uniques on the repo home page. |
| A single day spikes 3×+ in uniques | Someone recommended JARVIS somewhere. Find the thread from the referrer list and reply in it as the developer the same day. |
| One referrer brings in most of the week's uniques | Double down there: reply in that thread and post the next update there first. |
| A referrer we posted to sends almost nothing after 7 days | Drop it or change the angle. Don't repost the same pitch. |
| Views are up but stars aren't (stars/unique visitors under ~3%) | The README is losing people. Put the demo video and the quick start higher, and trim everything above the fold. |
| Clones or installs jump right after a release | Release notes are working as a channel. Post highlights for notable releases to the forum thread. |
| `/blob/main/README.md` or the `/releases` page dominates *popular paths* | Visitors are trying to evaluate or install. Make sure the quick start says "search JARVIS in HACS" near the top. |
| Week-over-week views are flat for 3+ weeks | Run the next channel down the list. |

**Release cadence note:** there were 15 releases in the week of 2026-09-22.
Frequent releases show the project is alive, but "update available" every
day wears on users. Batch user-facing releases to about one or two a week,
and post a single highlights reply for each.

## Four-week plan

| Week | Do | Watch in the report |
|---|---|---|
| 1 | Finish Step 0 (description, topics, zip releases). Add the README FAQ. Record the demo video. | Baseline uniques (~17/day); `chatgpt.com` share of referrers. |
| 2 | Reply in the Facebook thread that recommended JARVIS. Post the HA forum "Share your Projects" thread and the awesome-home-assistant PR. | `community.home-assistant.io` vs Facebook uniques; stars/week. |
| 3 | Post to r/homeassistant, then r/LocalLLaMA 3–4 days later. | Reddit referrers; stars/unique visitors. |
| 4 | Pitch 3–5 YouTube creators. Review what worked and re-rank this list. | Which channel had the best uniques → stars rate. |

## Launch-post draft (HA forum → "Share your Projects!")

Post from the maintainer's account. Swap the placeholder for a real HUD
screenshot first. Reply to the thread for notable releases instead of
starting new ones.

**Title:** JARVIS: an AI butler for Home Assistant that learns your routine and suggests automations (HACS)

```markdown
Hi all! I've been building **JARVIS**, a HACS integration that gives Home Assistant something closer to Stark's JARVIS: an assistant you can talk to, that also watches the house on its own and decides what's worth telling you.

The best summary came from a user in the HA Facebook group:

> "It takes a while to just monitor your day to day and eventually starts making suggestions based off your actions."

That's the core idea: **suggest, don't act.**

[screenshot: the HUD panel]

**Install:** it's in the HACS default store. Search **JARVIS AI Assistant**, install, restart, then add it under *Settings → Devices & Services*.
GitHub: https://github.com/sam3gp8/jarvis-aio

### What makes it different from a regular LLM conversation agent

Most LLM integrations answer when you speak to them. JARVIS does that too (it plugs into the normal Assist voice pipeline). It also works in the background:

- **Learns your routine and suggests automations.** It only starts doing something on its own after you've accepted the same suggestion three times, and you can revoke that at any time.
- **Decides what's worth your attention.** It classifies every home event by urgency, based on your home's own history. The kitchen light at 7 a.m. is routine. The basement window opening at 3 a.m., when it never has before, gets flagged, and escalated if you're away.
- **Keeps working offline.** If the cloud provider drops, a local reasoning brain takes over event decisions. Or run everything on Ollama and nothing leaves your network.
- **Cameras (optional).** Doorbell-press analysis, package and mail announcements, and quiet visitor learning, over Frigate (and Nest through it).
- **Answers from your paperwork.** Drop appliance manuals and receipts into a folder and ask "what filter does the furnace take?"
- **Knows your calendar.** It flags overlapping and back-to-back events, and can look things up on the web (DuckDuckGo, or your own SearXNG).
- **Iron Man HUD dashboard**, with a live 3D house, per-room occupancy and an event feed.

### Getting started is small

You need HA 2024.10+ and **one** LLM provider: Groq (free tier), OpenAI, Anthropic, Gemini, Ollama, or any OpenAI-compatible endpoint. You can be talking to it in about five minutes. Cameras, voice satellites and GPUs are all optional add-ons. It speaks in the language you address it in, and the UI is translated into 20 languages.

Everything it learns stays in `/config/jarvis/` on your own instance: no JARVIS cloud, no telemetry.

### What I'd love feedback on

- What should it notice in *your* home that it doesn't yet?
- How much personality do you want? There's a banter setting (plain / dry / full), and it always goes serious for smoke alarms and the like.
- Anything confusing in setup. I'd like the first five minutes to be painless.

Bugs and ideas are welcome here or on GitHub Issues. I'll post notable releases in this thread.
```
