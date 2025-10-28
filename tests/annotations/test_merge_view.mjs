import test from 'node:test';
import assert from 'node:assert/strict';

import { createVsCodeMergeBridge, DiffMergeView } from '../../src/annotations/merge.js';

test('createVsCodeMergeBridge threshold sanitization', (t) => {
  const bridge = createVsCodeMergeBridge({
    thresholds: {
      legacy: { request: 0.2, fallback: 0.1 },
      beta: { request: 0.95, fallback: 0.6 },
      stable: { request: 0.97, fallback: 0.5 }
    }
  });

  const thresholds = bridge.thresholds;
  assert.equal(thresholds.legacy.request, 0.65);
  assert.equal(thresholds.legacy.fallback, 0.65);
  assert.equal(thresholds.beta.request, 0.9);
  assert.equal(thresholds.beta.fallback, 0.75);
  assert.equal(thresholds.stable.request, 0.94);
  assert.equal(thresholds.stable.fallback, 0.82);
});

test('merge: stable precision inserts diff before golden and selects it initially', () => {
  const bridge = createVsCodeMergeBridge();
  const plan = bridge.buildTabPlan({ precision: 'stable', hasDiffStats: true });

  assert.deepEqual(
    plan.tabs.map((tab) => tab.id),
    ['plan', 'diff', 'golden']
  );
  assert.equal(plan.initialTabId, 'diff');
});

test('merge: tab plan snapshot', () => {
  const bridge = createVsCodeMergeBridge();
  const beta = bridge.buildTabPlan({ precision: 'beta', hasDiffStats: true });
  const legacy = bridge.buildTabPlan({ precision: 'legacy', hasDiffStats: true });

  assert.deepEqual(beta.tabs, [
    { id: 'plan', kind: 'plan', label: 'Plan', guard: null },
    { id: 'golden', kind: 'golden', label: 'Golden', guard: null },
    { id: 'diff', kind: 'diff', label: 'Diff', guard: null }
  ]);

  assert.deepEqual(legacy.tabs, beta.tabs);
  assert.equal(beta.initialTabId, 'plan');
  assert.equal(legacy.initialTabId, 'plan');
});

test('merge-ui: stable precision diff tab renders but keeps guard when stats missing', () => {
  const bridge = createVsCodeMergeBridge();
  const plan = bridge.buildTabPlan({ precision: 'stable', hasDiffStats: false });

  const view = new DiffMergeView({ plan, persistResolvedTabSelection: async () => {} });
  const diffTab = view.getTab('diff');
  assert.equal(diffTab.guard?.active, true);
  assert.equal(view.getSelectedTabId(), 'plan');
});

test('merge-ui: beta precision diff tab renders but guard blocks activation without stats', async () => {
  const warnings = [];
  const bridge = createVsCodeMergeBridge();
  const plan = bridge.buildTabPlan({ precision: 'beta', hasDiffStats: false });
  const view = new DiffMergeView({
    plan,
    persistResolvedTabSelection: async () => {
      throw new Error('persist-failed');
    },
    logger: { warn: (msg, error) => warnings.push([msg, error?.message]) }
  });

  const activated = await view.select('diff');
  assert.equal(activated, false);
  assert.equal(view.getSelectedTabId(), 'plan');
  assert.deepEqual(warnings, [['DiffMergeView: failed to persist resolved tab selection', 'persist-failed']]);
});
