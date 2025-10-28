const PRECISION_LIMITS = {
  legacy: { request: { min: 0.65 }, fallback: { min: 0.65 } },
  beta: { request: { min: 0.75, max: 0.9 }, fallback: { min: 0.75 } },
  stable: { request: { min: 0.82, max: 0.94 }, fallback: { min: 0.82 } }
};

function clamp(value, { min, max }) {
  const lower = min ?? Number.NEGATIVE_INFINITY;
  const upper = max ?? Number.POSITIVE_INFINITY;
  if (value === undefined || Number.isNaN(value)) {
    return lower;
  }
  return Math.min(Math.max(value, lower), upper);
}

function sanitizeThresholds(thresholds = {}) {
  const result = {};
  for (const [precision, limits] of Object.entries(PRECISION_LIMITS)) {
    const values = thresholds[precision] ?? {};
    result[precision] = {
      request: clamp(values.request ?? limits.request.min, limits.request),
      fallback: clamp(values.fallback ?? limits.fallback.min, limits.fallback)
    };
  }
  return result;
}

function buildTabPlan(precision, hasDiffStats) {
  const diffGuard = hasDiffStats ? null : { reason: 'stats-missing', active: true };
  const tabs = [
    { id: 'plan', kind: 'plan', label: 'Plan', guard: null },
    { id: 'golden', kind: 'golden', label: 'Golden', guard: null }
  ];

  const diffTab = { id: 'diff', kind: 'diff', label: 'Diff', guard: diffGuard };

  if (precision === 'stable') {
    tabs.splice(1, 0, diffTab);
  } else {
    tabs.push(diffTab);
  }
  const initialTabId = precision === 'stable' && !diffGuard ? 'diff' : 'plan';

  return { tabs, initialTabId };
}

class DiffMergeView {
  constructor({ plan, persistResolvedTabSelection = async () => {}, logger = console }) {
    this._plan = plan;
    this._persist = persistResolvedTabSelection;
    this._logger = logger;
    this._selected = plan.initialTabId;
  }

  getSelectedTabId() {
    return this._selected;
  }

  getTab(tabId) {
    const tab = this._plan.tabs.find((t) => t.id === tabId);
    if (!tab) {
      throw new Error(`Unknown tab: ${tabId}`);
    }
    return tab;
  }

  async select(tabId) {
    const tab = this.getTab(tabId);
    const guardActive = Boolean(tab.guard?.active);
    if (!guardActive) {
      this._selected = tabId;
    }
    try {
      await this._persist(tabId);
    } catch (error) {
      this._logger.warn('DiffMergeView: failed to persist resolved tab selection', error);
    }
    return !guardActive;
  }
}

function createVsCodeMergeBridge(options = {}) {
  const thresholds = sanitizeThresholds(options.thresholds);

  return {
    thresholds,
    buildTabPlan: ({ precision, hasDiffStats }) => buildTabPlan(precision, hasDiffStats),
    createView(planOptions) {
      const plan = planOptions.tabs ? planOptions : buildTabPlan(planOptions.precision, planOptions.hasDiffStats);
      return new DiffMergeView({
        plan,
        persistResolvedTabSelection: options.persistResolvedTabSelection,
        logger: options.logger
      });
    }
  };
}

export { createVsCodeMergeBridge, DiffMergeView };
