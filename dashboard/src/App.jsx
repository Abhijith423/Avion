import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Compass,
  Radio,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

const COHORT_STYLES = {
  'HIGH-RISK': {
    badge: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
    bar: 'from-rose-500 to-amber-500',
    glow: 'hover:border-rose-500/50 hover:shadow-rose-950/30',
    dot: 'bg-rose-400',
  },
  'MID-RISK': {
    badge: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
    bar: 'from-amber-400 to-yellow-300',
    glow: 'hover:border-amber-500/50 hover:shadow-amber-950/30',
    dot: 'bg-amber-400',
  },
  STABLE: {
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
    bar: 'from-emerald-400 to-teal-300',
    glow: 'hover:border-emerald-500/50 hover:shadow-emerald-950/30',
    dot: 'bg-emerald-400',
  },
};

export default function App() {
  const [assessments, setAssessments] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [cohortFilter, setCohortFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [dispatching, setDispatching] = useState(false);
  const [dispatchBanner, setDispatchBanner] = useState(null);
  const [selectedSpecies, setSelectedSpecies] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const [healthRes, assessRes] = await Promise.all([
        fetch(`${API_BASE}/health`),
        fetch(`${API_BASE}/assessments`),
      ]);
      if (!healthRes.ok || !assessRes.ok) {
        throw new Error('FastAPI backend returned an error.');
      }
      const healthJson = await healthRes.json();
      const assessJson = await assessRes.json();
      const rows = Array.isArray(assessJson)
        ? assessJson
        : assessJson.assessments || [];
      setHealth(healthJson);
      setAssessments(rows);
      if (rows.length > 0 && !selectedSpecies) {
        setSelectedSpecies(rows[0]);
      }
    } catch (err) {
      setError(
        err.message ||
          'Unable to reach FastAPI on http://127.0.0.1:8000. Ensure fastapi dev api.py is running.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const triggerRangerDispatch = async () => {
    setDispatching(true);
    setDispatchBanner(null);
    try {
      const res = await fetch(`${API_BASE}/alerts/n8n?min_score=0.60`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'n8n dispatch failed');
      }
      setDispatchBanner({
        type: 'success',
        text: `Dispatched ${data.dispatched} HIGH-RISK alert(s) to n8n → Telegram (@kiwi_ranger_bot) [HTTP ${data.n8n_status_code}]`,
      });
    } catch (err) {
      setDispatchBanner({
        type: 'error',
        text: `Dispatch error: ${err.message}`,
      });
    } finally {
      setDispatching(false);
    }
  };

  const stats = useMemo(() => {
    const total = assessments.length;
    const high = assessments.filter((a) => a.cohort === 'HIGH-RISK').length;
    const mid = assessments.filter((a) => a.cohort === 'MID-RISK').length;
    const stable = assessments.filter((a) => a.cohort === 'STABLE').length;
    const avgScore =
      total > 0
        ? (
            assessments.reduce((acc, item) => acc + Number(item.risk_score || 0), 0) /
            total
          ).toFixed(2)
        : '0.00';
    return { total, high, mid, stable, avgScore };
  }, [assessments]);

  const filteredAssessments = useMemo(() => {
    return assessments.filter((item) => {
      const matchesCohort =
        cohortFilter === 'ALL' || item.cohort === cohortFilter;
      const q = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !q ||
        item.common_name?.toLowerCase().includes(q) ||
        item.scientific_name?.toLowerCase().includes(q);
      return matchesCohort && matchesSearch;
    });
  }, [assessments, cohortFilter, searchQuery]);

  return (
    <div className="min-h-screen bg-[#060b14] text-slate-100 selection:bg-emerald-500/30">
      {/* Ambient background glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="absolute top-20 right-1/4 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Top Command Bar */}
        <header className="mb-8 flex flex-col justify-between gap-4 rounded-2xl border border-slate-800/80 bg-slate-900/70 p-6 backdrop-blur-xl lg:flex-row lg:items-center">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 shadow-lg shadow-emerald-950/50">
              <Compass className="h-6 w-6" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="bg-gradient-to-r from-white via-emerald-200 to-cyan-300 bg-clip-text text-2xl font-bold tracking-tight text-transparent sm:text-3xl">
                  AVION // SEQA Nova Triage Console
                </h1>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                  {health?.status === 'ok' ? 'API LIVE :8000' : 'CONNECTING'}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                Live Bio-Telemetry & Extinction Risk Scoring • GBIF • iNaturalist • eBird • Open-Meteo • Local Qwen2.5:3B
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={fetchData}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Sync Telemetry
            </button>

            <button
              onClick={triggerRangerDispatch}
              disabled={dispatching}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-rose-600 to-amber-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-rose-950/50 transition hover:from-rose-500 hover:to-amber-500 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              {dispatching ? 'Dispatching...' : 'Dispatch Ranger Alert'}
            </button>
          </div>
        </header>

        {/* Dispatch Feedback Banner */}
        {dispatchBanner && (
          <div
            className={`mb-6 flex items-center justify-between rounded-xl border px-4 py-3 text-sm ${
              dispatchBanner.type === 'success'
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
                : 'border-rose-500/40 bg-rose-500/10 text-rose-200'
            }`}
          >
            <div className="flex items-center gap-2.5">
              {dispatchBanner.type === 'success' ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-rose-400" />
              )}
              <span>{dispatchBanner.text}</span>
            </div>
            <button
              onClick={() => setDispatchBanner(null)}
              className="text-xs opacity-70 hover:opacity-100"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* API Error Alert */}
        {error && (
          <div className="mb-6 rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
            <p className="font-semibold">Backend Connection Error</p>
            <p className="mt-1 text-rose-300/90">{error}</p>
          </div>
        )}

        {/* 4 KPI Summary Cards */}
        <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-semibold tracking-wider uppercase">
                Monitored Taxa
              </span>
              <Radio className="h-4 w-4 text-cyan-400" />
            </div>
            <p className="mt-3 text-3xl font-bold text-white">{stats.total}</p>
            <p className="mt-1 text-xs text-slate-400">
              Active species in avian_nova.db
            </p>
          </div>

          <div className="rounded-2xl border border-rose-500/30 bg-gradient-to-br from-rose-950/30 to-slate-900/70 p-5 backdrop-blur">
            <div className="flex items-center justify-between text-rose-300">
              <span className="text-xs font-semibold tracking-wider uppercase">
                High-Risk Cohort
              </span>
              <ShieldAlert className="h-4 w-4 text-rose-400" />
            </div>
            <p className="mt-3 text-3xl font-bold text-rose-400">{stats.high}</p>
            <p className="mt-1 text-xs text-rose-200/70">
              Score ≥ 0.60 • Immediate triage
            </p>
          </div>

          <div className="rounded-2xl border border-amber-500/25 bg-slate-900/60 p-5 backdrop-blur">
            <div className="flex items-center justify-between text-amber-300">
              <span className="text-xs font-semibold tracking-wider uppercase">
                Mid-Risk Watchlist
              </span>
              <Activity className="h-4 w-4 text-amber-400" />
            </div>
            <p className="mt-3 text-3xl font-bold text-amber-300">{stats.mid}</p>
            <p className="mt-1 text-xs text-slate-400">
              Score 0.35 – 0.59 • Elevated watch
            </p>
          </div>

          <div className="rounded-2xl border border-emerald-500/25 bg-slate-900/60 p-5 backdrop-blur">
            <div className="flex items-center justify-between text-emerald-300">
              <span className="text-xs font-semibold tracking-wider uppercase">
                Mean Risk Index
              </span>
              <TrendingUp className="h-4 w-4 text-emerald-400" />
            </div>
            <p className="mt-3 text-3xl font-bold text-emerald-300">
              {stats.avgScore}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {stats.stable} species in STABLE cohort
            </p>
          </div>
        </section>

        {/* Filter & Search Toolbar */}
        <section className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex flex-wrap gap-2">
            {['ALL', 'HIGH-RISK', 'MID-RISK', 'STABLE'].map((tab) => (
              <button
                key={tab}
                onClick={() => setCohortFilter(tab)}
                className={`rounded-xl px-3.5 py-2 text-xs font-semibold tracking-wide transition ${
                  cohortFilter === tab
                    ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-950/50'
                    : 'border border-slate-800 bg-slate-900/70 text-slate-300 hover:border-slate-700'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter common or Latin name..."
              className="w-full rounded-xl border border-slate-800 bg-slate-900/80 py-2 pr-4 pl-10 text-sm text-slate-200 placeholder-slate-500 focus:border-emerald-500/50 focus:outline-none"
            />
          </div>
        </section>

        {/* Main Split Grid: Species Cards + AI Triage Inspector */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Left Column: Scored Species Grid */}
          <div className="space-y-4 lg:col-span-7">
            {filteredAssessments.map((species, idx) => {
              const style =
                COHORT_STYLES[species.cohort] || COHORT_STYLES['MID-RISK'];
              const scorePct = Math.min(
                100,
                Math.max(5, Math.round(Number(species.risk_score || 0) * 100))
              );
              const isSelected =
                selectedSpecies?.scientific_name === species.scientific_name;
              const drivers = Array.isArray(species.top_3_drivers)
                ? species.top_3_drivers
                : [];

              return (
                <div
                  key={`${species.scientific_name}-${idx}`}
                  onClick={() => setSelectedSpecies(species)}
                  className={`cursor-pointer rounded-2xl border bg-slate-900/70 p-5 transition-all duration-200 shadow-lg ${
                    isSelected
                      ? 'border-cyan-400/60 bg-slate-900/95 ring-1 ring-cyan-400/30'
                      : `border-slate-800/80 ${style.glow}`
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2.5">
                        <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
                        <h2 className="text-lg font-bold text-white">
                          {species.common_name}
                        </h2>
                      </div>
                      <p className="mt-0.5 pl-5 text-xs italic text-slate-400">
                        {species.scientific_name}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <span
                        className={`rounded-lg border px-2.5 py-1 text-xs font-bold tracking-wide ${style.badge}`}
                      >
                        {species.cohort}
                      </span>
                      <div className="text-right">
                        <span className="font-mono text-xl font-extrabold text-white">
                          {Number(species.risk_score).toFixed(2)}
                        </span>
                        <span className="block text-[10px] tracking-wider text-slate-500 uppercase">
                          RISK SCORE
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Risk Score Meter */}
                  <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full rounded-full bg-gradient-to-r ${style.bar} transition-all duration-500`}
                      style={{ width: `${scorePct}%` }}
                    />
                  </div>

                  {/* Top-3 Explainable Drivers */}
                  {drivers.length > 0 && (
                    <div className="mt-4">
                      <p className="mb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                        Top-3 Explainable Drivers
                      </p>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                        {drivers.slice(0, 3).map((d, dIdx) => (
                          <div
                            key={dIdx}
                            className="rounded-xl border border-slate-800 bg-slate-950/70 p-2.5"
                          >
                            <div className="flex items-center justify-between text-xs font-semibold text-cyan-300">
                              <span className="truncate">{d.factor}</span>
                              {d.weight !== undefined && (
                                <span className="ml-1 font-mono text-[11px] text-slate-400">
                                  {Number(d.weight).toFixed(2)}
                                </span>
                              )}
                            </div>
                            <p className="mt-1 line-clamp-2 text-[11px] text-slate-400">
                              {d.detail}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {!loading && filteredAssessments.length === 0 && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-10 text-center text-sm text-slate-400">
                No species match your current cohort filter or search query.
              </div>
            )}
          </div>

          {/* Right Column: Qwen2.5:3B Conservation Triage Inspector */}
          <aside className="lg:col-span-5">
            <div className="sticky top-6 rounded-2xl border border-slate-800/90 bg-slate-900/80 p-6 backdrop-blur-xl">
              <div className="flex items-center gap-2 text-xs font-semibold tracking-wider text-emerald-400 uppercase">
                <Sparkles className="h-4 w-4" />
                Local Qwen2.5:3B Field Triage Protocol
              </div>

              {selectedSpecies ? (
                <div className="mt-4">
                  <h3 className="text-xl font-bold text-white">
                    {selectedSpecies.common_name}
                  </h3>
                  <p className="text-xs italic text-slate-400">
                    {selectedSpecies.scientific_name}
                  </p>

                  <div className="mt-5 rounded-xl border border-emerald-500/20 bg-slate-950/80 p-4">
                    <p className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
                      Recommended Ranger Intervention
                    </p>
                    <p className="mt-2 text-sm leading-relaxed text-slate-200">
                      {selectedSpecies.intervention_note ||
                        'No triage note recorded for this assessment.'}
                    </p>
                  </div>

                  <div className="mt-5 space-y-2.5">
                    <p className="text-xs font-semibold tracking-wider text-slate-400 uppercase">
                      Signal Attribution Breakdown
                    </p>
                    {(selectedSpecies.top_3_drivers || []).map((drv, i) => (
                      <div
                        key={i}
                        className="flex items-start justify-between gap-3 rounded-xl border border-slate-800/80 bg-slate-950/50 p-3 text-xs"
                      >
                        <div>
                          <p className="font-semibold text-slate-200">
                            #{i + 1} {drv.factor}
                          </p>
                          <p className="mt-0.5 text-slate-400">{drv.detail}</p>
                        </div>
                        {drv.weight !== undefined && (
                          <span className="rounded-md bg-cyan-500/10 px-2 py-0.5 font-mono font-semibold text-cyan-300">
                            +{Number(drv.weight).toFixed(2)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-400">
                  Select any species card on the left to inspect its local LLM conservation triage note and driver weights.
                </p>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}