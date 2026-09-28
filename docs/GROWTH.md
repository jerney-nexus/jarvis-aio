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

1. **AI answer engines (ChatGPT, Perplexity, Claude, Gemini).** This is
   already our second-biggest referrer, and nobody pushed it. These tools
   answer questions like "best AI assistant for Home Assistant" by quoting
   whatever explains JARVIS most clearly. Make that easy:
   - Keep the first README paragraph a plain, self-contained answer to
     "what is it, who is it for, how do I install it". The HACS search line
     now sits in the quick start.
   - Add a short FAQ section with the literal questions people ask: "Does it
     work without the cloud?", "Does it work with Ollama?", "How is it
     different from the built-in Assist / OpenAI Conversation?"
   - Every forum or Reddit post below becomes more text these tools can cite.
   Referrer: `chatgpt.com`, `perplexity.ai` and similar. Watch whether that
   share grows after the FAQ lands.
2. **Home Assistant Community forum → "Share your Projects".** This is the
   usual launch venue for HA integrations. Post one thread and keep it going
   as the changelog: each notable release is a reply, which bumps the thread.
   Referrer: `community.home-assistant.io`.
3. **Reddit.** Pick the angle to fit each sub. Space posts about a week
   apart, and don't cross-post the same text.
   - r/homeassistant: the doorbell and package announcements, plus a
     "what it noticed this week" screenshot.
   - r/LocalLLaMA and r/selfhosted: **the Local Mind**. It keeps reasoning
     offline with Ollama, and no cloud account is required. That audience
     wants exactly this.
   - r/homeautomation: the Cognitive Core and the "suggest, don't act"
     philosophy.
4. **A 60–90 s demo video/GIF at the top of the README.** Every visual in
   the README today is an SVG mockup. The caption even says so. A real
   screen recording of a voice question, the HUD reacting, and a doorbell
   announcement will lift the views → stars conversion on every other
   channel. It's also what gets you a slot in a creator's video.
5. **HA YouTube creators.** Everything Smart Home, Smart Home Junkie,
   BeardedTinker, Home Automation Guy and similar channels regularly cover
   LLM integrations. Send each one a short note with the demo video and
   the 5-minute quick start. One mention can outweigh every other channel
   combined.
6. **Curated lists.** Open a PR to
   [awesome-home-assistant](https://github.com/frenck/awesome-home-assistant)
   and to awesome LLM/agent lists. It's a small but lasting referrer.
7. **Show HN.** Save this for after the demo video. Lead with the Local Mind and the "suggest, don't act" design,
   not the Iron Man theme.

## Reading the weekly report and acting on it

| If the report shows… | Then… |
|---|---|
| Page views jump but unique visitors don't | That's our own activity (reviewing PRs, checking Actions). Judge traction by uniques on the repo home page. |
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
| 2 | Post the HA forum "Share your Projects" thread and the awesome-home-assistant PR. | `community.home-assistant.io` among referrers; stars/week. |
| 3 | Post to r/homeassistant, then r/LocalLLaMA 3–4 days later. | Reddit referrers; stars/unique visitors. |
| 4 | Pitch 3–5 YouTube creators. Review what worked and re-rank this list. | Which channel had the best uniques → stars rate. |

## Launch-post draft (forum / r/homeassistant)

> **JARVIS: an AI butler for Home Assistant that suggests before it acts**
>
> I've been building a HACS integration that turns HA into something closer
> to Stark's JARVIS. It uses a pluggable LLM brain (Groq's free tier, OpenAI,
> Anthropic, Gemini, or fully local Ollama), talks through the normal voice
> pipeline, reads your calendar and your appliance manuals, and runs a
> "Cognitive Core" that classifies every home event by urgency, so the
> basement window opening at 3 a.m. gets flagged and the kitchen light at
> 7 a.m. doesn't. If the internet drops, a local reasoning brain takes over.
>
> It starts conservative. It suggests automations from patterns it notices
> and only acts on its own as you allow it. You can be talking to it in
> five minutes; cameras, voice hardware, and GPUs are optional.
>
> [demo video] · https://github.com/sam3gp8/jarvis-aio · feedback very welcome
