---
layout: default
title: Search
permalink: /search/
i18n: true
title_es: Buscar
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

<h1>{{ 'search_h1' | t }}</h1>

<p>{{ 'search_intro' | t }}</p>

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
  <p><strong>{{ 'search_nojs_a' | t }}</strong> {{ 'search_nojs_b' | t }}
  <a href="{{ '/beats/' | loc | relative_url }}">{{ 'search_nojs_link' | t }}</a>{{ 'search_nojs_c' | t }}</p>
</noscript>
