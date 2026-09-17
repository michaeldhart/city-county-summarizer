---
layout: default
title: Beats
permalink: /beats/
---
{%- comment -%}
  layout: default, not page — this is a list of links rather than content, and
  indexing it would make it a result for every body name on the site. Same
  reasoning the front page carries.

  Cards, set in columns rather than a grid. The governments are lopsided — nine
  bodies for the county, one each for the two conservation districts — and a
  grid sizes every card in a row to the tallest of them, so the county would
  punch a nine-line hole beside the Park District. Columns let the cards flow
  and pack instead. The front page sets its briefs the same way, for the same
  reason.

  This was the front page until the masthead redesign; it kept its shape and
  moved wholesale to /beats/, then became this.
{%- endcomment -%}

<h1>Beats</h1>

<p class="standfirst">Every body The Belvidere Wire covers, grouped by the
government it belongs to — twenty-two beats across six of them. Each links to
every dispatch filed from it, and each government links to its backgrounder:
how it is organized, who currently serves, and when its bodies meet.</p>

{% assign ordered = site.bodies | sort: "sort_key" %}
<div class="beat-grid">
{% assign current = "" %}
{% for body in ordered %}
  {%- if body.jurisdiction != current %}
    {%- unless forloop.first %}
  </ul>
</section>
    {%- endunless %}
    {%- assign current = body.jurisdiction %}
{%- comment -%}
      A body whose about_url does not name its own jurisdiction is folded into
      another government's backgrounder — both conservation districts live
      inside the county's, being one-body governments. Link straight to their
      section rather than dropping the reader at the top of a page about
      someone else.

      The anchor is the jurisdiction id, pinned on those headings with a
      kramdown IAL and specified in general._BOONE_OUTLINE so a regenerated
      backgrounder keeps it. Deriving it instead would not work: the
      backgrounder is machine-written, so heading text can move, and Liquid's
      slugify cannot reproduce kramdown's id for the Soil & Water district
      anyway (kramdown drops the "&" and leaves a double hyphen).

      Checked rather than assumed. If a regeneration loses the anchor, the
      heading falls back to the page itself — a link to the top of the right
      backgrounder, not a dead fragment.
    {%- endcomment -%}
    {%- assign anchor = "" %}
    {%- unless body.about_url contains body.jurisdiction_id %}
      {%- assign about_page = site.pages | where: "url", body.about_url | first %}
      {%- assign ial = "{: #" | append: body.jurisdiction_id | append: " }" %}
      {%- assign attr = 'id="' | append: body.jurisdiction_id | append: '"' %}
      {%- if about_page.content contains ial or about_page.content contains attr %}
        {%- assign anchor = "#" | append: body.jurisdiction_id %}
      {%- endif %}
    {%- endunless %}
<section class="beat-card">
  <h2 class="beat-name"><a href="{{ body.about_url | relative_url }}{{ anchor }}">{{ body.jurisdiction }}</a></h2>
  <ul class="beat-bodies">
  {%- endif %}
  {%- assign count = site.meetings | where: "body_id", body.body_id | size %}
    <li>
      <a href="{{ body.url | relative_url }}">{{ body.title }}</a>
      {%- if count > 0 %}
      <span class="count">{{ count }} dispatch{% if count != 1 %}es{% endif %}</span>
      {%- else %}
      <span class="count">no dispatches filed yet</span>
      {%- endif %}
    </li>
  {%- if forloop.last %}
  </ul>
</section>
  {%- endif %}
{%- endfor %}
</div>

<section class="beat-wire">
  <h2>The wire</h2>
  <p><a href="{{ '/feed/meetings.xml' | relative_url }}">Subscribe to the wire</a>
  — one entry per dispatch as it is filed, across every beat. For one entry per
  edition instead, <a href="{{ '/feed/issues.xml' | relative_url }}">subscribe to
  the edition</a>.</p>
</section>
