# Hermod pitch deck: plan

The hackathon requires a **four-page deck** (see [hackathon-brief.md](hackathon-brief.md)). Judges score
Problem, Product and Presentation equally, and the central question is: *what can this person
now do that they couldn't do before? Show us.* The deck is read on a screen by judges before
demo night, so it must work without a presenter.

Build it in Canva, 16:9 (1920 x 1080), exactly four pages. No cover page: the product name sits
as a small kicker on page 1, because a fifth page breaks the "four-page" instruction.

## 1. Story in one line

A patient leaves the clinic with a prescription and nobody knows what happens next. Hermod is
a Telegram contact that checks in at each dose, so the patient follows the course and the
doctor sees what happened before the next visit.

## 2. The four pages

Every page title is a conclusion, not a label. One idea per page. The biggest thing on each
page is the one number, the one screenshot, or the one sentence that carries that idea.

### Page 1: Who it's for, and how big the problem is

- **Title:** Between visits, nobody knows whether the prescription was followed.
- **Person:** a patient who has just been given a new course (demo persona: 7-day antibiotic),
  and their GP who only sees them again at the follow-up.
- **How they manage today:** memory, a pill box, a paper note, nothing. At the follow-up the
  patient can't remember and the doctor is guessing.
- **The one number (set large):** ~50% of patients with chronic conditions don't take medication
  as prescribed (WHO, *Adherence to long-term therapies*, 2003). This is the only sourced
  figure we have; don't add others unless someone verifies the source before Monday.
- **Evidence from people:** one or two short quotes from the people you talked to (lived
  experience or first-hand accounts). Label them "paraphrased" or "synthetic" if they are.
- Visual: the number, left-aligned, with the citation in small muted type. No stock photo.

### Page 2: What they can do now (the new ability)

- **Title:** The patient follows the course. The doctor sees what happened.
- Two columns, each a real screenshot, each with a three-word caption:
  1. **Telegram conversation**: Hermod's check-in at dose time, the patient's free-text reply
     ("took it", "did I already take it?"), Hermod answering from the log.
  2. **Doctor dashboard**: the dose timeline with taken / late / missed / extra, adherence %,
     and an open flag.
- One line under the screenshots: *The LLM records what the patient said. Deterministic rules
  decide what counts as a problem. Overdose or emergency text never reaches the model; it goes
  to a fixed escalation (000, Poisons Information 13 11 26) and an urgent flag.*
- Visual rule: screenshots at real device proportions, on the page background, no drop
  shadows, no browser chrome, cropped to the conversation.

### Page 3: What we learned

- **Title:** We assumed WhatsApp. We tested it. We shipped Telegram.
- Three learnings, each one sentence of evidence and one sentence of what changed:
  1. **Channel assumption, changed.** WhatsApp (Meta Cloud API and Twilio) adapters were built
     and could not reach a phone: Meta blocked signup, Twilio trials only send templates, the
     test number was banned. Telegram is free, needs no approval and no public URL. The
     `Channel` protocol keeps WhatsApp a one-class change.
  2. **Safety assumption, tested.** We assumed the model could be trusted to summarise flags
     and set their severity. The prompt now limits flag summaries to the patient's own words
     (no added causes or links to earlier messages) and code caps LLM severity: urgent only
     within 24h of an emergency, otherwise a warning. Confirm with whoever saw the model
     overreach before quoting the failure on the page.
  3. **Hand-over test (fill in Sunday).** Someone unfamiliar does a 2-day course on their own
     phone. Report where they got stuck and what changed. If the tester was a teammate or the
     scenario was compressed, say so on the page.
- Visual: three short rows, numbered, generous spacing. No icons.

### Page 4: What is real today

- **Title:** Everything here was built this weekend. Here is what's real and what isn't.
- Four short lists in a two-by-two arrangement (text only, no cards):
  - **Built and working:** Telegram agent end to end (link, welcome, check-ins at each dose,
    free-text logging with tools, "did I take it?" from the log, side-effect and question
    flags), scheduled check-ins, deterministic guardrails and adherence rules, every LLM call
    traced, JSON API, React doctor dashboard (patients, reminders, timeline, adherence, flags).
    72 automated tests.
  - **How AI was used:** in the product, Gemini 3.5 Flash Lite via LiteLLM with tool calling
    (records only, never judges, never gives dosing advice). In the build, Claude Code wrote
    and reviewed most of the Python against a written design doc.
  - **Simulated or manual:** all patients are synthetic and labelled; the 12-patient clinic is
    seeded; the server runs on a laptop (Telegram long polling, no hosting); n8n alerts are
    optional; prescription-photo parsing is a stub.
  - **Still needs work:** hand-over findings, a public website, WhatsApp adapter, EHR
    integration, multi-clinic auth.
- **Before vs during:** nothing existed before Fri 9 Oct. First commit Sat 10 Oct; the repo
  (https://github.com/RatherN-t/hermod) is public.
- Footer: links to the website, repo and demo video, in muted type.

## 3. Design system for the deck

Match the dashboard (`frontend/src/index.css`) so the website, dashboard and deck read as one
product. Taste rules below follow [impeccable](https://github.com/pbakaus/impeccable): no
default fonts, tinted neutrals rather than pure black or grey, no card-in-card layouts, no
decorative icon above every heading, no gradients.

| Token | Value | Use |
| --- | --- | --- |
| Page | `#F7F6F2` | every page background (warm, tinted, never pure white) |
| Ink | `#1C1C1A` | titles and body |
| Muted | `#6B6862` | captions, citations, footers |
| Accent | `#2F6B57` | one element per page at most: the big number, a rule, a highlighted word |
| Accent soft | `#EAF2EE` | behind a screenshot if it needs lift; nothing else |
| Danger | `#B42318` | only the "urgent flag" mark on page 2 |

- **Type:** a warm serif for titles plus a neutral grotesk for body, both in Canva's library.
  First choice: **Fraunces** (titles) + **DM Sans** (body). Fallbacks: Source Serif Pro or Lora
  for titles, Manrope for body. Not Inter, Roboto, Arial or Canva's default.
- **Scale (px at 1920 wide):** big number 160 to 200, title 56, body 24, captions 16. Line
  height 1.1 for titles, 1.4 for body. Two sizes that are close together (24 and 28) is the
  mistake to avoid; keep steps of about 1.5x.
- **Layout:** margins of 120 px on every side, a 12-column grid inside, everything
  left-aligned, titles at the top-left. Fill space with whitespace, not with boxes.
- **Imagery:** only real artefacts from the product (Telegram screenshot, dashboard
  screenshot). No stock photos, no illustrations, no AI-generated images.
- **Motion:** none. The deck is read as a PDF.
- **Copy:** every title a full sentence that states the conclusion. Body under 40 words per
  block. No exclamation marks.

## 4. Picking the Canva starting point

Canva's public template library can't be searched from the agent tools, and the account has no
Brand Templates yet (it does have one Brand Kit). Two routes:

1. **Recommended: blank presentation, built by hand.** Four pages is small, and a template adds
   decoration you would then remove. Create a 1920 x 1080 presentation, set the page colour,
   add the two fonts, and build each page from the content above. About an hour.
2. **Fast fallback: Canva AI from the outline.** The outline in this file was sent to Canva's
   outline review widget with the "minimalist" style. Approve it to get a generated draft,
   then restyle fonts and colours to the tokens above and replace any stock imagery with the
   two screenshots.

If you prefer a template, search Canva for "minimal pitch deck" or "simple presentation" and
pick one that passes all of these: one typeface family or a serif-plus-sans pair, a light
background, no photos in the layout, no icon rows, and titles that can hold a full sentence.

## 5. Assets to capture before building

- [ ] Telegram screenshot: check-in, "took it", "did I already take it?", side-effect flag.
      Use a synthetic patient. Crop to the conversation.
- [ ] Dashboard screenshot: a patient page with a timeline, adherence %, and an open flag.
- [ ] One or two quotes from the people you talked to (page 1).
- [ ] Hand-over test notes: who, what they did, where they got stuck, what changed (page 3).
- [ ] Public website URL, demo video URL (page 4 footer).

## 6. Review checklist before export

- [ ] Exactly four pages, 16:9, exported as PDF with a public link that opens without access.
- [ ] Each page answers its brief question in the title alone.
- [ ] "Real vs simulated" is explicit on page 4 and the synthetic-data label is visible.
- [ ] Only one accent element per page; danger red appears once in the whole deck.
- [ ] Fonts are the chosen pair everywhere; no leftover template type.
- [ ] Every number has a source in muted type beside it.
- [ ] Naming is consistent: the dashboard is titled "everwell" in `frontend/`, the bot and repo
      are "Hermod". Decide one product name for the deck, website and demo, and use it on all
      three.
