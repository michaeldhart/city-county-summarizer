---
layout: default
title: Home
---
{%- comment -%}
  PLACEHOLDER FRONT PAGE.

  The body list that lived here moved wholesale to /beats/. What replaces it is
  a newspaper-style front page — lead dispatch, recent filings, something that
  reads as an edition rather than an index — and that is a separate design pass.

  Until then this page is deliberately thin but not broken: masthead,
  standfirst, and a way into each section, so a visitor who lands on the root
  URL is never stranded. Keep layout: default — a front page is links, not
  content, and `page` would put it in the search index.
{%- endcomment -%}

<h1 class="masthead">The Belvidere Wire</h1>
<p class="standfirst">A first draft of the public record — machine-written
dispatches from every public meeting in Boone County, Illinois. Twenty-two
beats across five governments: the county board and its committees, the City of
Belvidere, School District 100, the park district, and the two conservation
districts. Every dispatch is written from the official agenda, the minutes, and
— where a meeting is streamed — the video, and every source is linked from the
page.</p>

<ul>
  <li><a href="{{ '/beats/' | relative_url }}">Beats</a> — every body we cover,
  grouped by government, with each one's dispatches and backgrounder.</li>
  <li><a href="{{ '/search/' | relative_url }}">Search</a> — full text of every
  dispatch on the wire.</li>
  <li><a href="{{ '/method/' | relative_url }}">How this is written</a> — what
  the machine sees, what it is told to do, and where it is known to be wrong.</li>
  <li><a href="{{ '/feed/meetings.xml' | relative_url }}">The wire</a> — one
  entry per dispatch as it is filed.</li>
</ul>

<p class="colophon"><em>Belvidere, from</em> belvedere <em>— a structure built
for the view.</em></p>
