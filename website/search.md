---
layout: default
title: Search
permalink: /search/
---
{%- comment -%}
  layout: default, not page — the search page has no content of its own to
  index, and indexing it would make it a result for every query.

  relative_url supplies the /city-county-summarizer baseurl, so these paths
  work in local preview and in production without being edited between them.
  The bundle lives at /pagefind/ and is written by the Pagefind CLI after
  Jekyll builds; see the Deploy workflow and the README.
{%- endcomment -%}
<link href="{{ '/pagefind/pagefind-component-ui.css' | relative_url }}" rel="stylesheet">
<script src="{{ '/pagefind/pagefind-component-ui.js' | relative_url }}" type="module"></script>
<pagefind-config bundle-path="{{ '/pagefind/' | relative_url }}"></pagefind-config>

<h1>Search</h1>

<p>Full text of every meeting summary on this site, plus the reference pages
for each government. Summaries only — the agendas, minutes and transcripts
they were written from are linked from each meeting page.</p>

<div class="search-ui">
  <pagefind-input></pagefind-input>

  <div class="search-filters">
    <pagefind-filter-dropdown filter="jurisdiction"></pagefind-filter-dropdown>
    <pagefind-filter-dropdown filter="body"></pagefind-filter-dropdown>
    <pagefind-filter-dropdown filter="year"></pagefind-filter-dropdown>
  </div>

  <pagefind-summary></pagefind-summary>
  <pagefind-results></pagefind-results>
</div>

<noscript>
  <p><strong>Search needs JavaScript.</strong> Without it, browse by government
  from the <a href="{{ '/' | relative_url }}">home page</a> — every meeting is
  listed under its body.</p>
</noscript>
