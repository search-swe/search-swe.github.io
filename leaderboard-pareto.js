/* Compare score with cost, tokens or reported time over the selected tasks. */
(() => {
  'use strict';
  const colors = ['#16847c', '#bd7b27', '#3976c6', '#9562bb', '#bd5b76', '#5a7994', '#69833c', '#b35439', '#5964c4', '#8d7438', '#287e9b', '#a16690', '#3e8757', '#c06c3a'];
  const money = value => value.toLocaleString('en-US', {style: 'currency', currency: 'USD'});
  const compact = value => value.toLocaleString('en-US', {notation: 'compact', maximumFractionDigits: value >= 1e9 ? 2 : 1});
  const duration = seconds => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    return minutes < 60 ? `${minutes}min` : `${Math.floor(minutes / 60)}h ${minutes % 60}min`;
  };
  const axes = {
    cost: {name: 'cost', label: 'Cost (USD)', title: 'total agent cost', unit: 1,
      format: money, tick: value => '$' + value.toLocaleString('en-US', {maximumFractionDigits: value < 1 ? 3 : value < 10 ? 2 : 0}),
      note: 'Total estimated agent cost across the selected tasks, using official API rates. DeepSeek uses official off-peak rates for all requests.'},
    tokens: {name: 'tokens', label: 'Total tokens', title: 'total agent tokens', unit: 1,
      format: value => `${compact(value)} tokens`, tick: compact,
      note: 'Total agent input and output tokens across the selected tasks. Cached tokens are included in input; reasoning is included in output.'},
    time: {name: 'time', label: 'Total agent time (hours)', title: 'total agent time', unit: 3600,
      format: duration, tick: value => value.toLocaleString('en-US', {maximumFractionDigits: 2}) + 'h',
      note: 'Sum of reported agent durations, including tools and waiting, across the selected tasks. Missing durations are omitted; each model shows its timing coverage.'},
  };
  const frontier = (entries, axis = 'cost') => entries.filter(entry => !entries.some(other =>
    other[axis] <= entry[axis] && other.score >= entry.score &&
    (other[axis] < entry[axis] || other.score > entry.score)
  )).sort((a, b) => a[axis] - b[axis] || b.score - a.score);

  function linearTicks(maxValue, intervals = 5) {
    const roughStep = (maxValue > 0 ? maxValue : 1) / intervals;
    const magnitude = 10 ** Math.floor(Math.log10(roughStep));
    const step = [1, 2, 2.5, 5, 10].find(n => n * magnitude >= roughStep) * magnitude;
    const count = Math.max(1, Math.ceil(maxValue / step));
    return Array.from({length: count + 1}, (_, i) => Number((step * i).toPrecision(12)));
  }

  function svgNode(tag, attributes = {}, text) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text != null) node.textContent = text;
    return node;
  }

  function render(entries, taskCount, axis = 'cost') {
    const metric = axes[axis];
    const chart = document.getElementById('pareto-chart');
    const legend = document.getElementById('pareto-legend');
    const eligible = entries.filter(e => e.trials.length === taskCount && taskCount > 0 &&
      Number.isFinite(e[axis]) && e[axis] >= 0 && Number.isFinite(e.score));
    const visible = eligible.filter(e => e.visible);
    const empty = document.getElementById('pareto-empty');
    empty.textContent = `No matching models with recorded ${metric.name} data.`;
    empty.hidden = visible.length > 0;
    const deepseek = entries.find(e => e.model === 'deepseek/deepseek-v4.1-flash-1017');
    document.getElementById('pareto-note').textContent = metric.note + (deepseek
      ? ` DeepSeek shows its highest-scoring harness overall (${deepseek.agent}).` : '');
    chart.hidden = visible.length === 0;
    if (!visible.length) {
      chart.replaceChildren();
      legend.replaceChildren();
      return;
    }
    legend.style.setProperty('--pareto-columns', Math.min(4, visible.length));

    // Search hides models, but does not turn a dominated model into a frontier point.
    const frontierIds = new Set(frontier(eligible, axis).map(e => e.id));
    const width = Math.max(300, chart.clientWidth);
    const height = window.matchMedia('(max-width: 600px)').matches ? 330 : 520;
    const left = 58, right = width - 32, top = 42, bottom = height - 54;
    const maxValue = Math.max(...eligible.map(e => e[axis] / metric.unit));
    const ticks = linearTicks(maxValue, width < 600 ? 3 : 5);
    const xMax = ticks[ticks.length - 1];
    const x = value => left + value / metric.unit / xMax * (right - left);
    const yMax = Math.min(100, Math.max(5, Math.ceil(Math.max(...eligible.map(e => e.score)) * 1.15 / 5) * 5));
    const y = value => bottom - value / yMax * (bottom - top);
    const svg = svgNode('svg', {viewBox: `0 0 ${width} ${height}`, 'aria-labelledby': 'pareto-title pareto-description',
      'data-x-scale': 'linear'});
    svg.append(svgNode('title', {id: 'pareto-title'}, `Mean task score versus ${metric.title}`));
    svg.append(svgNode('desc', {id: 'pareto-description'},
      `The chart covers ${taskCount} selected tasks. The horizontal axis is linear and starts at zero. Higher scores and lower ${metric.name} are better. ${metric.note} ` +
      `The frontier connects models for which no model has both an equal or higher score and an equal or lower ${metric.name}, with at least one strict improvement. Select a model to open its results.`));
    svg.append(svgNode('text', {x: left, y: 18, class: 'pareto-axis-label'}, 'Mean task score (0–100)'));
    svg.append(svgNode('rect', {x: left, y: top, width: right - left, height: bottom - top, class: 'pareto-plot'}));
    const yStep = yMax <= 25 ? 5 : yMax <= 50 ? 10 : 20;
    for (let tick = 0; tick <= yMax; tick += yStep) {
      svg.append(svgNode('line', {x1: left, x2: right, y1: y(tick), y2: y(tick), class: 'pareto-grid'}));
      svg.append(svgNode('text', {x: left - 12, y: y(tick) + 4, 'text-anchor': 'end', class: 'pareto-tick'}, String(tick)));
    }
    ticks.forEach(tick => {
      const position = x(tick * metric.unit);
      svg.append(svgNode('line', {x1: position, x2: position, y1: top, y2: bottom, class: 'pareto-grid pareto-grid-vertical'}));
      svg.append(svgNode('text', {x: position, y: bottom + 23, 'text-anchor': 'middle',
        class: 'pareto-tick pareto-tick-x', 'data-value': tick * metric.unit}, metric.tick(tick)));
    });
    svg.append(svgNode('path', {d: `M${left},${top}V${bottom}H${right}`, class: 'pareto-axis'}));
    svg.append(svgNode('text', {x: (left + right) / 2, y: height - 6, 'text-anchor': 'middle', class: 'pareto-axis-label'},
      metric.label));
    const line = frontier(eligible, axis).filter(e => e.visible);
    if (line.length > 1) {
      svg.append(svgNode('path', {class: 'pareto-frontier', d: line.map((e, i) => `${i ? 'L' : 'M'}${x(e[axis])},${y(e.score)}`).join(' ')}));
    }
    const leaders = svgNode('g', {'stroke': '#a3adb9', 'pointer-events': 'none', 'aria-hidden': 'true'});
    svg.append(leaders);
    const tooltip = document.createElement('div');
    tooltip.className = 'pareto-tooltip';
    tooltip.hidden = true;
    tooltip.setAttribute('aria-hidden', 'true');
    const legendItems = document.createDocumentFragment();

    visible.forEach(entry => {
      const color = colors[entry.colorIndex % colors.length];
      const onFrontier = frontierIds.has(entry.id);
      const label = `${entry.name} (${entry.effort})`;
      const identity = entry.agent ? `${entry.name} / ${entry.agent}` : entry.name;
      const coverage = axis === 'time' ? ` · ${entry.timedTasks}/${taskCount} tasks timed` : '';
      const summary = `${entry.score.toFixed(1)} · ${metric.format(entry[axis])}`;
      const link = svgNode('a', {href: entry.url, tabindex: 0, class: 'pareto-point',
        'data-entry': entry.id, 'data-cost': entry.cost, 'data-score': entry.score,
        'data-axis': axis, 'data-value': entry[axis],
        'data-frontier': onFrontier, 'aria-label': `${identity} (${entry.effort}): ${summary}${coverage}${onFrontier ? ', Pareto frontier' : ''}. View results.`});
      if (onFrontier) link.append(svgNode('circle', {cx: x(entry[axis]), cy: y(entry.score), r: 11, fill: color, opacity: '.13', class: 'pareto-halo'}));
      const dot = svgNode('circle', {cx: x(entry[axis]), cy: y(entry.score), r: 6, fill: color, class: 'pareto-dot'});
      link.append(dot);
      const pointLabel = svgNode('text', {x: x(entry[axis]), y: y(entry.score), class: 'pareto-point-label',
        'data-entry': entry.id, 'data-frontier': onFrontier, 'data-point-x': x(entry[axis]),
        'data-point-y': y(entry.score), 'aria-hidden': 'true'}, entry.name);
      const showTooltip = () => {
        const name = document.createElement('strong');
        name.textContent = identity;
        const details = document.createElement('span');
        const exact = axis === 'tokens' ? `${entry[axis].toLocaleString('en-US')} tokens` : metric.format(entry[axis]);
        details.textContent = `${entry.effort} effort · ${entry.score.toFixed(1)} · ${exact}${coverage || ` · ${taskCount} tasks`}`;
        tooltip.replaceChildren(name, details);
        tooltip.hidden = false;
        const marker = dot.getBoundingClientRect(), bounds = chart.getBoundingClientRect();
        const centerX = marker.x + marker.width / 2 - bounds.x;
        const centerY = marker.y + marker.height / 2 - bounds.y;
        tooltip.style.left = `${Math.max(8, Math.min(centerX + 14, bounds.width - tooltip.offsetWidth - 8))}px`;
        tooltip.style.top = `${Math.max(0, centerY - tooltip.offsetHeight - 18)}px`;
      };
      dot.addEventListener('mouseenter', showTooltip);
      link.addEventListener('focus', showTooltip);
      dot.addEventListener('mouseleave', () => { tooltip.hidden = true; });
      link.addEventListener('blur', () => { tooltip.hidden = true; });
      svg.append(pointLabel, link);

      const item = document.createElement('a');
      item.href = entry.url;
      item.className = 'pareto-legend-item';
      const legendDot = document.createElement('span');
      legendDot.className = 'pareto-legend-dot';
      legendDot.style.backgroundColor = color;
      const name = document.createElement('span');
      name.textContent = label;
      const details = document.createElement('span');
      details.className = 'pareto-legend-summary';
      details.textContent = summary + coverage;
      item.append(legendDot, name, details);
      legendItems.append(item);
    });
    // Keep the previous chart in place until its replacement is ready. Measuring
    // an empty chart collapses the page and clamps the user's scroll position.
    chart.replaceChildren(svg, tooltip);
    legend.replaceChildren(legendItems);
    function layoutLabels() {
      const points = visible.map(e => ({id: e.id, x: x(e[axis]), y: y(e.score)}));
      const markers = points.map(p => ({x: p.x - 8, y: p.y - 8, width: 16, height: 16}));
      const overlaps = (a, b, gap) => a.x < b.x + b.width + gap && a.x + a.width + gap > b.x &&
        a.y < b.y + b.height + gap && a.y + a.height + gap > b.y;
      const distance = (box, px, py) => Math.hypot(
        Math.max(box.x - px, px - box.x - box.width, 0),
        Math.max(box.y - py, py - box.y - box.height, 0)
      );
      const labels = [...svg.querySelectorAll('.pareto-point-label')].map(label => {
        label.style.display = '';
        const size = label.getBBox();
        if (!size.width) return null; // Point labels are hidden on mobile.
        const px = Number(label.dataset.pointX), py = Number(label.dataset.pointY);
        const baseline = Number(label.getAttribute('y')) - size.y;
        const centeredY = py - size.height / 2;
        const options = [];
        const neighbors = points.filter(p => p.id !== label.dataset.entry);
        const add = (x, y, alignmentPenalty) => {
          const box = {x, y, width: size.width, height: size.height};
          if (x < left || x + box.width > right || y < top || y + box.height > bottom ||
              markers.some(marker => overlaps(box, marker, 1))) return;
          const gap = distance(box, px, py);
          const dx = Math.max(x, Math.min(x + box.width, px)) - px;
          const dy = Math.max(y, Math.min(y + box.height, py)) - py;
          const ambiguous = neighbors.some(p => distance(box, p.x, p.y) + 1 < gap);
          const crossed = gap > 16 && neighbors.some(p => {
            const along = ((p.x - px) * dx + (p.y - py) * dy) / (gap * gap);
            return along > 0 && along < 1 && Math.hypot(p.x - px - along * dx, p.y - py - along * dy) < 8;
          });
          if (crossed) return;
          const leader = gap > 16 ? {
            x1: px + dx * 7 / gap, y1: py + dy * 7 / gap,
            x2: px + dx * (1 - 2 / gap), y2: py + dy * (1 - 2 / gap),
          } : null;
          const leaderBox = leader && {
            x: Math.min(leader.x1, leader.x2), y: Math.min(leader.y1, leader.y2),
            width: Math.abs(leader.x1 - leader.x2), height: Math.abs(leader.y1 - leader.y2),
          };
          options.push({box, leader, leaderBox, gap, rank: gap + alignmentPenalty + (ambiguous ? 10 : 0)});
        };
        const verticalAnchors = new Set([.5, .25, .75, 0, 1].map(fraction =>
          Math.max(left, Math.min(right - size.width, px - size.width * fraction))));
        for (const markerGap of [11, 17, 23]) {
          for (let offset = -42; offset <= 42; offset += 3.5) {
            add(px + markerGap, centeredY + offset, Math.abs(offset) / 4);
            add(px - markerGap - size.width, centeredY + offset, Math.abs(offset) / 4);
          }
          for (const labelX of verticalAnchors) {
            add(labelX, py - markerGap - size.height, 3);
            add(labelX, py + markerGap, 3);
          }
        }
        options.sort((a, b) => a.rank - b.rank);
        return {label, baseline, options};
      }).filter(Boolean).sort((a, b) => a.options.length - b.options.length);
      const choices = [];
      const occupied = [];
      const conflicts = (a, b, spacing) => overlaps(a.box, b.box, spacing) ||
        (a.leaderBox && overlaps(a.leaderBox, b.box, 1)) ||
        (b.leaderBox && overlaps(a.box, b.leaderBox, 1));
      let attempts = 0;
      const fit = (remaining, limit, spacing) => {
        if (!remaining.length) return true;
        let next, available;
        for (const index of remaining) {
          const free = labels[index].options.filter(option => option.gap <= limit &&
            !occupied.some(other => conflicts(option, other, spacing)));
          if (!free.length) return false;
          if (!available || free.length < available.length) { next = index; available = free; }
        }
        for (const option of available) {
          if (++attempts > 3000) return false;
          occupied.push(option);
          choices[next] = option;
          if (fit(remaining.filter(index => index !== next), limit, spacing)) return true;
          occupied.pop();
        }
        return false;
      };
      // Widen the search only when nearby placements cannot fit all names.
      const indices = labels.map((_, index) => index);
      // In dense areas, allow up to one pixel of label-box overlap.
      const placed = [13, 18, 24, 32, 40].some(limit => [1, -1].some(spacing => {
        attempts = 0;
        return fit(indices, limit, spacing);
      }));
      if (!placed) {
        // Keep readable labels in the plot and leave every name available in the legend.
        labels.forEach(({options}, index) => {
          choices[index] = options.find(option => !occupied.some(other => conflicts(option, other, -1)));
          if (choices[index]) occupied.push(choices[index]);
        });
      }
      leaders.replaceChildren();
      labels.forEach(({label, baseline}, index) => {
        const chosen = choices[index];
        if (!chosen) { label.style.display = 'none'; return; }
        label.setAttribute('x', chosen.box.x);
        label.setAttribute('y', chosen.box.y + baseline);
        if (chosen.leader) leaders.append(svgNode('line', chosen.leader));
      });
    }
    layoutLabels();
    if (document.fonts?.status === 'loading') {
      document.fonts.ready.then(() => { if (svg.isConnected) layoutLabels(); });
    }
  }
  window.SearchSwePareto = {render, frontier, linearTicks};
})();
