'use strict';

const state = {
  overview: null,
  events: [],
  detail: null,
  anchorDetail: null,
  eventId: null,
  milestoneId: null,
  seriesId: null,
  visibility: 'ALL',
  search: '',
  eventRequestToken: 0,
  anchorRequestToken: 0,
};

const EVENT_ZH = {
  'event-01': '\u4e16\u536b\u7ec4\u7ec7\u5c06\u65b0\u51a0\u75ab\u60c5\u5b9a\u6027\u4e3a\u5168\u7403\u5927\u6d41\u884c',
  'event-02': '\u4fc4\u7f57\u65af\u5bf9\u4e4c\u514b\u5170\u53d1\u52a8\u5168\u9762\u8fdb\u653b',
  'event-03': '\u7f8e\u8054\u50a8\u52a0\u606f 75 \u4e2a\u57fa\u70b9',
  'event-04': '\u4e2d\u56fd\u53d1\u5e03\u4f18\u5316\u75ab\u60c5\u9632\u63a7\u5341\u6761\u63aa\u65bd',
  'event-05': '\u7845\u8c37\u94f6\u884c\u5173\u95ed\u53ca\u76d1\u7ba1\u90e8\u95e8\u7a33\u5b9a\u91d1\u878d\u7cfb\u7edf',
  'event-06': 'OPEC+ \u6210\u5458\u5ba3\u5e03\u989d\u5916\u81ea\u613f\u51cf\u4ea7',
  'event-07': '2023 \u5e74 10 \u6708 7 \u65e5\u4e2d\u4e1c\u51b2\u7a81\u5347\u7ea7',
  'event-08': '\u65e5\u672c\u94f6\u884c\u7ed3\u675f\u8d1f\u5229\u7387\u653f\u7b56',
  'event-09': '\u4e2d\u56fd\u5ba3\u5e03\u4e00\u63fd\u5b50\u91d1\u878d\u652f\u6301\u653f\u7b56',
  'event-10': '\u7f8e\u56fd\u5ba3\u5e03\u5e7f\u6cdb\u5bf9\u7b49\u5173\u7a0e\u63aa\u65bd',
};

const SERIES_ZH = {
  SP500: '\u6807\u666e 500',
  VIXCLS: 'VIX \u6ce2\u52a8\u7387',
  DCOILWTICO: 'WTI \u539f\u6cb9',
  DCOILBRENTEU: '\u5e03\u4f26\u7279\u539f\u6cb9',
  DEXCHUS: '\u7f8e\u5143/\u4eba\u6c11\u5e01',
  DGS10: '\u7f8e\u56fd 10 \u5e74\u671f\u56fd\u503a',
  DTWEXBGS: '\u7f8e\u5143\u5e7f\u4e49\u6307\u6570',
  DEXJPUS: '\u7f8e\u5143/\u65e5\u5143',
};

const PHASE_ZH = {
  PRECONDITION: '\u524d\u7f6e\u80cc\u666f',
  INITIAL_SHOCK: '\u9996\u6b21\u51b2\u51fb',
  ESCALATION: '\u5347\u7ea7',
  POLICY_RESPONSE: '\u653f\u7b56\u54cd\u5e94',
  EASING: '\u7f13\u548c',
  SECONDARY_SHOCK: '\u4e8c\u6b21\u51b2\u51fb',
  EVIDENCE_INPUT: '\u8bc1\u636e\u8f93\u5165',
};

const EXPECTATION_ZH = {
  SCHEDULED_RELEASE: '\u9884\u5b9a\u53d1\u5e03',
  UNSCHEDULED_SHOCK: '\u7a81\u53d1\u51b2\u51fb',
  EVOLVING_EVENT: '\u6301\u7eed\u6f14\u5316',
};

const CONFOUNDER_ZH = {
  CLEAN: '\u65e0\u663e\u8457\u91cd\u53e0\u4e8b\u4ef6\uff0c\u53ef\u8fdb\u5165\u5e72\u51c0\u5f52\u56e0\u4e3b\u5206\u3002',
  MINOR: '\u5b58\u5728\u8f7b\u5fae\u91cd\u53e0\u4e8b\u4ef6\uff0c\u9700\u5728\u8fb9\u9645\u89e3\u91ca\u4e2d\u4fdd\u7559\u3002',
  MATERIAL: '\u91cd\u8981\u7ade\u4e89\u89e3\u91ca\u4e0e\u4e8b\u4ef6\u7a97\u53e3\u91cd\u53e0\uff0c\u6837\u672c\u53ea\u8fdb\u5165\u6311\u6218\u96c6\u3002',
  DOMINANT: '\u7ade\u4e89\u9a71\u52a8\u53ef\u80fd\u4e3b\u5bfc\u884c\u60c5\uff0c\u7981\u6b62\u4f5c\u4e3a\u5e72\u51c0\u5f52\u56e0\u6837\u672c\u3002',
  UNRESOLVED: '\u73b0\u6709\u8bc1\u636e\u65e0\u6cd5\u89e3\u51b3\u7ade\u4e89\u89e3\u91ca\uff0c\u5e94\u4f18\u5148\u62d2\u7b54\u3002',
};

const WINDOW_ORDER = ['T60', 'T20', 'T1', 'D1', 'D3', 'D5', 'D20', 'M3'];

function el(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function api(path) {
  const response = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new Error('API ' + response.status);
  }
  return response.json();
}

function formatDateTime(value) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZoneName: 'short',
  }).format(date);
}

function formatNumber(value, digits) {
  if (value == null || Number.isNaN(Number(value))) return '\u2014';
  return Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits == null ? 4 : digits,
  });
}

function formatMetric(value, metricType) {
  if (value == null) return '\u2014';
  const suffix = metricType === 'yield_basis_points' ? ' bp' : '%';
  return formatNumber(value, 4) + suffix;
}

function targetForSeries(seriesId) {
  if (!state.detail) return null;
  return (state.detail.event.targets || []).find(function (row) {
    return row.series_id === seriesId;
  }) || null;
}

function renderOverview() {
  el('event-count').textContent = state.overview.event_count;
  el('window-count').textContent = state.overview.market_window_count;
  el('validation-state').textContent = state.overview.validation_valid
    ? '\u7ed3\u6784\u6821\u9a8c\u901a\u8fc7'
    : '\u6821\u9a8c\u5931\u8d25';
}

function filteredEvents() {
  const needle = state.search.trim().toLowerCase();
  if (!needle) return state.events;
  return state.events.filter(function (row) {
    return (
      row.event_id.toLowerCase().includes(needle)
      || row.title.toLowerCase().includes(needle)
      || (EVENT_ZH[row.event_id] || '').includes(state.search.trim())
    );
  });
}

function renderEventList() {
  el('event-list').innerHTML = filteredEvents().map(function (row) {
    const active = row.event_id === state.eventId ? ' active' : '';
    const meta = row.split === 'EXAMPLE' ? '\u516c\u5f00\u793a\u4f8b' : '\u9690\u85cf\u8bc4\u6d4b';
    const challenge = row.challenge_set ? ' \u00b7 \u6311\u6218\u96c6' : '';
    return (
      '<button class="event-item' + active + '" data-event-id="' + escapeHtml(row.event_id) + '" type="button">'
      + '<span class="event-number">' + escapeHtml(row.event_id.replace('event-', 'E')) + '</span>'
      + '<span class="event-item-copy"><strong>' + escapeHtml(EVENT_ZH[row.event_id] || row.title) + '</strong>'
      + '<small><span>' + meta + '</span><span>' + row.series_count + ' \u5e8f\u5217' + challenge + '</span></small></span>'
      + '</button>'
    );
  }).join('');

  el('event-list').querySelectorAll('[data-event-id]').forEach(function (button) {
    button.addEventListener('click', function () {
      selectEvent(button.dataset.eventId);
    });
  });
}

async function selectEvent(eventId) {
  if (eventId === state.eventId && state.detail) return;
  const eventRequestToken = ++state.eventRequestToken;
  state.anchorRequestToken += 1;
  el('loading-state').classList.remove('hidden');
  state.eventId = eventId;
  try {
    const detail = await api('/api/v2/events/' + encodeURIComponent(eventId));
    if (
      eventRequestToken !== state.eventRequestToken
      || eventId !== state.eventId
    ) return;
    state.detail = detail;
    const primary = detail.milestones.find(function (row) {
      return row.anchor_role === 'PRIMARY';
    }) || detail.milestones[0];
    const evidenceInput = detail.evidence_timeline[0] || null;
    state.milestoneId = detail.evaluation_restricted
      ? (evidenceInput ? evidenceInput.timeline_id : null)
      : (primary ? primary.milestone_id : null);
    state.seriesId = detail.market_windows.length
      ? detail.market_windows[0].series_id
      : null;
    state.anchorDetail = null;
    renderEventList();
    renderHeader();
    renderTimeline();
    if (detail.evaluation_restricted) {
      renderGraph();
      renderEvidenceInput(state.milestoneId);
    } else {
      await selectMilestone(state.milestoneId, false);
    }
    if (
      eventRequestToken !== state.eventRequestToken
      || eventId !== state.eventId
    ) return;
    renderMarket();
    renderConfounder();
  } catch (error) {
    if (eventRequestToken === state.eventRequestToken) {
      console.error(error);
    }
  } finally {
    if (eventRequestToken === state.eventRequestToken) {
      el('loading-state').classList.add('hidden');
    }
  }
}

function renderHeader() {
  const detail = state.detail;
  const event = detail.event;
  const caseRow = detail.benchmark_case;
  const eventRow = state.events.find(function (row) {
    return row.event_id === state.eventId;
  });
  el('event-id').textContent = event.event_id.toUpperCase();
  el('event-title').textContent = EVENT_ZH[event.event_id] || event.title;
  el('event-split').textContent = caseRow.split === 'EXAMPLE'
    ? '\u5b8c\u6574\u793a\u4f8b'
    : '\u9690\u85cf\u8bc4\u6d4b';
  el('challenge-badge').hidden = !eventRow.challenge_set;
  el('challenge-badge').textContent = '\u6311\u6218\u96c6';
  el('event-meta').innerHTML = [
    '<span>' + escapeHtml(event.category || '--') + '</span>',
    '<span>\u4e3b\u951a\u70b9 ' + formatDateTime(event.anchor_at) + '</span>',
    '<span>' + (
      detail.evaluation_restricted ? detail.evidence_timeline.length : detail.milestones.length
    ) + ' \u4e2a\u8bc1\u636e\u8282\u70b9</span>',
    '<span>' + detail.market_windows.length + ' \u6761\u8d44\u4ea7\u5e8f\u5217</span>',
  ].join('');
  el('forecast-cutoff').textContent = formatDateTime(caseRow.forecast_cutoff_at);
}

function visibleMilestones() {
  if (state.detail.evaluation_restricted) {
    return state.detail.evidence_timeline.map(function (row) {
      return {
        milestone_id: row.timeline_id,
        occurred_at: row.first_public_at,
        first_public_at: row.first_public_at,
        phase: 'EVIDENCE_INPUT',
        fact: row.title,
        anchor_role: 'NONE',
        visibility: 'PUBLIC_PREDICTION',
        evidence_input: true,
      };
    }).filter(function (row) {
      return state.visibility === 'ALL' || row.visibility === state.visibility;
    });
  }
  return state.detail.milestones.filter(function (row) {
    return state.visibility === 'ALL' || row.visibility === state.visibility;
  });
}

function renderTimeline() {
  const rows = visibleMilestones();
  if (state.detail.evaluation_restricted) {
    el('timeline-summary').textContent = (
      state.detail.evidence_timeline.length + ' \u4e2a\u53ef\u89c1\u8bc1\u636e\u8f93\u5165'
    );
  } else {
  const publicCount = state.detail.milestones.filter(function (row) {
    return row.visibility === 'PUBLIC_PREDICTION';
  }).length;
  const hiddenCount = state.detail.milestones.length - publicCount;
  el('timeline-summary').textContent = (
    publicCount + ' \u4e2a\u9884\u6d4b\u53ef\u89c1\u8282\u70b9 \u00b7 '
    + hiddenCount + ' \u4e2a\u9690\u85cf\u9a8c\u8bc1\u8282\u70b9 \u00b7 '
    + state.detail.episodes.length + ' \u4e2a\u9636\u6bb5'
  );

  }
  el('timeline-track').innerHTML = rows.map(function (row) {
    const hidden = row.visibility === 'HIDDEN_VALIDATION';
    const selected = row.milestone_id === state.milestoneId;
    const visibility = hidden ? '\u9690\u85cf\u9a8c\u8bc1' : '\u9884\u6d4b\u53ef\u89c1';
    const anchor = row.anchor_role === 'PRIMARY'
      ? '\u4e3b\u951a\u70b9'
      : (row.anchor_role === 'SECONDARY' ? '\u6b21\u951a\u70b9' : '\u80cc\u666f');
    return (
      '<button class="timeline-node' + (hidden ? ' hidden-node' : '') + (selected ? ' selected' : '')
      + '" data-milestone-id="' + escapeHtml(row.milestone_id) + '" type="button">'
      + '<time>' + formatDateTime(row.occurred_at) + '</time>'
      + '<strong>' + escapeHtml(PHASE_ZH[row.phase] || row.phase) + '</strong>'
      + '<small>' + escapeHtml(row.fact) + '</small>'
      + '<span class="timeline-tags"><span>' + visibility + '</span><span>' + anchor + '</span></span>'
      + '<span class="timeline-public-at">\u9996\u6b21\u516c\u5f00 '
      + formatDateTime(row.first_public_at) + '</span>'
      + '</button>'
    );
  }).join('');

  el('timeline-track').querySelectorAll('[data-milestone-id]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (state.detail.evaluation_restricted) {
        renderEvidenceInput(button.dataset.milestoneId);
      } else {
        selectMilestone(button.dataset.milestoneId, true);
      }
    });
  });
}

function renderEvidenceInput(timelineId) {
  const item = state.detail.evidence_timeline.find(function (row) {
    return row.timeline_id === timelineId;
  });
  if (!item) return;
  state.milestoneId = timelineId;
  state.anchorDetail = null;
  renderTimeline();
  renderGraph();
  const source = state.detail.sources.find(function (row) {
    return row.evidence_id === item.evidence_id;
  });
  el('anchor-detail').innerHTML = (
    '<div class="detail-block"><span class="detail-label">\u5f53\u524d\u8bc1\u636e\u8f93\u5165</span>'
    + '<strong>' + escapeHtml(item.title) + '</strong>'
    + '<p>\u9996\u6b21\u516c\u5f00 ' + formatDateTime(item.first_public_at) + '</p>'
    + '<p>' + escapeHtml(item.publisher || '--') + ' \u00b7 '
    + escapeHtml(item.source_tier || '--') + '</p></div>'
  );
  el('source-detail').innerHTML = sourceBlock(source);
  el('expectation-detail').innerHTML = (
    '<div class="detail-block"><span class="detail-label">\u8bc4\u6d4b\u8fb9\u754c</span>'
    + '<strong>\u7b54\u6848\u5df2\u9694\u79bb</strong>'
    + '<p>\u9636\u6bb5\u3001\u951a\u70b9\u3001\u4f20\u5bfc\u8fb9\u4e0e\u4e8b\u540e\u884c\u60c5\u4e0d\u5728\u516c\u5f00\u8f93\u5165\u4e2d\u3002</p></div>'
  );
}


async function selectMilestone(milestoneId, scrollIntoView) {
  if (!milestoneId) return;
  const eventId = state.eventId;
  const anchorRequestToken = ++state.anchorRequestToken;
  state.milestoneId = milestoneId;
  renderTimeline();
  try {
    const detail = await api(
      '/api/v2/events/' + encodeURIComponent(eventId)
      + '/anchors/' + encodeURIComponent(milestoneId)
    );
    if (
      anchorRequestToken !== state.anchorRequestToken
      || eventId !== state.eventId
      || milestoneId !== state.milestoneId
    ) return;
    state.anchorDetail = detail;
    renderGraph();
    renderEvidence();
    if (scrollIntoView) {
      const node = el('timeline-track').querySelector(
        '[data-milestone-id="' + milestoneId + '"]'
      );
      if (node) {
        node.scrollIntoView({
          behavior: 'smooth', block: 'nearest', inline: 'center',
        });
      }
    }
  } catch (error) {
    if (anchorRequestToken === state.anchorRequestToken) {
      console.error(error);
    }
  }
}

function edgeByTarget(edges) {
  const map = {};
  edges.forEach(function (edge) {
    map[edge.to_node_id] = edge;
  });
  return map;
}

function renderGraph() {
  const graph = state.detail.graph;
  const nodes = {};
  graph.nodes.forEach(function (node) {
    nodes[node.node_id] = node;
  });
  const incoming = edgeByTarget(graph.edges);
  const directEdges = state.anchorDetail ? state.anchorDetail.edges : [];
  const directIds = new Set(directEdges.map(function (edge) { return edge.edge_id; }));
  const assets = graph.nodes.filter(function (node) {
    return node.layer === 'asset';
  });

  el('graph-summary').textContent = state.detail.evaluation_restricted
    ? '\u4f20\u5bfc\u56fe\u5c5e\u4e8e\u9690\u85cf\u8bc4\u6d4b\u7b54\u6848'
    : (directEdges.length
      ? directEdges.length + ' \u6761\u8fb9\u4e0e\u5f53\u524d\u951a\u70b9\u76f4\u63a5\u7ed1\u5b9a'
      : '\u5f53\u524d\u8282\u70b9\u662f\u8bc1\u636e\u80cc\u666f\uff0c\u672a\u76f4\u63a5\u7ed1\u5b9a\u4f20\u5bfc\u8fb9');

  el('graph-branches').innerHTML = assets.map(function (asset) {
    const e3 = incoming[asset.node_id];
    const intermediate = e3 ? nodes[e3.from_node_id] : null;
    const e2 = intermediate ? incoming[intermediate.node_id] : null;
    const channel = e2 ? nodes[e2.from_node_id] : null;
    const e1 = channel ? incoming[channel.node_id] : null;
    const shock = e1 ? nodes[e1.from_node_id] : null;
    if (!e3 || !intermediate || !e2 || !channel || !e1 || !shock) return '';
    const active = [e1, e2, e3].some(function (edge) {
      return directIds.has(edge.edge_id);
    });
    const direction = e3.expected_path.SHORT_TERM;
    return (
      '<div class="branch-row' + (active ? ' active' : '') + '">'
      + branchNode('\u51b2\u51fb', shock.label, 'anchor')
      + branchNode('\u7edf\u4e00\u6e20\u9053', channel.label, e1.lag.maximum)
      + branchNode('\u4e8b\u4ef6\u4e2d\u95f4\u53d8\u91cf', intermediate.label, e2.lag.maximum)
      + branchNode('\u8d44\u4ea7', asset.label, direction + ' \u00b7 ' + Math.round(e3.confidence * 100) + '%')
      + '</div>'
    );
  }).join('') || '<div class="branch-empty">\u4f20\u5bfc\u5206\u652f\u6682\u65e0\u53ef\u7528\u8282\u70b9</div>';
}

function branchNode(layer, label, meta) {
  return (
    '<div class="branch-node"><span>' + layer + '</span><strong>' + escapeHtml(label)
    + '</strong><em>' + escapeHtml(meta) + '</em></div>'
  );
}

function sourceBlock(source) {
  if (!source) return '';
  const link = source.source_url
    ? '<a class="source-link" href="' + escapeHtml(source.source_url) + '" target="_blank" rel="noreferrer">\u6253\u5f00\u539f\u59cb\u6765\u6e90</a>'
    : '';
  return (
    '<div class="detail-block"><span class="detail-label">\u6765\u6e90\u4e0e\u54c8\u5e0c</span>'
    + '<strong>' + escapeHtml(source.title || source.evidence_id)
    + '<span class="evidence-tier">' + escapeHtml(source.source_tier) + '\u7ea7</span></strong>'
    + '<p>' + escapeHtml(source.publisher || '--') + ' \u00b7 ' + formatDateTime(source.published_at) + '</p>'
    + '<p>SHA-256 ' + escapeHtml(source.sha256) + '</p>'
    + '<p>' + escapeHtml(source.snapshot_status) + ' \u00b7 ' + escapeHtml(source.snapshot_path || '--') + '</p>'
    + link + '</div>'
  );
}

function listBlock(label, values) {
  const rows = (values || []).filter(Boolean);
  if (!rows.length) return '';
  return (
    '<div class="detail-block"><span class="detail-label">' + label + '</span><ul>'
    + rows.map(function (value) { return '<li>' + escapeHtml(value) + '</li>'; }).join('')
    + '</ul></div>'
  );
}

function renderEvidence() {
  const milestone = state.anchorDetail.milestone;
  const expectation = milestone.expectation || {};
  const source = state.anchorDetail.sources[0];
  const edges = state.anchorDetail.edges || [];
  const invalidation = [];
  const counter = [];
  edges.forEach(function (edge) {
    (edge.invalidation_conditions || []).forEach(function (value) {
      if (!invalidation.includes(value)) invalidation.push(value);
    });
    (edge.counterevidence || []).forEach(function (value) {
      if (!counter.includes(value)) counter.push(value);
    });
  });

  el('anchor-detail').innerHTML = (
    '<div class="detail-block"><span class="detail-label">\u5f53\u524d\u951a\u70b9</span>'
    + '<strong>' + escapeHtml(PHASE_ZH[milestone.phase] || milestone.phase) + '</strong>'
    + '<p>' + escapeHtml(milestone.fact) + '</p>'
    + '<p>' + formatDateTime(milestone.occurred_at) + ' \u00b7 '
    + escapeHtml(milestone.anchor_role) + ' \u00b7 ' + escapeHtml(milestone.visibility) + '</p>'
    + '<p>\u9996\u6b21\u516c\u5f00 ' + formatDateTime(milestone.first_public_at)
    + '</p></div>'
  );
  el('source-detail').innerHTML = sourceBlock(source) + listBlock('\u53cd\u8bc1', counter)
    + listBlock('\u5931\u6548\u6761\u4ef6', invalidation);
  el('expectation-detail').innerHTML = (
    '<div class="detail-block"><span class="detail-label">\u9884\u671f\u57fa\u51c6</span>'
    + '<strong>' + escapeHtml(EXPECTATION_ZH[expectation.type] || expectation.type || 'UNKNOWN') + '</strong>'
    + '<p>consensus: ' + escapeHtml(expectation.consensus) + '</p>'
    + '<p>actual: ' + escapeHtml(expectation.actual) + '</p>'
    + '<p>surprise: ' + escapeHtml(expectation.surprise) + '</p>'
    + (expectation.qualitative_baseline
      ? '<p>' + escapeHtml(expectation.qualitative_baseline) + '</p>'
      : '')
    + '</div>'
  );
}

function selectedWindow() {
  return state.detail.market_windows.find(function (row) {
    return row.series_id === state.seriesId;
  }) || state.detail.market_windows[0];
}

function renderMarket() {
  const windows = state.detail.market_windows;
  if (!windows.length) return;
  if (!windows.some(function (row) { return row.series_id === state.seriesId; })) {
    state.seriesId = windows[0].series_id;
  }
  el('market-series-tabs').innerHTML = windows.map(function (row) {
    const active = row.series_id === state.seriesId ? ' active' : '';
    return (
      '<button class="' + active + '" data-series-id="' + escapeHtml(row.series_id) + '" type="button">'
      + escapeHtml(SERIES_ZH[row.series_id] || row.series_id) + '</button>'
    );
  }).join('');
  el('market-series-tabs').querySelectorAll('[data-series-id]').forEach(function (button) {
    button.addEventListener('click', function () {
      state.seriesId = button.dataset.seriesId;
      renderMarket();
      renderConfounder();
    });
  });

  const row = selectedWindow();
  const target = targetForSeries(row.series_id) || {};
  const metricType = target.metric_type || 'price_return_pct';
  const t1 = row.windows.T1;
  const d3 = row.windows.D3;
  const restricted = state.detail.evaluation_restricted;
  el('market-hero').innerHTML = (
    '<div class="primary-value"><span>' + escapeHtml(SERIES_ZH[row.series_id] || row.series_id)
    + (restricted ? ' \u00b7 T-1 \u7edd\u5bf9\u503c' : ' \u00b7 D3 \u539f\u59cb\u53d8\u5316')
    + '</span><strong>'
    + (
      restricted
        ? (t1 ? formatNumber(t1.value, 6) : '\u2014')
        : formatMetric(d3 ? d3.raw_change : null, metricType)
    ) + '</strong></div>'
    + heroItem('T-1 \u57fa\u51c6', t1 ? t1.date : '--', t1 ? formatNumber(t1.value, 6) : '\u2014')
    + (
      restricted
        ? heroItem('\u9a8c\u8bc1\u7a97\u53e3', '--', '\u5df2\u9694\u79bb')
        : heroItem('D3 \u7ec8\u503c', d3 ? d3.date : '--', d3 ? formatNumber(d3.value, 6) : '\u2014')
    )
    + heroItem('T0 / \u622a\u6b62', row.t0.date || '--', row.observation_cutoff + ' ' + row.timezone)
  );

  el('window-table-body').innerHTML = WINDOW_ORDER.map(function (label) {
    const point = row.windows[label];
    if (!point) {
      return (
        '<tr><td>' + label + '</td><td class="null">'
        + (restricted ? '\u5df2\u9694\u79bb' : '\u7f3a\u5931') + '</td>'
        + '<td class="null">\u2014</td><td class="null">\u2014</td>'
        + '<td class="null">\u2014</td><td class="null">\u2014</td><td class="null">\u2014</td></tr>'
      );
    }
    return (
      '<tr class="' + (label === 'D3' ? 'highlight' : '') + '"><td>' + label + '</td>'
      + '<td>' + escapeHtml(point.date) + '</td>'
      + '<td>' + formatNumber(point.value, 6) + '</td>'
      + '<td>' + formatMetric(point.raw_change, metricType) + '</td>'
      + '<td>' + formatNumber(point.standardized_change, 4) + '</td>'
      + '<td>' + formatMetric(point.relative_change, metricType) + '</td>'
      + '<td>' + (point.empirical_percentile == null
        ? '\u2014'
        : formatNumber(point.empirical_percentile * 100, 2) + '%') + '</td></tr>'
    );
  }).join('');
  el('calculation-basis').textContent = row.calculation_basis;
}

function heroItem(label, meta, value) {
  return (
    '<div><span>' + label + '</span><strong>' + escapeHtml(value)
    + '</strong><span>' + escapeHtml(meta) + '</span></div>'
  );
}

function renderConfounder() {
  const row = selectedWindow();
  if (!row) return;
  el('confounder-level').textContent = row.confounder_level;
  el('confounder-copy').textContent = CONFOUNDER_ZH[row.confounder_level] || row.confounder_level;
  if (state.detail.evaluation_restricted) {
    el('confounder-level').textContent = 'HIDDEN';
    el('confounder-copy').textContent = '\u6df7\u6742\u7b49\u7ea7\u5c5e\u4e8e\u9690\u85cf\u8bc4\u6d4b\u7b54\u6848\u3002';
    el('edge-review-summary').textContent = '\u4f20\u5bfc\u8fb9\u5df2\u9694\u79bb';
    return;
  }
  const edges = state.detail.graph.edges || [];
  const proposed = edges.filter(function (edge) { return edge.status === 'PROPOSED'; }).length;
  const confirmed = edges.filter(function (edge) { return edge.status === 'CONFIRMED'; }).length;
  el('edge-review-summary').textContent = (
    proposed + ' PROPOSED \u00b7 ' + confirmed + ' CONFIRMED'
  );
}

function bindControls() {
  el('event-search').addEventListener('input', function (event) {
    state.search = event.target.value;
    renderEventList();
  });
  el('visibility-filter').querySelectorAll('[data-visibility]').forEach(function (button) {
    button.addEventListener('click', function () {
      state.visibility = button.dataset.visibility;
      el('visibility-filter').querySelectorAll('button').forEach(function (item) {
        item.classList.toggle('active', item === button);
      });
      renderTimeline();
    });
  });
}

async function boot() {
  bindControls();
  try {
    const payload = await Promise.all([
      api('/api/v2/overview'),
      api('/api/v2/events'),
    ]);
    state.overview = payload[0];
    state.events = payload[1];
    renderOverview();
    renderEventList();
    const initial = state.events.find(function (row) {
      return row.event_id === 'event-02';
    }) || state.events[0];
    if (initial) await selectEvent(initial.event_id);
  } catch (error) {
    el('loading-state').innerHTML = '<p>\u6570\u636e\u52a0\u8f7d\u5931\u8d25\uff1a' + escapeHtml(error.message) + '</p>';
  }
}

boot();
