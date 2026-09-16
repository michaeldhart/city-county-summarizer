---
layout: default
title: Beats
permalink: /beats/
---
{%- comment -%}
  layout: default, not page — this is a list of links rather than content, and
  indexing it would make it a result for every body name on the site. Same
  reasoning the front page carries.

  This was the front page until the masthead redesign; it kept its shape and
  moved wholesale to /beats/.
{%- endcomment -%}

<h1>Beats</h1>

<p class="standfirst">Every body The Belvidere Wire covers, grouped by the
government it belongs to — twenty-two beats across five of them. Each links to
every dispatch filed from it, and each government links to its backgrounder:
how it is organized, who currently serves, and when its bodies meet.</p>

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
— one entry per dispatch as it is filed, across every beat.</p>
