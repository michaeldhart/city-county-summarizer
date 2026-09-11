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
