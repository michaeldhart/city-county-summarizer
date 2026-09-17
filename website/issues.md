---
layout: default
title: Back issues
permalink: /issues/
---
{%- comment -%}
  layout: default, not page — a list of links, like the front page and /beats/.
  Indexing it would make it a result for every headline the site has ever run.
{%- endcomment -%}

<h1>Back issues</h1>

<p class="standfirst">Every edition of The Belvidere Wire, newest first. Each is
kept as it was published — the briefs it led with, in the order it ran them.
Regenerating the front page starts a new issue rather than overwriting the last
one.</p>

<p><a href="{{ '/feed/issues.xml' | relative_url }}">Subscribe to the edition</a>
— one entry per issue, the briefs it led with. For every dispatch as it is
filed, <a href="{{ '/feed/meetings.xml' | relative_url }}">subscribe to the
wire</a> instead.</p>

{% assign issues = site.front_pages | sort: "issue" | reverse %}
{% if issues.size == 0 %}
  <p><em>No issues published yet.</em></p>
{% else %}
<ul class="issue-list">
  {% for issue in issues %}
  <li>
    <a href="{{ issue.url | relative_url }}">No. {{ issue.issue }}</a>
    <span class="count">— {{ issue.generated | date: "%B %-d, %Y" }}, {{ issue.brief_count }} brief{% if issue.brief_count != 1 %}s{% endif %}</span>
    {% if issue.lead %}<br><span class="issue-lead">{{ issue.lead }}</span>{% endif %}
  </li>
  {% endfor %}
</ul>
{% endif %}
