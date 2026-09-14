---
layout: default
title: Home
---

# Boone County & Belvidere Government Watch

<p>Meeting recaps for local government in Boone County, Illinois — the county
board and its committees, the City of Belvidere, School District 100, the park
district, and the two conservation districts. Each meeting page summarizes the
agenda, the minutes, and where a meeting was streamed, its transcript.</p>

{% assign ordered = site.bodies | sort: "sort_key" %}
{% assign current = "" %}
{% for body in ordered %}
  {% if body.jurisdiction != current %}
    {% unless forloop.first %}
  </ul>
    {% endunless %}
  <h2>{{ body.jurisdiction }}</h2>
  <p class="about-link"><a href="{{ body.about_url | relative_url }}">About {{ body.jurisdiction }}</a></p>
  <ul>
    {% assign current = body.jurisdiction %}
  {% endif %}
  {% assign count = site.meetings | where: "body_id", body.body_id | size %}
    <li>
      <a href="{{ body.url | relative_url }}">{{ body.title }}</a>
      {% if count > 0 %}<span class="count">— {{ count }} meeting{% if count != 1 %}s{% endif %}</span>
      {% else %}<span class="count">— no meetings recorded yet</span>{% endif %}
    </li>
  {% if forloop.last %}
  </ul>
  {% endif %}
{% endfor %}

<p><a href="{{ '/feed/meetings.xml' | relative_url }}">Subscribe via RSS</a> — one entry per newly-ingested meeting, across every tracked body.</p>
