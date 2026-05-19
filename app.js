(function () {
  'use strict';

  // --- State ---
  var peptides = [];
  var references = {};
  var summary = {};
  var activeTier = 'all';
  var searchQuery = '';
  var activeRefType = 'rct';

  // --- DOM refs ---
  var grid = document.getElementById('peptideGrid');
  var searchInput = document.getElementById('searchInput');
  var filterChips = document.getElementById('filterChips');
  var resultsCount = document.getElementById('resultsCount');
  var drawerOverlay = document.getElementById('drawerOverlay');
  var detailDrawer = document.getElementById('detailDrawer');
  var drawerBody = document.getElementById('drawerBody');
  var drawerClose = document.getElementById('drawerClose');
  var disclaimerClose = document.getElementById('disclaimerClose');
  var disclaimer = document.getElementById('disclaimer');
  var refTabs = document.getElementById('refTabs');
  var refList = document.getElementById('refList');

  // --- Data loading ---
  function getDataURL() {
    // Support GitHub Pages subpath deployments
    var base = document.querySelector('base');
    if (base && base.href) {
      return new URL('data/peptide_details.json', base.href).href;
    }
    // Derive from script location or use relative path
    return './data/peptide_details.json';
  }

  function loadData() {
    showLoading();
    fetch(getDataURL())
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        summary = data.summary || {};
        references = data.references || {};
        peptides = deduplicatePeptides(data.peptides || []);
        updateStats(data);
        renderGrid();
        renderReferences();
      })
      .catch(function (err) {
        console.error('Failed to load peptide data:', err);
        showError(err.message);
      });
  }

  function deduplicatePeptides(raw) {
    // Keep last occurrence per slug (often the most detailed)
    var map = {};
    for (var i = 0; i < raw.length; i++) {
      map[raw[i].slug] = raw[i];
    }
    return Object.values(map);
  }

  // --- Stats ---
  function updateStats(data) {
    var refs = data.references || {};
    var rctCount = Array.isArray(refs.rct) ? refs.rct.length : 0;
    var preclinicalCount = Array.isArray(refs.preclinical) ? refs.preclinical.length : 0;
    var reviewCount = Array.isArray(refs.review) ? refs.review.length : 0;
    var officialCount = Array.isArray(refs.official) ? refs.official.length : 0;
    var observationalCount = Array.isArray(refs.observational) ? refs.observational.length : 0;
    var adverseCount = Array.isArray(refs.adverse) ? refs.adverse.length : 0;
    var sourceCounts = data.summary && data.summary.source_counts ? data.summary.source_counts : {};
    var totalRefs = data.summary && data.summary.total_references ? data.summary.total_references : (rctCount + preclinicalCount + reviewCount + officialCount + observationalCount + adverseCount);
    var indexedNotes = data.summary && data.summary.total_source_notes_indexed ? data.summary.total_source_notes_indexed : totalRefs;

    // Update hero badge
    var badge = document.querySelector('.hero-badge');
    if (badge) {
      badge.textContent = peptides.length + ' Compounds · ' + indexedNotes + ' Vault Notes · One Canonical Source';
    }

    // Update stat cards with the canonical vault counts instead of legacy tier buckets.
    setTextById('statRCT', sourceCounts.study || 0);
    setTextById('statPreclinical', sourceCounts.youtube || 0);
    setTextById('statReviews', totalRefs);

    // Update references section description
    var sectionDesc = document.querySelector('.references-section .section-desc');
    if (sectionDesc) {
      sectionDesc.textContent = totalRefs + ' public links indexed from the regular peptide vault. Inventory/orders/private notes are excluded from this public build.';
    }

    // Update reference tabs counts
    var tabCounts = {
      rct: rctCount,
      preclinical: preclinicalCount,
      review: reviewCount,
      official: officialCount,
      observational: observationalCount,
      adverse: adverseCount
    };
    var tabs = refTabs ? refTabs.querySelectorAll('.ref-tab') : [];
    for (var t = 0; t < tabs.length; t++) {
      var type = tabs[t].getAttribute('data-type');
      var countEl = tabs[t].querySelector('.ref-count');
      if (countEl && tabCounts[type] !== undefined) {
        countEl.textContent = tabCounts[type];
      }
    }

    // Update footer
    var footerSource = document.querySelector('.footer-source');
    if (footerSource) {
      footerSource.textContent = 'Data: ' + totalRefs + ' references from public research literature.';
    }
  }

  function setTextById(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  // --- Rendering ---
  function showLoading() {
    if (!grid) return;
    grid.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><p>Loading peptide data\u2026</p></div>';
  }

  function showError(msg) {
    if (!grid) return;
    grid.innerHTML = '<div class="error-state"><p><strong>Failed to load data</strong></p><p>' + escapeHtml(msg) + '</p><p style="margin-top:12px;color:var(--text-dim);">Ensure data/peptide_details.json is accessible.</p></div>';
  }

  function renderGrid() {
    if (!grid) return;

    var filtered = getFilteredPeptides();
    if (resultsCount) {
      resultsCount.textContent = filtered.length + ' of ' + peptides.length + ' compounds';
    }

    if (filtered.length === 0) {
      grid.innerHTML = '<div class="loading-state"><p>No compounds match your search.</p></div>';
      return;
    }

    var html = '';
    for (var i = 0; i < filtered.length; i++) {
      var p = filtered[i];
      html += renderCard(p);
    }
    grid.innerHTML = html;

    // Attach click listeners
    var cards = grid.querySelectorAll('.peptide-card');
    for (var c = 0; c < cards.length; c++) {
      cards[c].addEventListener('click', onCardClick);
    }
  }

  function renderCard(p) {
    var tierClass = 'tier-' + p.tier.toLowerCase();
    return '<div class="peptide-card" data-slug="' + escapeAttr(p.slug) + '" style="--card-tier-color:' + escapeAttr(p.tier_color) + '">' +
      '<div class="card-header">' +
        '<span class="card-name">' + escapeHtml(p.name) + '</span>' +
        '<span class="card-tier"><span class="tier-badge ' + tierClass + '">' + escapeHtml(p.tier) + '</span></span>' +
      '</div>' +
      '<p class="card-one-liner">' + escapeHtml(p.one_liner) + '</p>' +
      '<div class="card-vault-meta">' + escapeHtml(p.category || 'Regular vault') + ' · ' + sourceSummary(p) + '</div>' +
    '</div>';
  }

  function sourceSummary(p) {
    var counts = p.source_counts || {};
    var total = 0;
    var parts = [];
    Object.keys(counts).sort().forEach(function (key) {
      total += counts[key];
      parts.push(counts[key] + ' ' + key);
    });
    return total ? parts.join(', ') : 'overview only';
  }

  // --- Filtering ---
  function getFilteredPeptides() {
    var q = searchQuery.toLowerCase().trim();
    return peptides.filter(function (p) {
      var matchesTier = activeTier === 'all' || p.tier === activeTier;
      var libraryText = (p.library_entries || []).map(function (e) { return [e.title, e.excerpt, e.vault_path].join(' '); }).join(' ');
      var noteText = (p.source_notes || []).map(function (n) { return [n.title, n.source_name, n.vault_path].join(' '); }).join(' ');
      var haystack = [p.name, p.one_liner, p.slug, p.category, (p.aliases || []).join(' '), libraryText, noteText].join(' ').toLowerCase();
      var matchesSearch = !q || haystack.indexOf(q) !== -1;
      return matchesTier && matchesSearch;
    });
  }

  // --- Detail Drawer ---
  function onCardClick(e) {
    var card = e.currentTarget;
    var slug = card.getAttribute('data-slug');
    var p = peptides.find(function (x) { return x.slug === slug; });
    if (!p) return;
    openDrawer(p);
  }

  function openDrawer(p) {
    var tierClass = 'tier-' + p.tier.toLowerCase();
    var aliases = (p.aliases && p.aliases.length) ? p.aliases.join(', ') : '—';
    var html = '<div class="drawer-tier-badge"><span class="tier-badge ' + tierClass + '">' + escapeHtml(p.tier) + '</span><span style="font-size:12px;color:var(--text-muted)">Tier ' + escapeHtml(p.tier) + '</span></div>' +
      '<h2 class="drawer-name">' + escapeHtml(p.name) + '</h2>' +
      '<div class="drawer-one-liner">' + escapeHtml(p.one_liner) + '</div>' +
      '<div class="drawer-section-title">Regular Vault Details</div>' +
      '<div class="drawer-meta">' +
        '<div class="drawer-meta-item"><div class="drawer-meta-label">Category</div><div class="drawer-meta-value">' + escapeHtml(p.category || '—') + '</div></div>' +
        '<div class="drawer-meta-item"><div class="drawer-meta-label">Aliases</div><div class="drawer-meta-value">' + escapeHtml(aliases) + '</div></div>' +
        '<div class="drawer-meta-item"><div class="drawer-meta-label">Source notes</div><div class="drawer-meta-value">' + escapeHtml(sourceSummary(p)) + '</div></div>' +
        '<div class="drawer-meta-item"><div class="drawer-meta-label">Vault path</div><div class="drawer-meta-value" style="font-family:var(--mono);font-size:12px;">' + escapeHtml(p.vault_path || p.slug) + '</div></div>' +
        '<div class="drawer-meta-item"><div class="drawer-meta-label">Tier</div><div class="drawer-meta-value">' + escapeHtml(p.tier) + ' — ' + getTierDescription(p.tier) + '</div></div>' +
      '</div>' + renderLibraryEntries(p) + renderSourceNotes(p);

    if (drawerBody) drawerBody.innerHTML = html;
    if (detailDrawer) {
      detailDrawer.classList.add('open');
      detailDrawer.setAttribute('aria-hidden', 'false');
    }
    if (drawerOverlay) drawerOverlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }


  function renderLibraryEntries(p) {
    var entries = p.library_entries || [];
    if (!entries.length) return '';
    var html = '<div class="drawer-section-title">Full Old-Vault Library Under ' + escapeHtml(p.name) + ' (' + entries.length + ')</div>' +
      '<div class="drawer-source-list drawer-library-list">';
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      var href = e.href ? ' href="' + escapeAttr(e.href) + '" target="_blank" rel="noopener noreferrer"' : '';
      var label = e.overview ? 'overview' : (e.type || 'library');
      html += '<a class="drawer-source-item drawer-library-item"' + href + '>' +
        '<strong>' + escapeHtml(e.title || 'Vault page') + '</strong>' +
        '<span>' + escapeHtml((e.category || 'Old vault') + ' · ' + label + ' · ' + (e.vault_path || '')) + '</span>';
      if (e.excerpt) {
        html += '<em>' + escapeHtml(e.excerpt) + '</em>';
      }
      html += '</a>';
    }
    return html + '</div>';
  }

  function renderSourceNotes(p) {
    var notes = p.source_notes || [];
    if (!notes.length) return '';
    var html = '<div class="drawer-section-title">Obsidian Vault Notes (' + notes.length + ')</div><div class="drawer-source-list">';
    for (var i = 0; i < notes.length; i++) {
      var n = notes[i];
      var tag = n.url ? 'a' : 'div';
      var href = n.url ? ' href="' + escapeAttr(n.url) + '" target="_blank" rel="noopener noreferrer"' : '';
      html += '<' + tag + ' class="drawer-source-item"' + href + '>' +
        '<strong>' + escapeHtml(n.title || 'Source note') + '</strong>' +
        '<span>' + escapeHtml((n.source_name || 'Regular vault') + ' · ' + (n.type || 'note')) + '</span>' +
      '</' + tag + '>';
    }
    return html + '</div>';
  }

  function closeDrawer() {
    if (detailDrawer) {
      detailDrawer.classList.remove('open');
      detailDrawer.setAttribute('aria-hidden', 'true');
    }
    if (drawerOverlay) drawerOverlay.classList.remove('open');
    document.body.style.overflow = '';
  }

  function getTierDescription(tier) {
    var map = {
      S: 'FDA-approved or Phase 3 RCT',
      A: 'Strong preclinical + limited human data',
      B: 'Promising early-phase or combo data',
      C: 'Mixed evidence or niche application',
      D: 'Minimal or outdated evidence',
      F: 'High risk / no quality human data'
    };
    return map[tier] || '';
  }

  // --- References ---
  function renderReferences() {
    if (!refList) return;
    var items = references[activeRefType] || [];
    if (items.length === 0) {
      refList.innerHTML = '<p style="color:var(--text-dim);padding:20px;">No references in this category.</p>';
      return;
    }

    var html = '';
    for (var i = 0; i < items.length; i++) {
      var ref = items[i];
      var tag = ref.url ? 'a' : 'div';
      var hrefAttr = ref.url ? ' href="' + escapeAttr(ref.url) + '" target="_blank" rel="noopener noreferrer"' : '';
      html += '<' + tag + ' class="ref-item"' + hrefAttr + '>' +
        '<div class="ref-header">' + escapeHtml(ref.header || '') + '</div>' +
        '<div class="ref-description">' + escapeHtml(ref.description || '') + '</div>' +
        (ref.notes ? '<div class="ref-notes">' + escapeHtml(ref.notes) + '</div>' : '') +
      '</' + tag + '>';
    }
    refList.innerHTML = html;
  }

  // --- Event listeners ---
  function bindEvents() {
    // Search
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        searchQuery = searchInput.value;
        renderGrid();
      });
    }

    // Filter chips
    if (filterChips) {
      filterChips.addEventListener('click', function (e) {
        var chip = e.target.closest('.chip');
        if (!chip) return;
        var tier = chip.getAttribute('data-tier');
        activeTier = tier;
        // Update active state
        var chips = filterChips.querySelectorAll('.chip');
        for (var i = 0; i < chips.length; i++) {
          chips[i].classList.toggle('active', chips[i].getAttribute('data-tier') === tier);
        }
        renderGrid();
      });
    }

    // Drawer close
    if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
    if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDrawer();
    });

    // Disclaimer
    if (disclaimerClose && disclaimer) {
      disclaimerClose.addEventListener('click', function () {
        disclaimer.classList.add('hidden');
        try { sessionStorage.setItem('disclaimer-dismissed', '1'); } catch (e) { /* ok */ }
      });
      // Auto-dismiss if previously dismissed
      try {
        if (sessionStorage.getItem('disclaimer-dismissed')) {
          disclaimer.classList.add('hidden');
        }
      } catch (e) { /* ok */ }
    }

    // Reference tabs
    if (refTabs) {
      refTabs.addEventListener('click', function (e) {
        var tab = e.target.closest('.ref-tab');
        if (!tab) return;
        activeRefType = tab.getAttribute('data-type');
        var tabs = refTabs.querySelectorAll('.ref-tab');
        for (var i = 0; i < tabs.length; i++) {
          tabs[i].classList.toggle('active', tabs[i] === tab);
        }
        renderReferences();
      });
    }

    // Smooth scroll for nav
    var navLinks = document.querySelectorAll('.nav-link, .hero-actions a');
    for (var i = 0; i < navLinks.length; i++) {
      navLinks[i].addEventListener('click', function (e) {
        var href = this.getAttribute('href');
        if (href && href.startsWith('#')) {
          var target = document.querySelector(href);
          if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth' });
          }
        }
      });
    }
  }

  // --- Utilities ---
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function escapeAttr(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // --- Init ---
  function init() {
    bindEvents();
    loadData();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
