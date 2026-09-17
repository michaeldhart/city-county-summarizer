---
layout: default
title: Search
permalink: /search/
---
{%- comment -%}
  layout: default, not page — the search page has no content of its own to
  index, and indexing it would make it a result for every query.

  relative_url resolves whatever baseurl is configured, so these paths work in
  local preview and in production without being edited between them. That
  baseurl is empty now the site serves from belviderewire.com, but it was
  /city-county-summarizer until the domain move — which is exactly why the
  filter stays rather than the paths being written out.

  The bundle lives at /pagefind/ and is written by the Pagefind CLI after
  Jekyll builds; see the Deploy workflow and the README.
{%- endcomment -%}
<link href="{{ '/pagefind/pagefind-component-ui.css' | relative_url }}" rel="stylesheet">
<script src="{{ '/pagefind/pagefind-component-ui.js' | relative_url }}" type="module"></script>
<pagefind-config bundle-path="{{ '/pagefind/' | relative_url }}"></pagefind-config>

<h1>Search the archive</h1>

<p>What's searched here is the dispatches themselves: every one in full, along
with each government's backgrounder and the pages explaining how this works.
The agendas, minutes and video behind them aren't indexed, so something raised
at a meeting won't necessarily turn up in the summary written from it. If a
dispatch looks close to what you're after, open it — the Resources list beside
it links the original documents, which are always nearer the record than a
summary can be.</p>

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
  from the <a href="{{ '/beats/' | relative_url }}">beats page</a> — every
  dispatch is listed under its beat.</p>
</noscript>
