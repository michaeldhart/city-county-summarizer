---
layout: default
title: Beats
permalink: /beats/
i18n: true
title_es: Secciones
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

<h1>{{ 'beats_h1' | t }}</h1>

<p class="standfirst">{{ 'beats_standfirst' | t }}</p>

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
  <h2 class="beat-name"><a href="{{ body.about_url | loc | relative_url }}{{ anchor }}">{{ body.jurisdiction }}</a></h2>
  <ul class="beat-bodies">
  {%- endif %}
  {%- assign count = site.meetings | where: "body_id", body.body_id | size %}
    <li>
      <a href="{{ body.url | loc | relative_url }}">{{ body.title }}</a>
      {%- if count > 0 %}
      <span class="count">{% if count == 1 %}{{ 'count_one' | t }}{% else %}{{ 'count_many' | t: count }}{% endif %}</span>
      {%- else %}
      <span class="count">{{ 'count_none' | t }}</span>
      {%- endif %}
    </li>
  {%- if forloop.last %}
  </ul>
</section>
  {%- endif %}
{%- endfor %}
</div>

<section class="beat-wire">
  <h2>{{ 'wire_h2' | t }}</h2>
  <p><a href="{{ '/feed/meetings.xml' | loc | relative_url }}">{{ 'feed_wire' | t }}</a>
  {{ 'wire_a' | t }} <a href="{{ '/feed/issues.xml' | loc | relative_url }}">{{ 'feed_edition_lc' | t }}</a>.</p>
</section>
