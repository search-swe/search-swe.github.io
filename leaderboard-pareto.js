/* Compare score with cost, tokens or reported time over the selected tasks. */
(() => {
  'use strict';
  const colors = ['#16847c', '#bd7b27', '#3976c6', '#9562bb', '#bd5b76', '#5a7994', '#69833c'];
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
    document.getElementById('pareto-note').textContent = metric.note;
    chart.hidden = visible.length === 0;
    if (!visible.length) {
      chart.replaceChildren();
      legend.replaceChildren();
      return;
    }
    legend.style.setProperty('--pareto-columns', Math.min(4, visible.length));

    // Search hides models, but does not turn a dominated model into a frontier point.
    const frontierIds = new Set(frontier(eligible, axis).map(e => e.id));
    const width = Math.max(300, chart.clientWidth), height = width < 600 ? 330 : 420;
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
      if (onFrontier) link.append(svgNode('circle', {cx: x(entry[axis]), cy: y(entry.score), r: 11, fill: color, opacity: '.13'}));
      link.append(svgNode('circle', {cx: x(entry[axis]), cy: y(entry.score), r: 6, fill: color, class: 'pareto-dot'}));
      const end = x(entry[axis]) > width * .6;
      link.append(svgNode('text', {x: x(entry[axis]) + (end ? -14 : 14), y: y(entry.score) - 12,
        'text-anchor': end ? 'end' : 'start', class: 'pareto-point-label'}, entry.name));
      const showTooltip = () => {
        const name = document.createElement('strong');
        name.textContent = identity;
        const details = document.createElement('span');
        const exact = axis === 'tokens' ? `${entry[axis].toLocaleString('en-US')} tokens` : metric.format(entry[axis]);
        details.textContent = `${entry.effort} effort · ${entry.score.toFixed(1)} · ${exact}${coverage || ` · ${taskCount} tasks`}`;
        tooltip.replaceChildren(name, details);
        tooltip.hidden = false;
        tooltip.style.left = `${Math.max(8, Math.min(x(entry[axis]) + 14, width - tooltip.offsetWidth - 8))}px`;
        tooltip.style.top = `${Math.max(0, y(entry.score) - tooltip.offsetHeight - 18)}px`;
      };
      link.addEventListener('mouseenter', showTooltip);
      link.addEventListener('focus', showTooltip);
      link.addEventListener('mouseleave', () => { tooltip.hidden = true; });
      link.addEventListener('blur', () => { tooltip.hidden = true; });
      svg.append(link);

      const item = document.createElement('a');
      item.href = entry.url;
      item.className = 'pareto-legend-item';
      const dot = document.createElement('span');
      dot.className = 'pareto-legend-dot';
      dot.style.backgroundColor = color;
      const name = document.createElement('span');
      name.textContent = label;
      const details = document.createElement('span');
      details.className = 'pareto-legend-summary';
      details.textContent = summary + coverage;
      item.append(dot, name, details);
      legendItems.append(item);
    });
    // Keep the previous chart in place until its replacement is ready. Measuring
    // an empty chart collapses the page and clamps the user's scroll position.
    chart.replaceChildren(svg, tooltip);
    legend.replaceChildren(legendItems);
    // Keep nearby model labels apart; the legend retains every model on crowded charts.
    const occupied = visible.map(e => ({x: x(e[axis]) - 9, y: y(e.score) - 9, width: 18, height: 18}));
    const overlaps = (a, b) => a.x < b.x + b.width + 4 && a.x + a.width + 4 > b.x &&
      a.y < b.y + b.height + 4 && a.y + a.height + 4 > b.y;
    const labels = [...svg.querySelectorAll('.pareto-point-label')]
      .sort((a, b) => Number(a.getAttribute('y')) - Number(b.getAttribute('y')) || a.textContent.localeCompare(b.textContent));
    labels.forEach(label => {
      if (!label.getBBox().width) return; // Point labels are hidden on mobile.
      const originalY = Number(label.getAttribute('y'));
      for (const offset of [0, 36, -22, 58]) {
        label.setAttribute('y', originalY + offset);
        const box = label.getBBox();
        if (box.x >= 0 && box.x + box.width <= width && box.y >= top && box.y + box.height <= bottom &&
            !occupied.some(other => overlaps(box, other))) {
          occupied.push(box);
          return;
        }
      }
      label.style.display = 'none';
    });
  }
  window.SearchSwePareto = {render, frontier, linearTicks};
})();
