---
layout: default
title: Home
---

# Boone County Government Watch

{% assign sorted_bodies = site.bodies | sort: "title" %}
<ul>
{% for body in sorted_bodies %}
  <li><a href="{{ body.url | relative_url }}">{{ body.title }}</a></li>
{% endfor %}
</ul>

<p><a href="{{ '/feed/meetings.xml' | relative_url }}">Subscribe via RSS</a> — one entry per newly-ingested meeting, across all tracked bodies.</p>
