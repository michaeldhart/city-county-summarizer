---
layout: default
title: Home
---

<h1 class="masthead">The Belvidere Wire</h1>
<p class="standfirst">A first draft of the public record — machine-written
dispatches from every public meeting in Boone County, Illinois. Twenty-two
beats across five governments: the county board and its committees, the City of
Belvidere, School District 100, the park district, and the two conservation
districts. Every dispatch is written from the official agenda, the minutes, and
— where a meeting is streamed — the video, and every source is linked from the
page.</p>

{% assign ordered = site.bodies | sort: "sort_key" %}
{% assign current = "" %}
{% for body in ordered %}
  {% if body.jurisdiction != current %}
    {% unless forloop.first %}
  </ul>
    {% endunless %}
  <h2>{{ body.jurisdiction }}</h2>
  <p class="about-link"><a href="{{ body.about_url | relative_url }}">Backgrounder: {{ body.jurisdiction }}</a></p>
  <ul>
    {% assign current = body.jurisdiction %}
  {% endif %}
  {% assign count = site.meetings | where: "body_id", body.body_id | size %}
    <li>
      <a href="{{ body.url | relative_url }}">{{ body.title }}</a>
      {% if count > 0 %}<span class="count">— {{ count }} dispatch{% if count != 1 %}es{% endif %}</span>
      {% else %}<span class="count">— no dispatches filed yet</span>{% endif %}
    </li>
  {% if forloop.last %}
  </ul>
  {% endif %}
{% endfor %}

<h2>The wire</h2>

<p><a href="{{ '/feed/meetings.xml' | relative_url }}">Subscribe to the wire</a>
— one entry per dispatch as it is filed, across every beat. Or read
<a href="{{ '/method/' | relative_url }}">how these are written</a>, which is
the part most worth reading first.</p>

<p class="colophon"><em>Belvidere, from</em> belvedere <em>— a structure built
for the view.</em></p>
