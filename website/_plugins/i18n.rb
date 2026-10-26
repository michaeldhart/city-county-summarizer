# frozen_string_literal: true

# Spanish version of the site, adapted from eyes-on-hawkeye's plugin.
#
# English lives at /, Spanish at /es/. Three kinds of Spanish page exist:
#
#   - Pages marked `i18n: true` (beats, issues, search) are cloned under /es/ at
#     build time. Any front matter key ending in _es replaces its English twin.
#   - Bodies (beats) are always cloned, since they are structure, not prose.
#   - Dispatches, issues and the front page are cloned only when the translation
#     store has a file for them: website/_i18n/es/{meetings,front_pages}/<name>.md
#     and website/_i18n/es/index.md. An untranslated dispatch simply has no
#     Spanish page, and every link to it falls back to the English one (`loc`).
#
# Hand-written Spanish pages (method, why, ...) live in es/ with an explicit
# /es/ permalink and are registered as twins automatically.
#
# Liquid helpers, all keyed off the lang of the page being rendered:
#   {{ 'nav_beats' | t }}          UI string from _data/i18n/<lang>.yml (English if missing)
#   {{ x | tx: 'title' }}          x.title_es on Spanish pages, falling back to x.title
#   {{ url | loc | relative_url }} the Spanish twin of url on Spanish pages, if one exists
#   {{ d | fdate: 'short' }}       "Sep 8, 2026" / "8 sep 2026" (also 'long')
#   {{ nil | i18n_strings | jsonify }}  all UI strings, for inline scripts

require 'date'
require 'yaml'

module WireI18n
  MONTHS = {
    'en' => { long: %w[January February March April May June July August September October November December],
              short: %w[Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec] },
    'es' => { long: %w[enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre],
              short: %w[ene feb mar abr may jun jul ago sep oct nov dic] }
  }.freeze
  FORMATS = {
    'long' => { 'en' => '%B %-d, %Y', 'es' => '%-d de %B de %Y' },
    'short' => { 'en' => '%b %-d, %Y', 'es' => '%-d %b %Y' }
  }.freeze

  # English url => Spanish url, for every page that has a Spanish twin.
  TWINS = {}

  module Filters
    def t(key, a = nil, b = nil)
      i18n = @context.registers[:site].data['i18n']
      s = i18n.dig(lang_now, key)
      if s.nil?
        s = i18n.dig('en', key)
        Jekyll.logger.warn 'i18n:', "missing #{lang_now} string '#{key}'" if lang_now != 'en'
      end
      s = key if s.nil?
      s.to_s.gsub('%1', a.to_s).gsub('%2', b.to_s)
    end

    def tx(item, field)
      return item[field] unless lang_now == 'es'

      v = item["#{field}_es"]
      v.nil? || v.to_s.strip.empty? ? item[field] : v
    end

    def loc(url)
      return url unless lang_now == 'es' && url.to_s.start_with?('/')

      path, rest = url.to_s.split(/(?=[#?])/, 2)
      twin = TWINS[path]
      twin ? "#{twin}#{rest}" : url
    end

    def fdate(input, style = 'long')
      return '' if input.nil? || input.to_s.empty?

      time = input.respond_to?(:strftime) ? input : Time.parse(input.to_s)
      fmt = FORMATS.dig(style, lang_now) || style
      m = time.month - 1
      fmt = fmt.gsub('%B', MONTHS[lang_now][:long][m]).gsub('%b', MONTHS[lang_now][:short][m])
      time.strftime(fmt)
    end

    def i18n_strings(_ignored = nil)
      i18n = @context.registers[:site].data['i18n']
      (i18n['en'] || {}).merge(i18n[lang_now] || {})
    end

    private

    def lang_now
      (@context.registers[:page] || {})['lang'] || 'en'
    end
  end

  class Generator < Jekyll::Generator
    safe true
    priority :low

    COLLECTION_LAYOUTS = { 'bodies' => 'body', 'meetings' => 'meeting', 'front_pages' => 'front-page' }.freeze
    # Collections whose Spanish page exists only when the store has a file.
    STORED = %w[meetings front_pages].freeze

    def generate(site)
      TWINS.clear
      store = File.join(site.source, '_i18n', 'es')
      clones = []
      pairs = []

      COLLECTION_LAYOUTS.each do |label, layout|
        coll = site.collections[label] or next
        coll.docs.each do |doc|
          stored = nil
          if STORED.include?(label)
            stored = read_store(File.join(store, label, "#{doc.basename_without_ext}.md"))
            next unless stored
          end
          clone = clone_doc(site, doc, layout, stored)
          clones << clone
          pairs << [doc, clone]
        end
      end

      home = read_store(File.join(store, 'index.md'))
      english_home = site.pages.find { |p| p.url == '/' }
      if home && english_home
        clone = stored_page(site, '', 'index.md', '/es/', 'front-page', home)
        clones << clone
        pairs << [english_home, clone]
      end

      site.pages.select { |p| p.data['i18n'] }.each do |page|
        clone = clone_page(site, page)
        clones << clone
        pairs << [page, clone]
      end

      # Cloned pages go first: render order is array order, and the Spanish
      # feeds read other pages' rendered `content`, which only exists once those
      # pages have rendered.
      site.pages.unshift(*clones)

      # Hand-written Spanish pages under es/ are twins of the English page at
      # the same path without the prefix.
      site.pages.each do |p|
        next unless p.url.start_with?('/es/') && !clones.include?(p)

        p.data['lang'] ||= 'es'
        en = site.pages.find { |q| q.url == p.url.sub('/es', '') }
        if en
          pairs << [en, p]
        else
          # jekyll-feed adds its pages after this generator runs, so the
          # English feed cannot be found yet; the link mapping is all it needs.
          TWINS[p.url.sub('/es', '')] = p.url
        end
      end

      pairs.each do |en, es|
        TWINS[en.url] = es.url
        en.data['alt_url'] = es.url
        es.data['alt_url'] = en.url
      end
    end

    private

    def read_store(path)
      return nil unless File.file?(path)

      m = File.read(path, encoding: 'utf-8').match(/\A---\s*\n(.*?)\n---\s*\n?(.*)\z/m)
      raise "#{path}: no front matter" unless m

      { data: YAML.safe_load(m[1], permitted_classes: [Date, Time]) || {}, content: m[2] }
    end

    def clone_doc(site, doc, layout, stored)
      dir = File.join('es', doc.url.sub(%r{\A/}, '').chomp('/'))
      page = Jekyll::PageWithoutAFile.new(site, site.source, dir, 'index.md')
      page.content = stored ? stored[:content] : doc.content
      page.data.merge!(doc.data)
      page.data.merge!(stored[:data]) if stored
      page.data['layout'] = layout
      page.data['permalink'] = "/#{dir}/"
      page.data['es_meeting'] = true if layout == 'meeting'
      page.data['es_issue'] = true if layout == 'front-page'
      localize!(site, page.data)
      page
    end

    def stored_page(site, dir, name, permalink, layout, stored)
      page = Jekyll::PageWithoutAFile.new(site, site.source, File.join('es', dir), name)
      page.content = stored[:content]
      page.data.merge!(stored[:data])
      page.data['layout'] = layout
      page.data['permalink'] = permalink
      localize!(site, page.data)
      page
    end

    def clone_page(site, src)
      src_dir = File.dirname(src.relative_path).sub(/\A\.\z/, '')
      page = Jekyll::PageWithoutAFile.new(site, site.source, File.join('es', src_dir), src.name)
      page.content = src.content
      page.data.merge!(src.data)
      page.data.delete('i18n')
      page.data['permalink'] = "/es#{src.data['permalink']}" if src.data['permalink']
      localize!(site, page.data)
      page
    end

    def localize!(site, data)
      data.keys.grep(/_es\z/).each do |k|
        v = data[k]
        data[k.delete_suffix('_es')] = v unless v.nil? || v.to_s.strip.empty?
      end
      data['lang'] = 'es'
      # seo-tag falls back to site.description, which is English.
      data['description'] ||= site.data.dig('i18n', 'es', 'site_description')
    end
  end
end

Liquid::Template.register_filter(WireI18n::Filters)
