---
title: How this is written
permalink: /method/
---

# How this is written

**No human reporter attends these meetings.** Every dispatch on The Belvidere
Wire is written by Claude, an AI model made by Anthropic, from the primary
documents a government publishes itself. Nothing here is reported, and nothing
here is edited by a person before it is filed.

That is an unusual thing for a publication to say, so this page says it plainly
and sets out exactly what the machine sees, what it is told to do, and where it
is known to be wrong.

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

## Corrections

If a dispatch gets something wrong, the underlying documents are linked at the
top of the page — start there, then
[open an issue](https://github.com/michaeldhart/city-county-summarizer/issues).
Corrections are made by re-writing the dispatch from source, and the code that
produces all of this is public.
