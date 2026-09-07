(() => {
  const demo = document.querySelector('.hero-demo');
  if (!demo) return;

  const modes = {
    build: {
      title: 'Implementation: make documents searchable',
      description: 'An agent assembles indexing, retrieval and ranking into a search capability. Documents enter an index. A query follows the retrieval path and matching documents become ranked results. This is a general illustration, not a particular algorithm, task or measured run.',
      stages: ['Define', 'Assemble', 'Search', 'Verify'],
      captions: ['Documents in. Search still to build.', 'Connect indexing, retrieval and ranking.', 'Find documents that match the query.', 'A working search capability.'],
    },
    optimize: {
      title: 'Optimization: find where search relevance falls short',
      description: 'The search engine returns results, but a relevant document is missing from the candidate set and another is buried in the ranking. The agent inspects retrieval and ranking. A missed document enters the candidate set, and the relevant documents move to the top of the results. Blue matching marks connect the query to relevant documents. This illustrates search-quality optimization, not measured results or guaranteed gains.',
      stages: ['Inspect', 'Diagnose', 'Improve', 'Compare'],
      captions: ['Results return. Relevance falls short.', 'Trace misses and weak rankings.', 'Improve retrieval and ranking.', 'Bring relevant documents to the top.'],
    },
    repair: {
      title: 'Repair: locate and fix a search execution error',
      description: 'A query is parsed but a fault in the retrieval stage prevents search results from returning. The index remains available. The agent traces the query path, isolates the failing stage, patches it and reruns queries. Search results and query checks return. This illustrates a general search execution failure rather than a particular language or implementation bug.',
      stages: ['Reproduce', 'Trace', 'Patch', 'Replay'],
      captions: ['A query fails to return results.', 'Trace the error through the search path.', 'Patch the failing retrieval stage.', 'Replay queries. Results restored.'],
    },
  };
  const names = Object.keys(modes);
  const modeButtons = [...demo.querySelectorAll('[data-mode-choice]')];
  const stageButtons = [...demo.querySelectorAll('[data-stage]')];
  const playButton = demo.querySelector('.demo-play');
  const scrubber = demo.querySelector('.demo-scrubber');
  const scene = demo.querySelector('.demo-scene');
  const caption = demo.querySelector('#demo-caption-text');
  const captionNumber = demo.querySelector('.demo-caption-number');
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const playbackRate = 1.95;
  const stageDuration = 3600 / playbackRate;
  demo.style.setProperty('--demo-speed', playbackRate);

  let mode = 'build';
  let stage = 0;
  let elapsed = 0;
  let playing = !motionPreference.matches;
  let inView = true;
  let lastTime = null;
  let frame = null;
  let lastProgress = -1;

  const buildModules = [...demo.querySelectorAll('.build-module')];
  const fragments = [...demo.querySelectorAll('.index-fragment')];
  const buildHits = [...demo.querySelectorAll('.build-hit')];
  const queryProbe = demo.querySelector('.build-query-probe');
  const queryRoute = demo.querySelector('.build-query-route');
  const queryRouteLength = queryRoute.getTotalLength();
  const missedDocument = demo.querySelector('.missed-document');
  const rankingRows = [...demo.querySelectorAll('.ranking-row')];
  const targetRanks = [2, 3, 4, 0, 1];
  const repairProbe = demo.querySelector('.repair-query-probe');
  const repairProbePath = demo.querySelector('.repair-probe-path');
  const repairProbeLength = repairProbePath.getTotalLength();
  const failureRing = demo.querySelector('.query-failure-ring');
  const repairedHits = [...demo.querySelectorAll('.repaired-hit')];

  const clamp = value => Math.max(0, Math.min(1, value));
  const ease = value => 1 - Math.pow(1 - clamp(value), 3);
  const place = (node, x, y) => node.setAttribute('transform', 'translate(' + x.toFixed(2) + ' ' + y.toFixed(2) + ')');

  function renderBuild(position) {
    const assembly = stage < 1 ? 0 : stage === 1 ? position : 1;
    buildModules.forEach((node, index) => {
      const mix = ease((assembly - index * 0.14) / 0.62);
      node.style.opacity = String(mix);
      place(node, 181 - (1 - mix) * 18, 86 + index * 44 + (1 - mix) * 19);
    });
    fragments.forEach((node, index) => {
      const mix = clamp((position - index * 0.075) / 0.48);
      node.style.opacity = stage === 1 ? String(Math.sin(mix * Math.PI) * 0.85) : '0';
      place(node, 86 + (200 - 86) * mix, 153 - 50 * mix - Math.sin(Math.PI * mix) * (25 + index * 2));
    });
    buildHits.forEach((node, index) => {
      const mix = stage < 2 ? 0 : stage === 2 ? ease((position - 0.24 - index * 0.12) / 0.38) : 1;
      node.style.opacity = String(mix);
      place(node, 391 - (1 - mix) * 24, 91 + index * 41 + (1 - mix) * 10);
    });
    const probeProgress = clamp(position / 0.65);
    const point = queryRoute.getPointAtLength(queryRouteLength * probeProgress);
    queryProbe.style.opacity = stage === 2 && probeProgress < 1 ? '1' : '0';
    queryProbe.setAttribute('cx', point.x);
    queryProbe.setAttribute('cy', point.y);
  }

  function renderOptimization(position) {
    const improvement = stage < 2 ? 0 : stage === 2 ? position : 1;
    const recall = ease(improvement / 0.64);
    place(missedDocument, 265 - recall * 103, 182 - recall * 66 - Math.sin(Math.PI * recall) * 22);
    const rerank = ease((improvement - 0.2) / 0.74);
    rankingRows.forEach((node, index) => {
      const initialY = 91 + index * 35;
      const targetY = 91 + targetRanks[index] * 35;
      const lift = Math.sin(Math.PI * rerank) * (index > 2 ? -13 : 5);
      place(node, 349 + lift, initialY + (targetY - initialY) * rerank);
      node.style.opacity = String(index === 2 ? 1 - rerank : index === 4 ? rerank : 1);
    });
  }

  function renderRepair(position) {
    // The failing query stops at retrieval; replayed queries reach the result list.
    const failedLength = repairProbeLength - (442 - 191);
    const travel = stage === 0
      ? failedLength * ease(position / 0.7)
      : repairProbeLength * clamp((position * 3) % 1 / 0.8);
    const point = repairProbePath.getPointAtLength(travel);
    repairProbe.setAttribute('cx', point.x);
    repairProbe.setAttribute('cy', point.y);
    repairProbe.style.opacity = (stage === 0 && position < 0.7) || (stage === 3 && position < 0.92) ? '1' : '0';
    const impact = clamp((position - 0.55) / 0.4);
    failureRing.setAttribute('r', String(12 + impact * 12));
    failureRing.style.opacity = stage === 0 ? String(Math.sin(impact * Math.PI) * 0.65) : '0';
    repairedHits.forEach((node, index) => {
      node.style.opacity = stage === 3 ? String(ease((position - index * 0.24 - 0.12) / 0.22)) : '0';
    });
  }

  function renderFrame() {
    const position = elapsed / stageDuration;
    const total = (stage + position) / 4;
    const progress = Math.round(clamp(total) * 1000);
    if (progress !== lastProgress) {
      demo.style.setProperty('--progress', (progress / 10) + '%');
      scrubber.value = String(progress);
      lastProgress = progress;
    }
    if (mode === 'build') renderBuild(position);
    if (mode === 'optimize') renderOptimization(position);
    if (mode === 'repair') renderRepair(position);
  }

  function renderStage() {
    demo.dataset.phase = String(stage);
    caption.textContent = modes[mode].captions[stage];
    captionNumber.textContent = String(stage + 1).padStart(2, '0');
    stageButtons.forEach((button, index) => {
      button.textContent = modes[mode].stages[index];
      if (index === stage) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    scrubber.setAttribute('aria-valuetext', modes[mode].stages[stage] + ' — ' + modes[mode].captions[stage]);
    renderFrame();
  }

  function selectMode(nextMode) {
    mode = nextMode;
    stage = 0;
    elapsed = 0;
    lastTime = null;
    lastProgress = -1;
    demo.dataset.mode = mode;
    demo.querySelector('.demo-counter').textContent = '0' + (names.indexOf(mode) + 1) + ' / 03';
    demo.querySelector('#demo-svg-title').textContent = modes[mode].title;
    demo.querySelector('#demo-svg-description').textContent = modes[mode].description;
    demo.querySelectorAll('[data-story]').forEach(story => story.setAttribute('aria-hidden', String(story.dataset.story !== mode)));
    modeButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.modeChoice === mode)));
    renderStage();
  }

  function tick(now) {
    frame = null;
    const delta = lastTime === null ? 0 : Math.min(now - lastTime, 100);
    elapsed += delta;
    lastTime = now;
    if (elapsed >= stageDuration) {
      elapsed = 0;
      if (stage === 3) selectMode(names[(names.indexOf(mode) + 1) % names.length]);
      else { stage += 1; renderStage(); }
    }
    renderFrame();
    frame = requestAnimationFrame(tick);
  }

  function syncPlayback() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    lastTime = null;
    demo.dataset.playing = String(playing);
    demo.dataset.suspended = String(!inView || document.hidden);
    playButton.setAttribute('aria-label', playing ? 'Pause animation' : 'Play animation');
    if (playing && inView && !document.hidden) frame = requestAnimationFrame(tick);
  }

  modeButtons.forEach(button => button.addEventListener('click', () => {
    selectMode(button.dataset.modeChoice);
    syncPlayback();
  }));
  stageButtons.forEach(button => button.addEventListener('click', () => {
    stage = Number(button.dataset.stage);
    elapsed = stageDuration * 0.95;
    playing = false;
    renderStage();
    syncPlayback();
  }));
  scrubber.addEventListener('input', () => {
    const position = Number(scrubber.value) / 1000 * 4;
    stage = Math.min(3, Math.floor(position));
    elapsed = (position - stage) * stageDuration;
    playing = false;
    renderStage();
    syncPlayback();
  });
  playButton.addEventListener('click', () => { playing = !playing; syncPlayback(); });
  document.addEventListener('visibilitychange', syncPlayback);
  motionPreference.addEventListener('change', () => {
    playing = !motionPreference.matches;
    demo.style.setProperty('--pointer-x', 0);
    demo.style.setProperty('--pointer-y', 0);
    renderFrame();
    syncPlayback();
  });
  demo.addEventListener('keydown', event => {
    if (event.key === 'Tab') { playing = false; syncPlayback(); }
  });
  scene.addEventListener('pointermove', event => {
    if (motionPreference.matches || event.pointerType === 'touch') return;
    const bounds = scene.getBoundingClientRect();
    demo.style.setProperty('--pointer-x', ((event.clientX - bounds.left) / bounds.width * 2 - 1).toFixed(3));
    demo.style.setProperty('--pointer-y', ((event.clientY - bounds.top) / bounds.height * 2 - 1).toFixed(3));
  });
  scene.addEventListener('pointerleave', () => {
    demo.style.setProperty('--pointer-x', 0);
    demo.style.setProperty('--pointer-y', 0);
  });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      syncPlayback();
    }, { threshold: 0.15 });
    observer.observe(demo);
  }
  demo.querySelectorAll('[hidden]').forEach(element => { element.hidden = false; });
  selectMode('build');
  syncPlayback();
})();
