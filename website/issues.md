---
layout: default
title: Back issues
permalink: /issues/
i18n: true
title_es: Números anteriores
---
{%- comment -%}
  layout: default, not page — a list of links, like the front page and /beats/.
  Indexing it would make it a result for every headline the site has ever run.
{%- endcomment -%}

<h1>{{ 'issues_h1' | t }}</h1>

<p class="standfirst">{{ 'issues_standfirst' | t }}</p>

<p><a href="{{ '/feed/issues.xml' | loc | relative_url }}">{{ 'feed_edition' | t }}</a>
{{ 'issues_feed_a' | t }} <a href="{{ '/feed/meetings.xml' | loc | relative_url }}">{{ 'feed_wire_lc' | t }}</a>{{ 'issues_feed_b' | t }}</p>

{% assign issues = site.front_pages | sort: "issue" | reverse %}
{% if issues.size == 0 %}
  <p><em>{{ 'no_issues' | t }}</em></p>
{% else %}
<ul class="issue-list">
  {% for issue in issues %}
  <li>
    {%- assign issue_url = issue.url | loc -%}
    {%- assign issue_date = issue.generated | fdate: 'long' -%}
    <a href="{{ issue_url | relative_url }}">{{ 'issue_no' | t: issue.issue }}</a>
    <span class="count">— {{ issue_date }}, {% if issue.brief_count == 1 %}{{ 'brief_one' | t }}{% else %}{{ 'brief_many' | t: issue.brief_count }}{% endif %}</span>
    {%- if page.lang == 'es' and issue_url == issue.url %} <span class="count">{{ 'in_english' | t }}</span>{% endif %}
    {% if issue.lead %}<br><span class="issue-lead">{{ issue.lead }}</span>{% endif %}
  </li>
  {% endfor %}
</ul>
{% endif %}
