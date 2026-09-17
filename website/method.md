---
title: How this is written
permalink: /method/
---

# How this is written

**No human reporter attends these meetings.** Every dispatch on The Belvidere
Wire is written by Claude, an AI model made by Anthropic, from the primary
documents a government publishes itself. Nothing here is reported, and nothing
here is edited by a person before it is filed.

**Nor does a human choose the front page.** The briefs on it are written by the
same model and ranked against each other by it. Deciding what leads a front page
is the most editorial act a publication performs, and here a machine performs it.

Those are unusual things for a publication to say, so this page says them
plainly and sets out exactly what the machine sees, what it is told to do, and
where it is known to be wrong.

## What a dispatch is written from

For a **county board or committee-of-the-whole meeting**: the full agenda as
published to the county's Diligent portal, and the complete automatic
transcript of the meeting video where the meeting was streamed — roughly
thirteen thousand words for a ninety-minute meeting.

For a **sub-body meeting** — zoning, planning, health, agricultural easement:
the same agenda materials. These meetings are not recorded, so there is no
record of what was said, only of what was scheduled.

For a **city, school district, park district or conservation district
meeting**: the agenda PDF, and the minutes PDF once the body publishes them —
which is usually at the following meeting, a month later. Scanned documents are
put through optical character recognition first.

The Resources column on every dispatch lists exactly which of these existed for
that meeting. Documents listed under *Also linked from the agenda* were **not**
read — they are backup material the agenda points at, published for
completeness.

## What the machine is told to do

Report, do not characterize. Record the vote count, not a theory of why anyone
voted that way. Correct the obvious mistakes in an automatic transcript —
proper nouns come through badly, numbers and dollar figures come through
cleanly — and quote sparingly. Invent nothing that is not in the source.

Where only an agenda exists and there is no record of what actually happened,
the dispatch is labelled an **agenda preview** and describes only what a body
was scheduled to take up. It will not tell you that anything was decided,
because nothing in its sources says so.

## What the front page is

The front page is assembled from **briefs** — short items of one paragraph each,
written from a dispatch rather than from the meeting behind it. A brief is a
summary of a summary, which is worth knowing: it is two removes from the
official record, and the dispatch it links to is always closer to the truth than
it is.

Between one and three are written per meeting, sorted into three kinds:

- **Civic** — something a resident of this county would want to know and could
  still act on. Residents turning out, speaking, or objecting counts for more
  here than anything else, followed by decisions still open to influence: a vote
  to come, a comment period, a hearing with a date, a vacancy taking
  applications.
- **Significant** — real decisions and real spending that don't rise to that.
- **Summary** — a plain account of a routine meeting, written only when nothing
  above applies, so that a dull meeting produces something honest rather than
  something inflated.

Briefs are never quotations, for the same reason dispatches aren't: most of what
they are drawn from began as an automatic caption.

## How the front page is chosen

Every brief from the last thirty days is a candidate. They are sorted by kind,
then by a score the model assigned when it wrote them, then by recency — and
then the shortlist is handed back to the model, which puts it in final order,
judging each brief against the others rather than in isolation.

That last pass exists because each brief is written without knowing any other
brief exists. Only something looking at them together can notice that a
committee taking a matter up and the board deciding it are one story and one
slot on the page.

The criteria it ranks on are the ones above: turnout, whether a decision is
still open, whether it changes what a resident pays, owns or is allowed to do,
the scale of public money involved, and whether a resident could learn it any
other way. Routine approvals, reports received and procedural motions rank down.

**There is one human lever.** A brief can be *pinned*, which forces it onto the
page regardless of where it ranked. Pinning cannot promote a brief — it keeps
its ranked position — and every pin is recorded in
[a file in the public repository](https://github.com/michaeldhart/city-county-summarizer/blob/main/docs/PINS.md).
Nothing else on this site is chosen by a person.

## Editions

Each time the front page is rebuilt it is published as a numbered issue and kept
at [/issues/]({{ '/issues/' | relative_url }}). Nothing is overwritten, so what
this publication led with on any given day stays on the record — including the
days it led with the wrong thing.

Back issues are frozen as published. If a dispatch is later corrected, the brief
printed in an issue that has already run is **not** updated, and may no longer
match the dispatch it links to. The dispatch is the one to trust.

## Where this is known to be wrong

- **Agendas are not always published in advance.** The county sometimes posts
  one close to, or after, the meeting. A meeting can appear on video days
  before a dispatch exists for it.
- **Two bodies never appear.** The Local Emergency Planning Committee and the
  Veteran's Assistance Commission do not publish to any portal we can read.
  They are on the beat list and have never produced a dispatch.
- **Older records drop off.** Some governments keep only a year or two of
  documents on their public site. Where material has since disappeared, a
  dispatch may link to less than it was written from.
- **Automatic transcripts garble names.** Most obvious errors get corrected.
  Some will not be.
- **A summary is not a record.** Where a dispatch and an official document
  disagree, the official document is right. Every one of them is linked.
- **A dispatch can be filed to the wrong beat.** Which body met is read from
  the label the meeting portal puts on it. When the county moved platforms in
  May 2026 every meeting carried over from the old system was relabelled as a
  County Board meeting, and nineteen dispatches — zoning, health, planning,
  the committees of the whole — sat on the County Board's beat until it was
  caught on September 17, 2026. They have been refiled, which moved their web
  addresses. The dispatches themselves were unaffected: each was written from
  its own meeting's agenda and names the body correctly.
- **The same meeting can appear twice.** A government occasionally lists one
  meeting under two entries with different documents attached. Both are read,
  and both are published, so a beat can carry two dispatches from one date.
- **Briefs don't know about each other.** Each is written from one meeting in
  isolation. The ranking pass is asked to catch the same story appearing twice,
  but it is the only thing that can, and it will sometimes miss.
- **A brief can describe a meeting nobody has a record of.** Where a dispatch
  was written from an agenda alone, its briefs describe what a body was
  scheduled to take up — not what it did. The dispatch says so; the brief has
  one paragraph and may not.
- **The wire goes quiet.** When too few meetings fall inside the window, it
  widens until the page fills, and the folio line says how far back it reached.

## What this site records about you

{% if site.goatcounter_code -%}
This site counts page views, using [GoatCounter](https://www.goatcounter.com),
an open-source analytics service. It sets no cookies and collects no personal
data, which is why you were not asked to dismiss a banner to read this. What it
records is the page, where you arrived from, your country, your browser and
operating system, and the size of your screen — counted in aggregate, never
tied to a person, never sold and never shared.

You do not have to take that on trust: the numbers are
[published in full](https://{{ site.goatcounter_code }}.goatcounter.com), the same view the publisher
has. A publication that asks you to believe a machine wrote it should not keep
its readership a secret.

{% else -%}
Nothing is counted. This site runs no analytics, sets no cookies, and has no
record that you were here.

{% endif -%}
Two things are not covered by that, and both are worth saying plainly.

**Reading by feed is invisible here.** [The wire]({{ '/feed/meetings.xml' | relative_url }}) and
[the edition]({{ '/feed/issues.xml' | relative_url }}) are fetched by your reader rather than loaded as
a page, and nothing on this site counts those. Whoever serves the files can see
the request, as with any web address.

**Searching stays in your browser.** The search index is downloaded and queried
on your machine rather than on a server, so what you type is not sent anywhere
as a search.

The one place this site asks for anything about you is the contact form, which
is a Google Form. Name and email are optional there — if you give them, they go
to Google along with whatever you write, and a correction does not need them.

## Corrections

If a dispatch gets something wrong, the underlying documents are linked at the
top of the page — start there, then
[send a correction](https://docs.google.com/forms/d/e/1FAIpQLScxpZW5UnwwEPaKGP5ls7szdGotiMh_0GA6FJIaHnRAG2WJiQ/viewform). The same goes for a brief, and for the front page
having led with the wrong thing: the ranking is a judgment, and judgments can
be argued with.

Corrections are made by re-writing the dispatch from source, not by editing the
sentence that was wrong — the dispatch has to keep matching the record it came
from.

That form is also the way to reach a person about anything else. Where the
fault is in the machinery rather than in one dispatch, the code that produces
all of this is public and can be [raised as an issue](https://github.com/michaeldhart/city-county-summarizer/issues) instead.
