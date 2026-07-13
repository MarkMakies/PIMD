# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# PIMD Classify (Classify) v1.2
# — Mode 2 live/replay signature classifier
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Fourth tool in the gui/classviz/delaycal/classify family. Classifies Mode 2
# frames from either a live serial port or a recorded ClassViz session CSV
# through one shared, Qt-free pipeline (baseline -> detection -> features ->
# classification) -- replay and live share the exact same Engine.process_frame
# call, so every live decision is reproducible from a session file. A
# --headless <session.csv> CLI mode runs the identical pipeline with no Qt
# import at all, for CI / no-hardware testing (DESIGN §9 Mode 2 protocol,
# §10 cal_72_air_v2 profile, §11 invariants -- no firmware changes, no new
# serial commands, never reorders the 72-cell channel order).
#
# Reuses (does not reimplement): pimd_features.py's session parser, profile
# geometry guard, and wide-format signature writer; pimd_corpus_check.py's
# corpus loader, cosine primitive and canary-suffix stripper; and
# pimd_v2_findings.py's band-mean/crossing-continuum physics (F13/F16).
#
# v1.0 Initial release.
#     - Qt-free core: FrameRecord/FrameResult, BaselineTracker (causal EMA air
#       baseline, F2), EventDetector (amplitude hysteresis + min-duration
#       state machine, Stage A), FeatureExtractor (band means/continuum/
#       band-8 sign/threshold late-early ratio), FamilyClassifier (continuum
#       rule, Stage B1), IdentityClassifier (1-NN cosine vs the corpus,
#       margin/open-set/pile-level policy, Stage B2), Engine (owns all of the
#       above, exposes the single process_frame() entrypoint the GUI and
#       --headless both call).
#     - GUI: live serial (QSerialPort, no auto-connect) or session replay
#       (play/pause/speed/seek) into the same Engine; heatmap + band-mean
#       curve, verdict panel (continuum gauge, top-3 identity, margin,
#       verdict reasoning), strip charts, Event Log tab, Dump Signatures /
#       event log / per-frame CSV exports, session report.
#     - --headless <session.csv> replay: prints one line per closed event
#       plus a scored summary (identity hit-rate from ground-truth marks,
#       family correctness against pimd_v2_findings.FAM3 -- verification-only,
#       never consulted by the live classifier itself). Exit code 2 on a
#       profile-geometry mismatch (DESIGN §11 guard), 0 otherwise.
#     - Canary rows (CANARY-START/END) are folded into their base target name
#       in the identity corpus pool (they're the same physical object, F20
#       shows they're highly repeatable) rather than excluded -- reversible
#       one-line change if a future finding wants them held out instead.
#
# v1.1
#     - Heatmap: added ±mV range spinbox + Autoscale checkbox (mirrors the
#       existing band-mean chart range control), and real axis labels/ticks
#       (bottom = Threshold, per-cell threshold_v; left = Band, per-band
#       freq_hz/pulse_us) -- same convention pimd_classviz.py already uses.
#     - Band-mean chart: x-axis now ticks only the profile's actual pulse
#       widths, not generic log-scale ticks.
#     - Event Log tab: fixed rows after the first populating with blank
#       cells -- root cause was QTableWidget sorting (enabled at build time)
#       re-sorting mid-way through a row's per-column setItem() calls once
#       any column sort was active, so later columns landed on a
#       different, already-sorted row. Sorting is now disabled for the
#       duration of each row's insert+populate.
#
# v1.2
#     - The 4 lower strip charts are now independently configurable: each has
#       a mode combo (STRIP_MODES, module-level) and a band combo (shown when
#       the mode needs one). Added two new modes: 'Band mean (mV)' (a chosen
#       band's mean signal delta over time) and 'Per-delay normalized (9
#       cells)' (that band's 9 individual cell readings, each divided by its
#       own first sample so all start at 1.0 -- shows which delay cell
#       drifts/responds most). The existing amp/continuum/cosine/baseline-
#       band-mean strips became modes too (baseline band mean generalized
#       from the old hardcoded-to-last-band 'band8' strip). Per-delay uses
#       raw (pre-baseline) per-cell readings, not delta -- delta's first
#       sample is always exactly 0 by construction (BaselineTracker.bootstrap()
#       sets the baseline to the very first frame), which would make
#       normalize-to-first-entry degenerate. Slot mode/band selections persist
#       to classify_settings.json (strip_modes/strip_bands, -1 == last band).
###############################################################################

import argparse
import json
import math
import os
import sys
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

import pimd_features
import pimd_corpus_check
import pimd_v2_findings

APP_VERSION = '1.2'

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPT_DIR, 'data', 'classify_settings.json')
DEFAULT_CORPUS = os.path.join(SCRIPT_DIR, '..', 'ML', 'V2', 'PIMD_target_corpus_signatures_v2.csv')
DEFAULT_PORT  = '/dev/ttyACM0'
REDRAW_MS     = 33   # ~30 Hz, decoupled from frame arrival (classviz pattern)

# Selectable content for each of the 4 lower strip charts (GUI only). 'Band
# mean' and 'Baseline band mean' read one chosen band's mean (of the signal
# delta / of the raw baseline respectively); 'Per-delay normalized' plots
# that band's 9 individual cell deltas, each divided by its own first sample
# so all 9 curves start at 1.0 and drift apart, showing which delay cell
# responds most/least over time. Shared between default_settings() and
# run_gui() so the two can't drift apart.
STRIP_MODES = [
    'Amplitude (mV)', 'Continuum (µs)', 'Top-1 cosine',
    'Band mean (mV)', 'Baseline band mean (mV)', 'Per-delay normalized (9 cells)',
]
STRIP_NEEDS_BAND = {'Band mean (mV)', 'Baseline band mean (mV)', 'Per-delay normalized (9 cells)'}
STRIP_LABELS = {
    'Amplitude (mV)': 'amp (mV)', 'Continuum (µs)': 'continuum (µs)',
    'Top-1 cosine': 'top-1 cosine', 'Band mean (mV)': 'band mean (mV)',
    'Baseline band mean (mV)': 'baseline band mean (mV)',
    'Per-delay normalized (9 cells)': 'per-delay (norm to t0)',
}
STRIP_DEFAULT_MODES = ['Amplitude (mV)', 'Continuum (µs)', 'Top-1 cosine', 'Baseline band mean (mV)']


def default_settings():
    """Flat settings dict -- persisted verbatim to classify_settings.json.
    Thresholds with no spec-given seed value (enter/exit amp, durations) are
    first-pass numbers, tuned against the four 2026-07-07 sessions during
    verification; the rest (floor/K/canary/SNR-gates) are the task's own
    stated defaults."""
    return {
        'port': DEFAULT_PORT,
        'baud': 115200,
        'profile_path': pimd_features.DEFAULT_PROFILE,
        'corpus_path': DEFAULT_CORPUS,
        'baseline_timescale_s': 15.0,
        'bootstrap_air_s': 8.0,
        'enter_amp_mV': 6.0,
        'exit_amp_mV': 4.0,
        'min_duration_s': 0.5,
        'exit_debounce_s': 0.3,
        'canary_mv_per_unit': 26.123,
        'repeat_floor': 0.0062,
        'k_reject': 8.0,
        'snr_family_gate': 10.0,
        'snr_detect_gate': 4.0,
        'heatmap_mode': 'current_frame',
        'heatmap_range_mV': 50.0,
        'heatmap_autoscale': True,
        'band_range_mV': 10.0,
        'band_autoscale': False,
        'strip_modes': list(STRIP_DEFAULT_MODES),
        'strip_bands': [-1, -1, -1, -1],   # -1 == last band
        'replay_speed': 1,
        'record_per_frame_csv': False,
        'last_session_dir': '',
        'last_export_dir': '',
        'window_w': 1600,
        'window_h': 1000,
        'window_x': None,
        'window_y': None,
        'top_h_splitter': None,
        'main_v_splitter': None,
    }


# =============================================================================
# CORE PIPELINE — Qt-free (no PyQt6/pyqtgraph import anywhere in this region).
# BaselineTracker/EventDetector never read wall-clock time, only rec.t_seconds
# -- this is what guarantees replay at any speed (or headless, which has no
# timer at all) produces byte-identical decisions.
# =============================================================================

@dataclass
class FrameRecord:
    t_seconds: float
    frame_mV: object      # np.ndarray (n_channels,), raw, pre-baseline
    mark_label: object    # raw '# mark:' text attached to this frame, or None
    source_index: int


@dataclass
class FrameResult:
    t_seconds: float
    state: str            # 'AIR' | 'CANDIDATE' | 'DETECT'
    amp_mV: float
    amp_units: float
    snr: float
    closed_event: object = None   # Event, non-None exactly on the frame an event closes


class BaselineTracker:
    """Causal rolling-air baseline (F2), EMA over air-state frames only,
    frozen while a target is present. Unlike pimd_features.baseline_at()'s
    piecewise-linear air-anchor interpolation (needs the *next* air segment,
    fine offline, unusable live), this only ever looks backward."""

    def __init__(self, n_channels, timescale_s=15.0):
        self.n_channels = n_channels
        self.timescale_s = timescale_s
        self.baseline_mV = None
        self.noise_var_mV2 = np.zeros(n_channels)

    def bootstrap(self, first_frame_mV):
        self.baseline_mV = np.array(first_frame_mV, dtype=float).copy()

    def update(self, frame_mV, dt_s, is_air):
        if self.baseline_mV is None:
            self.bootstrap(frame_mV)
            return
        if not is_air or dt_s <= 0:
            return
        alpha = 1.0 - math.exp(-dt_s / self.timescale_s)
        delta = frame_mV - self.baseline_mV
        self.baseline_mV = self.baseline_mV + alpha * delta
        self.noise_var_mV2 = self.noise_var_mV2 + alpha * (delta ** 2 - self.noise_var_mV2)

    def delta(self, frame_mV):
        if self.baseline_mV is None:
            return np.zeros_like(np.asarray(frame_mV, dtype=float))
        return np.asarray(frame_mV, dtype=float) - self.baseline_mV

    def air_noise_l2(self):
        return float(np.linalg.norm(np.sqrt(np.maximum(self.noise_var_mV2, 0.0))))


class EventDetector:
    """Amplitude hysteresis + min-duration state machine (Stage A).
    AIR -> CANDIDATE (amp >= enter) -> DETECT (held >= min_duration_s) ->
    AIR (amp < exit for >= exit_debounce_s). A CANDIDATE that drops back
    below exit before min_duration_s never becomes an event (discarded by
    the caller, not by this class -- this class only tracks state)."""

    def __init__(self, enter_amp_mV, exit_amp_mV, min_duration_s, exit_debounce_s):
        self.enter_amp_mV = enter_amp_mV
        self.exit_amp_mV = exit_amp_mV
        self.min_duration_s = min_duration_s
        self.exit_debounce_s = exit_debounce_s
        self.state = 'AIR'
        self._candidate_start_t = None
        self._below_exit_since = None

    def step(self, t_seconds, amp_mV):
        if self.state == 'AIR':
            if amp_mV >= self.enter_amp_mV:
                self.state = 'CANDIDATE'
                self._candidate_start_t = t_seconds
        elif self.state == 'CANDIDATE':
            if amp_mV < self.exit_amp_mV:
                self.state = 'AIR'
                self._candidate_start_t = None
            elif (t_seconds - self._candidate_start_t) >= self.min_duration_s:
                self.state = 'DETECT'
                self._below_exit_since = None
        elif self.state == 'DETECT':
            if amp_mV < self.exit_amp_mV:
                if self._below_exit_since is None:
                    self._below_exit_since = t_seconds
                elif (t_seconds - self._below_exit_since) >= self.exit_debounce_s:
                    self.state = 'AIR'
                    self._below_exit_since = None
            else:
                self._below_exit_since = None
        return self.state

    def reset_to_air(self):
        self.state = 'AIR'
        self._candidate_start_t = None
        self._below_exit_since = None


@dataclass
class EventFeatures:
    shape: object          # np.ndarray (n_channels,), L2-normalized delta
    band_means: object     # np.ndarray (n_bands,), pimd_v2_findings.bandmeans()
    crossing_us_raw: object    # float or None
    continuum_us: float         # ladder-clamped 5/150, pimd_v2_findings.continuum()
    band8_sign: int
    late_early_ratio: float


class FeatureExtractor:
    """Per-event feature computation from the event's median delta vector.
    Band means / crossing / continuum are reused verbatim from
    pimd_v2_findings.py (F13/F16) -- not reimplemented here."""

    def __init__(self, colmap):
        n_bands = max(c['band_index'] for c in colmap) + 1
        n_cells = len(colmap) // n_bands
        self.n_bands = n_bands
        self.n_cells = n_cells
        self.pulses_us = [colmap[b * n_cells]['pulse_us'] for b in range(n_bands)]

    def extract(self, delta_mV):
        norm = np.linalg.norm(delta_mV)
        shape = delta_mV / norm if norm > 1e-12 else np.zeros_like(delta_mV)
        band_means = pimd_v2_findings.bandmeans(delta_mV)
        crossing_raw = pimd_v2_findings.crossing_us(delta_mV, self.pulses_us)
        continuum_us = pimd_v2_findings.continuum(delta_mV, self.pulses_us)
        band8_sign = 1 if band_means[-1] >= 0 else -1
        cell_profile = np.mean(np.abs(delta_mV.reshape(self.n_bands, self.n_cells)), axis=0)
        early = cell_profile[:4].mean()
        late = cell_profile[5:].mean()   # cell index 4 (mid threshold, 1.45V) excluded
        late_early_ratio = float(late / early) if early > 1e-9 else float('inf')
        return EventFeatures(shape, band_means, crossing_raw, continuum_us, band8_sign, late_early_ratio)


class FamilyClassifier:
    """Stage B1 -- continuum rule. Sign convention verified against
    pimd_v2_findings.continuum()'s actual code (`5.0 if bandmeans(v)[7] > 0
    else 150.0`) AND against real corpus data (steel spanner/galvanized pipe
    -- ferrous -- have positive band-8 means; aluminium plate -- non-ferrous
    -- has a negative one). This also matches the task spec's own wording
    ("no-crossing-negative non-ferrous") exactly."""

    def classify(self, f):
        if f.crossing_us_raw is not None:
            if f.crossing_us_raw < 7.0:
                return 'ferrous', 'crossing {0:.3f} µs < 7 µs'.format(f.crossing_us_raw)
            return 'crossover', 'crossing {0:.3f} µs >= 7 µs (mid-range)'.format(f.crossing_us_raw)
        if f.band_means[-1] > 0:
            return 'ferrous', 'no crossing, band-8 positive (clamped 5 µs, pure ferrous)'
        return 'non-ferrous', 'no crossing, band-8 negative (clamped 150 µs, pure non-ferrous)'


@dataclass
class IdentityResult:
    mode: str        # 'detection-only' | 'family-only' | 'identified' | 'pile-level' | 'unknown-object'
    label: object     # str or None
    top3: object        # list[(target, cosine, distance_in_floor_multiples)]
    margin_floor: object  # float or None
    reason: str


_PILE_LABELS = {
    'ferrous': 'ferrous pile',
    'non-ferrous': 'non-ferrous good conductor',
    'crossover': 'ambiguous (crossover)',
}


class IdentityClassifier:
    """Stage B2 -- 1-NN cosine vs the corpus usable set, margin-in-floor-units
    policy, pile-level fallback, open-set reject (F15/F17)."""

    def __init__(self, corpus_pool, repeat_floor=0.0062, k_reject=8.0,
                 snr_family_gate=10.0, snr_detect_gate=4.0):
        self.corpus_pool = corpus_pool
        self.repeat_floor = repeat_floor
        self.k_reject = k_reject
        self.snr_family_gate = snr_family_gate
        self.snr_detect_gate = snr_detect_gate

    def classify(self, f, event_snr, family):
        if event_snr < self.snr_detect_gate:
            return IdentityResult('detection-only', None, [], None,
                                   'SNR {0:.3f} < {1:.3f} -> detection-only'.format(
                                       event_snr, self.snr_detect_gate))
        if event_snr < self.snr_family_gate:
            return IdentityResult('family-only', family, [], None,
                                   'SNR {0:.3f} < {1:.3f} -> family-only ({2})'.format(
                                       event_snr, self.snr_family_gate, family))
        if not self.corpus_pool:
            return IdentityResult('family-only', family, [], None,
                                   'no usable corpus rows loaded -> family-only ({0})'.format(family))

        best_per_label = {}
        for label, ref_shape in self.corpus_pool:
            d = 1.0 - pimd_corpus_check.cosine(f.shape, ref_shape)
            if label not in best_per_label or d < best_per_label[label]:
                best_per_label[label] = d
        ranked = sorted(best_per_label.items(), key=lambda kv: kv[1])
        top3 = [(label, 1.0 - d, d / self.repeat_floor) for label, d in ranked[:3]]
        label1, d1 = ranked[0]
        d2 = ranked[1][1] if len(ranked) > 1 else math.inf
        margin_floor = (d2 - d1) / self.repeat_floor
        nearest_floor = d1 / self.repeat_floor

        if nearest_floor > self.k_reject:
            return IdentityResult('unknown-object', None, top3, margin_floor,
                                   'nearest {0:.1f}x floor > K={1:.1f} -> unknown object'.format(
                                       nearest_floor, self.k_reject))
        if margin_floor < 2.0:
            pile_label = _PILE_LABELS.get(family, 'unclassified pile')
            return IdentityResult('pile-level', pile_label, top3, margin_floor,
                                   'margin {0:.1f}x floor < 2x floor -> pile-level ({1})'.format(
                                       margin_floor, pile_label))
        return IdentityResult('identified', label1, top3, margin_floor,
                               'nearest {0}, margin {1:.1f}x floor'.format(label1, margin_floor))


def load_corpus_pool(corpus_path, snr_gate=10.0):
    """Builds the 1-NN identity pool: [(label, unit_shape), ...]. SNR >= gate
    (F12) rows only. CANARY-START/END rows are folded into their base target
    name via pimd_corpus_check.strip_canary_suffix (design decision -- see
    the plan/changelog: canaries are the same physical object and F20 shows
    they're highly repeatable, so folding adds real samples instead of
    discarding good data)."""
    data = pimd_corpus_check.load_corpus(corpus_path)
    pool = []
    for (_, target, _), row in data.items():
        if row['splithalf'] <= 0:
            continue
        if row['amp'] / row['splithalf'] < snr_gate:
            continue
        stripped = pimd_corpus_check.strip_canary_suffix(target)
        label = stripped[0] if stripped and stripped[0] else target
        norm = np.linalg.norm(row['shape'])
        if norm <= 1e-12:
            continue
        pool.append((label, row['shape'] / norm))
    return pool


def build_verdict(family, identity):
    if identity.mode == 'identified':
        return identity.label, identity.reason
    if identity.mode == 'pile-level':
        return identity.label, identity.reason
    if identity.mode == 'unknown-object':
        return 'unknown object', identity.reason
    if identity.mode == 'family-only':
        return '{0} (family only)'.format(family), identity.reason
    return 'detection only', identity.reason


@dataclass
class Event:
    event_id: int
    t_start_s: float
    t_end_s: float
    n_frames: int
    amp_series_mV: object        # list[float]
    amp_mean_mV: float
    amp_peak_mV: float
    amp_drift_pct: float
    delta_median_mV: object      # np.ndarray (n_channels,)
    delta_frames_mV: object      # np.ndarray (n_frames, n_channels) -- kept for splithalf/export
    features: object              # EventFeatures
    event_snr: float
    family: str
    family_reason: str
    identity: object               # IdentityResult
    verdict: str
    verdict_reason: str
    ground_truth_label: object = None
    hit: object = None


class Engine:
    """Owns the whole Stage A/B pipeline. process_frame() is the single
    entrypoint both the GUI (live and replay) and --headless call -- no
    branch anywhere in this class depends on how the frame arrived."""

    def __init__(self, profile, colmap, settings, corpus_pool):
        self.profile = profile
        self.colmap = colmap
        self.n_channels = len(colmap)
        self.settings = settings
        self.baseline = BaselineTracker(self.n_channels, settings['baseline_timescale_s'])
        self.detector = EventDetector(settings['enter_amp_mV'], settings['exit_amp_mV'],
                                       settings['min_duration_s'], settings['exit_debounce_s'])
        self.feature_extractor = FeatureExtractor(colmap)
        self.family_clf = FamilyClassifier()
        self.identity_clf = IdentityClassifier(corpus_pool, settings['repeat_floor'], settings['k_reject'],
                                                settings['snr_family_gate'], settings['snr_detect_gate'])
        self.bootstrap_air_s = settings['bootstrap_air_s']

        self.events = []
        self.frame_log = []
        self._next_event_id = 0
        self._prev_t = None
        self._bootstrap_done = False
        self._event_buf_t = []
        self._event_buf_delta = []
        self._event_air_noise_at_open = None
        self._raw_frame_history = deque(maxlen=20)   # recent raw frames, for request_rebaseline()

    def process_frame(self, rec):
        self._raw_frame_history.append(rec.frame_mV)
        t = rec.t_seconds
        dt_s = 0.0 if self._prev_t is None else max(t - self._prev_t, 0.0)
        self._prev_t = t

        if not self._bootstrap_done:
            if t >= self.bootstrap_air_s:
                self._bootstrap_done = True
            elif rec.mark_label is not None:
                _, _, is_air_mark = pimd_features.parse_mark_label(rec.mark_label)
                if not is_air_mark:
                    self._bootstrap_done = True

        prev_state = 'AIR' if not self._bootstrap_done else self.detector.state
        is_air = (prev_state == 'AIR')
        self.baseline.update(rec.frame_mV, dt_s, is_air=is_air)
        delta = self.baseline.delta(rec.frame_mV)
        amp_mV = float(np.linalg.norm(delta))

        new_state = 'AIR' if not self._bootstrap_done else self.detector.step(t, amp_mV)

        closed_event = None
        if self._bootstrap_done:
            entering = (prev_state == 'AIR' and new_state in ('CANDIDATE', 'DETECT'))
            if entering:
                self._event_buf_t = []
                self._event_buf_delta = []
                self._event_air_noise_at_open = self.baseline.air_noise_l2()
            if new_state in ('CANDIDATE', 'DETECT') or prev_state in ('CANDIDATE', 'DETECT'):
                self._event_buf_t.append(t)
                self._event_buf_delta.append(delta)
            if prev_state == 'CANDIDATE' and new_state == 'AIR':
                self._event_buf_t = []
                self._event_buf_delta = []
            elif prev_state == 'DETECT' and new_state == 'AIR':
                closed_event = self._close_event()

        air_noise = self.baseline.air_noise_l2()
        result = FrameResult(
            t_seconds=t, state=new_state, amp_mV=amp_mV,
            amp_units=amp_mV / self.settings['canary_mv_per_unit'],
            snr=(amp_mV / air_noise) if air_noise > 1e-12 else float('inf'),
            closed_event=closed_event,
        )
        self.frame_log.append(result)
        return result

    def _close_event(self):
        t_arr = np.array(self._event_buf_t, dtype=float)
        delta_arr = np.array(self._event_buf_delta, dtype=float)
        amp_series = np.linalg.norm(delta_arr, axis=1).tolist()
        delta_median = np.median(delta_arr, axis=0)
        features = self.feature_extractor.extract(delta_median)
        amp_mean = float(np.mean(amp_series))
        amp_peak = float(np.max(amp_series))
        n = len(amp_series)
        k = max(1, int(round(n * 0.2)))
        amp_drift_pct = float((np.mean(amp_series[-k:]) - np.mean(amp_series[:k])) / amp_mean * 100.0) \
            if amp_mean > 1e-9 else 0.0
        air_noise = self._event_air_noise_at_open if self._event_air_noise_at_open else self.baseline.air_noise_l2()
        event_snr = (amp_mean / air_noise) if air_noise > 1e-12 else float('inf')

        family, family_reason = self.family_clf.classify(features)
        identity = self.identity_clf.classify(features, event_snr, family)
        verdict, verdict_reason = build_verdict(family, identity)

        event = Event(
            event_id=self._next_event_id,
            t_start_s=float(t_arr[0]), t_end_s=float(t_arr[-1]), n_frames=n,
            amp_series_mV=amp_series, amp_mean_mV=amp_mean, amp_peak_mV=amp_peak,
            amp_drift_pct=amp_drift_pct, delta_median_mV=delta_median, delta_frames_mV=delta_arr,
            features=features, event_snr=event_snr,
            family=family, family_reason=family_reason, identity=identity,
            verdict=verdict, verdict_reason=verdict_reason,
        )
        self._next_event_id += 1
        self.events.append(event)
        self._event_buf_t = []
        self._event_buf_delta = []
        self._event_air_noise_at_open = None
        return event

    def finalize(self):
        """Called at EOF (or user-initiated stop). A DETECT in progress is
        closed and flagged truncated; a CANDIDATE in progress never reached
        min_duration_s and is discarded."""
        if self.detector.state == 'DETECT' and self._event_buf_t:
            ev = self._close_event()
            ev.verdict_reason += ' [truncated at session end]'
            return ev
        self._event_buf_t = []
        self._event_buf_delta = []
        return None

    def request_rebaseline(self):
        """Manually snaps the air baseline to the median of recently seen raw
        frames right now, instead of waiting for the EMA to catch up -- for
        the operator to confirm 'the coil is in air now' and get an
        immediate clean reference (e.g. after physically clearing a target)
        rather than a slow ~15s EMA re-converge. Available identically from
        the GUI (button) and any future headless/scripted caller (method) --
        both call this same Engine method, keeping the shared-pipeline
        invariant. Discards any in-progress candidate/detect event without
        logging it, since its baseline-relative delta is invalidated by the
        snap -- the operator is asserting the buffered frames were air, not
        a real target. Returns False (no-op) if no frames have been seen
        yet."""
        if not self._raw_frame_history:
            return False
        median_frame = np.median(np.array(self._raw_frame_history), axis=0)
        self.baseline.baseline_mV = median_frame.copy()
        self.baseline.noise_var_mV2 = np.zeros(self.n_channels)
        self.detector.reset_to_air()
        self._event_buf_t = []
        self._event_buf_delta = []
        self._event_air_noise_at_open = None
        return True


# -----------------------------------------------------------------------------
# Session / replay support (Qt-free)
# -----------------------------------------------------------------------------

def colmap_from_profile(profile):
    """Builds a colmap list (band_index/freq_hz/pulse_us/delay_us/threshold_v
    per channel) directly from a profile dict, in the same band-major channel
    order (band_index*n_cells+cell_index) session CSVs use -- for live mode,
    where there is no recorded colmap to read."""
    colmap = []
    for b, band in enumerate(profile['bands']):
        for c in range(len(band['delays_us'])):
            colmap.append({
                'band_index': b,
                'freq_hz': band['freq_hz'],
                'pulse_us': band['pulse_us'],
                'delay_us': band['delays_us'][c],
                'threshold_v': band['threshold_v'][c],
            })
    return colmap


DYNAMIC_PROFILE_INDEX = 5   # must match firmware's NUM_PROFILES (pimd_mcu.py v4.07+) -- same
                             # slot pimd_classviz.py's "Load and Run" uses (DYNAMIC_PROFILE_INDEX)


def build_d_command(profile):
    """Builds the firmware 'D' command that loads a profile as a RAM-only
    dynamic profile (no flash writes, DESIGN §11) at DYNAMIC_PROFILE_INDEX --
    identical wire format to pimd_classviz.py's _build_d_command(). Needed
    because cal_72_air_v2 is not one of the board's compiled static profiles
    (those are 45-channel CLASSIFY_EP-family profiles) -- it only exists once
    pushed onto the board this way, exactly as ClassViz's "Load and Run" does."""
    parts = ['D{0}'.format(profile['averages'])]
    for b in profile['bands']:
        fields = [str(b['freq_hz']), '{0:.3f}'.format(b['pulse_us'])]
        fields += ['{0:.3f}'.format(d) for d in b['delays_us']]
        parts.append(','.join(fields))
    return ';'.join(parts)


def load_session(path):
    sess = pimd_features.parse_session_file(path)
    sess = pimd_features.drop_flagged(sess)
    return sess


class ReplayFrameSource:
    """Qt-free adapter over a parsed SessionData -- pumped by the GUI's replay
    QTimer or directly by a plain for-loop in headless mode. Marks are
    attached to the first frame at/after their timestamp."""

    def __init__(self, sess):
        self.sess = sess
        mark_at_frame = {}
        for mark_dt, label in sorted(sess.marks, key=lambda m: m[0]):
            mark_t = (mark_dt - sess.t0).total_seconds()
            idx = int(np.searchsorted(sess.t_seconds, mark_t))
            if idx < len(sess.t_seconds):
                mark_at_frame.setdefault(idx, label)
        self._mark_at_frame = mark_at_frame
        self.marks_by_frame = sorted(mark_at_frame.items())

    def __len__(self):
        return len(self.sess.t_seconds)

    def __iter__(self):
        for i in range(len(self.sess.t_seconds)):
            yield FrameRecord(
                t_seconds=float(self.sess.t_seconds[i]),
                frame_mV=self.sess.frames_mV[i],
                mark_label=self._mark_at_frame.get(i),
                source_index=i,
            )


def plateau_time_ranges(sess, frame_rate_hz, settle_s=None):
    """Non-air plateau (label, t_start, t_end) ranges from '# mark:' ground
    truth, for post-hoc event scoring. Empty if the session has no marks."""
    if not sess.marks:
        return []
    if settle_s is None:
        settle_s = pimd_features.SETTLE_S_DEFAULT
    plateaus = pimd_features.segment_from_marks(sess, frame_rate_hz, settle_s)
    ranges = []
    for p in plateaus:
        if p.is_air:
            continue
        end_idx = min(p.end_idx, len(sess.t_seconds) - 1)
        ranges.append((p.label, float(sess.t_seconds[p.start_idx]), float(sess.t_seconds[end_idx])))
    return ranges


def _normalize_gt_label(label):
    stripped = pimd_corpus_check.strip_canary_suffix(label)
    base = stripped[0] if stripped and stripped[0] else label
    return base.split('(rpt')[0].strip()


def attach_ground_truth(event, ranges):
    """Sets event.ground_truth_label / event.hit by time-overlap against
    mark-derived plateaus. Never used to drive live detection -- see
    Engine.process_frame's bootstrap-only use of marks -- only to score an
    already-closed event."""
    if not ranges:
        return
    mid = 0.5 * (event.t_start_s + event.t_end_s)
    contained = [r for r in ranges if r[1] <= mid <= r[2]]
    if contained:
        label = contained[0][0]
    else:
        label = min(ranges, key=lambda r: min(abs(mid - r[1]), abs(mid - r[2])))[0]
    event.ground_truth_label = label
    gt_norm = _normalize_gt_label(label)
    if event.identity.mode == 'identified':
        event.hit = (event.identity.label == gt_norm)
    else:
        event.hit = None


def score_family(event):
    """Verification-only: compares the live family verdict against
    pimd_v2_findings.FAM3's hand-curated campaign-2 ground truth. Never
    consulted by FamilyClassifier itself, which stays a live physics rule
    with no fixed target list -- this exists purely so --headless can print
    an automated family-correctness summary during verification."""
    if not event.ground_truth_label:
        return None
    base = _normalize_gt_label(event.ground_truth_label)
    true_family = pimd_v2_findings.FAM3.get(base)
    if true_family is None:
        return None
    return event.family == true_family


def _event_splithalf(event):
    n = event.delta_frames_mV.shape[0]
    half = n // 2
    if half == 0:
        return 0.0
    first_med = np.median(event.delta_frames_mV[:half], axis=0)
    second_med = np.median(event.delta_frames_mV[half:], axis=0)
    return float(np.linalg.norm(first_med - second_med) / 2.0)


# -----------------------------------------------------------------------------
# Export helpers (shared by GUI and --headless)
# -----------------------------------------------------------------------------

EVENT_LOG_HEADER = (
    'event_id,t_start_s,t_end_s,duration_s,n_frames,amp_mean_mV,amp_peak_mV,amp_drift_pct,'
    'event_snr,continuum_us,band8_sign,late_early_ratio,family,family_reason,identity_mode,'
    'identity_label,margin_floor,top1,top2,top3,verdict,verdict_reason,ground_truth,hit,'
    + ','.join('band_mean_{0}'.format(i) for i in range(8))
)


def write_event_log_csv(path, events):
    with open(path, 'w') as f:
        f.write(EVENT_LOG_HEADER + '\n')
        for e in events:
            top_strs = ['{0}:{1:.3f}'.format(label, cos) for label, cos, _ in e.identity.top3]
            while len(top_strs) < 3:
                top_strs.append('')
            row = [
                str(e.event_id),
                pimd_features.format_value(e.t_start_s), pimd_features.format_value(e.t_end_s),
                pimd_features.format_value(e.t_end_s - e.t_start_s), str(e.n_frames),
                pimd_features.format_value(e.amp_mean_mV), pimd_features.format_value(e.amp_peak_mV),
                pimd_features.format_value(e.amp_drift_pct), pimd_features.format_value(e.event_snr),
                pimd_features.format_value(e.features.continuum_us), str(e.features.band8_sign),
                pimd_features.format_value(e.features.late_early_ratio),
                e.family, e.family_reason, e.identity.mode, e.identity.label or '',
                pimd_features.format_value(e.identity.margin_floor) if e.identity.margin_floor is not None
                and math.isfinite(e.identity.margin_floor) else '',
                top_strs[0], top_strs[1], top_strs[2],
                e.verdict, e.verdict_reason, e.ground_truth_label or '',
                '' if e.hit is None else str(e.hit),
            ] + [pimd_features.format_value(v) for v in e.features.band_means]
            # Every CSV in this repo is parsed with a plain split(',') -- a comma inside a
            # free-text reason string would corrupt every later column, so neutralize it.
            row = [str(v).replace(',', ';') for v in row]
            f.write(','.join(row) + '\n')


def write_wide_signatures(path, sess, events, reference_profile):
    n_channels = len(sess.colmap)
    f = pimd_features.open_wide_writer(path, append=False, profile_name=reference_profile['name'],
                                        n_channels=n_channels)
    try:
        session_stem = os.path.splitext(os.path.basename(sess.path))[0]
        for e in events:
            label = e.ground_truth_label if e.ground_truth_label else 'unknown-{0}'.format(e.event_id)
            plateau = pimd_features.Plateau(label=label, distance_cm=None, is_air=False, start_idx=0, end_idx=0)
            splithalf = _event_splithalf(e)
            quality = pimd_features.quality_flags(splithalf, e.amp_mean_mV, e.n_frames)
            amp_mean_abs = float(np.mean(np.abs(e.delta_median_mV)))
            row = pimd_features.build_wide_row(session_stem, plateau, e.delta_median_mV, e.amp_mean_mV,
                                                splithalf, quality, amp_mean_abs)
            f.write(row + '\n')
    finally:
        f.close()


# -----------------------------------------------------------------------------
# Headless mode
# -----------------------------------------------------------------------------

def format_event_line(e, canary_mv_per_unit):
    margin_str = '{0:.1f}xfloor'.format(e.identity.margin_floor) \
        if e.identity.margin_floor is not None and math.isfinite(e.identity.margin_floor) else 'n/a'
    return ('event {0}  t={1:.3f}-{2:.3f}s  n={3}  amp_mean={4:.3f}mV({5:.3f}u)  snr={6:.3f}  '
            'cont={7:.3f}us  family={8}  id={9} (margin={10})  gt={11}  hit={12}').format(
        e.event_id, e.t_start_s, e.t_end_s, e.n_frames,
        e.amp_mean_mV, e.amp_mean_mV / canary_mv_per_unit, e.event_snr,
        e.features.continuum_us, e.family, e.identity.label or '-', margin_str,
        e.ground_truth_label or '-', '-' if e.hit is None else str(e.hit))


def run_headless(args):
    try:
        reference_profile = pimd_features.load_reference_profile(args.profile)
    except (OSError, ValueError, KeyError) as exc:
        print('[ERROR] failed to load reference profile {0}: {1}'.format(args.profile, exc), file=sys.stderr)
        return 1

    try:
        sess = load_session(args.headless)
    except Exception as exc:  # noqa: BLE001 -- any parse failure is a clean [ERROR], not a traceback
        print('[ERROR] failed to parse session: {0}'.format(exc), file=sys.stderr)
        return 1

    ok, reason = pimd_features.validate_profile(sess.profile, reference_profile)
    if not ok:
        print('[REFUSED] profile geometry mismatch -- {0} (refusing to mix profile geometries, '
              'DESIGN §11)'.format(reason), file=sys.stderr)
        return 2

    if len(sess.t_seconds) < 2:
        print('[ERROR] fewer than 2 usable frames after dropping flagged rows', file=sys.stderr)
        return 1

    settings = default_settings()
    if args.settings and os.path.isfile(args.settings):
        with open(args.settings) as f:
            settings.update(json.load(f))

    try:
        corpus_pool = load_corpus_pool(args.corpus, settings['snr_family_gate']) if args.corpus else []
    except SystemExit as exc:
        print('[WARN] corpus load failed, identity stage disabled -- {0}'.format(exc), file=sys.stderr)
        corpus_pool = []

    engine = Engine(sess.profile, sess.colmap, settings, corpus_pool)
    frame_rate_hz = pimd_features.measure_frame_rate_hz(sess.t_seconds)
    ranges = plateau_time_ranges(sess, frame_rate_hz)

    closed_events = []
    for rec in ReplayFrameSource(sess):
        result = engine.process_frame(rec)
        if args.speed:
            time.sleep(args.speed)
        if result.closed_event is not None:
            attach_ground_truth(result.closed_event, ranges)
            closed_events.append(result.closed_event)
            print(format_event_line(result.closed_event, settings['canary_mv_per_unit']))
    trailing = engine.finalize()
    if trailing is not None:
        attach_ground_truth(trailing, ranges)
        closed_events.append(trailing)
        print(format_event_line(trailing, settings['canary_mv_per_unit']))

    family_scores = [s for s in (score_family(e) for e in closed_events) if s is not None]
    identity_scores = [e.hit for e in closed_events if e.hit is not None]
    print('{0} events, {1}/{2} family-correct, {3}/{4} identity-correct'.format(
        len(closed_events), sum(family_scores), len(family_scores),
        sum(1 for h in identity_scores if h), len(identity_scores)))

    if args.export_event_log:
        write_event_log_csv(args.export_event_log, closed_events)
    if args.dump_signatures:
        write_wide_signatures(args.dump_signatures, sess, closed_events, reference_profile)

    return 0


# =============================================================================
# GUI — PyQt6 (imported lazily inside run_gui(), never at module scope, so
# --headless has zero Qt/display dependency at runtime).
# =============================================================================

def run_gui(args):
    os.environ.setdefault('QT_API', 'pyqt6')

    from PyQt6.QtCore import QIODevice, QObject, QTimer, Qt, pyqtSignal
    from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo
    from PyQt6.QtWidgets import (
        QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
        QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
        QProgressBar, QPushButton, QSlider, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
        QVBoxLayout, QWidget,
    )
    import pyqtgraph as pg

    pg.setConfigOptions(background='w', foreground='k', antialias=True)

    MY_GREEN = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED = 'background-color: rgb(246, 97, 81);'
    MY_ORANGE = 'background-color: rgb(250, 178, 101);'

    STATE_LAMP_STYLE = {
        'AIR': MY_YELLOW, 'CANDIDATE': MY_ORANGE, 'DETECT': MY_ORANGE,
        'CLASSIFIED': MY_GREEN, 'UNKNOWN': MY_RED,
    }

    def _setup_colormaps():
        try:
            cm_div = pg.colormap.get('RdBu_r', source='matplotlib')
        except Exception:
            try:
                cm_div = pg.colormap.get('RdBu_r')
            except Exception:
                cm_div = pg.ColorMap(pos=np.array([0.0, 0.5, 1.0]),
                                      color=np.array([[0, 0, 220, 255], [255, 255, 255, 255],
                                                       [220, 0, 0, 255]], dtype=np.uint8))
        return cm_div

    class LiveFrameSource(QObject):
        """QSerialPort adapter, event-driven via readyRead like classviz --
        no worker thread, no auto-connect (caller must call open()/
        start_streaming() explicitly)."""

        frame_ready = pyqtSignal(object)
        line_received = pyqtSignal(str)
        command_sent = pyqtSignal(str)
        error = pyqtSignal(str)

        def __init__(self, port_name, active_profile_idx, n_channels, baud=115200):
            super().__init__()
            self.serial = QSerialPort()
            self.serial.readyRead.connect(self._on_ready_read)
            self.port_name = port_name
            self.baud = baud
            self.active_profile_idx = active_profile_idx
            self.n_channels = n_channels
            self._t0_ms = None
            # Diagnostic counters -- surfaced in the GUI status bar so a stuck
            # live feed can be triaged (no bytes at all / wrong profile index /
            # wrong channel count) without needing a terminal.
            self.n_lines = 0
            self.n_w_lines = 0
            self.n_w_matched = 0
            self.n_w_wrong_idx = 0
            self.n_w_wrong_len = 0
            self.n_parse_errors = 0

        def open(self):
            port = self.port_name[5:] if self.port_name.startswith('/dev/') else self.port_name
            self.serial.setPortName(port)
            self.serial.setBaudRate(self.baud)
            self.serial.setDataBits(QSerialPort.DataBits.Data8)
            self.serial.setParity(QSerialPort.Parity.NoParity)
            self.serial.setStopBits(QSerialPort.StopBits.OneStop)
            self.serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
            ok = self.serial.open(QIODevice.OpenModeFlag.ReadWrite)
            if ok:
                self.send('E')
                self.send('V')
                self.send('L')
            else:
                self.error.emit('Could not open {0}'.format(self.port_name))
            return ok

        def load_and_start(self, profile):
            """Loads `profile` onto the board as a RAM-only dynamic profile
            and starts streaming it -- the exact E / D<cmd> / Q<idx> / G
            sequence pimd_classviz.py's "Load and Run" uses. cal_72_air_v2
            is not one of the board's compiled static profiles, so a bare
            Q<n>/G against an arbitrary index either selects the wrong
            (previously-active) profile or nothing at all -- this is why a
            live run must always (re)send the D command, not just Q/G."""
            self._t0_ms = None
            self.active_profile_idx = DYNAMIC_PROFILE_INDEX
            self.send('E')
            self.send(build_d_command(profile))
            self.send('Q{0}'.format(DYNAMIC_PROFILE_INDEX))
            self.send('G')

        def stop_streaming(self):
            self.send('E')

        def close(self):
            if self.serial.isOpen():
                self.send('E')
                self.serial.waitForBytesWritten(100)
                self.serial.close()

        def send(self, text):
            data = (text + '\n').encode()
            n = self.serial.write(data)
            self.serial.waitForBytesWritten(200)
            display = text if len(text) <= 40 else '{0}… ({1} bytes total)'.format(text[:40], len(text))
            if n != len(data):
                self.error.emit('TX short write ({0}/{1} bytes): {2}'.format(n, len(data), display))
            self.command_sent.emit(display)

        def _on_ready_read(self):
            while self.serial.canReadLine():
                raw = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
                if not raw:
                    continue
                self.n_lines += 1
                self.line_received.emit(raw)
                line = raw.replace(', ', ',')
                if len(line) < 2 or line[0] != 'W' or not line[1].isdigit():
                    continue
                self.n_w_lines += 1
                parts = line.split(',')
                try:
                    w_idx = int(parts[0][1:])
                    if w_idx != self.active_profile_idx:
                        self.n_w_wrong_idx += 1
                        continue
                    if len(parts) != 2 + self.n_channels:
                        self.n_w_wrong_len += 1
                        continue
                    t_ms = int(parts[1])
                    frame_uv = np.array([int(parts[2 + i]) for i in range(self.n_channels)], dtype=float)
                except (ValueError, IndexError):
                    self.n_parse_errors += 1
                    self.error.emit('W parse error: {0}'.format(raw))
                    continue
                self.n_w_matched += 1
                if self._t0_ms is None:
                    self._t0_ms = t_ms
                self.frame_ready.emit(FrameRecord(
                    t_seconds=(t_ms - self._t0_ms) / 1000.0, frame_mV=frame_uv / 1000.0,
                    mark_label=None, source_index=t_ms))

        def diag_summary(self):
            return ('rx {0} lines, {1} W-frames ({2} matched, {3} wrong-idx, {4} wrong-len, '
                    '{5} parse-err)').format(self.n_lines, self.n_w_lines, self.n_w_matched,
                                              self.n_w_wrong_idx, self.n_w_wrong_len, self.n_parse_errors)

    class SettingsDialog(QDialog):
        FIELDS = [
            ('baseline_timescale_s', 'Baseline EMA timescale (s)', 1.0, 120.0, 0.5),
            ('bootstrap_air_s', 'Bootstrap air window (s)', 0.0, 60.0, 0.5),
            ('enter_amp_mV', 'Enter threshold (mV)', 0.01, 1000.0, 0.01),
            ('exit_amp_mV', 'Exit threshold (mV)', 0.01, 1000.0, 0.01),
            ('min_duration_s', 'Min duration (s)', 0.0, 30.0, 0.1),
            ('exit_debounce_s', 'Exit debounce (s)', 0.0, 30.0, 0.1),
            ('canary_mv_per_unit', 'Canary unit (mV/u, F11)', 0.001, 1000.0, 0.001),
            ('repeat_floor', 'Repeat floor (1-cos, F15)', 0.0001, 1.0, 0.0001),
            ('k_reject', 'Open-set reject K× floor', 1.0, 100.0, 0.5),
            ('snr_family_gate', 'SNR family gate', 0.1, 100.0, 0.1),
            ('snr_detect_gate', 'SNR detect gate', 0.1, 100.0, 0.1),
        ]

        def __init__(self, settings, parent=None):
            super().__init__(parent)
            self.setWindowTitle('Classify Settings')
            self._settings = settings
            self._spins = {}
            form = QFormLayout()
            for key, label, lo, hi, step in self.FIELDS:
                sb = QDoubleSpinBox()
                sb.setRange(lo, hi)
                sb.setDecimals(4)
                sb.setSingleStep(step)
                sb.setValue(float(settings[key]))
                form.addRow(label, sb)
                self._spins[key] = sb
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                        | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout = QVBoxLayout(self)
            layout.addLayout(form)
            layout.addWidget(buttons)

        def values(self):
            return {k: sb.value() for k, sb in self._spins.items()}

    class MainWindow(QMainWindow):
        def __init__(self, args):
            super().__init__()
            self.setWindowTitle('PIMD Classify v{0} by Mark Makies'.format(APP_VERSION))
            self.args = args
            self.settings = default_settings()
            self.cm_div = _setup_colormaps()

            self.reference_profile = pimd_features.load_reference_profile(args.profile)
            self.corpus_pool = []
            self._load_corpus(args.corpus)

            self.engine = None
            self.sess = None
            self._replay_source = None
            self._replay_iter = None
            self._marks_ranges = []
            self._live_source = None
            self._pending_result = None
            self._current_delta = None
            self._n_channels = sum(len(b['delays_us']) for b in self.reference_profile['bands'])
            self._n_bands = len(self.reference_profile['bands'])
            self._n_cells = self._n_channels // self._n_bands
            self._band_display_order = sorted(
                range(self._n_bands),
                key=lambda i: self.reference_profile['bands'][i]['delays_us'][0], reverse=True)
            self._has_threshold_v = all(
                'threshold_v' in b and len(b['threshold_v']) == self._n_cells
                for b in self.reference_profile['bands'])
            if self._has_threshold_v:
                self._cell_labels = ['{0:.3f}V'.format(v)
                                      for v in self.reference_profile['bands'][0]['threshold_v']]
            else:
                self._cell_labels = ['c{0}'.format(j) for j in range(self._n_cells)]
            self._band_labels_raw = ['{0:,}Hz / {1:.3f}µs'.format(b['freq_hz'], b['pulse_us'])
                                      for b in self.reference_profile['bands']]
            self._display_band_labels = [self._band_labels_raw[i] for i in self._band_display_order]

            self._strip = self._new_strip_buf()

            self._build_ui()
            self._load_settings()

            self._redraw_timer = QTimer(self)
            self._redraw_timer.setInterval(REDRAW_MS)
            self._redraw_timer.timeout.connect(self._redraw)
            self._redraw_timer.start()

            self._replay_timer = QTimer(self)
            self._replay_timer.timeout.connect(self._replay_tick)

        # ------------------------------------------------------------
        # Setup helpers
        # ------------------------------------------------------------
        def _new_strip_buf(self):
            return {'t': [], 'amp': [], 'cont': [], 'cos1': [],
                    'delta_band_means': [], 'baseline_band_means': [], 'cell_raw': []}

        def _load_corpus(self, path):
            try:
                self.corpus_pool = load_corpus_pool(path, self.settings['snr_family_gate'])
            except SystemExit as exc:
                self.corpus_pool = []
                QMessageBox.warning(self, 'Corpus load failed',
                                     'Identity stage disabled:\n{0}'.format(exc))

        # ------------------------------------------------------------
        # UI construction
        # ------------------------------------------------------------
        def _build_ui(self):
            central = QWidget()
            outer = QVBoxLayout(central)

            # --- top bar ---
            top = QHBoxLayout()
            top.addWidget(QLabel('Port:'))
            self.cb_port = QComboBox()
            self.cb_port.setEditable(True)
            for info in QSerialPortInfo.availablePorts():
                self.cb_port.addItem(info.portName())
            top.addWidget(self.cb_port)
            self.pb_connect = QPushButton('Not Connected')
            self.pb_connect.setStyleSheet(MY_YELLOW)
            self.pb_connect.clicked.connect(self._on_connect_clicked)
            top.addWidget(self.pb_connect)
            self.pb_start_live = QPushButton('Start')
            self.pb_start_live.setCheckable(True)
            self.pb_start_live.setEnabled(False)
            self.pb_start_live.setStyleSheet(MY_YELLOW)
            self.pb_start_live.clicked.connect(self._on_start_live_clicked)
            top.addWidget(self.pb_start_live)

            self.pb_load_session = QPushButton('Load Session…')
            self.pb_load_session.clicked.connect(self._on_load_session_clicked)
            top.addWidget(self.pb_load_session)
            self.pb_play = QPushButton('Play')
            self.pb_play.setCheckable(True)
            self.pb_play.setEnabled(False)
            self.pb_play.clicked.connect(self._on_play_clicked)
            top.addWidget(self.pb_play)
            self.cb_speed = QComboBox()
            self.cb_speed.addItems(['x1', 'x5', 'x20', 'max'])
            top.addWidget(self.cb_speed)
            self.sl_seek = QSlider(Qt.Orientation.Horizontal)
            self.sl_seek.setEnabled(False)
            self.sl_seek.sliderMoved.connect(self._on_seek)
            top.addWidget(self.sl_seek, 1)
            self.lbl_time = QLabel('t=0.000s')
            top.addWidget(self.lbl_time)

            self.pb_settings = QPushButton('Settings…')
            self.pb_settings.clicked.connect(self._on_settings_clicked)
            top.addWidget(self.pb_settings)
            outer.addLayout(top)

            top2 = QHBoxLayout()
            self.lbl_profile = QLabel('profile: {0}'.format(self.reference_profile.get('name', '?')))
            top2.addWidget(self.lbl_profile)
            self.lbl_corpus = QLabel('corpus: {0} rows'.format(len(self.corpus_pool)))
            top2.addWidget(self.lbl_corpus)
            self.lbl_state = QLabel('AIR')
            self.lbl_state.setStyleSheet(MY_YELLOW)
            self.lbl_state.setMinimumWidth(100)
            self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top2.addWidget(self.lbl_state)
            self.lbl_amp = QLabel('amp: 0.000 mV (0.000 u)')
            top2.addWidget(self.lbl_amp)
            self.lbl_snr = QLabel('SNR: 0.000')
            top2.addWidget(self.lbl_snr)
            top2.addStretch(1)
            outer.addLayout(top2)

            # --- left: signature panel ---
            left = QWidget()
            left_l = QVBoxLayout(left)
            self.heat_glw = pg.GraphicsLayoutWidget()
            self.heat_plot = self.heat_glw.addPlot()
            self.heat_plot.invertY(True)
            self.heat_img = pg.ImageItem()
            self.heat_plot.addItem(self.heat_img)
            self.heat_img.setColorMap(self.cm_div)
            ax_b = self.heat_plot.getAxis('bottom')
            ax_b.setTicks([[(j + 0.5, self._cell_labels[j]) for j in range(self._n_cells)]])
            ax_b.setLabel('Threshold' if self._has_threshold_v else 'Cell')
            ax_l = self.heat_plot.getAxis('left')
            ax_l.setTicks([[(d + 0.5, self._display_band_labels[d]) for d in range(self._n_bands)]])
            ax_l.setLabel('Band')
            self.heat_plot.setXRange(0, self._n_cells, padding=0)
            self.heat_plot.setYRange(0, self._n_bands, padding=0)
            left_l.addWidget(self.heat_glw, 2)
            heat_row = QHBoxLayout()
            self.pb_heatmap_toggle = QPushButton('Heatmap: current frame (click for event median)')
            self.pb_heatmap_toggle.setCheckable(True)
            self.pb_heatmap_toggle.clicked.connect(self._on_heatmap_toggle)
            heat_row.addWidget(self.pb_heatmap_toggle, 1)
            self.pb_rebaseline = QPushButton('Rebaseline (air)')
            self.pb_rebaseline.setToolTip(
                'Snap the air baseline to the median of recently seen frames right now -- use '
                'while the coil is confidently in air, instead of waiting for the EMA to catch up.')
            self.pb_rebaseline.clicked.connect(self._on_rebaseline_clicked)
            heat_row.addWidget(self.pb_rebaseline)
            left_l.addLayout(heat_row)

            heat_range_row = QHBoxLayout()
            heat_range_row.addWidget(QLabel('Heatmap range (±mV):'))
            self.sp_heat_range = QDoubleSpinBox()
            self.sp_heat_range.setRange(0.1, 100000.0)
            self.sp_heat_range.setDecimals(3)
            self.sp_heat_range.setSingleStep(1.0)
            self.sp_heat_range.setValue(50.0)
            heat_range_row.addWidget(self.sp_heat_range)
            self.cb_heat_autoscale = QCheckBox('Autoscale')
            self.cb_heat_autoscale.setChecked(True)
            heat_range_row.addWidget(self.cb_heat_autoscale)
            heat_range_row.addStretch(1)
            left_l.addLayout(heat_range_row)

            self.band_glw = pg.GraphicsLayoutWidget()
            self.band_plot = self.band_glw.addPlot()
            self.band_plot.setLogMode(x=True, y=False)
            self.band_plot.setLabel('bottom', 'pulse width (µs)')
            self.band_plot.setLabel('left', 'band mean (mV)')
            band_pulses = sorted(set(b['pulse_us'] for b in self.reference_profile['bands']))
            band_ticks = [(math.log10(p), '{0:.3g}'.format(p)) for p in band_pulses]
            self.band_plot.getAxis('bottom').setTicks([band_ticks, []])
            self.band_curve = self.band_plot.plot([], [], pen=pg.mkPen('b', width=2), symbol='o')
            self.band_plot.addLine(y=0, pen=pg.mkPen((150, 150, 150), width=1))
            self.band_cross_marker = pg.ScatterPlotItem(size=12, brush=pg.mkBrush('r'))
            self.band_plot.addItem(self.band_cross_marker)
            left_l.addWidget(self.band_glw, 1)

            band_range_row = QHBoxLayout()
            band_range_row.addWidget(QLabel('Band chart Y range (±mV):'))
            self.sp_band_range = QDoubleSpinBox()
            self.sp_band_range.setRange(0.1, 1000.0)
            self.sp_band_range.setDecimals(3)
            self.sp_band_range.setSingleStep(1.0)
            self.sp_band_range.setValue(10.0)
            band_range_row.addWidget(self.sp_band_range)
            self.cb_band_autoscale = QCheckBox('Autoscale')
            self.cb_band_autoscale.setChecked(False)
            band_range_row.addWidget(self.cb_band_autoscale)
            band_range_row.addStretch(1)
            left_l.addLayout(band_range_row)

            # --- right: verdict panel ---
            right = QWidget()
            right_l = QVBoxLayout(right)
            self.gauge_glw = pg.GraphicsLayoutWidget()
            self.gauge_plot = self.gauge_glw.addPlot()
            self.gauge_plot.setLogMode(x=True, y=False)
            self.gauge_plot.setXRange(math.log10(5.0), math.log10(150.0))
            self.gauge_plot.setYRange(0, 1)
            self.gauge_plot.getAxis('left').setTicks([[]])
            self.gauge_plot.addItem(pg.LinearRegionItem(
                values=(math.log10(5.0), math.log10(7.0)), brush=(255, 120, 120, 80), movable=False))
            self.gauge_plot.addItem(pg.LinearRegionItem(
                values=(math.log10(7.0), math.log10(40.0)), brush=(200, 150, 255, 80), movable=False))
            self.gauge_plot.addItem(pg.LinearRegionItem(
                values=(math.log10(40.0), math.log10(150.0)), brush=(120, 160, 255, 80), movable=False))
            self.gauge_needle = pg.InfiniteLine(pos=math.log10(5.0), angle=90, pen=pg.mkPen('k', width=3))
            self.gauge_plot.addItem(self.gauge_needle)
            right_l.addWidget(self.gauge_glw, 1)

            self.tbl_top3 = QTableWidget(3, 3)
            self.tbl_top3.setHorizontalHeaderLabels(['Target', 'Cosine', 'Distance (×floor)'])
            self.tbl_top3.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            right_l.addWidget(self.tbl_top3)

            self.pb_margin = QProgressBar()
            self.pb_margin.setRange(0, 100)
            self.pb_margin.setFormat('margin: n/a')
            right_l.addWidget(self.pb_margin)

            self.lbl_verdict = QLabel('—')
            self.lbl_verdict.setWordWrap(True)
            right_l.addWidget(self.lbl_verdict)
            right_l.addStretch(1)

            self.top_h_splitter = QSplitter(Qt.Orientation.Horizontal)
            self.top_h_splitter.addWidget(left)
            self.top_h_splitter.addWidget(right)

            # --- bottom: strip charts -- 4 independently-configurable slots.
            # Each slot picks its content from STRIP_MODES; modes in
            # STRIP_NEEDS_BAND (band mean / baseline band mean / per-delay
            # normalized) also read that slot's band combo. Up to n_cells
            # curves are pre-created per slot so "per-delay normalized" can
            # show all 9 at once; unused curves are just fed empty data.
            strip_container = QWidget()
            strip_v = QVBoxLayout(strip_container)
            strip_v.setContentsMargins(0, 0, 0, 0)
            controls_row = QHBoxLayout()
            self._strip_mode_combos = []
            self._strip_band_combos = []
            for i in range(4):
                controls_row.addWidget(QLabel('Chart {0}:'.format(i + 1)))
                mode_cb = QComboBox()
                mode_cb.addItems(STRIP_MODES)
                mode_cb.setCurrentText(STRIP_DEFAULT_MODES[i])
                mode_cb.currentTextChanged.connect(lambda _, idx=i: self._on_strip_mode_changed(idx))
                controls_row.addWidget(mode_cb)
                band_cb = QComboBox()
                band_cb.addItems(self._band_labels_raw)
                band_cb.setCurrentIndex(self._n_bands - 1)
                controls_row.addWidget(band_cb)
                self._strip_mode_combos.append(mode_cb)
                self._strip_band_combos.append(band_cb)
            controls_row.addStretch(1)
            strip_v.addLayout(controls_row)

            self.strip_glw = pg.GraphicsLayoutWidget()
            self._strip_plots = []
            self._strip_curve_sets = []
            pens = [pg.mkPen(pg.intColor(j, hues=max(self._n_cells, 9)), width=1)
                    for j in range(self._n_cells)]
            for i in range(4):
                plot = self.strip_glw.addPlot(row=i, col=0)
                if i > 0:
                    plot.setXLink(self._strip_plots[0])
                if i == 3:
                    plot.setLabel('bottom', 'time (s)')
                curves = [plot.plot([], [], pen=pens[j], connect='finite') for j in range(self._n_cells)]
                self._strip_plots.append(plot)
                self._strip_curve_sets.append(curves)
            self.strip_enter_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('g', style=Qt.PenStyle.DashLine))
            self.strip_exit_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('r', style=Qt.PenStyle.DashLine))
            self._strip_plots[0].addItem(self.strip_enter_line)
            self._strip_plots[0].addItem(self.strip_exit_line)
            for i in range(4):
                self._on_strip_mode_changed(i)
            strip_v.addWidget(self.strip_glw)

            # --- Event Log tab ---
            log_tab = QWidget()
            log_l = QVBoxLayout(log_tab)
            self.tbl_events = QTableWidget(0, 17)
            self.tbl_events.setHorizontalHeaderLabels([
                'id', 't_start', 'duration', 'frames', 'amp_mean', 'amp_peak', 'drift%',
                'SNR', 'crossing_us', 'band8', 'late/early', 'family', 'top3', 'margin',
                'verdict', 'ground_truth', 'hit'])
            self.tbl_events.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.tbl_events.setSortingEnabled(True)
            log_l.addWidget(self.tbl_events)
            exp_row = QHBoxLayout()
            self.pb_export_log = QPushButton('Save event log CSV…')
            self.pb_export_log.clicked.connect(self._export_event_log_csv)
            exp_row.addWidget(self.pb_export_log)
            self.pb_dump_sig = QPushButton('Dump signatures…')
            self.pb_dump_sig.clicked.connect(self._export_signatures_wide)
            exp_row.addWidget(self.pb_dump_sig)
            self.pb_per_frame = QPushButton('Per-frame feature log')
            self.pb_per_frame.setCheckable(True)
            self.pb_per_frame.setStyleSheet(MY_YELLOW)
            self.pb_per_frame.clicked.connect(self._toggle_per_frame_log)
            exp_row.addWidget(self.pb_per_frame)
            self.pb_report = QPushButton('Generate report…')
            self.pb_report.clicked.connect(self._generate_session_report)
            exp_row.addWidget(self.pb_report)
            log_l.addLayout(exp_row)

            self.main_v_splitter = QSplitter(Qt.Orientation.Vertical)
            self.main_v_splitter.addWidget(self.top_h_splitter)
            self.main_v_splitter.addWidget(strip_container)

            monitor_tab = QWidget()
            mon_l = QVBoxLayout(monitor_tab)
            mon_l.addWidget(self.main_v_splitter)

            self.tabs = QTabWidget()
            self.tabs.addTab(monitor_tab, 'Monitor')
            self.tabs.addTab(log_tab, 'Event Log')
            outer.addWidget(self.tabs, 1)

            self.setCentralWidget(central)
            self.statusBar().showMessage('Ready — no auto-connect; use Connect or Load Session')

        # ------------------------------------------------------------
        # Connect / Live
        # ------------------------------------------------------------
        def _on_connect_clicked(self):
            if self.pb_connect.text() != 'Connected':
                self._live_source = LiveFrameSource(
                    self.cb_port.currentText(), active_profile_idx=None, n_channels=self._n_channels)
                self._live_source.frame_ready.connect(self._on_live_frame)
                self._live_source.line_received.connect(self._on_live_line)
                self._live_source.command_sent.connect(
                    lambda text: self.statusBar().showMessage('TX: {0}'.format(text)))
                self._live_source.error.connect(lambda msg: self.statusBar().showMessage('ERROR: {0}'.format(msg)))
                if self._live_source.open():
                    self.pb_connect.setText('Connected')
                    self.pb_connect.setStyleSheet(MY_GREEN)
                    self.pb_start_live.setEnabled(True)
                    self.statusBar().showMessage('Connected — press Start to load cal_72_air_v2 and stream')
                else:
                    self.pb_connect.setText('Port Error')
                    self.pb_connect.setStyleSheet(MY_RED)
            else:
                if self.pb_start_live.isChecked():
                    self.pb_start_live.setChecked(False)
                    self._on_start_live_clicked(False)
                if self._live_source:
                    self._live_source.close()
                    self._live_source = None
                self.pb_connect.setText('Not Connected')
                self.pb_connect.setStyleSheet(MY_YELLOW)
                self.pb_start_live.setEnabled(False)

        def _on_live_line(self, raw):
            # Raw firmware responses (V/L identify/list lines, and any non-W
            # traffic) surfaced to the status bar -- otherwise there is no
            # visible feedback at all that the board is talking back.
            if raw and raw[0] in ('V', 'L'):
                self.statusBar().showMessage('board: {0}'.format(raw))

        def _on_start_live_clicked(self, checked):
            if not self._live_source:
                self.pb_start_live.setChecked(False)
                return
            if checked:
                colmap = colmap_from_profile(self.reference_profile)
                settings = self._collect_settings()
                self.engine = Engine(self.reference_profile, colmap, settings, self.corpus_pool)
                self._live_source.load_and_start(self.reference_profile)
                self.pb_start_live.setText('Running')
                self.pb_start_live.setStyleSheet(MY_GREEN)
                self.statusBar().showMessage(
                    'Streaming {0} (profile pushed via D command, Q{1}) — DESIGN §3: allow ~5 min '
                    'warm-up before trusting data'.format(self.reference_profile.get('name', '?'),
                                                            DYNAMIC_PROFILE_INDEX))
            else:
                self._live_source.stop_streaming()
                self.pb_start_live.setText('Start')
                self.pb_start_live.setStyleSheet(MY_YELLOW)
                self.statusBar().showMessage('Stopped')

        def _on_live_frame(self, rec):
            if self.engine is None:
                return
            self._feed(rec)

        # ------------------------------------------------------------
        # Session load / replay
        # ------------------------------------------------------------
        def _on_load_session_clicked(self):
            path, _ = QFileDialog.getOpenFileName(
                self, 'Load Session', self.settings.get('last_session_dir', ''), 'Session CSV (*.csv)')
            if not path:
                return
            try:
                sess = load_session(path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, 'Load failed', str(exc))
                return
            ok, reason = pimd_features.validate_profile(sess.profile, self.reference_profile)
            if not ok:
                QMessageBox.critical(self, 'Profile mismatch',
                                      'Refusing to load -- profile geometry mismatch:\n{0}\n\n'
                                      '(DESIGN §11 -- never mix profile geometries)'.format(reason))
                return

            self.sess = sess
            self.settings['last_session_dir'] = os.path.dirname(path)
            settings = self._collect_settings()
            self.engine = Engine(sess.profile, sess.colmap, settings, self.corpus_pool)
            frame_rate_hz = pimd_features.measure_frame_rate_hz(sess.t_seconds)
            self._marks_ranges = plateau_time_ranges(sess, frame_rate_hz)
            self._replay_source = ReplayFrameSource(sess)
            self._replay_iter = iter(self._replay_source)
            self._strip = self._new_strip_buf()
            self.tbl_events.setRowCount(0)
            self.sl_seek.setEnabled(True)
            self.sl_seek.setRange(0, len(self._replay_source) - 1)
            self.sl_seek.setValue(0)
            self.pb_play.setEnabled(True)
            self.statusBar().showMessage('Loaded {0} ({1} frames, {2} marks)'.format(
                os.path.basename(path), len(self._replay_source), len(sess.marks)))

        def _on_play_clicked(self, checked):
            if not self._replay_source:
                self.pb_play.setChecked(False)
                return
            if checked:
                self.pb_play.setText('Pause')
                frame_rate_hz = pimd_features.measure_frame_rate_hz(self._replay_source.sess.t_seconds)
                speed_text = self.cb_speed.currentText()
                if speed_text == 'max':
                    self._replay_timer.setInterval(0)
                else:
                    mult = float(speed_text.lstrip('x'))
                    self._replay_timer.setInterval(max(1, int(1000.0 / (frame_rate_hz * mult))))
                self._replay_timer.start()
            else:
                self.pb_play.setText('Play')
                self._replay_timer.stop()

        def _on_seek(self, value):
            # Rebuild the engine from scratch and replay up to `value` -- simplest way to
            # guarantee the causal baseline/detector state is consistent after a seek.
            if not self._replay_source:
                return
            settings = self._collect_settings()
            self.engine = Engine(self.sess.profile, self.sess.colmap, settings, self.corpus_pool)
            self.tbl_events.setRowCount(0)
            self._strip = self._new_strip_buf()
            self._replay_iter = iter(self._replay_source)
            for i, rec in enumerate(self._replay_iter):
                if i > value:
                    break
                self._feed(rec)

        def _replay_tick(self):
            if self._replay_iter is None:
                return
            deadline = time.monotonic() + 0.015   # "max" speed: pump for a fixed time budget, stay responsive
            budget = 50 if self.cb_speed.currentText() == 'max' else 1
            for _ in range(budget):
                rec = next(self._replay_iter, None)
                if rec is None:
                    self._replay_timer.stop()
                    self.pb_play.setChecked(False)
                    self.pb_play.setText('Play')
                    trailing = self.engine.finalize() if self.engine else None
                    if trailing is not None:
                        attach_ground_truth(trailing, self._marks_ranges)
                        self._on_event_closed(trailing)
                    self.statusBar().showMessage('Replay complete')
                    return
                self._feed(rec)
                self.sl_seek.blockSignals(True)
                self.sl_seek.setValue(rec.source_index)
                self.sl_seek.blockSignals(False)
                if time.monotonic() > deadline:
                    break

        # ------------------------------------------------------------
        # Shared pipeline call site — live and replay both funnel here
        # ------------------------------------------------------------
        def _feed(self, rec):
            result = self.engine.process_frame(rec)
            self._pending_result = result
            delta = self.engine.baseline.delta(rec.frame_mV)
            self._current_delta = delta
            cont = math.nan
            cos1 = math.nan
            if result.state in ('CANDIDATE', 'DETECT'):
                feats = self.engine.feature_extractor.extract(delta)
                cont = feats.continuum_us
                if self.engine.identity_clf.corpus_pool:
                    cos1 = max(pimd_corpus_check.cosine(feats.shape, ref)
                               for _, ref in self.engine.identity_clf.corpus_pool)
            self._strip['t'].append(rec.t_seconds)
            self._strip['amp'].append(result.amp_mV)
            self._strip['cont'].append(cont)
            self._strip['cos1'].append(cos1)
            self._strip['delta_band_means'].append(pimd_v2_findings.bandmeans(delta))
            self._strip['baseline_band_means'].append(
                pimd_v2_findings.bandmeans(self.engine.baseline.baseline_mV))
            self._strip['cell_raw'].append(rec.frame_mV)
            self.lbl_time.setText('t={0:.3f}s'.format(rec.t_seconds))
            if result.closed_event is not None:
                attach_ground_truth(result.closed_event, self._marks_ranges)
                self._on_event_closed(result.closed_event)

        # ------------------------------------------------------------
        # Redraw (decoupled from frame arrival, classviz REDRAW_MS pattern)
        # ------------------------------------------------------------
        def _redraw(self):
            if self._live_source is not None and self.pb_start_live.isChecked():
                # Shown independent of whether any frame has actually arrived yet --
                # this is the one place to see "0 lines received at all" vs "frames
                # arriving but filtered" vs "frames arriving and matching" live,
                # without needing a terminal.
                self.statusBar().showMessage(self._live_source.diag_summary())
            if self.engine is None or self._pending_result is None:
                return
            r = self._pending_result
            self.lbl_state.setText(r.state)
            self.lbl_state.setStyleSheet(STATE_LAMP_STYLE.get(r.state, MY_YELLOW))
            self.lbl_amp.setText('amp: {0:.3f} mV ({1:.3f} u)'.format(r.amp_mV, r.amp_units))
            self.lbl_snr.setText('SNR: {0:.3f}'.format(r.snr) if math.isfinite(r.snr) else 'SNR: inf')

            self.strip_enter_line.setValue(self.engine.detector.enter_amp_mV)
            self.strip_exit_line.setValue(self.engine.detector.exit_amp_mV)
            if self._strip['t']:
                self._update_strip_charts()

            if self.pb_heatmap_toggle.isChecked() and self.engine.events:
                delta = self.engine.events[-1].delta_median_mV
                self.pb_heatmap_toggle.setText('Heatmap: last event median (click for current frame)')
            else:
                delta = self._current_delta
                self.pb_heatmap_toggle.setText('Heatmap: current frame (click for event median)')
            if delta is None:
                return   # no frame processed yet -- nothing to draw
            grid = delta.reshape(self.engine.feature_extractor.n_bands, self.engine.feature_extractor.n_cells)
            grid = grid[self._band_display_order, :]
            self.heat_img.setImage(grid.T, autoLevels=False)
            if self.cb_heat_autoscale.isChecked():
                lim = max(1.0, float(np.max(np.abs(grid))) * 1.05)
            else:
                lim = self.sp_heat_range.value()
            self.heat_img.setLevels((-lim, lim))

            band_means = pimd_v2_findings.bandmeans(delta)
            pulses = self.engine.feature_extractor.pulses_us
            self.band_curve.setData(pulses, band_means)
            if self.cb_band_autoscale.isChecked():
                self.band_plot.enableAutoRange(axis='y')
            else:
                rng = self.sp_band_range.value()
                self.band_plot.setYRange(-rng, rng, padding=0)

        def _on_heatmap_toggle(self):
            pass  # state read directly from the checkable button in _redraw()

        def _on_rebaseline_clicked(self):
            if self.engine is None:
                self.statusBar().showMessage('No engine running -- Connect+Start or Load Session first')
                return
            ok = self.engine.request_rebaseline()
            if ok:
                self.statusBar().showMessage(
                    'Rebaselined from {0} recent frames -- confirm the coil was actually in '
                    'air'.format(len(self.engine._raw_frame_history)))
            else:
                self.statusBar().showMessage('No frames seen yet -- nothing to rebaseline from')

        # ------------------------------------------------------------
        # Strip chart slots -- content picked per-slot from STRIP_MODES
        # ------------------------------------------------------------
        def _on_strip_mode_changed(self, idx):
            mode = self._strip_mode_combos[idx].currentText()
            plot = self._strip_plots[idx]
            plot.setLabel('left', STRIP_LABELS.get(mode, mode))
            plot.setLogMode(x=False, y=(mode == 'Amplitude (mV)'))
            self._strip_band_combos[idx].setEnabled(mode in STRIP_NEEDS_BAND)
            if idx == 0:
                # enter/exit threshold lines only mean something on the Amplitude
                # chart, which defaults to slot 0 -- hidden if slot 0 is repurposed.
                show = (mode == 'Amplitude (mV)')
                self.strip_enter_line.setVisible(show)
                self.strip_exit_line.setVisible(show)
            n_used = self._n_cells if mode == 'Per-delay normalized (9 cells)' else 1
            for curve in self._strip_curve_sets[idx][n_used:]:
                curve.setData([], [])

        def _strip_series(self, mode, band_idx):
            """Returns (t, y) for single-curve modes or (t, [y_cell0..y_cell8])
            for 'Per-delay normalized' -- all read from the same self._strip
            history recorded once per frame in _feed(), never recomputed from
            raw frames here."""
            t = self._strip['t']
            if mode == 'Amplitude (mV)':
                return t, [max(v, 1e-6) for v in self._strip['amp']]
            if mode == 'Continuum (µs)':
                return t, self._strip['cont']
            if mode == 'Top-1 cosine':
                return t, self._strip['cos1']
            if mode == 'Band mean (mV)':
                return t, [bm[band_idx] for bm in self._strip['delta_band_means']]
            if mode == 'Baseline band mean (mV)':
                return t, [bm[band_idx] for bm in self._strip['baseline_band_means']]
            if mode == 'Per-delay normalized (9 cells)':
                # Raw (pre-baseline) per-cell reading, not delta -- delta's first
                # sample is always exactly 0 (BaselineTracker.bootstrap() sets the
                # baseline to that very first frame), which would make "normalized
                # to first entry" degenerate. Raw readings start away from zero,
                # so dividing by each cell's own first sample gives 9 curves that
                # all start at 1.0 and separate as each delay cell drifts/responds
                # differently over the session.
                n_cells = self._n_cells
                cols = [[cr[band_idx * n_cells + c] for cr in self._strip['cell_raw']]
                        for c in range(n_cells)]
                norm = [[v / col[0] for v in col] if col and abs(col[0]) > 1e-9 else col
                        for col in cols]
                return t, norm
            return t, []

        def _update_strip_charts(self):
            for i in range(4):
                mode = self._strip_mode_combos[i].currentText()
                band_idx = self._strip_band_combos[i].currentIndex()
                t, series = self._strip_series(mode, band_idx)
                curves = self._strip_curve_sets[i]
                if mode == 'Per-delay normalized (9 cells)':
                    for c in range(self._n_cells):
                        curves[c].setData(t, series[c])
                else:
                    curves[0].setData(t, series)

        # ------------------------------------------------------------
        # Event closed -> verdict panel + event log row
        # ------------------------------------------------------------
        def _on_event_closed(self, e):
            self.lbl_state.setText('CLASSIFIED' if e.identity.mode == 'identified' else
                                    ('UNKNOWN' if e.identity.mode == 'unknown-object' else e.identity.mode.upper()))
            self.lbl_state.setStyleSheet(STATE_LAMP_STYLE.get(
                'CLASSIFIED' if e.identity.mode == 'identified' else 'UNKNOWN', MY_YELLOW))
            self.lbl_verdict.setText('{0}: {1}'.format(e.verdict, e.verdict_reason))
            self.gauge_needle.setValue(math.log10(max(e.features.continuum_us, 5.0)))

            self.tbl_top3.clearContents()
            for row, (label, cos, dist) in enumerate(e.identity.top3[:3]):
                self.tbl_top3.setItem(row, 0, QTableWidgetItem(label))
                self.tbl_top3.setItem(row, 1, QTableWidgetItem(pimd_features.format_value(cos)))
                self.tbl_top3.setItem(row, 2, QTableWidgetItem(pimd_features.format_value(dist)))

            if e.identity.margin_floor is not None and math.isfinite(e.identity.margin_floor):
                self.pb_margin.setValue(int(min(100, max(0, e.identity.margin_floor / (2 * self.engine.identity_clf.k_reject) * 100))))
                self.pb_margin.setFormat('margin: {0:.1f}x floor'.format(e.identity.margin_floor))
            else:
                self.pb_margin.setValue(0)
                self.pb_margin.setFormat('margin: n/a')

            top3_str = '; '.join('{0}:{1:.3f}'.format(l, c) for l, c, _ in e.identity.top3)
            values = [
                str(e.event_id), pimd_features.format_value(e.t_start_s),
                pimd_features.format_value(e.t_end_s - e.t_start_s), str(e.n_frames),
                pimd_features.format_value(e.amp_mean_mV), pimd_features.format_value(e.amp_peak_mV),
                pimd_features.format_value(e.amp_drift_pct), pimd_features.format_value(e.event_snr),
                pimd_features.format_value(e.features.continuum_us), str(e.features.band8_sign),
                pimd_features.format_value(e.features.late_early_ratio), e.family, top3_str,
                pimd_features.format_value(e.identity.margin_floor)
                if e.identity.margin_floor is not None and math.isfinite(e.identity.margin_floor) else '',
                e.verdict, e.ground_truth_label or '', '' if e.hit is None else str(e.hit),
            ]
            # Sorting must be off while a row is being populated -- with it on, Qt
            # can re-sort the table after each individual setItem() call, so the
            # `row` index used by later columns in this loop no longer points at
            # the row being built (it silently lands on whatever row sorted into
            # that slot instead, leaving the new row's later columns blank).
            self.tbl_events.setSortingEnabled(False)
            row = self.tbl_events.rowCount()
            self.tbl_events.insertRow(row)
            for col, v in enumerate(values):
                self.tbl_events.setItem(row, col, QTableWidgetItem(v))
            self.tbl_events.setSortingEnabled(True)

            if self.pb_per_frame.isChecked():
                pass  # per-frame CSV is written incrementally in _feed when enabled — see _toggle_per_frame_log

        # ------------------------------------------------------------
        # Settings dialog
        # ------------------------------------------------------------
        def _collect_settings(self):
            s = dict(self.settings)
            s['profile_path'] = self.args.profile
            s['corpus_path'] = self.args.corpus
            return s

        def _on_settings_clicked(self):
            dlg = SettingsDialog(self.settings, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.settings.update(dlg.values())
                if self.engine is not None:
                    d = self.engine.detector
                    d.enter_amp_mV = self.settings['enter_amp_mV']
                    d.exit_amp_mV = self.settings['exit_amp_mV']
                    d.min_duration_s = self.settings['min_duration_s']
                    d.exit_debounce_s = self.settings['exit_debounce_s']
                    self.engine.baseline.timescale_s = self.settings['baseline_timescale_s']
                    self.engine.bootstrap_air_s = self.settings['bootstrap_air_s']
                    ic = self.engine.identity_clf
                    ic.repeat_floor = self.settings['repeat_floor']
                    ic.k_reject = self.settings['k_reject']
                    ic.snr_family_gate = self.settings['snr_family_gate']
                    ic.snr_detect_gate = self.settings['snr_detect_gate']

        # ------------------------------------------------------------
        # Exports
        # ------------------------------------------------------------
        def _export_event_log_csv(self):
            if self.engine is None or not self.engine.events:
                QMessageBox.information(self, 'Nothing to export', 'No closed events yet.')
                return
            path, _ = QFileDialog.getSaveFileName(
                self, 'Save event log CSV', self.settings.get('last_export_dir', ''), 'CSV (*.csv)')
            if path:
                write_event_log_csv(path, self.engine.events)
                self.settings['last_export_dir'] = os.path.dirname(path)

        def _export_signatures_wide(self):
            if self.engine is None or not self.engine.events or self.sess is None:
                QMessageBox.information(self, 'Nothing to export',
                                         'Dump signatures needs a loaded session and closed events '
                                         '(live-captured events have no session to attribute to yet).')
                return
            path, _ = QFileDialog.getSaveFileName(
                self, 'Dump signatures', self.settings.get('last_export_dir', ''), 'CSV (*.csv)')
            if path:
                write_wide_signatures(path, self.sess, self.engine.events, self.reference_profile)
                self.settings['last_export_dir'] = os.path.dirname(path)

        def _toggle_per_frame_log(self, checked):
            if checked:
                self.pb_per_frame.setStyleSheet(MY_RED)
                path, _ = QFileDialog.getSaveFileName(
                    self, 'Per-frame feature log', self.settings.get('last_export_dir', ''), 'CSV (*.csv)')
                if not path:
                    self.pb_per_frame.setChecked(False)
                    self.pb_per_frame.setStyleSheet(MY_YELLOW)
                    return
                self._per_frame_fh = open(path, 'w')
                self._per_frame_fh.write('time_ms,amp_mV,snr,continuum_us,top1_cosine,'
                                          + ','.join('band_mean_{0}'.format(i) for i in range(self._n_bands))
                                          + '\n')
            else:
                self.pb_per_frame.setStyleSheet(MY_YELLOW)
                if hasattr(self, '_per_frame_fh') and self._per_frame_fh:
                    self._per_frame_fh.close()
                    self._per_frame_fh = None

        def _generate_session_report(self):
            if self.engine is None or not self.engine.events:
                QMessageBox.information(self, 'Nothing to report', 'No closed events yet.')
                return
            path, _ = QFileDialog.getSaveFileName(
                self, 'Session report', self.settings.get('last_export_dir', ''), 'PNG (*.png)')
            if not path:
                return
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            events = self.engine.events
            n = len(events)
            fig, axes = plt.subplots(1 + (n + 7) // 8, 8, figsize=(16, 2.2 * (1 + (n + 7) // 8)))
            axes = np.atleast_2d(axes)
            for i, e in enumerate(events):
                ax = axes[i // 8, i % 8]
                grid = e.delta_median_mV.reshape(self.engine.feature_extractor.n_bands,
                                                  self.engine.feature_extractor.n_cells)
                lim = max(1.0, float(np.max(np.abs(grid))))
                ax.imshow(grid, cmap='RdBu_r', vmin=-lim, vmax=lim, aspect='auto')
                ax.set_title('#{0} {1}'.format(e.event_id, e.verdict), fontsize=7)
                ax.set_xticks([]); ax.set_yticks([])
            for i in range(n, axes.size):
                axes[i // 8, i % 8].axis('off')
            fig.suptitle('PIMD Classify session report — {0} events'.format(n))
            fig.tight_layout()
            fig.savefig(path, dpi=120)
            plt.close(fig)
            md_path = os.path.splitext(path)[0] + '.md'
            with open(md_path, 'w') as f:
                f.write('# Session report\n\n')
                f.write('| id | t_start | family | verdict | ground_truth | hit |\n|---|---|---|---|---|---|\n')
                for e in events:
                    f.write('| {0} | {1:.3f} | {2} | {3} | {4} | {5} |\n'.format(
                        e.event_id, e.t_start_s, e.family, e.verdict,
                        e.ground_truth_label or '', '' if e.hit is None else e.hit))
            self.statusBar().showMessage('Report written to {0}'.format(path))

        # ------------------------------------------------------------
        # Settings persistence
        # ------------------------------------------------------------
        def _load_settings(self):
            try:
                with open(SETTINGS_PATH) as f:
                    s = json.load(f)
                self.settings.update(s)
                self.cb_port.setEditText(self.settings.get('port', DEFAULT_PORT))
                self.sp_band_range.setValue(float(self.settings.get('band_range_mV', 10.0)))
                self.cb_band_autoscale.setChecked(bool(self.settings.get('band_autoscale', False)))
                self.sp_heat_range.setValue(float(self.settings.get('heatmap_range_mV', 50.0)))
                self.cb_heat_autoscale.setChecked(bool(self.settings.get('heatmap_autoscale', True)))
                strip_modes = self.settings.get('strip_modes', STRIP_DEFAULT_MODES)
                strip_bands = self.settings.get('strip_bands', [-1, -1, -1, -1])
                for i in range(4):
                    mode = strip_modes[i] if i < len(strip_modes) else STRIP_DEFAULT_MODES[i]
                    if mode in STRIP_MODES:
                        self._strip_mode_combos[i].setCurrentText(mode)
                    band = strip_bands[i] if i < len(strip_bands) else -1
                    band = self._n_bands - 1 if band < 0 or band >= self._n_bands else band
                    self._strip_band_combos[i].setCurrentIndex(band)
                w = int(self.settings.get('window_w', 1600))
                h = int(self.settings.get('window_h', 1000))
                self.resize(w, h)
                x, y = self.settings.get('window_x'), self.settings.get('window_y')
                if x is not None and y is not None:
                    self.move(int(x), int(y))
                top_sizes = self.settings.get('top_h_splitter')
                if top_sizes and len(top_sizes) == 2:
                    QTimer.singleShot(0, lambda: self.top_h_splitter.setSizes([int(v) for v in top_sizes]))
                main_sizes = self.settings.get('main_v_splitter')
                if main_sizes and len(main_sizes) == 2:
                    QTimer.singleShot(0, lambda: self.main_v_splitter.setSizes([int(v) for v in main_sizes]))
            except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
                self.resize(1600, 1000)

        def _save_settings(self):
            self.settings['port'] = self.cb_port.currentText()
            self.settings['band_range_mV'] = self.sp_band_range.value()
            self.settings['band_autoscale'] = self.cb_band_autoscale.isChecked()
            self.settings['heatmap_range_mV'] = self.sp_heat_range.value()
            self.settings['heatmap_autoscale'] = self.cb_heat_autoscale.isChecked()
            self.settings['strip_modes'] = [cb.currentText() for cb in self._strip_mode_combos]
            self.settings['strip_bands'] = [cb.currentIndex() for cb in self._strip_band_combos]
            self.settings['window_w'] = self.width()
            self.settings['window_h'] = self.height()
            self.settings['window_x'] = self.x()
            self.settings['window_y'] = self.y()
            self.settings['top_h_splitter'] = self.top_h_splitter.sizes()
            self.settings['main_v_splitter'] = self.main_v_splitter.sizes()
            try:
                os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
                with open(SETTINGS_PATH, 'w') as f:
                    json.dump(self.settings, f, indent=2)
            except OSError:
                pass

        def closeEvent(self, event):
            self._save_settings()
            if self._live_source:
                self._live_source.close()
            super().closeEvent(event)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(args)
    window.show()
    return app.exec()


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(
        description='PIMD Classify -- Mode 2 live/replay signature classifier (DESIGN §9/§10/§11).')
    p.add_argument('--headless', metavar='SESSION.csv', default=None,
                    help='Run the shared pipeline over a recorded session with no GUI, print the '
                         'event log, and exit (no PyQt6/pyqtgraph import in this mode).')
    p.add_argument('--profile', default=pimd_features.DEFAULT_PROFILE,
                    help='Reference profile JSON for the geometry guard (default: cal_72_air_v2.json).')
    p.add_argument('--corpus', default=DEFAULT_CORPUS,
                    help='Corpus CSV for the identity classifier (default: ML/V2 campaign-2 corpus).')
    p.add_argument('--settings', default=SETTINGS_PATH,
                    help='Settings JSON overriding built-in defaults (default: {0}).'.format(SETTINGS_PATH))
    p.add_argument('--dump-signatures', metavar='OUT.csv', default=None,
                    help='(--headless only) Write closed events as a wide-format signatures CSV.')
    p.add_argument('--export-event-log', metavar='OUT.csv', default=None,
                    help='(--headless only) Write the full event log CSV.')
    p.add_argument('--speed', type=float, default=None,
                    help='(--headless only, test aid) Sleep this many seconds between process_frame() '
                         'calls -- never touches the timestamps fed to the pipeline, so this proves '
                         'replay speed cannot change event decisions.')
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    if args.headless:
        sys.exit(run_headless(args))
    else:
        sys.exit(run_gui(args))


if __name__ == '__main__':
    main()
