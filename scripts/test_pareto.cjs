/* Test strict dominance, including ties and values that round to the same cent. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../leaderboard-pareto.js'), 'utf8'), context);
const frontier = (entries, axis) => Array.from(context.window.SearchSwePareto.frontier(entries, axis), e => e.id);
assert.deepEqual(frontier([
  {id: 'cheap', cost: 10, score: 5}, {id: 'best', cost: 20, score: 16},
  {id: 'dominated', cost: 40, score: 15}, {id: 'expensive', cost: 167, score: 1},
]), ['cheap', 'best']);
assert.deepEqual(frontier([
  {id: 'tie-a', cost: 2, score: 3}, {id: 'tie-b', cost: 2, score: 3},
  {id: 'lower-score', cost: 2, score: 2}, {id: 'higher-cost', cost: 3, score: 3},
]), ['tie-a', 'tie-b']);
assert.deepEqual(frontier([
  {id: 'slightly-cheaper', cost: 1.001, score: 3}, {id: 'rounded-tie', cost: 1.004, score: 3},
]), ['slightly-cheaper']);
assert.deepEqual(frontier([{id: 'free', cost: 0, score: 0}, {id: 'paid', cost: 1, score: 1}]), ['free', 'paid']);
assert.deepEqual(frontier([]), []);
const differentAxes = [
  {id: 'fast', cost: 5, tokens: 30, time: 1, score: 10},
  {id: 'efficient', cost: 10, tokens: 20, time: 2, score: 20},
  {id: 'best', cost: 20, tokens: 10, time: 3, score: 30},
];
assert.deepEqual(frontier(differentAxes, 'tokens'), ['best']);
assert.deepEqual(frontier(differentAxes, 'time'), ['fast', 'efficient', 'best']);
assert.deepEqual(frontier([
  {id: 'faster', time: 1.001, score: 3}, {id: 'rounded-tie', time: 1.004, score: 3},
], 'time'), ['faster']);
console.log('Pareto dominance checks passed.');
