### .gitignore — KiCad auto-backup zips are ignored

`Electronics/**/*-backups/` — KiCad writes a timestamped zip into `<project>-backups/` every time the
schematic is opened, and they were accumulating as untracked noise in `git status`. The rule is
directory-scoped and does not touch the 11 tracked sources in `Electronics/PIMD604/`. (2026-08-10)

---

### profile — `cal_3x10_v3` — the skip is gone; a geometric ladder replaces it, and the model says the slow pole belongs to the target

**Not locked, not swept, nothing captured against it.** The operator fixed the **first and last delay
in each band by hand**; the 8 interior delays are filled in here as a **geometric ladder** between
them — constant ratio **1.3296 / 1.2762 / 1.1836** per band — snapped to the 8 ns PWM grid. Every
cell is strictly increasing and passes the firmware's `pulse_duties_valid()` check. Geometry stays
3 × 10 = 30.

| band | delays (µs) |
|---|---|
| 100 µs @ 3.125 kHz | 9.24 · 12.288 · 16.336 · 21.72 · 28.88 · 38.4 · 51.048 · 67.88 · 90.256 · 120.0 |
| 50 µs @ 5 kHz | 8.352 · 10.656 · 13.6 · 17.36 · 22.152 · 28.272 · 36.08 · 46.048 · 58.768 · 75.0 |
| 10 µs @ 25 kHz | 6.36 · 7.528 · 8.912 · 10.544 · 12.48 · 14.776 · 17.488 · 20.696 · 24.504 · 29.0 |

**The skip spans are deliberately gone** — with the +97 mV bias fitted no cell is excluded for
railing, so the constraint that shaped `cal_3x10_v2` no longer exists.

**Geometric was chosen after an information-weighted placement was tried and rejected.** Equal arc
length along the three targets' combined log-signature put **nine of ten cells below 18 µs** and left
a 6.5× gap to the fixed 120 µs endpoint, because log-space arc length is dominated by the steep early
fall. Constant ratio gives equal resolution per decade of delay, which is the same principle as the
retired ×1.5 pulse ladder, applied to delays.

**`threshold_v` is carried over from v2 UNCHANGED, and that is deliberate.** It is no longer a
voltage in any sense — nothing was swept — but it is the **cell ordering key**: `pimd_shape` and
`pimd_corpus_check` both sort rows by `(pulse_us, -threshold_v)`, and `pimd_rawlog` already calls the
field vestigial. Writing modelled air voltages there would have been **non-monotonic through the
null** and would have scrambled cell order. The profile's `notes` now says this in the file itself.

**Model fits over the measured window** *(2026-08-10 captures, fitted in log space)*. **Air and brass
need only a single repeated pole** — the free two-pole fit drives τ_fast → τ_slow, and
`(P + Q·t)·e^(−t/τ)` fits identically well. **Steel on the two long bands needs a genuine second,
slow pole, and that is the target's own eddy decay:**

| band | air | brass | steel |
|---|---|---|---|
| 100 µs | τ 1.96 µs · ±5.6 mV | τ 1.79 µs · ±8.5 mV | τf 1.24, **τs 19.0 µs** · ±6.0 mV |
| 50 µs | τ 1.89 µs · ±6.8 mV | τ 1.77 µs · ±8.4 mV | τf 1.18, **τs 23.4 µs** · ±8.7 mV |
| 10 µs | τ 1.78 µs · ±13.4 mV | τ 1.76 µs · ±13.2 mV | τ 1.67 µs · ±12.4 mV |

**The slow pole appears only when a ferrous target is present, and it vanishes again on the 10 µs
band** — a 10 µs pulse barely excites it. That is the same conclusion the fill fractions reached by a
different route (steel filled only 62 % of the null at 10 µs), which is worth something as
corroboration. *Caveat on the fast pole: every capture starts at ~9–12 µs because the window
saturates below that, so a ~1.2 µs pole is far outside the data and **τ_fast is not independently
identifiable here** — treat it as a fitted shape parameter, not a measurement.*

**Three reasons this must not be locked yet:**

1. **Only two cells sit inside the measured polarity window** on the 100 µs band (9.24 and 12.288,
   against §2's 7.97–12.30) where `cal_3x10_v2` had six. Geometric spacing buys tail resolution and
   sells early density. **If the ferrous/non-ferrous sign split matters more than decay-rate
   resolution, this ladder is weighted the wrong way** and wants re-cutting.
2. **Several cells are placed beyond any measurement** — 67.88 / 90.256 / 120 µs (100 µs band),
   58.768 / 75 (50 µs), 29.0 (10 µs). The scope record stops at 55.5 µs.
3. **The first cells of every band sit inside the saturated region** and are unverified. One capture
   per band at a coarser vertical (500 mV/div or 1 V/div) closes this and item 1 together.

`References/images/bias_mod_delay_plot_20260810.png` is the delay plot for this profile — the same
three bands with the fitted models overlaid dotted, so the fit quality is visible rather than
asserted. (2026-08-10)

---

### findings — the bias mod is fitted and the null is real, discriminating signal

**Plan A is built and it works.** 240 k from 5V-REF into U3A pin 3, as specified in the proposal
below. Bench session 2026-08-10, `pimd_gui` Mode 1, scope on the LT6203 input (CH1) with MCLK on CH2
as the sample-instant reference, 64 averages, all three bands, air / RHS steel tube / brass block at
**0 cm** — pressed as close to the inner coil as possible to maximise swing. Nine traces and the
plotting script are in `References/scope/20260810_bias_mod/`; the figure is
`References/images/bias_mod_delay_plot_20260810.png`.

**The design number was met.** The operator had already centred CH1 at **+112.8 mV** before the
session began; the proposal predicted a biased quiescent of **+111.7 mV**. The timing chain also
checked itself: the capture assumed scope t = 0 was sd 15.504 µs and the CH2 rising edge landed at
**15.512** — one 8 ns PWM grid step.

**Air never goes below 67.2 mV** (worst case, 100 µs band), against the old 2.441 mV output floor.
Every cell in the previously-railed window, on all three bands, is now live signal with ≥ 65 mV of
headroom underneath it.

| band | air null bottom | depth below quiescent |
|---|---|---|
| 100 µs @ 3.125 kHz | 67.2 mV at **sd 17.52 µs** | 38.2 mV |
| 50 µs @ 5 kHz | 75.0 mV at **sd 16.10 µs** | 33.7 mV |
| 10 µs @ 25 kHz | 84.5 mV at **sd 13.99 µs** | 30.3 mV |

***This retires the "amplitude-invariant crossing" argument in the entry below.*** That entry
separated an amplitude-invariant zero crossing from an amplitude-dependent rail crossing, and
concluded the null's *timing* was fixed across bands. **Measured, the null bottom itself moves
1.4 µs between 100 µs and 50 µs, and 3.5 µs across the full band set.** The reasoning was incomplete:
pulse width changes the **initial conditions** — how much energy sits in L versus C at release — so
the ratio of the two mode amplitudes changes and `ln(A/B)` moves with it. What survives is the
conclusion the operator's bench edges were right about: the window is band-dependent, and the
per-band brackets in `cal_3x10_v2` were tracking a real shift in the feature.

**Sign is not the discriminant inside the null — fill depth is.** Both families read *positive*
against air there, because air is the thing that dips and both targets fill the dip in. Defining
**fill = 1 − (target dip depth / air dip depth)**, depths taken against each trace's own late level:

| band | brass fill | steel fill |
|---|---|---|
| 100 µs | 52 % | **100 %** — monotonic, no dip at all |
| 50 µs | 38 % | **100 %** — monotonic |
| 10 µs | **8 %** | 62 % |

The two families are **7× apart on the shortest pulse and 2× on the longest**. Note the metric
saturates at 100 %, so the 100/50 µs steel figures are floors rather than measurements. This is a τ
probe read through the null rather than through amplitude — a third mechanism alongside the polarity
split and the late-tail decay rate.

**Both mechanisms are visible in one trace now.** Brass crosses from negative to positive against
air at **~12.3 µs** on the 50 µs band and **~11.7 µs** on the 10 µs band; below that it is the
classic sign split (§2), above it, fill. The crossover marches earlier with shorter pulse, same as
everything else here.

**The case for keeping these cells is SNR, not novelty.** The steel:brass magnitude ratio through
the null is **6–8× on every band** — but out on the tail at sd 30 µs it is 5.8×, i.e. much the same
discrimination. What differs is amplitude: **Δsteel is +187 mV at sd 17.5 against +78 mV at sd 30**,
for a noise floor that does not change with delay. These are the best-SNR cells in the profile.

**Two things only visible when the traces are read cell-by-cell through the null** *(sampled at the
null bottom ±3 µs; reproducible from the CSVs)*:

- **On the 10 µs band brass and air are 3–5 mV apart across the whole null**, against a 12–13 mV fit
  RMS on that band. That is at or below the noise, so **the 10 µs band contributes essentially
  nothing to non-ferrous discrimination in the null** — the 7× fill ratio quoted above is carried by
  the ferrous side alone.
- **Past the bottom, steel's slope is opposite to air's and brass's.** On the 100 µs band air and
  brass recover (67 → 91 mV, 94 → 111 mV over the following 4 µs) while steel keeps falling
  (254 → 223 mV). **The sign of the slope is a cleaner discriminator than the levels**, and reading
  it needs at least two cells past each band's null bottom — a placement constraint that no other
  finding here implies.

**Three things this session did not settle, and the first is load-bearing:**

1. **Everything here is at 0 cm.** Coupling dominates, and a feature that only exists on contact is
   not corpus material. One repeat at 50 mm on the 100 µs band answers it, and **nothing should be
   captured against a filled-in profile until it is answered.**
2. **The top of the decay is unverified.** Everything moved up ~97 mV and the 4.85 V cell now sits
   near 4.95 V against 5.000 V full scale. The scope window clipped above 1.4 V, so this needs a
   delaycal sweep or a coarse capture.
3. **All pre-mod scope values are void.** Air's dip went 29.3 → 38.2 mV, and the bias cannot deepen
   it — a 240 k shunt attenuates ~2 %, which would make it shallower. **The replaced 7815 is the
   likely cause**, which means §7's measured front-end values need re-taking on their own account,
   independently of the bias. (2026-08-10)

---

### hardware — proposal — bias the RX front end ~97 mV so the null stops being thrown away

**Not built. Operator has chosen Plan A; this entry is the record of the design and the acceptance
test, written before anything is soldered.** The motivation is the finding below: the null is real
coil physics, it responds to metal, and `cal_3x10_v2` deals with it by refusing to sample there. If
the region can be lifted into the linear window instead, it is corpus material rather than a hole.

**The mechanism is a single-supply floor, not a fault.** U3A is a unity-gain follower on +12 V and
its output cannot go below ~2.441 mV, so air's excursion below quiescent is clipped. Lifting the DC
operating point at pin 3 lifts the whole transient clear of that floor. **Plan A is one resistor,
no track cuts, fully reversible:**

```
U5 pin 7 (5V-REF) ──[ 240k, 1 % metal film ]──► U3A pin 3
```

Pin 3's DC path to ground is `R8 + R9 + RX coil` ≈ **4.77 kΩ** (the coil's 19.9 Ω shorts out R1's
1304 Ω, so R1 barely features), giving 5.0 × 4770/244770 = **97.4 mV**. Measure R_gnd at pin 3
unpowered and re-derive from `Rb = R_gnd × (5.0 / V_offset − 1)`; the result is insensitive to it.

**~97 mV is the right target, not a round number.** Air bottoms 29.3 mV below quiescent, but air is
not the worst case — the largest measured non-ferrous excursion is −74.4 mV at the ADC, ≈ −65 mV at
the input, so worst-case depth below quiescent is ≈ 94 mV. 50 mV would clip the strong non-ferrous
targets that are the whole point.

***Corrected during the design:*** an earlier sketch split the bias into 2 × 120 k with 100 nF at
the midpoint and called the signal-node loading 2.5 %. **Both parts were wrong.** With the cap at
the midpoint the node sees 120 k against `R9 + R8` = 4.747 kΩ, which is **3.8 %** attenuation; a
single 240 k sees 240 k against the same, **1.9 %**. The LTC6655 is quiet enough not to need the RC,
so the single resistor is preferred — fewer parts, half the signal loss, easier to remove.

**Take the bias from 5V-REF, not +5V or +12V.** That net is the ADC's own reference, so offset and
full scale drift together and the code does not move. Use metal film: the new thermal term is
`97 mV × divider tempco`, ~2.5 µV/°C at 25 ppm/°C (invisible) but ~300 µV over a 30 °C soak at
100 ppm/°C, which is at the noise floor on a project whose first open problem is thermal drift.

**Acceptance test — re-run the 2026-08-08 scope capture at the LT6203 input with the bias fitted:**

| | before | predicted after |
|---|---|---|
| air quiescent | +14.34 mV | **+111.7 mV** |
| air lobe bottom | −15 mV | **+82.4 mV** |
| worst-case non-ferrous (−65 mV at input) | below the floor | **+32.4 mV** |
| input-referred output floor | 2.12 mV | unchanged |

The pass condition is the strongest non-ferrous target at closest coupling staying above ~2 mV at
the input.

**What it costs, and it is not small.** **LTC2508 pin 6 (IN−) is grounded** *(operator confirmed)*,
so the ADC reads `IN+ − 0` and the bias appears in the data: every `threshold_v` in the ladder
moves, the pedestal goes ~16.5 → ~113 mV, and this is **a new profile, a new sha and a new
measurement epoch**. Top-end headroom also tightens — the 4.85 V cell becomes 4.947 V against
5.000 V full scale, 53 mV of margin — so re-anchor the top early cell to ~4.70 V at recalibration.

**Timing, which is the decision that actually matters.** A corpus run was imminent. Capturing 30
cells now and then fitting this resistor means capturing twice, because nothing before the mod is
mergeable with anything after it. **Fit, scope-check, then decide** whether the profile becomes
3 × 10 with the middle filled in or stays as it is.

**Plan C, recorded but not chosen.** The spare half of the same physical DIP-8 (sheet 2's `U18B` —
sheet 2's designators are known wrong, and its pin 7 lands on TP24) could buffer the same bias onto
the ADC's IN−, making the offset cancel differentially: the ladder would stay valid, only the newly
visible middle would need sweeping, and drift would be common-mode. It costs three cuts —
`R80`/`R82` links out, IN− lifted from GND, RX cold end floated onto V_b. **If Plan A shows real
discrimination information in the null, build Plan C before capturing**, because Plan A as a
permanent fitting spends an epoch for no reason.

**Open before anything is cut:** whether R1 is through-hole (Plan C lifts its ground leg), and D3's
reverse leakage once permanently back-biased by ~100 mV — Schottky leakage roughly doubles per
10 °C, and a few hundred nA through R9's 4.7 kΩ at the 54.8 °C board temperature is a few mV of
temperature-dependent error. Probably lost in the noise; worth a bench look, not an assumption.

**R1 is untouched, so ζ = 1.06 is unchanged, and no §11 invariant is involved.** No firmware change.
(2026-08-10)

---

### findings — the below-rail window is band-dependent, and §7's single figure is a 100 µs number

**Operator bench result: the rail window shifts and widens with band energy.** The edges of each
band's skipped span were tuned by hand — nudging the bracketing cell's delay until it climbs off the
**~2.4 mV** rail onto the **~16.5 mV** pedestal — **independently per band, not derived from the
scope capture.** Read off the lock, the brackets are:

| band | last clean early cell | first clean late cell |
|---|---|---|
| 100 µs @ 3.125 kHz | 13.0 µs | 30.0 µs |
| 50 µs @ 5 kHz | 12.352 µs | 24.0 µs |
| 10 µs @ 25 kHz | 10.36 µs | 18.44 µs |

**The mechanism is consistent with §7's two-pole model, and it is worth separating two things that
had been conflated.** The *zero crossing* is amplitude-invariant: it sits at
`ln(A/B) / (1/τ_f − 1/τ_s)`, and driving harder scales both residues together so `ln(A/B)` does not
move. But **the rail is not zero — it is a fixed 2.441 mV floor**, and where a curve crosses a fixed
threshold depends on its depth. The lobe's depth scales with band energy, so a deeper lobe crosses
the floor earlier and climbs out later. Same null, different below-rail window. That is exactly the
ordering the bench found.

**So §7's `sd 14.23–18.44` is a 100 µs / 2 kHz figure, not a global constant**, and the sentence
"any new profile must clear sd 14.23–18.44" over-generalises a single-condition reconstruction to
all three bands. Worth rescoping at the next consolidation pass. Note also that pack voltage scales
the decay (§12), so these crossings drift with state of charge within a session — the brackets are
a bench-tuned centre, not a hard edge.

***Correction to the `cal_3x10_v2` entry below:*** that entry moved the 10 µs band's first late cell
**18.0 → 18.44 µs** on the grounds that 18.0 "may still be inside the rail", reading the 100 µs
band's reconstructed rail exit as if it applied to the 10 µs band. **It does not** — the 10 µs band
has the shallowest lobe and therefore the *earliest* rail exit of the three, so 18.0 was already
clear, which is the operator's assessment from the independent bench tuning. **The stated
justification for v2 is withdrawn.** The move itself is harmless — 18.44 is on the 8 ns grid,
validates clean, and 0.44 µs later on the pedestal costs nothing measurable — so **`cal_3x10_v2`
stands as the lock** rather than churning a v3 for no gain, and no corpus exists against either
version. What is retired is the reasoning, not the file.

The pattern is the same one the v2 entry itself called out an hour after writing it: **a
single-condition measurement quietly applied outside the condition it was taken in.** First time it
was a placeholder column read as data; this time it is one band's rail exit read as every band's.

`References/images/profile_3x10_timing.png` is redrawn accordingly — the shaded window is a wedge
following the per-band brackets rather than one rectangle across all three lanes. (2026-08-10)

---

### References/images — `profile_3x10_timing.png`, the sample-timing map for `cal_3x10_v2`

A figure for the blog, tracked here because it is also the clearest single picture of the operating
geometry. Three lanes, one per band, on a log delay axis: the six amplitude-anchored early cells,
the four time-anchored late cells, and the below-rail window shaded across all three — which lands
in the gap in every lane, because that is what the profile exists to do (§7, §10). *(Superseded on
the same day by the findings entry above: the window is drawn as a per-band wedge, not as a single
rectangle, and the 10 µs band's annotation is corrected.)*

**The delays are read from `src/data/profiles/cal_3x10_v2.json` at render time, not transcribed**,
so the figure cannot drift from the lock it describes; only the rail bounds are hard-coded, from §7.
The generator is a one-off and deliberately **not** in the repo — `utilities/` was retired at the
epoch turnover and `src/*.py` is live tool source, so a throwaway figure script belongs in neither.
Regenerating it means rewriting it, which is the right cost for something this small. (2026-08-10)

---

### DESIGN.md / .gitignore — Doc-rev 1.15.7 — content already carried by CHANGELOG.md is cut, and the superseded profiles come back into the repo

Operator trim, plus repair of the artefacts it left. No new bench data.

**Cut from DESIGN.md as duplicated history rather than current design fact:** §12's U1 dissipation
cost bullet (≈ 2.5 W → ≈ 4.6 W across the discharge) and its ADC error-budget RSS bullet (≈ 92 mV
pack-referred, ≈ 53 mV available ratiometrically off the LTC6655, identified not built); the
standing caution about regulated-window claims taken over a narrow interval; the retired
`cal_63_air_bat_v3` 21.5–23.3 V data-quality window with its 22.5–24.0 V transition band; the
idle-drain-vs-streaming 15× and session-planning arithmetic, and the ≈ 0.29 V measured IR drop; the
"highest-value unmade measurement" note (the +15 V rail under scope during a TX pulse, fresh pack vs
near-flat); §13's footnote on what retired with the 63-cell epoch; §14 open problems 8–12 (threshold
noise zone, classification-layer rebuild, the `Sn_Pb_solder_spool_01` id collision, the missing
within-placement quality gate, fw v4.34's outstanding bench acceptance); and §16's recalibration
procedure. **All of it is in this file — the findings stand, and none of them are withdrawn.**

**Four consequences of the cut are repaired.** The `---` rule before §14 had been left as `--`, so
it rendered as text. Two stray spaces went (`*(measured)*. ` and `pedestal** .`), as did a doubled
blank line in §12. The §14.8 / §14.9 / §16 cross-references pointed at sections that no longer
exist — each is dropped rather than left dangling, with the substance it pointed at stated in place:
delaycal's §15 row now says *why* Import Profile comes first (persisted settings are not anchored to
the locked profile, so a stale baseline is inherited, band plan included) instead of pointing at the
deleted procedure.

**1.15.6's own text no longer described the file.** It stated that two enclosure references were
deliberately kept, one being §12's note that the dissipation is trapped inside a sealed enclosure —
that bullet is one of the ones cut here, so the Hardware rev line is now the only enclosure
reference and the Doc-rev block says so.

**All six superseded calibration profiles are restored to the repo** — `cal_3x10_v1`,
`cal_63_air_bat_v3`, `cal_63_air_v1`, `cal_63_air_v2`, `cal_72_air_v2`, `cal_72_air_v3` — recovered
from git history, where each had been untracked at its retirement. **This reverses the
track-by-exception convention:** `.gitignore` no longer carries a per-lock retirement list, so it is
no longer the authoritative record of which locks are retired (1.15.5 relied on it for exactly
that), and a retired lock can no longer be lost by a working-copy accident. §15's profiles row is
rewritten to match. `.gitignore` also loses rules for `REDO.md` and `assets`, neither of which
exists. (2026-08-10)

---

### DESIGN.md — Doc-rev 1.15.6 — the 2026-07-13 enclosure is no longer a measurement epoch

**Operator assessment: fitting the shielded enclosure did not materially move what was being
measured at the time.** All "pre-enclosure" staleness framing is removed from DESIGN.md
accordingly — §3's flyback, RX front-end node voltages, sample-timing precision and thermal drift
now stand as current rather than as historical reference awaiting re-measurement.

**The 2026-07-13 epoch row survives, re-attributed.** That date bundled two changes, and only one of
them is being retired as a reset: **fw v4.24 made Mode 2 boundary settling time-floored**, which
genuinely voided Mode 2 per-cell values and delay tables (§8 — it was the root cause of the
first-heatmap-column noise). The enclosure went on the same day and rode along in the framing. §1's
table now names fw v4.24 as the reason and drops the enclosure from it.

**Two enclosure references are deliberately kept, because they are build facts rather than staleness
claims:** the Hardware rev line, and §12's note that the doubled U1 dissipation sits **inside a
sealed shielded enclosure** on a project whose first open problem is thermal drift. That last one is
the one place the enclosure does bite, and it is a live concern, not a stale measurement.

**§12's supply-noise table keeps its caveat, on the other reason.** Those rows were taken on the
**5S** pack that the 6S supply replaced — a different supply, a real and specific reason to
distrust them — so "5S / pre-enclosure, stale on both counts" becomes simply 5S. §14.2 is retitled
from "Post-enclosure / post-6S re-measurement backlog" to "Re-measurement backlog" and rescoped: the
unreconciled ±200 µV / ±450 µV filtered-path pair stays its first item, now on the grounds that
neither has been measured on current hardware rather than on epoch grounds.

**The Doc-rev block is compressed from ~57 lines to a terse lineage**, matching the one-line-per-
version header convention `CLAUDE.md` sets for source files. It had accreted six stacked revisions
of prose — including archaeology about a tagging scheme that no longer exists — which is the
accretion §18 exists to prevent. Full detail for every rev is in this file. (2026-08-09)

---

### DESIGN.md — Doc-rev 1.15.5 — §10 epoch ledger dropped; §3's per-value epoch tags become one sentence

Operator trim, plus repair of two artefacts that came with it. No new bench data.

**Dropped from §10:** the epoch-ledger table of superseded profiles, and the 63-cell / 45-cell rows
of the sweep-rate table. A retired profile's lineage belongs in this file and in git history, not in
the working brief; `.gitignore` remains the authoritative list of which locks are retired, and every
superseded JSON is still on disk and still usable as a delaycal comparison reference. **Verified
before removing the pointer:** all four sha8s — `4a2352d2`, `89590f69`, `b4bee9d2`, `def96704` — are
present in this file, so nothing became unfindable.

**Changed in §3:** the per-value `[pre-enclosure]` tags are replaced by a single statement in the
section banner naming the five pre-enclosure quantities (flyback, RX front-end node voltages,
sample-timing precision, thermal drift, and the on-slope noise row). Same information, less markup.
This mattered because the tags had been removed while the banner still *defined* the tag — which
would have left those five values reading as current again, the exact defect Doc-rev 1.15.2 was cut
to fix. The `[63-cell]` tags are unchanged.

**Two artefacts repaired.** The tag removal left **empty backtick pairs and stray spacing**
(`*(measured)* .`, `after R9 : `, a table row with trailing double-spaces), and a line in §10 was
**truncated mid-word** — `r sweep and a 3-band`, the front of the sentence gone. The truncated
sentence explained the 63-vs-33-cell rate difference, and with those rows deleted, restoring it
verbatim would have pointed at data no longer present; it is rewritten to stand alone: measured on
fw v4.34, rates from earlier firmware are not comparable because v4.34 delivers the full boundary
settle it had been short-changing, and **`cal_3x10_v2` has not been rate-measured yet**.
(2026-08-09)

---

### DESIGN.md — Doc-rev 1.15.4 — §13 and §10 described the retired profile, not this one

**§13 "What makes this design unusual" was largely a description of `cal_63_air_bat_v3`.** Four of
its claims are false of `cal_3x10_v2`, and §10's "Design principles (**carried across every
epoch**)" repeated two of them under a heading that made the error worse.

| claim | reality on `cal_3x10_v2` |
|---|---|
| "Geometric pulse ladder (×1.5)" | pulses are **100 / 50 / 10 µs** — ratios **2× and 5×** |
| "evenly spaced slice of log target-τ" per band | log₁₀ gaps are **0.7 and 0.3** — not even |
| "sampling the **0.5 – 4.9 V** band" | span is **4.85 V down to the ~16.5 mV pedestal** |
| "amplitude-anchored **thresholds** … the matrix self-normalising" | only the **6 early** cells are amplitude-anchored; the **4 late** ones are at fixed delays |

The ×1.5 figure was exact on the retired profile — its ratios run 1.49–1.50 across all seven bands —
so this is not a rounding quibble. It is a **design principle that was dropped at the epoch change
and never written down as dropped**, which is the same failure class as the rest of today's audit:
the statement stayed true-sounding while the thing it described was replaced.

**What the design actually is now, and it is a more interesting story than the one it replaced.**
The ladder is a **hybrid of two anchoring schemes**, because the front end makes the two halves of
the decay carry different information (§2):

- **6 early cells, amplitude-anchored** on the volt-scale decay — this is where target **polarity**
  separates families, so voltage is the right anchor. They inherit the pack-scaling cost (§12).
- **4 late cells at fixed delays** on the tail, landing on the pedestal — past the front end's lobe
  **both families read positive**, so sign is not a discriminant and **decay rate** is what
  separates them. Time is the right anchor there, and amplitude anchoring would sample the wrong
  quantity.
- **Nothing in between**, because that is where the unipolar front end rails (§7).

Conventionally a PI profile picks one anchoring scheme. Using one here would have sampled the wrong
quantity in one half of the ladder.

**Three-band spacing is a bench judgement, not a derived optimum**, and §10 now says so: three bands
cannot tile log-τ evenly, and the plan trades τ resolution for sweep rate (63 cells 6.49 Hz → 33
cells 11.49 Hz). The old ×1.5 rationale — constant-ratio spacing gives equal discrimination
information per slice — was a real principle and is recorded as retired rather than deleted.

**Two follow-ons in the same class.** §14.7 (possible TX coil-current plateau above ~67 µs) rested
entirely on the retired ladder's band-to-band clip-release increments; `cal_3x10_v2` has no 67 µs
band, so that comparison **cannot be repeated** — re-scoped, and noted that the question matters
more now, since the 100 µs band is one of three rather than one of seven. And a boundary worth a
bench check is recorded: §2's measured polarity window on the 100 µs band is **sd 7.97–12.30 µs**,
while two of that band's six early cells sit **outside** it (7.48 and 13.0 µs) — so the polarity
split may be carried by four cells there, not six. Flagged, not asserted: that window was measured
against one target pair, and its ends are where the split narrows rather than vanishes. (2026-08-09)

---

### DESIGN.md — Doc-rev 1.15.2 / 1.15.3 — staleness audit, and R1 is two resistors in parallel

**A full pass for claims of the same kind as the withdrawn damping figure**: internally consistent,
but undated, from a retired epoch, or propping up something newer. Five found. **Three are
regressions the 1.15 consolidation introduced**, which is the useful lesson — a trim that removes
qualifiers is a way of *creating* stale statements, not just of shortening the document.

1. **§3's epoch banner was gutted.** The pre-1.15 text read *"every value below was measured before
   the shielded enclosure"* — a blanket claim covering the whole section. 1.15 replaced it with a
   per-value tagging scheme and then tagged almost nothing, silently promoting flyback, the RX
   front-end node voltages, sample-timing precision and thermal drift to "current". §3 now carries
   explicit `[pre-enclosure]` / `[63-cell]` tags and states that untagged means current.
2. **Two unreconciled filtered-path noise figures.** §3 gives ≈ ±200 µV, §7 gives ≈ ±450 µV for the
   same SDOA path — 2.25× apart, both pre-enclosure, and §7's boxcar arithmetic is built on the
   larger. The pre-1.15 doc flagged this; 1.15 dropped the flag. Restored in **both** sections and
   promoted to the head of §14.2. Nothing downstream depends on it (the acquisition path is raw,
   where ±1400 µV is consistent throughout), which is how it survived — but one of the two is wrong.
3. **§3 and §17 disagreed on epoch tags for the same numbers.** `splithalf_floor`, the
   between-session component and the 70–130 ps timing jitter are tagged `63-cell` in §17 and were
   untagged in §3. Now consistent.
4. **SoC's "4 min warm-up" is a bench-supply figure** and warm-up is longer on the pack; the caveat
   was dropped in 1.15 and is restored, along with Mode 2 warm-up's "untested on `cal_3x10_v2`".
5. **§17.1's ~0.5 A was tagged "all epochs"** — it was measured on the 63-cell profile and the §12
   capacity figures rest on it. Now tagged, with a duty check recorded as *inference*: mean band
   duty goes 28.1 % → 27.1 % across the profile change, so the figure should carry, but it has not
   been re-measured.

**Then the substantive finding, from the bench rather than the document: R1 is two resistors in
parallel and the schematic does not show it.** Brown-green-red-gold ∥ brown-black-black-red-gold =
**1.5 kΩ ∥ 10 kΩ = 1304 Ω**, where schematic v6.04 draws a single `R1 1.3k`. That is within
**0.33 %** of the value the front-end fit assumed, so **no measured result moves** — but the
schematic is what a future reader will trust, and it is wrong. Recorded as new open item §14.5a,
with the suggestion that a single 1 % part would be preferable to a ±5 % pair.

**The best thing to come out of it: ζ does not depend on R at all.** For a parallel RLC the fitted
poles alone fix it —

> ζ = (τ_f + τ_s) / (2 √(τ_f · τ_s)) = **1.0622**

— because C ∝ 1/R and L ∝ R, so √(L/C) ∝ R and the R cancels. **The over-damped verdict is therefore
immune to the R1 uncertainty and to the ±5 % tolerance**, which is a much stronger statement than
the document previously made. L and C individually *do* move with the assumed R (577 pF / 4.43 mH at
1304 Ω against the published 579 pF / 4.41 mH at 1300 Ω — a 0.33 % shift kept as published, being far
inside the fit's own uncertainty).

Consequently the ζ-vs-R table is **relabelled as substitution sensitivity**, not as uncertainty in
this build: it holds the fitted L and C constant and asks what a *different* resistor would do, so
it inherits the R = 1300 assumption and is a guide to picking a part rather than a measurement. Read
that way it still says something worth knowing — a ±5 % pair spans 1239–1370 Ω, and the upper corner
sits ~10 Ω from critical. (2026-08-09)

---

### DESIGN.md — Doc-rev 1.15.1 — the legacy critical-damping figure is withdrawn as corroboration

**Question asked, and it was the right one: is the front end under- or over-damped?** The answer is
**over-damped, mildly, ζ = 1.06**, and it is consistent everywhere — but checking it surfaced a
stale claim propping up the fit.

DESIGN §7 carried an undated bench note, *"critically damps at ≈ 1.3–1.4k (measured)"*, and the
`RX L and C — pinned` block cited it as **independent corroboration** of the 2026-08-08 fit,
saying that "two quantities obtained years apart by different means agreeing to a few per cent is
why these are recorded rather than left open". **That corroboration is withdrawn.** The note is in
the very first repo commit (2026-06-22) with no date of its own, so it predates all recorded
history; it also predates the June 2026 front-end rework, and it describes an RX network that may
not be this one. It is not a check on the current values.

**The fit does not need it.** C = 579 pF, L = 4.41 mH, R_crit = 1381 Ω rest on the 2026-08-08 scope
measurement alone — 894 points, residual RMS 0.87 mV, taken at the amplifier input on the current
hardware. What changes is the *warrant*, not the numbers.

**The practical consequence is worth more than the retraction, because that band straddles the
boundary.** Damping is a shunt, so lower R means more damping:

| R1 | ζ | |
|---|---|---|
| **1300 Ω — as built** | **1.06** | over-damped, the intent |
| 1381 Ω | 1.00 | critical |
| 1400 Ω | 0.99 | **under-damped — ring returns** |

So the legacy "1.3–1.4k critical" band is **not a range to pick R1 from**: its top end is
under-damped by the current fit. Anyone swapping R1 to 1.4k on the strength of that line would
reintroduce ring. §7 now states the ζ table explicitly and marks the old band historical.

Two smaller repairs in the same pass. The **direct RX self-resonance measurement** is promoted in
priority — with the corroboration withdrawn it is the only thing that would confirm L and C
independently of a transient fit. And the guard against re-deriving **ζ = 1.00** is restored: it was
cut as narrative in the 1.15 consolidation, but it is a methodological warning, not history —
assuming the critically-damped form and fitting τ = 2RC can only ever report ζ = 1.00, and did, on
2026-08-07. Cutting it made the same mistake available again. (2026-08-09)

---

<!-- Add new entries above this line. Format: ### <file> — v<N> — <short title> -->

## Archive — consolidated 2026-08-09

### profile — `cal_3x10_v2` closes the last open question: no cell sits inside the rail

The one thing the `cal_3x10_v1` entry below deliberately left open is now shut. That profile's
10 µs band placed its first *late* cell at **18.0 µs**, while the reconstructed below-rail window
runs to **sd 18.44** (§7) — so the single cell most likely to still be clipped was in the very
profile cut to eliminate clipped cells. It moves to **18.44 µs**, the measured rail exit itself.
Nothing else changes: the diff is three lines — `name`, `notes`, and that one delay.
**sha8 `def96704`** (was `89590f69`). `cal_3x10_v1` is retired to the superseded list without ever
having been captured against. (2026-08-09)

**This is the cheapest this change will ever be, which is why it happens now.** The profile was
locked less than two hours ago and **no corpus exists against it** — so retiring it orphans
nothing, splits no dataset, and costs no recapture. The same edit made after a capture campaign
would have meant a new `(profile_name, profile_sha8)` group that `pimd_features` refuses to merge
with the first, i.e. throwing away or re-running the campaign. Locked profiles are never edited in
place, so this is `cal_3x10_v2` as a new file, not a corrected v1.

**Checks run before writing it, not after.** 18.44 µs is **exactly on the 8 ns PWM grid**
(2305 × 8 ns — the firmware cannot produce a delay between grid points, so an off-grid value would
have been silently rounded to something nobody chose); `_validate_profile_pwm()`, the client-side
mirror of the firmware's `validate_profile()`, returns clean; the ladder stays monotonic; and the
profile round-trips through `_apply_profile()` at 3 / 10 / 30 with a `D` command that builds. Worth
noting the 10 µs band's headroom is genuinely tight — **max valid delay 29.095 µs against a
largest-used 29.0 µs**, about 95 ns of margin, unchanged by this edit but not much to give away.

***Correction, same day, before any capture:*** this entry originally claimed that the moved
cell's `threshold_v` of **0.017 V** had gone stale — that it was a pedestal figure *measured* at
18.0 µs and no longer described a cell now sitting at the rail exit — and called for a re-measure
or a v3. **That was wrong, and it contradicted the `cal_3x10_v1` entry below, which already had it
right.** The last four `threshold_v` values in **every** band (`0.017, 0.016, 0.015, 0.014`) are
**placeholders for the pedestal, not measurements of anything.** The 1 mV steps exist only to keep
the ladder monotonic. Only the six *early* values are measured voltages.

So moving a late cell's delay invalidates nothing: a placeholder does not describe where its cell
sits and was never claiming to. **No v3 is needed and no re-measurement is owed.** The rule that
matters for anyone reading this column later is the one the v1 entry already states — *the four
late values are not four distinct measurements and should not be mined as such* — and it applies
uniformly across all three bands, at whatever delay each late cell ends up at.

Recorded rather than edited away, because the mistake is instructive: the drift happened between
two entries written an hour apart, where the second treated a column the first had explicitly
flagged as placeholder data as though it were measured. **A column that mixes measured and
placeholder values is exactly the kind of thing that gets mis-mined later** — which is the reason
the v1 entry called it out in the first place.

**The pack-voltage window is now carried in the profile's own `notes`** — "full charge down to
21.5 V" — rather than living only in a CHANGELOG entry. §10 requires a profile to be specified
together with a voltage range, and the file is the thing that gets loaded, copied and handed
around; a lock that has to be cross-referenced against a changelog to be fully specified is
half-specified in practice.

---

### repo — `pimd_classify.py` archived to history, then deleted; `src/*.py` is now all repo source

The classification/heatmap surface goes the same way as the rest of the previous epoch, but in
**two commits rather than one, and the ordering is the entire point.** `pimd_classify.py` was
untracked at `ff3b619` as a previous-epoch ML tool, and the newest copy in any commit was
`2f7f58a`'s **v1.2** — while local development had continued to **v1.5**. Deleting straight from
the working tree would have silently destroyed three versions that existed nowhere else. So it was
force-added first (**`08c9892`**, ~97 KB, verified byte-identical to the working tree before the
removal) and deleted second. (2026-08-09)

What that saved, and why it was worth a commit:

- **v1.3** — heatmap rows sorted delay-descending to match the standard grid orientation.
- **v1.4** — heatmap band order keyed on `pulse_us` rather than the `delays_us[0]` proxy. This is
  the one that mattered: `25d6a9a` made the identical fix in `pimd_classviz` v1.71 and recorded
  that *"the two must agree or one profile renders two different ways"*. Deleting unarchived would
  have left a **paired** change with one half committed and the other half gone, and a CHANGELOG
  entry describing code that no longer existed anywhere.
- **v1.5** — `DEFAULT_CORPUS` repointed out of the `ML/` tree deleted in `16edf75`.

**This is the opposite call to `pimd_v2_findings.py`**, deleted an hour earlier with no archive
commit — and the difference is not inconsistency. That file was checked against its history copy
and found **byte-identical**, so history already held everything; this one was three versions
ahead. The rule worth carrying forward: *before deleting an untracked file, diff it against the
newest copy in history — untracked does not mean unrecoverable, and tracked-once does not mean
tracked-current.*

**Nothing depended on it.** No module imports it anywhere in `src/` or `mcu/` — verified, the only
reference is a comment in `pimd_delaycal.py` citing it for a shared display convention, which
needs no code. It was a leaf: it consumed `pimd_features`, `pimd_corpus_check` and
`pimd_v2_findings`, and nothing consumed it. It had also stopped running entirely — an
`ImportError` once `pimd_v2_findings` went, on top of the older `pimd_features.DEFAULT_PROFILE`
`AttributeError` that killed it at argument parsing.

**Consequences.** The `.gitignore` block covering the 2026-07-13 "previous-epoch ML tools" is gone:
all three files it named are resolved (`pimd_corpus_check.py` re-tracked 2026-07-15, the other two
deleted), and **every `src/*.py` is now repo source** with nothing ignored in its place. Its
`src/data/classify_settings.json` went with it — gitignored, so invisible to the repo, but a
settings file for a tool that no longer exists is just a thing to wonder about later. **Retiring a
tool means retiring its settings file too**, which is the precedent worth having here. `USAGE.md`
→ **v1.31** records the deletion in §6 with the recovery shas for both files and the warning that
reviving one means reviving both. *For the next §18 consolidation pass:* §15's `src/pimd_classify.py`
row (still describing v1.3) should go, and §1's pipeline diagram and the "fourth tool in the
gui/classviz/delaycal/classify family" framing no longer hold — it is a three-tool family plus
`pimd_rawlog`.

---

### repo — `utilities/`, `ML/`, `References/scope/` and `References/Targets v1 Analysis/` retired at the epoch turnover

Four directories removed now that `cal_3x10_v1` has replaced `cal_63_air_bat_v3` (entry below).
All four served the previous epochs and none of them describes the instrument as it now stands:
`ML/V1` and `ML/V2` are **72-cell**, two epochs stale, and were already superseded by
`pimd_classify.py`; `References/Targets v1 Analysis/` is the offline analysis of the 2026-07-23
**63-cell `cal_63_air_v2`** corpus; `References/scope/` and `utilities/` are the measurement and
tooling behind work that has since been consolidated into DESIGN §7 and §12. The outputs worth
keeping were copied into `References/images/` first — `6S-pack-discharge-curve.jpg`,
`decay_model.png`, `lobe_at_amp_input_20260808.png` and `spanner_fills_the_null_20260808.png`.
(2026-08-09)

**Recoverability is not uniform, and that is the important part of this entry.**
`utilities/` (9 files) and `References/scope/` (5) were tracked and are retrievable in full at
**`59a9117`** — e.g. `git show 59a9117:References/scope/air_wide_20260808.csv`. **`ML/` (24 files)
and `References/Targets v1 Analysis/` (7) were gitignored and had never been committed, so they
are simply gone** — no history, no copy, ~4.8 MB. That was chosen deliberately rather than by
accident, which is why it is written down here: nobody should later go looking through the log
for them.

**Findings that keep their result but lose their tool.** Each of these stands on its own in this
file; what goes is the ability to *re-run* it from a clone. Named individually because a
one-line "utilities removed" would make them unfindable:

| tool | what it produced |
|---|---|
| `decay_model/decaymodel.py` (v5) | the two-pole front-end model of §7 — τ_fast/τ_slow, ζ, the null, the below-rail reconstruction |
| `decay_model/make_sweep_profile.py` | the characterisation sweep profiles (`sweep_*_decay_v1`) |
| `soak_vs_voltage/soakvolt.py` | the 2026-07-30 pack-voltage result (§17.13) — the finding the tracked-utility rule was written to protect |
| `pack_discharge/packv.py` | the SoC curve `pimd_gui.py` copies (its comment still cites the path; the table is duplicated in four tools and is unaffected) |
| `session_relabel/relabel.py` | the reconstructed `# mark:` lines in five session dumps, each stamped `reconstructed cos=… src=…` — those dumps keep their marks, but the reconstruction cannot be redone or audited |
| `mode2_noise/mode2_cell_noise.py` | the cell-0 outlier investigation that traced the ±120/−200 mV population to the blocking emit |

**DESIGN §15's tracked-utility rule retires with the directory.** That rule — *"a utility cited
from `CHANGELOG.md` has to be tracked"* — exists because `soakvolt.py` nearly stayed local and
would have left the project's headline pack finding unreproducible from a clone. It was the right
rule while `utilities/` existed. With the directory gone it now guards nothing, and leaving it in
place would make the next person think a tracked copy must be somewhere. **Recorded here as a
deliberate retirement, not an oversight.**

**Checklist for the next §18 consolidation pass** *(DESIGN.md is regenerated from this file, not
edited directly — these are the rows that will otherwise dangle)*: drop the §15 inventory rows
for `utilities/`, `References/scope/` and `References/Targets v1 Analysis/`; drop §15's
tracked-utility rule; drop the two §16 offline run commands that invoke
`utilities/decay_model/decaymodel.py` and `make_sweep_profile.py`; and check §15's
`src/data/sessions/` row, which cites `utilities/session_relabel/` for the reconstructed marks —
the marks survive, the tool does not, and the row should say so. Also repath the two
`References/training-results-v1b.png` / `-v1c.png` rows, which moved into `References/images/`
with the rest of the kept figures — same files, tracked as renames, new location.

**Three more files go with the same sweep.** `HANDOFF_cell_reduction.md` is retired because its
question has been **answered**: it was the 2026-08-03 brief asking which rows and columns of
`cal_110_full_range_v4` (10 × 11 = 110 cells) could be dropped "without losing information, to cut
sweep/frame time and thermal exposure", and `cal_3x10_v1` — 30 cells, 6.49 → 11.49 Hz — is the
answer. A handover doc outlives its usefulness the moment the handover completes. Also
`sweep_100us_asbuilt_20260808.json`, the reconstruction of the superseded 68-cell ladder (§10),
and `sweep_150us_decay_v1.json`.

**That last one is half of a documented pair, and the consolidation pass needs to know.** §10's
*"Characterisation sweeps — `sweep_100us_decay_v1` / `sweep_150us_decay_v1`"* subsection and
§15's inventory row both describe the two together as the 66-cell single-band sweeps built to
model the decay rather than sample it. **`sweep_100us_decay_v1.json` survives and stays tracked;
the 150 µs half does not.** The §10 subsection and the §15 row should be rewritten around the one
that remains rather than left describing a pair that no longer exists. The 150 µs sweep is
retrievable at **`16edf75`** like the rest of this cleanup, and §10's reasoning for why the pair
existed at all — `cal_110_full_range_v4`'s 150 µs band puts only two columns between clip release
and the rail, and two points cannot constrain a decay — stands as written and should be kept.

**`src/pimd_v2_findings.py` deleted too** — the v1.0 reproduction script for `ML_Findings_v2.md`,
which went with `ML/` above, so it was reproducing a document that no longer exists. Gitignored
since `ff3b619` untracked it, but **tracked before that and byte-identical to the copy at
`84471fe`** *(checked, not assumed)*, so it is recoverable despite not being in the current index.
Its `.gitignore` rule goes with it.

**It takes `pimd_classify.py` with it, and that is worth stating rather than discovering.** That
tool does not merely import it — it delegates its band-mean / crossing-continuum physics to it at
eleven call sites (`bandmeans()`, `crossing_us()`, `continuum()`, and the hand-curated `FAM3`
campaign-2 ground truth), by deliberate design: *"reuses, does not reimplement"*. So
`pimd_classify.py` now fails at **import** as well as at argument parsing. In practice this
changes nothing — it was already unrunnable for the `DEFAULT_PROFILE` reason above, it is
gitignored, and its whole feature set is 63/72-cell — but anyone reviving it needs both
`84471fe:src/pimd_v2_findings.py` and a decision about what it should classify against in a
30-cell epoch.

**Not touched by any of this:** `src/data/corpora/` keeps both 63-cell corpora. They are
previous-epoch and cannot be mixed into a 30-cell dataset, but they remain the only corpora on
disk and `pimd_shape.py --selftest` still expects them (§14.15).

**`src/pimd_classify.py` v1.4 → v1.5** — its `DEFAULT_CORPUS` pointed at
`../ML/V2/PIMD_target_corpus_signatures_v2.csv`, which stopped existing, so the default is
repointed at `src/data/corpora/gui_signatures_targets_v3_20260728_142316.csv` and the `--corpus`
help text corrected. The file is gitignored and so is not in this commit; recorded here because
a silent dangling default is exactly the kind of thing that surfaces months later as a confusing
traceback.

***Flagged, not fixed — and it is worse than a dangling default.*** `pimd_classify.py` does not
currently run **at all**: `build_arg_parser()` reads `pimd_features.DEFAULT_PROFILE` for its
`--profile` default, and `pimd_features` has no such attribute, so every invocation dies with an
`AttributeError` before parsing a single argument — GUI and `--headless` alike. **This predates
the ML/ removal and is unrelated to it**: `DEFAULT_PROFILE` was removed from `pimd_features`
deliberately (its own header comment records *"validate_profile/DEFAULT_PROFILE/--profile
removed"*), and `pimd_classify.py` was never updated to match. Left alone on purpose: it is a
gitignored previous-epoch tool whose defaults are 63/72-cell, and repairing it means deciding
what it should point at in a 30-cell epoch that has no corpus yet — a real piece of work, not a
one-line fix, and not one to fold silently into a cleanup.

---

### profile — `cal_3x10_v1` is the new corpus starting point; the null cells are gone and the matrix is less than half the size

**3 bands × 10 cells = 30 channels**, `averages: 32`, sha8 **`89590f69`**. Bands 3125 Hz/100 µs,
5000 Hz/50 µs, 25000 Hz/10 µs. Per band the ladder is **6 early samples, a skipped span, then 4
late samples** — the skips are **13→30 µs** (100 µs band), **12→24 µs** (50 µs) and **10→18 µs**
(10 µs). This replaces `cal_63_air_bat_v3` (7 × 9 = 63) as the operating profile and is the
geometry the next capture campaign is built on. It was arrived at on the bench as best
representing the range of targets, and it is the first profile in this project cut with the
front-end model in hand rather than by sweeping and hoping. (2026-08-09)

**Why the middle cells are gone.** The front end has two real poles with opposite-sign residues
(τ_fast 1.125 µs, τ_slow 2.270 µs, ζ = 1.06), so air has exactly one zero crossing and swings
negative — measured at the LT6203 input as **sd 14.3 → 18.0 µs**, bottoming **≈ −15 mV** (§7).
The path is unipolar and the output **rails at 2.441 mV**; reconstructed through the 1.149
input→ADC gain, air is genuinely **below the rail for 4.21 µs, sd 14.23–18.44**. §14.17 is the
consequence and it is the whole argument: Δ = target − air, and where air is clipped up onto the
floor the subtrahend is too large, so **the delta is always understated — by up to ~3.5×** (at
sd 17.3 µs the ADC records **+6.3 mV** where the input shows **~+22 mV**). Those cells do not
merely add noise. They compress amplitude non-linearly and by an amount that depends on target
strength, so every band mean, crossing width and amplitude feature computed over them inherits
that bias. Cutting them out of the geometry is the cheapest possible fix: no feature code has to
learn about the rail, because nothing is sampled there any more.

**What that costs, stated plainly.** The null is **real coil physics, not an artefact** — it is
present *before* the amplifier and it **responds to metal**: a steel spanner on the coil removes
the crossing entirely (minimum +15.5 mV, difference up to **+48.9 mV** at sd 13.57 µs). And the
rail is an **air** problem, not a cell problem — a close ferrous target lifts the whole trace
clear of it, so the same cell that is dead in air is perfectly live on a strong target. Dropping
these cells therefore trades a target-present signal for a **bias-free** corpus. That is a
deliberate choice and it should be revisited if the classifier turns out to want that region;
it is not a free win.

**The lineage, all of it on 2026-08-09, all on fw 4.34.** Read off the session dumps in
`src/data/sessions/` — the embedded `profile_json` / `profile_sha8` headers are the primary
record, since none of this line of work was written down until now:

| profile | sha8 | geometry | measured sweep rate |
|---|---|---|---|
| `cal_63_air_bat_v3` (outgoing) | `4a2352d2` | 7 × 9 = 63 | **6.49 Hz** |
| `cal_3x15_v2` | `fd369286` | 3 × 15 = 45 | **8.77 Hz** |
| `cal_3x15_v3` — *"middle nulls removed from v2"* | `baf9019e` | 3 × 11 = 33 | **11.49 Hz** |
| **`cal_3x10_v1`** (new) | `89590f69` | **3 × 10 = 30** | no session yet |

Rates are the median of each dump's `firmware_time_ms` deltas, so they are on the firmware clock,
and all four were taken on the same bench within an hour of each other. **The 63-cell profile
nearly doubles in rate at 33 cells** — which is the direct answer to `next.txt`'s "our current
system is slow to acquire due to large profile matrix".

*Inference, not measurement, on one point:* 6.49 Hz for `cal_63_air_bat_v3` is **below** the
0.1445–0.1455 s / 6.88–6.92 Hz §17.13 records for that same profile on 2026-07-30/31. Firmware
v4.34 now delivers the *full* boundary settle it had previously been short-changing, and a 7-band
profile pays that seven times per sweep where a 3-band profile pays it three. If that is the
cause it is a second, independent argument for fewer bands — but the v4.34 acceptance figure
(§14.18) is still outstanding and this is one 77-frame session, so it wants confirming rather
than asserting.

**`cal_3x15_v3` → `cal_3x10_v1` is one more early cell per band.** Dropped `8.32` µs (100 µs
band), `7.744` µs (50 µs) and `6.0` µs (10 µs) — the second sample in each row — **as noisy and
carrying no information the neighbouring cells did not already have** *(bench observation)*. The
profile's own `notes` field now describes the final geometry rather than the v2→v3 step it used
to record.

**`threshold_v` in this profile is measured voltage, not a nominal target ladder,** and that is a
change of meaning worth flagging because delaycal's `threshold_v` normally records the voltage a
swept delay was *aimed at* (`_targets_v`). Here it is uniform across all three bands and reads
**4.85, 2.17, 1.05, 0.48, 0.19, 0.07** for the six early cells and **0.017, 0.016, 0.015, 0.014**
for the four late ones. Those last four are the **~16.5 mV front-end pedestal** (§7: +14.34 mV at
the input, **16.472 mV** at the ADC), which is exactly what a late sample is *for* — the decay is
over and what is left is the front-end DC. The 1 mV steps between them keep the ladder monotonic;
they are not four distinct measurements and should not be mined as such.

**What this invalidates.** Both corpora on disk are 63-cell and **cannot be migrated** into a
30-cell epoch — `gui_signatures_targets_v1_20260723.csv` (4 158 rows, `cal_63_air_v2`/`b4bee9d2`)
and `gui_signatures_targets_v3_20260728_142316.csv` (11 844 rows, `cal_63_air_bat_v3`/`4a2352d2`).
The `(profile_name, profile_sha8)` guard in `pimd_features.py` refuses to build across them by
design, and §10 is explicit that an identical cell count would not have implied comparability
either. `ML/V1` and `ML/V2` are 72-cell and were already two epochs stale. On the tooling side
nothing needs changing: classviz rebuilds its dims from the profile and discards the
old-geometry air reference, `pimd_classify` derives geometry from the colmap, and **no firmware
change is required** — this rides in the RAM-only `D`/`Q5` dynamic slot, as every 3x15 session
already did. `cal_63_air_bat_v3.json` moves to `.gitignore`'s superseded-locks list and
`cal_3x10_v1.json` becomes the tracked profile, per the procedure in that file's own comment.

**The pack-voltage window: full charge down to 21.5 V — the whole usable pack.** §10 requires a
profile to be specified together with a voltage range, and this is it. **21.5 V is not an
arbitrary floor:** it is where the firmware's low-voltage failsafe re-arms (§12), it is the
dashed edge already drawn on the pack gauge in all four PC tools (`PACK_WINDOW_LO_MV`), and the
LOCKOUT floor sits below it at 21.0 V. The epoch's capture window is therefore bounded by
something instrumented and on screen rather than by a number the operator has to hold in their
head — and the board stops the run itself at the bottom of it.

**This is wider than §12's 21.5–23.3 V clean window, deliberately, and it is a bench judgement
about *this profile* rather than a correction to §12.** The relevant precedent is already in the
record: the 2026-07-24 survey found the suspect columns elevated at **22.4 V**, which the 07-30
rule calls clean, and §17 resolves that tension only as a hypothesis — *"the clean window may
belong to **(pack voltage × profile delays)** rather than to pack voltage alone"*, since the zone
sits at a fixed place on the decay and each profile's delays cut the decay at different points.
`cal_3x10_v1`'s delays are entirely new and were cut against the front-end model, so it has no
particular reason to inherit `cal_63`'s window. **That is consistent with the hypothesis, not
confirmation of it** — DESIGN is explicit that it is "a hypothesis, not a result", and one
profile behaving well over a wider range does not settle it.

What the widening buys is concrete. §12's discharge budget writes off `full → 23.3 V` as
**1.78 h, 17 % of the pack**, "unusable, above the data-quality ceiling", leaving **4.55 h** as
the session-planning number. Capturing from full down to 21.5 V instead makes it **≈ 6.33 h per
charge, +39 %** — the difference between one capture campaign per charge and two. The obligation
that comes with it is that every capture records the voltage it actually ran at, which classviz
v1.72 now does by itself on every `# pack_v:` line. If the wide window does cost quality at the
top end, that per-frame track is what will show it. This is a testable widening, not an
assumption; the sessions that established the geometry already span it, running at **24.30 V**
down to **21.94 V** with the board at **54.8 °C**.

**One thing this entry deliberately leaves open: the 10 µs band's first late cell sits at 18.0 µs,
and the reconstructed below-rail window runs to sd 18.44.** It may still be inside the rail. The
100 µs and 50 µs bands clear it comfortably (first late cell at 30 µs and 24 µs); the shortest
band is where the margin is tightest, and the below-rail figure is a reconstruction from one
scope condition rather than a per-band measurement. Worth one check before a corpus is built on
it — a railed cell is precisely what this profile exists to remove, and it would be an unhappy
irony to ship one.

---

### src/pimd_classviz.py — v1.72 — pack voltage and board temperature from firmware telemetry; Pack V / Log V removed

The `Pack V` spinbox and the `Log V` button are gone, and with them the 20-minute
`PACK_V_REMIND_S` nag. Both readings now come off the wire: `P<time_ms>,<pack_mV>,<board_temp_dC>`
(unsolicited, ~60 s) and fields 8..10 of the `V` identify reply, shown on the same `BatteryGauge` /
`BarGauge` widgets `pimd_gui` uses — pack SoC with its §12 zone colour, board temperature to
0.1 °C. **Why the hand-entry had to go rather than be supplemented:** v1.64 added it precisely
because a 6S pack falls ~2.5 V across a long run and none of it was recorded, but a typed number is
only as complete as the operator's memory, and the 2026-07-29 dump — the one the warm-up findings
rest on — has **1h51m between two readings**, which is exactly where interpolating voltage onto the
frame timeline is least defensible. The firmware has been reporting this on the same wire since
v4.28. Nothing polls: the gauges are primed by the `V` already in `connect_port()`'s handshake
(sent while the rig is idle) and refresh from the firmware's own cadence, so no command is ever
injected between `W` records. (2026-08-09)

**Session dump.** Every accepted reading now appends its own
`# pack_v: <iso>, <volts>, age_s=<n>, temp_c=<c|none>` line while recording, so the voltage track
is complete by construction and a board-temperature track exists for the first time — warm-up and
battery sag are the two confounders that move a session's levels, and only one of them was being
written down. `temp_c` is appended to the same `key=value` tail `age_s` lives in, which
`pimd_features._parse_kv_tail` hands back as strings and ignores when unknown, so **the new field
is additive and every existing reader keeps working** — verified by round-tripping a written dump
through `pimd_features.parse_session_file()` and `pack_v_at()`. The literal `none` rather than a
number when the DS18B20 gave no reading, for the same reason `-32768` is never displayed: a later
reader has no way to tell a sentinel from a temperature. `age_s` changes meaning — it is now the
age of the *firmware's* report (normally under 60 s), not seconds since the value was typed — and
the header gains a `# sensor_source:` line so a dump says which regime produced it. `PACK:` and
`LOCKOUT` firmware messages are marked in as `# mark: firmware: …`; frames after a latched lockout
are not the same experiment as frames before it, and offline there was no other way to know.

The `P` branch anchors on a digit after the tag, which is load-bearing and is the defect
`pimd_gui` v4.17 was cut to fix — a bare `P` test also matches `PACK: …` and the boot banner, which
split on commas into an `IndexError` once per pack power-cycle. `'lockout cleared'` is matched
explicitly for the same class of reason: that message contains the word "lockout" while meaning the
opposite, so a substring test would latch on it and invert the state. The age label beside the
gauges retargets from nagging a human (20 min) to reporting that the board went quiet
(`SENSOR_STALE_S` 180 s ≈ three missed reports). The persisted `pack_v` settings key is no longer
written or restored; a stored one is ignored. Constants, SoC maths and both gauge widgets are
duplicated from `pimd_gui.py` rather than imported, per the standing rule that every PC app in
`src/` stands alone — the four copies (`pimd_gui`, `pimd_rawlog`, `pimd_delaycal`, here) must be
retuned together. **`pimd_features` is deliberately not touched**: it reads the extended track
correctly today, but it does not yet expose `temp_c` as a parsed field or a corpus column, and
doing that is a schema change with its own blast radius.

---

### src/pimd_delaycal.py — v1.47 — pack / board-temperature gauges, and the conditions a calibration was measured under

A calibration is only comparable with another if the conditions match (§14.1), and until now the
conditions were **not recorded anywhere at all** — the exported profile's notes carried the sweep
parameters and the geometry, but nothing about the pack or the rig's thermal state, which is the
variable heavy-band delays actually move with (tens of ns cold-to-warm, §10). This adds a `Rig
State` group to the left column with the same `BatteryGauge` / `BarGauge` widgets `pimd_gui` uses,
fed by the firmware's `P` telemetry and primed by a `V` sent once on connect. (2026-08-09)

The readings are folded into a conditions span reset at connect and again at Run, and that span —
pack first→last (min) and board temperature first→last (max) — is written into the exported
profile's `notes`, alongside a new `#` header block in the exported CSV (export timestamp, tool and
firmware version, sensors at export, the same span). The span deliberately keeps running through
the THERMAL soak and Auto Nudge that follow a sweep, because those refine the delays the profile
ships with. A temperature the firmware could not read is folded in as nothing at all, never as a
number, so a missing DS18B20 cannot drag the recorded minimum to something that looks measured.

**Placement in the serial reader is the load-bearing part.** The new branches sit *ahead* of the
`_pending_d_ready` gate: an unsolicited `P` can land in the window between `D` being sent and its
reply arriving, and that gate consumes every line it sees. They also sit ahead of the
`'ERROR' in raw` catch-all. Nothing here sends a command while a sweep or a soak is running — an
injected command would interleave with the `R` records the sweep state machine advances on — so
the gauges live entirely on the firmware's own ~60 s cadence after the one idle `V`. A latched
`LOCKOUT` now stops a running sweep: past that point the table is being filled with readings taken
against a pack the firmware has cut, and nobody should calibrate against those. The `P` isdigit
guard and the `'lockout cleared'` special case are carried over verbatim from `pimd_gui` v4.17 and
`pimd_rawlog` v1.15 — see those entries for why both are not simplifiable. Constants, SoC maths and
both widgets are duplicated from `pimd_gui.py`, not imported, per the standing rule that every PC
app in `src/` stands alone.

---

### src/pimd_delaycal.py — v1.46 — calibration table rows pulse-ascending, matching the two thermal tables

The two thermal tables (mean, std dev) have sorted their rows by `pulse_us` since v1.17
(`_thermal_display_order`); the calibration table above them stayed in protocol/JSON order, which
the v1.17 comment recorded as deliberate. With `cal_3x15_v1` — protocol order 100 / 50 / 10 µs —
that left the top table reading 100/50/10 while the two below it read 10/50/100. All three now
read top-to-bottom in pulse-ascending order, the project's standard grid orientation (lowest
top-left, highest bottom-right).

**Done as a `QHeaderView` section move, not as a permutation of the data, and that choice is the
whole point of the change.** The calibration table's row index doubles as the **protocol band
index** in ten places: `_build_profile()`, `export_csv()`, `_fill_cell()`, `_mark_row_pending()`,
`_start_auto()`, `_auto_finish()`, `_auto_color_cell()`, `_on_manual_nudge_clicked()`, and the two
thermal colour mirrors in `_update_thermal_tables()`. Several of those *write* a calibration.
Permuting the data would mean getting a protocol↔display mapping right at every one of them, and
getting it wrong in `_build_profile()` would silently pair the wrong delays with the wrong band in
an exported profile — a corruption with no visible symptom until a capture campaign came out
strange. Moving header sections leaves every logical index untouched, so all ten stay correct by
construction and only the screen changes. `_on_manual_nudge_clicked()` is the clearest example: it
uses its row argument both to address the table *and* to index `_fp_pairs` for its log label, and
under this approach both remain right with no edit at all.

**`_fp_pairs` is deliberately not reordered.** It drives the `D` command, so its order *is* the
sweep order — rotating it would move which band sits at which sweep position, and this week's work
has established that sweep position is exactly the variable under investigation.

Verified by driving the real `_rebuild_table` / `_apply_cal_row_order` / `_fill_cell` against
`cal_3x15_v1` under an offscreen Qt: display reads 10 / 50 / 100 µs top-to-bottom, while
`table.item(0, ·)` still returns the 100 µs band's own delays and the full band↔delay round-trip
is intact. Three Qt behaviours were checked rather than assumed — `moveSection()` works
programmatically even though `sectionsMovable` is False (so rows still cannot be dragged by hand),
`clear()` + `setRowCount()` do **not** reset section order (hence the re-apply on every rebuild,
or a stale permutation would survive a profile change), and the move loop converges from any
starting state. Switching afterwards to the 7-band `cal_63_air_bat_v3` renders
9/13.44/20/30/45/67.2/100 with no residue. (2026-08-09)

---

### src/pimd_classviz.py — v1.71 / src/pimd_classify.py — v1.4 — heatmap band order keyed on pulse_us, not the `delays_us[0]` proxy

`cal_3x15_v1` (3 bands: 3125 Hz/100 µs, 5000 Hz/50 µs, 25000 Hz/10 µs) rendered its heatmap rows
**50 / 10 / 100 µs** on both the Main and Analysis sheets — neither the profile's own band order
nor the project's standard grid orientation, which `pimd_rawlog.py`'s header declares as
**lowest top-left, highest bottom-right**.

Cause: `_band_display_order` sorted on `bands[i]['delays_us'][0]`, the band's *first delay*, as a
stand-in for pulse width. That holds for every calibrated profile — a shorter pulse releases the
clamp earlier, so first delay and pulse width ascend together — and v1.70 adopted it having
explicitly verified only that `cal_110_full_range_v4` behaves that way. The proxy fails the
moment two bands are given the **same delay ladder by hand**: `cal_3x15_v1` starts both its 50 µs
and 10 µs bands at 5.160 µs, the tie fell to protocol order (50 before 10), and the 100 µs band's
7.480 µs sorted last. Sorting on `pulse_us` is what the orientation rule actually means, so the
key is now the quantity itself rather than something correlated with it.

**Scope, checked rather than asserted:** across all eleven profiles in `src/data/profiles/`, the
old and new keys produce an identical permutation for ten of them — every tracked and operating
profile included (`cal_63_air_bat_v3`, `cal_110_full_range_v4`, both `cal_72` generations, all
the `cal_100_10_x15` variants). `cal_3x15_v1` is the only one that moves, and it moves from
50/10/100 to 10/50/100. The change is a no-op on every capture ever taken.

Fixed in **both** tools. `pimd_classify.py` carried the same proxy with the same comment
(its v1.3 was the sibling of classviz v1.70) and would have rendered the same profile the same
wrong way — one profile displaying two different ways across two tools is worse than either being
wrong alone. `pimd_delaycal.py` already sorted its thermal rows on `pulse_us`
(`_thermal_display_order`), which is corroboration that pulse width is the intended convention
rather than a new decision made here.

Ties between equal pulse widths now keep protocol order, Python's sort being stable — which is
what a profile carrying a deliberately duplicated band (`cal_100_10_x15_v1_3band`) wants.
`_pulse_sort_order` is left as a separate name even though it is now the same permutation: it
expresses a different requirement ("vs pulse width" plotting on the Analysis tab, not grid
orientation) and the two only coincide while both are defined as pulse-ascending. Noted in place
so neither is collapsed into the other. (2026-08-09)

---

### Findings — the cell-0 population is caused by the EMIT. Not the band boundary, not settling, not dwell.

`cal_100_10_x15_v1_3band` (97a12499) was run under fw v4.34, 1427 frames / 143 s / 9.95 Hz. It
fills the open cell of the factorial and closes the question. The 25 kHz/10 µs @ 5.160 µs cell,
absolute >100 mV gate, Poisson errors:

| run | emit? | energy step? | settle at that cell | events per 1000 |
|---|---|---|---|---|
| `cal_100_10_x15_v1` pos 0 | **yes** | yes | 3 ms | **32.6 ± 5.0** |
| **3-band pos 0** | **yes** | **no** | **none — `needs_settling` is False** | **28.1 ± 4.4** |
| `_bandswap` pos 15 | no | yes | 3 ms | 0.0 ± 0.7 |
| **3-band pos 30** | **no** | **yes** | **3 ms** | **0.0 ± 0.7** |

**The emit alone reproduces the population at full strength.** 28.1 ± 4.4 against 32.6 ± 5.0 is
indistinguishable, and it is produced at a cell with *no* band boundary, *no* energy step and *no*
settle sleep whatsoever. Removing the emit takes it to exactly zero in two independent runs.

**The within-run control is the strongest evidence in this whole investigation.** ch0 and ch30 are
the same frequency, same pulse, same delay, same profile, same sweep, the same second of the same
capture — the only difference between them is which one follows the emit. Over 1426 sweeps:
**ch0 151 events (min −205, max +129 mV), ch30 zero.** Not "fewer": zero.

**Dwell is excluded over the full range tested.** The population appears at ~0 ms of settle (here,
where the wrap changes neither frequency nor drive duty) and at ~16 ms (the v4.35 10 ms-floor run,
10 ms settle + ~6 ms emit) at statistically the same rate, while every *settling* gradient in the
profile responds strongly to that same range. Settling and this population are different
phenomena and always were.

**So the residual mechanism is the emit itself, and it is configuration-selective.** The bandswap
run put the emit in front of the 3.125 kHz/100 µs cell and got 0.0 per 1000, so it is not simply
"the cell after the emit". It is the emit *and* the 25 kHz/10 µs operating point. Dwell is out and
the code path is byte-identical for both bands, which leaves the electrical environment during and
after the USB TX burst — a ~250-byte W record is four packets and TX continues for milliseconds
after `print()` returns, through cell 0's conversion. At 25 kHz a conversion completes every 40 µs
so the BUSY-synced read lands inside that window; at 3.125 kHz the next conversion is up to 320 µs
away. **Per CLAUDE.md this is not decidable from the code and wants the scope** — trigger on the
USB D+/D− activity and watch the LT6203 output and the LTC2508 reference.

**Two firmware options exist that do not require knowing the mechanism**, both cheap and
reversible, and neither is a redesign: (a) decimate the emit via `MIN_EMIT_MS` and confirm the rate
falls proportionally — a one-constant causality check; (b) **move the emit's service point off
`i == 0` to a sweep index whose following cell sits on the pedestal**, where a corrupted sample
costs nothing (cells 13/14 of the 25 kHz band read 15–16 mV at 1 LSB of σ). (b) is a real fix
rather than a diagnostic and would leave the informative top-of-decay cells clean, but it is a hot
path change and the v4.13/v4.20/v4.24/v4.26 sequence is fair warning that it needs its own A/B.

**Secondary, and a caution for profile design.** The same run shows the 100 µs band reading
*higher* and *noisier* in the 3-band profile than in the 2-band one — 4874.3 mV / σ 12.14 against
4845.8 / 9.59 at 7.48 µs, and 3885.3 / σ 23.05 against 3852.4 / 10.87 at 8.32 µs. Thirty of the
forty-five cells are now the low-power band, so the rig runs cooler and the 100 µs band's energy
step is *larger* relative to steady state. **Band composition changes the operating point of the
other bands** — which is §10's "a profile is only fully specified together with a pack-voltage
range" extended to a dimension that was not previously written down. The two identical 25 kHz
bands also differ by **34 mV** at 5.160 µs (4874.1 at position 0 vs 4839.8 at position 30) purely
from position-30's under-settling, a direct measure of the residual boundary bias at a 3 ms floor.
(2026-08-09)

---

### src/data/profiles/cal_100_10_x15_v1_3band.json — new — within-run factorial separating the emit from the energy step

Diagnostic profile, not a calibration. Three bands × 15 delays = 45 cells:
**25 kHz/10 µs, 3.125 kHz/100 µs, 25 kHz/10 µs**, where the two 25 kHz bands are *byte-identical*
— same frequency, same pulse, same delays. The same physical configuration therefore appears at
sweep position 0 **and** position 30 inside one sweep, at the same pack state, the same thermal
state and the same run. Every comparison so far has been between runs; this is the first within-run
control.

**The design turns on a property of `needs_settling`, not on the repetition.** Because band 2 is
also 25 kHz/10 µs, the wrap from position 44 into position 0 changes neither the frequency nor the
drive duty, so `at_boundary or dd != cells[prev][2]` is **false** at position 0 — verified against
the firmware's own arithmetic. That cell gets the blocking emit and *no* boundary settle and *no*
energy step. Position 30 gets the 100 µs → 10 µs energy step and its settle but *not* the emit.
The two confounded factors are separated, and combined with the existing runs the four-cell
factorial is complete:

| | emit | no emit |
|---|---|---|
| **energy step** | `cal_100_10_x15_v1` pos 0 — **32.6 /1000** | `_bandswap` pos 15, this profile pos 30 — **0.0 /1000** |
| **no energy step** | **this profile, pos 0** — the open cell | — |

Reading the result at 25 kHz/10 µs @ 5.160 µs on the absolute >100 mV gate: population at pos 0
only ⇒ the emit alone is sufficient and the energy step is irrelevant; at pos 30 only ⇒ the energy
step alone is sufficient and the emit is irrelevant; at both ⇒ each is independently sufficient;
at neither ⇒ the two are required together, which is what the existing 32.6 vs 0.0 pair implies
and which would point squarely at the emit's interaction with the low-power band rather than at
either factor alone.

Validated before writing: all 45 cells pass the firmware's `compute_pulse_duties` /
`pulse_duties_valid` arithmetic, all three bands carry 15 delays (the `D` command rejects unequal
bands), and the `D` string is 337 chars against 227 for the two-band profile — longer than
anything sent so far but well inside what the 110-cell profiles already require. Expected sweep
~117 ms (~8.5 Hz) at 45 cells and two real boundaries, so the 32-deep rolling window spans ~3.7 s.

Two operational notes. `pimd_delaycal` labels rows by freq/pulse, so **two rows will look
identical**; its thermal tables sort by `pulse_us` with a stable sort, giving display order
band 0, band 2, band 1 — top row is the position-0 copy, middle row is the position-30 copy,
bottom row is the 100 µs band. And `_meas_cache` / any keying on `(freq, pulse, delay)` collides
between the two copies; the session `colmap` carries `band_index`, so `mode2_cell_noise` separates
them correctly (smoke-tested on a synthetic 45-channel session: planted 52.2 outliers per 1000 on
ch0, recovered 44.5, and the identical ch30 correctly reported 0.0 with no false positive).
(2026-08-09)

---

### Findings — SETTLE_FLOOR_US 10 ms was tried and reverted: it fixes settling, and it kills the dwell hypothesis

`SETTLE_FLOOR_US` was raised 3000 → 10000 µs (briefly FW_VERSION 4.35), flashed, run, and
**reverted the same session**. No shipped version carries it, so this is recorded as a finding
rather than a version entry — but the experiment answered two things and should not be re-run
blind. The constant's comment block in `pimd_mcu.py` carries the short form.

**It fixed the settling, comprehensively.** Equivalent timing jitter, first five cells of each
band, across all four runs (`session_20260809_133725` / `_133928` at 3 ms, `_140356` / `_140331`
at 10 ms; "emit" marks the band that sat at sweep position 0 and therefore also received the
~6 ms blocking emit inside its settle window):

| band | floor | at position 0 (**+ emit**) | at position 15 (settle only) |
|---|---|---|---|
| 3.125 kHz / 100 µs | 3 ms | 2.1 2.3 1.9 1.5 1.4 ns | 8.1 7.8 5.3 3.7 4.1 ns |
| 3.125 kHz / 100 µs | **10 ms** | 1.1 1.4 1.4 0.7 1.4 ns | **3.3 3.9 3.0 2.2 2.7 ns** |
| 25 kHz / 10 µs | 3 ms | 2.5 2.2 2.3 2.1 2.6 ns | 2.4 5.2 5.2 4.3 5.2 ns |
| 25 kHz / 10 µs | **10 ms** | 2.5 1.3 1.4 1.4 1.3 ns | **1.0 2.2 2.3 2.1 2.6 ns** |

Every position-15 gradient collapses to roughly the emit-fed figure, and the emit-fed positions
improve again on top. The tool stops flagging a boundary gradient anywhere. The ~9–11 ms transient
estimate is confirmed a second time, and 10 ms covers it.

**It did not touch the cell-0 outlier population, and that is the valuable part.** The 25 kHz /
10 µs @ 5.160 µs cell at sweep position 0, absolute >100 mV gate, with Poisson errors:

| run | events / sweeps | rate per 1000 |
|---|---|---|
| v4.34, 3 ms, original | 43 / 1321 | 32.6 ± 5.0 |
| v4.34, 3 ms, bandswap (same cell at pos 15) | 0 / 1425 | 0.0 ± 0.7 |
| 10 ms, original | 6 / 258 | 23.3 ± 9.5 |
| 10 ms, bandswap (same cell at pos 15) | 0 / 210 | 0.0 ± 4.8 |

32.6 ± 5.0 against 23.3 ± 9.5 is **no change within the error** — and the 10 ms runs are only
20–24 s / 211–259 frames, which is ample for σ (a MAD over ~250 differences) but far too short for
a rate claim off six events. The conjunction holds identically under both floors: the population
appears only where the 25 kHz/10 µs band meets sweep position 0, and position 0 occupied by the
100 µs cell is 0 events in both firmwares.

**So variable emit dwell is not the mechanism.** At a 10 ms floor cell 0 receives ~10 ms of settle
plus the ~6 ms emit — roughly 16 ms at its own configuration before its sample, against a
transient that every other measurement in this profile says is over by ~11 ms. Every settling
gradient in the profile vanished at that dwell. If the population were the emit's *duration*
moving the sample around on a relaxing curve, it would have gone with them. It did not. What
remains is something about the emit that is not its length — USB TX burst coupling into the front
end or the LTC2508 reference is the standing candidate, and per CLAUDE.md that is not decidable
from the code.

**Why it was reverted despite fixing settling.** The floor is global and the cost is real:
12.07 → 10.53 Hz on this profile, and ~6.2 → ~4.8 Hz on `cal_63_air_bat_v3`'s seven boundaries,
against the 6.88–6.92 Hz DESIGN §8 records as that profile's measured rate — and frame rate is
part of the firmware↔ML contract, not a free parameter. The 10 ms number was measured on a **12.5×**
adjacent-band power step (P ∝ pulse²×freq); `cal_63`'s bands step ×1.5 and very likely never
needed it. The right shape, if a characterisation profile wants it, is a **per-boundary floor
scaled to the actual energy step**, not a larger global constant. (2026-08-09)

---

### Findings — the band-swap experiment: settling needs ~10 ms, and cell 0's outlier population is a *conjunction*

Two 2026-08-09 sessions under fw v4.34, **two minutes apart**, same pack and same thermal state —
`session_20260809_133725` (`cal_100_10_x15_v1`, 056797db) and `session_20260809_133928`
(`cal_100_10_x15_v1_bandswap`, 2c205e24) — as controlled an A/B as this rig gets. Scored with
`mode2_cell_noise` on the **absolute** 100 mV excursion gate, matching cells across the two runs
by `(freq, pulse, delay)`.

**The cell-0 outlier population is neither cell-bound nor position-bound. It needs both.** The
25 kHz/10 µs @ 5.160 µs cell runs **32.6 events per 1000 sweeps** at sweep position 0 and
**0.0** at position 15 — the same physical cell, same delay, same firmware, minutes apart. So it
does not follow the cell, which rules out a purely analogue, cell-intrinsic mechanism (clamp
release, converter ceiling). But the cell that *takes over* position 0 in the swapped profile —
3.125 kHz/100 µs @ 7.480 µs — is also **0.0**, so it does not follow the position either. The
artefact requires the 25 kHz/10 µs configuration **and** the sweep position that carries the
emit. Neither prediction in the v4.34 entry was right, and the conjunction is the more useful
answer: it is not "cell 0 is noisy", it is "the emit interacts with the low-power band".

**Settling: whichever band gets the emit comes out clean, and both bands need it.** The emit
costs ~6 ms (from the 82.8 ms sweep: 30 cells × ~2.3 ms + 7.8 ms of delivered settle), and it
lands entirely inside the settle window of whichever band sits at position 0. Equivalent timing
jitter for the first five cells of each band:

| band | at position 0 (settle **+ emit**) | at position 15 (settle only) |
|---|---|---|
| 3.125 kHz / 100 µs (4800 µs settle) | 2.1, 2.3, 1.9, 1.5, 1.4 ns | 8.1, 7.8, 5.3, 3.7, 4.1 ns |
| 25 kHz / 10 µs (3000 µs settle) | 2.5, 2.2, 2.3, 2.1, 2.6 ns | 2.4, 5.2, 5.2, 4.3, 5.2 ns |

σ falls 3–4× on the 100 µs band and ~2× on the 25 kHz band. **Both floors are still too short:**
4800 µs and 3000 µs both leave a gradient, and only the extra ~6 ms removes it. The boundary
transient for this 12.5× power step therefore runs **~9–11 ms**, which confirms by *manipulation*
the ~8–10 ms inferred from the v4.33 data. `SETTLE_FLOOR_US` wants to be ≈ 10 000 for a step this
size — measured evidence for the number v4.34 deliberately deferred. Cost would be ~+12 ms per
sweep on this profile and ~+49 ms on `cal_63_air_bat_v3`'s 7 boundaries, so it is a real trade,
not a free win.

**The §17.7 "first-column noise" model needs a refinement.** In the swapped run the 25 kHz band's
*first* cell (position 15) is its **cleanest** at 2.4 ns while its 2nd–5th sit at ~5 ns. Only the
first cell of a band gets a settle `sleep_us` — a fixed, well-defined dwell. Every later cell has
`remaining` go negative (overrun, no sleep at all), so its sample lands wherever ~2.3 ms of
interpreter time happens to put it, while the band is still relaxing. The excess is not "the first
column is bad", it is "cells 2–5 ride the transient with undamped timing". That is why raising the
floor helps them: it moves the whole band past the transient before any of them sample.

**Correction to the v4.34 entry's caveat.** That entry warned the pack had fallen 24.30 → 22.65 V
and would confound the firmware A/B. The 24.30 V is `pimd_classviz`'s operator-entered `pack_v`
header field (`age_s=unknown`), and it is stale and identical in all three sessions. The
**firmware's** own readings are 22.959 V (12:36, in that session's `V` string) and 22.652 V
(13:26) — a 0.31 V change, ~13–16 mV of decay amplitude. The v4.33/v4.34 comparison is therefore
much better controlled than that caveat claimed.

**And the header is not stale data — it is an unimplemented consumer.** `pimd_classviz`'s
`pack_v` is a manually-typed spinbox (`sp_pack_v`, with a `PACK_V_REMIND_S` 20-minute nag), and
the file contains **no** reference to `pack_mV` or `board_temp_dC`: it never reads the firmware's
`P` telemetry or the `V` reply's trailing sensor fields. `pimd_delaycal` has none either.
`pimd_gui` and `pimd_rawlog` do consume them. So the firmware side (the v4.29 calibrated divider,
the v4.33 DS18B20) is real and reporting; the plumbing into the two tools that write capture
metadata simply has not been built yet. Wiring `pack_v`/`board_temp_dC` straight from the wire
into the classviz session header would satisfy §10's "state the window you ran in" automatically
and remove a hand-entered field from the record — worth doing before the next corpus campaign,
and it is a tooling task, not a firmware one.

**What v4.34 actually bought** (identical profile, 62.5 → 76.5 relative-gate events was an artefact
of the moving gate — see the tool v1.01 entry): σ **halved** across the 25 kHz band (×0.50–0.67),
−15…−35 % on the 100 µs band, ch0 equivalent jitter 5.0 → 2.5 ns, and the cell-0 excursion median
132 → 60 mV with the >100 mV rate 43.3 → 32.6 per 1000. A material improvement that did **not**
eliminate the cell-0 population. Sweep 12.49 → 12.07 Hz, against a predicted ~11.8 Hz.
(2026-08-09)

---

### utilities/mode2_noise/mode2_cell_noise.py — v1.01 — absolute-excursion column; the relative gate is not comparable between runs

v1 gated candidate outliers at `4 × robust sigma` of the step series. That finds the anomalous
cell **within** one run, which is what it was built for, but it is actively misleading **between**
runs: the gate moves with each run's own noise, so halving a channel's sigma lets smaller events
start crossing it. On the v4.33 → v4.34 A/B ch0 read **62.5 → 76.5** events per 1000 while sigma
halved, equivalent jitter went 5.0 → 2.5 ns and the median excursion fell 132 → 60 mV — the count
rose because the run got quieter. Reporting that as "the fix made it worse" would have been wrong.

v1.01 adds a second column gated at an **absolute** `ABS_GATE_MV = 100` mV excursion (a single
sample that far out steps an N-deep boxcar by `100/N`, which is what is detected), and keeps the
relative column alongside it. Same-run diagnosis reads the relative column; any A/B reads the
absolute one. The constant carries the reasoning so the trap is not re-entered. (2026-08-09)

---

### mcu/pimd_mcu.py — v4.34 — boundary settling is measured from the config write, not the loop top

`acquire_mode2()` computed its band-boundary settle as
`remaining = period - elapsed - 2` and then `remaining += period * settle_i`, where `elapsed` is
`ticks_diff(ticks_us(), t0)` and `t0` is taken at the **top** of the loop iteration — before
`read_raw_bytes_hold()` and before the freq/CC writes. Every microsecond of `elapsed` was
therefore spent at the **previous** cell's configuration, and it was being deducted from this
cell's settle budget. Delivered settle was `period·settle − (elapsed − period)`, not
`SETTLE_FLOOR_US`. v4.34 captures `t_cfg = ticks_us()` immediately after `enable_irq(_held_irq)`
— the instant cell[i]'s configuration goes live — and sleeps `period·settle` measured from
*there*. Non-boundary cells are untouched, and the v4.26 IRQ-off critical section is not
lengthened (the one new `ticks_us()` call is outside it).

**How far short it fell.** Per-cell interpreter cost is ~2.3–2.4 ms, dominated by the BUSY sync
(DESIGN §7 — the poll loop catches roughly one BUSY-high in six). That is far longer than any
band period above ~400 Hz, so `elapsed` always exceeded `period` and the floor was always
diluted:

| boundary | intended | delivered before v4.34 |
|---|---|---|
| 25 kHz band, 75 periods | 3000 µs | ≈ 600–740 µs |
| 3.125 kHz band, 15 periods | 4800 µs | ≈ 2.7–2.8 ms |

So **`SETTLE_FLOOR_US` was not an absolute floor on any band in any profile in the repository.**
v4.24 was still a real improvement and its bench verification was not wrong — before it the
sleep went *negative* at high-frequency bands and there was no settling at all — but the
mechanism was never delivering the number §8 and §17.7 quote for it.

**What found it.** Hand-tuning `cal_100_10_x15_v1` (2 bands × 15 thresholds, 25 kHz/10 µs and
3.125 kHz/100 µs) showed the first cell of each row with a std dev far above its neighbours —
2.60 mV and 0.89 mV — that would **not move when the delay was nudged all the way down to
2.5 V**. That control rules out timing jitter and decay slope and points at sweep position.
`session_20260809_123634.csv` (3235 frames / 259 s, `profile_sha8 056797db`, 12.49 Hz) was
analysed with the new `utilities/mode2_noise/mode2_cell_noise.py`, which deconvolves the 32-deep
rolling mean to recover single samples. Two distinct signatures, neither delay-dependent:

- **Band 1's first three cells** carry a decaying excess — 10.3 → 11.9 → 6.2 ns equivalent
  timing jitter against the band's own 4.2 ns settled baseline. That is the §17.7 under-settled
  boundary gradient, and it says this profile's boundary transient is still running **~8–10 ms**
  after the switch.
- **Cell 0 alone** carries a discrete single-sample outlier population: **62.5 events per 1000
  sweeps** against 6.8 for the worst other cell in its band, median excursion 132 mV, bimodal at
  ≈ −200 mV and ≈ +120 mV, spread evenly over all 32 residue classes and uniform in time. At one
  event per 8–16 sweeps against a 12.49 Hz sweep this beats at **≈ 0.8–1.5 Hz**, which is the
  "about 1 Hz" wander seen on the bench; each event then holds the displayed mean off for 32
  frames (2.6 s), which is why an 8-frame std-dev window reports it so loudly and why it is
  insensitive to the delay.

**Falsified on the way, recorded so it is not re-checked.** The 1 Hz `SENSOR_SAMPLE_MS`
pack-voltage read is *not* the cause: its exact schedule was reconstructed from the firmware
clock, and those sweeps run +0.34 ms and carry *less* cell-0 movement, not more. DS18B20 fires
16 times in the session. There is no 1 Hz spectral line, and no correlation between excursions
and sweep interval (79.3 ms on event sweeps vs 80.1 ms otherwise). `src/pimd_delaycal.py` has no
defect here — its "Std dev" is the std of 8 consecutive 32-deep rolling means sharing 31/32 of
their samples, so it faithfully amplifies exactly this.

**This fix does not claim to explain cell 0.** The dilution explains band 1's gradient and
explains why cell 0 is fragile, but cell 0 is also the one cell whose settle window contains the
blocking emit `print()`, so it may already be the best-settled cell in the sweep, and a discrete
bimodal population is not what a settling curve looks like. Three candidates remain, in the same
index-locked family as v4.13/v4.20/v4.24/v4.26: residual transient sampled on its varying part;
emit-adjacent interpreter timing (a GC pass at the emit's allocation site, or USB frame
scheduling); or USB TX burst coupling into the front end or the LTC2508 reference — a ~250-byte W
record is four packets and TX activity continues for milliseconds after `print()` returns, through
cell 0's settle and into its conversion. **That last one is an analogue question and cannot be
settled from the code.** `cal_100_10_x15_v1_bandswap.json` is the discriminator: if the population
follows sweep position 0 it is firmware, if it follows the 25 kHz cell it is analogue.

**Cost, and why it is not a silent adoption.** Roughly +2.3 ms per boundary per sweep:
`cal_100_10_x15_v1` 80.1 → ~85 ms (12.5 → 11.8 Hz), and `cal_63_air_bat_v3` with 7 boundaries
~145 → ~161 ms (6.9 → 6.2 Hz) against the 0.1445–0.1455 s §8 records. It also deliberately moves
every band's first-cell operating point. This is an acquisition change of the same class as v4.24
and v4.26: it wants a v4.33/v4.34 A/B under one profile and a delay re-cal of the operating
profile before any corpus capture. `SETTLE_FLOOR_US` and `BOUNDARY_PRIME` keep their values —
make the floor deliver first, then measure whether 3 ms is the right number. Invariants (§11) are
untouched: GPIO4/5 slice-2 phase-locking, the wire format, no scheduler, no flash writes.
(2026-08-09)

---

### utilities/mode2_noise/mode2_cell_noise.py — v1 — recover per-cell single-sample noise from a Mode 2 session

New offline tool. Mode 2 never emits samples — each W record carries a rolling mean `averages`
deep (§9) — so per-cell noise has not been directly measurable from a session dump. But the
firmware adds exactly **one** new sample per cell per sweep, so
`m[i] − m[i−1] = (x[i] − x[i−N]) / N`, which recovers the single-sample series up to one unknown
constant per residue class `i mod N`. Two statistics fall out:

- **Matched-pair outlier detection.** A single bad sample entering the boxcar steps the mean by
  `+d` and, exactly `N` frames later, leaving it steps the mean by `−d`. Requiring both makes the
  test independent of drift, of the per-class constants and of the reconstruction itself — it is
  not something detrending can manufacture. This is the primary statistic and the one the A/B is
  scored on.
- **Equivalent timing jitter.** A cell's σ is meaningless without its own local decay slope: 5 ns
  is 6 mV on a steep cell and 0.4 mV on a flat one. Dividing the recovered σ by dV/dt from the
  neighbouring cells gives nanoseconds, which is flat across a healthy band at the §8 timing
  precision. A cell that stands out in mV but not in ns is behaving normally; one that stands out
  in ns is not. This is what separates "steep slope" from "actually noisy", which is the exact
  confusion that made the bench symptom hard to read.

Robust statistics throughout (`1.4826·MAD`), so an outlier population cannot inflate the estimate
of the population it is being compared against. The tool flags the two signatures by name —
boundary-settling gradient and index-locked outlier population — against each **band's own**
settled baseline rather than a hard-coded expectation, so it travels across bands, pack states and
epochs. Cells below 1 LSB (610 µV) or flatter than 20 mV/µs report `--` rather than a number:
the rail and the ~16.5 mV pedestal (§7) carry no timing information and dividing by their slope
produces four-figure nonsense. It checks the firmware clock for dropped frames, because a drop
breaks the N-frame pairing. `--hist <ch>` adds the excursion-size histogram and the residue-class
control that distinguishes a real discrete mechanism from a reconstruction artefact.

Read-only, pure numpy, no board required. Baseline for the v4.34 A/B:
`python utilities/mode2_noise/mode2_cell_noise.py --hist 0 src/data/sessions/session_20260809_123634.csv`
must report ch0 at 62.5 events/1000 with a 132 mV median and ch1/ch2 at zero. (2026-08-09)

---

### src/data/profiles/cal_100_10_x15_v1_bandswap.json — new — band-order discriminator for the cell-0 outlier population

Diagnostic profile, not a calibration. Byte-identical to `cal_100_10_x15_v1` — same delays,
thresholds and `averages` — with the two bands in the opposite **protocol** order, so
3.125 kHz/100 µs occupies sweep position 0 instead of 25 kHz/10 µs. It answers the one question
the v4.34 analysis could not: whether cell 0's discrete outlier population is locked to the sweep
position (firmware) or to the 25 kHz cell (analogue). This is the same test §17.8 used on the
index-locked σ anomaly, and it needs no code change. `pimd_delaycal` sorts its thermal rows by
`pulse_us` for display and maps back through `_thermal_proto_to_display`, so the table looks
unchanged and only the protocol order moves — the population visibly jumps rows if it is
position-locked. Not to be calibrated against or captured with. (2026-08-09)

---

### References/images — the three `profile8b-*` captures are tracked; the README image was broken on GitHub

`README.md` has always opened with `profile8b-spanner-copper.jpg` as its lead figure, but
`.gitignore` excluded `References/images/profile8b-*`, so the file existed only on the author's
disk and **GitHub rendered a broken image** — the first thing a visitor to the repository saw.
The markdown was never at fault. Rule dropped and all three captures committed.

**The rule was not arbitrary, and the reason it existed still applies to the content.** Its
comment recorded these as *previous-epoch* captures whose DESIGN.md §15 rows were deliberately
dropped at Doc-rev 1.8. Publishing them fixes the README but does not make them current: they
predate the enclosure, the 6S supply and both `cal_63` epochs, so the 8×9 matrix in that figure
is not what the rig produces today. It is being used as an illustration of *what the display
looks like*, which it still serves, rather than as evidence about the present instrument — worth
knowing before anyone cites it as data. The other two (`profile8b-spanner.jpg`,
`profile8b-copper-pipe.jpg`) are committed alongside it so the directory is not half-ignored,
which is the state that produced this bug.

No DESIGN.md change: §15 rows for previous-epoch assets were removed by a deliberate decision at
Doc-rev 1.8 and reinstating them is a consolidation-pass call, not a side effect of fixing an
image link. (2026-08-08)

---
## Archive — consolidated 2026-08-08

### utilities/decay_model/decaymodel.py — v5 — model refitted to the scope; below-rail reconstruction; file halved

**The model is now measured rather than inferred.** v1–v4 fitted air to the calibrated `cal_63`
ladder, which only samples the volt-scale region, then extrapolated past it — the failure already
recorded on 2026-08-07, where fits agreeing with that ladder to ≤ 2 % predicted anywhere from
+64 to −400 mV at sd 14.7 µs. v5 drops the ladder and fits the 2026-08-08 scope capture of the
LT6203 input, which covers the whole decay including the part the ADC cannot see.

Two real poles with opposite-sign residues plus the measured quiescent DC,
`s(t) = A·exp(−t/τf) − B·exp(−t/τs)`:

| | |
|---|---|
| τ_fast | **1.125 µs** |
| τ_slow | **2.270 µs** (ratio 2.02) |
| ζ | **1.06 — mildly overdamped** |
| residual vs the scope | **RMS 0.87 mV**, max 2.70 mV, over 894 points |
| single zero crossing | sd 13.92 µs modelled, ~14.0 µs measured |

**The component values it implies are an independent check, not an input, and they land.** With
R1 = 1.3 k: **C = 579 pF, L = 4.41 mH, √(L/C) = 2762 Ω → R_crit = 1381 Ω**, against DESIGN §7's
*measured* 1300–1400 Ω critical-damping value, and L close to the stale 3.9 mH. Two quantities
measured years apart by different means agreeing to a few per cent is the reason to trust this
fit. It also supersedes the "ζ = 1.00" of 2026-08-07 for the reason given there: that came from
assuming the critically-damped form and fitting τ = 2RC to it, which cannot report anything else.

**Below-rail reconstruction added.** The scope measures the input, where nothing is clipped, so
multiplying by the input→ADC gain (1.149, from the two quiescent levels) gives what the ADC
*would* have recorded with no output floor. Air really reaches **−16.9 mV in ADC terms** — against
a recorded 2.441 mV — and is below the rail for **4.21 µs, sd 14.23–18.44**. The figure draws that
explicitly, shaded, so the difference between what the instrument records and what the front end
does is visible rather than argued.

The chart is rebuilt around that: full span in ADC terms with the reconstruction and the three
measured classes; the null with the hidden region shaded; and a residual panel, which shows the
one place the model is imperfect — it runs a mean **−0.59 mV** below the measured tail over sd
25–98 µs, i.e. the slow pole is slightly too fast. Left as-is and reported rather than patched
with a third term.

**Comments cut roughly in half** at the same time: **1023 → 489 lines**, 35 comment lines. The
removed material was historical justification that has since been settled and is recorded here —
why the anchors went, why the plateau path exists, what each earlier version got wrong. What is
kept is the load-bearing kind: why the probe column is chosen from the data, why roles come from
`material_class`, why smoothing trims its ends. Three fixes fell out of the rebuild, all
artefacts of my own plotting rather than the data: the MCLK ring was not masked in the wide
capture, `np.convolve(mode="same")` tapered the trace ends toward zero and invented a step, and
smoothing spanned the masked ring gap. Verified across model-only, bracketed-session and
plateau-fallback runs. (2026-08-08)

---

### findings — a ferrous target fills the null in completely, and railed cells under-report target deltas

Follow-up to the entry below, same scope session and settings (DHO1204, CH1 = LT6203 input,
CH2 = MCLK, sd 15.5 µs, 2 kHz / 100 µs). Adjustable spanner 250 (steel, 271 g) resting **on** the
coil; 83 CH1 traces averaged over 169 s, trace-to-trace scatter 0.60 mV. Figure and CSV in
`References/scope/spanner_fills_the_null_20260808.png` / `spanner_vs_air_20260808.csv`.

**The lobe carries target signal, so it is coil physics — the question is now closed from both
ends.** The entry below showed the lobe exists *before* the amplifier; this shows it *responds to
metal*. No-spanner air swings negative from sd 14.3 to 17.8 µs and bottoms at **−15.0 mV**; with
the spanner on the coil the trace **never crosses zero at all**, with a minimum of **+15.5 mV**.
The difference peaks at **+48 mV around sd 13.6 µs** and is still +16 mV at sd 22. An instrument
artefact — amplifier recovery, clock feedthrough, anything downstream of the coil — cannot do
that.

**New, and it bites the corpus: where air is railed, the ADC under-reports the target delta.**
Comparing the true delta at the amplifier input against what the sweep recorded through the same
window:

| sd (µs) | air (ADC) | Δ recorded by the ADC | Δ at the amplifier input |
|---:|---:|---:|---:|
| 14.86 | 9.12 mV | +40.7 mV | ~+43 mV |
| 15.46 | 2.44 (railed) | +24.0 | ~+33 |
| 16.06 | 2.44 (railed) | +12.6 | ~+27 |
| 17.26 | 3.66 | **+6.3** | **~+22** |
| 21.61 | 5.19 | +19.6 | ~+16 |

The mechanism is simple and one-directional: Δ = target − air, and when the air baseline is
clipped up to the 2.44 mV floor the subtrahend is too large, so **the delta is always
under-stated, by up to ~3.5×**. Previous entries called these cells "worthless as a calibration
point" and "not dead cells, just cells where every millivolt is target". Both understate it —
those cells actively **compress** measured target amplitude, and anything derived from them
(band means, crossing widths, any amplitude feature) inherits a non-linear, target-strength-
dependent bias. This is a reason to exclude railed cells from feature maths, not merely to avoid
calibrating on them.

**A corollary that softens the operating note:** the rail is an *air* problem. A strong ferrous
target lifts the whole trace clear of it, so the same cell that is dead in air is perfectly live
on a close target — which is exactly what the 2026-08-03 close-target run saw from the other side.
The right test for whether a cell is usable is therefore whether **air** is railed there, not
whether the cell ever reads low.

**Two corrections to my own working, both caught in the analysis and both mine.** (1) The polling
script computed the time axis without `xorig`, mislabelling the spanner traces by +3 µs; the
pairing was correct but the first comparison table I produced was labelled wrong and was
discarded. (2) I first quoted the air bottom as −19.8 mV using a ±90 ns mask around the MCLK
edge. The edge ring is **asymmetric** — sharp before the edge, ~250 ns of tail after it — so
±90 ns still included ringing. With a ±250 ns mask the bottom is **−15.0 mV** (−13.7 smoothed
across the gap), which is what the operator read off the screen directly. The masking width is
now recorded on the figure.

**Paired reference captured, and the earlier caveat is now closed with a number.** The first
comparison used a no-spanner trace from ~30 minutes earlier, because the spanner was already in
place when the watch began. The spanner was then lifted and 83 air traces taken in the same run,
minutes after the spanner set, at identical settings. **The paired air agrees with the earlier
reference to RMS 1.5 mV, max 3.6 mV** across the whole window — against a target effect of up to
49 mV, so the unpaired conclusion was safe by better than 13×. Paired numbers, which supersede
the earlier ones only in precision: air bottoms **−14.75 mV at sd 15.79 µs** with zero crossings
at **14.29 and 18.00 µs**; spanner bottoms **+15.45 mV** with **no zero crossing**; largest
difference **+48.9 mV at sd 13.57 µs**. Run-to-run scatter 0.31 mV (air) and 0.60 mV (spanner),
so every number above is far outside the noise. Both states are in
`spanner_vs_air_20260808.csv` along with the earlier reference.

Still open, and now the obvious next probe: whether the MCLK-edge ring exists in the circuit as
well as between scope channels. If it does, the ADC samples on that edge and captures the kick.
(2026-08-08)

---

### findings — SETTLED by scope: the negative lobe is at the amplifier INPUT, and so is the pedestal

Rigol DHO1204 over LAN (192.168.2.161, raw SCPI on 5555), `pimd_gui` Mode 1, 2 kHz / 100 µs,
sample delay 15.5 µs. **CH1 = LT6203 input (post-R8); CH2 = MCLK, whose rising edge is the ADC
sample instant** — so scope t = 0 is sd 15.5 µs and the whole trace reads directly in sample
delay. Scope state was saved before and restored after; timebase and CH1 range were changed for
the wide captures and put back. Traces kept in `References/scope/`.

**This closes the question open since 2026-08-05: it is the front end, not the amplifier.** The
negative excursion is present *before* the LT6203, so it cannot be output overload recovery. At
the input it spans **sd 14.3 → 17.8 µs** (zero crossings, ~3.5 µs wide) and bottoms at
**≈ −15 mV**. Both entries below that leaned on "amplifier recovery" as the likely explanation —
including the one that argued the coil poles had no room for it — are wrong on that point.

**The −31.4 mV apparent minimum is not signal, and the operator called it before the analysis
did.** It is a **70 ns FWHM** spike sitting exactly on CH2's ~10 ns MCLK edge — three orders of
magnitude faster than the 3.5 µs feature it sits inside — i.e. crosstalk from the adjacent
channel, not circuit behaviour. Masking ±90 ns around the edge leaves a smooth lobe bottoming at
−14 to −15 mV. Worth keeping in mind for any future scope work at this node: the trigger channel
carries a fast logic edge and the interesting signal is tens of mV.

**The ~16.5 mV pedestal is also a front-end DC level.** The input's quiescent value out past
sd 60 µs is **+14.34 mV**, against the ADC's 16.472 mV pedestal — the offset exists *before* the
amplifier. That retires the 2026-08-05 entry's alternatives: it is not amplifier Vos and not ADC
offset. It is consistent with that entry's preferred mechanism (input bias current through the
front-end resistance), which was explicitly flagged there as "inferred from the datasheet and the
measured level — not measured". It is measured now, at the node. The pedestal-to-quiescent ratio
is 1.15, so the path is near unity gain — but that is two anchor points from captures ~2 h and
one pack-state apart, so treat it as an order check, not a calibration.

**Why the output rails.** The input swings ~29 mV below its own quiescent level. At near-unity
gain that puts the output well under the LT6203's ~2.44 mV output floor, which is exactly the
railed value the sweep measures over sd 15.46–16.66 µs. The rail width does not match the input
excursion cell-for-cell, which is expected: the ADC sweep is the raw path two hours earlier at a
different pack voltage, and the sweep samples the region at only three delays.

**What this implies about damping, and a correction to the 2026-08-07 arithmetic.** A ~3.5 µs
lobe at the input fits a slow real pole of ~2–3 µs alongside the fast decay — which is what
L/R1 gives (3.9 mH / 1.3 k ≈ 3 µs), i.e. the **two-real-poles-with-opposite-sign-residues** shape
the 2026-08-05 entry proposed. The 2026-08-07 entry's "ζ = 1.00" came from *assuming* the
critically-damped form and fitting τ = 2RC to it; with L = 3.9 mH and C = 354 pF the network is
slightly **overdamped** (α = 1.09×10⁶, ω₀ = 8.51×10⁵, ζ ≈ 1.28, poles at τ ≈ 0.57 and 2.44 µs),
and the 2.44 µs pole is the right scale for the observed lobe. That conclusion still rests on the
stale 3.9 mH, so §7's "re-measure RX self-resonance to pin L and C" is now the gating measurement
for the whole front-end model rather than a loose end. **What survives from 2026-08-07 unchanged:
the undershoot is not fixed by changing R1, and damping remains the wrong knob** — the lobe is
the network's own slow pole, not a ringing artefact.

Open and now cheap to answer, since the rig is instrumented: whether the lobe carries target
information at the input (present a target and watch this node), and whether the MCLK-edge
crosstalk exists in the circuit as well as between scope channels — if it does, the ADC samples
on that edge and would capture the kick. (2026-08-08)

---

### findings — first dense sweep: the lobe resolved, the polarity split located, and the ladder is ~0.4 µs off for this pack state

`rawlog_20260808_145702.txt`, 100 µs / 2 kHz, 68 cells, fw 4.33, 711 frames, pack **24.13 → 24.04 V**.
First capture with the bracketed logger (`pimd_rawlog` v1.16) and the dense sweep: air / copper
pipe / air / steel spanner / air, 20 frames each, all `complete=yes`, **targets at 0 mm** (resting
on the coil). Every segment read from its own brackets — no inference.

**Air, resolved.** Clamped through sd 7.168 µs; 4950.9 mV at 7.568; **44.4 mV at 14.264 → 9.1 at
14.864**; bottoms at **2.437–2.441 mV across sd 15.46–16.66 µs**; 3.66 at 17.26; 5.19 at 21.6;
10.18 at 23.6; 15.27 at 30.8; settles at **16.472 mV** from ~37 µs and holds to 311.7 µs.

Three numbers that were previously estimates are now measurements:

- **The air pedestal crossing is at sd ≈ 14.64 µs** (log-interpolated between the two bracketing
  cells), against the session's own settled level of 16.472 mV rather than the §14 constant.
- **The rail flat is ≥ 1.2 µs wide** — three consecutive cells at 2.437/2.441/2.441 mV with σ
  exactly 0. The 2026-08-05 hand-read estimate off a live trace was 0.5–1 µs; it is wider than
  that. Note 17.264 and 19.760 µs also have σ = 0 but sit at 3.662 and 4.272 mV — 6 and 7 LSB of
  the 610.35 µV raw quantum, so those are quantisation-locked, not saturated.
- **Air does not reach the pedestal until ~37 µs**, far later than the ~21 µs the v1 model implied.

**The polarity split is located, and it is a window, not a column.** Steel and copper carry
opposite signs across **sd 7.968–12.304 µs**, widest at **9.568 µs: steel +46.5 mV, copper
−74.4 mV**. Past that the copper delta itself **crosses zero at sd ≈ 12.425 µs** and both targets
read positive thereafter. That crossing is a per-material coordinate the 2026-08-07 capture could
not see at all — it had two usable pre-rail cells and this has 26.

**Copper overtakes steel at ~44 µs** and stays ahead: at sd 311.7 µs copper is **+1.375 mV** over
air against steel's **+0.036 mV**, on a 0.08 mV air σ. Same ordering as 2026-08-07 (crossover
~77 µs there, at 60 mm) — the crossover moves with coupling, which is worth a controlled distance
series rather than an inference from two points.

**Actionable: the ladder is positioned ~0.4 µs early for this pack state.** The crossing region
was placed against the 2026-08-07 measured rail of 14.712 µs, but at 24.13 V the rail sits at
15.46–16.66 µs and the crossing at 14.64 µs — so the fine 0.16 µs cells end at 14.224 and the
crossing falls in the **0.600 µs gap** to the first rail-region cell. It was still bracketed to
0.6 µs, which is why the number exists at all, but the region should follow the pack. The
2026-08-07 session ran at **22.04 V**; ~2 V of pack moved the features ~1–2 µs later, which is
larger than the crossing region is wide. `MEASURED_RAIL_US` in the generator is therefore a
pack-state-specific constant, not a band constant, and should be re-derived per epoch — or the
region widened to cover the range. **Not changed here**; it needs a deliberate decision about
which pack state the profile is centred on.

Also note the capture used a superseded 68-cell ladder (the live file is now 66) and its `META`
name field reads `late / target` from the v2 shadowing bug, so the log cannot identify its own
ladder. Reconstructed and verified as `sweep_100us_asbuilt_20260808.json` — 68 cells, clamped and
railed cells landing exactly where the regions predict — so the capture stays analysable.
(2026-08-08)

---

### utilities/decay_model/decaymodel.py — v4 — roles from `material_class`, probe column chosen from the data, figure text de-hard-coded

Running v3 against the first dense capture surfaced four defects, three of which produced wrong
output rather than an error.

1. **Ferrous/non-ferrous roles were assigned by insertion order.** This session presented copper
   first, so copper was painted with the ferrous colour and the crossover search looked for a sign
   change in the wrong direction and returned `nan`. Roles now come from the log's own
   `material_class` field, which `pimd_rawlog` already writes into every target marker. A target
   with no `material_class` is reported and treated as non-ferrous for colouring only.
2. **The probe column for the plateau fallback was hard-coded to index 3.** That is a good
   post-rail cell in `cal_110`'s 150 µs band and a **clamped** cell in the 100 µs sweep — constant,
   no excursion to find, so the whole session became one active run and there were no air frames
   left, crashing. The column is now chosen from the data as the best excursion-to-MAD ratio among
   unclamped, non-constant columns.
3. **Figure text was hard-coded to the first dataset** — "targets at 60 mm", "2026-08-07 session",
   and a fixed rail value. All now derived from the session: distance and material from the MARK
   fields, date from the first frame, rail and crossing from the data.
4. **`order[2]` assumed exactly two target classes**, crashing on a single-target session.

Also adds the air pedestal crossing to the printout — the coordinate the dense ladder exists to
measure — computed against the session's own settled level rather than `PEDESTAL_MV`, since that
constant is a 2026-08-03/05 figure and this session settles at 16.472 mV. The polarity-split
search judges significance against the **settled-region** noise, not air's per-frame σ at the
cell: on the steep pre-rail slope that σ is slope × timing jitter (26 mV here, §14.3) and a
3σ gate on it rejects a genuine +46 / −74 mV split. Verified against four inputs — the real
bracketed session, a plateau fixture (end markers stripped), a single-target fixture, and
model-only. (2026-08-08)

---

### utilities/decay_model/make_sweep_profile.py — v3 — cal_110 anchors dropped, crossing region tightened, junctions guarded; both profiles regenerated

**The anchors are gone, and the rule that put them there was wrong.** v1/v2 forced the eleven
`cal_110_full_range_v4` delays of the matching band into the ladder so captures would stay
"directly comparable" to `rawlog_20260807_194234.txt`. Measured, that bought nothing. Sampling the
2026-08-07 air curve onto the anchor-free ladder and interpolating back to the anchor delays
recovers them to **≤ 0.05 mV past sd 20 µs** and **0.000 mV from 62 µs out**, against target
deltas of 0.09–7.1 mV. The one large residual, **+2.7 mV at sd 10.912 µs**, sits on the steep
slope where that cell's own frame-to-frame σ is **7.8 mV** — the interpolation error is inside the
cell's own noise. The railed cell cannot be interpolated meaningfully and carries no information
anyway.

Against that, the anchors cost **10 cells at 150 µs and 11 at 100 µs, ~15 % of the ladder**, and
crowded it: `15.448 → 15.600 µs` was a 0.152 µs gap inside a region whose step is 0.600 µs, so one
of that pair was wasted. They also coupled this profile to another profile — the coupling that
broke silently when the 150 µs file was hand-retargeted to 100 µs and kept the wrong band's
anchors (0 of 11 correct). **And the comparability claim was overstated when written:** that
session ran 110 cells at 4.07 Hz with a 7.9 s rolling window against this profile's 7.6 Hz and
4.2 s, on a different pack state and soak, and DESIGN §10's `(profile_name, profile_sha8)` guard
exists precisely because cross-profile comparison is not automatically valid.

**The freed cells went into the crossing region**, which is the one that decides the crossing
time — the pack-independent coordinate. It goes from **11 cells at 0.240 µs to 17 at 0.160 µs**
(1.5× finer) and now runs up to the rail region instead of stopping at 14.810 µs and leaving the
plunge to be covered at 0.600 µs. Net 66 cells (was 72), ~132 ms, ~7.6 Hz, 4.2 s rolling window.

**`MIN_GAP_FRAC` guards region junctions.** Region boundaries do not land on each other's grids,
and the first build after dropping the anchors put the crossing region's last cell 0.040 µs before
the rail region's first — 4× tighter than the finer of the two steps, i.e. exactly the defect the
anchors used to cause. A cell is now dropped if it sits closer than 0.75 × the finer local step to
its neighbour. The region boundaries were then aligned so every junction gap equals the finer
step, and the guard stops firing — it is a safety net, not a workaround, and it is checked by the
per-region cell counts in the printout.

**One bug found by the validation pass, worth recording because it is the same defect this work
flagged in a hand-edited file.** v2 parameterised the profile name, and the per-region reporting
loop then shadowed `name`, so both regenerated JSONs were written with
`"name": "late / target"` — the last region's label. `pimd_rawlog` copies that field into every
session's `META … name=` line, so every capture would have been mislabelled. Fixed (loop variable
renamed) and now **asserted in the generator** before the file is written, so it cannot regress
silently.

Both profiles regenerated and validated end to end: 66 cells each, correct `name`, no off-grid
delays, gaps 0.160–41.936 µs, every cell passing the firmware's own `compute_pulse_duties` /
`pulse_duties_valid`, `D` line 471/473 chars round-tripping losslessly through the MCU parser, no
`threshold_v`, and worst-case `pulse+delay+0.904` of 412.6 µs (100 µs) and 463.4 µs (150 µs)
against the 500 µs period. (2026-08-08)

---

### utilities/decay_model/make_sweep_profile.py — v2 — `--pulse` / `--freq`; regions positioned against the band's measured rail

The v1 generator hard-coded 150 µs: the pulse width, the output name, and the eleven
`cal_110_full_range_v4` anchors. Retargeting it to another band by hand-editing the JSON — which
is what happened to `sweep_150us_decay_v1.json`, now on disk as `sweep_100us_decay_v1.json` with
`pulse_us` changed to 100.0 — leaves three things wrong that the file itself cannot show you:

1. **The internal `name` still reads `sweep_150us_decay_v1`.** `pimd_rawlog` writes that field
   into every session's `META profile=… name=…` line, so every capture would be stamped with the
   wrong band.
2. **The ladder is still positioned for the 150 µs band.** The measured air minimum is at
   sd 14.712 µs at 100 µs drive against 15.448 µs at 150 µs, so the fine steps land ~0.74 µs late
   — the crossing region's 0.24 µs resolution is spent just past where the crossing is.
3. **The anchors are the wrong band's.** `0 of 11` of cal_110's 100 µs delays appear in the
   hand-edited file, so it is no longer a superset and captures are not directly comparable to
   the 100 µs band data already measured.

v2 takes `--pulse` and `--freq`, derives the output name and path from the pulse width, pulls the
anchors from the matching `cal_110_full_range_v4` band, and shifts all six regions rigidly by the
difference between that band's measured rail position and the 150 µs reference
(`MEASURED_RAIL_US`, from the 2026-08-07 session). It **refuses** to generate for a pulse width
with no measured rail rather than guessing an offset — the regions are positioned against a
measured feature, and inventing one would be the same error as cal_110's threshold labels.
Regenerating at 100 µs gives 72 valid cells, all 11 anchors present, drive duty 13107 fixed, last
cell sd 311.736 µs → `pulse+delay+0.904` = 412.6 µs of 500. `--pulse 150` still reproduces v1's
output exactly (shift 0.000). (2026-08-08)

---

### utilities/decay_model/decaymodel.py — v3 — `--session` prefers the log's acquire/end brackets; plateau detection becomes the fallback

Completes the loop opened by `pimd_rawlog` v1.16. `load_session()` now has two segmentation
modes and picks by what the log contains, so a recorded extent is never quietly replaced by an
inferred one:

- **bracketed** — taken whenever the log has any `MARK acquire end` line. Each acquisition is
  read verbatim between its own start and end markers, repeated segments of one label are
  concatenated (two air captures either side of a target become one air set), and nothing is
  inferred at all.
- **plateau** — the v2 behaviour, kept unchanged for pre-v1.16 logs, which have no end markers
  and where the extent genuinely has to be recovered from the probe cell.

The mode is returned, printed in the header, and stated on the figure, so the two can never
disagree silently — a log either has brackets or it does not.

**The bracketed path checks the log against itself rather than trusting it.** The end marker
states `frames=`; the reader counts the frames actually inside the bracket and warns on any
mismatch, because silently believing either number would be the same class of mistake the
brackets exist to remove. It also warns on `complete=no` (keeping the data, labelled short, with
the reason), on an end marker naming a different target than its start, on end markers with no
start, and on a start left open at EOF — which is **skipped**, not guessed at.

Frame selection is `start < t <= end`: the start marker is written before any frame is counted
and the end marker just after the last one, so that half-open form recovers exactly the captured
set. Verified by re-marking the 2026-08-07 session at the plateau boundaries and running both
paths over it — **the bracketed reader reproduces the plateau means exactly** (61 and 70 frames,
`allclose` on all 11 cells), which is the check that says the new path is right rather than
merely different. The integrity warnings were each provoked deliberately and confirmed to fire,
and the unclosed-start case confirmed to skip the segment rather than include a partial one.

Also adds `--profile` (default `cal_110_full_range_v4`) so a session streamed with
`sweep_150us_decay_v1` can be read with the right channel layout — v2 had the profile name
hard-coded, which would have mis-sliced the channel vector for any other profile. No change to
the model, the fit, or the figure's construction. (2026-08-08)

---

### src/pimd_rawlog.py — v1.16 — FIX the grid could force the window off-screen; acquisitions become fixed-length and bracket themselves

Two changes, both surfaced by loading `sweep_150us_decay_v1` (72 delays on one band).

**1. FIX: the last-frame grid set the window's minimum width, and it could not be dragged back.**
`lbl_grid` was a `QLabel`, and a QLabel reports its full text extent as its size hint — a layout
cannot shrink below that. One band of 72 delays is ~720 monospace characters, several times a
3440 px screen, and with the window origin saved at x=1957 most of it was off the right-hand
edge. Measured after the fix: **window minimum width 778 px**, and identical for
`cal_110_full_range_v4` (10 bands × 11) — the width is now independent of the profile.

The numbers moved to a read-only, **non-wrapping** `QPlainTextEdit`, which has a small minimum
width whatever it contains and scrolls horizontally instead; the prose header stayed a QLabel and
now word-wraps. This is the third attempt at this bug and the first that addresses the mechanism:
v1.11 turned on word-wrap (a comma-separated numeric row has no break points), v1.12 truncated the
text (bounds the width by discarding the data you opened the pane to read). Height is set from the
band count and clamped at `GRID_MAX_ROWS = 12`, so the pane is 38 px for a single-band sweep and
164 px for cal_110 rather than claiming a text editor's default. Horizontal scroll position is
preserved across frames — the pane repaints several times a second and resetting it would make a
scrolled-to column impossible to watch. Values are now selectable, which is a free side effect
worth having at the bench.

**2. "Settle window (frames)" becomes "Capture frames", and an acquisition ends itself.** Pressing
Acquire Target/Air now starts a capture of exactly that many streamed frames and writes
`MARK acquire end mode=… [target_id=…] frames=N requested=M complete=yes|no reason=…`
automatically when the count is reached. The operator's model is the one that changed: the settle
figure tells you when it is steady enough to press, and the press then takes a defined number of
samples to average offline — rather than opening a segment of indefinite extent.

**This closes a defect in the record, not just an inconvenience.** A `MARK acquire` recorded the
state *from that point on* with nothing to close it, so the log said when a segment began and
never when it ended, leaving every analysis pass to infer the extent — and inferring wrong is not
a small error. In `rawlog_20260807_194234` the second Fe marker landed ~9 s after the spanner was
already away; segmenting on the markers as written mixes ~30 s of air into the target window and
reports Δ at sd 21.88 µs as **+3.5 mV**, sign-flipping depending on which air segment is used,
against **+7.12 mV** from the actual plateau. Bracketed segments remove that class of mistake from
the log itself.

Details that matter: `frames`/`requested`/`complete` record what was *actually* captured, so a run
cut short by a second press, a Stop or a window close is labelled short rather than silently
truncated (`reason=superseded|stopped|session-closed`). The start marker is written **after** the
previous segment's end, inside `_begin_acquisition`, not by the callers before it — writing it
first emits the new segment's start ahead of the old one's end and the log stops reading as
brackets, which is the whole point; verified by walking a synthetic log and asserting the nesting
depth stays in {0,1} and returns to 0. `_scan_session_file` treats `acquire end` as closing, so a
resume does not re-arm a finished segment; **logs written before v1.16 have no end markers and
still resume exactly as they did**, since "last acquire marker, open to EOF" is what they meant at
the time. A resumed open segment is re-armed for a fresh full count, because the frames it already
captured are in the previous file.

**The settle indicator is now decoupled from the spinbox** (`SETTLE_WINDOW_FRAMES = 20`, fixed).
They answer different questions, and tying them was actively broken once the capture range went to
2000: a 500-frame capture gave a settle figure that needed ~5 minutes at 6.9 Hz to fill before it
read anything. The settings key is now `capture_frames`, falling back to the old `settle_window`
so an existing `rawlog_settings.json` keeps its value. Verified headless (offscreen Qt) across
completion, supersede, stop, resume, and pre-v1.16 back-compat. No firmware or wire-protocol
change — DESIGN §9/§11 untouched. (2026-08-08)

---

### profile — sweep_150us_decay_v1.json — single-band 150 µs ladder built to model the decay, not to detect

New profile in `src/data/profiles/`, plus the generator that produced it
(`utilities/decay_model/make_sweep_profile.py` v1 — the ladder's rationale lives in code, so it
can be re-derived rather than re-guessed). **One band, 2 kHz / 150 µs, 72 delays, averages 32** (66 as of v3 — anchors dropped, crossing region tightened).
Not a calibration and not a detection profile.

**The problem it solves.** `cal_110_full_range_v4`'s 150 µs band places exactly **two** columns
between clip release and the rail — 7.904 and 10.912 µs. Everything else on that band is clamped,
railed, or pedestal. Two points cannot constrain a decay, and the 2026-08-05/08-07 analyses failed
for exactly that reason: fitting the four calibrated cal_63 columns with τ_s pinned at different
values produced fits agreeing with the data to ≤ 2 % that predicted anywhere from **+64 mV to
−400 mV** at sd 14.7 µs. The fix is samples, not a better model. This ladder puts **26 cells in
7.9–15.4 µs** where cal_110 has 2.

**Six regions, each sized to the feature it has to resolve** — deliberately not one geometric
rule, since a single geometric ladder is what under-sampled 8–15 µs in the first place:

| region | cells | span | what it is for |
|---|---:|---|---|
| clamp exit | 6 | 7.040–7.840 µs | clip release on this band is currently **unmeasured** — cal_110 has no cell here at all, and the figure in use is the 100 µs band's 7.392 µs plus an extrapolated shift |
| decay / τ | 12 | 7.904–12.304 µs | 0.4 µs steps ≈ 0.43 τ, ~5 e-folds across the region — enough to pin τ and to separate `(a+bt)·exp` from one exponential from two |
| crossing | 11 | 12.400–14.800 µs | the pedestal crossing, never sampled (892 mV at 10.912, railed by 15.448). Crossing *time* is the pack-independent coordinate, so this is the highest-value region |
| rail width | 9 | 15.000–19.800 µs | the lobe's depth is unmeasurable through a unipolar path, but the **width of the flat bounds it** — the 2026-08-05 observation was hand-read off a live trace and has never been measured |
| recovery | 10 | 20.496–44.520 µs | τ ≈ 4.2 µs currently rests on **two** points; ten decide whether it is one exponential or several — one mechanism or more than one |
| late / target | 14 | 48.000–312.472 µs | pedestal sag and the discrimination window, where copper overtakes steel near 77 µs. **Extended past cal_110's 250 µs stop** — the rep rate allows ~349 µs and copper was still +0.40 mV at 250 |

**~~It is a strict superset of the band it replaces.~~ SUPERSEDED 2026-08-08** — the anchors were
dropped in `make_sweep_profile.py` v3 and this profile regenerated without them. Measured, they
were worth ≤ 0.05 mV past sd 20 µs while costing ~15 % of the ladder; see that entry. The
comparability claim was also overstated: sweep rate, rolling-window duration, pack state and soak
all differ from that session regardless of delay alignment.

**Why 72 cells is affordable on one band when 110 across ten bands cost 246 ms.** The firmware's
`needs_settling` is `at_boundary or dd != cells[prev][2]` — with one frequency and one pulse width
the drive duty is identical for every cell (19660) including the wrap-around, so
`BOUNDARY_PRIME`/`SETTLE_FLOOR_US` never fire. There is no per-pulse energy step for settling to
absorb; only the sample compare value moves. Estimated sweep ~144 ms (~6.9 Hz) at cal_110's
measured 2.24 ms/cell, giving a ~4.6 s rolling window at averages 32 — **shorter** than cal_110's
7.9 s, so less drift inside the average, not more. **Estimate, not measured — confirm on the
bench.**

**Validated offline against the firmware's own arithmetic.** `compute_pulse_duties` and
`pulse_duties_valid` are reproduced verbatim in the generator: all 72 cells pass, all land on the
8 ns grid, and the `%.3f` µs wire format round-trips losslessly through the MCU's own `D` parser.
The `D` line is 517 chars against cal_110's ~780, which already works. Worst-case cell is
sd 312.472 µs → sample duty 60734/65535, `pulse + delay + 0.904` = 463.4 µs of the 500 µs period.

**No `threshold_v`, deliberately.** The field is vestigial for streaming (`pimd_rawlog` never
reads it, `pimd_classviz` guards on its absence). cal_110's copy was carried over unverified and
is wrong by a large factor — its "0.5 V" column at 62 µs sits on the pedestal, because 0.5 V is
reached near 11.5 µs. Inventing a fresh ladder here would repeat that error. **Consequence:
`pimd_delaycal` will refuse to import this profile** ("Profile has no threshold_v field"), which
is correct — it is a characterisation sweep, not a calibration. (2026-08-08)

---

### src/pimd_rawlog.py — v1.15 — pack volts, board temperature, firmware version and firmware alerts on screen

Reported from the bench: the raw logger shows no pack voltage or board temperature. Verified
first against a real 2 m 45 s session (`rawlog_20260807_190829.txt`) that the data was being
*captured* correctly — two `P` records, 60.084 s apart against the firmware's
`SENSOR_REPORT_MS = 60_000`, carrying 22.138 V / 51.3 °C and 22.126 V / 50.0 °C, both real
readings rather than the `TEMP_INVALID_DC` sentinel. So this was never a logging or firmware
fault: the tool wrote every line faithfully and simply never looked at any of them. Its parser
branched on `W` and `D OK` only, and there was no `P` branch anywhere in the file.

Adds a sensor row under the port field, at information parity with `pimd_gui.py`'s gauges: pack
volts with SoC % and zone caption, board temperature, firmware version (board ID on the tooltip),
and an alert line for `PACK:` / `LOCKOUT` / `Command Input ERROR`. Rendered as **text, not
painted gauges** — this tool is deliberately dumb, and a number you can read off and paste into a
Note beats a bar you have to eyeball. The SoC/zone maths is duplicated from `pimd_gui.py` rather
than imported, keeping each PC app standalone exactly as `_build_d_command()` already is; a
parity test over 19–26 V confirms the two agree to the percent and the caption. Only the zone
*colours* differ, and deliberately: the GUI's are pale fills sitting behind dark text, which are
illegible as text colours, so the clean-window and transition entries are darkened.

`V` is sent **once, on connect**, to prime the row rather than leave it blank for up to a minute
until the first unsolicited `P`. It is deliberately not polled on a timer: the whole value of this
tool is that the logged stream is what the firmware sent unbidden, so nothing is injected once
streaming is running. Pack and temperature then refresh from `P` every ~60 s, and a lockout
announces itself on the wire. Sensors are cleared on disconnect so a stale reading cannot outlive
the connection that produced it. **The log file format is unchanged** — parsing feeds the display
only, and every line is still written verbatim, sentinel and all, which is what an offline pass
should be reading.

Two traps taken directly from `pimd_gui.py` v4.17's scars. The `P` branch is guarded with
`raw[1:2].isdigit()`, because a bare `startswith('P')` also matches `PACK:` messages and the
`Pulse Induction Metal Detector v…` boot banner. And the lockout latch is matched narrowly
(`LOCKOUT:` or the literal `lockout latched`) rather than by a substring test for `lockout`,
which would have caught `PACK: present again at … mV — lockout cleared …` and latched the state
that line exists to retire — an inversion caught during review, before it reached the bench.
That message now explicitly *clears* the latch.

Tested headlessly by feeding lines through the real `read_from_serial()` dispatch with a stubbed
port: the session's own two `P` records render correctly; the boot banner and all `PACK:`
variants leave the pack reading untouched and raise no parse error; the `-32768` sentinel blanks
the field while a genuine −55 °C still displays; `V` primes all fields and 8-field pre-v4.28
firmware leaves them blank; a plain rejected config alerts without latching while `LOCKOUT:` and
a latch-naming `ERROR` both latch; the `W` grid path is unaffected. Replaying all 671 `RAW` lines
of the real session leaves the last record's 22.13 V / 50.0 °C on screen with zero parse errors.
(2026-08-07)

---

### src/pimd_gui.py — v4.17 — FIX the `P` record parse also matched `PACK:` messages, so the GUI has never shown a failsafe transition

Reported from the bench: `Sensor packet parsing error: list index out of range`, appearing once
per pack power-cycle. The trigger was diagnostic — power-cycling the pack is exactly what makes
the firmware emit a `PACK:` line.

`process_packet()` dispatched on `line.startswith('P')`, which is true of the `P<time_ms>,…`
telemetry record *and* of every firmware message beginning with P: `PACK: rail absent (… mV) —
USB power assumed, failsafe suspended…`, `PACK: present again at … — failsafe armed`, and the
`Pulse Induction Metal Detector v…` boot banner. Each was split on commas, indexed, and threw.
Now guarded with `line[1:2].isdigit()` — a record always carries `<time_ms>` immediately after
its tag, a message never does. Pre-existing since v4.28 and unrelated to the DS18B20 work; it
surfaced now only because v4.31/v4.32 gave the firmware more to say about the pack.

**The parse error was the smaller half.** Those `PACK:` lines were being *consumed* by the P
branch, so fixing the crash alone would have made them vanish silently — and v4.32 exists
specifically so that an ARMED failsafe is distinguishable from a SUSPENDED one, which is the
state you most need to be sure you are not in. They now reach the alert row. Deliberately
**non-sticky**: each line reports a transition that has already completed, and the standing state
is carried by the pack gauge. A latched `LOCKOUT` is a different kind of thing — a standing
condition — and keeps its own sticky branch, unchanged, along with stopping the run.

`DS18B20:` messages are deliberately left falling through: unlike pack arming, that state already
has a GUI indicator, since the gauge blanks to `—` the moment a reading goes invalid.

Checked against the real firmware strings copied from the v4.33 boot log: both record forms still
parse, all three `PACK:` variants alert without error, the boot banner is ignored, `PACK:` alerts
are non-sticky, and `LOCKOUT` still latches sticky and stops the run. The v4.16 sentinel tests
still pass. (2026-08-07)

---

### mcu/pimd_mcu.py — v4.33 — DS18B20 board temperature on GP6; the GP27 pot placeholder retired

`board_temp_dC` has been on the wire since v4.28 and has never once carried a temperature. GP27
sat on bench pot RV7 scaled by `THERM_TEMP_FULLSCALE_DECIC`, so the field reported a pot position
dressed as degrees — a number the file header, the DESIGN text and the GUI tooltip all warned
about and which the gauge displayed anyway. The planned fix was an analogue NTC on GP27; that is
superseded. A **DS18B20 is wired to GP6**, a pin previously reserved for a panel meter that is not
being fitted. The part is digital and factory-calibrated to ±0.5 °C, so the Beta/Steinhart-Hart
curve the analogue path would have needed — the reason the placeholder constant said it must be
"replaced with the proper curve, not just re-tuned" — does not arise at all.

**The whole design is about where the transaction is allowed to run.** 1-Wire is bit-banged and
each bit slot is ~70 µs with IRQs briefly off inside the driver, so a scratchpad read is ~7.6 ms of
blocking CPU. That is CPU time and only CPU time: the drive/sample PWM pair and the LTC2508's
conversions are hardware and free-run straight through it, and GP6 is on PWM slice 3 used as a
plain open-drain GPIO, so §11's same-slice phase-locking invariant (GPIO4/5, slice 2) is untouched.
The one place ms-scale blocking is already known to be affordable is the `i == 0` service point in
`acquire_mode2()` — it absorbs the blocking emit `print()` today, and per the v4.24 note a delay
there lands as *extra settling* for cell 0 rather than as a corrupted read. So every 1-Wire access
is routed through `service_sensors()`, which **is** that point: it is the function's only Mode 2
call site, so the placement rule is enforced by construction rather than by comment. Nothing goes
anywhere near `read_raw_bytes_hold()`.

Three further choices fall out of the same budget. The 750 ms conversion is **never waited on
inline** — `service_ds18b20()` is a two-step state machine that issues `CONVERT T` on one service
tick (~2.2 ms) and reads the scratchpad on a later one (~7.6 ms), so the longest single block is
the read. **SKIP ROM, not MATCH ROM**, which is why `ds18x20.py` is deliberately not used: its
`read_temp()` addresses the device by its 64-bit ROM code, writing 8 extra bytes — ~4.8 ms of
bit-bang — to reach the only thing on the bus that could answer. And the cadence is
`DS18B20_INTERVAL_MS = 30_000`, not `SENSOR_SAMPLE_MS`: board thermal time constants are minutes,
so 1 Hz would be 30× the hot-path exposure for information the 60 s `P` report cannot even carry.
Net cost is ~10 ms per ~200 sweeps — one sweep in 200 running ~5 % long, well inside the 3× window
span guard the PC tools apply, in the benign direction. All 9 scratchpad bytes are read rather than
the 2 that carry the temperature: the extra 7 cost ~4.2 ms and buy the CRC, which is the difference
between a corrupted bit arriving as a wrong temperature and arriving as no temperature. On a line
running past this front end that is worth 4 ms every 30 s.

**Failure is a first-class path, because the detector must not care.** The `onewire` import is
guarded, bus construction is guarded, and every transaction is wrapped; a missing module, a missing
sensor, a bus exception or a CRC failure all resolve to the same thing — `board_temp_dC` reports
`TEMP_INVALID_DC` and acquisition is untouched. There is no error latch: the state machine returns
to idle and retries on the next interval, so a sensor that comes back simply starts working, with
no reset. Health messages print **only on transitions**, following the v4.32 `PACK:` convention,
because a per-attempt print inside the Mode 2 loop is precisely the emit-block hazard v4.27 exists
to measure. `ds18b20_init()` runs *after* `pack_voltage_boot_check()` — the "never fires a pulse
below the floor" guarantee keeps the front of the boot order — and announces its result
**unconditionally**, since `ds_present` starts `False` and a sensor missing at boot is therefore
not a transition; without that the "no sensor" state would be indistinguishable from a healthy
silent one, the same trap v4.32 closed. `service_ds18b20()` sits *after* the pack block in
`service_sensors()` so a pack trip never waits behind a scratchpad read, and the 9-byte buffer is
allocated once at module scope so the Mode 2 loop cannot trigger a GC pass on it.

**Wire format (§11).** Field *counts* on `P` and `V` are unchanged, so no parser breaks. What is
new is a sentinel: `board_temp_dC == -32768` means NO READING, and a consumer must blank rather
than plot it. This is a semantic extension of a documented field and is recorded here rather than
treated as free, following the precedent §9 sets for the `B` counters. It cannot collide with a
real reading — the part's range is −55…+125 °C, i.e. −550…+1250 dC. `board_temp_dC` starts at the
sentinel rather than 0, because before the first conversion there genuinely is no reading and 0 dC
is plausible enough to be believed.

Verified offline, the board not being on the bench: the raw→deci-degC conversion matches all ten
datasheet reference values including both range endpoints and the two's-complement negatives
(−25.0625 °C → −251 dC, floor-rounded in both directions deliberately); and a 20-check mock-bus
exercise of the state machine confirms the convert/read split, SKIP-ROM-never-MATCH-ROM, CRC
failure resolving to the sentinel and not to a wrong number, transition-only printing, unattended
recovery, and exceptions never propagating into the sweep. The bench acceptance gate is unchanged
and still outstanding: sweep interval must stay 0.1445–0.1455 s on the 63-cell profile measured on
the *firmware* clock, and `B`'s `overrun_count` must not rise against a DQ-unplugged baseline.

DESIGN now trails the code in three places, for the next consolidation pass rather than for direct
edit: §8's SPI/pin map gains 1-Wire on GP6, §9's `P`/`V` `board_temp_dC` semantics gain the
sentinel, and §7's "still to measure" list no longer needs a thermistor front end. (2026-08-07)

---

### src/pimd_gui.py — v4.16 — the temperature gauge stops trusting the field, and the tooltip stops lying

Follows fw v4.33. `pimd_gui.py` is the only consumer of `board_temp_dC` anywhere — classviz,
delaycal, rawlog and features do not read it — so this is the entire PC-side surface of the change.

`_update_sensors()` resolves the firmware's no-reading sentinel exactly once, at the top, so
neither the gauge nor the session log ever sees the raw `-32768`. The gauge gets `None`, which
`BarGauge` has always rendered as `—`, so no gauge code changed. The log gets the word `none`
rather than the number: a `-32768` sitting in a `# sensor:` line is indistinguishable from a
temperature to any later reader, and these session CSVs are read long after the run. The test is a
threshold (`TEMP_INVALID_MAX_DC = -10_000`) not an equality, so any future out-of-band code blanks
too, and it cannot swallow a real reading — the part bottoms out at −55 °C, i.e. −550 dC.

Sub-zero readings are now reachable and are left as-is: `BarGauge` clamps the bar fraction to
[0, 1], so they show an empty bar with the correct negative number printed. That is the right split
— the number is the reading, the bar is the glance. The tooltip's "PLACEHOLDER linear ADC scale —
the thermistor front end does not exist yet" is replaced with what the field now is, and keeps one
line naming fw v4.28–v4.32 as the versions that sent a bench pot on it, because session logs from
that epoch exist and their temperature column is not a temperature.

Checked against a stub: normal, sub-zero, both part endpoints and the sentinel all resolve
correctly in gauge and log, with no raw sentinel leaking into either. (2026-08-07)

---

### findings — DS18B20 on GP6: the RP2040's internal pull-up is not adequate, and the 1-Wire cost is CPU-only

Recorded because both questions have answers that are easy to get wrong in the reassuring
direction — the internal pull-up in particular *appears* to work.

**The external 4.7 kΩ pull-up from DQ to +3V3 is required, not belt-and-braces.** The RP2040's
internal pull-up is ~50–80 kΩ. Against even 50–100 pF of bus capacitance that is a rise time of
several µs, and the 1-Wire master samples a read slot ~15 µs in. On a short lead with one device it
can work well enough to pass a bench test and then fail intermittently once the lead is dressed
into the enclosure — which is the worst available failure mode. MicroPython's driver sets the pad
`OPEN_DRAIN | PULL_UP` regardless, so the internal pull-up is *enabled* in normal operation; that
is not a substitute for the external resistor. Use 2.2 kΩ if the lead is long. The sensor runs from
**+3V3, not +5 V** — DQ is tied to its supply through the pull-up and must not exceed the RP2040
rail — in **normal 3-wire mode, not parasite power**: parasite needs an active strong pull-up
driven onto the line for the whole conversion, which this pin cannot do while the sweep is running.
100 nF across VDD/GND at the sensor body, and the DQ lead routed away from the RX front end — it
only switches for ~10 ms every 30 s, but it is a 3V3 digital edge near a front end whose measured
noise floor is ~450 µV (§7).

**The timing answer.** The instinctive worry about 1-Wire here is the 750 ms conversion, and it is
the wrong worry — the conversion is a property of the *sensor*, not of the bus, and is simply not
waited on. The real cost is the bit-banged transaction: ~70 µs per bit slot with IRQs briefly off,
so ~2.2 ms to start a conversion and ~7.6 ms to read the scratchpad. Crucially that is CPU time
only. The PWM pair and the LTC2508 conversions are hardware and free-run through it, so nothing in
the acquisition is perturbed; what is deferred is the firmware's own ability to do the next thing.
That makes placement the entire question, and the answer already existed in the loop: the `i == 0`
service point absorbs the blocking emit `print()` today and the v4.24 note records that a delay
there lands as extra settling for cell 0. GP6 itself is clean — PWM slice 3, used as plain GPIO,
with the slice-2 drive/sample pair untouched.

Also worth having written down: the DS18B20's power-on scratchpad default is `0x0550`, which is
exactly **+85.0 °C** — a read that beats the first conversion returns a plausible hot number, not
an error. That is guarded by sequencing (the read only ever happens 800 ms after a `CONVERT T`
that got a presence pulse) and deliberately *not* by value-filtering: +85.0 is a legal reading, and
rejecting it would mean silently dropping a real over-temperature, the one reading that must not be
lost. (2026-08-07)

---

### src/pimd_gui.py — v4.15 — the connected board's firmware version is on screen and in the log

Asked for alongside a confirmation that the GUI pulls pack/temp early. It does, and has since
v4.14: `connect_port()` sends `E` then `V` the moment the port opens, and `sensor_poll_timer`
re-sends `V` every 10 s. That connect-time `V` is the whole reason the gauges populate promptly
— the firmware's unsolicited `P` telemetry is only every 60 s, so without it a freshly connected
board would show `—` for up to a minute. No change was needed there.

The version turned out to cost nothing on the wire. The firmware has always answered `V` with
`V<fw>,<board_id>,…` and the GUI has always split that line — it simply used indices 8..10 and
threw fields 0 and 1 away. So this is a **display-only change: no firmware edit, no new command,
no wire-format change**, and DESIGN §11's serial-format invariant is untouched.

A `Firmware:` row now sits in the top-left session block under `Session:`, showing `v4.32` with
the board ID in the tooltip, and `—` when nothing is connected. The parse deliberately sits
**ahead of** the existing `len(parts) >= 11` guard, because fields 0 and 1 exist on every
firmware revision while the pack/temp/lockout trailers need v4.28+ — against older firmware the
version still displays and only the gauges stay blank. `_clear_fw_identity()` resets the row on
disconnect: the version is a property of the open connection, and a stale one outliving it would
be worse than no reading. The gauges are left holding their last value, as before.

`setup_file_logging()` also writes `# fw_version: <N>` beside the existing `# pimd_gui v<N>`
line, so a session CSV records which firmware produced it — previously recoverable only by
correlating timestamps against this file. Falls back to `unknown` if Start is somehow reached
before a `V` reply lands. The alert row moved from grid row 2 to row 3 to make space; no change
to its behaviour. (2026-08-07)

---

### DESIGN.md — errata — §9 documents the `V` identify reply with 8 fields; firmware sends 11

Noticed while wiring up the GUI's firmware readout. `DESIGN.md` §9 still describes the reply as
`V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>` —
the pre-v4.28 shape. Firmware v4.28 appended `pack_mV`, `board_temp_dC` and `lockout`, and both
`mcu/pimd_mcu.py` and `src/pimd_gui.py` have depended on those three ever since; they are
documented only in the two file headers.

Harmless in practice — the append-only convention means nothing splits by field count — but §9
is the reference a reader would trust, and it currently understates the record by three fields.
Recorded here rather than fixed in place, per the rule that `DESIGN.md` is regenerated from this
file. For the next consolidation pass (§18). (2026-08-07)

---

### mcu/pimd_mcu.py — v4.32 — the pack absent→present transition always announces itself

Found immediately on the first bench run of v4.31, and worth its own version because it is an
observability defect rather than a cosmetic one. The rig was booted USB-first with the pack
switched on afterwards — the exact workflow v4.31 was written to support — and it worked: the
boot at 3859 mV suspended instead of latching, and the pack coming back at 22 507 mV cleared
`pack_absent` and left `lockout = 0`. But it did all of that **in silence**, because v4.31 only
printed when there was an actual latch to clear, and there had never been one. The transition
was read as a failure to re-arm.

It was not a failure, but the reading was reasonable, and that is the problem: **a suspended
failsafe and an armed one were indistinguishable from the log and from the wire.** `pack_absent`
is not reported on `V` and the re-arm path printed conditionally, so the one state you most need
to be certain you are not in — protection silently switched off — was the state you could not
observe. Same class of defect as the invisible `LOCKOUT:` line recorded under v4.30.

Every path through the absent→present branch now prints exactly once, and every message ends
`— failsafe armed`, so the arming is stated rather than inferred:

- `PACK: present again at <N> mV — failsafe armed` (no latch had been set)
- `PACK: present again at <N> mV — lockout cleared, failsafe armed`
- `PACK: present again at <N> mV, below re-arm floor 21500 mV — lockout state unchanged, failsafe armed`

No logic change: thresholds, debounce, latch semantics and the trip path are all identical to
v4.31, and `pack_voltage_lockout = False` moved inside the branch that tests it, which is a
no-op. The `V` field for `pack_absent` remains not done — the print covers the transition, and
adding a 12th field is still the better fix for the GUI's gauge reading 0.4 V / 0 % / red
`LOCKOUT floor` while the pack is simply switched off. (2026-08-07)

---

### mcu/pimd_mcu.py — v4.31 — pack-absent suspend (< 6 V ⇒ USB power) and re-arm hysteresis; a battery swap no longer needs an MCU reset

Requested after the v4.28 latch proved impractical to live with on the bench. The MCU is
USB-powered and **outlives the `+20V` rail** — measured during the v4.30 investigation, where
the board ran normally with the rail decayed to 3.85 V. So switching the pack off, or swapping
cells, dropped the sense reading to near zero without the firmware rebooting; the failsafe read
that as a catastrophically flat pack and latched, and clearing it needed a physical MCU reset.
That is not a reasonable price for changing a battery, and it also blocked the ordinary workflow
of powering the board over USB for programming and switching the pack on afterwards.

`PACK_ABSENT_MV = 6_000`: below this the rail is **off**, not low. A connected 6S pack cannot
sit at 1 V/cell, and the +15 V rail dropped out some 12 V higher up — so nothing is being
discharged and there is nothing for the failsafe to protect. The check now suspends (clears the
streak, emits one `PACK: rail absent` line) instead of latching, and takes no view on any pack
while suspended, on the grounds that a reading taken with no pack present says nothing about a
pack.

`PACK_REARM_MV = 21_500`: release requires a returning pack to reach this, **not** merely to
clear `PACK_VOLTAGE_TRIP_MV`. That is the hysteresis, and 21.5 V is the DESIGN §12 clean-window
lower edge rather than an arbitrary margin. The reason it is not 21 000: re-arming at the trip
itself would let a genuinely flat pack, switched off and straight back on, return on its no-load
recovery, re-arm, and sag again under load — precisely the cycle the v4.28 hard latch was built
to stop, and precisely how the cells were damaged in the first place. A pack returning below
this leaves the latch untouched and normal trip logic resumes immediately, so a weak pack that
keeps sagging still latches on its own merits.

**This is not a serial re-arm.** No command clears the latch; it still takes the pack physically
going away and a healthy one being presented. The trip threshold, the debounce, the boot check
and the `S`/`G`/`D` rejection are all unchanged.

Verified against a faithful port of the state machine over nine scenarios, all passing: battery
swap mid-session · USB-only boot with the pack switched on later · genuine discharge to the
floor still latching · a flat pack switched off and on **not** re-arming · a fresh pack fitted
after a latch **does** re-arm · pack removed while already locked, returning healthy · weak pack
returning at 21.4 V then sagging, latching on merit · normal running never tripping.

One behaviour to expect rather than be alarmed by: switching the pack off makes the rail **decay
through the 21 → 6 V band**, which takes longer than the 3-sample debounce, so a `LOCKOUT:` line
is emitted on the way down before the absent threshold is reached. It self-clears on re-arm — the
simulated decay sequence ends unlocked. Note also that the sweep does genuinely stop during a
swap (`state = 'stop'`, `set_safe_state()`); the rail is gone, so that is unavoidable. What v4.31
buys is restarting with `G`/`S` afterwards instead of power-cycling the MCU.

Not done, deliberately: `pack_absent` is not on the wire. It would be a safe additive 12th field
on `V` (the GUI tests `len(parts) >= 11`) and would let the pack gauge show "no pack" instead of
0.4 V, SoC 0 % and a red `LOCKOUT floor` caption, which is what it will now display with the
pack switched off. Left out to keep this change to the failsafe alone. (2026-08-07)

---

### mcu/pimd_mcu.py — v4.30 — harden `pack_voltage_boot_check()` against divider RC settling (defensive; original lockout root cause NOT established)

Prompted by a lockout on a healthy 22.5 V pack: the rig came up latched, the gauge reading the
correct voltage beside a `LOCKED OUT` caption. **The cause was never established, and this
entry does not claim it.** What follows is a real weakness found while investigating, worth
fixing on its own merits, plus an explicit record of what was ruled out — because the
investigation produced two confident wrong answers before the measurements landed.

The weakness is genuine. The v4.28 latch logic is unchanged and had been bench-proven against a
pot, but a 10 kΩ pot wiper is a stiff, capacitor-free node that settles instantly, whereas the
v4.29 divider is 22 k ∥ 2.7 k = 2405 Ω against C_tap 1 µF + C_pin 100 nF. **Measured τ = 2.9 ms**
(predicted 2.65 ms, four independent fit points), needing ~22 ms to reach one LSB of settled.
GP26 also sits under the RP2040 pad's default pull-down for the whole MicroPython boot, released
only when `ADC(Pin(26))` is constructed — a few milliseconds before the boot check runs, since
the module is compiled first and then executed, and everything between is definitions costing
microseconds. So the boot check did sample a recovering node. Two fixes:

1. `PACK_SENSE_SETTLE_MS = 100` (≈ 34 τ) slept before the first boot reading.
2. `PACK_VOLTAGE_BOOT_SAMPLE_MS = 20` spacing the boot samples. This is the more important of
   the two: back-to-back the three reads completed within ~2.8 ms and all landed inside the
   same transient, so `PACK_VOLTAGE_TRIP_CONSECUTIVE = 3` had **degenerated into a single
   sample taken at the worst available moment**. The debounce was decorative. That is a defect
   regardless of what caused the original latch.

**But it does not explain the observed lockout.** Reproducing the exact v4.29 path on the bench
at a live 22.5 V pack — pull-down held 400 ms, released, then three back-to-back 64-conversion
averages — gives 21 497 / 21 839 / 22 035 mV, repeatable across three trials, every read
comfortably above the 21 000 mV trip. Verdict: *would not latch*. An earlier claim that the
mechanism was confirmed rested on a 7.30 % depression measured with the rail decayed to 0.42 V
and then scaled to 22.5 V; measured directly at the live voltage the depression is **5.13 %**,
landing at 21 348 mV — 348 mV clear of the trip. **The extrapolation was unsound and the
conclusion drawn from it was wrong.**

Also ruled out, and recorded so it is not re-proposed: the MCU being USB-powered and outliving
the pack rail. That is *true* — the board was later observed running normally with `+20V`
decayed to 3.85 V — but it cannot explain this event, because the rig had been powered pack-first
with USB disconnected and only plugged in afterwards. A fact about the board is not a cause.

The one condition not reproducible from the REPL is a genuine cold start with `+20V` itself
rising from zero; every bench measurement had the rail already up. That remains the leading
hypothesis and nothing more. **The fault has not recurred since.** If it does, `pimd_rawlog.py`
attached across a boot would capture the `LOCKOUT:` line and its mV value — the number lost the
first time because the failsafe printed it to USB CDC with no host listening.

The latch semantics are **untouched** — no threshold moved, no re-arm path added, the hard
latch is still hard. A genuinely flat pack still latches, 100 ms later than before. This is a
sleep at boot, not a scheduler, so §11 is unaffected.

Worth recording for diagnosis, because it cost time: **the LOCKOUT line was invisible.** The
firmware latched at boot and printed its message to USB CDC with no host attached, so the line
was lost; the GUI connected afterwards and learned of the latch only from field 10 of the `V`
poll, captioning the gauge `"22.51 V · LOCKED OUT"`. That caption was initially read as the
alert text, which sent diagnosis after a phantom — a reading *above* the floor appearing in a
latch message. It cannot happen: `_pack_voltage_trip_check()` zeroes the streak in the same
call before testing it, so the printed value is provably ≤ `PACK_VOLTAGE_TRIP_MV`. The
inconsistency was the tell that the number came from somewhere else. **A failsafe that reports
only over a link that may not be attached when it fires is half-instrumented** — the boot-time
latch reason is a candidate for latching into a variable that `V` can report, not just a print.

Also corrected here: the v4.29 header history line said `FULLSCALE 25000 -> 30304`, the interim
divider-only figure, where the version actually shipped 30083. (2026-08-07)

---

### mcu/pimd_mcu.py — v4.29 — pack-voltage divider built and bench-calibrated; FULLSCALE 25000 → 30083 mV; POT pin comments corrected

The v4.28 sense path is no longer notional: the pack-voltage divider has been built and
wired, so `PACK_VOLTAGE_FULLSCALE_MV` stops being a placeholder and becomes a measured
constant. Hardware fitted (design detail in the findings entry below): **22 kΩ / 2.7 kΩ**
from the `+20V` rail at J11 pin 2 to GP26/ADC0, **1 µF** across the 2.7 kΩ and **1 kΩ + 100 nF**
at the pin, all mounted at the MCU end with the divider return on MCU-local ground.
Bench calibration 2026-08-07: **2.460 V at the ADC pin against 22.59 V at the pack**, giving a
measured ratio of **9.18293** — +0.38 % off the 9.14815 nominal, implying R_top ≈ 22.094 kΩ,
inside 1 % tolerance, so the build itself is confirmed correct rather than merely working. A
second point (2.457 V / 22.55 V → 9.17786) agrees to 0.055 %.

**`PACK_VOLTAGE_FULLSCALE_MV = 30_083`**, which is the *fully* calibrated figure —
divider ratio and ADC reference together. It was briefly 30_304 in this same version, from
3.300 × 9.18293, i.e. divider-only with the reference assumed. That figure never ran on
hardware and the version was amended rather than superseded. **The reference is not 3.300 V:**
the first flash attempt didn't take, so the board was still running v4.28's FS = 25 000 when a
pin measured at 2.457 V reported 18 740 mV — which solves directly for **ADC_VREF = 3.2777 V**,
the RP2040-Zero's 3V3 LDO sitting **0.67 % low**. Re-running the firmware's full integer path
(12-bit quantisation, MicroPython's `read_u16` scaling, `* FS // 65535` truncation) at that
reference reproduces the observed 18 740 to within 2 mV. 3.2777 × 9.17786 = 30.083 V.

Worth recording as method: a reading taken against a *known* constant is a complete
calibration, because `reported = V_pin × FS_config / VREF` inverts for VREF with everything
else measured. The accidental stale flash produced the paired `P`-line/DMM measurement this
entry had listed as outstanding work. The LDO term is **0.73 %, 221 mV at full scale** — not a
rounding error, and **per-module**, so this must be redone if the RP2040-Zero is ever swapped.

The old 25 000 value was not merely uncalibrated, it was **unusable**: full scale sat *below*
a full 6S pack (25.2 V charged; §17.13 measured pack B at 25.04 V no-load), so a fresh pack
would have pegged the reading exactly where DESIGN §12's data-quality ceiling lives. At the
bench point it would have reported 18 636 mV against a true 22 590 mV — a −3.95 V error, far
enough below the 21 000 mV trip that the failsafe would have latched instantly on a healthy
pack. Nothing was lost, because the channel had never been wired.

**The failsafe was proven end-to-end on real hardware by the stale-flash incident**, which is
the one good thing to come out of it: 18 740 mV ≤ the 21 000 mV trip, so the firmware latched,
rejected `S`/`G`/`D`, and `pimd_gui.py` painted the lockout state and caption correctly. The
whole v4.28 chain — ADC read, debounce, latch, `V`-line lockout field, GUI alert — ran against
a live pack for the first time. It was only ever fed a wrong scale factor.

Also corrected here, comment-only but riding along because it was flagged by v4.28's own
"VERIFY against schematic sheet 1" instruction and the check **failed**: the pin→pot mapping
runs backwards from the pin numbering. Sheet 1 wires **GP29→POT-0, GP28→POT-1, GP27→POT-2,
GP26→POT-3**, so v4.28's "GP26 / ADC0, POT-0" and "GP27 / ADC1, POT-1" named the wrong pots.
The *pins* were right (both are ADC-capable and both were pot-wired), so no behaviour was
wrong — but the v4.28 bench procedure would have had the operator turning RV5/RV6 and seeing
nothing move. GP26's pot **RV8 has now been removed** from the board and its footprint reused
for the divider (pin 1 = GND, pin 2 = wiper/GP26, pin 3 = +3V3 left open); leaving it fitted
would have put 10 kΩ across a 2.4 kΩ divider node and swamped the ratio. GP27 remains on RV7.
`THERM_TEMP_FULLSCALE_DECIC` is untouched and still a placeholder. (2026-08-07)

---

### findings — the +20V rail is the correct pack-sense node, and the sense-divider error budget is dominated by the RP2040's own 3V3 reference

Design pass behind the v4.29 divider above, from DESIGN §12 plus both schematic sheets. Three
results worth keeping.

**`+20V` is pack terminal voltage, with no diode drop to compensate.** D4 (1N4004) reads as a
series element in the block description, but on sheet 1 it is a **shunt reverse-polarity
clamp** — cathode on `+20V`, anode on GND, blowing F1 on reversal. So the sense node needs no
forward-drop correction and, more importantly, does not drift with load current the way a
series diode would between idle and streaming (a ~0.3 V, state-dependent error that would have
been indistinguishable from the IR-drop effect §17.13 measured at 0.29 V). `+20V` is also
downstream of SW3, so the divider draws nothing with the rig switched off. J11 pin 2 is the tap.

**Sizing.** Ratio 1/9.148 puts full scale at 30.19 V nominal, so a 25.2 V pack sits at 83.5 %
of range and the ADC pin cannot be over-driven until the input passes 30.2 V — above anything
the board survives anyway. Thevenin 2.4 kΩ, drain 1.02 mA (10.5 mAh over a full 10.33 h
session, 0.2 % of the pack), 23 mW in R_top. The pack-referred leakage error reduces to exactly
**1 µA × R_top**, which is what caps R_top at ~22 kΩ rather than the 82 kΩ a drain-first choice
would suggest. Filter poles at 66 Hz and 1.6 kHz give 237× rejection at a 5 kHz TX rate and
5900× at 25 kHz, settling in 17 ms against the 1 Hz sample. Divider mounted at the MCU with
only the stiff `+20V` lead crossing the board: putting R_top at the source end instead would
have left a 2.4 kΩ node on a long wire beside a µV-scale front end.

**Error budget, pack-referred at 25 V, after one-point calibration** — resistor *tolerance*
does not appear, because a divider is perfectly linear and one-point calibration removes the
ratio error across the whole range; only tempco survives. 3V3 LDO drift ±75 mV · resistor
tempco mismatch (50 ppm/°C over 30 °C) ±38 mV · ADC leakage ±22 mV · RP2040 SAR DNL/INL ±30 mV ·
quantisation ±7 mV → **RSS ≈ 92 mV**. That is comfortably sufficient for the 21.0 V failsafe,
which is the whole reason v4.28 exists, but **marginal for placing the pack inside §12's
21.5 / 23.3 / 24.0 V data-quality bands**, which want ±50 mV. The dominant term is the module's
3V3 LDO serving as the ADC reference. If band placement is wanted from this channel, the fix is
cheap and uses parts already on the board: divide the existing `5V-REF` (U5, LTC6655-5 —
0.025 % initial, 2 ppm/°C) 10k/10k into spare GP29, and compute the pack ratiometrically. LDO
drift then cancels entirely and RSS falls to ≈53 mV; it also lands the reference conversion at
2.50 V, close to the pack's 2.75 V, so both sit on the same part of the SAR's transfer curve.
Not built.

Buffering with the spare LT6203 half was considered and rejected: U3 runs single-supply from
**+12 V**, so its output could present 12 V to a 3.3 V ADC pin on any fault — not worth it for
a 1 Hz housekeeping channel.

**Unrelated observation on the same node, recorded because it was found here:** C18 is a
4700 µF **25 V** part on `+20V`, and a fully-charged 6S pack is 25.2 V (§17.13 measured pack B
at 25.04 V no-load). It runs at ~100 % of rating on a fresh pack, which ages an electrolytic
quickly. A 35 V part is the obvious swap. Not acted on. (2026-08-07)

---

### findings — the RX network is critically damped and the undershoot is not it; damping is the wrong knob for a second reason

Follow-up to the "CORRECTION: the negative lobe is real" entry below, answering "was the model wrong because we are still
underdamped?" Offline, no bench time. Three separate results.

**1. Why the v1 extrapolation failed: it was unconstrained, not merely inaccurate.** Fitting
`A·exp(−t/τ_f) − B·exp(−t/τ_s)` to the same four calibrated columns with τ_s pinned at a series
of values gives fits that agree with the data to **≤ 2 %** while predicting anything from
**+64 mV to −400 mV** at sd 14.7 µs:

| τ_s (µs) | τ_f (µs) | worst residual | predicted V(14.7 µs) |
|---:|---:|---:|---:|
| 1.5 | 1.50 | 9.3 % | +64 mV |
| 2.0 | 2.00 | 8.0 % | +19 mV |
| 3.0 | 2.99 | 2.6 % | −180 mV |
| 5.0 | 2.75 | 2.0 % | −302 mV |
| 8.0 | 2.47 | 2.0 % | −336 mV |
| 30.0 | 2.27 | 2.1 % | −400 mV |

A ~2 % difference in fit quality moves the extrapolation by 460 mV. Sums of exponentials are
famously ill-conditioned and four points over 0.88 decades cannot separate them; the
critically-damped form v1 chose (+38.6 mV) is one member of that family, not the answer, and the
measurement (at or below the 2.441 mV rail) sits inside the family's spread. **The v1 entry
should have quoted the spread and did not.** The lesson is not "fit harder" — it is that this
region needs samples, and it does not have them: between clip release and the rail,
`cal_110_full_range_v4` places exactly **two** columns on the 150 µs band (7.904 and 10.912 µs)
and two on the 100 µs band (7.528 and 10.496 µs). Two points cannot constrain a decay.

**2. The network is critically damped, and the arithmetic closes on itself.** For the parallel
RLC (R1 shunting the coil, C its self-capacitance): α = 1/(2RC), ω₀ = 1/√(LC),
ζ = α/ω₀ = √(L/C)/(2R), and at ζ = 1 the response is `(a + b·t)·exp(−t/τ)` with τ = 2RC — which
is the form that fitted the ladder to ±0.84 %. Taking the measured τ = 0.920 µs and
R1 = 1.30 kΩ: **C = τ/2R = 354 pF**, ω₀ = 1/τ = 1.087×10⁶ rad/s (**f₀ = 173 kHz**),
**L = 1/(ω₀²C) = 2.39 mH**, so **√(L/C) = 2600 Ω** and **R_crit = ½√(L/C) = 1300 Ω** — against
DESIGN §7's independently *measured* 1300–1400 Ω, and against the fitted R1 of 1300 Ω. **ζ = 1.00.**
Two of those numbers were measured on the bench years apart by different means and they agree, so
this is a real check, not a tautology. It also puts a value on §7's outstanding "re-measure RX
self-resonance to pin L and C" item: **354 pF / 2.39 mH, inferred from the decay rather than from
a resonance**, and worth confirming against the direct measurement when it happens. (The stale
figures were 311 pF / 3.9 mH — the capacitance was close; the inductance was not.)

**3. The undershoot cannot be the coil, by a factor of 7000.** The coil transient decays with
τ = 0.92 µs from ~4.7 V at clip release (sd 7.9 µs). By sd 21.9 µs that is 15.2 time constants,
leaving **1.2 × 10⁻³ mV**. The measured deviation from the settled level there is **−8.45 mV** —
7341× more than the network can still supply. By sd 43.9 µs, where air has only just reached the
pedestal, the coil term is 5 × 10⁻¹⁴ mV. Underdamping would not rescue this: at ζ = 0.9 the ring
is 75 kHz and each half-cycle is attenuated ×1.5 × 10⁻³, so the visible consequence is one small
undershoot ~3 µs after the crossing and nothing after — not a lobe bottoming at 15 µs and taking
until 44 µs to clear. **So the answer to "are we still underdamped" is no, and the reasoning that
R1 is the wrong knob (2026-08-05 entry) survives the correction intact — for a stronger reason
than the one given then.**

**4. And it is not a linear network response at all.** From the recovery, −8.45 mV at sd 21.88 µs
to −0.97 mV at sd 30.99 µs, the undershoot's own time constant is **τ ≈ 4.2 µs**, 4.6× the coil's.
A linear network released at t = 0 has every mode present from t = 0, so that component
back-extrapolates to **−114 mV at sd 10.912 µs — 13 % of the 876 mV signal there** — whereas the
ladder fit agrees with measurement to ~3 % at that delay. **The component was not there yet.**
A term that switches on late is the signature of a recovery from saturation, not of an RLC being
released. That is consistent with the LT6203 overload-recovery hypothesis and inconsistent with
any passive coil-network explanation, but it is a deduction from two fitted points and a 3 %
agreement across two epochs, so it is **suggestive, not settled** — the scope at the preamp output
is still the instrument that decides. Note also that target-sensitivity does **not** discriminate
here: overload recovery depends on how hard the stage was overloaded, so a target that changes the
drive changes the recovery too, which is why the +7.12 mV the spanner adds at sd 21.9 µs is weaker
evidence than it looks. (2026-08-07)

---

### findings — CORRECTION: the negative lobe is real, it is in air, and it is on every band

Supersedes the conclusion of the entry below it (2026-08-05, "the calibrated ladder puts the air
decay at ~60 mV where 3 mV was reported"). That entry argued from a ladder fit that the coil
network had no room for the reported undershoot and leaned toward amplifier recovery. The
2026-08-07 session measures air directly across the whole delay sweep and **the undershoot is
there, in air, on all ten bands.** The argument was wrong; the fit that produced it was fine
inside its own range and simply does not extrapolate.

Source: `src/data/sessions/rawlog_20260807_194234.txt`, Mode 2 W5 stream over
`cal_110_full_range_v4` (10 bands × 11 delays), fw 4.33, 4.07 Hz, 562 frames, 138 s.

**What air actually does on the 150 µs / 2 kHz band** (n = 222 frames, σ ≤ 0.18 mV on every
post-rail cell): 4698.9 mV at sd 7.904 µs → 891.7 at 10.912 → **2.441 at 15.448** → 7.40 at
21.880 → 14.88 at 30.992 → 16.14 at 43.888, then a slow sag to 15.86 at 250 µs. The fit
predicted 30 mV at 15.448 µs. On the 100 µs band air reads **2.441 mV at sd 14.712 µs** — the
2026-08-05 session's "flat 3 mV bottom around sd 14 µs", reproduced to the delay. Every band
bottoms out between 2.441 and 4.272 mV somewhere in sd 11.7–16.0 µs, and the bottom moves only
weakly with pulse width (12.3 µs at 4 µs drive, 15.4 µs at 150 µs drive) — a feature nearly
fixed in absolute time after turn-off, which is worth explaining but is not explained here.

**2.441 mV is the rail, and the evidence is now direct.** Its σ is exactly 0.000 across every
frame of every class — air, spanner and copper all read the identical code. 2441 µV is 4 × the
raw path's 610.35 µV LSB (5 V / 8192), so it is not an ADC zero code either. **The 15.448 µs
column of the 150 µs band is a dead cell: it cannot respond to any target.** Same for the
100 µs band's 14.712 µs column.

**Where the fit does and does not hold.** At sd 10.912 µs the fit gives 848 mV against 892
measured (−5 %), and it is ±0.84 % on the four columns it was fitted to (sd 8.4–11.3 µs). Past
~11 µs it diverges hard. So the correct statement is narrow: *the calibrated ladder constrains
the decay only over the volt-scale region it samples, and says nothing about what happens below
0.5 V.* The 2026-08-05 entry's supporting arguments — that ~400× rescaling would be needed, that
a two-pole negative term wide enough to reach the rail could not recover by 20 µs — were
reasoning from that same over-extended fit and should not be relied on. What remains open is
unchanged and still needs a scope at the preamp output: whether the lobe is the coil network or
LT6203 overload recovery. **This session does not settle it** — see below, it argues weakly the
other way.

**Targets: the polarity convention lives entirely on the pre-rail cells.** Two targets at 60 mm,
window means over the plateau of each presentation:

| sd (µs) | air | Δ steel spanner (271 g) | Δ copper pipe (122 g) |
|---:|---:|---:|---:|
| 7.904 | 4698.9 | **+10.8** | **−15.1** |
| 10.912 | 891.7 | **+24.8** | **−12.7** |
| 15.448 | 2.441 | +0.000 | +0.000 |
| 21.880 | 7.40 | +7.12 | +2.46 |
| 30.992 | 14.88 | +3.46 | +1.29 |
| 43.888 | 16.14 | +1.95 | +1.15 |
| 62.152 | 16.13 | +1.19 | +0.91 |
| 88.016 | 16.04 | +0.63 | +0.81 |
| 124.648 | 15.97 | +0.35 | +0.63 |
| 176.528 | 15.90 | +0.15 | +0.51 |
| 250.000 | 15.86 | +0.09 | +0.40 |

Three results in that table. **(1)** §17.6's ferrous-positive / non-ferrous-negative convention
holds on the two pre-rail columns and *only* there — steel +25 mV, copper −13 mV at 10.9 µs.
**(2)** Past the rail **both targets read positive**, so sign is not a discriminant in the late
window; the 2026-08-05 entry's suggestion that a non-ferrous target would cross down through the
pedestal is not what happens. **(3)** The late window discriminates by *decay rate* instead:
steel falls 73× from 21.9 to 250 µs while copper falls only 6.2×, so **copper overtakes steel at
~77 µs** and at 250 µs is 4.3× more visible (+0.40 vs +0.09 mV). A long thick copper tube having
the longer eddy time constant is ordinary PI physics; the point is that it makes the 88–250 µs
columns non-ferrous-selective, which is the opposite of what those columns were assumed to be
worth.

**The targets do move the readings around the lobe, which bears on the open coil-vs-amplifier
question.** At 21.880 µs — the first cell off the rail — the spanner adds +7.12 mV on a 7.40 mV
air baseline, nearly a doubling. An amplifier-recovery artefact should be indifferent to metal.
That is *suggestive*, not decisive: 21.9 µs is past the bottom, and nothing can be learned at the
bottom itself because that cell is railed for every class. A scope is still the instrument that
settles it.

**Method note that changed a number, not just a procedure.** `MARK acquire` records the state
*from that point on*, so the marks locate presentations but do not bracket them — in this session
the second `Fe_spanner_01` mark lands ~9 s after the spanner was already away. Segmenting on the
marks as written mixes ~30 s of air into the spanner window and reports Δ at 21.88 µs as
**+3.5 mV against the wrong baseline, sign-flipped depending on which air segment is used**,
versus **+7.12 mV** from the presentation plateau. The tool therefore uses the marks only to name
each excursion and takes the window from the probe cell's own plateau. Worth considering a
paired place/remove marker in `pimd_rawlog` — not proposed as a change here. (2026-08-07)

---

### utilities/decay_model/decaymodel.py — v2 — `--session` overlay of measured air/ferrous/non-ferrous

Adds `load_session()`: reads a `pimd_rawlog` session, segments it into air and one window per
target presentation, and returns per-class means for one band, which the three existing panels
then overlay as solid measured traces. The v1 modelled curves stay on the figure but are demoted
to thin dashed — they are the reference the measurement broke, and the header now says so rather
than presenting them as prediction. Panel titles, annotations and axis limits switch to the
measured story when `--session` is given; without it the tool renders exactly as v1 did.

The W-line parse mirrors `pimd_rawlog._parse_w_line` rather than importing it — that module pulls
in PyQt6 at import time and this tool is offline. Window detection is the substantive part and is
documented in the function docstring: marks locate, the data delimits (see the findings entry
above for why that distinction changes the answer), each presentation is trimmed to the top 80 %
of its own excursion to drop the operator's approach/withdraw ramps and the 32-deep rolling
average's ~8 s smear, seed searches are narrow and skip already-claimed frames so a strong
target's tail cannot out-peak a weaker one, and air is everything outside the windows plus a
guard, after a 20 s skip for the §17.13 stream-start transient. Run:
`.venv/bin/python utilities/decay_model/decaymodel.py --session src/data/sessions/rawlog_20260807_194234.txt --out …`. (2026-08-07)

---

### findings — the calibrated ladder puts the air decay at ~60 mV where 3 mV was reported, and it settles without an undershoot

**SUPERSEDED 2026-08-07 — see "CORRECTION: the negative lobe is real, it is in air, and it is on every band" above.** Read this header
before quoting anything below it.

- **Wrong:** "the coil network's own poles have no room for a −14 mV excursion at 14 µs", and
  the supporting arguments (the ~400× rescaling, the recovery-time contradiction). Direct
  measurement of air shows the undershoot on every band, reaching the 2.441 mV rail at sd
  14.7 µs on this very band.
- **Wrong:** consequence 1, "air carries no information past ~21 µs". Measured air is still
  recovering at sd 21.9 µs (7.40 mV) and 31.0 µs (14.88 mV) and only reaches the pedestal
  around 44 µs — and then sags 16.14 → 15.86 mV out to 250 µs, a 0.28 mV slope against a
  0.07 mV σ, so it is not flat there either. The pedestal is a level the air approaches, not
  one it sits on.
- **Wrong:** consequence 3's sign claim. Both targets read positive past the rail; non-ferrous
  does not cross down through the pedestal.
- **Stands:** the τ = 0.920 µs critically-damped fit and its ±0.84 % residuals over sd
  8.4–11.3 µs, the pedestal's existence, and consequence 2 — `cal_110_full_range_v4`'s interior
  threshold labels are wrong, now confirmed directly (measured 891 mV at sd 10.912 µs, so 0.5 V
  falls near 11.5 µs, not the 62 µs its label implies).

Offline analysis, no bench time and no hardware change. Prompted by a request to plot the
estimated decay and its crossings from 4 µs / ~5 V out to 250 µs / a few mV on the **150 µs**
drive band. New tool `utilities/decay_model/decaymodel.py` (entry below) does the fitting; this
entry is what it found.

**The air decay was fitted to hard data that the previous two entries did not use.** The nine
`delays_us` in each band of `cal_63_air_bat_v3` are delaycal-converged (0.3 mV, 8 ns grid)
sample points at which the trace *actually reaches* the column's threshold voltage — nine
(delay, volts) pairs on the real curve, per band, sitting in the tracked profile the whole time.
Taking the four columns clear of clamp release (3.8 / 2.4 / 1.5 / 0.5 V at 8.360 / 9.240 /
9.944 / 11.320 µs on the 100 µs band) and fitting the **critically damped** form
`V = 17 mV + (a + b·t)·exp(−t/τ)` — the shape §7's measured R1 ≈ 1.3k should give — lands
**τ = 0.920 µs with residuals of −0.14 / +0.76 / −0.84 / +0.23 %**. Three points to make about
that number. It is a genuine test of the two-real-pole claim, not an assumption: four points, three
parameters, and the form could have failed. It agrees with the τ_fast ≈ 0.9 µs the 2026-08-05
entry fitted by hand from three points on a completely different data set. And it reproduces,
*without being fitted to them*, the same session's held-back observations — model 17.116 mV at
sd 20 µs against "~17 mV by 20 µs", 17.000 against SDOA's 16.674 mV at sd 30 µs, 17.000 at
sd 100 µs against "unchanged".

**Everything the two entries above record is reproduced except the undershoot.** The fitted
curve is **monotonic**: it lands on the 17 mV pedestal from above and never crosses it. At
sd 14 µs, where the session reports a flat 3 mV bottom, the calibrated decay is at **59.6 mV** —
57 mV above the observation and 43 mV above the pedestal. No rescaling closes that: the
amplitude factor required is ~400×, against the ~11× §17.13 allows across the *entire*
pack-voltage range, and the same session's own sd 8 µs reading (4.3 V, model 4.11 V) rules out
a delay offset. Nor does a negative term fix it while staying consistent — any second pole steep
enough to reach the rail by 14 µs is several µs wide and takes ~25 µs to recover, contradicting
both the hand-read 0.5–1 µs flat *and* the measured "17 mV by 20 µs". Fitting a two-pole model
to all of it at once was tried first and degrades the ladder to ±12–24 %.

**This does not overturn the observation; it narrows what the observation can be.** The
2026-08-05 entry already listed, and could not settle, whether the lobe belongs to the coil
network or is LT6203 overload recovery. This is independent support for the second: the coil
network's own poles, pinned by the calibration and by the settling behaviour the same session
measured, have no room for a −14 mV excursion at 14 µs. It remains **inferred from a fit, not
measured** — a scope at the preamp output settles it, and so does the target test that entry
already names (an amplifier artefact will not move when metal approaches). If the lobe *is* real
and *is* the coil, then the calibrated ladder and the fit are both wrong in a way this analysis
cannot see, and that is the more interesting outcome of the two.

**Three consequences that do not depend on which way the lobe goes.**

1. **Air carries no information past ~21 µs on this band.** The fitted curve is inside ±3σ of
   the pedestal (±44 µV at the measured 14–15 µV floor) from sd 21.2 µs onward. Of the eleven
   columns in `cal_110_full_range_v4`'s 150 µs band, **eight** — 21.88, 30.99, 43.89, 62.15,
   88.02, 124.65, 176.53, 250 µs — sit in that region. They are not dead cells; they are cells
   where the air baseline is flat and *every* millivolt is target. That is the same thing the
   2026-08-03 close-target entry saw from the other side, and it is directly relevant to the
   cell-reduction work: those eight columns are near-duplicates *in air* and only separate on a
   target.
2. **`cal_110_full_range_v4`'s interior threshold labels are wrong by a large factor, as its own
   profile entry warned.** That ladder's `threshold_v` came across from `test v4h` "pending the
   voltages this ladder actually reaches on the bench". Against the fit, the column labelled
   0.5 V at 62.15 µs is on the pedestal; 0.5 V is actually reached near 11.5 µs. Only the first
   two or three columns are on the decay at all. The delays are bench-verified and fine — it is
   the voltage labels that should not be quoted.
3. **The rail is closer than the free-air numbers suggest, and it is a non-ferrous problem.**
   Scaling a target term to the one measured post-pedestal amplitude (+11.0 mV over floor at
   22 µs, 2026-08-03 close capture) and giving it the ordinary sign convention (§17.6), a
   *ferrous* target never crosses the pedestal — it sits above it and is still ~0.9 mV up at
   sd 250 µs. A *non-ferrous* target crosses **down** through the pedestal (≈15.4 µs on this
   band) and bottoms out under it, and at the measured coupling it reaches 5.2 mV — **19 % from
   the 3 mV rail.** So the sign of the post-pedestal reading is itself a family discriminant,
   and the cells at risk of clipping are the non-ferrous ones, at close range, in the same
   delay window the 2026-08-05 entry already flagged as unusable. Both target curves are
   illustrative — sign and amplitude anchored, time constants assumed — so treat the 15.4 µs
   as a shape, not a number. (2026-08-05)

---

### utilities/decay_model/decaymodel.py — v1 — new offline decay/crossing model and plot

New standalone tool, offline, read-only against the repo (reads the tracked profile JSONs,
writes only its PNG). Fits the air decay to the calibrated `cal_63_air_bat_v3` ladder,
extrapolates the rigid band shift to a 150 µs drive pulse (+0.24 µs, from the shrinking
per-band slope that §14.6 flags as a coil-current plateau), overlays illustrative ferrous and
non-ferrous target terms, and renders a three-panel figure across 4 → 250 µs sample delay:
the whole span on log-log, the region where the three curves separate, and the late window
with `cal_110_full_range_v4`'s 150 µs columns marked. Prints every number it derives, labelled
measured or modelled.

It exists because that separation is the whole point — the module docstring is an explicit
measured/modelled/unresolved split, the fit consumes only the calibrated ladder, and the
2026-08-05 session observations are **held back and used as a check**, which is what makes the
agreement at sd 20/30/100 µs meaningful and the disagreement at sd 14 µs legible. The model is
not drawn where it is not valid (below its own peak, across the clamp-release stretch), and the
lobe is plotted as an observation sitting off the curve rather than fitted into it. Run:
`.venv/bin/python utilities/decay_model/decaymodel.py [--pulse 150] [--out …]`. (2026-08-05)

---

### findings — the sub-0.5 V plateau has a negative lobe under it; the 3 mV bottom is a rail, not the floor

Bench session 2026-08-05, `pimd_gui` v4.14 (title bar), Mode 1, 100.0 µs pulse / DS 256, pack
23.16 V ("clean window"), board 34.4 °C, GUI at 500 µV/div, on battery. Firmware version not
captured this session. The operator reported the sweep at 3.125 kHz; the reference screenshot
is 4.000 kHz / 100.0 µs / sd 30.000 µs. Delay figures below are as reported. Sample delay swept
by hand across the region the 2026-08-03 entries left open.

**Observed.** ~4.3 V at sd = 8 µs, falling to a **flat ~3 mV bottom** held across roughly
0.5–1 µs around sd ≈ 14 µs, then rising to ~17 mV by sd ≈ 20 µs and sitting there unchanged all
the way out to sd = 100 µs. Across that boundary the Mode 1 std dev drops from ~300 µV to
**14–15 µV**, and the cell still responds clearly to every metal presented. Below the boundary
the reading shows the usual thermal behaviour; above it, it does not. Both acquisition paths
agree on the settled level — at sd = 30 µs the filtered path (SDOA) reads 16.674 mV / σ 15 µV
while the raw boxcar (SDOB, `A32`) reads 16.269 mV / σ 709 µV — so the plateau is not a
decimation-filter artefact. (That 709 µV is the firmware's per-sample σ over the 32 raw samples,
not the σ of their mean, so it is directly comparable to §7's ±1400 µV single-sample figure and
is better than it at this operating point.)

**This refines the 2026-08-03 reading; it does not overturn it.** That entry had the sub-0.5 V
columns "crossing below the RX chain's floor", with the mean thereafter reading the floor
(~16–18 mV, the same in every band regardless of delay). An additive floor can only be
approached from above. **A dip to 3 mV, below the 17 mV level, cannot be a floor effect** — it
requires a signal component of about −14 mV or more negative. The earlier fine sweeps (a smooth
monotonic 6 → 17 mV rise on the 25 kHz bands) were looking at the *recovery* side of a feature
whose bottom they never reached.

Three separate things are stacked in the trace, and separating them is most of the value here.

1. **The ~17 mV level is a DC pedestal — the instrument zero, not signal.** The 2026-08-03
   measurement is the proof: a level identical across delays from 20 µs to 250 µs and across
   every band cannot be decay. The arithmetic is consistent with LT6203 input bias current
   flowing out through R9 = 4.7k — near the ground rail the part's PNP input pair sources bias
   current, and ~3.6 µA × 4.7k ≈ +17 mV, with the datasheet typical (6.5 µA) giving ~31 mV, so
   the measured level sits inside the part's spread. **Inferred from the datasheet and the
   measured level — not measured.** The cheap check is to add 4.7k in series with R9 (the safe
   direction: it *reduces* clamp current, which §7 already flags as possibly under-estimated)
   and see whether the pedestal moves to ~34 mV. If it does not, this model is wrong and the
   pedestal is something else — amp Vos with unexpected gain, or ADC offset.
2. **The 3 mV bottom is a hard rail.** The signal path is unipolar — single +12 V supply, 0–5 V
   into the ADC — so the LT6203 output saturates a few mV above ground. The flat bottom is the
   signature; a genuine minimum would turn around smoothly, and the operator confirmed it is
   flat across several delay steps rather than a single touch. It is *not* an ADC zero code,
   which would read exactly 0 µV. **The lobe's true depth is therefore unmeasurable through this
   path** — at least −14 mV, and the width of the flat says more than that.
3. **One sign reversal is expected behaviour for this front end, not a defect.** The RX network
   is second order with two real poles (≈ R1·C fast, ≈ L/R1 slow). Released with energy in
   *both* L and C — which a 265 V flyback guarantees — the response is a sum of two decaying
   exponentials with opposite-sign residues, and that has exactly **one** zero crossing. A
   critically damped release does it too; it is not evidence of wrong damping. **It is not
   ringing** — ringing means repeated crossings, and §17.4 already located the real ring at
   ~2.08 MHz, dead by 7–8 µs, whereas this lobe is ~7 µs wide (≈150 kHz half-period). Using §7's
   stale inductance, L/R1 = 3.9 mH / 1.3k ≈ 3 µs is the right order for the slow pole. This is a
   direct use for §7's outstanding "re-measure RX self-resonance to pin L and C" item.

**Consequence for R1: damping is the wrong knob.** Reducing R1 pushes the two poles further
apart — null earlier, reverse tail *longer*, which is worse for the quiet region past it.
Raising it pulls them together — null later, tail shorter — until it crosses into real ringing.
Neither removes the crossing. No front-end change proposed and none made.

**What is not established.** Whether the lobe belongs to the coil network at all. The LT6203
input is clamped hard for the first ~7 µs of every cycle at this duty (40 % at 4 kHz / 100 µs),
and amplifier overload recovery produces mV-scale tails over µs that would look identical from
the ADC's side. Nothing in the delay-sweep data distinguishes the two, and it cannot be settled
from the record. The discriminating test does not need a scope: an amplifier artefact will not
move when a target approaches. Scope detail to follow from the operator.

**Operating note.** Any cell landing between roughly 13 and 20 µs at this band is reading a
rail, not a signal — non-linear, sign-ambiguous and worthless as a calibration point. The locked
`cal_63_air_bat_v3` never sweeps below 0.5 V so it is unaffected, but hand-edited ladders that go
lower can land there; `pimd_delaycal` has a signal-detect *ceiling* (`sp_signal_v`, 4.9 V) and no
floor, so nothing currently warns about it. (2026-08-05)

---

### findings — the recorded noise floors are slope × timing jitter, not amplifier noise

Follow-up to the entry immediately above, same session.

The σ drop across the boundary — ~300 µV below, 14–15 µV above — is not the noise improving. It
is the **slope term going to zero**. §14.3 already models the soaked per-cell floor as
slope × equivalent timing jitter (70–130 ps across most of the grid); this is the same model seen
from the other end, at a delay where the slope against sample delay is ~0 and only the amplitude
term survives.

Consistency check, order of magnitude only: fitting τ_fast ≈ 0.9 µs to the 4.3 V @ 8 µs →
~17 mV @ ~13 µs leg gives a slope near sd = 8 µs of ~4.8 mV/ns, and 300 µV / 4.8 mV/ns ≈ **63 ps**,
just under §14.3's 70–130 ps band. The τ is fitted from three hand-read points and the 300 µV was
not tied to a specific delay, so this is corroboration of the model, not a measurement of the
jitter.

**Why this matters more than it looks.** Every filtered-path noise figure in DESIGN §3 (≈ ±200 µV,
and §7's "real-world 450 µV floor") was measured *on the slope*, so each is a mixture of two
unrelated quantities. Measured with the slope removed, the same chain reads **14–15 µV at DS 256**
— 13–30× better. The amplitude floor and the timing floor are separate specifications. The §14.8
re-measurement backlog should record which one it is measuring: a noise figure without the slope
it was taken on is not comparable to another one.

**The same argument disposes of thermal drift in this region.** §14.1's 50 µV/s predicts ~9 mV
over the reference screenshot's 180 s trace; the trace is flat to well inside 100 µV at
500 µV/div — at least ~100× below prediction. Drift cannot couple into a reading whose slope
against delay is zero, which would make the far side of the null intrinsically immune to the
reference-age ceiling §14.1 calls a hard limit on any frozen-reference measurement. Read from one
screenshot, not from a dedicated soak — worth measuring properly before it is relied on.

**Open, and the reason the negative lobe is worth pursuing rather than wearing.** Crossing *times*
are invariant under amplitude scaling, and the dominant confounder in §14.7/§17.13 is pack voltage
*scaling* the decay (~11× across its range, against ~2.5–3× for soak). The clip destroys the
lobe's depth but not its timing: the trace crosses the 17 mV pedestal cleanly on both sides of the
lobe, and both crossings are in the linear region, so both are measurable now with no hardware
change. From the same τ fit the slope at the crossing is ~200× shallower than at sd = 8 µs (order
20 µV/ns), which against the measured 14 µV floor puts the crossing's own resolution below a
nanosecond and implies ~1 mV of target signal would move it ~40 ns. That is roughly the *same*
SNR as reading the 1 mV directly in the flat window — the attraction is not sensitivity but a
coordinate that does not move with the pack. Whether the crossing carries target information at
all is unmeasured, and is the same experiment that settles the coil-vs-amplifier question in the
entry above. (2026-08-05)

---

### src/pimd_gui.py — v4.14 — UI folded into the app, pack/temp gauges, session logs, full pulse/delay range

Five changes in one pass, all in the Mode 1 GUI; no firmware or wire-protocol change (DESIGN
§9/§11 untouched — the app still sends only `S`/`E`/`*`/`A<n>`/`V`).

**1. `pimd111.ui` / `pimd111_ui.py` retired.** The window is now built in code
(`_build_ui()` and four `_build_*_block()` helpers), like `pimd_classviz.py`,
`pimd_delaycal.py` and `pimd_rawlog.py`. The generated module had become a liability rather
than a convenience: every edit since v4.06 was a *deletion* performed at runtime
(`getattr(self.ui, 'label_9').setParent(None)` for the dead F1–F4 preset chips, then the same
for four V/div radios in v4.12), with new widgets bolted onto layouts by object name
(`gridLayout_2`, `formLayout_10`) — so the real layout could only be read by holding both files
in your head at once, and Qt Designer had not been used since 2026-07-02. Both files deleted;
`README.md`'s layout listing and `USAGE.md` §3 updated. Behaviour preserved deliberately:
same widgets, same button-group ids (now assigned explicitly with `addButton(btn, id)` rather
than relying on Qt's implicit −2, −3, … allocation order, which the `vert_scales` /
`horiz_scales` dicts silently depended on), same key chips, same settings keys — an existing
`gui_settings.json` loads unchanged.

*One latent bug fell out of the move.* `apply_soc_defaults()` sets the sliders to values they
already hold at construction, so `valueChanged` never fired and the three QLineEdits kept
whatever text the `.ui` file carried (`25.0 kHz` / `10.0 us` / `7.6 us`) until settings were
loaded over them — on a first run with no settings file those stale strings were what
`change_parameters()` then parsed and sent. The defaults now set the displays explicitly.

**2. ENT / SPC removed.** The Return→Connect and Space→Start/Stop shortcuts and their two
chips are gone. Both are single, deliberate actions at the start of a run, and Space in
particular is one fat finger away from stopping a soaked rig mid-capture.

**3. Connect / Start brought in line with the newer apps.** Connect now sends `E` (safe state)
then `V`, as `pimd_classviz.py` and `pimd_delaycal.py` do; Start is **disabled until a port is
open** and refuses to run without one (previously "Running" would light up green against a
closed port, log to a file and show nothing, with no indication why); disconnecting stops a
running acquisition first; the port field is `.strip()`ed and matched to classviz's width.
State is still read back from the button text, as in the other two apps — left alone
deliberately, since making this app the odd one out is worse than the idiom. New alert line
under the port field carries firmware complaints (`Command Input ERROR: …`, `LOCKOUT: …`),
which the app previously dropped on the floor: the status bar is rewritten ~20×/s by the `*`
stream, so an error posted there is invisible.

**4. Raw-voltage progress bar replaced with pack + board-temperature gauges.** The old
vertical `dialV` bar duplicated the Current readout beside it, at 50 px of width. In its place,
consuming firmware v4.28's new telemetry: a **battery-icon gauge** — fill and centre text are
state of charge, caption is the measured pack voltage and which DESIGN §12 *data-quality* zone
it sits in (≥24.0 above the ceiling / 23.3–24.0 transition / 21.5–23.3 clean window / below
that out of window / ≤21.0 lockout floor), with the clean window's lower edge drawn as a dashed
tick — and a plain **board-temperature bar**. Fed by the unsolicited `P` line plus a 10 s `V`
poll, because the firmware re-samples both channels at 1 Hz but only reports `P` every 60 s,
and `V`'s trailing fields also carry the lockout flag. A latched lockout turns the gauge red,
stops the run, and prints the firmware's own line in the alert row.

SoC comes from the same nominal ICR18650-26C curve as `utilities/pack_discharge/packv.py`,
copied rather than imported (nothing in `src/` depends on `utilities/`, DESIGN §15). It is
applied to the **loaded** voltage with no correction, so it reads a few percent low while
pulsing (~0.29 V at the terminals, §12) — an indicator, not the calibrated runway number, and
commented as such. The temperature scale is the firmware's **placeholder** linear mapping,
so the gauge is deliberately single-colour with no threshold bands: inventing green/amber/red
limits on an uncalibrated placeholder would read as measurement.

**5. Pulse and sample delay reach the profile maxima.** Ranges were 5–40 µs pulse and 5–30 µs
delay (sliders) against 5–100 µs (typed entry), which cannot reach the cells the current
profiles actually sweep. Now **4–150 µs pulse / 4–250 µs delay**, taken from
`cal_110_full_range_v4.json` (pulse 4.0–150.0, delays 4.288–250.0), so Mode 1 can sit on any
cell Mode 2 visits. Whether a given pair is *legal* depends on frequency — the firmware
rejects any config where `pulse + delay + 0.904 µs` does not fit inside one period
(`pulse_duties_valid()`) — and that limit is now reachable at the low-frequency bands, so a new
readout under the sliders shows drive duty and `pulse+delay` against the period, turning red
before the board has to say no. The 8 ns-grid orange highlights are unchanged, and the ±10-count
(80 ns) coarse keys are deliberately left as they were: direct entry is the way across a
250 µs range, and re-tuning muscle memory was not part of the ask.

**Session logs move to `data/sessions/`.** Was `data/P<DDMM-HHMMSS>.csv`, opened in
`my_init()` — so merely *starting* the app left an empty CSV beside the settings files
(three were sitting there, two of them zero bytes). Now `data/sessions/gui_<ts>.csv` opened on
**Start**, alongside every other session dump in this project, line-buffered, with a three-line
`#` header (app version, `session_start_iso`, column names) and `# sensor:` lines interleaved as
pack/temp telemetry arrives — so a Mode 1 dump can be correlated against pack state after the
fact, which is exactly what §17.13 needed and did not have. The filename QLineEdit is replaced
by a label; nothing reads these files, so the added header breaks no consumer. Path is now
absolute (script-relative), not `'data/…'` against the process cwd.

**6. Current readout to µV, and the alert row now clears itself.** Two bench annoyances found
on the first real run. The Current readout formatted a µV integer as `{:9,.0f} mV`, throwing
away the whole sub-mV part — the part being measured; now `{:9,.3f}`, i.e. the full resolution
the `*` record already carries (minimum width 120 → 150 px so the column does not reflow when
the first packet lands). And the new alert row only ever *wrote*: the single clear was on a
successful Connect, so `Command Input ERROR: rejected pulse config (drive_duty=78748,
sample_duty=135161)` sat under the Session row for the rest of the session, while the board ran
happily on a later, valid config. A firmware complaint is about the config that was live when
it was sent, so it now retires when that stops being true: non-sticky alerts self-clear after
`ALERT_CLEAR_MS` (10 s, single-shot `QTimer`), and `change_parameters()` clears before sending
a new `*` — a still-bad config re-alerts within one serial round trip. A latched **LOCKOUT** is
posted `sticky=True` and is exempt from both, since it is a standing condition, not an event:
it goes only on a reconnect or when a `V` reply reports the latch dropped. (2026-08-05)

Verified offscreen against synthetic `*`/`R`/`P`/`V`/`LOCKOUT` lines: layout renders, gauges
track, session file lands in `data/sessions/` with the expected content, the period-fit readout
flips red at 25 kHz / 150 µs / 250 µs and back to a 30.0 % duty at 2 kHz. **Not yet run against
the board** — firmware v4.28's own sensor path is itself still bench-unverified. (2026-08-04)

---

### mcu/pimd_mcu.py — v4.28 — pack-voltage + board-temp sense (ADC), 'P' telemetry, hard-latched low-voltage failsafe

Motivated directly by an incident: the rig was left running unattended and two 18650 cells
over-discharged past recovery, because there is no voltage-sense hardware on the board and no
firmware concept of pack state at all (DESIGN §12: "no divider, no thermistor, no NTC;
GP26-29 appear only as symbol pins"). Schematic sheet 2
(`References/images/schematic-v604-sheet2.jpg`) shows all four RP2040 ADC-capable pins
(GP26-29) already wired to onboard 10k pots (`POT-0`..`POT-3`) for bench bring-up, unused by
this firmware until now — which lets the whole path below be exercised on the bench without a
real pack divider or thermistor circuit.

New `machine.ADC` reads on GP26 (pack voltage, `POT-0`) and GP27 (board temperature, `POT-1`);
GP28/29 (`POT-2`/`POT-3`) are the spare fallback pins if GP26/27 turn out to carry something
else on the real board (flagged for a schematic-sheet-1 check before flashing). Both channels
are 64x-oversampled and serviced together at 1 Hz by a new `service_sensors()`, reusing the
exact `ticks_ms()`/`ticks_diff()` idiom `acquire_mode2()` already used for
`MIN_EMIT_MS`/`COMMAND_POLL_MS` — no new scheduler. `service_sensors()` is called from both the
main loop and from inside `acquire_mode2`'s own `i==0` block, because the main loop's call
doesn't run while control sits inside `acquire_mode2`'s internal `while` for the duration of a
Mode 2 sweep. Every 60 s it emits a new unsolicited, additive telemetry line —
`P<time_ms>,<pack_mV>,<board_temp_dC>` (board_temp_dC is deci-°C, x10 integer, matching the
project's no-floats wire convention) — a prefix no PC tool currently checks for, the same
property that made the `B` line (v4.11/v4.27) safe to add: `pimd_gui.py`, `pimd_classviz.py`,
`pimd_delaycal.py` and `pimd_rawlog.py` all dispatch on `line[0]`/prefix with no catch-all
`else`, so this breaks no consumer. `V` also gains three additive trailing fields
(`pack_mV`, `board_temp_dC`, `lockout`) for the same reason — confirmed nothing in `src/`
splits `V` by field count.

**Low-voltage failsafe**, the higher-priority half: at the 21.0 V floor DESIGN §12 already
documents as the working discharge limit (`PACK_VOLTAGE_TRIP_MV = 21_000`), three consecutive
1 Hz debounced readings latch `pack_voltage_lockout` — forces `state = 'stop'`, calls the
existing `set_safe_state()`, and permanently rejects `S`/`G`/`D` until a physical power-cycle
clears the RAM-only flag. **Deliberately a hard latch, not an auto-resume or a soft re-arm
command** — an automatic resume would repeat exactly the failure mode that damaged the cells
(voltage creeps back up under no load once pulsing stops, a resume reloads the pack, it sags
again). A new `pack_voltage_boot_check()` runs before `'Ready'` is even printed, so a rig
powered on already below the floor never fires a single pulse. `A<n>` is deliberately left
unblocked — verified by reading `acquire_raw_average()`: it never calls `duty_u16()` on either
PWM, only reads at whatever duty `set_safe_state()` already zeroed, so it cannot re-arm the
coil even though the command stays callable.

Both ADC-to-physical mappings (`PACK_VOLTAGE_FULLSCALE_MV = 25_000`,
`THERM_TEMP_FULLSCALE_DECIC = 1500`) are **placeholder linear scales** — the real analog front
ends (pack divider, thermistor conditioning) don't exist yet; 0-3.3V↔0-25V and 0-3.3V↔0-150°C
are the design target as specified by the operator. Flagged explicitly rather than glossed
over: a raw NTC thermistor+divider is **not** linear in temperature (Beta/Steinhart-Hart
curve) — if that ends up being the chosen part, this linear placeholder needs replacing with
the correct curve or a lookup table, not just re-tuning the constant.

Scope deliberately excludes any PC-tool change in this pass; `pimd_rawlog.py` already logs
every raw serial line verbatim regardless of prefix, so it verifies the new `P` line with zero
PC-side code changes. **Not yet verified live** — needs the bench pass in the implementation
plan's checklist: a `POT-0`/`POT-1` sweep smoke test via `pimd_rawlog.py`, then trip/boot/
recovery tests using `POT-0` in place of a real pack. (2026-08-04)

---

### src/pimd_rawlog.py — v1.14 — settings persistence, matching the other PC apps

`pimd_rawlog.py` was the only PC app without settings persistence — port, target/distance,
settle window/threshold, warm-up target, and window geometry all reset to defaults on every
launch. Added `_load_settings`/`_save_settings` following the same JSON-file pattern as
`pimd_gui.py`, `pimd_delaycal.py`, `pimd_classviz.py`, and `pimd_classify.py` (each app owns its
own settings file — `data/rawlog_settings.json` here — not a shared one), loaded at the end of
`__init__` and saved from `closeEvent`. The loaded profile itself is not persisted, consistent
with the other apps (a profile is re-selected via Load Profile / Resume Session each run, not
auto-restored). (2026-08-04)

---

### src/pimd_classify.py — v1.3 — Heatmap rows now match the standard grid orientation

`_band_display_order` sorted bands by first delay value **descending**, and with
`invertY(True)` on `heat_plot` that put the longest-pulse/longest-delay band at the top of the
heatmap and the shortest at the bottom — the opposite of this project's standard grid
orientation (declared in `pimd_rawlog.py`'s header, CHANGELOG v1.13: shortest pulse/delay
top-left, longest bottom-right). Flipped the sort to ascending so this file's heatmap now
agrees with `pimd_rawlog.py`'s raw-value grid and `pimd_classviz.py`'s tables/heatmaps. Found
while auditing `pimd_classviz.py` for the same bug (below) and confirming cross-app
consistency, at the user's request. (2026-08-04)

---

### src/pimd_classviz.py — v1.70 — Main/Analysis heatmap rows now match the standard grid orientation

Same bug as `pimd_classify.py` v1.3 above: `_band_display_order` sorted bands by first delay
value **descending**, so with `invertY(True)` the Main Heatmap and Analysis Heatmap tabs (which
both reindex by this array) showed the longest-pulse/longest-delay band at the top and the
shortest at the bottom — inconsistent with `pimd_rawlog.py`'s declared standard grid
orientation (v1.13: shortest pulse/delay top-left, longest bottom-right) and with this file's
own Stats table, which already derived an ascending (correct) order from the same data via
`reversed(_band_display_order)`. Flipped `_band_display_order` to sort ascending and stopped
deriving `_band_stats_order` by reversing it — both are now the same ascending order, so the
Stats table's already-correct row order is unaffected. Verified against the profile actually in
use, `cal_110_full_range_v4.json`: its bands list `pulse_us` and `delays_us[0]` both ascending
together, so ascending-by-delay is a valid pulse-width proxy for this profile. (2026-08-04)

---

### src/pimd_delaycal.py — v1.45 — Std dev table Colour lo/hi: lo spinbox floor -999 mV (was 0)

The "Colour lo/hi" pair that drives Absolute-mode colouring on the bottom (Std dev / metric)
table shares its lo/hi spinboxes across every metric in the selector, including "Mean level" —
the one metric that isn't a spread measure but the cell's raw signed mean reading (v1.44 gave it
a diverging green/red-by-sign scale). `sp_stddev_lo_mv` was still floored at 0.0 mV from when
every metric was an unsigned spread, so a negative mean reading clipped straight to the lo end
(t=0) regardless of how far negative it actually was, losing all resolution below zero. Lowered
the floor to -999.0 mV (matching the existing ±999 span used elsewhere for these spinboxes); the
hi spinbox's floor is unchanged. (2026-08-04)

---

### .claude/settings.json — config — worktree.bgIsolation set to "none"

Background-job (bg-agent) sessions were auto-isolating every edit into a fresh git worktree,
branched from `origin/main` by default. That's what produced the multi-worktree tangle cleaned
up the same day: `main`, `worktree-move-jpg-images` and `worktree-rawlog-instrument` all
diverging independently, one of them (`worktree-rawlog-instrument`) accumulating zero real
commits while unrelated work landed straight in `main`'s working tree instead. No git config or
prior settings entry actually controlled this — a CLAUDE.md line added in an earlier session
("we prefer to only work in one branch at a time") read as a fix but had no mechanism behind it;
it's been reverted.

Setting `worktree.bgIsolation: "none"` in `.claude/settings.json` makes background jobs edit the
shared checkout directly, like a normal foreground session — no more auto-created worktrees to
merge back and clean up. Trade-off: the isolation that stopped a background job and concurrent
foreground work from touching `main` at the same time is now off. `.claude/` is itself gitignored
in this repo, so this entry is the only record of the change; the setting takes effect purely by
the file existing on disk. (2026-08-04)

---

### DESIGN.md — 1.13.1 — post-consolidation corrections (§18)

Human-directed, read-only rule suspended per §18. **Not a consolidation and no new bench data** —
this folds in the four entries below, all of which are same-day desk work on defects 1.13 had
itself recorded as *known but not fixed*. Doc-rev 1.13.1 rather than 1.14, matching the 1.9.1 /
1.8.1 precedent for a correction pass.

**Why it was needed immediately rather than at the next §18.** 1.13 shipped three statements that
the same day's code changes made false — §14.12 "recorded there and not fixed", and two §15 rows
carrying "Known defect … not fixed". A curated snapshot that describes fixed defects as open is
worse than one that lags, because a reader has no way to tell which claims are stale.

**Sections changed.** Header → versions classviz **v1.69**, delaycal **v1.30**, features **v14**;
Doc-rev 1.13.1, keeping 1.13's summary as a one-line `Previous:` tail rather than a chain.
**§14.12** rewritten from an open problem to a resolved one, carrying the measured before/after
(61 of 4 079 windows now refused on the 07-29 stall dump; worst case 101 s / 14× nominal, from
which the old path drew 1 716 µV of drift as noise; the glitch half verified by injection at
334× → 1.00× because all 12 dumps hold **zero** mid-run glitch frames). **§15** classviz,
features and delaycal rows carry the fixes and both "Known defect" notes are gone. **§17.15**'s
closing line updated — the change it called for was made.

**New §14.15 — both offline acceptance gates fail on the current corpus, and neither failure is a
regression.** This is the one genuinely outstanding item and it needs an operator decision, so it
is recorded as an open problem rather than quietly fixed. `pimd_shape --selftest` reads FAIL (46)
against v3 and PASS against v1 because its expectations are hard-coded from the 2026-07-23
`cal_63_air_v2` analysis and **38 of the 46 are the crossing ladder**, which §17.14 has just shown
to be per-epoch — so §16's documented command has been wrong since the registry moved to v3.
Three fixes are possible and none is obviously right (point back at v1 / re-derive against v3 /
parameterise by epoch), and the trade-offs are recorded with it. `pimd_corpus_check`'s 411 checks
/ 229 FAIL is **not diagnosed** and is written as such — consistent in kind with §17.14's own
measurements, but not assumed to be them. **§16 carries a caveat on both commands** and its
selftest line now points at the v1 corpus, which is the only invocation that currently means
anything, until §14.15 is settled.

**Nothing dropped, no content removed.** (2026-07-31)

---

### findings — the documented `pimd_shape --selftest` command fails, and §17.14 says why

Found while regression-testing the v1.69/v1.30/v14 fixes, **pre-existing and unrelated to them**
(identical output with those changes stashed). Recorded, not fixed — the fix is a judgement call
about what the acceptance test is for.

`DESIGN §16` instructs:

```
python pimd_shape.py --selftest data/corpora/gui_signatures_targets_v3_20260728_142316.csv
```

That reads **FAIL (46 problems)**. Against the v1 corpus it reads **PASS**. The expectations are
hard-coded from the 2026-07-23 `cal_63_air_v2` analysis, and 38 of the 46 are item 3 — the
**crossing ladder**, which §17.14 has just established is a **per-epoch quantity**: under v3 every
interior crossing moves shorter by ×0.76 median, so `Fe_SS_disc_01 @60` reads 18.59 µs against a
hard-coded `30.6 ± 1.5`. The test is not detecting a regression; it is correctly reporting that
the corpus it was pointed at belongs to a different epoch from its expectations. Item 4's two
failures are the same story (`Fe_Cast_iron_trivet_01 @120` decay 1.15 — the §14.13 rogue capture)
and item 3 also names `Fe_SS_shackle_01` / `Fe_Zn_gal_pipe_01` captures now absent from the gated
set.

So §16's command has been wrong since the registry moved to v3: the selftest is an acceptance
check for the **feature maths**, and it can only serve that role against the corpus its
expectations were derived from. **Three options, none obviously right:** point §16 back at
`gui_signatures_targets_v1_20260723.csv` (honest, but the check then never exercises the current
epoch); re-derive the expectations against v3 (exercises the live epoch, but bakes in the rogue
capture unless it is excluded first); or make the expectations epoch-parameterised. Wants a
decision before the next capture day leans on it as a gate.

Separately and also pre-existing: `pimd_corpus_check` on the v3 corpus reads **411 checks:
181 PASS, 229 FAIL** — 101 `splithalf-snr`, 95 `repeat-consistency`, 24 `shape-invariance`,
9 `distance-falloff`. Not diagnosed here. Consistent in kind with §17.14's own measurements (the
SNR gate really being a reproducibility gate of ≈ 2.5–3.5, the §14.13 rogue capture, the §14.14
solder spool), but the count is high enough to want its own look rather than an assumption.
(2026-07-31)

---

### src/pimd_classviz.py — v1.69 — FIX both Std Dev displays bypassed the glitch filter and the stall guard

The Std Dev (rolling N) heatmap was the only heatmap mode not getting two guards the other
three get. The Stats table's **Mean/Std columns share the same defect and the same fix** — they
had to, because "the heatmap and stats-table std dev always agree for the same N" is a stated
property of `_compute_rolling_stddev_nxn()`, and fixing one alone would have quietly broken it.
Both are display-path only: **no recorded data was ever affected**, and no corpus row, session
dump or capture changes.

**1. No glitch substitution.** Both read `_rolling_buf`, which holds unfiltered `raw`; the
Δ / Z / RAW modes read `_latest_raw`, which is the 64-frame-median-substituted `raw_display`. So
a single ADC bit-truncation artifact entered σ at full weight and stayed visible for a whole
window (~7.2 s at N=50) — **a glitch drawn as a noisy cell, in the display used to judge noise.**

**2. No window-span stall guard.** Both sliced the buffer directly, so under a host stall
(§14.10) they reduced across the gap and drew accumulated **drift** as noise while the gauges
beside them correctly refused. This is the exact failure that manufactured the phantom
2026-07-29 "noise relapse".

**The fix.** A new `_rolling_disp_buf` carries the glitch-substituted frames, appended in
lockstep with `_rolling_buf` and `_fw_ms_buf` and with the same maxlen, so index `-k` aligns
across all three — the same parallel-deque pattern v1.64 used for the firmware clock, and for
the same reason (`_rolling_buf` must keep holding unfiltered raw, because the session dump and
the capture path read it and a recording has to stay faithful). `_get_current_baseline()`'s
rolling mode is deliberately **left on the raw buffer**: it reduces with a median, which is
already immune. A single new `_stddev_window()` is now the only place either display computes σ,
so they cannot drift apart again.

`_window_frames()` gains `record=False`. The guard's side effect — publishing span and reason for
`_window_status_text()` — is ordering-sensitive, and the heatmap redraws on the 30 Hz timer
*ahead* of the gauges, so a recording call from it would have described the heatmap's window
underneath the gauges' number. New `_window_last_span_s` / `_window_last_reason` are written
either way so a non-publishing caller can still read its own verdict. All four existing callers
keep the default and are byte-for-byte unaffected.

**Refusal is now visible rather than silent**, which was the point of the guard in the first
place: the heatmap draws zeros *and* the scale label reads `STALLED 307 s window — not reduced`
(or `filling…`), and the Stats table shows `—` with neutral colouring instead of a green cell
over a stall. Drawing a stalled stream as a quiet grid would have been a new version of the same
bug.

**Measured before/after on the real dumps**, since this changes a long-standing instrument.
Replaying `session_20260729_191643` (the 47-minute stall) through both paths: of 4 079 sampled
windows, **61 are now refused that the old path reduced**, worst case a window spanning **101 s
(14× nominal) from which the old path drew a mean σ of 1 716 µV** — drift rendered as noise, at a
magnitude squarely in the range of the elevated-column readings this display exists to detect.
A healthy dump (`session_20260730_171026`, 89 692 frames) refuses **nothing**, so the guard does
not cost normal operation.

**The glitch half is defensive, and the honest statement is that it has no measured effect on
anything on disk.** Across all 12 session dumps (373 k+ frames) there are **zero mid-run glitch
frames** — every flagged frame sits in the first 64, i.e. the glitch buffer's own fill period.
Verified by injection instead: one 600 mV artifact on one frame takes the old path to
**83 993 µV, 334× the 251 µV floor**, while the new path reads **252 µV, 1.00×**.

Verified against the real methods (bound to a stub, frames from a real dump, no Qt widgets):
σ on a healthy window matches a direct reduction exactly; `record=False` leaves the published
pair untouched while still setting the last-reason; σ follows the substituted buffer, not raw;
a 300 s gap is refused with the span available for the label; too few frames reads `filling`,
not `stalled`; and a backwards firmware clock refuses with span left `None` so the label says
just `STALLED`. Both apps still construct headless. (2026-07-31)

---

### src/pimd_features.py — v14 — TOOL_VERSION constant re-synced with the header

`TOOL_VERSION` sat at `pimd_features.py v11` through the v12 and v13 edits while the header read
v13 — the same de-sync `pimd_delaycal.py` v1.25 fixed. It is not a label: it is stamped into
every corpus row's `tool_version` column, so anything built by v12 or v13 was recorded as the
work of v11. Nothing on disk is affected — all corpus rows to date come from classviz directly,
not through this path — but the next `--out` build would have mislabelled its output. Bumped to
v14 rather than quietly set to v13, so the corrected stamp has a version of its own and the
`tool_version` values in any future corpus stay meaningful. Constant now carries a comment saying
it is output, not a label. (2026-07-31)

---

### src/pimd_delaycal.py — v1.30 — fine step snapped to the 8 ns grid at default, restore and use

The fine-step spinbox shipped a default of **100 ns**, which is 12.5 PWM grid steps —
reintroducing *as a default* the off-grid condition v1.26 existed to remove. The stepper cannot
produce an off-grid value (range and single-step are both 8), but three other routes can, and one
of them is how 100 got there: `_load_settings()`'s v1.25 migration multiplies a stored µs value by
1000, so a persisted `0.1 µs` lands on exactly 100 ns; typing works too; and an off-grid value
then persists itself on the next save, which is how it survived v1.26.

Fixed at all three points rather than just the default: new `PWM_GRID_NS` / `FINE_STEP_DEFAULT_NS`
constants (default now **96 ns**, the nearest on-grid value to the old 100), a `_snap_step_ns()`
helper applied on settings restore *and* where the value becomes a sweep parameter, and the
tooltip now says what happens. The snap rounds **down**, not to nearest: a fine step is a
resolution promise, so rounding 100 up to 104 would sweep coarser than the operator asked while
96 only costs an extra sample. The existing `_snap_8ns()` delay helper now uses the same constant.

**No effect on the current bench setup** — the persisted `step_ns` is **40**, already on-grid and
the value DESIGN §10 records for the `cal_63_air_bat_v3` sweep. This only bit a fresh install or
a cleared settings file. (2026-07-31)

---

### DESIGN.md — 1.13 — consolidation pass (§18)

Human-directed, read-only rule suspended per §18. Consolidates the 13 entries above the previous
marker. Net state determined per file first; the CHANGELOG was **not** replayed.

**Three of those 13 were already in DESIGN** — the `DESIGN.md — 1.12` audit entry, the
pack-voltage re-measurement and the errata list were folded in at 1.12 and only sat above the
marker because the marker was never moved. Treated as consolidated, not re-imported.

**The result that drove the pass: family is an orientation coordinate, not a material one.** The
v3 corpus (170 captures / 25 targets, 2.6× the first and deliberately spanning orientation)
shows the early-band sign splitting by *placement* — 90.9 % accurate transverse, **53.8 % axial**,
every miss axial. The trivet reads `crossover` flat and `ferrous` on edge, because the axis
measures **presented eddy-loop area = geometry × orientation**. What survives is stronger than
the old verdict: the late-band sign reads iron-bearing vs non-ferrous at **97.2 % ungated**.
Separately, the **Pasion–Oldenburg mixing law is confirmed** on the 13 tilt-recorded captures —
oblique fits land on `cos²θ` within scatter, amplitude right to 2 %, every oblique pose a
positive convex combination of the two extremes — so orientation becomes a *fitted parameter*.

**Sections changed.** Header → Doc-rev **1.13**, classviz **v1.68**, features **v13**,
corpus_check **v1.9**; per the operator's decision the Doc-rev line is now **short with no
`(Previous: …)` chain** — the per-pass narrative lives here, in the archives. §1 gains an
orientation paragraph and the corpus snapshot moves 66 → 188. §3 gains two measured lines:
`splithalf_floor` **understates reproducibility noise ~2×** (so the SNR ≥ 5 gate is really a
reproducibility gate of ≈ 2.5–3.5), and the **between-session noise component measures zero**.
§10 **cashes in the feature-portability question** deferred since the 1.10 pass — the v2→v3 shift
is coherent and one-parameter (band means +5.2 ×10⁻³, crossings ×0.76, amplitude by family not by
gain), and **no target changed family**; the `(profile_name, profile_sha8)` guard still stands,
since the epochs are relatable rather than interchangeable. §13 gains the two-basis bullet. §14.1
gains independent offline confirmation of the reference-age ceiling; §14.7 gains the air-capture
census as a third, target-free sighting of the moving zone; §14.11 is scoped (the corner is a
second-rank floor contributor — 7 % of noise energy against the 3.80 V column's 46 %); **§14.9 is
substantially rewritten** from a noise problem to an orientation problem, with the dead band
demoted to a coverage trade. Three new open problems: **§14.12** the Std Dev heatmap bypasses both
the glitch substitution and the stall guard, **§14.13** no within-placement consistency check
(a rogue capture passes both gates at SNR 16.5), **§14.14** `Sn_Pb_solder_spool_01` is two objects
under one id and its shorted-loop behaviour is a genuine tier-1 false-positive mode. §15: rows
rewritten for classviz, features, corpus_check, delaycal, targets_v3, corpora and sessions, plus a
**new `utilities/session_relabel/` row**. New **§17.14** (six results) and **§17.15** (the
placement transient).

**Two errors of the source entries corrected rather than carried.** The v3-analysis entry says
"the §17.6 ladder values need restating against v3" — the crossing ladder lives in **§17.9**, and
the per-epoch flag was written there. And "188 captures" was carried into the §17.14 provenance
line as though the whole analysis ran on it; results 1–2 and 4–6 ran on 170, only the oblique
study takes the file to 188. Both verified against the file (188 captures / 11 844 rows / 25
targets / 100 with `pack_v` / **13** with `tilt_deg`; registry 27 objects).

**Flagged, not fixed** (both code, outside a docs pass): `pimd_features.py`'s header reads v13
while its `TOOL_VERSION` constant still reads **v11** — the de-sync delaycal v1.25 fixed, and
`TOOL_VERSION` is what stamps a corpus row; and delaycal's **100 ns fine-step default**, off the
8 ns grid and unreachable by its own spinbox. Both now recorded in their §15 rows.

**Dropped / not carried**, as changelog-level detail: the relabel tool's `--apply` mechanics
beyond its provenance and limits, the corpus tilt-migration procedure, and the withdrawn
"steel spool core" speculation (the registry row was right; recorded in §14.14 as the correction
it turned out to be). **No content removed.** Uncited-and-unmatched assets left alone rather than
guessed: `References/Targets v1 Analysis/CC_BRIEF_shape_space.md`,
`References/V3/NEXT_SESSION_handover_and_V3_profiling.md`, `References/V3/warm_bat_notes.md`.
(2026-07-31)

---

### src/pimd_delaycal.py — v1.42 — "Mean level" metric for sustained Compare-over-time; baseline log

Bench report on v1.39-v1.41's Compare-over-time: capture a baseline, most cells read green; add a
target, most go red (correct); but 10-11 seconds later, with the target still physically present,
everything reads green again. Reproduced exactly with a standalone simulation before touching any
code: a sliding 16-sample ("Samples N") window stepping from a quiet 1000 µV level to a stable
1400 µV level, computing Max |Δ from mean| frame by frame --

```
frame 39 (t+ 0): Max|Δ|=  4.94 uV  ratio=0.00   green   <- baseline captured here
frame 40 (t+ 1): Max|Δ|=381.00 uV  ratio=76.14  RED     <- target just appeared
frame 54 (t+15): Max|Δ|=379.33 uV  ratio=75.81  RED     <- window still straddles old/new
frame 55 (t+16): Max|Δ|=  5.24 uV  ratio=0.06   green   <- window now ALL target-present
```

Root cause: every metric on offer (Std dev, Range P-P, Max |Δ|, Drift, Max %Δ) is a *spread* measure
— computed relative to the window's own mean, re-centred fresh every tick. Once a step change has
fully slid out of the window (exactly `Samples N` frames later, matching the reported ~10-11 s),
the window is just as internally "flat" at the new level as it was at the old one — these metrics
are structurally blind to a *sustained* level shift, only the transition through it. Not a bug in
any one metric's arithmetic; a category mismatch between what Compare-over-time needs (a level to
compare) and what every existing metric measures (noise around whatever level currently holds).

New 6th metric, **Mean level** (`_STD_METRICS`/`_STD_METRIC_UNITS` index 5): the window's raw
average, mV, with no self-centring at all. Verified against the same simulated step change that a
Std dev/Max Δ metric would clear in ~16 frames stays at the true ~40% ratio for as long as the
elevated level holds. Selecting it doesn't change how any other metric behaves — it's an additional
option, not a replacement — and Auto Nudge's own evaluation is (as always) untouched, still reading
`_stdev()` directly at its own three call sites regardless of what this dropdown shows.

Separately, an operator counter-example ("I saw ~4 mV right at capture and that cell still greyed
out") couldn't be resolved from the screenshot alone -- "Latest mean" and the selected spread metric
are different numbers, and confirming which one was actually stored needed the real value, not
another guess. `_capture_compare_baseline()` now logs every cell's captured value to the Activity
Log on each capture (`ch<N> [<band>/<threshold>]: <value>`), flagging any that will trip the
near-zero guard in `_compare_value_ratio()` (`abs(baseline) < 1e-9`) with the exact reason a cell
will show as unsettled (`…`) instead of leaving it to be inferred. (2026-08-03)

---

### src/pimd_delaycal.py — v1.41 — FIX misleading Q5 error; client-side PWM duty pre-validation

Operator report: importing a saved profile and pressing THERMAL showed "Firmware: Command Input
Error: invalid profile index (Q5)". Traced to `mcu/pimd_mcu.py`'s `Q` handler (`:716-724`):
`Q<DYNAMIC_PROFILE_INDEX>` fails whenever `dynamic_profile` is `None`, i.e. whenever the `D` command
sent immediately before it was rejected (`validate_profile()` at `:281-288` requires every cell's
`sample_duty` to fit 16 bits, `compute_pulse_duties()` at `:253-261`, and land after `drive_duty`).
`_start_thermal()`/`_manual_push_profile()`/`_auto_run_soak()` all fired `E`/`D`/`Q<n>`/`G` as one
unconditional burst with no check that `D` actually succeeded, so **Q5's failure was never the real
story** — it's a downstream symptom of a rejected `D`, and its error line simply overwrote the
actual rejection reason in `status_label` before the operator ever saw it. Confirmed against every
saved profile in `data/profiles/`: `test v4f.json` has cells (the short-period bands' extended
"tail" delay column) that overflow the 16-bit ceiling — `sample_duty` scales with `delay × freq`, so
a tail delay that's fine on the long-period bands overflows on the short-period ones in the same
file.

**Worse than just a bad message**: a rejected `D` leaves the firmware's *previous* `dynamic_profile`
untouched, so a follow-up `G` still succeeds — Mode 2 keeps streaming on the **stale, pre-attempt**
delay set with no crash and no obvious interruption. This is exactly what the operator went on to
report separately: reducing a delay then increasing it back past the limit "still keeps going
without error as far as I can see" — the stream never stopped, it just silently stopped reflecting
the requested change.

**Fix 1 — client-side pre-validation, catch it before ever sending.** New `_compute_pulse_duties()`
/ `_pulse_duties_valid()` / `_max_valid_delay_us()` module functions, an exact mirror of the
firmware's own copy (same constants, same integer truncation — comment cross-references
`mcu/pimd_mcu.py` so the two don't silently drift apart). New `_validate_profile_pwm(profile)` /
`_warn_profile_pwm_problems(problems, context)` methods, wired in at every point a delay could
become live or get saved:
- `_on_manual_nudge_clicked()` checks the *proposed* delay before updating the cell or pushing at
  all — refuses with the offending value, the sample_duty, and the largest delay that would still
  be valid at that band's pulse width, leaving the cell exactly where it was. Refusing rather than
  clamping was the deliberate choice: silently rewriting a value mid-experiment (the operator has
  been visibly probing exactly this ceiling across `test v4a`-`v4f`) would hide the boundary they're
  trying to find.
- `_start_thermal()`, `_start_auto()`, `_manual_push_profile()` validate the whole profile and
  refuse to send anything if any cell is invalid, each with the full list of bad cells logged.
  `_auto_run_soak()` gets the same guard as defensive insurance (a nudge staying within its own cap
  should already be valid) and cleanly aborts the whole Auto Nudge run rather than soaking on
  half-applied delays if it ever isn't.
- `_import_profile()` warns (doesn't block — the table still loads as-is) immediately on import,
  the earliest point an exploratory/hand-edited grid like `test v4f.json` reaches this tool, rather
  than waiting for a THERMAL press to discover it.

**Fix 2 — for whatever pre-validation doesn't anticipate, stop sending blind.** New
`_send_dynamic_profile(profile, on_ready)` sends `E`+`D` and holds `Q<n>`/`G` back via a new
`self._pending_d_ready` callback instead of firing all four commands unconditionally.
`read_from_serial()` now checks for a pending callback first: `'E'` prints nothing, so the very next
line after sending `D` is always its own response — `'D OK'` fires the callback (which sends
`Q<n>`/`G` and does whatever state/UI setup used to run unconditionally), any `ERROR` clears the
callback and shows *that* message directly, and `Q<n>`/`G` are never sent at all. All three
reconfigure sites refactored to this pattern; `_start_thermal()`'s `_thermal_state = 'running'` also
moved inside the callback -- it must not read as running when nothing actually started.

Verified with a mock serial simulating both a `D OK` and a `D`-rejection response for all three call
sites: `Q`/`G` are only ever sent after confirmed success, the real rejection message reaches
`status_label` unmasked, and `_thermal_state`/`_auto_state` correctly stay unchanged (not falsely
"running"/"soaking") when `D` fails. Cross-checked `_validate_profile_pwm()`'s output against the
firmware's own math on a live-edited profile file and confirmed exact agreement. (2026-08-03)

---

### src/pimd_delaycal.py — v1.40 — FIX Compare-over-time: unsigned ratio, not a signed percentage

Operator correction on v1.39, two changes: don't multiply by 100 (a plain ratio, not a percentage),
and show the magnitude only (unsigned), not a signed `+`/`-` value.

`_compare_value_pct()` renamed `_compare_value_ratio()` (the old name was actively wrong once it no
longer returns a percentage) and its body changed from `(smoothed_mv - base) / base * 100.0` to
`abs((smoothed_mv - base) / base)`. Since the return value is now always ≥ 0 — matching every other
metric this table already shows — the two `abs()` wrappers v1.39 added specifically to handle a
*signed* value at the colour/rank call sites in `_update_thermal_tables()` are reverted (`sorted(...,
key=cell_values.get)` and `_value_gradient_color(val_mv)`, dropping their now-redundant `abs(...)`
wrapping and the comment explaining why it was there, which no longer applies). Both display-text
call sites drop their `:+.2f` formatting back to plain `:.2f`, matching every other metric.

Direct consequence, not scope creep: `_refresh_std_metric_label()`'s Compare-mode label changes
`' Δ (%):'` → `' Δ:'` and the Absolute-mode lo/hi spinbox suffix `'%'` → `''` (a ratio has no
natural unit) — leaving stale "%" text next to a bare ratio would be actively misleading. The
`cb_compare_mode` tooltip's wording updated to match (`0.10` now reads as "moved by a tenth of the
baseline", not ten percent). Verified: a rise and an equal-magnitude fall from baseline now return
identical unsigned values, display text carries no leading sign, and the label/suffix read correctly
in both modes. (2026-08-02)

---

### src/pimd_delaycal.py — v1.39 — Compare-over-time: baseline capture / rolling-lag %Δ, age-warned

Every metric so far (v1.36-v1.38) reads an *instantaneous* window. The operator's next ask: compare
that reading across two points in time — snapshot a baseline before touching something (a nudge, a
physical target move) and watch how far each cell has drifted since, with a visible warning once the
snapshot is too old to be a fair comparison. Same shape of problem classviz already solved for its
own "leading air reference" (`_sig_air_ref_ts`, `pimd_classviz.py:762` — captured value + wall-clock
age, coloured against a threshold, `:2938-2947`) — reimplemented here with delaycal's own plain
QLabel/table tools rather than importing classviz's gauge-widget machinery.

**Applies to whichever metric is currently selected** (confirmed with the operator over a hardcoded
6th metric) — one comparison mechanism reused for Std dev, Range, either Max Δ variant, or Drift.
Displays **percent change from baseline**: `(current − baseline) / baseline × 100`.

**Two modes**, new `cb_compare_type` combo: **Capture** — press **Space** (new
`QApplication`-level `eventFilter`, guarded on `cb_compare_mode` checked + Capture selected + focus
not in a `QLineEdit`, so typing "25/10, 20/20" with its embedded spaces or a focused button's own
Space-activates-click behaviour is undisturbed) or the new "Capture" button to snapshot every cell's
current smoothed value via `_capture_compare_baseline()`. **Rolling lag** — no action needed,
continuously compares against the reading from a new "Lag:" spinbox's worth of redraw ticks ago, via
a small per-channel `_compare_lag_buf` history.

**Persistence across reconfigures — the one non-obvious call.** A captured baseline survives a
nudge/reconfigure (the five existing `_thermal_buf.clear()` sites) — the whole point of Capture mode
is comparing *across* exactly that kind of change. The rolling-lag buffer, by contrast, *is* cleared
at those same five sites (same reasoning as `_metric_smooth_buf`: a post-nudge reading compared
against a pre-nudge lagged one is comparing across a physical parameter change, not organic
settling). Both are cleared on a metric change or a profile-shape change (`_rebuild_thermal_tables`),
since the flat channel index either is keyed on would otherwise silently point at a different
physical cell, or blend two different metrics' numbers together.

**Colouring** reuses the existing Rank/Absolute machinery (`_gradient_color_from_fraction`,
`cb_std_color_mode`) unchanged — `abs()` applied at the point colour/rank is computed (not stored in
`cell_values`, which keeps its sign for the displayed `+12.34`-style text) so a rise and a fall of
the same size read as equally noteworthy drift; a no-op for every other metric, which were already
always ≥ 0. Still gates on `manual_live`, consistent with every colouring feature this session — no
colour outside Manual Nudge's live view.

**Age label** (`lbl_capture_age`): a dedicated 1 Hz `QTimer`, independent of THERMAL's own state (a
stale-baseline warning still ticks even with THERMAL stopped), shows "no snapshot" (grey) or "Δt =
Ns" coloured green→red via the same gradient against new `sp_age_lo_s`/`sp_age_hi_s` spinboxes
(defaults 30/120 s).

New settings keys `compare_type`, `compare_lag`, `age_lo_s`, `age_hi_s`; `cb_compare_mode`'s checked
state is deliberately not persisted (same reasoning as `cb_manual_nudge` — don't surprise-arm a
keyboard shortcut on launch). Verified offline: the event filter fires only when focus is on a
neutral widget and not a `QLineEdit` (checked against a real focused widget, not just `isinstance`
on the target), percent arithmetic for both modes, baseline surviving `_auto_settle_done()` while
being cleared by a metric change or profile rebuild, and the age label crossing green→red. (2026-08-02)

---

### src/pimd_delaycal.py — v1.38 — new metric: Max %Δ from mean

Follow-up bench feedback on v1.37: neither Rank nor Absolute colouring actually answered the
underlying question. The operator's real complaint with "Max |Δ from mean|" (mV) wasn't the colour
scheme, it was the *unit* — two cells with genuinely similar relative noise read as wildly different
absolute mV numbers whenever their underlying signal levels differ (a short-delay cell sampling
early in the decay sits at volts; a long-delay cell sampling late sits at millivolts), because
"worst outlier in mV" conflates *how noisy* a cell is with *how big its signal happens to be*.
Comparing cells/pulse-widths/bands against each other — the operator's stated goal — needs the
outlier expressed relative to that cell's own signal level, not an absolute figure.

New 5th metric, **Max %Δ from mean**: the same worst-single-frame-outlier numerator as "Max |Δ from
mean|", but divided by the window's own mean and expressed as a percentage instead of read off in
mV. Verified with a synthetic pair mirroring the bench scenario — a ~4.7 V cell and a ~0.05 V cell,
both given the same ~1% relative noise: absolute Max|Δ| reads 39.0 mV vs 0.39 mV (unusable for
comparison), Max %Δ reads 0.83% vs 0.78% (directly comparable, as intended).

`_STD_METRICS` gains the new entry; new parallel `_STD_METRIC_UNITS` tuple (`'mV'`×4, `'%'`) drives
the table's label suffix and — since Absolute mode's lo/hi spinboxes are shared across every metric
— their `setSuffix()` too, so a percent metric read against stale mV-labelled thresholds (or vice
versa) can't happen silently. Guards `abs(mean) < 1e-9` (a stalled/dead channel) to avoid a
divide-by-zero rather than assuming a real signal channel never reads exactly 0 µV. Rank/Absolute
colouring, smoothing, and the settings/reset machinery from v1.37 apply to this metric exactly as
they do to the other four — no separate plumbing needed. (2026-08-02)

---

### src/pimd_delaycal.py — v1.37 — FIX Std dev table metric jitter; rank-based colouring added

Bench report on v1.36's metric selector: watching the live Std dev table with Range P-P selected,
a 150 µs-pulse/100 µs-delay cell's reading bounced between 0.08 and 0.4 mV, and a 100 µs-pulse/8 µs-
delay cell (same target, a spanner) bounced between 1.10 and 3.0 mV — a 3–5× swing *within the same
cell*, with the operator noting "max delta from mean is correct" by contrast. Re-read
`_update_thermal_tables()` end to end first: no bug — the window genuinely is recomputed fresh
every redraw tick from the last `Samples N` frames of `_thermal_buf`, exactly as designed. Two
separate, real problems, not one:

**The metric itself is inherently jittery.** Range P-P and Max |Δ from mean| are order statistics —
driven by one or two extreme samples in the window, not an average over all of them. Each redraw
tick the window slides forward a few frames; if a single spike sample enters or leaves, the value
can swing hard purely from that one sample. Std dev averages over the whole window so one outlier
barely moves it, which is why it read as "correct" by comparison — nothing was wrong with the
Range/Max|Δ| arithmetic, just their statistical volatility as an instantaneous live reading.

**The colour can't discriminate what the operator is actually comparing.** The two example cells
sit on wildly different absolute scales (~10× apart) — itself real, useful signal about which
pulse-widths/delays carry more SNR, which is exactly the "which cells carry less info, to prune"
question the operator is using this table to answer. But with one *global* lo/hi mV threshold
colouring every cell, everything in the quiet band clips to one end of the gradient and everything
in the loud band clips to the other — zero colour variation *within* a band, which is precisely the
comparison needed.

**Fix, two parts, confirmed with the operator (Rank as the new default over keeping Absolute-only):**

1. **Smoothing.** New per-channel `self._metric_smooth_buf: dict[int, deque]` (flat channel →
   recent *computed* mV readings, not raw samples) and `_smoothed_metric_mv()`: a simple moving
   average over the last `Smoothing` draws (new spinbox, range 1–50, default 5; 1 = raw/off) before
   display. Applied after `_metric_value_mv()` in both `_update_thermal_tables()` branches. Cleared
   at every existing `_thermal_buf.clear()` call site (`_start_thermal`, `_start_auto`,
   `_auto_run_soak`, `_auto_settle_done`, `_manual_push_profile`) plus on a metric change, so
   smoothing never blends pre/post-reconfigure data or two different metrics together.

2. **Rank colouring.** New `cb_std_color_mode` combo (`'Rank'` / `'Absolute'`, **default Rank**)
   next to the existing lo/hi spinboxes, which now disable themselves in Rank mode (inert there).
   `_value_gradient_color()` split into a low-level `_gradient_color_from_fraction(t)` (the
   existing stop-interpolation, unchanged) plus a thin absolute-mode wrapper, so Rank mode can
   share the same gradient stops with `t` = a cell's percentile among all currently-visible,
   fully-settled cells for the selected metric, instead of `t` = position between lo/hi. This
   required restructuring `_update_thermal_tables()`'s Manual Nudge path into two passes — compute
   every settled cell's (smoothed) value first, since Rank mode needs the whole table's values
   before any single cell's colour can be decided, then paint. Verified offline: two synthetic
   cells at the bench's ~10× scale gap get three genuinely distinct colours in Rank mode, while
   Absolute mode with the same lo/hi reproduces the reported clipping exactly — confirming both the
   diagnosis and the fix.

**Scope unchanged from v1.36**: Auto Nudge's own pass/fail evaluation (`_auto_evaluate_parallel` /
`_channel` / `_initial`, `_capture_measurement`) still calls `_stdev()` directly at its three
existing sites, untouched by any of this — reconfirmed by grep after the change. New settings keys
`std_color_mode` and `metric_smooth`, same safe-default/out-of-range-guard pattern as `std_metric`.
(2026-08-02)

---

### src/pimd_delaycal.py — v1.36 — Std dev table metric selector: Range P-P, Max |Δ|, Drift ½ vs ½

The Std dev table only ever computed one reduction over its rolling window (`_stdev(vals)`), but
the operator wanted to look at other things through the same live window without a second table —
concretely, peak-to-peak voltage range ("a value of 10 would mean there was 10 mV between the
lowest low and highest high in that sample period"), plus whatever else was worth suggesting. The
window-buffering/gating machinery (`_thermal_buf`, the "filling" guard, the sample-count spinbox)
was already generic; only the reduction itself was hardcoded.

New `QComboBox` (`cb_std_metric`) next to the table's label, populated from a new `_STD_METRICS`
tuple: **Std dev** (unchanged default), **Range P-P** (the requested metric — `max(vals) -
min(vals)`), **Max |Δ from mean|** (worst single-frame outlier, a one-sided view range can miss),
and **Drift ½ vs ½** (first-half vs second-half window mean — catches a channel steadily walking in
one direction, which a symmetric spread metric like std dev or range reports as noise rather than
trend). All four are cheap reductions over the same already-sliced `vals` list. New
`_metric_value_mv()` dispatches on the combo index; both call sites in `_update_thermal_tables()`
(the plain numeric path and Manual Nudge's gradient-coloured path) now go through it instead of
calling `_stdev()` directly. `_stddev_gradient_color()` / `_STDDEV_GRADIENT` renamed
`_value_gradient_color()` / `_VALUE_GRADIENT` since they now colour whichever metric is selected,
not std dev specifically — same lo/hi spinboxes and gradient, just re-labelled ("Std colour lo/hi:"
→ "Colour lo/hi:").

**Scope decision: display only.** Auto Nudge's own pass/fail evaluation (`_auto_evaluate_parallel`
/ `_channel` / `_initial`, `_capture_measurement`) still calls `_stdev()` directly at its three
existing call sites, completely untouched — confirmed by grep after the change. Changing what Auto
Nudge's automatic search optimises for is a materially bigger, unrequested behaviour change; this
feature is about what the operator *looks at* live, not what Auto Nudge hunts for.

**Relabelled** "Std dev N:" → "Samples N:" (variable name `sp_thermal_n` unchanged — it's still the
one rolling-window size shared by Thermal, Auto Nudge and Manual Nudge; only the UI label was
std-dev-specific). New settings key `std_metric` (combo index) persists the selection, defaulting to
0 (Std dev) when absent so existing settings files keep today's behaviour unchanged; an out-of-range
stored index is ignored rather than crashing `_load_settings()`. (2026-08-02)

---

### src/pimd_delaycal.py — v1.35 — Manual Nudge guard/status messages now say what to do, not just what not to

v1.34's mutual-exclusion guard produced "Turn off Manual Nudge before starting Auto Nudge." when
Auto was clicked while Manual Nudge was checked — accurate, but the very next question the operator
asked was "so how do I start Manual Nudge, then?", because Manual Nudge has no button of its own: it
is a checkbox that arms the −/+ overlay and colouring, and the existing **THERMAL** button (a
different section entirely) is what actually starts the live stream it reacts to. Nothing wrong with
the underlying mutual-exclusion logic from v1.34; the messaging around it just didn't say that.

Two messages now name the actual next step. `_start_auto()`'s refusal is now "Manual Nudge is on --
press THERMAL to stream live data and use each cell's −/+ buttons, or uncheck Manual Nudge to use
Auto Nudge instead." And `_on_manual_nudge_toggled()` now proactively shows "Manual Nudge on -- press
THERMAL to start streaming, then use each cell's −/+ buttons." the moment the checkbox is ticked (only
when THERMAL isn't already running), rather than waiting for the operator to hit the wrong button
first and read about it from a refusal. (2026-08-02)

---

### src/pimd_delaycal.py — v1.34 — FIX Auto Nudge running was painting over Manual Nudge; modes now exclusive

v1.33's screenshot-driven bug report ("colours only update every 14 or so cycles and restart at
zero... that timeout still stopped everything") turned out not to be a Manual Nudge bug at all — the
screenshot showed **Auto Nudge actually running** (green "Auto" button, "Stop Auto" enabled,
"Parallel — iter 7/20 ... soaking 5s", Activity Log lines in Auto Nudge's own `nudge #N` format)
with the Manual Nudge checkbox *also* ticked alongside it. `_update_thermal_tables()`'s
`manual_live = cb_manual_nudge.isChecked() and not self._auto_running` guard was working exactly as
coded: because Auto Nudge was running, Manual Nudge's continuous gradient never engaged at all, and
every cell was showing Auto Nudge's own existing state-mirror colouring instead — which by Auto
Nudge's own long-standing design resets every soak cycle (`sp_auto_soak_s`, 5 s here) and stops when
`sp_auto_max_iter` is reached (20 here). Both symptoms were 100% pre-existing Auto Nudge behaviour,
unrelated to anything Manual Nudge does; the actual bug was that nothing stopped the two features
from running concurrently with no indication of which one was driving what was on screen.

Fixed by making the two modes **mutually exclusive**, confirmed with the operator over the
alternative (letting them coexist and stripping Auto Nudge's own iteration cap, which would have
blurred two different interaction models together and touched Auto Nudge's working design rather
than Manual Nudge's). `_start_auto()` now refuses to start ("Turn off Manual Nudge before starting
Auto Nudge.") while `cb_manual_nudge` is checked. `_on_manual_nudge_toggled()` now stops Auto Nudge
first (logged) if it happens to be running when Manual Nudge is checked, and disables/re-enables
`pb_auto` in step with the checkbox so the button itself reflects which mode is available.
`cb_manual_nudge` is disabled for the duration of an Auto Nudge run (`_start_auto()`) and re-enabled
wherever Auto Nudge's own cleanup already re-enables its other buttons (`_stop_auto()`,
`_auto_finish()`). With the two modes now unable to overlap, Manual Nudge's v1.33 rolling-window
gradient (already verified correct in isolation) is what will actually paint the tables whenever
Manual Nudge is checked. (2026-08-02)

---

### src/pimd_delaycal.py — v1.33 — Manual Nudge: rolling-window std gate, continuous gradient colour, no THERMAL timeout

Three operator-reported problems after using v1.31/v1.32's Manual Nudge on the bench, all in
`_update_thermal_tables()` / the Std dev colouring path.

**"Every colour change I see them all at once and they all start at 0.0."** The std column was
colouring off `len(recent) >= 2` — as few as two buffered frames — instead of a genuinely full
rolling window, so right after any reconfigure (a nudge push, a THERMAL restart) every channel's
buffer is simultaneously near-empty and reads a spuriously tiny (often near-zero) std for its first
fraction of a second, colouring every cell "quiet" together before real readings arrive. Fixed by
gating Manual Nudge's own colouring on `len(recent) >= n` (the full configured `Std dev N`) — the
same "filling" guard `pimd_classviz.py`'s `_stddev_window()`/`_window_frames()` already uses for
its rolling reductions. Below the full window a cell now shows a neutral grey `…` (reusing the
existing `_COL_NR` constant) rather than a numeric `0.00`, matching classviz's own refusal to
render an unsettled window as if it were a real (quiet) reading. The "at once" part is otherwise
inherent to the architecture and not new here: `D`/`Q`/`G` redefines the whole profile, so a
reconfigure restarts the shared frame stream for every channel simultaneously, same as Auto Nudge's
existing soak-and-restart cycle.

**"No purple entries, just the colour representing level" + "greater range, like heatmap."** Turned
out to be two sides of one bug. `_apply_manual_nudge_overlay()`'s per-cell widget (v1.31) is a plain
`QWidget`/`QLabel` with no explicit background, i.e. transparent — confirmed by grabbing the table's
pixmap in an offscreen test and sampling pixels under the overlay: a purple `_COL_AUTO_DRIFTED`
background painted on a delay-table cell by an earlier Auto Nudge run bled straight through the
nudge buttons untouched. Manual Nudge's colouring also only ever touched `tbl_thermal_std`, so
`self.table`'s cells kept whatever state colour Auto Nudge (or a sweep) had last left there. Fixed
by having Manual Nudge explicitly repaint **both** `self.table` and `tbl_thermal_std` for every cell
on every redraw tick (never leaving a background unset), and by replacing the old 3-bucket
green/yellow/red scheme (`_stddev_heatmap_color`, reusing the Auto Nudge state palette including the
lavender "drifted" colour) with a new continuous `_stddev_gradient_color()` — a 4-stop green →
yellow → orange → red ramp interpolated between the lo/hi mV spinboxes and clamped at both ends.
This is deliberately its own palette, decoupled from `_COL_DONE`/`_COL_AUTO_FLAGGED`/etc.: Manual
Nudge shows a continuous *level*, not one of Auto Nudge's discrete *states*, so none of that
palette's colours — purple included — can appear in it, and the wider graduated range gives far
more visual resolution across the lo–hi band than three flat buckets did.

**"No max iterations, manual continues until stopped by user."** THERMAL's own fixed run length
(`sp_thermal_secs`, default 240 s) was still ticking down underneath Manual Nudge and auto-stopping
the whole live view exactly like an ordinary Thermal run — silently ending a nudge-and-watch session
mid-work. `_thermal_tick()` now checks `cb_manual_nudge` first: while it's checked, the countdown is
skipped entirely (a new `_thermal_manual_elapsed` counter tracks and displays elapsed seconds
instead) and THERMAL runs indefinitely until the operator presses Stop; unchecking it resumes the
ordinary countdown from wherever `_thermal_remaining` was left, untouched by the manual interval. (2026-08-02)

---

### src/pimd_delaycal.py — v1.32 — FIX v1.31's no-scroll sizing overshot the screen; compact rows + screen clamp

v1.31's fix for internal table scrollbars worked exactly as designed — and overshot: fitting
three full tables without a scrollbar just moved the excess height to the *window*, which grew
past the operator's actual screen. Two compounding causes. First, `_table_min_height()`'s row
budget (34 px, bumped from the original 30 to fit the new Manual Nudge overlay) was only ever a
*minimum*, not an enforced size — `self.table` had no explicit row height, so once the −/+
overlay's `QPushButton`s were installed, Qt sized each row to the button's own sizeHint (a stock
button's internal padding alone exceeds 34 px), which is taller than the budget assumed and stacks
across every row. Second, the default window height was raised 1200 → 1500 alongside that budget,
with no relationship to the screen actually in front of the operator.

**Rows are now genuinely fixed, not just budgeted.** New `_compact_table()` helper applies an 8 pt
font and `verticalHeader().setSectionResizeMode(Fixed)` at `TABLE_ROW_PX` (20 px, down from the
34 px budget) to all three live tables at construction — Qt can no longer grow a row to fit a cell
widget's sizeHint, so the Manual Nudge buttons are shrunk to fit inside 20 px instead (`setFixedSize`
+ a stylesheet stripping the stock padding/margin that a font-size change alone doesn't remove) and
`TABLE_HEADER_PX` drops to match. `TABLE_MIN_H_PX` floor drops 120 → 64 accordingly. The Activity
Log's minimum height also drops 160 → 90 px — another fixed minimum that was stacking on top of the
three tables' own. For the 3-band × 9-threshold default config this drops the window's actual
`minimumSizeHint` from needing roughly 950+ px to **646 px**, comfortably under any normal laptop
screen's usable height.

**Window geometry is now screen-clamped, not just guessed.** New `_clamp_to_screen()` reads
`QApplication.primaryScreen().availableGeometry()` and caps both the fallback default (reverted
1500 → 1000, since rows no longer need the extra room) and whatever `window_h`/`window_w` a
settings file supplies — covering not only first run but a size saved from a larger or different
monitor than the one currently in front of the operator, which no fixed default could have
anticipated. (2026-08-01)

---

### src/pimd_delaycal.py — v1.31 — Manual Nudge mode: std-dev heatmap colouring + per-cell −/+ nudge buttons

Auto Nudge already drives the calibrated delay table's cells toward a std-dev threshold
automatically; there was no operator-driven equivalent — no way to nudge one cell by hand
and watch the effect on live std dev without editing config files and re-running a sweep.

**Std dev table now colours by value.** `tbl_thermal_std` previously only ever showed plain
numbers — the only colouring it ever got was Auto Nudge mirroring the calibration table's
pass/fail state onto it while Auto Nudge is running. `_update_thermal_tables()` now also
colours each cell green/yellow/red against two new spinboxes (`sp_stddev_lo_mv`,
`sp_stddev_hi_mv`) via a new `_stddev_heatmap_color()` helper, whenever the new "Manual
Nudge" checkbox (`cb_manual_nudge`) is on and Auto Nudge isn't (so Auto Nudge's own
pass/fail mirror still wins if both are touched in one session). This is deliberately the
same 3-bucket scheme `pimd_classviz.py`'s Stats tab already uses for its own Std column
(`sp_std_lower`/`sp_std_upper` there) — and its three colours are already delaycal's own
`_COL_DONE` / `_COL_AUTO_QUEUED` / `_COL_AUTO_FLAGGED` constants, so the palette is shared
across both tools with nothing new invented. classviz's other Std Dev view — the pyqtgraph
gradient heatmap with a draggable colorbar region acting as a range "slider" — was not
pulled in: delaycal has zero pyqtgraph coupling today, and adding it as a dependency for one
table wasn't worth it next to the two-spinbox scheme classviz's own plain-table equivalent
already uses.

**Delay table cells get a −/+ overlay.** `self.table`'s cells are (and remain) plain
`QTableWidgetItem`s — text is still the only store of a cell's delay, read by
`_build_profile()` and written by `_fill_cell()` / `_auto_finish()` exactly as before; none
of that changed. What's new is a removable visual overlay: while `cb_manual_nudge` is
checked, `_apply_manual_nudge_overlay()` installs a small `−`/label/`+` composite widget on
every cell via `setCellWidget()`, purely occluding the item (its background colour is
untouched underneath). Unchecking calls `_clear_manual_nudge_overlay()` and reveals the
plain item again. `_rebuild_table()`, `_import_profile()`, `_finish()` and
`stop_calibration()` all refresh the overlay if it's active, so a fresh sweep or import
never leaves stale button labels; the checkbox itself is disabled for the duration of a
sweep to avoid needing to refresh it mid-fill.

**Clicking − or + on a cell** (`_on_manual_nudge_clicked`) reads the cell's current delay,
adds/subtracts the new `sp_manual_nudge_ns` step (8–9600 ns, same shape as
`sp_auto_nudge_ns` but a separate control — Auto and Manual Nudge are independent
workflows), snaps to the 8 ns grid via the existing `_snap_8ns()`, and writes the result
back into the item and the overlay label. If THERMAL is currently streaming,
`_manual_push_profile()` pushes the change to the firmware immediately — the same
`E` / `D` / `Q<n>` / `G` reconfigure sequence `_auto_run_soak()` already uses for every Auto
Nudge iteration — and reuses the existing `_auto_settling` 1 s settle gate / buffer clear so
the reconfigure transient doesn't contaminate the next std-dev window. Without THERMAL
running, the click only updates the display; the change is picked up the next time THERMAL
starts or a profile is exported, same as any other cell edit today.

**No-scroll table sizing**, raised separately mid-session: the calibration delay table had no
minimum-height sizing, unlike the thermal mean/std tables which already compute one so every
row is visible without an internal scrollbar. Pulled that formula out into a shared
`_table_min_height()` helper (constants `TABLE_HEADER_PX`/`TABLE_ROW_PX`/`TABLE_BORDER_PX`/
`TABLE_MIN_H_PX`, row height bumped 30 → 34 px to fit the nudge overlay comfortably) and
applied it to all three tables — delay, mean, and std dev — so none of them scroll
internally. Default window height (first-run / missing-settings-file fallback only; existing
saved geometry is untouched) raised 1440×1200 → 1440×1500 to give the taller stack of three
tables room without the operator needing to resize manually.

New settings persisted: `manual_nudge_ns`, `stddev_lo_mv`, `stddev_hi_mv`. The Manual Nudge
checkbox's own on/off state is deliberately **not** persisted — it defaults unchecked on
every launch so the button overlay never appears unexpectedly on startup. (2026-08-01)

---

### findings — sub-0.5 V thresholds plateau at a ~16-18 mV measurement floor, not a bug

Reported from a live `pimd_delaycal` v1.42 session (fw v4.26) streaming a hand-edited 11-threshold
ladder (`test v4a-distributted`, thresholds 4.9 → 0.005 V) — every row's Latest-mean (mV) column
decreased correctly down to a few mV, then rose back to a steady ~16-18 mV across the last 3-4
columns (0.3/0.1/0.01/0.005 V), the same magnitude in every band regardless of that column's very
different delay (20 µs to 250 µs). Flagged as "should only ever be decreasing."

**Confirmed real and stable, not a code defect.** Live board checks (`V` identify, then a
standalone script replaying `pimd_delaycal`'s own `D`/`Q5`/`G` sequence and W-record parsing
against the same profile):

- Firmware is v4.26 — has the v4.25 outlier-gate fix and the v4.26 CC-write fix; v4.27 only adds
  an unrelated diagnostic counter, so this is not a stale-firmware artefact.
- A 150 s / 616-frame capture shows the plateau is **flat from the first frame** (t=5 s) to the
  last (t=149 s), ruling out both a still-diluting rolling average and the documented
  stream-start transient (§17.13) — this is a settled steady state from the moment streaming
  starts, not a transient.
- A fine delay sweep on the `25000 Hz / 4.0 µs` and `25000 Hz / 6.0 µs` bands between their 0.5 V
  and 0.3 V delays (15.2→18.7 µs and 15.1→18.4 µs) shows a smooth, monotonic rise from ~6 mV to
  ~17 mV — no discontinuity, no glitch, just the true decaying signal crossing below the RX
  chain's floor and the rolling mean thereafter reading that floor instead of the target.

**Reading is: the decaying pulse has fallen below the acquisition chain's noise/offset floor by
this point, and the "mean" is now measuring the floor, not the signal.** The floor sits at
~16-17 mV for most bands, with a mild per-band tilt (up to ~18.2 mV on the fastest/25 kHz bands,
tapering toward ~16.3 mV on the slowest). Onset delay (where a band's decay crosses the floor)
varies by band, which is why it shows up in different columns per row — but the locked operating
profile `cal_63_air_bat_v3` (§10) never sweeps below 0.5 V, so this floor was never characterized
before; the sub-0.5 V columns of any hand-edited ladder are past the edge of previously-measured
territory. Not a firmware or delaycal defect — no code changed. Open question, not pursued here:
whether the ~1-2 mV per-band tilt above the common floor is genuine RX floor variation by drive
frequency or coupling from the higher-frequency PWM bands — would need a scope to settle.
(2026-08-03)

---

### findings — sub-67.2 µs bands' tail-column plateau tracks coupling strength, corroborates §14.6

Follow-up to the finding immediately above. Board updated to fw v4.27 (was v4.26 — no behaviour
difference relevant here, v4.27 only adds a diagnostic emit-block counter). Same
`test v4a-distributted` profile, live-captured with a real target (spanner + aluminium plate)
first at 60 mm above the coil, then again with the target close to/resting on the coil, using
the same replay-harness approach as the prior entry.

At 60 mm, every band **under 67.2 µs pulse width** (4, 6, 9, 13.44, 20, 30, 45 µs) showed its
0.3 V-and-below columns collapsed to essentially the same ~17-18 mV reading as the no-target
floor (delta mostly < 1-3 mV) — flagged as still a problem, since a large ferrous+aluminium
target should read higher than free air.

**Resolved by proximity, not by code.** With the target moved close, those same cells rose
clearly above both the free-air floor and the 60 mm reading — e.g. `15,625 Hz / 20.0 µs` at
0.3 V: floor 14.92 mV, 60 mm 17.01 mV, close 25.92 mV (+11.0 mV over floor, +8.9 mV over the
60 mm run); `10,000 Hz / 30.0 µs` at 0.3 V: 16.28 → 18.31 → 27.00 mV. Every sub-67.2 µs band
showed the same rising pattern down through 0.1/0.01/0.005 V — the plateau moves with coupling
strength, so it is real target signal that was simply too weak to clear the floor at 60 mm on
these shorter pulses, not a hardware ceiling.

**Corroborates the independently-recorded §14 item 6** ("possible TX coil-current plateau above
~67 µs" — the 67.2→100 µs band-to-band increment being the smallest on the ladder, consistent
with coil current flattening above that pulse width). The boundary observed here matches that
open item's boundary exactly: bands below it likely drive less coil current/field energy, so
they couple more weakly and need the target closer (or the floor lower) to read above it. This
is corroborating field evidence, not the scope measurement §14.6 itself still calls for — that
follow-up (coil current vs pulse width) remains open.

**Practical consequence for `test v4a-distributted.json` / any hand-edited ladder:** the
sub-0.3 V thresholds on bands under 67.2 µs are only informative at closer range/stronger
targets than 60 mm — at 60 mm they read as floor, not as "no signal reachable at any range."
No firmware or delaycal code changed. (2026-08-03)

---

### src/pimd_delaycal.py — v1.43 — FIX Compare-over-time "Mean level": was a ratio vs baseline, not an absolute delta

Found live: a brass block and, separately, a steel spanner held close to the coil for a full
minute each lit up the *same* narrow set of 6 cells (the 67.2/100/150 µs bands' 4.4 V/3.7 V
columns) under Mean-level Compare-over-time, regardless of which target material was used —
while the exact same targets had produced tens-of-mV changes across *every* band's high-voltage
columns in the raw Latest-mean table moments earlier. Two different materials producing an
identical, oddly narrow pattern was the tell that this was arithmetic, not physics.

**Root cause:** `_compare_value_ratio()` (the single function behind every Compare-over-time
metric) always returned `abs((current - baseline) / baseline)` — a change *relative to the
cell's own baseline level*. That's a reasonable design for the other four selectable metrics
(Std dev, Range P-P, Max |Δ from mean|, Drift ½ vs ½), which are spread statistics where "the
noise doubled" is meaningful independent of the cell's absolute level (deliberate as of v1.40).
But "Mean level" (added v1.42) is the raw signal level itself, not a spread — its own docstring
already said it should track absolute level, but the implementation was never special-cased and
inherited the divide-by-baseline behaviour anyway. Result: a cell with a large baseline (the
thousands-of-mV, short-delay columns on every band) could shift by 50-113 mV and still divide
down to a ratio of 0.01-0.05 (reads as quiet); a cell whose baseline happened to already be a
few mV (further down the decay on the longer-pulse bands) could shift by only 4-17 mV and divide
into a ratio past 1.0 (reads as red). Which cells turned red was tracking each cell's baseline
size, not the target's actual effect on it — confirmed offline by replaying the fix's arithmetic
against the spanner+aluminium-at-60mm capture from the two entries above: the cells the bug hid
(3-5 % ratio) carried the largest real absolute shifts (up to 113 mV); the cells it flagged red
carried the smallest (4-17 mV).

**Fix:** `_compare_value_ratio()` now special-cases metric index 5 (Mean level) to return
`abs(smoothed_mv - base)` in mV, guarded only by `base is not None` — the ratio path's
near-zero-baseline guard doesn't apply to an absolute difference, where a near-zero baseline is
a legitimate reading. `_refresh_std_metric_label()` updated to match: Mean level's Compare-over-
time label and lo/hi spinbox suffix now read `mV`, not the blanket unitless-ratio label used by
the other four metrics. The other four metrics' ratio behaviour is untouched — that was a
deliberate, already-shipped design choice and not part of this defect.

**Not yet done:** the Colour lo/hi spinboxes for the Std dev table (currently tuned around
0.50/1.00 for a ratio scale) will need re-tuning to an mV-appropriate range now that Mean level
reports absolute mV in compare mode — left for the operator, not changed here. (2026-08-03)

---

### src/pimd_delaycal.py — v1.44 — "Mean level" Compare-over-time is now signed, with a diverging colour scale

Follow-up to v1.43 above. With that fix live, a brass block and a steel spanner held close to
the coil both produced a broad, sensible response across every band's high-voltage columns —
confirming the ratio bug was the whole story for *that* symptom — but a new pattern showed up:
a diagonal band of near-zero Mean-level Δ cells running from the bottom-left of the grid toward
the top-middle, its column position marching systematically with pulse width. Flagged as a
possible new problem; investigated before touching any code.

**Diagnosis, confirmed against this session's own captured data before changing anything.**
v1.43 made Mean level's compare value `abs(current_mV - baseline_mV)`. `abs()` is mathematically
forced to read nearly zero wherever the *signed* difference crosses zero, regardless of how
large the true response is on either side. Recomputing the *signed* delta (not abs) from an
already-recorded spanner+aluminium close-range capture confirmed exactly that: every band shows
a clean negative-to-positive crossing (e.g. `25,000Hz/9.0us` crosses between 1.5 V and 0.5 V;
`3,125Hz/100.0us` crosses between 4.8 V and 4.4 V), and the crossing column marches from the
low-voltage/short-pulse corner to the high-voltage/long-pulse corner — precisely the diagonal
shape reported. This matches the project's own documented two-basis/crossing-ladder behaviour
for ferrous/conductive targets (an early-time and late-time response of opposite sign), so the
diagonal is a real, expected sign flip that `abs()` was rendering as a false "no change" cell,
not lost signal and not a new hardware defect.

**Fix:** `_compare_value_ratio()`'s Mean-level branch now returns the signed difference
(`smoothed_mv - base`) instead of `abs(smoothed_mv - base)`. `_update_thermal_tables()`'s
Manual-Nudge live-colouring path special-cases this signed metric: Rank mode now ranks by
magnitude (`abs()`) rather than the raw signed value, so crossing cells sort to the quiet end
instead of landing in the middle of the order; the cell colour comes from a new diverging scale
(`_diverging_color_from_fraction` / `_diverging_value_color`, near-white at zero fading to blue
for a negative-going response and to the existing "noisy" red for a positive-going one) instead
of the quiet-green-to-noisy-red gradient the other five metrics use; and the displayed number is
signed (`+12.34` / `-45.67`) in both the Manual-Nudge live table and the plain (non-Manual-Nudge)
compare display. The other five metrics are untouched — this only changes metric index 5.

**Not yet done:** the Colour lo/hi spinboxes still drive the diverging scale's saturation
distance from zero (same spinboxes v1.43 flagged as needing mV re-tuning) — verify the diverging
colours read sensibly against real target data once re-tuned; not confirmed live yet, only
against the offline signed-delta replay. (2026-08-03)

---

### findings — reading the v1.44 signed Mean-level Δ heatmap on a live brass-close capture

Operator's own read of a brass-close-range capture (v1.44, Δt=132 s since baseline), checked
point by point rather than taken on trust:

- **"Top-left negative block moves with thermal/battery effects."** Partly right, but likely
  secondary, not primary. The −14 to −38 mV block at 4.9-3.7 V appeared at only 132 s since
  baseline; an earlier clean spanner+aluminium test with no drift confound (target introduced
  immediately after baseline capture) showed comparable-or-larger negative deltas at the same
  columns (−46 to −220 mV) from the target alone, and session drift rates measured elsewhere
  this session would only account for ~8-15 mV over a 132 s window. So this block is most
  likely dominated by the target's own real early-time (negative-going) response, with drift
  contributing a real but secondary skew on top.
- **"Diagonal blanks are averaging on both sides of zero."** Right in spirit, one precision
  correction: it isn't the rolling *time* average within a cell mixing positive and negative
  samples (each cell's rolling average is a steady value at its own fixed delay). It's that the
  signed difference (current level minus baseline) genuinely passes through zero **across
  cells** — the target's response is negative early in the decay and positive later, so there's
  a real delay where it crosses, and whichever column lands closest reads a genuinely-near-zero,
  correctly-measured difference, not a noise artefact. Confirmed against the raw numbers:
  `25,000Hz/6.0us` @ 2.4V reads +0.00, sitting between −8.21 (3.7V) and +0.09 (1.5V).
- **"Cells right of the crossing are stable until a target arrives; cells left of it need
  constant adjustment."** Consistent with the calibration-delay table's own colouring pattern
  seen throughout this session (nudging concentrated on the shorter-delay/higher-threshold
  cells) — a threshold anchored on the steep part of the decay is far more sensitive to a small
  timing/level shift than one anchored on the flat floor.
- **"Cells reading 2-4 mV instead of 16-18 mV are driven lower by oscillation/op-amp behaviour,
  settling to a ~16 mV bias with no drive."** The pattern is real, confirmed numerically in this
  capture's own raw Latest-mean table — every row has a genuine local *minimum* below its
  eventual floor, not a monotonic approach to it (e.g. `25,000Hz/9.0us`: 10, 3, 4 mV at
  2.4/1.5/0.5V before settling at 16-17 mV further out; `6,250Hz/45.0us`: 4 mV at 3.7V before
  settling at 16-17 mV). An op-amp/ringing overshoot-then-settle is a plausible, common analogue
  mechanism that would produce this shape — but per CLAUDE.md this can't be confirmed or ruled
  out from logs alone; it matches the data shape without being provable from here. A scope on
  the preamp output around that part of the decay is the way to actually confirm the mechanism.
  (2026-08-03)

---

### profile — test v4a-distributted.json — geometric delay ladder between bench-verified sample points

Not previously recorded — the three existing `CHANGELOG.md` mentions of this file (the two
entries above and the delaycal v1.43 entry) all reference it but none describe how it was built.

For every band, the first and last `delays_us` are kept exactly as in `test v4h` — these are the
earliest and latest sample points actually reached and validated on the bench via the
instrumentation during hand calibration, not arbitrary picks. The 9 interior delays per band are
a geometric progression between them (ratio `r = (last/first)^(1/10)`, i.e. `delay[i] =
first * r^i`), giving equal log-spaced coverage of the whole bench-verified delay range per band,
rather than the ad hoc/linear spacing `test v4h` had. Thresholds/`threshold_v` are unchanged from
`test v4h`, pending the voltages this ladder actually reaches on the bench. (2026-08-03)

---

### src/pimd_rawlog.py — v1.00 — new standalone raw MCU logger, independent of pimd_delaycal.py

Motivation: before starting training against `cal_110_full_range_v4.json` (10 bands x 11
thresholds = 110 cells, geometric ladder out to 200 µs), the operator wants to analyse raw data
to find which rows/columns can be dropped without losing information — a job that needs a
ground-truth raw capture tool decoupled from `pimd_delaycal.py`'s own display/processing code,
after this session's ratio-bug (v1.43) and sign-crossing (v1.44) fixes both turned out to be
display-layer defects rather than hardware issues. A dumb, unopinionated logger removes that
whole class of risk from the data going into the reduction analysis.

New PyQt6 tool, same `QSerialPort`/115200-8N1 pattern as `pimd_delaycal.py`, same `E`/`D`/`Q5`/`G`
wire sequence (§9/§11 unchanged, no new protocol behaviour) — but deliberately minimal: no
tables, no metrics, no derived values. Load Profile parses a profile JSON (same shape
`pimd_delaycal.py` exports/imports); Start sends `E` then the built `D...` command, waits for
`D OK`, then `Q5`/`G`; every line read from serial is appended verbatim to a timestamped session
file in `data/sessions/` (`rawlog_<timestamp>.txt`) as `<iso-timestamp> RAW <line>`, unmodified.
A free-text field + "Log Note" button (Enter also submits) writes `<iso-timestamp> NOTE <text>`
into the same file, interleaved in arrival order, so a later analysis pass can find exactly
which raw lines fall inside a given target placement. Stop sends `E` and closes the file.

**Verified:** UI construction and `_build_d_command()`'s output format checked offline (matches
`pimd_delaycal.py`'s own D-command shape). **Not yet verified live** — the board's serial port
was held by an active `pimd_delaycal.py` session at the time (`cal_110_full_range_v4.json`
brass-block testing), so the connect/stream/log path itself needs a live smoke test next time
the port is free. (2026-08-03)

---

### src/pimd_rawlog.py — v1.10 — target/distance picker, Place/Remove markers, settle + warm-up indicators, Resume Session

Motivation: `pimd_rawlog.py` v1.00 could log a raw stream but gave the operator nothing to work
with while capturing the `cal_110_full_range_v4.json` cell-reduction dataset (per
`HANDOFF_cell_reduction.md`) — no structured way to record what was placed and how far from the
coil, no feedback on when a segment had enough stable data to move on, no sense of whether the
rig itself was warmed up yet, and no way to pick a multi-sitting capture session back up.

Target/distance controls: a `Target:` combo populated from `src/data/targets/targets_v4.csv`
(13 registered targets; comment lines are `#`-prefixed but some are CSV-quoted because they
contain commas — `_load_targets()` strips both forms) plus a `Distance from coil (mm):` spinbox
(0–500, step 5). Note: `targets_v4.csv`'s registry fields don't include `threshold_v` and neither
does anything else in this tool — per the operator, delays are no longer voltage-aligned, so that
profile field is vestigial and deliberately never read here; columns are identified purely by
band index + position in `delays_us`.

Place/Remove markers: `Place Target` / `Remove Target` buttons write self-contained `MARK` lines
— `MARK place target_id=... short_name="..." shape_class=... material_class=... mass_g=...
dim_a_mm=... dim_b_mm=... dim_c_mm=... distance_mm=...` / `MARK remove target_id=...` — embedding
the registry's key fields inline so the raw log alone identifies what was in the field without
needing the CSV alongside it. Buttons enforce a strict place→remove→place cycle and each
transition resets the settle window (below) so a segment's reading is never contaminated by the
previous segment's tail.

Settle indicator ("enough data, move on"): own metric, not `pimd_classviz.py`'s code — a rolling
per-channel std-dev over the last N `W`-line frames (window adjustable, default 20), reduced to a
single mean-across-channels mV number, compared against an adjustable threshold (default 1.0 mV).
Grey "Collecting N/M" while the window fills, amber "SETTLING σ=X.XX mV" above threshold, green
"READY σ=X.XX mV" at/below — serves air and target segments identically, since it's a statement
about local stability, not about what's in the field.

Warm-up indicator ("is the rig ready to trust"): cumulative *firmware-clock* streaming time
(summed `time_ms` deltas from `W` lines, not wall clock, so idle/stopped gaps don't silently
count), against an adjustable target (default 240 s, DESIGN's ~4 min SoC warm-up figure as a
starting point). Red "WARMING Ns/240s" below target, green "WARM ✓ (Ns)" at/above.

Resume Session: a "Resume Session" button opens a file picker over `data/sessions/`
(`rawlog_*.txt`); `_scan_session_file()` recovers the profile path from the file's own `META`
line (now `shlex`-quoted on write since several profile filenames in this repo contain spaces —
e.g. `test v4a.json` — an initial version of this without quoting silently truncated those paths
on resume), the cumulative streamed seconds, and whether the last `MARK place`/`remove` pair is
still open (to restore Place/Remove button state). Reopens the same log file in append mode (not
a new file) and re-runs the same `E`→`D...`→`D OK`→`Q5`→`G` sequence Start already uses, then
writes a `META resumed streamed_s=...` line.

**Verified:** offscreen PyQt smoke test (targets CSV parses to 13 rows; profile load reports
10×11=110 channels; synthetic `W`-line frames drive the settle indicator through
Collecting→READY and the warm-up indicator's elapsed-time math; a full place→remove cycle
produces correctly-tagged `MARK` lines with fields intact; `_scan_session_file()` round-trips
both a closed and a still-open placement, correct streamed-seconds accounting, and a
space-containing profile filename). Caught and fixed two real bugs this way: quoted-comment lines
in `targets_v4.csv` weren't being filtered (naive `#`-prefix check missed `"# ...",,,` rows,
corrupting the CSV header), and the original resume parser split `MARK` lines on whitespace,
truncating any quoted multi-word field (`short_name="brass gear"` → `brass`) — nearly every
target's `short_name` has a space, so this would have silently corrupted every resumed placement
label. Both fixed and re-verified. **Not yet verified live** — same as v1.00, needs a real bench
pass with the MCU connected; that's the operator's own pace, not something this session could do.
(2026-08-03)

---

### src/pimd_rawlog.py — v1.11 — Last-line wrap fix, warm-up target floor lowered to 1s

Two small usability fixes from first live UI feedback, before any bench testing: the "Last line"
label showed the raw serial line unwrapped, which on a 110-cell profile's `W` record (110+
comma-separated fields) blew out the window's horizontal size well past screen width —
`lbl_last_line.setWordWrap(True)` fixes it. Separately, the warm-up target spinbox's floor was
30 s; lowered to 1 s so the operator can effectively disable the warm-up gate (or test the
indicator itself) without it refusing sub-30 s values. (2026-08-03)

---

### src/pimd_rawlog.py — v1.12 — actual fix for the Last-line window-width blowout

v1.11's `setWordWrap(True)` didn't fix the reported problem — the operator confirmed the window
was still blowing out horizontally. Root cause: a Mode 2 `W` record for a 110-cell profile is a
single comma-separated line with no spaces anywhere (`W5,145.0,1000.0,1001.0,...`), and Qt's
`QLabel` word-wrap only breaks at whitespace — a run with no whitespace has no break points, so
wrap silently does nothing and the label still reports its full, enormous preferred width to the
layout. Fix: stop relying on wrap at all. A new `_truncate_for_display()` caps the "Last line"
label's text at `LAST_LINE_DISPLAY_MAX = 140` chars (`…(+N more chars)` suffix), which bounds the
window width unconditionally regardless of whether the underlying line has anything to break on.
The full untruncated line is still written to the session log file — this only affects the live
status display. Verified offscreen with a synthetic 110-channel line (778 raw chars → 174
displayed chars). (2026-08-03)

---

### src/pimd_rawlog.py — v1.13 — Acquire Target/Acquire Air, live raw-value grid

Two operator-requested changes to the cell-reduction capture workflow.

**Place/Remove Target renamed to Acquire Target/Acquire Air**, and the semantics changed to
match: there is no longer a place-then-remove pairing to enforce. Each button just stamps the
start of its own segment (`MARK acquire target target_id=... ...` / `MARK acquire air`) and
resets the settle window; both buttons stay enabled the whole session, and pressing either one
at any time — including right after Start, or straight from one target to another — simply
starts that segment. This is simpler than the old state machine (no forced Remove-before-next-
Place) and matches the actual bench workflow: "acquire this" is the only action, there's nothing
to separately mark as removed. `_scan_session_file()`'s resume path now tracks the single most
recent acquire marker (target or air) rather than an open/closed placement pair.

**"Last line" panel replaced with a live raw-value grid.** The single-line display (already
patched twice this session for the same underlying complaint — v1.11's word-wrap attempt and
v1.12's truncation) is gone; in its place, `_format_grid()` lays the last streamed `W` frame out
as a band x delay grid matching the profile's own structure, comma-separated with fixed 8-char
right-aligned cells so digits line up column to column row to row. This is declared as this
project's **standard grid orientation** (documented in the module header, for other tools to
follow): rows are bands in profile order (increasing pulse width, shortest at the top); columns
are delays within a band in profile order (increasing delay/time, shortest at the left) — so the
top-left cell is shortest-pulse/shortest-delay and the bottom-right is longest-pulse/longest-
delay. This holds without reordering because it's already how `cal_110_full_range_v4.json` (and
every other profile in this repo) lists its bands and each band's `delays_us`, and matches the
`col_index,band_index,...` ordering `pimd_classviz.py`'s session-dump colmap already uses.

**Verified:** offscreen PyQt smoke test extended to cover grid orientation (checked against the
profile's own band/delay ordering, not assumed), fixed-width cell alignment, an Acquire
Air→Acquire Target→Acquire Air sequence producing three correctly-tagged `MARK` lines with no
place/remove pairing errors, and resume recovering a still-open target acquisition as well as a
trailing air acquisition. **Not yet verified live** — still needs a real bench pass with the MCU
connected. (2026-08-03)

---

---

## Archive — consolidated 2026-07-31

### findings — the heatmap transient is scan order, not material; viscosity not supported

*2026-07-31 · answers the operator note at `TODO.md:112-115` · 41 timeable transitions from
9 targets across three relabelled dumps (`session_20260730_150124`, `_112854`, `_171026`).*

**The question.** Watching the Std Dev (rolling N) heatmap at 500/1000 while placing a target,
the grid "morphs to all yellow and back" — and *where the epicentre of that change sits appears
to vary with material*. Is that real, and is it being captured?

**It was not being captured, and it still is not, by design.** The transient is detected as a
single bit (`_sig_removal_armed`) and everywhere else defined as contamination — the settle
gate clears the buffer on any settle loss, `SETTLE_S_DEFAULT = 2.0` trims after every mark, and
the Settle tooltip says the quiet part out loud: *"so target/air transitions … can't enter the
window"*. The raw material was on disk the whole time; nothing had ever read session frames as
a per-cell time series.

**Most of the visible effect is the display, and this was predicted before measuring.** σ over
a fixed 50-frame window straddling a step of per-cell amplitude `A` goes as `A·√(f(1−f))` —
peaking at **`A/2`** half a window in (~3.6 s), back to floor one window (~7.2 s) later. At the
500/1000 µV scale **any cell whose settled |Δ| exceeds ~2 mV saturates**; a spanner at 60 mm is
39 mV, i.e. peak σ ≈ 19 500 µV, **19× over the ceiling**. So "all yellow" is guaranteed, and the
apparent epicentre is the settled signature re-rendered through a saturating scale — which is
material-dependent *by construction*, with no time-domain physics required.

**There is real per-cell structure, and it is scan order.** Timing each cell's 50% crossing
across a transition, the spread runs ~3× the noise prediction — so something beyond noise is
there. It is the sweep:

| measure | value |
|---|---|
| slope of t50 against channel index | **−5.6 ms/channel** (median) |
| across all 63 channels | **−350 ms** |
| one sweep at 6.94 Hz | 144 ms |
| sign consistency | negative in **33 of 41** events |

Cells are sampled sequentially within a sweep, so while the target is still moving, later-sampled
cells see it closer and cross their halfway point earlier. Direction and consistency both match.
**The magnitude does not fully match** — 350 ms is 2.4× the sweep period, which sequential
sampling alone does not explain; the 32-deep boxcar interacting with a monotonic per-channel
offset is the obvious candidate but is **flagged, not asserted**. It cannot be settled without a
controlled motion profile, which the hand-placed captures are not.

**The viscosity hypothesis is not supported, and the first answer was wrong.** Regressing out
the scan-order trend and normalising by transition duration, the per-*event* test read iron
0.090 vs non-ferrous 0.068, Mann-Whitney **p = 0.035** — apparently significant. It is not: those
41 events come from only **9 distinct targets** (`Fe_SS_disc_01` alone contributes 6,
`Ag_SS_spoon_plated_01` 10), so the test was pseudo-replicated. Aggregating to one median per
target first, the honest comparison is **iron n=4 median 0.099 vs non-ferrous n=5 median 0.069,
p = 0.286**. **Not supported.** With four iron targets the test has almost no power, so this is
"not shown", not "shown absent" — but the direction is at least consistent with the hypothesis,
and it would take a deliberate design (many targets, controlled placement) to say more.

**No consistent placement/removal asymmetry either** — it runs both ways across targets
(`Cu_Zn_brass_block_01` 0.443 place vs 1.165 remove; `Ag_SS_spoon_plated_01` 0.201 vs 0.175),
and tracks transition duration rather than material.

**What remains unexplained:** after scan-order removal the residual is still ~2.4–2.7× the noise
prediction, for iron and non-ferrous alike. Something common to all materials is in there, and
hand-motion trajectory — which varies per event and is unrecorded — is the leading candidate.

**Bottom line for the operator: the effect is real to look at but is instrumentation, not
target physics.** Nothing here justifies a new feature axis. The one concrete change worth
making is unrelated to materials: **the Std Dev heatmap's own defects** — it is the only heatmap
mode that bypasses the 64-frame glitch substitution and the v1.64 window-span stall guard, so it
displays glitches and post-stall drift as noise. Recorded separately; not fixed here.
(2026-07-31)

---

### utilities/session_relabel/ — v1 — retro-label the mark-free dumps by signature matching

**NOT read-only with respect to the repo**, unlike the rest of `/utilities/` — `--apply`
rewrites session dumps in place. Default is a dry run.

Every dump written before classviz v1.68 carries **zero `# mark:` lines**: logging auto-started
at v1.63 but the marks only ever came from a button nobody pressed. ~380 000 frames with no
ground truth, and no key to the corpus — the corpus `session` id and the dump filename are
independent stamps of different events. v1.68 fixes this forward; this recovers what it can
from the eleven dumps already on disk.

Plateaus come from the existing change-point approach; each is matched against the corpus by
**cosine on the unit shape**, with time used only to bound the candidate set (never to break a
tie, because `captured_at` lags the frames by tens of seconds). **The air baseline must be
interpolated between a reference before and one after**, exactly as `compute_plateau_stats()`
does — a single earlier reference carries the full drift to the capture, which at ~50 µV/s over
a 400 s plateau gap is tens of mV, and it was costing ~0.05 of cosine. With interpolation the
correct pairings score **0.996–1.000**.

Applied at a 0.95 floor: **39 mark pairs across 5 dumps** (171026 ×20, 122511 ×9, 112854 ×6,
150124 ×3, 082729 ×1), 440 plateaus rejected — most of them air, which shape matching cannot
identify by construction and which the tool therefore declines to label rather than guess.

**Provenance is explicit**: every injected `mark_target:` carries `reconstructed cos=… src=…`
in its notes, and a `# session_notes:` line records the tool, date and floor. **Two limits worth
knowing.** The match identifies the *target*, not the individual capture — repeated placements
of one target at one distance are shape-identical, so two plateaus can and do cite the same
`src=` capture. And injecting marks changes what `pimd_features.py --out` would produce from
these dumps: it currently emits nothing for them, and would now emit rows that *duplicate*
corpus captures under different ids. Do not merge without deciding to.

Every file backed up (`.bak-*-pre-relabel`) and verified after writing: injection only inserts
comment lines, and all 221 754 data lines across the five files came back byte-identical.
(2026-07-31)

---

### src/pimd_classviz.py — v1.68 — saving a signature marks the dump; new '# capture:' join key

Session logging has auto-started since v1.63, and `_append_mark()` / `_append_mark_target()`
have existed since v1.32 — but they were only ever called from the manual Mark button
(`:4765-4766`), which nobody pressed. Result: **all eleven session dumps on disk carry zero
`# mark:` lines.** ~380 000 frames of raw per-cell data, completely unlabelled, while the
ground truth sat in a separate CSV with no key linking the two.

`_on_sig_save_clicked()` now calls new `_sig_save_marks()`, which stamps the running dump with
the same `placement` dict the corpus row was built from — same functions, same format, no new
schema for the mark pair. Every capture labels its own frames as a side effect of being saved.

**The `# capture:` line is the part that matters.** A mark says *what* was in the field; it does
not say *which frames*. Those two were not recoverable from each other: the corpus `session` id
(`gui_*`) and the dump filename are independent stamps of different events, and `captured_at` is
stamped at **save** time — tens of seconds after the frames, because the air-after capture and
the Save/Ignore decision sit in between. Measured on the 07-30 data: a plateau at 15:31:44
belongs to a capture stamped 15:32:40. Recovering the window meant searching backwards for a
stable run, i.e. reconstruction.

`_append_capture()` writes the bounds explicitly — `capture_id`, the corpus `session` id,
`n_central`, and the target / air-before / air-after windows as epoch seconds — taken **straight
off the capture buffers** rather than re-derived, so the line cannot drift from what was
actually reduced. Those are the same PC clock that stamps every frame's `pc_wallclock` column,
so the join is exact and lossless. This also makes emitting at save time correct rather than a
compromise: the line self-describes its window, so there is no need to reach into the
acquisition state machine.

**Guarding is in the caller by necessity.** `_append_mark()` writes to `self._session_file`
without checking it (`:7540-7542`) — the Mark button guards upstream — so `_sig_save_marks()`
no-ops when not recording, paused, or with no file. Those are ordinary states (logging stopped,
replaying an old corpus), not errors, and a capture must never fail because of one. The write is
additionally wrapped: the corpus row is already on disk and is the product, so a dump-annotation
failure reports to the status bar rather than taking the capture down with it.

Verified: the three lines emit in order and round-trip through `parse_mark_target_line()` and
the new `_parse_capture_content()` (including `tilt_deg=30` surviving); `air_after` is correctly
omitted when that slot is empty; capturing with no session recording does not raise; and both
pre-v1.68 dumps still parse with `captures=[]`. (2026-07-31)

---

### src/pimd_features.py — v13 — '# capture:' lines parsed into SessionData.captures

Reader for the line classviz v1.68 writes. `SessionData` gains `captures` —
`list[(datetime, dict)]` with `capture_id`, `session`, `n_central` and the window bounds parsed
to `(start, end)` float pairs on the same clock as `t_seconds`, so a corpus row can be resolved
to the exact frames it was reduced from.

Two deliberate choices. Unknown keys are **kept rather than dropped**: this line is the join key
between the corpus and the frame stream, and a reader that silently discarded a field a later
classviz added would fail worse than one that carries it. And the branch sits with the other
mid-stream `#` handlers, so it is additive — every dump written before v1.68 parses exactly as
before with `captures=[]`, which was verified against two of them rather than assumed.
(2026-07-31)

---

### findings — the two-basis mixing law is confirmed; and two corrections to the 07-31 entry

*2026-07-31 · `gui_signatures_targets_v3_20260728_142316.csv`, now 188 captures ·
`cal_63_air_bat_v3` sha `4a2352d2` · fw 4.26 · 6S battery. Oblique captures taken the same day
the Tilt input shipped: `Fe_Cast_iron_trivet_01` at 0/30/60/90° ×2 reps and `Fe_SS_disc_01` at
30/60/90°, all at 60 mm, `long_axis=z`.*

**1. Pasion–Oldenburg's mixing law holds on this instrument.** The morning's entry could confirm
rank-2 structure and x ≈ y but explicitly could not test the model's actual content — that an
oblique orientation is a *weighted mix* of the two extremes — because every capture on disk sat
at 0° or 90°. It now can.

Fitting each oblique capture as `v(θ) = a·v_axial + b·v_transverse` against the dipole
prediction `a = cos²θ`, `b = sin²θ`:

| target | cos(axial, transverse) | oblique fit error in `a` | in `b` | amplitude meas./pred. |
|---|---|---|---|---|
| `Fe_Cast_iron_trivet_01` | 0.747 | **−0.015 ± 0.036** | −0.010 ± 0.075 | 0.982 – 1.006 |
| `Fe_SS_disc_01` | 0.753 | **+0.008 ± 0.048** | −0.035 ± 0.006 | 0.927 – 1.042 |

Both coefficients land on the prediction within their scatter, and the *amplitude* — a
prediction the shape fit does not constrain — comes out right to within 2% on the trivet.
Every oblique capture is a **positive convex combination** of the two extremes (a, b ≥ 0 within
noise, a + b ≈ 1): no extrapolation, no third component. Fit residuals run 4–21% against a
repeat-noise RMS of 9.4% (trivet) / 6.6% (SS disc).

**The fit must be done on raw vectors, not unit shapes.** Normalising each capture to unit
length destroys the amplitude weighting the model predicts, and the unit-shape version reads
*shallower* than cos²θ (weight 0.83 / 0.46 at 30° / 60° against 0.75 / 0.25) — which would have
been recorded as a partial failure of the model rather than an error of method. Noted because it
is the kind of mistake that gets published.

Every derived coordinate moves monotonically with tilt, which is the same result seen
qualitatively — trivet early-band mean **+35 → +17 → −22 → −58** (×10⁻³) and crossing width
**8.0 → 8.5 → 17.4 → 30.8 µs** across 0/30/60/90°, with amplitude falling 45.2 → 21.4 mV.
**The same object walks from `ferrous` to `crossover` as it is tipped**, which confirms from a
second direction the reframe that family is orientation, not material.

**What this changes.** Orientation stops being a confound and becomes a *fitted parameter*:
given a target's two basis shapes, θ is solvable from one capture, and an orientation-invariant
descriptor — the 2-D subspace itself rather than any signature in it — becomes well-defined.
That is the foundation the τ-class + size tier needs. **Cost of the result: two placements per
target**, since the extremes were already being captured.

**2. Correction — the solder roll's registry row was right.** The morning's entry stated that
`magnet_test = none` "cannot be right for an object behaving this way" and named a steel spool
core as "the obvious candidate". The operator has since magnet-tested it: **not magnetic at
all.** The registry needs no change and that speculation is withdrawn.

**The surviving explanation is a shorted multi-turn coil**, and it is more interesting than the
one it replaces. A spool of solder wire whose ends touch is a closed conductive loop of high
inductance and very low resistance — a long L/R time constant. A slowly-decaying induced current
reads exactly like ferrous on *both* discriminators: flat late band (`late` +178 ×10⁻³) and high
decay persistence (5.26, 5.70), crossing pinned at the 8 µs rail. So this is a genuine
**false-positive mode for tier 1** — the one non-ferrous target in the corpus that breaks the
97.2% late-sign rule — and a shorted loop is a shape a real buried target can take.

The new `ax=z, tilt=0` captures read ferrous (persistence 5.26/5.70) while the 07-30 untilted
`ax=z` captures read non-ferrous (1.07/1.20), so the two states are orientation-selected —
consistent with flux threading the shorted turns in one pose and not the other. **Flagged, not
asserted:** this cannot be settled from the corpus. The decisive test is a continuity
measurement across the spool's two wire ends, which takes seconds and would confirm or kill it
outright.

**3. Correction — `magnet_test` was not the thing to doubt.** The morning's entry reached for a
registry error to explain a signature. The registry was correct and the physics was unusual;
the reasoning should have run the other way. Recorded because the same reflex would misfire on
any closed-loop target. (2026-07-31)

---

### src/pimd_classviz.py — v1.67 — Tilt (°) capture input for oblique poses

`long_axis` can only express 0° or 90° to the coil axis, so every capture in every corpus
on disk sits at one of those two poses. That is why the 2026-07-31 analysis could confirm
the two-basis model's rank-2 structure and its x ≈ y prediction (cosine 0.998) but **not
its actual content** — that an oblique orientation is a weighted mix landing on the arc
between the extremes. Nothing in the capture path could record an intermediate angle.

New **Tilt (°)** spinbox (0–90, step 5) in the Analysis tab's Signatures placement row,
immediately right of Long axis. It is enabled only when **Long axis is `z`** — a tilt is
defined relative to the coil normal, so it is meaningless against the others — *and* a
signature file is open; `_update_tilt_enabled()` is kept separate from
`_update_sig_capture_gating()` because both conditions have to hold and they change
independently. `_placement_from_widgets()` is the single place the rule lives: it emits
the spinbox value for `z` and `''` for everything else, so a 30° left over from an
oblique run cannot reach an x/y row.

**Deliberately not persisted to settings.** It reopens at 0 every launch. A persisted
placement combo silently riding along on every later capture is exactly what got
`face_normal` removed at v1.60, and the same trap is available here; holding the value
within a session but not across launches keeps the convenience without it.

`tilt_deg` joins the placement tuple, so the Repeat # suggestion had to be re-wired to
the spinbox's `valueChanged` — otherwise a 30° capture inherits the 0° placement's count
and the two poses collide as repeats of one placement.

**One guard is load-bearing.** `_scan_editable_signature_file()` builds its column index
from the *tool's* `CORPUS_HEADER_FIELDS` while reading rows from the *file*, and every
corpus on disk is one column short of the grown list. Verified: an unguarded
`first[idx['tilt_deg']]` raises `IndexError` on all three real files
(v3 26 cols, v1 25, scratch 25), i.e. opening any of them would have broken the signature
list. Guarded, they read `''`. `_placement_tuple_key()` moved to `.get()` for the same
reason. `_append_mark_target()` appends the field last, matching
`pimd_features._MARK_TARGET_KEYS`. Header title line also corrected — it still read
v1.63 against `APP_VERSION` 1.66. (2026-07-31)

---

### src/pimd_features.py — v12 — tilt_deg column

New `tilt_deg` column: tilt of `dim_a` away from the coil normal in degrees, or blank when
not recorded. **0 = `dim_a` down the coil axis** (the same pose as `long_axis=z`),
**90 = in the coil plane** (the same pose as `x`/`y`). The two ends are deliberately
redundant with `long_axis`; the column exists for the angles in between.

Appended **last** in `CORPUS_HEADER_FIELDS`, and that is a constraint rather than a
preference: `pimd_classviz._scan_editable_signature_file()` indexes positionally off this
list while reading files that lack the column, so appending is safe and inserting would
silently misread every corpus on disk. Same reasoning for `_MARK_TARGET_KEYS`, which
`parse_mark_target_line()` zips positionally — appending leaves old nine-field lines
parsing correctly and gaining a blank tilt (verified both ways).

`Plateau` gains the field with a default, so none of the ~9 construction sites across this
module and classviz needed touching, and the air/placeholder/scratch paths keep writing
blank. New `format_tilt()` renders `None` and `''` identically as `''` while preserving a
recorded `0` — the distinction the placement key depends on. Optional on read, like
`pack_v` and for the same reason: every corpus on disk predates it. (2026-07-31)

---

### src/pimd_corpus_check.py — v1.9 — tilt_deg joins the placement tuple

`tilt_deg` added to `PLACEMENT_FIELDS`, so 0°/30°/60° at one distance are three distinct
placements with independent `repeat_idx` sequences rather than three repeats of one — the
whole point of recording the angle. Added to `OPTIONAL_FIELDS`.

The delicate part is that an optional field in the placement key can present as an absent
column, a missing dict key, `None` or `''`, and all four are the same physical statement.
New `PLACEMENT_BLANK_FIELDS` collapses them to `''`; `placement_key()`/`target_key()` moved
from `sig[f]` to `sig.get(f)` so a dict built from a corpus without the column does not
`KeyError`. This is the failure `PLACEMENT_CONSTANT_FIELDS` was created to prevent arriving
by a different route — without it every historical placement would split in two and every
`repeat_idx` restart.

**A recorded `0` is not blank.** 0° is a real axial capture; conflating it with "no angle
recorded" would merge the oblique study's 0° base with every `long_axis=x/y` capture of the
same target.

Verified rather than argued: `pimd_corpus_check` output on both corpora is **byte-identical**
to the pre-change baseline, all 377 checks and all 134 repeat-consistency rows. (2026-07-31)

---

### src/data/corpora/gui_signatures_targets_v3_20260728_142316.csv — migrated for tilt_deg

Corpus append writes **the file's own header columns**, not the tool's (classviz v1.65), so
appending an oblique capture to a file with no `tilt_deg` column would have silently dropped
the angle — the feature would appear to work and record nothing. The active v3 corpus is
therefore migrated in place: `tilt_deg` appended to the header, one blank cell added to each
of 10 710 rows. Backup kept alongside the existing ones as `.bak-*-pre-tilt`.

Migrating rather than starting a fresh file keeps the corpus in one piece, which the
2026-07-31 analysis supports directly — the between-session noise component measured **zero**
across three days and eight sessions, so captures made before and after this line are
comparable. Verified: every pre-existing column byte-identical across all 10 710 rows, and
`pimd_corpus_check` output identical to the pre-migration baseline. The v1 corpus and the
scratch file are left unmigrated; they still load, reading blank. (2026-07-31)

---

### findings — v3 corpus analysis: the two-basis model holds, and "crossover" is orientation

*2026-07-31 · `gui_signatures_targets_v3_20260728_142316.csv` · 170 captures / 25 targets over
eight sessions 07-28 → 07-30 · `cal_63_air_bat_v3` sha `4a2352d2` · fw 4.26 · 6S battery ·
gate = SNR ≥ 5 on `splithalf_floor` unless stated. Compared throughout against the 2026-07-23
`targets_v1` corpus (66 captures, `cal_63_air_v2`, bench PSU).*

**1. The Pasion–Oldenburg two-basis model is supported, and the coil-frame prediction is
confirmed.** Placement records `long_axis` in the coil frame: **z = axial** (dim_a down the
coil's winding axis), **x and y = transverse** (both in the coil plane, differing by a 90°
in-plane rotation). If a signature is a weighted mix of one axial and one transverse basis
shape, then x and y must be the *same* mix and every target's orientation set must be rank 2.

Both hold. Across the five targets holding both x and y, `cos(x̄, ȳ) = 0.998` median, minimum
0.983 — the two transverse orientations are indistinguishable *even for a 210 mm spanner*,
where a 90° in-plane rotation is a large physical change. All the variation sits on the
transverse↔axial contrast, and it is graded by geometry:

| target | cos(transverse, axial) | rank-1 → rank-2 RMS residual | own repeat noise |
|---|---|---|---|
| Cu_pipe_01 (tube) | 0.991 | 0.137 → 0.109 | 0.114 |
| Fe_Zn_gal_rhs_01 (tube) | 0.982 | 0.171 → 0.144 | 0.154 |
| Fe_spanner_01 (irregular) | 0.986 | 0.183 → 0.131 | 0.144 |
| Al_plate_01 (plate) | 0.950 | 0.153 → 0.099 | 0.042 |
| Cu_Zn_brass_block_01 | 0.935 | 0.180 → 0.078 | 0.158 |
| Fe_SS_disc_01 (thin disc) | 0.776 | 0.338 → **0.043** | 0.062 |
| Fe_Cast_iron_trivet_01 (thin disc) | 0.736 | 0.446 → 0.266 | 0.320 |
| Sn_Pb_solder_spool_01 (see §5) | **−0.298** | 0.602 → 0.127 | 0.201 |

Every anisotropic target collapses to its own electronics-noise floor at rank 2, and rank 3
buys nothing. Rod-like targets are already rank 1 — they have no measurable orientation
dependence at all, which the model permits (axial ≈ transverse basis). **`Al_plate_01` is the
only apparent counterexample** (rank-2 residual 0.099 against a 0.042 noise reference), and it
is not one: its residual correlates −0.82 with SNR and +0.54 with distance, its noise reference
is estimated from four high-SNR placements only, and within its best-sampled orientation
(ax = y, n = 9, SNR 7.7–189) it is rank 1 at 0.048. The excess is the marginal 300/360 mm
captures sitting on the gate.

**What this corpus cannot test, and it is the whole remaining question.** `long_axis` only ever
takes x, y or z, so **every capture is at 0° or 90° to the coil axis.** Rank-2 structure and
x ≈ y are necessary consequences of the two-basis model but they are also consequences of
"there are two placements and they differ". The model's actual content — that an oblique
orientation is a *weighted mix* landing on the arc between the two extremes — is untested,
because no oblique placement exists. **Test:** capture one strongly anisotropic target
(`Fe_Cast_iron_trivet_01` or `Fe_SS_disc_01`, cos 0.74–0.78, the largest lever in the set) at
~30° and ~60° at 60 mm, and check the fitted mixing weight against cos²θ. Two placements per
target would settle it.

**2. "Ferrous vs crossover" is an orientation coordinate, not a material one.** This is the
session's main reframe. The early-band sign — which is what separates `ferrous` from
`crossover` in `pimd_shape.family()` — splits by *placement*, not by target:

| orientation | ferrous-vs-crossover accuracy (gated) |
|---|---|
| ax = y (transverse) | 90.9% (n = 22) |
| ax = x (transverse) | 75.0% (n = 16) |
| ax = z (**axial**) | **53.8%** (n = 13) |

Every crossover→ferrous miss in the corpus is an ax = z capture. `Fe_Cast_iron_trivet_01` is
the clean demonstration: lying flat (ax = x) it reads `crossover` at 29–36 µs crossing with
early −50 to −102 ×10⁻³; stood on edge (ax = z) it reads `ferrous`, crossing pinned at the
8 µs rail, early +7 to +47 — and it is 2.4× louder on edge (50.1 mV against 20.9 mV L2 at
60 mm). That is what a 3 mm-thick 75 mm disc should do: face-on, flux threads the disc and the
eddy loop has the full 75 mm of area, so the fast negative eddy term dominates the early bands;
edge-on the loop area collapses to the 3 mm thickness, the eddy term goes with it and the
magnetic term is left exposed. The spanner fails the other way — it reads `crossover` broadside.

So the early axis measures **presented eddy-loop area** = geometry × orientation, and cannot be
read as a material subclass. Decay persistence does not rescue the split either: ferrous
median 4.20, crossover median 4.82, fully overlapping. Recommend the tier be renamed and
re-scoped rather than its accuracy chased.

**3. What survives the reframe is stronger than the old family verdict.** The *late*-band sign
— iron-bearing vs non-ferrous — is the robust axis, and it does not need the gate:

| tier | rule | accuracy |
|---|---|---|
| **1 — iron-bearing vs non-ferrous** | sign of late-band mean | **97.2%** (141/145) **ungated**; 98.3% gated |
| 2 — ferrous vs crossover | sign of early-band mean | 76.5% (39/51) gated — see §2 |
| combined 3-class (the v1 comparison) | current `family()` | 88.1% gated, 85.5% ungated |

Against the 2026-07-23 epoch's 100% gated / 95.3% ungated three-class figure this reads as a
regression, and it is not one: the v1 corpus held **no ax = z captures of any crossover
target**. It sampled only the orientation where the early sign happens to work. The v3 corpus
is 2.6× larger and deliberately spans orientation, so it exposes a failure mode the earlier
number could not see. Decay persistence remains a clean independent second opinion on tier 1 —
non-ferrous 0.65–1.80, iron-bearing 2.12–9.02, **no overlap** (excluding the two contaminated
captures of §5). The `ferrite_toroid_01` contradiction reproduces: positive by sign, 1.51 by
persistence — still the mineralised-ground preview.

A noise-scaled dead band on the early axis works as anticipated but is a coverage trade, not a
fix, since the misses are physical rather than marginal: 1.5σ → 90.7% on 92% decided; 3σ →
95.7% on 80% decided.

**4. Placement variation is below the electronics noise floor — it is not the limiting factor.**
Repeats at an identical placement tuple were captured without moving the target, so they
measure electronics alone; the same tuple recaptured in a *later session* necessarily involved
re-placing it. The two distributions are the same:

| | n | median cos | p10 | min | median angle |
|---|---|---|---|---|---|
| same session (never moved) | 46 | 0.9894 | 0.9550 | 0.577 | 8.3° |
| cross session (**re-placed**) | 37 | 0.9899 | 0.9675 | 0.948 | 8.1° |

The re-placed set is if anything *tighter* in the tail. Across 11 tuples spanning four targets,
manual re-placement at a nominal (distance, orientation) contributes nothing measurable on top
of the measurement noise. Amplitude repeatability at a fixed placement: CV median 2.6%, p90
9.6% (consistent with the ~6% in the 07-28 entry).

Shape scatter does **not** saturate — it tracks SNR all the way down (13.4° at SNR 5–10,
7.8° at 10–20, 4.8° at 20–40, 2.6° at 40–100, 1.2° above 100). But it runs **2.4× the
isotropic-additive-noise prediction** built from `splithalf_floor` in 90% of pairs, which is
the same factor the air captures show directly (across-capture L2 4.03 mV against a median
`splithalf_floor` of 1.82 mV, ×2.2). **`splithalf_floor` understates reproducibility noise by
roughly 2×**, because it is a within-capture short-timescale statistic. Practical consequence:
the SNR ≥ 5 gate is really a reproducibility gate of ≈ 2.5–3.5, which is why raising it keeps
paying.

**5. Two data-integrity items found, both isolated and both needing an operator decision.**

- **`Sn_Pb_solder_spool_01` is a different physical object across the epoch boundary.**
  `targets_v3.csv`'s own header records "changed solder roll", and the data agrees
  emphatically: cross-epoch cosine of the mean shapes is **+0.143**, against ≥ 0.95 for every
  other matched target. In v1 it read textbook non-ferrous (early −94, late −130, never
  crosses, persistence 0.88). In v3 it reads non-ferrous end-on (ax = z) but **ferrous**
  broadside (ax = y: early +31, late +166, crossing at the 8 µs rail, persistence 4.28), with
  cosine **−0.3 between its own two orientations** — the largest orientation effect in the
  corpus by a wide margin. The registry row still says `magnet_test = none`,
  `material_class = solder_sn_pb`, which cannot be right for an object behaving this way; a
  steel spool core is the obvious candidate. **Actions:** magnet-test the new roll and correct
  the registry; and since `target_id` must never be reused (registry rule), the new object
  needs its own id, with the v1 captures left pointing at the old one. All cross-epoch
  comparison for this id is invalid until then. It is excluded from the aggregates above.
- **One rogue capture: `Fe_Cast_iron_trivet_01` @ 120 mm, ax = x, r1 (07-28T16:30).** Cosine
  0.33–0.68 to every other trivet capture *including its own r2 sibling at 0.577*; persistence
  1.15 against 2.6–4.4 for the rest; late-band mean +70 against +116…+155. It passes both
  quality gates — stamped `ok`, SNR 16.5 — and it single-handedly sets the worst within-target
  cross-distance cosine in the corpus (0.591, against a 0.985 median) and inflates the trivet's
  noise reference from ~0.13 to 0.320. Air-reference staleness is the leading suspect (§17.4:
  a reference older than ~10 s rivals a weak target) but the corpus carries no air age, so this
  cannot be settled from the file. **Neither gate catches it; a within-placement consistency
  check between repeats would.**

**6. The epoch change is a coherent one-parameter shift; nothing needs re-labelling.** No target
changed its majority family verdict between `cal_63_air_v2` and `cal_63_air_bat_v3`. The early
and late band-range means both moved **+5.2 ×10⁻³ median** (positive), and every crossing width
that is interior to the ladder in both epochs moved **shorter, ratio 0.76 median** — trivet
34 → 24 µs, SS disc 31 → 18, gal RHS 21 → 19, gal pipe 17 → 13. Direction and sign are what the
profile's own delay re-anchoring predicts: v3 samples 40–144 ns *later*, the fast negative eddy
term has decayed further by the sample instant, so every band-mean moves positive and the
negative→positive crossing arrives at a shorter pulse width. The shift lands hardest on the
crossover family because that is where |early| is smallest. Amplitude moved by family, not by
gain: non-ferrous ×0.67–0.89 (Al plate, Cu pipe), iron-bearing ×1.28–1.79 (trivet, ferrite,
SS disc, shackle) — same explanation, and not a supply effect, which would scale everything one
way. **Crossing widths are therefore per-epoch quantities and the §17.6 ladder values need
restating against v3.**

**7. Noise: the corpus's 19 air captures are the best floor probe in the record, and they say
the between-session component is zero.** Pooling within-session per-cell σ against the
all-captures σ gives L2 4.24 mV vs 4.03 mV — **no measurable session-to-session offset** across
three days and eight sessions. Captures from different days are directly comparable, which is
what a training corpus needs.

The floor is not flat, and the dominant feature is **not** the (9 µs, 4.9 V) corner of the
07-28 entry. Per-cell σ over the 19 air captures puts **46% of all noise energy in the 3.80 V
column alone** (column L2 2.85 mV against 0.37–1.48 for the other eight), concentrated at long
pulse widths — (100 µs, 3.80 V) = 1.91 mV, (45 µs, 3.80 V) = 1.23, (100 µs, 4.40 V) = 1.02.
The three corner cells carry 7%. The two findings are not in conflict: the 07-28 corner came
from matched target pairs within one afternoon, this is across-capture σ spanning the campaign,
and the 3.80 V excess is **entirely confined to the fresh-pack and cold-start captures** —
21:17 at 24.40 V reads 5.55 mV on that column, 22:34 at 23.69 V reads 4.39, the 09:39/09:52
cold pair read 4.85/6.15, while every settled capture in the 21.1–23.4 V window reads
0.64–2.06. That is §17.13's moving-zone model showing up in target-free data, and it means
**the 46% is a pack-state artefact that operator discipline already removes**, not a property
of the profile. Air captures at 23.36 V *after* a long soak read clean (0.64, 1.56),
consistent with the transition band being soak-sensitive rather than voltage-fatal.

Aggregate floor comparison against the v1 epoch is unfavourable at face value — median
`splithalf_floor` 1.245 → 1.784 mV, and matched (target, distance) SNR down ×0.73 median — but
this is composition plus the pack-state tail above, not a regression in the rebuilt supply:
the 07-28 session opens at 1.25 median, indistinguishable from v1, and the settled air captures
close at 0.90–0.97. (2026-07-31)

---

### DESIGN.md — 1.12 — audit pass: corrections against the latest bench data

Human-directed, read-only rule suspended as for a §18 pass. **Not** a consolidation — no new
tooling or hardware work is folded in. This pass fixes defects found by a full
contradiction / unit-error / non-sequitur audit of DESIGN.md 1.11 and every CHANGELOG archive,
run 2026-07-31. **Rule applied throughout: the latest bench data wins.** Where two measurements
disagree the later is kept and the earlier *scoped*, never deleted; where the text cannot be
settled from data it is flagged rather than asserted (`CLAUDE.md`).

**The three substantive corrections.**

1. **Frame rate — the ≈ 301 ms full-sweep refresh was never measured, and is wrong by ~2×.**
   `acquire_mode2()` gives each cell one PWM period per sweep and emits exactly one W record
   per sweep (`MIN_EMIT_MS = 10` never binds at these sweep times), so frame rate *is* sweep
   rate. Measured on the firmware clock across the campaign dumps: **6.88–6.92 Hz, interval
   0.1445–0.1455 s** (the 07-29 dump's 5.94 Hz mean is the §14.10 stall inflating gaps).
   The ~289/301 ms figures — and the "32-deep ≈ 9.2 s rolling average" derived from them —
   are the stale ~3.3 Hz assumption that features v11 already corrected in the tooling
   comments; they had survived into DESIGN as though measured. §8, §9, §10, §17.7 corrected.

2. **The pack-voltage window's three edges were used interchangeably, and contradicted the
   result's own anchor observations.** §1 said the columns are bad above ≈ 23.5 V "however
   long the rig has run" while §17.13 said always-bad begins at 24.0 V with 22.5–24.0 V a
   soak-sensitive transition. Now stated once, consistently: **≈ 24.0 V = always-bad edge
   (measured) · 22.5–24.0 V = transition, soak worth ~2.5–3× · 21.5–23.3 V = conservative
   operating window · ≈ 23.5 V = operational shorthand for the transition's practical onset.**
   Three observations that sat *outside* the window while being cited as inside it are now
   described as what they were — the v3 lock at 23.5 → 23.35 V, the 07-28 corpus day opening
   at 23.77 V, and §17.11's "drained into the good window" (it had drained into the
   transition band, where a soaked rig reads clean).

3. **§14.10 was carrying superseded first-pass numbers for the post-stall step** (+10 mV at
   9 µs to +78 mV at 100 µs, one sign across bands). That reading came from the same first
   pass through the 07-29 dump that manufactured the phantom 23:28 "noise relapse" — windows
   spanning the stall read accumulated drift as signal. The stall-guard-cleaned re-analysis in
   §17.13 reads **−8.3 … +23.8 mV, changing sign across bands**, which is also the only
   version consistent with the document's own supply-vs-thermal discriminator. §14.10 now
   carries §17.13's row.

**Unit and value corrections.** RX coil wire length **30.8 m → ≈ 69.5 m**: 2 × (0.43 + 0.265) m
× 50 turns = 69.5 m, and the measured 22.9 Ω at ~0.34 Ω/m (30 AWG) independently implies ~67 m
— 30.8 m was wrong by 2.3× (§5). §17.1's power table de-garbled from the 2026-06-17 bench
entries: the "10.6" cell is 10601 Hz with the kHz value left in an Hz column, and the "Freq
(actual)" column is **supply current in mA**, not a frequency. §17.5's freeze cal "1 delay of
72" → **13 delays** (the coherent +40 ns shift of the 4.5 V column). Registry **26 → 27
objects** (26 at the 07-26 check plus the solder stick added 07-28; verified against the file).
§7's Mode 2 single-cell σ "matching the M=32 boxcar expectation" → **M=16**, which is what that
profile used and what 310 µV actually matches. §3's raw noise **±400 µV → ±1400 µV**, agreeing
with §7 and with every measurement in this file — ±400 appears nowhere in the record. §14.11's
"3–10× above every other cell" scoped to the two cells for which it holds. §17.9's
decay-persistence claim reworded off "iron-bearing vs non-ferrous", which the gated ferrite
toroid at 1.37 falsifies as stated.

**Stale pointers fixed:** the scratch row's promotion path (`targets_v1.csv` → `targets_v3`),
a §14.1 thermistor precondition that no longer exists in §14.1, a "§13 feature-portability
question" that §13 does not contain, and the LiPo/18650 chemistry mismatch. §8's `ticks_ms`
choice is kept but its stated reason corrected — the observed blocks were 2–15 s, well inside
`ticks_us` validity; the guard is against a single ≥ 8.9-minute block.

**Not fixed, recorded instead** (see the errata entry): items needing bench data — §3 vs §7
filtered-noise figures, R9's clamp current against the +135 V RX flyback, the
group-delay/settling pair, and the stall's mutually inconsistent delivery figures. (2026-07-31)

---

### findings — pack-voltage result independently re-measured; zone migration confirmed

The 2026-07-30 result was re-derived from the raw session dumps by a different method than
`soakvolt.py` used, as an audit check on the most consequential claim in the document.
**It reproduces, and the structural claim comes out stronger.**

**Method, and why it differs.** Per-column noise as the **standard deviation of successive
frame differences, ÷ √2**, averaged over the seven bands of each threshold column. A plain
windowed σ — what the published µV figures use — cannot separate noise from drift, and over a
250-frame window drift dominates: the same windows read ~12.8 mV on *every* column during the
15:01 warm-up, which is slope, not noise. The first-difference estimator is blind to any linear
trend, so it measures per-frame noise directly. Absolute values therefore run ~2.8× below the
published ones and **are not comparable to them**; the ratios are.

| condition | 3.80 V | 4.40 V | 4.20 V | 2.40 V |
|---|---|---|---|---|
| 20:52 dump, pack B fresh, 24.90 V | **749** | **277** | 83 | 78 |
| 08:27 dump, opening (high pack) | **719** | **449** | 130 | 67 |
| 15:01 dump, contested cold start | **292** | 153 | 56 | 47 |
| 17:10 dump, mid-session ~22.3 V | 67 | 72 | 68 | 57 |
| 17:10 dump @ 20:41, 21.08 V | 64 | 70 | **173** | 55 |

(µV, detrended; 400-frame windows taken past the stream-start transient.)

**What it confirms.** On a fresh pack the 3.80 V and 4.40 V columns are elevated with **4.20 V
clean between them** — the non-monotonic signature no uniform level shift can produce.
Mid-window the whole grid sits at one floor (57–72 µV). And at 21.08 V the trouble has **left**
3.80/4.40 V and **appeared at 4.20 V** at 2.5× the floor. That is the moving-zone model — a
noise region fixed on the decay waveform while pack voltage scales the decay — observed
directly, by an estimator that cannot confuse it with drift. Ratio cross-check against the
published metric: the contested 15:01 session reads 292/749 = 0.39 of the fresh-pack value here
against 742/2090 = 0.36 published.

**What it changes — one rule.** §17.13's "below 22.5 V the 3.80 V column is *always* acceptable
(189–502 µV)" is too strong. The 15:01 cold start reads **~5× its own floor** (292 against
~55 µV) at a corrected ≈ 22.45 V. The changelog's settling correction for that session stopped
at the 3.4-minute reading and put it at ≈ 22.67 V; its own 25-minute point shows settling still
running at 0.88 V/h — ~3× the streaming drain — and back-extrapolation from the settled point
gives **≈ 22.45–22.47 V**, which cross-checks against the session's actual 15:36 reading, where
22.67 V matches nothing. So the contested point sits at or just below the 22.5 V edge *and* is
genuinely elevated. Restated: below ~22.5 V those columns are usually at the floor, but the
lower transition is **not guaranteed clean from cold**.

**Hypothesis this raises — flagged, not asserted.** The 2026-07-24 survey found the same two
columns elevated at **22.4 V**, below the "always acceptable" edge, and that has read as a flat
contradiction. It ran `cal_63_air_v2`, whose delays are 40–144 ns earlier than v3's. Since the
zone sits at a fixed place on the decay and each profile's delays cut that decay at different
points, **the clean window plausibly belongs to (pack voltage × profile delays), not to pack
voltage alone** — which would explain elevated columns at 22.4 V under v2 while v3 reads floor
at 22.3 V. Not established: no v2-era session dumps exist to test against (auto-logging starts
07-29). **Test:** run the §17.7 fine threshold sweep at two stated pack voltages under *both*
delay sets, not just v3's. If it holds, §10's "a profile is only fully specified together with a
pack-voltage range" tightens to "…and the window is itself per-profile". (2026-07-31)

---

### findings — errata from the 2026-07-31 document audit

Contradictions and arithmetic errors found inside **archived** entries. Archives are the
historical record and are not rewritten, so they are recorded here instead. Where DESIGN.md had
taken a side, the side it now takes is noted.

**Numbers that disagree with themselves or each other.**

- **Campaign frame count: "435k frames" vs "332 957 frames"** for the same nine dumps, 31 %
  apart. Neither matches the files today, which hold **373 325** rows — 332,957 was the
  analysis-time snapshot (the last dump was still growing; it ran to 23:31:35, not the recorded
  21:14 endpoint, which that dump's own soak counter also contradicts: +3,334 s past 20:52:37
  lands at ≈ 21:48). DESIGN keeps 332,957 as the figure the analysis was actually run on, now
  labelled as such.
- **Host-stall delivery figures do not close.** "414 → ~35 per minute for 47 minutes" with
  "2700 s" of dead time inside a 2,820 s window: 2,700 s dead leaves ~120 s live ⇒ ~18
  frames/min, not ~35. The 2,700 s is corroborated twice (222 gaps averaging ~12.2 s; the
  "overstates soak by ~45 min" figure), so "~35/min" is the suspect number. Not resolvable from
  text — the raw gap list would settle it, and nothing downstream depends on it.
- **34 vs 35 rejected windows** for the same 07-29 stall, between `soakvolt.py` and classviz
  v1.64's guard, which are documented as mirroring the same test.
- **The same pre-15:01 rest is "94 minutes" and "2 h"** in different entries. Related: the
  "+0.29 V rest recovery" was read 20 s after load-on, so much of it is unsettled transient.
- **The 15:01 settling correction is ≈ 22.45 V, not ≈ 22.67 V** — see the re-measurement entry
  above, which also shows why it matters.
- **`setData` "1 + n_bands + n_cells … (17 at 63 cells)"** — that expression gives 71;
  17 = 1 + 7 bands + 9 thresholds.
- **"up to 40×" vs "~28×"** for the same frame-rate window-sizing error, within one entry.
- **`SAMPLE_PULSE_CORRECTION` 0.752 → 0.908 µs is undocumented** — no entry records the change,
  and 0.752 µs is exactly on-grid (94 × 8 ns), so the half-grid dither v4.22 fixed could not
  have arisen while it held.
- **Solder-roll falloff "~1.7×" vs "1.21×"** for the same 5→15 cm ratio on the same corpus.
- **`pimd_classify` v1.0 "a perfect score" of 6/6/5/5 against event counts 6/6/6/4** — as
  written, session 4 scored 5 of 4. The totals match (22), so a transposition is likely.
- **"~100 Hz nominal" Mode 2 rate** (classviz v1.28) is ~14–30× the real rate; see the DESIGN
  1.12 entry.
- **Registry count stated as 23** in two v1 entries; the corrected figure is 22, and that
  correction lives only in DESIGN.
- **Duplicate "new — v1" entries for `pimd_targets.py`** giving incompatible accounts of the
  same negative test (5 planted errors vs 6, different sets).
- **Corpus capture counts are three same-file snapshots**: 98 (post-repair, midday), 166
  (features v11), and **170 today**. `pack_v` "populated on only 10 of 166, all 22.67" was
  already stale when written — the file now carries **82** populated values spanning
  21.08–24.4 V, of which exactly 10 are the held 22.67. The null result that used the 10-of-166
  state is unaffected, but the figure should not be quoted as current.

**Claims that outrun their evidence.**

- **"Everything above is simulated"** closes the classviz v1.42 entry, which above it reports a
  first bench run and three results labelled *Measured* — including the copper-pipe window test
  and the spanner hold-time test the design still relies on.
- **"Intermittent rather than a trend"** for excursion rates running 12 → 25 → 40 → 47 % across
  four consecutive sessions, dismissed on a Spearman of +0.10 computed over all captures — which
  tests the bulk, not the tail the entry itself says is growing.
- **"The three implicated cells stand 3–10× above every one of the other sixty"** — the third
  cell reads 0.61 against a 0.50 best-of-the-rest, i.e. 1.2×.
- **"Degrades monotonically with pulse width (0.9× at 9 µs → 8.0× at 67.2 µs)"** — a series
  monotonic in pulse width would peak at 100 µs; the parenthesis contradicts the claim.
- **"Converging"** for the 6S thermal fingerprint, where the only quoted comparator is the
  previous −56…+16 ns against the new −96…+16 ns.
- **"A 60 s-old reference carries ~1 mV"** — at the 50 µV/s rate used two lines earlier that is
  3.0 mV, and the entry's own weak-target figures are 0.35–0.36 mV.
- **The 3381 s baseline "observed" at ~169 mV/cell** is exactly 3381 × 50 µV — the nominal
  prediction restated as an observation. The same entries' one direct measurement (5.2 mV at
  150 s) implies ~35 µV/s, which would predict ~117 mV. The 50 vs 35 µV/s discrepancy runs
  through every reference-age figure and is nowhere acknowledged.
- **"Right to within a few minutes"** for a runtime prediction whose crossing was never observed
  (the pack came off first) and which the entry's own drain rate puts ~20 min out.
- **A findings heading asserting "the Frames default caused it"** while its body says two
  candidate causes were "not separated", and the adjacent entry favours the other one.
- **The "equal-power bands"** description is contradicted by the same era's own P ∝ pulse² · freq
  model, which spans 12× across those bands; three incompatible power models are in use.
- **The 64-frame median "ensures ≥ 33 clean frames"** against a 32-frame glitch — 64 − 32 = 32,
  exactly the case with no clean majority.
- **v1.63's "the 8 minutes that happened to be running"** cannot exist on that entry's own
  timeline, which has logging stopping before the settle began.
- **The ≈ 4.67 V noise-zone edge is called "consistent with" the 07-13 mapping**, which recorded
  4.6625 V as clean; and that mapping's stated ~4.45 V lower bound never accounts for its own
  4.475 V step.

**Known issue, not fixed** (docs-only pass): `src/pimd_delaycal.py` sets the fine-step default to
**100 ns**, which is not a multiple of 8 and is unreachable by the spinbox's own 8 ns steps —
reintroducing, as a default, the off-grid condition v1.26 existed to remove. Left for a
deliberate code pass.

**Needs bench data, flagged in DESIGN rather than resolved:** §3's filtered ±200 µV against §7's
450 µV floor (both pre-enclosure); R9's "≈ 9.6 mA at the +50 V damped peak" against the measured
+135 V RX flyback, which would imply ~28 mA; and the filtered path's 0.46 s group delay against
0.5 s settling. (2026-07-31)

---

## Archive — consolidated 2026-07-30

### DESIGN.md — 1.11 — consolidation pass (§18)

Human-directed, read-only rule suspended per §18. Consolidates the 73 entries above the
previous marker (241 headings total across the file, all preserved byte-for-byte — only the
marker moved). Net state determined per file first; **the CHANGELOG's two contradicting
warm-up entries were resolved, not replayed.**

**The correction that drove the pass.** The 2026-07-29 entry titled *"the warm-up transient is
two threshold columns, and it is soak time, not pack state"* is overturned by the 2026-07-30
pack-voltage entry. Its **column-localisation result is carried** (reconfirmed at r = 0.9960);
its **causal attribution is not**, and neither are its four supporting arguments or its claim
that the coherence result contradicted §17.10 — that claim was withdrawn before it ever reached
DESIGN.md, so there was nothing to retract, only something not to import.

**Sections changed.** Header → Doc-rev 1.11, fw v4.27, classviz v1.66, delaycal v1.29,
features v11, target_check v4, corpus_check v1.8, profile `cal_63_air_bat_v3`. §1 status
rewritten (lock landed, registry v3, pack state of charge is now an operating variable). §3 —
SoC supply note scoped, Mode 2 warm-up flagged as not holding for this profile on battery, new
time-to-usable-data bullet by criterion. §8 — fw v4.27 emit-block counters and the
`ticks_ms`-not-`ticks_us` reason. §9 — `B` documented at all (it had existed undocumented since
v4.11) plus its two new fields, flagged as an additive wire-format extension with no parser in
`src/`. §10 — new operating-profile section for v3, v2 demoted to superseded, and **both items
the 1.10 pass deferred are cashed in**: the state-of-charge window is now a stated term of the
profile contract, and the threshold-geometry change makes the §13 portability question live.
§12 — the state-of-charge claim scoped to its measured interval, ≈ 23.5 V data-quality ceiling
added beside the 21.0 V regulation floor as a *different kind* of limit, pack capacity and
idle-drain figures, measured 0.29 V IR drop. §13 — ladder move, plus the general observation
that a fixed threshold ladder samples a decay whose scale moves with the pack. §14.1
reattributed (discharge, not soak — thermal drift stays open and is the smaller effect), §14.3
partially answered on battery, §14.7 **resolved in mechanism** with follow-ups now required to
state a pack voltage, and two new open problems: §14.10 host-blocks-MCU, §14.11 the
`(9 µs, 4.9 V)` corner and why a *static* cell exclusion cannot work. §15 — five tool rows
rewritten, registry v3 promoted with v1 kept as the registry the 2026-07-23 corpus must be read
against, `utilities/` inventoried with both tools, new `src/data/sessions/` row, and
`NEXT_SESSION_soak_vs_voltage.md` cited for its pre-registered predictions. §16 — stale
selftest corpus path corrected, registry and corpus check invocations added. §17 banner scoped;
§17.10 scoped to its 0.55 V interval with its voltage-domain inference re-supported; new
§17.11 (v3 lock, 0.3 mV convergence, thermal-convergence criterion), §17.12 (the corner, two
supply nulls, the retracted floor-doubling reading), §17.13 (the pack-voltage result).

**Dropped:** only §10's "recalibration in progress, nothing locked" block, superseded by the
lock; its two forward-looking warnings are cashed in rather than lost. No §3 or §17.1–17.9
content removed. Not carried into DESIGN.md, as changelog-only: the two corpus data repairs,
the eight `repeat_idx` renumberings, per-version verification detail, and the `[FILL:]` markers
— except §14.7's, which the pack-voltage result answers.

**Flagged, not fixed (source edits, out of scope for a doc pass).** `pimd_classviz.py`'s header
title line reads **v1.63** against `APP_VERSION = '1.66'` — the same desync features v9 fixed
for itself; DESIGN records v1.66 as the net version. And **USAGE.md v1.24/v1.25/v1.26 have no
entries in this file**, existing only in USAGE.md's own inline changelog, which puts three
versions of history outside the single source of detailed history. (2026-07-30)

---

### findings — pack A capacity and drain rates: the clean window is 4.5 h of streaming

*Cycle-derived from the `# pack_v:` lines in the seven 2026-07-30 dumps 08:28 → 20:46 — pack A,
one complete discharge, 33 readings of which 21 settled-under-load · analysed with
`utilities/pack_discharge/packv.py` v3*

**Supporting the entry below, not disputing it.** The `findings — the 3.80/4.40 V transient is
PACK VOLTAGE, not soak time` entry establishes the mechanism and the 21.5 – 23.3 V operating
window; nothing here touches either. What it adds is a **denominator**. That entry's numbers are
intervals — "the top ~2 h of pack capacity", "a 1.5–2 h wait" — and an interval cannot say what
fraction of a pack it is, or how long the window it recommends actually lasts.

**Independent agreement first, because the extrapolations are only worth as much as it.** Fitting
a constant-current discharge to the `pack_v` track says pack A took **110 min** to fall 24.55 →
23.28 V. That entry measured **114 min** by an unrelated route — `soakvolt.py`, provenance-graded
notes and interpolation. The same fit puts the unusable top of the pack at **1.78 h** against its
"1.5–2 h". Two methods sharing no code and no metric, agreeing to 3.5%.

**Pack A, full to empty under continuous streaming load: 620 streaming-minutes (10.33 h.)**
Residual RMS 46 mV; leave-one-out over the 21 settled readings holds the runtime within
613–624 min, a 1.7% spread. From which:

| | streaming hours | share of the pack |
|---|---|---|
| full → 23.3 V — unusable, above the data-quality ceiling | 1.78 h | 17% |
| **23.3 → 21.5 V — the clean window** | **4.55 h** | **44%** |
| 21.5 V → empty — below the window | 4.0 h | 39% |

**4.55 h is the session-planning number.** The operating window was specified in volts, which
says where to run but not how long a session can last inside it. Just under half the pack is
usable for profiling, and it is the middle half.

**Idle drain is 0.019 V/h against 0.28–0.34 V/h streaming — roughly 15×.** Measured across the
1.6 h load-off gap between the 15:36 and 17:11 readings (22.25 → 22.22 V). This turns "do not
start a profiling session on a freshly-charged pack" into something actionable: **a fresh pack
cannot be idled down into the window.** At 0.019 V/h the top 1.4 V would take three days. It has
to be *streamed* off, so the 1.78 h is unavoidable bench time rather than a wait that can be
scheduled around — and it is 17% of the pack spent reaching a usable state.

**Capacity, inferred and labelled as such.** 10.33 h at DESIGN §17.1's measured ~0.5 A average
gives **≈5.2 Ah**, which is the nominal capacity of a 6S2P pack of the ICR18650-26C cells — so
pack A is behaving at about its rated capacity despite being built from recovered laptop cells.
This *infers* construction from behaviour and does not establish it; it bears on argument 1 of the
entry below (packs A and B differing in internal resistance) without resolving it.

**One caution on the voltage axis of that entry's central table, offered as a flag rather than a
correction.** Its `07-30 15:01 first` row reads **22.85 V, grade `typed`** — a genuine fresh DMM
reading, correctly graded, taken 20 s after load came on following a 94-minute rest. But a pack
that has just come off a rest has not finished settling: the same session reads 22.66 V at
3.4 min and 22.34 V at 25 min, and steady discharge over that first 3.4 min accounts for only
0.019 V of the 0.19 V drop. **~0.17 V of it is load-settling**, so that row sits about 0.17 V
above the settled loaded voltage its correlation is against. Corrected it reads ≈22.67 V, which
is still inside the 22.5 – 24.0 V transition band, so **the threshold-crossing structure and
every conclusion drawn from it are unaffected** — the pre-registered 15:01 prediction test likewise.
It is worth recording only because that is one of two `typed` anchors in the table and the effect
is systematic in one direction: any reading taken within a few minutes of load-on after a rest
reads high. `soakvolt.py` already excludes *unloaded* readings and refuses to interpolate across a
rest; this is the narrower case of a loaded-but-not-yet-settled one. `packv.py` drops anything
within 5 min of load-on for exactly this reason.

**Limits.** Pack A only, one cycle, and the terminal knee below 21.08 V is extrapolated rather
than observed. `x = 0` assumes a full pack when the 08:28 session opened — no voltage was logged
in that dump at all, so the assumption rests on the operator's handwritten 24.55 V note and on
the 110-vs-114-min agreement. And it bears **not at all** on the +15 V rail under scope during a
TX pulse, which that entry correctly names as the highest-value measurement outstanding: this is
a DMM-on-terminals result and cannot see pulse-instant sag.

**For the next §18 consolidation pass**, one amendment only:

| section | amendment |
|---|---|
| **§12 Power system** | Add pack-A capacity beside the 21.0 V floor and the new ≈23.5 V ceiling: **620 streaming-min (10.3 h) full to empty at the §17.1 ~0.5 A average, ≈5.2 Ah**, of which the clean 23.3–21.5 V window is **4.55 h (44%)** and the unusable top is **1.78 h (17%)**. Record that **idle drain is ~15× below streaming drain (0.019 vs 0.28–0.34 V/h)**, so the pack cannot be idled into the window. |

(2026-07-30)

---

### repo — `/utilities/`: local analysis tools, and how their history is kept

Analysis tools that are not part of the PIMD toolset live under `/utilities/`, one directory each.
They are ordinary tools by convention — `TOOL_VERSION`, a terse `# History:` lineage in the
header, read-only with respect to the repo — and their history is recorded **here, in this file**,
under a `### utilities/<name>/ — v<N>` heading like any other.

There was briefly a separate untracked `CHANGELOG.local.md` for them. It is **gone**: a second
change log meant two places to look, two formats to keep in step, and a standing risk that the
detail behind a tracked finding lived in a file no clone would ever have. `CHANGELOG.md` is the
single source of detailed history, and these tools are inside it.

The rule that made the split untenable is worth stating, because it is what caught the problem:
**a utility cited from `CHANGELOG.md` has to be tracked.** The 2026-07-30 pack-voltage finding
names `soakvolt.py` as the tool behind its central result; had that file stayed excluded from git,
the project's headline finding would not have been reproducible from a clone. Anything cited gets
tracked. (2026-07-30)

---

### utilities/soak_vs_voltage/ — v1 — separate pack voltage from soak time

`soakvolt.py` v1 reads every classviz session dump for the campaign and separates the two
variables that every session before 2026-07-30 had confounded in the same direction. Emits
JSON; `soakvolt.json` is the 2026-07-30 run over all nine dumps (435k frames).

**Why it exists.** The 2026-07-30 warm-up findings entry attributed the 3.80/4.40 V threshold
transient to soak time, from four within-session arguments. Within one session soak and pack
voltage are perfectly confounded (ρ 0.80–0.91 against either, identical magnitude), so no
within-session correlation could have settled it — a tool that works across sessions and grades
its own inputs was the only way. **It overturned the conclusion:** see the
`### findings — the 3.80/4.40 V transient is PACK VOLTAGE, not soak time` entry in
the `findings` entry above, which is where the result lives; this entry records only the tool.

**What it does that a one-off script would not have.**

- **Window hygiene as a span test, not a masked clock range.** A 50-frame window is one
  measurement only if those frames arrived a nominal period apart. The test is
  `WINDOW_SPAN_TOLERANCE × nominal` on the firmware clock, mirroring
  `pimd_classviz._window_frames`, so it caught the 2026-07-29 host stall (34 windows rejected)
  without being told about it — and would catch an unknown one. A hardcoded 23:03–23:50 mask
  would have passed the first test and failed the real job.
- **Three provenance grades on every pack-voltage figure**, never mixed silently: `typed`
  (`age_s` ≤ 30 s), `held` (a large `age_s`, or the pre-v1.66 two-field form), `note`
  (handwritten DMM readings, the only record for the two oldest dumps), degrading to
  `interp`/`extrap`. The `age_s` correction — true measurement time is `logged − age_s` — is
  inherited from `pack_discharge/packv.py`, where it was established, rather than re-derived.
  A header `pack_v` with `age_s=unknown` is **dropped**: it is a settings restore, not a reading.
- **Loaded readings only.** Loaded and unloaded differ 0.4–0.5 V, so mixing them manufactures a
  step at every session boundary. Interpolation is never carried across a rest, because a rested
  pack rebounds (22.56 → 22.85 with no charging) — gaps are held flat and reported as `extrap`.
- **Startup transient removed by test, not by duration.** The 08:28 dump reads 14–16 mV on all
  nine columns in its opening minutes — a global stream-start event. Detected as
  "every column above 5× its own session floor", so it cannot silently eat real warm-up.
- **Operating point per band**, which is what identifies the mechanism: a supply change moves all
  seven bands the same way, a thermal change moves light and heavy bands in opposite directions.

Uses `pimd_features` v11's new `SessionData.fw_seconds` — the firmware clock. v11 exists because
this analysis needed it and `parse_session_file()` had been discarding it; the alternative was
hand-rolling a reader, which the handover brief explicitly ruled out. (2026-07-30)

---

### utilities/pack_discharge/ — v3 — the fitted offset is not internal resistance

Both files v3. Pure relabelling — the fitted values are bit-identical, verified against a
recorded baseline (T 619.7870428168494, RMSE 0.04560715568551285, LOO spread 1.7327994684664263
before and after). What changed is what the number is *called* and what it is claimed to be.
(2026-07-30)

**The error.** v1 and v2 named the second fitted parameter `sag` and reported it everywhere —
JSON, README, page prose — as the pack's IR drop under load: 159 mV/cell, ~0.95 V at the pack.
The page went further and asserted "a full pack reads 0.93 V lower with the coil driving than it
does at rest", which is a physical claim about the hardware. It is wrong by about 3×. The
operator had already measured it directly: pack B at **25.04 V no-load / 24.96 MCU-only /
24.75 V running — 0.29 V**, recorded in the tracked 2026-07-30 findings entry. Caught only by
reading `CHANGELOG.md` properly while checking whether this session had anything to contribute.

**What the parameter actually is.** A curve-alignment constant. The model applies a nominal
ICR18650-26C OCV shape it cannot deform, so the offset absorbs whatever mismatch exists between
that published shape and these cells — and the mismatch is evidently around 0.66 V of the
0.95 V. Renamed to `offset` in code and `curve_offset_v_per_cell` in the JSON, with both the
module docstring and the page stating the 0.29 V comparison outright rather than leaving the
misreading available.

**What this costs the result, and what it doesn't.** The runtime is unaffected and still stands:
it is cross-checked two ways that do not depend on the curve's absolute placement — leave-one-out
(1.7% over 21 readings), and independent agreement with the operator's own interval measurement
(110 min against their 114 min for pack A over 24.55 → 23.28 V). What is now explicitly *not*
trustworthy is the shape: the voltage axis is an alignment of a nominal curve, not a measured
one, so **trust the runtime the fit implies, not the curve it draws.** Stated in the README and
on the page rather than held here.

**Worth generalising.** A two-parameter fit will give a physically-named parameter a confident
value whether or not that name is right, and nothing in the residual complains — RMSE was 46 mV
throughout, which looked like a good fit and was, of the wrong thing. The check that caught it
was an independent direct measurement of the same quantity, not any internal diagnostic. Where a
fitted parameter carries a physical name, it needs an external number to be held against before
it is reported as that quantity.

---

### utilities/pack_discharge/ — v2 — refuse to fit across a recharge

`packv.py` v2 detects charge cycles and analyses one at a time; `build_page.py` v2
renders the resulting caveats as a banner above the numbers. (2026-07-30)

**Found by being caught out.** The pack was swapped at 20:52 — 21.08 V out, 24.94 V
in — while v1 was still being verified. v1 fitted straight across the step and
reported a confident **T = 1738 min** and "4.81 h to the 21.0 V floor". Both were
nonsense: a 3 V rise reads as negative discharge. The only outward sign was the
residual, which blew from ~50 mV to **1113 mV** — a number v1 computed, put in its
JSON, and never surfaced. Silent wrongness is the worst failure mode available to a
tool like this, and v1 had it.

**Cycle detection.** Any rise beyond `--recharge-v` (default 0.8 V) between
consecutive datable readings opens a new cycle. The threshold has to clear rest
recovery, which is real and was measured at **+0.29 V** across a 2 h load-off gap
earlier the same day; a pack swap is an order of magnitude larger, so the gap
between the two is comfortable. Streaming time is re-zeroed per cycle, which also
makes the `x = 0` assumption explicit per pack rather than per day.

**Default is the latest cycle**, on the grounds that the live question is almost
always about the pack currently on the bench. `--cycle 0` (or any index) reaches an
earlier one; `--cycle all` restores the old across-everything behaviour for
anyone who wants to see the step.

**Fit-quality warnings**, emitted to stderr and rendered on the page rather than
left in the JSON: more than one cycle present, fitted span under 0.5 V, fewer than
5 settled readings, or residual RMS over 200 mV. The fresh pack trips three of the
four — 3 readings across 0.45 V, all near full — and the page now says so instead
of printing an authoritative 2.9 h runtime. That is the intended behaviour: the
tool should be least confident exactly when it has least to go on.

**Cycle 0 re-fitted cleanly** once separated: **T = 620 min (10.33 h)**, sag
159 mV/cell, residual RMS 46 mV, leave-one-out spread 1.7% over 21 settled
readings — better constrained than the mid-afternoon figures, because the discharge
ran far enough down to put real curvature in the data.

**Accidental validation.** At 20:20 the model put the 21.0 V crossing at roughly
20:47. The pack came off at 20:52 reading 21.08 V. Nobody planned that as a test,
and one coincidence is not a validation series, but the prediction was right to
within a few minutes on the one occasion it could be checked.

---

### utilities/pack_discharge/ — v1 — pack discharge rate from session dumps

Derives the 6S pack's discharge rate, state of charge, and remaining streaming
runway from the `# pack_v:` comment lines a classviz session dump already carries.
Two files: `packv.py` v1 parses and fits, emitting JSON; `build_page.py` v1
renders that JSON to a self-contained HTML page. Written 2026-07-30 against that
day's seven sessions (30 readings, 18 usable).

**Why it exists.** Pack voltage is not telemetry — there is no voltage field in the
serial protocol (DESIGN §9) and no sensing hardware (DESIGN §12, and the v1.66
CHANGELOG entry establishes there is no divider and no thermistor on the 6.04
schematic). The only record of pack state is what the operator typed and pressed
`Log V` on. That record turned out to be rich enough to answer "how long until the
21.0 V working floor", which is an operational question that came up mid-session
and had no tool.

**What the fit does.** The classviz profile loop draws a fixed duty, so current is
constant, so charge drains linearly in *streaming* time — state of charge is a
straight line by construction, and that is the x axis. Two free parameters are
fitted to the readings themselves rather than taken from a datasheet: `T`, the
streaming minutes from full to the empty-cell voltage, and `sag`, a constant IR
drop per cell. On 2026-07-30 that gave **T ≈ 614 min (10.2 h)** and **156 mV/cell**
of sag, residual RMS ≈ 50 mV, over 18 settled readings spanning 23.04 → 21.23 V.

**Three corrections the raw log requires**, each of which changes the answer rather
than merely tightening it:

- `age_s` must be applied. A dump's *header* `# pack_v:` line is the spinbox value
  restored at session open, not a fresh reading — the 17:10 session opened with
  `22.25, age_s=5659`, measured 95 min before that session existed. Applying it
  recovers a genuine reading and collapses phantom duplicates. Header lines with no
  `age_s` (pre-v1.66 two-field form, or `age_s=unknown`) cannot be dated and are
  dropped. This is the v1.66/features-v10 `age_s` work being cashed in.
- The axis must be accumulated streaming minutes, not wall clock. Idle drain measured
  0.019 V/h against 0.276 V/h streaming, a ~14× ratio; wall clock would flatten the
  slope through every gap between sessions. Per-session streaming time comes from
  each dump's first→last data-row span, because `# soak:` lines exist only in recent
  dumps and one reported `streamed_s=0`.
- Readings within 5 min of load-on are rested voltage, not settled-under-load, and
  sit high — 15:01:45 read 22.85 V, *above* 12:38's 22.56 V, after a 2 h rest.
  Excluded from the fit, drawn hollow.

**The methodological trap worth recording.** The first version of this claimed
split-half cross-validation as evidence: fitting the newest session alone gave
618.6 min against 608.2 min from the earlier ones, "agreeing to 1.7%". That was
**coincidence, not robustness**, and it broke as soon as more readings arrived —
the same split then reported a 52% spread. Cause: the newest session's readings
span under 1 V, all of it plateau, and across so little voltage `T` and `sag` trade
off freely, so that subset returns T ≈ 1030 min with a compensating +307 mV/cell
sag. It has no leverage on `T` at all. Splitting by session correlates with voltage
range, so it was never a valid partition. Replaced with **leave-one-out** (refit
dropping each reading in turn), which held T within 614–627 min, a 2.1% spread. The
subset fits are still reported, now with each subset's voltage span alongside, as a
conditioning diagnostic rather than as validation. Practical consequence, and the
most useful thing this exercise produced: **constraining the runtime needs
curvature, not more points on the flat** — readings taken early in a charge cycle
are worth far more than readings near the floor.

**Standing limitation.** `x = 0` assumes the pack was full when the day's first
session began. Nothing in the data confirms it — on 2026-07-30 no voltage was
logged before 11:29, roughly 3 h into the day's streaming. If the pack started down,
`T` is not full-pack capacity but a scaled equivalent and every projection shifts
with it. The terminal knee is likewise extrapolated, not observed. Neither is
fixable by better fitting; both are fixed by taking a reading at pack-swap time.

---

### findings — the 3.80/4.40 V transient is PACK VOLTAGE, not soak time. The operator was right.

*Nine session dumps, 2026-07-29 19:17 → 2026-07-30 21:14, **332 957 frames**, packs A and B ·
`cal_63_air_bat_v3` / sha `4a2352d2` · fw 4.26 · 6S battery · free air ·
analysed with `pimd_features` v11 (firmware clock) and `utilities/soak_vs_voltage/soakvolt.py` v1*

**Metric validated against the entry it overturns before anything else was concluded.** The
published 2026-07-29 column table reproduces at **r = 0.9960 across all 54 cells** — 3.80 V at
19:29 reads 1441 µV here against 1449 published, 4.40 V 514 against 522 — with a systematic
+8.9 % median bias on the already-quiet columns, attributable to window placement. Same method,
same numbers: **the disagreement in this entry is about causation, not measurement.**

`session_20260730_205236.csv` was **still being written** while this ran (it grew 10k → 25k frames
during the analysis). Its "first 5 min" slice is stable; its last slice is whatever had landed by
21:14. Treated as a partial session throughout.

**This closes out classviz v1.66's "Not yet run on the bench."** That entry's `# pack_v: … age_s=`
and `# soak:` lines are the instrumentation this result rests on, and they are now **bench-verified
in the field over five sessions**: 26 `pack_v` readings across three provenance grades and 217
`soak` lines, and `streamed_s` proved to be the quantity that turned an accidental pack swap into
a controlled experiment. Both line types read back exactly as specified. One behaviour the entry
did not state, found here and now recorded: **`streamed_s` banks within a classviz process, not
across restarts** — see the nulls below.

**This overturns the central claim of the 2026-07-30 entry below**
(*"the warm-up transient is two threshold columns, and it is soak time, not pack state"*). Its
column-localisation result stands and is reconfirmed. Its **causal attribution is wrong.** A
reader must not have to infer that: the title claim of that entry is false, and §4 of it —
the four arguments for soak — is answered argument by argument further down.

**Pre-registered predictions** were written before any data was touched
(`References/V3/NEXT_SESSION_soak_vs_voltage.md` §1), because the operator did not accept the
soak conclusion and re-arguing it was not going to settle it. For the 15:01 cold-start-on-a-flat-
pack session: soak predicted the 3.80 V column starts **bad, 1700–2100 µV**; voltage predicted it
starts **clean, 200–400 µV**. It read **742 µV** — 2.3× better than soak predicted, 1.9× worse
than voltage predicted. Reported as the mixture it is: **soak is falsified as the controlling
variable, voltage is substantially right, and soak survives as a real secondary effect.**

**The measurement that settles it, with soak held constant.** The new `# soak:` counters show
`streamed_s` running continuously from the 17:10 session into the 20:52 one (12652 → 12963 s,
`idle_before_s=366`). So the rig is at the **same thermal state, eleven minutes apart, 3.5 hours
into a continuous run**, and the *only* thing that changed is that the pack was swapped:

| | 20:41:27 | 20:52:37 | |
|---|---|---|---|
| effective soak | 12 652 s | 12 963 s | +311 s — unchanged for this purpose |
| pack (loaded) | **21.08 V** | **24.90 V** | pack A out, fresh pack B in |
| **3.80 V column** | **189 µV** | **2090 µV** | **11.1× worse** |
| 4.40 V column | 189 µV | 940 µV | 5.0× worse |
| grid mean | 3404.0 mV | 3565.7 mV | +161.7 mV |

A rig 3.5 h into a continuous run reading **worse than any cold start in the campaign** is not
something soak time can produce. The soak hypothesis predicts ~185 µV at that point; it is out
by an order of magnitude. No model is needed to read this pair.

**The full set, all nine dumps.** Detrended σ over 50-frame windows, averaged down each threshold
column, µV; first and last 5 min of each session; pack voltage loaded, provenance graded:

| session | pack V | grade | eff. soak | **3.80** | 4.40 | 4.20 | grid mV |
|---|---|---|---|---|---|---|---|
| 07-29 19:17 first | 24.33 | note | — | **1656** | 898 | 144 | 3556.8 |
| 07-29 00:37 last | 22.28 | interp | — | **197** | 192 | 190 | 3465.8 |
| 07-30 08:28 first | 24.55 | note | — | **1685** | 1026 | 311 | 3591.9 |
| 07-30 10:43 last | 23.27 | interp | — | **316** | 209 | 205 | 3492.0 |
| 07-30 11:28 first | 23.22 | held | — | **862** | 406 | 148 | 3512.2 |
| 07-30 15:01 first | 22.85 | **typed** | 0 (94 min idle) | **742** | 397 | 235 | 3496.6 |
| 07-30 15:36 last | 22.30 | interp | ~2 100 | **255** | 206 | 213 | 3470.2 |
| 07-30 17:10 first | 22.22 | interp | 0 (94 min idle) | **502** | 317 | 186 | 3475.8 |
| 07-30 20:41 last | 21.08 | extrap | 12 652 | **189** | 189 | **457** | 3404.0 |
| 07-30 20:52 first | 24.90 | **typed** | 12 963 | **2090** | 940 | 158 | 3565.7 |
| 07-30 21:14 last | 24.08 | extrap | 16 297 | **1031** | 245 | 174 | 3521.1 |

Ordered by voltage instead of by time, the structure is a **threshold crossing, not a linear
trend**: above 24.0 V the 3.80 V column is *always* bad (1031–2090 µV) whatever the soak; below
22.5 V it is *always* acceptable (189–502 µV); 22.5–24.0 V is the transition, and **that is where
soak is visible as the second variable** — at matched voltage, 23.27 V soaked 135 min reads
**316 µV** against 23.22 V freshly started at **862 µV**, and 22.28 V soaked 5 h reads **197 µV**
against 22.22 V after a 94-min idle at **502 µV**. So soak buys ~2.5–3× inside the transition
band; voltage spans ~11× across its range. **Both are real. Voltage dominates.**

**Mechanism: pack voltage reaches the operating point, and the noise zone rides it.**
Grid mean against pack voltage over all 17 slices, both packs: **43.3 mV/V, r = 0.962**; pack A
alone (which controls for pack-to-pack internal resistance): **50.9 mV/V, r = 0.972**.

The band structure is what identifies the mechanism, and the discriminator is **not** the
correlation with pulse width — both candidate mechanisms have one. It is **whether the shift
changes sign across bands**:

| | 9 | 13.44 | 20 | 30 | 45 | 67.2 | 100 | r vs log pw | sign |
|---|---|---|---|---|---|---|---|---|---|
| **pack 21.08 → 24.90 V** (mV) | +153 | +152 | +155 | +158 | +162 | +164 | +189 | +0.845 | **one sign, all bands** |
| **07-29 post-stall step** (mV) | −8.3 | −4.1 | +0.2 | +4.8 | +10.1 | +15.4 | +23.8 | +0.993 | **changes sign** |

A supply change scales the whole decay, so every band moves the same way (+152…+189 mV, σ 7.3 %
of the mean). A thermal change re-times the drive, so light and heavy bands move in *opposite*
directions — the §14.1/§17.10 fingerprint, and exactly what the post-stall step does. (Sign
convention: those sections quote r = −0.95 in *delay* ns; measured here as *voltage at a fixed
delay* the sign inverts, so +0.99 here is the same fingerprint, not a contradiction.)

So **DESIGN §12's "state of charge does not reach the operating point within the regulated window,
measured down to 23.05 V" is wrong outside the range it was measured over.** §17.10 established
it across 23.60 → 23.05 V — 0.55 V, where this slope predicts only ~25 mV, comfortably buried
under the thermal drift that measurement was actually reading. Over the 21.0 → 25.0 V now
available it is a 160 mV effect and unmissable. §17.10 is not wrong about its own interval; it
does not generalise, and the profile notes' inference that the 4.40/3.80 elevation was
"supply-borne" turns out to have been **right all along**.

This also **resolves §14.7 rather than deepening it.** That section records, unresolved, that the
zone "tracks the operating point, not a fixed voltage", and that noisy–clean–noisy across
4.40/4.20/3.80 defeats any single contiguous zone. Both follow if the noisy region sits at a fixed
place on the **decay waveform** while pack voltage scales the decay: which threshold columns
intersect it then moves with the pack. Direct evidence — at 21.08 V the trouble has *left*
3.80/4.40 (189/189 µV) and appears at **4.20 V (457 µV)** and 4.75 V (295 µV), which is the
operator's own bench observation that "noise just changes area". The per-band pattern is
zone-like rather than uniform: on the fresh pack the 3.80 V degradation peaks in the middle bands
(20–45 µs, 19×) and is weakest at 9 µs (2.7×) and 100 µs (8.0×), while the 4.40 V column degrades
monotonically with pulse width (0.9× at 9 µs → 8.0× at 67.2 µs). Each band has a different decay
shape, so the zone lands on a different threshold in each.

**Answering the four arguments of the entry below, in its own terms.**

1. *"Matched on both variables at once"* (24.05 V and ~28 min in both sessions; pack A 1834 µV vs
   pack B 1036 µV, 1.8× apart) — **not explained by this analysis, and not claimed to be.** The
   likely reason is that DMM terminal voltage is not the pulse-instant rail: the two packs differ
   in internal resistance, and the operator measured pack B at 25.04 no-load / 24.96 MCU-only /
   24.75 running. Nothing in the logs can separate a pack's IR from its terminal voltage. This is
   precisely DESIGN §12's unmeasured quantity, and it stays open.
2. *"One voltage trajectory, opposite outcomes"* (24.37 → 23.56 V moved `(100 µs, 3.8 V)`
   306 → 2284 µV while `(13.44 µs, 3.8 V)` went 1737 → 264 µV) — **this is evidence for a moving
   zone, not against a voltage mechanism.** A uniform level shift cannot move two cells in
   opposite directions; a zone sweeping across the threshold ladder does exactly that, one cell
   entering as another leaves. The entry read a zone signature as a refutation of the voltage
   domain.
3. *"An unintended cooling experiment"* (the 47-min host stall) — **survives, and is genuinely
   thermal.** Reproduced here: frame delivery 413.8 → 34.5 → 413.7 frames/min across
   22:45 / 23:03–23:50 / 23:52, and the operating-point step **changes sign across bands**
   (−8.3 mV at 9 µs to +23.8 at 100 µs, r = +0.993), which supply cannot do. Magnitudes differ
   from the +10…+78 mV quoted there — a window-choice difference, not a disagreement about
   structure. A stall also unloads the pack and lets it rebound, so the two causes are confounded
   in that window; the sign change is what discriminates, and it points thermal. **The thermal
   effect is real. It is the smaller of the two.**
4. *"Soaked, with the pack still draining"* (22.95 → 22.26 V, 3.80 V held at 210 µV, ρ = −0.02) —
   **consistent, and it is the key to why a careful analysis went wrong.** Below ~22.5 V the zone
   has already left the 3.80 V column, so there is no sensitivity left to detect. The effect is
   **non-monotonic in pack voltage**, and all four arguments above were drawn from 22.3–24.4 V —
   the flat part. Within-session correlation could not have found it, and neither could more of
   the same data.

**The "≈ 3 hour warm-up" is largely the pack discharging into the clean window.** Pack A fell
24.55 → 23.28 V in **114 min** and pack B 24.33 → 23.19 V in **135 min** — the same ~2 h the
entry below attributed to thermal soak, and the reason soak and voltage looked interchangeable.
The clearing order (4.40 V before 3.80 V; 100 µs last) needs no separate thermal explanation: it
is the zone sweeping down the ladder as the pack droops. At 21.08 V the 100 µs band still carries
the largest residual in the grid (232 µV at 3.80 V, 268 at 4.40 V), so it remains the long pole.

**Operating window — the actionable result. Run the pack at 21.5 – 23.3 V** (3.58–3.88 V/cell).

- **Ceiling ≈ 23.5 V is new** and is the constraint that was missing. Above 24.0 V the two
  highest-signal threshold columns are unusable regardless of how long the rig has run.
- **Floor ≈ 21.5 V.** Below it the trouble migrates to 4.20 V, 4.75 V and the 9 µs band — the
  operator tracked this live from 21.46 → 21.03 V. DESIGN §12's 21.0 V working floor needs no
  change; it was never the binding limit for data quality.
- **Do not start a profiling session on a freshly-charged pack.** That buys a 1.5–2 h wait which
  is discharge, not warm-up. The 15:01 and 17:10 sessions opened at 742 and 502 µV *because* the
  pack was already down. Cost of the window is the top ~2 h of pack capacity.
- **A delay recalibration does not fix this** — the operator's own reading, and it is correct. A
  cal at 24.5 V re-anchors the delays so the zone falls between thresholds, but the zone moves
  with the pack, so the fix expires as the pack drains. Noted for the record:
  `cal_63_air_bat_v3` was locked at 23.5 → 23.35 V, i.e. on the **upper edge** of the clean
  window; ~22.5 V would be more central if it is ever re-locked. **No profile change follows from
  this entry** — the ladder and `4a2352d2` stand.
- **Dynamic cell exclusion, deferred by decision, inherits one hard requirement:** a *static*
  threshold-column exclusion cannot work, because which cells are bad is a function of pack
  state. And the affected columns cannot simply be dropped — 3.80 and 2.40 V carry the *most*
  target signal in the grid (column mean |Δ| 4.23 and 4.88 mV against 1.83 at 4.9 V).

**Nulls and negative results, recorded so they are not re-derived.**

- **The corpus cross-check is a null. It cannot separate the two variables**, and that is a
  property of the corpus, not of the method. 166 captures, ρ(`splithalf_floor`, pack voltage)
  = **−0.182** over all placements — weak, and it mixes placements, so it is not a real test. The
  best-sampled placement (`Cu_pipe_01` @120 mm y) gives floor 4.622 → 1.842 → 1.564 → 1.956 as
  voltage falls 23.52 → 23.28 → 23.27 → 22.65 V, but every one of those captures sits inside a
  single morning session where voltage and soak were still marching together. Weakly suggestive
  that the one "noisy" capture is the one above the 23.5 V ceiling; n = 1 either side, so it is
  not evidence. The 2026-07-28 captures **cannot be assigned a pack voltage at all** — they
  predate every reading in the record and the model flat-extrapolates them, which is wrong and is
  labelled `extrap` rather than silently used.
- `pack_v` is populated on only 10 of 166 corpus captures, all `22.67`, one typed value held
  across a whole stretch.
- **`streamed_s` is banked per classviz process, not across restarts** — a caveat the handover
  does not state. It read 0 at 17:10 having already run 15:01→15:36 under a previous launch. That
  is *why* 17:10 and 20:52 form one continuous soak and hence a controlled experiment, so it is
  load-bearing rather than a footnote.
- The stall guard is a firmware-clock span test, not a masked clock range: it rejected **34
  windows** in the 07-29 dump on its own, and did not reproduce the phantom 23:28 "noise relapse"
  the first pass through that data produced.
- The 08:28 dump reads **14–16 mV on all nine columns** in its opening minutes — a global
  stream-start event, not a column effect. Excluded by an all-columns-elevated test rather than a
  hardcoded duration; averaging it in would invent a warm-up belonging to something else.

**RECOMMENDED FOR THE NEXT DESIGN.md §18 CONSOLIDATION PASS.** These are definitive bench
measurements over a 21.0 → 25.0 V span, and they contradict currently-documented ground truth.
`DESIGN.md` is not edited here (it is regenerated from this file by a human-run pass), so the
amendments are listed explicitly so the pass is mechanical:

| section | amendment |
|---|---|
| **§12 Power system** | *"State of charge does not reach the operating point … measured down to 23.05 V"* — **correct only over 23.60–23.05 V, false over 21–25 V**: 43–51 mV/V, one sign across all seven bands. Add the **≈ 23.5 V data-quality ceiling** beside the existing 21.0 V floor, and note the two are different kinds of limit. |
| **§17.10** | Scope the supply-regulation result to its measured 0.55 V interval. Its inference that a threshold-tracking fault localises to the voltage domain is **re-supported**, and this entry withdraws the previous entry's claim that the coherence result contradicted it — independent per-cell wander is compatible with a shared operating-point shift that merely *positions* each cell on the decay. |
| **§14.7** | *"The zone tracks the operating point, not a fixed voltage"* — **confirmed, no longer unresolved.** The noisy–clean–noisy puzzle is explained by a zone fixed on the decay waveform while the operating point scales with the pack. Both listed follow-ups (fine threshold sweep, front-end scope) should now be specified **at a stated pack voltage**, or they will not reproduce. |
| **§14.1 / §3** | The "≈ 3 h warm-up" is largely **pack discharge into the clean window**, not thermal soak. §3's "Mode 2 warm-up ≈ 5 min" remains wrong for this profile, but for a different reason than the entry below gave. Thermal drift remains a genuine open problem — it is just not what the 3.80/4.40 V columns were showing. |
| **§10 / profile notes** | Record that `cal_63_air_bat_v3` was locked at 23.5 → 23.35 V, on the upper edge of the clean window. Its notes' "supply-borne" attribution for the 4.40/3.80 elevation is **vindicated**. |
| **§15** | `pimd_features` v11 — firmware clock exposed; `measure_frame_rate_hz()` fixed. |

**The next physical step, and it is now the highest-value measurement on the project:** the
**+15 V rail under scope during a TX pulse, fresh pack vs near-flat** (DESIGN §12, never taken).
This analysis infers a supply mechanism from its band signature; that capture would observe it
directly, and it is the only way to settle argument 1 above. There is no voltage-sense and no
temperature-sense hardware on the board (6.04 schematic, GP26–29 unconnected), so **no amount of
logging substitutes for it** — the entire separation achieved here rests on band *geometry*,
because the two channels that would have shown it outright do not exist. Second priority: repeat
the §17.7 fine threshold sweep at two stated pack voltages (say 24.5 and 22.0 V), which would map
the zone's position on the decay directly and is the measurement that would turn this inference
into a model. (2026-07-30)

---

### src/pimd_features.py — v11 — firmware clock exposed; FIX frame rate measured on arrival time

Both changes were forced by the soak-vs-voltage analysis above, which could not be done correctly
without them.

**`SessionData.fw_seconds` (new).** `parse_session_file()` had always read column 1
(`firmware_time_ms`) and then **discarded it** — only `t_seconds`, from PC arrival timestamps,
reached the caller. So the one clock that ticks once per frame was parsed and thrown away, and any
offline analysis either used arrival time without noticing or hand-rolled its own reader. Both
have now happened in this project. Exposed as elapsed seconds zeroed at the first frame, so it
shares an origin with `t_seconds` and the two are directly comparable. `drop_flagged()` masks it
alongside the other `(n,)` arrays or they desynchronise.

`t_seconds` is **not** deprecated and its docstring now says what it is for: marks, `pack_v`
readings and `captured_at` are all stamped by the same PC clock, so aligning them needs arrival
time and nothing else. Every remaining use of it in the module was checked against that rule.

**FIX: `measure_frame_rate_hz()` was being fed the arrival clock.** `process_session()` passed
`sess.t_seconds`. USB delivery is burst-batched, so on these dumps the median arrival interval is
**0.0035 s (57 % under 10 ms)** against a uniform **0.1440 s** on the firmware clock — the
measured rate came out **73–290 Hz depending on the session, against a true 6.94 Hz**. Its
consumers `segment_from_marks()` and `detect_changepoints()` convert seconds → frames with it, so
every segmentation window on a session-dump build was sized wrong by up to 40×, and
`min_seg_frames` with it — which for the changepoint path means no segment ever qualifies.

**Why it hid for so long, worth recording:** the two clocks share the same *mean*. Only the median
is wrong, and `measure_frame_rate_hz` uses the median deliberately (it survives the stalls a mean
is destroyed by — same reasoning as `pimd_classviz._nominal_frame_s`). A mean-based rate would
have looked correct indefinitely. The existing >15 % deviation-from-nominal warning **was** firing
on every session dump and was the visible symptom; it is now silent, which is the confirmation.

**Blast radius: none on data.** Checked rather than assumed — all **10 458 rows / 166 captures**
of `gui_signatures_targets_v3_20260728_142316.csv` come from `gui_*` sessions written directly by
classviz (the primary corpus source since v1.32). **No corpus row on disk was ever built through
`process_session()`**, which is why a ~28× window-sizing error could sit in a shipped tool
unnoticed, and why no rebuild is required. No corpus-schema change; `CORPUS_HEADER_FIELDS`,
`pimd_corpus_check` and both corpora are untouched.

Verified: `fw_seconds` gives 6.94 Hz and a 0.1440 s median period on every one of the nine dumps,
with firmware span matching wall span to 0.1 min (no clock drift); `drop_flagged()` keeps all
three `(n,)` arrays equal length; the CLI runs end-to-end on a session dump with the frame-rate
warning now silent. (2026-07-30)

---

### src/pimd_classviz.py — v1.66 — session dump: pack_v carries age_s; new '# soak:' history lines

Both additions are **comments**, not columns: the operator's call, and the right one — a
timestamped comment can be interpolated and re-interpreted afterwards, where a per-frame column
would bloat every row with a value that changes a few times an hour.

Motivated by the warm-up conclusion **not** being accepted. The 2026-07-29/30 finding rests on
soak time rather than pack state, and the record as it stood could not be used to re-test that
independently: pack voltage existed only as sparse manual entries, and run history not at all.

Two facts that bound what is possible here, established before writing any code:

- **There is no voltage-sense and no temperature-sense hardware.** The 6.04 schematic has no
  divider, no thermistor, no NTC; GP26–29 (the RP2040's ADC pins) appear only as symbol pins.
  Pack voltage therefore cannot be sampled and stays operator-entered, and the one channel that
  would separate thermal from supply outright — temperature — does not exist to be logged.
- **Pack terminal voltage is not the decisive supply quantity anyway.** DESIGN §12 records that
  the +15 V rail under scope *during a TX pulse*, fresh pack vs near-flat, "has never been taken,
  and it is what would establish the real floor". A DMM cannot show pulse-instant sag. Nothing
  here substitutes for that measurement, and it should not be read as doing so.

**`# pack_v:` gains `age_s`.** `# pack_v: <iso>, 22.67, age_s=180`. Age is seconds since the
value was last **typed**, not since it was last logged — that is what says whether the number is
a fresh meter reading. Trigger is unchanged: `Log V` only, no automatic emission.

The trap worth recording: `_load_settings` restores the last session's voltage via `setValue()`,
which fires `valueChanged` exactly as an edit does. Left alone, every launch would have stamped a
confident `age_s=0` on a value nobody had looked at — and the field genuinely does come up
pre-filled (22.56 at the time of writing). So the restore clears the edit timestamp and such a
value reports `age_s=unknown`. The field is never omitted: an absent age would read as fresh,
which is the failure this exists to prevent.

**New `# soak:` lines.**
`# soak: <iso>, streamed_s=4210, stalled_s=12, idle_before_s=912, event=periodic`, written at
stream start, stream stop, every 60 s while streaming, and once in each dump's header (so a dump
opened mid-run by a profile change is still self-describing). ~300 lines over five hours against
114k data rows. `event=` is not in the original sketch and was added on the way: knowing whether
a line is the last one of a run matters when reading the file back.

- `streamed_s` — cumulative seconds the stream **actually ran**, banked across stop/start rather
  than taken as `now − session_start`. This is the quantity thermal state depends on; wall-clock
  elapsed is not, because a stopped stream cools the rig and nothing recorded that.
- `stalled_s` — cumulative seconds lost to firmware-time gaps, from the v1.64 detector (which
  now sums as well as keeping count and worst). Carried alongside rather than pre-subtracted so
  the arithmetic stays visible: **effective soak = `streamed_s − stalled_s`**. It matters at
  full scale — during the 2026-07-29 stall the stream was nominally running while the rig was
  cooling, so wall time streaming overstates soak by ~45 min on that session alone.
- `idle_before_s` — seconds since the previous **observed** stream stop, persisted via
  `last_stream_stop_iso` in settings so it survives an app restart.

**What `idle_before_s` is not**, written into the code and not just here: it is
classviz-observed idle, not guaranteed rig idle. If the app was closed, the board unplugged, or
the rig left powered with the stream merely stopped, it describes what this tool saw. Settings
are written on close, so a kill loses it and it reads `unknown`. A strong hint, not a
measurement — and it must not be read as one, because the entire point of logging it is to stop
inferring thermal state from a proxy without saying so.

Both line types reuse the `_append_mark` write+flush pattern; the 60 s tick rides the existing
1 Hz `_rate_timer` rather than adding a timer, as v1.64 did for the pack-voltage age label.
`_append_soak` additionally checks the handle is not closed — it is called from `start_stop`'s
two branches, where the dump is opened and closed a line or two away, making it the one append
site where an inconsistent state is a plausible ordering slip rather than an impossible one.

Verified offscreen, 34 checks, and the two that first failed were both worth having: the
harness had never exercised the real `start_stop` path (only `_session_start` directly), and one
assertion was defeated by `%.0f` rounding. Now covered: `age_s=unknown` / `=0` / `=300` for the
three provenance cases; the write→parse round trip for both line types through the real window;
`stalled_s` picking up an injected 12 s gap; `idle_before_s` reading back as the ~600 s gap on a
genuine `start_stop()` start; and `streamed_s` **not** advancing while stopped, which is the
whole point of it. Regression: all five pre-existing harnesses re-run clean. **Not yet run on
the bench.** (2026-07-30)

---

### src/pimd_features.py — v10 — pack_v gains age_s (old form still read); '# soak:' parsed

**Required, not optional.** v9's `_parse_pack_v_content` did `rest.partition(',')` and then
`float()` on everything after the first comma, so a three-field `22.67, age_s=180` would have
raised and the line would have been **silently dropped**. Growing the written format without
growing the parser would have made the new lines invisible — which is the failure mode this
project has been bitten by twice this week already.

`_parse_pack_v_content` now splits on commas and reads any trailing `k=v` pairs through a new
`_parse_kv_tail`. **The bare two-field form is still accepted, and that is load-bearing:** every
dump captured before today uses it, including `session_20260729_191643.csv` and
`session_20260730_082729.csv` — the pair the warm-up findings rest on. A malformed *age* yields
`age_s=None` rather than dropping an otherwise good voltage; a malformed timestamp or voltage
still drops the line, since a track with a bogus entry is worse than a shorter one.

`SessionData.pack_v` widens from `(datetime, volts)` to `(datetime, volts, age_s)`, with
`age_s=None` for the old form and for `unknown`. `pack_v_at()` — the only consumer in `src/`,
checked — follows. It deliberately does **not** weight or filter by age: silently discarding a
stale reading would hide it from whoever is deciding whether to trust it. The widening broke two
offscreen harnesses on tuple unpacking, which is the change being visible rather than a problem.

New `_parse_soak_content` and `SessionData.soak` as
`(datetime, streamed_s, stalled_s, idle_before_s, event)`. A line without `streamed_s` is
dropped — that is the field the line exists to carry. `idle_before_s=unknown` reads as `None`.

The module docstring now lists **every** `#` comment form the parser understands, with what each
means and what `idle_before_s` cannot tell you; the `pack_v` corpus-column entry notes that the
column carries no staleness information while the session track does.

**No corpus-schema change** — `CORPUS_HEADER_FIELDS`, `pimd_corpus_check` and both corpora on
disk are untouched, per the decision to leave the column stamping the field's current value.
(2026-07-30)

---

### findings — v3 corpus repaired twice: Ag_jewellery distance, and a ragged schema I caused

Data repair, recorded because it edits captured data (same footing as the 2026-07-28
repeat_idx renumbering). `src/data/corpora/` is gitignored, so git could not have restored
either file — a timestamped `.bak-` copy was taken before each write, and each write proved
itself against that copy rather than being trusted.

**1. `Ag_jewellery_01` was captured at 60 mm, recorded as 240 mm.** Bench report. All four
captures of that target — the last four in the file — carried `distance_mm=240`:

| capture | time | axis | repeat | amp mV |
|---|---|---|---|---|
| `..._113042_c95` | 12:33:05 | y | r1 | 19.36 |
| `..._113042_c96` | 12:34:06 | y | r2 | 14.76 |
| `..._113042_c97` | 12:35:13 | y | r3 | 20.17 |
| `..._113042_c98` | 12:36:09 | z | r1 | 4.47 |

Checked before writing, not assumed: exactly four such captures exist, all at 240, and they
are the last four in the file. **No `repeat_idx` renumbering was needed** — verified through
`pimd_corpus_check.placement_key()`, the moved placements `(Ag_jewellery_01, 60, y|z, …)` had
no existing captures, and the four stay distinct from each other. Result: 252 cells
(4 × 63), and only the `distance_mm` column differing from the backup.

**Amplitude cross-check, and it only half-supports the report — recorded that way.** Against
every other target in this corpus: `@60 mm` median amp 42.7 (n=26), `@120` 21.2, `@180` 9.9,
`@240` 5.0 (n=8). The three y captures at 14.8–20.2 mV sit far above the @240 distribution and
inside the @60 range, so for those the data agrees with the report. **`c98` at 4.47 mV sits
right on the @240 median** — it is the z orientation, presenting a much smaller loop, and it
flagged `noisy`, so the amplitude says nothing either way about that one. It was moved with the
other three on the strength of the bench report, which is the right authority for a placement
fact; noting it because a later reader comparing amplitudes would otherwise wonder.

**2. A ragged corpus, caused by classviz v1.64 — 10 captures.** More serious, and self-
inflicted. v1.64 was applied to the working checkout at ~11:28; classviz was restarted at
11:30:42 and captures `c89`–`c98` were saved with it. features v9 had added `pack_v` to
`CORPUS_HEADER_FIELDS`, and the corpus append path writes one value per *tool* field while
emitting a header row only for a new file — so 630 rows (10 × 63) were written **26 fields
wide under a 25-column header**. Fixed in classviz v1.65 below.

The orphaned 26th field held **22.67** on all 630 rows — a pack voltage the operator had
actually entered — so truncating would have discarded a real measurement. The file was instead
**migrated to the 26-column v9 schema**: `pack_v` appended to the header, the 5544 older rows
padded blank, the 630 keeping their value. Verified: header is now exactly
`CORPUS_HEADER_FIELDS`, all 6174 rows uniformly 26 wide, **not one cell in the original 25
columns changed**, and `pimd_corpus_check` reads 98 captures with `pack_v` on 10 and blank on
88 — which is what an optional column is for.

Two things this exposed, neither yet acted on:

- **`pack_v` in a corpus row is the field's current value, not a fresh reading.** All 10
  captures spanning 11:30–12:36 carry the same 22.67 V, because that is what the box said
  throughout. Over 66 minutes the pack genuinely moved (23.33 V at 10:19 the same morning).
  The 20-minute nag exists for this, but the column is only ever as good as the last time
  someone typed in it — unlike a session dump, where `pack_v_at()` interpolates a track.
  [FILL: should a stale pack_v (say >20 min old) be written blank rather than confidently
  wrong? A wrong voltage is worse than a missing one for the supply-vs-thermal question this
  column was added to answer.]
- **My verification of repair 1 did not notice the file was already ragged.** It compared
  backup against result row-by-row and asserted equal widths *between* them, which held —
  both were ragged. Comparing a file against its own backup cannot detect damage that predates
  the backup. Checking absolute row width against the header would have caught it, and that is
  now what the append harness does. (2026-07-30)

---

### src/pimd_classviz.py — v1.65 — FIX corpus append wrote the tool's columns, not the file's

Both signature-append paths built each CSV row as one value per
`pimd_features.CORPUS_HEADER_FIELDS` entry, and write a header row only when the file is new.
That was correct for as long as the field list never grew. features v9 added `pack_v`, and the
next Save into any corpus captured before it produced rows one value wider than the header
declares — silently, no error, a ragged CSV. It happened for real within two hours: 10 captures
in the live v3 corpus (see the findings entry above, which also records the data repair).

New `_corpus_fields_for_path()` reads the target file's own header and returns those columns;
both append sites now write `[row.get(k, '') for k in fields]` against it. A new file still
gets the full current header. Values are looked up with `.get`, so a header naming a column the
row has no value for (a joined or hand-edited corpus) writes blank instead of raising.

Writing the file's own columns is the right resolution rather than migrating the file on append
or refusing to append at all: `pack_v` is **optional by construction**
(`pimd_corpus_check.OPTIONAL_FIELDS`), so a corpus that has no such column simply does not
record it — the same outcome as a capture taken with no voltage entered. It also means this
class of bug cannot come back the next time a column is added.

Verified offscreen, 13 checks, using the real corpora as fixtures rather than synthetic ones:
appending a v1.65 capture to the clean 25-column v1 corpus leaves **every** row 25 wide
(4159 → 4222, the 63 new rows among them) and the file still loads; a new file gets all 26
columns and the voltage reads back; the pre-fix behaviour is reproduced on a copy to confirm
the failure mode was real (mixed 25/26); and the migrated v3 corpus now accepts all 26. The
harness asserts absolute row width against the header, which is the check whose absence let the
original damage through. (2026-07-30)

---

### findings — the warm-up transient is two threshold columns, and it is soak time, not pack state

*2026-07-29 19:17 → 00:37 (pack B, 114 246 frames) and 2026-07-30 08:28 → 10:25 (pack A,
cold start, 48 386 frames) · `cal_63_air_bat_v3` / sha `4a2352d2` · fw 4.26 · 6S battery ·
air, no profiling, both sessions captured whole by classviz v1.63's auto-logging*

The first analysis of these two dumps that was possible at all: v1.63 landed the day before
and auto-started both sessions, including the warm-up windows nobody would have pressed
Record for. 151k frames of continuous free-air stream, at a measured **6.9 Hz** sweep rate
(not the ~3.3 Hz the tooling comments had assumed — see the classviz v1.64 entry).

**The transient lives in the 3.80 V and 4.40 V threshold columns. The other seven are flat
from the first window to the last.** Detrended per-cell noise, µV, averaged down each
threshold column, full-rate frames only:

| clock | 4.90 | 4.80 | 4.75 | 4.40 | 4.20 | **3.80** | 2.40 | 1.50 | 0.50 | settle |
|---|---|---|---|---|---|---|---|---|---|---|
| 19:29 | 188 | 176 | 156 | **522** | 175 | **1449** | 160 | 111 | 50 | 0.529 |
| 20:09 | 197 | 176 | 156 | 220 | 172 | **722** | 158 | 111 | 51 | 0.333 |
| 20:49 | 205 | 178 | 161 | 179 | 174 | **362** | 158 | 111 | 52 | 0.255 |
| 21:29 | 203 | 175 | 157 | 174 | 174 | 231 | 153 | 108 | 50 | 0.234 |
| 22:09 | 204 | 178 | 158 | 178 | 176 | 194 | 156 | 109 | 50 | 0.234 |
| 22:48 | 201 | 180 | 162 | 178 | 174 | 188 | 153 | 108 | 48 | 0.227 |

4.40 V clears in ~70 min, 3.80 V in ~2h50m, and both land on the same ~185 µV floor as their
neighbours. **3.80 V is not a bad column** — it is where the warm-up shows up. During warm-up
those 14 cells of 63 contribute **68–75 %** of the whole `settle` figure; excluding them the
grid reads **0.141 mV cold, from minute one, unchanged for five hours**. So the rig is settled
on 49 of 63 cells within minutes and the wait is about two threshold columns.

**It is soak time, not pack voltage.** Four independent lines, because within one session
voltage and elapsed time are perfectly confounded (ρ = 0.80–0.91 against each, identical
magnitude — no within-session correlation can separate them):

1. **Matched on both variables at once.** At **24.05 V and ~28 min elapsed in both sessions**,
   pack A read **1834 µV** and pack B **1036 µV** — same voltage, same elapsed time, 1.8×
   apart. The only difference is that Tuesday's rig started partly warm. The same comparison
   holds at 23.85 V (1397 vs 672) and 23.69 V (1041 vs 473).
2. **One voltage trajectory, opposite outcomes.** As the pack fell 24.37 → 23.56 V, the
   `(100 µs, 3.8 V)` cell went **306 → 2284 µV (7.5× worse)** while `(13.44 µs, 3.8 V)` went
   **1737 → 264 µV (6.6× better)**. A voltage-domain mechanism cannot move two cells in
   opposite directions over the same volt; the split is by pulse energy, i.e. thermal load.
3. **An unintended cooling experiment.** The 47-minute host stall below did not merely lose
   frames — it *cooled the rig* (see that entry). Fully soaked and clean at 188 µV before it,
   the 3.80 V column returned to **290 µV** after, then decayed to 182 µV over the following
   30 min. Pack voltage was ~22.6 V throughout and falling — lower than anything measured on
   Wednesday, when the same column read 700–2000 µV.
4. **Soaked, with the pack still draining.** Across 22:15 → 00:37 (22.95 → 22.26 V) the 3.80 V
   column median held at 210 µV and the other seven gave ρ vs pack voltage = **−0.02**.

**This corrects §17.10.** The 4.40/3.80 elevation was recorded there as supply-borne, and
`cal_63_air_bat_v3`'s own profile notes bake that in ("that trial's 4.40/3.80 elevation was
supply-borne"). It is the warm-up transient. The v3 decision to keep both thresholds at their
original values was right for the wrong reason: they "came back clean under battery" because
the rig was soaked by the time they were looked at. **No profile change follows from this** —
the ladder and `4a2352d2` stand.

**Warm-up time, by criterion, because there is no single number.** An earlier pass through
this data said "~3 hours" flatly; that was the time for one column to approach its asymptote,
extrapolated, and it is not the time to usable data:

| criterion | from cold |
|---|---|
| 49 of 63 cells at the floor | minutes |
| a capture the quality gate accepts | ~2 h — `c85` at 85 min soak: floor 4.622, "noisy"; `c86` at 114 min: floor 1.842, "ok", inside the 2026-07-28 soaked spread (0.876–3.98) for the same placement |
| 4.40 V column at the floor | ~70 min |
| 3.80 V column at the floor | ~2h50m observed from a partly-warm start; ~3 h extrapolated from cold (single-exponential fit, floor pinned, R² 0.86; a two-exponential fit — an 8.5 min rise then a 52 min decay — gives R² 0.998 and ~3 h) |
| 100 µs band at the floor | **not reached in 90 min** — still ~2045 µV against a 190 µV floor. The long pole, and where long-τ discrimination lives (§14.6) |

DESIGN §3's "Mode 2 warm-up ≈ 5 min" does not hold for this profile on battery.

**The affected columns are the high-signal ones, so this cannot be waited out by ignoring
them.** Column mean |Δ| for `c86` (Cu_pipe_01 @120 mm): 4.9 V **1.83 mV**, 4.2 V 3.98,
**3.80 V 4.23**, **2.40 V 4.88**, 0.5 V 1.86. The 3.80 and 2.40 columns carry the *most*
target signal in the grid.

Distinct from the 2026-07-28 `(9 µs, 4.9 V)` corner, which is a **soaked** phenomenon with the
opposite temperature dependence: the 4.9 V column runs *cleanest cold* (88 µV at 7 min → 230 µV
at 87 min). Warming trades one for the other. No contradiction between the two entries; they
are different cells at different thermal states.

**Mechanism narrowed, not solved.** What the data rules out:

- **Not common-mode.** Magnitude-squared coherence between the seven 3.80 V cells is **0.023**
  against an estimator noise floor of ~0.05 — indistinguishable from zero, and the same for
  3.80 vs 4.20 within one band. Every cell wanders independently. This **contradicts §17.10's
  inference** that a threshold-tracking fault localises to the voltage domain (front end /
  1N4732 / preamp): a shared analogue mechanism would move all seven bands together.
- **Not a contiguous zone.** 4.20 V reads clean *between* two elevated columns at every time
  point in both sessions. §14.7's noisy–clean–noisy is confirmed and now has a full time course.
- **Local decay slope contributes but does not explain it.** ρ(excess, slope) = +0.63 across
  63 cells, but the 3.80 V slope (1585 µV/ns, from the profile's own delay/threshold table) is
  only 12 % above 4.20 V (1415) against 8× the noise.
- **It is a slow wander, not sample jitter.** ~50 % of the excess power sits at 0.02–0.1 Hz
  (10–50 s periods) and the spectral *shape* is unchanged cold vs soaked — only the amplitude
  moves (5706 → 1515 → 313 µV rms).

Incidental and worth keeping: expressing the *soaked* floor as slope × time gives a near-uniform
**70–130 ps** equivalent timing jitter across most of the grid, which is a tidy description of
the floor. The exceptions are the top thresholds and the 9 µs and 100 µs bands at 260–400 ps —
consistent with the `(9 µs, 4.9 V)` corner being a separate mechanism.

[FILL: does the noise follow the DELAY or the THRESHOLD? A fine delay sweep at the 3.80/4.40
cells separates those, and nothing in the logs can. Failing that, a scope on the decay between
4.2 and 3.8 V.]

**Nulls, recorded so they are not re-derived.** `c85` → `c86` amplitude 20.9 → 27.1 mV at one
placement is **not** claimed as a soak effect: the 2026-07-28 repeats at that placement read
24.0 and 22.5, so today's two straddle them and hand-placement variance covers it. And the
r1-vs-r2 settling question was already tested and rejected on 2026-07-28.

**Protocol debt this exposed.** Pack voltage existed only as handwriting on paper and had to be
interpolated onto the frame timeline by hand — the 2026-07-29 session has a **1h51m gap**
between the 22:00 and 23:51 readings, which is where that interpolation is least defensible.
Fixed in classviz v1.64 / features v9 (a logged `# pack_v:` track and a `pack_v` corpus column),
so the next run of this comparison is measured rather than reconstructed.

---

### findings — the MCU can be blocked by the host, and was, for 47 minutes

*2026-07-29 23:03–23:50, found in the pack B dump above*

The Mode 2 emit is a blocking `print()` to USB CDC (`mcu/pimd_mcu.py`). When the host stopped
draining the pipe, the MCU stalled inside it: frame delivery collapsed from **414 to ~35 per
minute** for 47 minutes (222 gaps of 2–15 s; all of the session's dead time is in this one
window, 2700 s of it), with the within-burst interval still a healthy 0.144 s.

**It is not just lost data — the rig cooled.** The firmware's own v4.24 note records that the
PWM free-runs at cell[0]'s config during the print, so a long stall parks the detector on one
band's duty instead of sweeping seven. The operating point stepped **+10 mV (9 µs band) to
+78 mV (100 µs band)** at 23:03 and walked back at −77 µV/s over ~7 min when the stream
resumed. That step correlates with the independently-measured cold-minus-warm direction across
all seven bands at **r = +0.99**, magnitudes in the same pulse-width order. Frames dropped
PC-side cannot do that; only the MCU actually pausing its sweep can.

Likely trigger, not established: the PC suspending or starving the Qt event loop. The recovery
coincides to the minute with the operator returning to take a voltage reading at 23:51.

Two consequences, both now addressed. It went **unnoticed live** — the Rate readout does show
0 Hz immediately, but it clears itself the moment the stream recovers and there was nobody
watching at 23:03 (classviz v1.64 latches it and writes a `# stall:` line). And it went
**unnoticed in analysis** for a while, because a 50-frame window spanning 100 s reads
accumulated drift as noise: the first pass through this data reported a "noise relapse" at
23:28 that does not exist (the same v1.64 entry; the artifact was 0.574 mV where the floor was
0.188 mV).

fw v4.27 counts these MCU-side rather than preventing them. **Deliberately not fixed:** making
the emit non-blocking. Dropping a record beats stalling the sweep, and no invariant objects,
but it needs bench proof that MicroPython's rp2 port reports stdout writability at all, and it
sits in the acquisition hot path — the v4.13/v4.20/v4.24/v4.26 sequence is a fair warning about
edits there. Measure first; the counters say whether it ever recurs. (2026-07-30)

---

### mcu/pimd_mcu.py — v4.27 — diagnostic: emit-block counters via 'B'

Detection only for the host-stall defect above; the emit path, its position in the sweep loop
and every bit of PWM/CC sequencing around it are untouched.

`acquire_mode2`'s emit `print()` is bracketed with `ticks_ms()`, and calls exceeding
`EMIT_BLOCK_WARN_MS` (50 ms — a normal emit is a few ms) increment `emit_block_count` and
update `emit_block_ms_max`.

**`ticks_ms`, not `ticks_us`, and that is the whole subtlety.** `ticks_us` wraps every ~17.9
min and `ticks_diff` is only valid over half a wrap (~8.9 min), so the 47-minute stall this
exists to catch would have decoded to garbage — plausible-looking garbage, since `ticks_diff`
returns a signed value in range. `ticks_ms` wraps at ~12.4 days. 1 ms resolution against a
50 ms threshold loses nothing.

The `B` response gains two trailing fields:
`B<busy_high_count>,<overrun_count>,<emit_block_count>,<emit_block_ms_max>`, reset-on-read like
the two before them. This is a change to a documented wire format (§9/§11), so: `grep` finds
**no parser for `B` anywhere in `src/`** — it is read by a human over the §16 serial terminal —
and the extension is additive, so no consumer breaks. Flagged rather than treated as free. The
header's command list now documents `B` at all, which it previously did not despite the command
existing since v4.11. (2026-07-30)

---

### src/pimd_classviz.py — v1.64 — window span guard, stall detection, pack voltage, chart pause

Four changes, all downstream of the two findings entries above.

**1. The `settle` metric could read drift as noise, and did.** `_current_settle_mv` and its
three siblings averaged over a window of *N frames*, which is only a window of *time* while
frames keep arriving. During the 23:03 stall a 50-frame window spanned ~100 s and σ inflated
~6×, which is the phantom "relapse" recorded above.

Every one of the four window reductions now goes through one new `_window_frames(n_win)`, which
returns `None` when the window spans more than `WINDOW_SPAN_TOLERANCE` (3×) its expected
duration. All four already had a documented `None` path for `< 2 frames`, and the gating call
sites already handled it (`settled = settle_mv is not None and …`), so a stall now **fails safe
to "not settled"** rather than to a plausible number. `_current_air_wander_mv` was previously
written out longhand on the argument that duplicated lines were cheaper than touching the
gating hot path; it is routed through the helper too, because a guard that holds on three of
four metrics still lets a stall through the fourth — and spanning *two* windows makes it the
most exposed of them.

**The reduction itself is unchanged** — same frames, same σ, no detrending — so the 0.4 mV gate
and every `splithalf_floor`/`quality` value already captured stay comparable. Verified rather
than asserted: replayed over all 114 246 frames of the 2026-07-29 dump in 2284 windows, **no
reduced value differs from the pre-v1.64 result at all**, and the guard refuses **35 windows,
every one of them between 23:03 and 23:51** — the known stall, and nothing else in 5h20m.

**The span is measured on the firmware clock, and this is the part that nearly went wrong.**
The obvious implementation — take the span from `_rolling_buf`'s own timestamps — does not
work, because those are **PC arrival** times and arrival is burst-batched: `read_from_serial()`
drains several lines per `readyRead` and stamps them microseconds apart. Over the whole
2026-07-29 dump, arrival intervals have median **0.0035 s** with **57 %** under 10 ms, against
a firmware clock that is uniform at median **0.1440 s** with none under 10 ms. Both share the
same mean (0.1683 s — same elapsed, same count), which is the trap: the mean looks right while
the median is 40× too small, and the median is the estimator that survives a stall. A first
cut used arrival time and refused healthy windows at a ratio of 42:1; the harness caught it.
So a new `_fw_ms_buf` deque carries the firmware frame clock index-aligned with `_rolling_buf`
(parallel deque rather than widening a tuple many consumers unpack), cleared with it, and
`_nominal_frame_s()` takes the median firmware interval over the last 500 frames — robust
because even through the stall the MCU emitted bursts of consecutive frames one nominal period
apart. Below `WINDOW_NOMINAL_MIN_N` frames no nominal is established and the guard stays off,
so stream start cannot read as stalled.

Also: the readout shows the window's real duration (`0.597 [6.9 s]`) or, blocked, why it is
blank (`STALLED 93 s`); `_set_gauge` uses `text or '—'` in its no-value branch so a caller that
knows the reason can say it (every pre-v1.64 caller passes `''` there, so rendering is
unchanged); and the Training status label distinguishes `σ — STREAM STALLED` from
`σ — (filling)`. The stale comments claiming 50 frames ≈ 15 s at ~3.3 Hz are corrected to the
measured 6.9 Hz / 7.2 s — nothing derived timing from them, but they are what made a
frame-count window look time-bounded.

**2. Stall detection on ingest.** `_note_frame_gap()` compares each frame's `firmware_time_ms`
against the previous one and, past `FRAME_GAP_WARN_S` (2 s ≈ 14 nominal frames; healthy p99 is
0.180 s), writes a timestamped `# stall:` line into the open dump and latches a red
`⛔ N stalls, worst Ns` on the Rate readout. Firmware time is the right clock: a gap in the
MCU's own clock is evidence the MCU stopped emitting. Latched because the instantaneous Rate
readout is exactly what failed to raise the alarm. A backwards firmware clock (board reset) is
ignored rather than counted. The latch resets on stream start, scoped to one run like v1.63's
auto-log suppression. On the real dump it finds 222 gaps, worst 14.8 s.

**3. Pack voltage.** A `Pack V:` spinbox and a `Log V` button on the Analysis session row.
0.00 shows as `—` and means *not measured*, written as blank rather than as a reading of a flat
pack. The button appends `# pack_v: <iso>, <volts>` mid-stream (same write+flush as
`_append_mark`); the value also goes into the session header and into every signature capture's
new `pack_v` column. A **20-minute** status-bar nag with the reading's age, sized against the
1h51m gap that made the 2026-07-29 interpolation weakest — status bar only, never a dialog,
since v1.63 established a modal would stall the stream behind a prompt. Persisted in settings
as a convenience (last session's closing voltage is the best guess for the next one's opening).

**4. Per-chart draw pause** — operator request, and on-point for the stall. The Pulse Width
Mean, Per Pulse Width Cell Profiles (8-grid) and Sample Delay Band Profiles (9-grid) groups
each get a `Pause` checkbox. Between them those three push 1 + n_bands + n_cells `setData`
calls per tick (17 at 63 cells) plus two scale re-syncs, and that drawing competes with
draining the serial port on the same single-threaded event loop — which is the race that ends
in the MCU blocking. With all three paused the shared `_compute_analysis_matrix()` is skipped
too, which is the largest single saving. Paused means *don't draw*, never *don't record*: the
frame path, `_rolling_buf`, the session dump and every gate are untouched, and resuming picks
up from live data with no backfill. Not persisted — a chart that comes back frozen after a
restart reads as a bug, and the reason to pause is a condition of the run, not a preference.

Verified offscreen: 22 checks against the real 2026-07-29 dump (the regression above, the
arrival-vs-firmware clock contrast, refusal reasons, both readout forms, the gap detector) plus
a launch smoke test and a session write → `pimd_features` parse round trip confirming the
written line formats match the parser. All under `-W error::DeprecationWarning`. **Not yet run
on the bench** — the induced-stall check (suspend the reader, confirm the gauge blanks with a
reason, a `# stall:` line lands, and `B` reports a non-zero block count) needs hardware.
(2026-07-30)

---

### src/pimd_features.py — v9 — pack_v track + stall lines parsed; pack_v corpus column

`parse_session_file` learns two `#` keys, in the header *and* mid-stream: `pack_v:` and
`stall:`. `SessionData` gains `pack_v` — an ordered `list[(datetime, volts)]`, header reading
first — and `stalls`, a `list[(datetime, gap_s)]`. A **track, not a scalar**, because a 6S pack
falls volts over a multi-hour run (2.5 V on 2026-07-29) and one figure cannot describe it. New
`pack_v_at(sess, t_s)` interpolates linearly between readings and holds flat outside them;
the corpus build calls it per capture, so `pack_v` is the voltage at *that* capture rather than
one value stamped across a whole session. Malformed lines and the header's `(not measured)`
form are dropped rather than guessed at — a track with a bogus entry is worse than a short one,
because the entries are what get interpolated between.

`pack_v` is appended to `CORPUS_HEADER_FIELDS` and `WIDE_TAIL_FIELDS`, and `build_rows` /
`build_wide_row` take it as a keyword with a `None` default, so every existing caller is
unaffected and an unmeasured capture writes blank. **Optional on read** — see the corpus_check
entry; that is the part that keeps the two corpora on disk readable.

Also resynced the header title line, which read v7 while `TOOL_VERSION` read v8. (2026-07-30)

---

### src/pimd_corpus_check.py — v1.8 — pack_v is an OPTIONAL column

`REQUIRED_FIELDS` was `set(CORPUS_FIELDS)`, so adding **any** column to
`pimd_features.CORPUS_HEADER_FIELDS` would have made every corpus written before it fail with
`missing required columns ['pack_v']` — both files on disk, immediately, for a column that is
blank whenever nobody measured a voltage. New `OPTIONAL_FIELDS = {'pack_v'}` is subtracted from
the requirement, and `load_corpus` reads the value as `None` when the column is absent *or* the
cell is blank, so pre-v9 corpora and unmeasured captures behave identically. Additive schema
growth belongs here rather than in a migration. No check consumes `pack_v` yet; it is carried
so one can.

Verified by running old and new against byte-identical snapshots of both corpora: v3 gives
`211 checks: 89 PASS, 0 AMBER, 121 FAIL, 1 SKIP` and v1 gives `143 checks: 62 PASS, 0 AMBER,
79 FAIL, 2 SKIP` — the same under v1.7/v8 and v1.8/v9. (The FAIL counts are the noise-floor
problem already recorded for these corpora, not a metadata one.) A corpus written *with*
`pack_v` also loads and reads back as floats. (2026-07-30)

---

### findings — the noise is a (9 µs, 4.9 V) corner, not a raised floor; not the battery

*2026-07-28 · `cal_63_air_bat_v3` / sha `4a2352d2` · fw 4.26 · 6S battery · 50 captures over
four sessions 14:25–16:38 (Cu_pipe_01 ×17, Fe_spanner_01 ×18, Fe_Cast_iron_trivet_01 ×13,
air ×2)*

**Correction to the 2026-07-28 air-wander entry.** That entry reported the noise floor as
having doubled between the first two sessions. It was drawn from 12 captures and does not
survive 50. Two batteries were swapped and left to settle before the 16:21 trivet session
partly on the strength of it; the swap changed nothing, which is itself the useful result.

**The floor is unchanged across the whole day.** Per-session `splithalf_floor`:

| session | window | n | min | median | q3 | max |
|---|---|---|---|---|---|---|
| 142336 | 14:25–14:37 | 8 | 0.88 | 1.25 | 1.41 | 2.07 |
| 150513 | 15:06–15:33 | 12 | 1.17 | 1.52 | 2.36 | 3.98 |
| 153912 | 15:44–15:59 | 15 | 0.90 | 1.77 | 2.45 | 3.48 |
| 161649 | 16:21–16:38 *(post battery swap)* | 15 | 0.90 | 1.67 | 2.53 | 3.45 |

The post-swap session is indistinguishable from the two before it. The two **air** captures
that close it — the purest noise probe in the corpus, no target coupling — read **0.899 and
0.974**, as clean as the best capture of the day. So the floor sits at ~0.9 mV throughout and
the supply is not implicated.

**What changed is the rate of excursions, and it is intermittent rather than a trend.**
Captures above 2.0 mV run 12% → 25% → 40% → 47% across the four sessions, but Spearman
rank correlation of `splithalf_floor` against elapsed time is only **+0.10** over the 133-minute
span. The distribution is growing a tail, not shifting: most captures still land at the floor
while a rising minority spike to 3–4×. Against amplitude the correlation is **+0.15**, so
`splithalf_floor` is target-independent as intended and the cross-session comparison is fair.

**Tested and rejected:** that the first capture at a placement is noisier than its repeat (the
rig still settling after handling). Across 21 placements holding both r1 and r2, r1 was
noisier in 10 and r2 in 11, medians 1.64 vs 1.67. No effect.

**Where the noise lives — 3 cells of 63.** Cell-by-cell noise/signal, from |noisy − clean|
over the eight most-contrasting matched pairs against the mean signal in the same cells:

| band | 4.9 V | 4.8 V | 4.75 V | 4.4 V | 4.2 V | 3.8 V | 2.4 V | 1.5 V | 0.5 V |
|---|---|---|---|---|---|---|---|---|---|
| **9.0 µs** | **5.31** | **1.52** | 0.48 | 0.39 | 0.38 | 0.50 | 0.45 | 0.32 | 0.13 |
| **13.44 µs** | **0.61** | 0.47 | 0.42 | 0.31 | 0.37 | 0.31 | 0.21 | 0.19 | 0.10 |
| 20 µs | 0.44 | 0.23 | 0.34 | 0.24 | 0.18 | 0.25 | 0.13 | 0.08 | 0.09 |
| 30 µs | 0.28 | 0.33 | 0.22 | 0.17 | 0.09 | 0.14 | 0.07 | 0.06 | 0.04 |
| 45 µs | 0.39 | 0.21 | 0.19 | 0.11 | 0.12 | 0.08 | 0.05 | 0.04 | 0.03 |
| 67.2 µs | 0.48 | 0.28 | 0.22 | 0.09 | 0.08 | 0.08 | 0.04 | 0.04 | 0.03 |
| 100 µs | 0.41 | 0.25 | 0.18 | 0.14 | 0.12 | 0.06 | 0.04 | 0.03 | 0.02 |

**A per-axis view of this data is actively misleading, and the mistake is recorded because it
is the kind that gets acted on.** Averaging down each column and across each band gives
4.9 V = 0.93 and 9 µs = 0.94, which reads as two bad lines and argues for deleting a band and
a threshold. Both averages are dragged up by the single 5.31 cell at their intersection. The
4.9 V column's other six cells run 0.28–0.48; the 9 µs band's other seven run 0.13–0.50.
**Neither line is bad.** The effect is `(9 µs, 4.9 V)`, `(9 µs, 4.8 V)` and, marginally,
`(13.44 µs, 4.9 V)` — 4.8% of the grid. Because `splithalf_floor` is an L2 across all 63
cells, that corner sets the noise figure for the whole capture, which is why it presents as a
floor problem at capture level.

The corner is marginal at every distance, not merely at range — mean |delta_mV| in the
`(9 µs, 4.9 V)` cell against ~0.9 mV of noise there:

| target | 60 mm | 120 mm | 180 mm | 240 mm |
|---|---|---|---|---|
| Cu_pipe_01 | 1.90 (SNR 2.0) | 2.08 (2.2) | 0.46 (0.5) | 0.16 (0.2) |
| Fe_spanner_01 | 1.16 (1.3) | 1.50 (1.6) | 0.78 (0.8) | 0.66 (0.7) |
| Fe_Cast_iron_trivet_01 | 2.04 (2.2) | 0.92 (1.0) | 2.94 (3.2) | — |

**Decision: keep profiling, change nothing.** Excluding just those 3 cells cuts the
paired-difference L2 (a `splithalf_floor` proxy) by **29% median / 32% mean** across 21
placements — the whole benefit is available from 4.8% of the grid, at analysis time, and is
reversible. A profile change is neither: it mints a new `profile_sha8`, the
`(profile_name, profile_sha8)` guard hard-errors across corpora so today's 50 captures would
stop being comparable with tomorrow's, and it needs a fresh delaycal sweep and lock (§10).
Dropping the band and the column would discard 15 cells to fix 3, and would take the
early-band discrimination §14.9 depends on with it. Cell exclusion or SNR weighting is a call
to make once the target set is complete, not now.

**The v3 profile's own fixes held.** 4.75 V — the step moved in the re-sweep after the 4.70
column misbehaved — reads 0.25 at its worst, and the 4.40 / 3.80 columns that §17.10 found
elevated under the failing supply read 0.09–0.17 and 0.06–0.50. Those are clean. This is the
**top of the ladder meeting the shortest band**, a different observation from §14.7's
~4.45–4.65 keep-out zone, and it is new.

**Supply: the pack fell 23.77 V → ~22.5 V with no measurable effect.** §17.10 established that
within the regulated window the L7815 holds coil drive constant and state of charge does not
reach the operating point, *"at least down to 23.05 V"* — as far as that trial went. Today ran
about **0.55 V below** that, and across the span amplitude reproducibility for repeats of one
placement held at 0.937 / 0.946 / 1.072 (~6%) while the floor was unchanged, closing on air at
0.899 / 0.974. So the regulated-window result now has evidence half a volt lower, and the
day's supply behaviour independently corroborates the battery-swap null: neither swapping
packs nor draining one by 1.27 V moved the noise. **This is not the measurement §17.10 used**,
which was the *direction* of per-band delay shift under a falling pack; amplitude stability
plus an unchanged floor is weaker, different evidence — consistent with regulation holding,
not proof of it. Thermal drift was visible to the operator after soaking (§14.1). Flagged, not
acted on: the corpus records `supply=battery` but **not pack voltage**, so this association is
between the day's endpoints and the day's captures rather than per capture; adding a voltage
column to `CORPUS_HEADER` would make it measurable next time, and is a schema decision of its
own.

**Confidence and what would settle it.** Eight matched pairs is a modest sample, and an
r1-vs-r2 difference contains real repositioning as well as noise — though repositioning would
scale *with* signal and this runs the other way. What carries the result is that the three
implicated cells stand 3–10× above every one of the other sixty, in a monotonic ordering that
chance does not produce. The direct confirmation is a **Std Dev (rolling N) heatmap under
v3**, the same instrument §17.10 used to find the 4.40/3.80 elevation: it shows the grid
per-cell rather than by inference from paired captures. Open until then.
[FILL: does the heatmap show the same three cells? And is 4.9 V simply unreachable for a
9 µs flyback — the crossing landing at or past the clamp, so the sample time is ill-defined —
in which case the ladder's top step is the thing to reconsider, not the band?]

**Protocol for 2026-07-29**, so the two days stay comparable: profile unchanged
(`cal_63_air_bat_v3` / `4a2352d2`, one epoch across both days); Std Dev heatmap before any
target; and an **air capture at the start and end of every session** — today's closing pair
was the single most informative measurement of the day, being the only target-free probe of
the floor, and two per session makes the floor trackable instead of inferred. (2026-07-28)

---

### src/pimd_classviz.py — v1.63 — session logging auto-starts with the stream

Session dumps were opt-in — `Record Session` on the Stats tab, or Session `Start` on the
Analysis tab — and on 2026-07-29 that cost the day's most wanted measurement. Logging ran
16:16–16:54 and then stopped; profiling ran 17:41–18:32, and the 47-minute pack-A settle
between them went unrecorded too. Raw stream is not reconstructable after the fact, and the
corpus carries no pack voltage, so the battery-settling question could only be answered from
the 8 minutes that happened to be running. Forgetting to press Record is silent, and the
loss is permanent.

A dump now opens by itself whenever the stream starts (`start_stop`'s Running branch, and
`_on_load_run_profile`, which sends its own `G` — the latter is the v1.53 launch auto-start,
i.e. the entire warm-up and settle window before anyone presses anything). `Start Training`
is a second-chance backstop, deliberately *not* the primary trigger: what mattered most on
the 29th happened before any training began. `_apply_profile` already force-closed the dump
on a dimension change because the header carries `profile_json`/`profile_sha8`; it now opens
a fresh correctly-headed one instead of leaving the rest of the run dark.

The preference (`Auto-log`, persisted as `session_autolog`) defaults **on**: the failure it
guards against is unrecoverable, and the opposite mistake costs ~13 MB/hour of gitignored
CSV — measured at ~220 KB/min from the 29th's own dumps. An explicit Stop latches
`_session_autolog_suppressed` and stays stopped until the stream is next started, so "stop"
means stop without meaning "stop for the day". The programmatic force-stops flag themselves
via `_session_stop_is_forced`, since they reach `_toggle_record_frames` through the same
`pb_record.setChecked(False)` an operator click does and would otherwise suppress logging as
a side effect of changing profile.

Auto-started dumps can't prompt — `QInputDialog` is modal and would stall the stream behind
a dialog nobody asked for — so they get a generated notes line naming the trigger, profile,
sha8 and supply, and the header records `# session_autostart: true|false`. Pressing Session
`Start` while one is already running now **adopts** it: prompts, and appends the operator's
notes mid-file as `# session_notes:` lines via `_append_session_notes` (same write+flush
pattern as `_append_mark`), rather than refusing or restarting and discarding the frames
already logged. Requires `pimd_features.py` v8 to read those late notes.

Also fixed, and reachable only because of the above: `_session_start` named files at
second resolution and opened with `'w'`, so a close-and-reopen inside the same second
silently truncated the dump just closed. Two deliberate button presses never hit it; the
auto-restart after a profile change does exactly that back-to-back. Colliding names now take
a `_2`, `_3` suffix. Consumers glob `session_*.csv` and read the timestamp from the header,
not the filename, so nothing downstream changes. (2026-07-29)

---

### src/pimd_features.py — v8 — parse mid-stream '# session_notes:' lines

`parse_session_file` recognised `session_notes:` only in the header block; mid-stream it
handled `mark_target:` and `mark:` and dropped everything else. With classviz v1.63
auto-starting sessions, the header notes are generated and the operator's own notes are
appended later, mid-stream — so without this they would be written and never read. One
`elif`, appending to the same `notes_lines` the header branch fills, so `session_notes` reads
as one block regardless of where in the file the lines landed. Additive; older session files
parse identically. (2026-07-29)

---

### src/pimd_classviz.py — v1.62 — FIX repeat_idx stuck at r1

Bench report: `Fe_spanner_01` rows reading `r1` where they should read `r2` — three rows
showing `@180mm  x  r1`, same placement *and* same repeat. Confirmed in the corpus: every
pair captured in the 15:39 session was stuck at r1. Two independent causes, and only one of
them was recent.

**The suggestion was never recomputed after a save — latent, not a regression.**
`_update_sig_repeat_idx_suggestion()` is connected in exactly one place, to placement-*widget*
change signals. `_reload_editable_signature_list()` rebuilds `_editable_repeat_counts` after
every save and then never re-ran the suggestion, so the spinbox kept its stale value: two
captures of one placement with nothing touched in between both saved as r1. Earlier sessions
hid this by alternating placements between repeats (c13 x → c14 y → c15 x), where each widget
change fired the signal; the 15:39 session did back-to-back repeats and exposed it. Fixed by
calling the suggestion at the end of `_reload_editable_signature_list()` — save, delete and
file-open all land on that one seam, so no second signal connection was needed.

**The placement key split across the v1.60 boundary — this one v1.60 caused.** Rows captured
before it carry `face_normal=z`; `_placement_from_widgets()` now yields `na`; both are in the
placement tuple. So returning to any pre-v1.60 placement failed to match its own history and
restarted at r1. It had already happened — c20 (`@180 x r1`, `z`) and c23 (`@180 x r1`, `na`)
are the same physical placement. `_placement_tuple_key()` now takes both its field list and
its per-field normalisation from `pimd_corpus_check` (below) instead of restating them, so
the app and the checker cannot drift on what "the same placement" means — which was the
constraint the v1.60 design turned on in the first place.

Verified offscreen: `z` and `na` (and a non-zero offset) key identically while `long_axis`
still separates; classviz's tuple equals `pimd_corpus_check.placement_key()` for the same
dict; asking for `Fe_spanner_01 @180 y` after a reload suggests **r3** against two captures on
file where it previously stayed at 1; a placement with no history still gives r1; and the
cross-boundary case — `Cu_pipe_01 @60 z`, whose file rows carry `face_normal=z` — now counts
them and suggests r3. Nine harnesses pass under `-W error::DeprecationWarning`.

**Not yet run on the bench**: capture twice at one placement without touching a control; the
second must save as r2. (2026-07-28)

---

### src/pimd_corpus_check.py — v1.7 — placement key normalises the fields v1.60 froze

`placement_key()` and `target_key()` route each field through a new `placement_value()`, which
substitutes the not-applicable constant for the three fields classviz v1.60 stopped accepting
as inputs (`PLACEMENT_CONSTANT_FIELDS` = `face_normal` `na`, both offsets `0`). Without it a
corpus straddling that change splits one physical placement into a `z` group and an `na`
group, so a repeat reads as a fresh base and the repeat-consistency check compares nothing
against nothing. classviz imports both the field tuple and this helper, so there is one
definition rather than two that agree by inspection.

Honest about the cost, in the constant's own comment: this discards information in principle
— a corpus with genuinely different offsets would collapse to one placement. It does not in
practice, since no corpus on disk has a non-zero offset or a `face_normal` other than
`z`/`na`, and neither can be entered any more.

Effect on the live corpus, with the repaired repeat_idx values: the run goes from **30 checks
to 90**. Repeat-consistency now pairs a base against a repeat for the spanner placements
instead of seeing duplicates, and **distance-falloff runs at all** — it had been SKIPping for
want of a target at ≥3 distances, and now fits copper pipe at n = 2.05 / 1.81 and the spanner
at n = 1.42 / 1.63. The FAIL count rises with the check count; those are the noise-floor
problem already recorded for this corpus, not a metadata one. (2026-07-28)

---

### findings — 8 captures renumbered in the v3 corpus (repeat_idx collisions)

Data repair, recorded because it edits captured data. Eight captures in
`gui_signatures_targets_v3_20260728_142316.csv` carried a `repeat_idx` colliding with another
capture at the same placement, caused by the two v1.62 bugs above:

| capture | target | placement | was | now |
|---|---|---|---|---|
| `..._153912_c22` | Fe_spanner_01 | @180 y | r1 | r2 |
| `..._153912_c23` | Fe_spanner_01 | @180 x | r1 | r2 |
| `..._153912_c25` | Fe_spanner_01 | @120 y | r1 | r2 |
| `..._153912_c27` | Fe_spanner_01 | @120 x | r1 | r2 |
| `..._153912_c29` | Fe_spanner_01 | @120 z | r1 | r2 |
| `..._153912_c31` | Fe_spanner_01 | @60 z | r1 | r2 |
| `..._153912_c33` | Fe_spanner_01 | @60 y | r1 | r2 |
| `..._153912_c35` | Fe_spanner_01 | @60 x | r1 | r2 |

`c23` is the cross-version one: it pairs with `c20`, which carries `face_normal=z` from before
v1.60, and only groups with it under the v1.7 normalisation.

Method: group by the normalised placement key, order by `captured_at`, assign 1..n. Idempotent
where the data was already right — Cu_pipe's existing r1/r2 pairs were untouched — and a
re-run reports no changes. `src/data/corpora/` is gitignored, so a timestamped `.bak-` copy was
taken first; git could not have restored it. The write proved itself rather than being trusted:
same header, same 2205 rows, and **only** the `repeat_idx` column differing from the backup
(504 cells = 8 captures × 63 cells).

Assumption made visible rather than buried: renumbering by capture time presumes no repeat_idx
was deliberately set out of order. Every affected value was the default 1, so nothing suggests
otherwise. (2026-07-28)

---

### src/pimd_classviz.py — v1.61 — signature rows carry long axis + repeat; colour is per target

Reported as detail the signature list had lost. It had not: `git log -S` finds no commit
that ever carried it, and the label format is unchanged since **v1.30**. The detail existed
in the v1.58/v1.59 build that ran on the bench today and is not on disk (see the v1.60
entry). So this is a restore from description rather than a revert, and worth recording as
such — the repo was never the source it was lost from.

**Rows now identify their capture.** `✎ Cu_pipe_01 @120mm  z  r2   amp=24 SNR=27.4 [ok]`.
Today's corpus is one target across four distances × three orientations × two repeats, so
six captures shared the string `Cu_pipe_01 @120mm` and nothing on the row separated them.
`long_axis` and `repeat_idx` already arrived from `_scan_editable_signature_file()` for the
editable and scratch sources; they were simply not formatted in. A `long_axis` of `na`
carries nothing and is omitted, as is the whole pair for the legacy 3-tuple key shape.

**Colour is now per target, not per row.** It was `pg.intColor(i, hues=…)` on the row's
index, so a target's colour changed whenever the list grew or re-sorted and two captures of
one target looked unrelated. New `_template_color()` takes the hue from the target_id and
steps **value** (230 → 140) across that target's captures, with a ±10° hue jitter alongside.

Three things that shaped it:

- The colour is not only the list row. It is stored into `_analysis_templates[key]['color']`
  and is the pen for the **chart overlay curves** and the **Family Plane markers**, so a flat
  per-target colour would have made two overlaid orientations of the same target
  indistinguishable. Hue-per-target with shade-per-capture serves both.
- The hue comes from **`zlib.crc32`, not the builtin `hash()`**. Python salts str hashing per
  process, so `hash()` would repaint every target on each launch — a subtler version of the
  instability being fixed, and one that passes every in-process check. There is a test that
  runs the helper in two subprocesses under different `PYTHONHASHSEED` values, because that
  is the only place the trap is visible.
- Value alone cannot separate many captures of one target: at 17 captures the steps are ~5
  units apart. The hue jitter helps and is honestly not a full answer — 17 distinct shades of
  one hue do not exist. The label is what identifies a row; the colour groups.

`_merge_template_list()` splits into two passes, because the shade needs each capture's
ordinal within its target and that is not known until every key is resolved. Pass 1 only
hoists the existing key-shape branch unchanged; pass 2 builds the items. Group sizes are per
source batch exactly as the old row index was, and the hue does not depend on them.

Verified offscreen against the real corpora: every v3 row carries its axis and `r<n>`, and
the six rows sharing `Cu_pipe_01 @120mm` are now six distinct strings; `Cu_pipe_01`'s 17
captures occupy hues 10–30 and values 140–230 while `Fe_spanner_01`'s occupy 320–340, with
the two bands asserted not to overlap; the helper returns identical colours under
`PYTHONHASHSEED` 0 and 12345; and overlays rebuild over a checked selection with every stored
colour valid. Noted while testing: `pimd_corpus_check.load_corpus()` dropped legacy-schema
support at v1.5 and **both** corpora on disk are v1.32+, so `_merge_template_list`'s 3-tuple
branch is defensive dead code for any real file — it is exercised synthetically rather than
left untested. All eight harnesses pass under `-W error::DeprecationWarning`. **Not yet run
on the bench.** (2026-07-28)

---

### USAGE.md — v1.23 — classviz v1.60 → v1.61

§5's Analysis bullet gains what a signature row reads and what its colour means (one hue per
target_id, shaded per capture, stable between sessions because it is derived from the id).
§1 diagram version follows. (2026-07-28)

---

### src/pimd_classviz.py — v1.60 — remove the face_normal / offset X / offset Y capture inputs

Three of the structured placement inputs were never used, and one of them was actively
writing junk. `face_normal` is a *persisted* combo (`sig_face_normal`), so a value chosen
once silently rode along on every later capture: all 12 captures in the first v3 corpus —
`Cu_pipe_01`, a **tube** — carry `face_normal=z`, a field its own tooltip reserves for the
dim_a × dim_b face of plates/discs/sheets and defines as `na` where meaningless. The X/Y
offsets were 0 throughout, which is the correct "centred" value, but nobody was setting
them either.

The three widgets are gone from `_build_target_placement_widget_set()`. Row B now reads
Long axis · Medium · Repeat #, absorbing Repeat # from the row the offsets used to share —
on its own it did not earn a row, so the form drops from three rows to two.

**The schema does not change, and that is the point of the design.**
`_placement_from_widgets()` still returns all eight keys, now with `face_normal='na'` and
both offsets `0` as literals, so the corpus CSV columns, the session dump's `mark_target:`
line, `_placement_tuple_key()` and the `pimd_features.Plateau` construction are all
untouched. Removing the columns would have broken
`pimd_corpus_check.PLACEMENT_FIELDS`, which keys repeat-consistency grouping on all seven
placement fields, and stranded the two existing corpora that carry real values in them. The
placement tuple keeps all seven fields for the same reason: three are constant now, so it is
effectively (target, distance, long_axis, medium), but it must stay field-for-field aligned
with the checker's or the two tools would disagree about what "the same placement" is.

Settings save/restore for the three keys is deleted rather than migrated. A stale
`sig_face_normal` sitting in an existing `classviz_settings.json` is simply never read
again, which is precisely what ends the leak.

**Version skips 1.58 and 1.59, deliberately.** Ten captures in the current v3 corpus are
stamped `pimd_classviz.py v1.59`, and that version is in no commit, stash or reflog entry.
Investigated rather than assumed: there is exactly one `pimd_classviz.py` on the machine, and
the app producing those captures is a process launched at ~14:58 that has been running since,
so it loaded this file at a moment when it read `1.59`; the file has since been restored to
`1.57` with no git trace, and `git diff` confirms nothing but this change is uncommitted, so
no work was lost. Releasing a v1.58 *after* captures stamped v1.59 would make version order
contradict time order in exactly the provenance field that exists to record it, so the next
release is **1.60**. The gap is this paragraph, not an accident.

Verified offscreen: the three widgets are absent while target/distance/long_axis/medium/
repeat_idx remain; `_placement_from_widgets()` still returns all eight keys with `na`/0/0;
`_placement_tuple_key()` is asserted equal to `tuple(str(p[f]) for f in
pimd_corpus_check.PLACEMENT_FIELDS)` — against the checker's own constant, not a copy, so the
two cannot drift; `pimd_features.CORPUS_HEADER` still carries all three columns; both
existing corpora still scan (66 and 18 captures, `face_normal='z'` preserved on read); and a
settings file containing the six removed keys loads without error and saves without them.
All seven harnesses pass under `-W error::DeprecationWarning`, and the rendered form reads
Target/Distance on one row, Long axis/Medium/Repeat # on the next. **Not yet run on the
bench** — the check is that a new capture writes `face_normal=na, offset_x_mm=0,
offset_y_mm=0` and that `pimd_corpus_check.py` groups it as expected. (2026-07-28)

---

### USAGE.md — v1.22 — classviz v1.57 → v1.60

§5's Analysis bullet: the placement field list drops `axes, offsets` for `long_axis`, and
gains a paragraph on why `face_normal`/offsets are no longer inputs but are still written
`na`/0/0, plus the `long_axis` x/y/z convention spelled out in physical terms (coil long
axis / coil short axis and rover travel / coil normal) — that convention was queried on the
bench and is worth stating where it is used, not only in a tooltip. §1 diagram version
follows. (2026-07-28)

---

### src/pimd_classviz.py — v1.57 — show the surviving central-frame count; Frames default 60 → 100

Prompted by the question "aren't some of those 120 profiling frames discarded?". They are —
`pimd_features.CENTRAL_FRACTION` is 0.60, so `central_frames()` trims **20% off each end**
(not 25%) of the target window *and* both air anchors before stats. At 120 frames, 72 feed
the result. Nothing on screen said so.

It is not a live "profiling but not sampling" phase, and the display does not pretend
otherwise: every frame is sampled and buffered, and the trim is applied retrospectively to
the finished window in `_compute_sig_stats()`. Which frames get dropped depends on where the
window ends up, so the only honest live number is **how many of the frames held right now
would survive** — which is also precisely the warning wanted before a Space force-advance.
A now reads `COLLECTING target — 47/120 (28 central)`, and the colour follows that count:
yellow below `MIN_CENTRAL_FRAMES`, then the existing blue/green. That extends the ladder
rather than fighting it — yellow already meant "not ready" — so a phase reads yellow → blue
→ green as frames bank up, and an `ACQUIRED` row still yellow means the Frames setting
itself is too low. New `_central_frame_count()` routes through
`pimd_features.central_frames()` with the same throwaway `Plateau` the stats path builds,
so the trim keeps one definition and cannot drift from the corpus builder.

**A defect found while checking it.** `quality_flags()` stamps `short` when
`n_central < MIN_CENTRAL_FRAMES` (60), and the Training Frames default *was*
`MIN_CENTRAL_FRAMES` itself — 60 frames trims to 36 central, below the very constant it was
taken from, so a default-Frames capture was stamped `short` every single time. The Family
Plane scratch path had already solved this at v1.46 by sizing its window to
`ceil(MIN_CENTRAL_FRAMES / CENTRAL_FRACTION)` = 100, with a comment naming the problem; the
Training group never got the same treatment. That expression is now the named constant
`SIG_CAPTURE_N_DEFAULT`, used as the Frames default (fresh settings only — a persisted value
still wins, so an existing 120 is untouched) and at the scratch call site in place of the
inline `ceil`. Below it the spinbox turns amber and its tooltip states the arithmetic for the
current value (`60 frames give 36 central`) plus the consequence. Not blocked: a deliberately
short capture is still allowed, just marked.

Flagged, not changed: `_sig_can_commit()` still accepts any window of ≥2 frames, so a Space
force-advance can commit a tiny capture — the likeliest origin of the short capture in the v3
corpus. The live count now warns before the press, and hard-blocking an override is a
separate decision.

Verified offscreen. `_central_frame_count()` is cross-checked against
`pimd_features.central_frames()` directly for 0/2/10/60/100/120 → 0/2/6/36/60/72, with the
old default (60 → 36 → `short`) and the new one (100 → 60 → `ok`) asserted as the defect and
its fix. The Frames warning is checked at 60/99/100/120 for both the style and the tooltip
numbers. The label walk asserts `(N central)` tracks the buffer and that the colour crosses
exactly at `MIN_CENTRAL_FRAMES` — observed yellow at 1/120 (1 central), blue at 100/120
(60 central). All six harnesses pass under `-W error::DeprecationWarning`; longest label is
still 36 characters against the 52 ceiling. **Not yet run on the bench** — the check there is
that a 120-frame cycle reads `(72 central)` when full and saves `quality=ok`, and a 60-frame
one stays yellow at `ACQUIRED` and saves `short`. (2026-07-28)

---

### findings — one capture in the v3 corpus is stamped 'short'; the Frames default caused it

Quality-flag census of the two tracked corpora, prompted by the v1.57 investigation:

| corpus | rows | quality |
|---|---|---|
| `gui_signatures_targets_v1_20260723.csv` | 4158 | 2898 ok, 1260 noisy, **0 short** |
| `gui_signatures_tragets_v3_20260727_171813.csv` | 819 | 756 ok, **63 short** |

63 rows is exactly one capture at 63 cells, so **one of that session's 13 captures** carries
the flag. The v1 corpus has none, so whatever produced it is new to the v3 session.

Two candidate causes, not separated: the Frames default of 60 (which cannot clear
`MIN_CENTRAL_FRAMES` at all — see the v1.57 entry), or a Space force-advance committing a
partly-filled window, which `_sig_can_commit()` permits down to 2 frames. Either way the flag
was only discoverable after the save; v1.57 surfaces the count live so the next one is
visible before committing.

Noted, not acted on: that corpus filename misspells "targets" as **`tragets`**. It is
captured data carrying provenance, so renaming is the owner's call, not a tidy-up.
(2026-07-28)

---

### USAGE.md — v1.21 — classviz v1.56 → v1.57

§5's Training paragraph gains the central-60% trim: what it discards, what `(N central)`
means and why it is the pre-commit warning, the yellow→blue→green ladder, and the Frames
default of 100 with the reason for the amber warning below it. §1 diagram version follows.
(2026-07-28)

---

### src/pimd_classviz.py — v1.56 — Training A/B labels name the gate holding each phase up

The two await phases each rendered one fixed string — `WAITING for target…` and `ACQUIRED
target — captured, remove now` — so an operator watching a 30 s countdown had no way to tell
whether the rig was still settling, or settled and simply short of Detect. Those are
different problems with different fixes (stop touching the bench / move the target closer),
and nothing on screen distinguished them. Between "place target now" and "profiling target"
there was no visible state at all.

**A** now pairs the live measurement with whichever gate is currently blocking the
transition, and **B** keeps the instruction plus either the guard countdown or the frame
count:

| state | A | B |
|---|---|---|
| leading air, unsettled | `SETTLING air — σ0.512 > 0.400` | `Acquiring leading air — waiting for settle` |
| air ready | `ACQUIRED air — 20/20 (rolling)` | `Press Space` |
| awaiting target, settled | `WAITING target — Δ0.028 < 0.500` | `Place target now — need Δ≥0.50 mV — 30s` |
| awaiting target, disturbed | `MOVING — σ19.153 > 0.400` | as above |
| profiling | `COLLECTING target — 47/120 (73 left)` | `Profiling target — 47/120 frames` |
| awaiting removal, untouched | `HOLDING target — lift it to release` | `Remove target now — 30s` |
| awaiting removal, disturbed | `MOVING — σ19.682 > 0.400` | as above |
| awaiting removal, re-settled short | `MOVED — Δ0.119 < 0.500` | as above |

`HOLDING target` is the v1.54 transient latch made visible: until something physically moves,
removal cannot fire whatever the magnitude reads, and the label now says so rather than
implying the app is waiting on a threshold. `_update_sig_train_indicator()` takes the
deviation alongside the settle value; `_sig_train_ingest()` passes what it already computed,
and it stays `None` while unsettled, which is what selects the σ form over the Δ form. The
settle value falls back to measuring itself when a phase-transition call site does not supply
one — otherwise every state change flashed a placeholder, which is the failure being fixed.

Two wording decisions worth recording. `await_target`'s disturbed state is `MOVING`, not
`SETTLING`: the collecting phases already use `SETTLING <subject>` and a bare `SETTLING`
read as the same state. And the filling note is `waiting for settle`, not "window cleared" —
the status is identical on a first fill, where nothing was cleared.

Verified offscreen by walking a synthetic cycle through `_sig_train_ingest()` frame by frame
and asserting the label at each of ten states an operator can sit in, including that A names
σ-vs-Settle while unsettled and Δ-vs-Detect once settled, and that the manual-placement
wording survives. Longest label rendered is 36 characters, checked against a 52-character
ceiling so neither label can widen the Training group. One fixture bug found and fixed on the
way (the synthetic clock outran the wall-clock guard deadline, aborting the cycle mid-walk),
which is why the walk now asserts the phase after locking rather than trusting it.
(2026-07-28)

---

### USAGE.md — v1.20 — classviz v1.55 → v1.56

§5's Training paragraph rewritten around the A/B status text: each state now names the gate
holding it up, with the actual label strings quoted, since the point of the change is that
the operator reads these rather than guesses. §1 diagram version follows. (2026-07-28)

---

### src/pimd_classviz.py — v1.55 — lift the v1.41 manual latch on removal auto-detect

v1.41 blocked removal auto-detect whenever placement had been forced by Space. That was
correct for the removal rule of the day: it was the placement comparison inverted, so for a
target that had never cleared Detect going on, "|Δ| below Detect" was already true on the
first settled frame of `await_remove` and the cycle skipped the removal wait outright (the
v1.40 field failure). The latch was a guard on a test that could fire on arrival.

v1.54 replaced that test — removal now needs a settle-loss transient **and** a departure
from the target snapshot — and neither half can be satisfied on arrival, so the failure the
latch existed to prevent is no longer reachable. The block is lifted: a Space-forced
placement gets removal auto-detect like any other. `_sig_target_manual` is *not* retired; it
still keeps Space permitted through the rest of that cycle without the override checkbox,
which is the fallback for a target too weak for either direction to fire. The `await_remove`
instruction reads `Remove target — auto, or Space` for a manual placement rather than
promising auto-detect alone, since that is the case most likely to need the fallback.

Verified offscreen, two new cases beside the four from v1.54. A manual placement followed by
a real removal (transient, then re-settle at air) now advances to `air_trail` where it
previously stalled — and, at the top of that case, `await_remove` is asserted still current
on arrival, which is the v1.40 regression under test. A **weak target** case covers the
other side: 0.2 mV against a 0.5 mV Detect, transient seen and latch armed, removal
correctly *declines* at 0.215 mV of departure and falls through to Space. The v1.54 cases
are unchanged and still pass, including the decisive one (1.66 mV of drift-driven deviation
with no transient does not advance). **Not yet run on the bench.** (2026-07-28)

---

### USAGE.md — v1.19 — classviz v1.54 → v1.55

§5's Training paragraph gains the lifted latch: a Space-forced placement now auto-detects
removal too, with Space still permitted as the fallback and the reason why (a target too
weak to clear Detect going on will not clear it coming off). §1 diagram version follows.
(2026-07-28)

---

### src/pimd_classviz.py — v1.54 — FIX removal auto-detect; Air age against the cycle budget

Acts on the concern flagged (deliberately unfixed) at v1.52, now confirmed on the bench:
the Air-age marker does go red during `await_remove`, so the removal test was being asked
to resolve a target against more accumulated drift than target.

**Removal auto-detect reworked.** It tested whether the signal had come back to within
Detect of the **leading air** — a reference by then a whole target-collection window older.
DESIGN §17.10 measured that as unable to work: at ~50 µV/s a 150 s-old air reference reads
5.2 mV where a spanner @60 mm reads 2.8 mV, so *removing the object makes |Δ| go up*. The
new test has two halves, and both are load-bearing:

- **A transient must have happened.** Lifting the object unsettles the signal before it
  re-settles elsewhere; drift never does. `_sig_removal_armed` latches a settle-loss seen
  during `await_remove` and the transition requires it. This is what separates "target
  lifted" from "reference aged", and it is why a magnitude test alone was not enough.
- **Then a departure from a *fresh* reference.** New `_current_dev_from_target()` compares
  the settle window against `_sig_target`, the snapshot taken in `_sig_finish_target()`
  moments before `await_remove` began — seconds old, not minutes. Removal fires on
  dev > Detect, so both gated phases now share one shape of test (settled, and |Δ| from a
  fresh reference above Detect), each against its own reference.

The v1.41 manual latch is untouched: a Space-forced placement still requires Space to leave
`await_remove`. It could now arguably be lifted, since the target snapshot exists however
the phase was entered — left alone as a separate decision.

**Air age now measures the cycle budget, not the drift budget.** The old limit,
Detect / 0.05 mV/s, was 10 s at Detect 0.5 — red long before a 120-frame target window could
finish, so it said nothing. That number described whether a magnitude test against the
frozen reference could still work; with removal no longer using that reference, nothing
gates on its age and the useful question became "is this cycle dragging".
`_sig_cycle_budget_s()` returns what one healthy cycle owes after the lock — two collecting
windows plus two 30 s guards — using the **measured** sweep rate (`_fps_hz`) where there is
one, because a 63-cell profile sweeps slower than a 45-cell one and a hardcoded period would
be wrong on half the profiles. 132 s at 120 frames and ~3.3 Hz. `AIR_DRIFT_MV_PER_S` is
removed rather than left dead; the figure and its §17.2/§17.10 citation live in the new
method's docstring.

The Detect gauge gained a third mode to match (`_sig_dev_is_gated()` → `_sig_dev_mode()`,
returning `air` / `target` / `wander`), so the unit column reads `mV vs target` through
`await_remove` and the gauge always names the reference it is showing. Green still means
"the thing you are waiting for", which is now a crossing *above* Detect in both gated
phases.

Verified offscreen, five state-machine cases driven through `_sig_train_ingest()` frame by
frame. The decisive one: a target sitting still under 50 µV/s of drift reaches **1.66 mV of
deviation from its own target reference — well past a 0.5 mV Detect — and the cycle does not
advance**, because no transient occurred. A magnitude-only fix would have false-fired there.
Also covered: a real removal (unsettle → re-settle at air) advances to `air_trail`; a knock
that arms the latch but leaves the target in place does not advance; the v1.41 manual latch
still blocks auto-advance; and `_sig_finish_target()` clears a stale arm so it cannot carry
into the next cycle. Gauge-side: all three Detect modes assert the right source, unit text
and value across a full phase walk, and the Air-age limit tracks Frames and the measured
rate.

**Bench-confirmed 2026-07-28**: cycles run through place and remove without operator
intervention, and Air age no longer goes red inside a normal 120-frame cycle. Known
remaining failure mode, unobserved so far: a target removed smoothly enough never to break
the Settle gate will not arm the transient latch, and that cycle times out to Space override
— the same fallback as before, but now this is the specific way it can happen. At the
working Settle of 0.4 mV σ any real movement should trip it. (2026-07-28)

---

### USAGE.md — v1.18 — classviz v1.50 → v1.54

§5 gains a **Trigger Levels** bullet (the five-gauge column, which thresholds are draggable,
and what each of the Detect row's three modes measures — the phase-dependent reference was
the thing that confused a reading on the bench, so it is spelled out) and an **Auto-start**
bullet. §5's Training paragraph corrected: it still described removal as "Δ back below
Detect" against the leading air, which v1.54 replaced — the new wording carries the §17.10
reason, since the old rule looks more sensible than it is. §1 diagram version follows.
(2026-07-28)

---

### findings — air wander at the v3 operating point: 0.2–0.3 mV, and the v1.52 fix confirmed

Bench check of the classviz v1.52 Detect gauge, `cal_63_air_bat_v3`, pack at **21.59 V**:
clean air with no cycle running reads **0.2–0.3 mV steady** on the `mV wander` reading, and
does not climb. That closes the loop on the v1.52 diagnosis — the same rig and the same
setting read ~10 mV and creeping under v1.51, which was a Training air reference roughly
200 s old being displayed as a live deviation, not the detector.

Two things worth recording beyond the fix.

**The Detect margin is wider than assumed.** 0.2–0.3 mV against the working Detect of
0.5 mV is a factor of ~2, and better than the ~0.8 mV predicted from the §17.2 50 µV/s drift
rate over a 50-frame (~16 s) window. Either the settle window in use is shorter than 50
frames, or drift at this operating point is below the §17.2 figure — that figure is a
pre-enclosure number on the §14 re-measurement backlog. Not separated here.

**Pack was at 21.59 V.** §17.10's regulation result — coil drive constant, state of charge
not reaching the operating point — is measured down to 23.05 V, and §12's working floor is
21.0 V. A clean, steady air reading at 21.59 V is consistent with regulation still holding
most of the way to that floor, but **it is not the same measurement**: §17.10's evidence is
the direction of per-band delay shift under a falling pack, and air wander is drift plus
noise over one window. It does not extend the regulated-window result on its own. The
outstanding check remains the unmeasured pulse-instant rail sag (§12). (2026-07-28)

---

### src/data/targets/targets_v3.csv — registry — solder stick added

New row `Sn_Pb_solder_stick_01` — solder stick, `rod`, 145 × 8 × 8 mm, solid (`wall_thickness_mm`
0), `closed_loop` n, `magnet_test` none, `material_class` solder_sn_pb. **Mass 56 g, weighed**
— it was first entered as a 62 g geometric estimate (a ø8 × 145 cylinder at the
`pimd_target_check.py` table density of 8.5 g/cm³) and that placeholder is now replaced by
the measured value.

Noted, not acted on: 56 g over the 7.288 cm³ cylinder volume implies **7.68 g/cm³**, against
the 8.5 the registry's density table carries for `solder_sn_pb` — which is what the
mass-plausibility check tests against. It stays well inside the check (the solid *bounding
box* at 8.5 is 78.9 g, and the row passes with 0 errors), so nothing is flagged. The gap is
about 10 %, consistent with a higher-tin alloy than Sn60/Pb40 — pure tin is 7.31, Sn96/Ag
7.4 — or with a stick slightly under its nominal 8 mm. Alloy is unconfirmed; the registry
records the object as `solder_sn_pb` on the owner's identification, and the measured mass
governs regardless. (2026-07-28)

---

### src/pimd_classviz.py — v1.53 — auto-start at launch; gauge row spacing; np.bool_ warning

**Auto-start.** The app now connects and runs the remembered profile on launch, instead of
waiting for Connect and then Load & Run — two clicks that were the invariable opening move
of every session. `_autostart()` fires from a `QTimer.singleShot(0, …)` in the constructor,
so the window is up and the event loop running before any serial I/O, then defers the
profile send by `AUTOSTART_PROFILE_MS` (600 ms) so the `D`/`Q`/`G` burst does not race the
`E`/`V`/`Q4` connect handshake — the same beat an operator leaves between the two clicks.
Nothing is forced: no remembered port, a port that will not open, or no remembered profile
each leave the app sitting exactly as it did before, with the reason in the status bar and
the Connect button reddened by the existing `connect_port()` path.
`_autostart_run_profile()` re-checks the port because the operator can disconnect inside the
delay window.

**Gauge row spacing.** The gauge column's row spacing goes 1 px → 8 px. With the v1.52
two-line rows (name over readout) against a boxed plot, 1 px ran the five rows together into
a single block and left the eye hunting for the boundaries. Analysis row 1 opens at 320 px
to fit five 46 px rows plus the new gaps and the group title.

**`np.bool_` DeprecationWarning.** `_set_gauge()` computed `has_value` as the bare
`np.isfinite(value)` result — an `np.bool_`, not a `bool` — and fed it through to
`QGraphicsItem.setVisible()`, which takes it as an *index*. NumPy warns on that, and at the
~30 Hz redraw rate across five gauges it was thousands of `DeprecationWarning` lines per
session on the console. Wrapped in `bool()`. A scan of every `setVisible`/`setEnabled`/
`setChecked` call site for other numpy-bool leaks found none.

**Also fixes a defect in v1.52 (never committed, caught on the render).** The Detect gauge
painted its verdict `good_above=True` in both modes, so quiet air — 0.049 mV of wander
against a 1.0 mV Detect, the *ideal* state — rendered red. The verdict direction has to
follow the mode, because "good" does: gated, dev at or above Detect means the target
registered; in wander mode the air moving *less* than Detect is what you want, because that
is the trigger level clearing the noise floor, which is the entire reason to look at the
row. Now `good_above=gated`.

Verified offscreen: the v1.52 suite re-run under `-W error::DeprecationWarning` passes, which
is the warning fix under test rather than eyeballed; new assertions cover all four
verdict-direction cases (quiet air green, air past Detect red, gated dev under Detect red,
gated dev over Detect green); a new autostart suite covers no-port, unopenable-port,
disconnected-inside-the-delay and no-saved-profile degradation plus the happy path, asserting
the exact command sequence `E,V,Q4` then `E, D…, Q5, G` onto `cal_63_air_bat_v3`. Both gauge
columns re-rendered and inspected. **Auto-start is not yet exercised against the board** —
the 600 ms handshake gap is reasoned from the manual click cadence, not measured; if the
first frames arrive on the wrong profile, that constant is the thing to raise. (2026-07-28)

---

### src/pimd_classviz.py — v1.52 — FIX Detect gauge read a stale air reference; Air age gauge

**Bench report:** the v1.51 Detect gauge read ~10 mV in clean air with no target and crept
steadily higher, against a Detect setting of 0.5 mV that has always worked. Settle read
0.2 mV σ at the same time. Diagnosed as a display fault, not a detector change.

`_current_dev_from_air()` measures mean per-channel |Δ| against `_sig_air_ref`, the leading
air a Training cycle locked. That reference is cleared on Start Training, Stop and
timeout-abort — but **`_sig_finish_air_trail()` never cleared it**, so after a normal cycle
completion it survived into the next cycle's `air_lead` and kept ageing. Harmless while
nothing read it: the state machine consults dev only in `await_target`/`await_remove`, both
entered from `_sig_lock_leading_air()` and so always against a fresh lock. v1.51 then put
the number on screen and called it every redraw regardless of phase.

DESIGN §17.10 already quantifies the result: at the §17.2 ~50 µV/s rate an air reference
accumulates 0.5 mV/cell at 10 s, 3.0 mV at 60 s, 7.5 mV at 150 s. **10 mV ⇒ a reference
about 200 s old.** Settle at 0.2 mV σ corroborates it — the rig is quiet frame to frame, so
that was a slow ramp, not noise. "Sometimes it behaves as previously" fits too: straight
after a Space lock, or after an abort/Stop, the reference is fresh or `None`. Detect 0.5 mV
was never wrong and the placement path is unchanged.

Three fixes. **(1)** `_sig_finish_air_trail()` now clears `_sig_air_ref` — the reference dies
with its cycle rather than being routed around. **(2)** The Detect gauge picks its source by
phase (`_sig_dev_is_gated()`): in `await_target`/`await_remove` it shows
`_current_dev_from_air()`, the very number being tested; everywhere else it shows a new
`_current_air_wander_mv()` — mean per-channel |Δ| between the current settle window and the
one immediately before it. Same reduction and units, so it is directly comparable to the
Detect setting, but it reads the drift *rate* rather than an accumulating total: a planted
0.05 mV/s ramp holds steady at ~0.48 mV instead of climbing without limit. The unit text
names which is on screen (`mV vs air` / `mV wander`) — reading "vs air" when nothing was
locked was the whole confusion. `_current_dev_from_air()` is deliberately **not** refactored
into a shared window helper: it is on the state machine's gating hot path, and a few
duplicated lines are cheaper than touching it. **(3)** New fifth gauge, **Air age**, with
`_sig_air_ref_ts` recorded at the lock. Read-only marker (binding `None` — the limit is
derived, not a setting) at the drift budget `Detect / AIR_DRIFT_MV_PER_S`, the age at which
thermal drift alone equals the Detect threshold. New module constant
`AIR_DRIFT_MV_PER_S = 0.05` carries the §17.2/§17.10 citation so the figure is auditable.

**Flagged, not changed.** `_sig_train_ingest()` detects target *removal* by the same
magnitude test against the leading-air reference, which by then is a whole
target-collection window old. §17.10 measured this head-on — "a spanner @60 mm reads |Δ|
2.8 mV while 150 s of drift reads 5.2 mV, so removing the object makes |Δ| go up. No
magnitude test against a frozen reference can detect removal, which is why auto-release was
abandoned by direction." That is a plausible mechanism for removal timeouts and it predates
v1.51 (v1.34+). Left alone: the 30 s guard and Space override are the existing fallback, and
this wants a bench observation before a design change. The Air-age gauge is what will show
whether it is actually biting — if the age marker is red before the target comes off, the
removal test cannot succeed on that cycle.

Layout, both gauge columns: the numeric readout moved from its own column right of the bar
to a second line under the row label, which gives every bar ~110 px back (~130 px → ~230 px
at a 300 px column) and stops the tick labels colliding. One uniform left-block width still
keeps all the bars starting at the same x, now measured on the whole two-line block rather
than the label alone; the separate unit-width pass is gone since nothing follows the bar.
Analysis row 1 opens at 300 px for the fifth row.

Verified offscreen (no board): flat air reads 0.04 mV wander and stays there; a planted
0.05 mV/s ramp reads 0.48 mV steady across three window-lengths rather than accumulating —
the reported regression, inverted into a test; the unit text and value switch to
`_current_dev_from_air()` in exactly `await_target`/`await_remove` across a full phase walk;
a planted +4 mV step reads 4.008 mV against the locked reference; Air age reads its age with
the marker tracking `Detect/0.05` and flipping green/red about it; `_sig_finish_air_trail()`
leaves both reference and timestamp `None` and Air age at `—`; all v1.51 checks (drag
write-back, clamping, spinbox→marker, Family Plane values) still pass. Both columns rendered
and inspected. **Not yet run on the bench** — item 7 of the plan (clean air must read
~0.8 mV steady, not 10 and climbing) is the confirmation. (2026-07-28)

---

### src/pimd_classviz.py — v1.51 — Analysis-tab Trigger Levels gauges (draggable thresholds)

New **Trigger Levels** column on the Analysis tab, leftmost in the top-right pane
(`row1_split`, left of Band Mean vs Time): four bar gauges — **Settle · Detect · Amp ·
SNR** — each with a dashed threshold marker you can **drag** to set the underlying
spinbox. The Training group's two auto-detect gates were previously set blind. Their
metrics drive the state machine every frame but were never plotted; the only visible
number was a settle reading smuggled into the status-label text (`SETTLING air — 0.412
mV`). Picking a level meant guessing, running a cycle, and watching it stall or
false-trigger. Now the bar shows the live quantity, the marker shows the gate, and the
gate is dragged to wherever the noise stops.

Settle and Detect read the *exact* helpers `_sig_train_ingest()` gates on —
`_current_settle_mv()` (Stats-tab window) and `_current_dev_from_air()` — so the bar
crossing the marker and the cycle advancing are one event rather than two things that
ought to agree. That mattered: a straight copy of the Family Plane column would have been
wrong twice over. Its `Settled` gauge uses the *Shape* window (`sp_shape_win_n`, 15
frames), not the Stats window (50) the training gate applies, so the displayed number
would not have been the gated number; and its `Amp ‖Δ‖₂` is a different quantity from the
mean per-channel |Δ| that Detect compares against, so a Detect marker on the Amp bar
would have been numerically meaningless. Hence Detect is its own row and the
Family-Plane-only `Air age` row is dropped.

Amp and SNR are context, not gates, and are measured against the Training cycle's **locked
leading air** (`_sig_air_ref`) over the Stats window — new `_analysis_gauge_features()`,
via `_shape_live_window(ref=, n_win=)`, which gained those two optional arguments and
defaults to its previous behaviour for every existing caller. Without that they would have
come from `_shape_live`, whose reference is the Family Plane's own and is *rolling* unless
Space was pressed on that tab, so both would have sat at ~0 here. They still fall back to
`_shape_live` before a cycle locks a reference. Their markers move
`sp_sig_q_amp_mv` (log₁₀ axis, so a dragged position goes back through `10**x`) and
`sp_shape_gate`.

Implementation is a shared column, not a clone: `_build_shape_gauges_dock` /
`_shape_set_gauge` were generalised into `_build_gauge_column(specs, store, value_w)` /
`_set_gauge(store, key, …)`, and the Family Plane keeps its four gauges as read-only specs
(`binding=None`). A spec's binding is `(spinbox_attr, to_axis, from_axis)` — the spinbox is
named rather than passed because the Analysis column is built before the Family Plane tab
exists, so `sp_shape_gate` cannot be resolved at build time. Two guards keep a drag from
fighting its own redraw: `_set_gauge` skips repositioning a line while `gate.moving`, and
`_gauge_marker_drag` suppresses the re-render triggered by the spinbox's own
`valueChanged`. Dragged values are clamped to the spinbox range, rounded to its decimals,
and the line is snapped to where the spinbox actually landed; `setBounds()` keeps a line on
its own axis. A draggable gate stays visible with no reading (Detect has none until a cycle
locks air — exactly when you want to pre-position it), while a read-only gate still hides
with its value, so Family Plane behaviour is unchanged.

Bar axes here are anchored on the **threshold** (`_gauge_hi`: `max(2×thr, 1.25×value,
0.2)`), not on the reading the way the Family Plane's settle gauge is (`max(value*2,
1.0)`) — a value-scaled axis slides the marker around under the cursor, and here the marker
is the control being grabbed.

Cosmetic, applied to both columns: row labels and unit suffixes are each given one uniform
width, so every bar starts and ends at the same x. Per-row minimums could not do this — the
widest name shortened its own bar and a unit-less row (`SNR`) ran 46 px longer than its
neighbours. Analysis row 1 now opens at 260 px tall rather than 220 (four 46 px gauge rows
plus the group title need ~210; at 220 they opened squashed to their 26 px minimum), and the
row-1 splitter sizes persist as `analysis_row1_split_sizes` alongside the existing left-split
entry.

Verified offscreen (no board) against synthetic frames: Settle matches
`_current_settle_mv()` to 3 d.p.; Detect stays `—` with no `_sig_air_ref` and then tracks a
planted 3.0 mV step; verdict colours flip green/red about the marker; drags write back
through both transforms (Amp to `10**pos`, not the raw log) and clamp at the spinbox
minimum and the axis bound; typing into `sp_sig_settle_mv` / `sp_shape_gate` moves the
marker the same frame; and the Family Plane column still renders and updates. Not yet
exercised on the bench — the coincidence of Detect crossing its marker with the cycle
advancing to `ACQUIRED target` is the check to make there. (2026-07-28)

---

### src/pimd_target_check.py — v4 — CLI requires `-f`; `wall_thickness_mm` 0 = solid

The CLI no longer defaults its registry path: `-f/--file` is now required (`--registry`
kept as an alias), so `python pimd_target_check.py` with no arguments is a usage error
instead of a silent check of whichever file the default happened to name. With several
registry versions on disk that default had become a trap — it still pointed at
`targets_v1.csv` while the live registry had moved to v3, so a clean run said nothing
about the file actually in use. Relative paths resolve against the current working
directory as usual (`-f data/targets/targets_v3.csv` from `src/`), and the run now prints
the absolute path of the registry it loaded before the table.

`wall_thickness_mm` gained an explicit "solid / not applicable" value of **0**, replacing
the `na` the v3 registry carried (which the tool rejected outright as unparseable) and the
empty cell v1 used. Both legacy spellings are still accepted and normalise to `0.0`, so
older registry files keep loading, and the column is now always a float — `Target.
wall_thickness_mm` is never `None`. The shape-mismatch warning fires on `> 0` rather than
"is set", so a solid `plate`/`disc`/`bolt` no longer trips it just for carrying the
sentinel; a negative wall is a new error.

`DEFAULT_REGISTRY_PATH` repointed to `targets_v3.csv`. It remains the single source of
truth for the *library* default, so `pimd_classviz.py` (`TARGETS_REGISTRY_PATH`),
`pimd_features.py` (`--registry` default) and `pimd_corpus_check.py` (no-arg
`load_targets()`) all follow it onto v3 unchanged — only the CLI lost its default.

Verified: all four PC tools `py_compile` clean; `-f` missing exits 2 with usage; v3 loads
26 targets / 0 errors / 2 pre-existing warnings (`ferrite_toroid_01` closed_loop, and
`Fe_heavy_pully`'s 66 mm wall on a `disc`); v1 still loads clean with its 12 blank walls
normalised to `0.0`; planted `abc` and `-2` walls both error. Note for downstream:
`pimd_features.py:745` writes `wall_thickness_mm` as `''` when `None`, which can no longer
happen — solid targets will now appear as `0` in newly built corpus CSVs rather than
blank. (2026-07-26)

---

### src/data/targets/targets_v3.csv — registry v3 — re-exported from UTF-7, data fixes

New registry revision (solder roll changed; rocks, quartz piece and water bottle added;
existing rows reviewed). The LibreOffice export had been written with the character set
left on **Unicode (UTF-7)**, so every `_`, `-`, `#`, `"`, `—` and `>=` in the file arrived
as a `+AF8-`-style modified-base64 escape — `targets+AF8-v3`, `dim+AF8-a +AD4APQ-
dim+AF8-b`. Decoded in place with `iconv -f UTF-7 -t UTF-8`; row count and content
otherwise unchanged. LibreOffice remembers the last charset used, so the export dialog
needs setting back to UTF-8 on the next Save As or this recurs.

Data fixes in the same pass: header typos (`reviwed`, `measuremnents`) and a duplicated
`dim_a >= dim_b >= dim_c.` cell on the units line; `Quartz_piece_01` had a shifted row —
`dim_c_mm` empty with its `40` sitting in `wall_thickness_mm` — corrected to
`60,50,40`; `material_class` for `Quartz_piece_01` and `Sandstone_rock_01` set from `?`
to `mineral`. All 37 lines now parse to exactly 13 fields and every row satisfies the
header's sorted-bounding-box invariant.

`wall_thickness_mm` migrated from `na` to `0` for the 15 solid targets, matching the
sentinel `pimd_target_check.py` v4 now understands; the header comment block documents
`0 = solid / not applicable`.

`Fe_heavy_pully` reclassified `disc` → `ring`, which was the last registry warning. Its
66 mm `wall_thickness_mm` was flagged as being set on a shape the registry treats as
solid, but the measurement is right — the pulley has a real bore and 66 is the radial
wall, `(150 − 18) / 2`. So the row was a shape misclassification, not a bad number: a
shape carrying a radial wall is a `ring`. That matches the three existing `ring` rows
(`Cu_Zn_brass_gear_01`, `ferrite_toroid_01`, `Fe_SS_shackle_01`), which all pair a radial
wall with `closed_loop=y`, and the mass agrees (a steel ring OD 150 / ID 18 × 28 is
3829 g against 3700 g measured). Dims were never at issue — `dim_a = dim_b = 150`,
`dim_c = 28` is the correct bounding box, same convention as the pipe rows.

Left alone deliberately: `Fe_heavy_pully` misspells "pulley" in both `short_name` and
`target_id`, and ids are stable by the registry's own rule — renaming one would orphan
any capture referencing it. Flagged, not changed: `closed_loop=y` is kept on the pulley,
which reads the flag as "supports a large circulating eddy-current path" rather than the
header's written rule (a bore comparable to object size; an 18 mm bore in a 150 mm body
doesn't meet it). Under that broader reading `Fe_Cast_iron_trivet_01` and `Fe_SS_disc_01`
are arguably mislabelled `n` and the header wording needs updating — a registry-wide
semantics decision left for a separate pass. (2026-07-26)

---

### repo — `cal_63_air_v2` retired; `cal_63_air_bat_v3` is the sole operating profile

`cal_63_air_v2.json` untracked (`git rm --cached`, still on disk) and added to the superseded
list in `.gitignore`, restoring the one-tracked-profile-at-a-time rule from the 2026-07-23
hygiene pass. From here everything runs under battery on `cal_63_air_bat_v3` — v2 is the
previous supply epoch and is no longer a thing new work should be anchored to.

Nothing in the code loads a profile by name, so this is a tracking change only: delaycal's
Import Profile and Compare Profiles both scan `data/profiles/*.json` off disk, so v2 stays
available as a comparison reference for as long as the file is kept. One stale reference
corrected — `pimd_shape.py`'s `default_band_ranges()` docstring named v2 as "the 7-band
operating profile"; the band plan is common to v2 and v3, so the derived early/mid/late split
is unchanged and only the naming needed updating (comment only, no version bump).

Note for corpus work: `gui_signatures_targets_v1_20260723.csv` was captured under v2, so the
only tracked profile no longer matches the only corpus on disk. That is expected across an
epoch boundary and is what the `(profile_name, profile_sha8)` guard exists to catch, but it
does mean a v3 corpus has to be recaptured before the two can be worked with together.
(2026-07-26)

---

### USAGE.md — v1.17 — delaycal v1.28 → v1.29

§4's intent no longer claims exports land at a fixed `cal_<ts>.json` path. New **Export
Profile** bullet: the filename sets the profile's `name`, and `name` — not the filename —
is what corpora record as `profile_name` and what the cross-epoch guard reports, so naming
the file names the epoch. Lists what the generated notes contain and says plainly that the
operator's own conditions (thermal state, soak time, pack voltage) have to be added there or
the calibration isn't reproducible. The Auto Nudge bullet now says its auto-save is
unattended and timestamp-named, with Export Profile as the follow-up step; the Import bullet
notes that notes and filename carry forward. §1 diagram: delaycal v1.28 → v1.29. (2026-07-26)

---

### src/pimd_delaycal.py — v1.29 — profile save dialog and auto-generated notes

Locking `cal_63_air_bat_v3` exposed two gaps in the export path. **Filename:** exports went
silently to `PROFILES_DIR/cal_<sweep timestamp>.json` with `name` set to the same stamp, so
every locked profile had to be renamed by hand afterwards — and renaming the *file* left the
`name` field, which is what `pimd_features.py` records as `profile_name` in every corpus row
and what the cross-epoch guard reports, still holding the stamp. Export Profile now opens a
save dialog (`.json` appended if omitted) and takes `name` from the basename chosen, so the
profile identifies itself by the name it is referred to by. The dialog is pre-filled from the
last save, else the imported profile's filename, else the timestamp.

**Notes:** profiles carried no record of the sweep that produced them. `_compose_notes()`
generates a `notes` field — sweep start → end and duration, sweep parameters (start, coarse
step, fine step, max delay, averages N, signal detect), Auto Nudge parameters (threshold,
step, soak, max iter, mode, std-dev N), the Auto Nudge outcome line, and the geometry — shown
in an editable multi-line dialog before writing so operator conditions (thermal state, soak
time, pack voltage) can be added. Notes and delays with no sweep behind them say so rather
than implying a run. **Carry-forward:** `_import_profile()` keeps the source profile's `notes`
and appends them attributed (`Carried forward from <name>: …`), so the v1/v2-style derivation
rationale survives an epoch change instead of being retyped; since USAGE §4 makes Import
Profile the standard start of a recalibration, this is the normal path.

`_build_profile()` gains optional `name`/`notes`; called bare (Compare tab, thermal, Auto
Nudge) it behaves exactly as before and emits no `notes` key. Field order is `name, notes,
averages, bands`, matching the hand-written v1/v2 profiles. `export_profile()` gains
`interactive`: the Auto Nudge completion save passes `interactive=False` and keeps the old
unattended timestamped behaviour — a finished long run must not block on a modal dialog —
and logs a pointer to Export Profile for the named save. The Export Profile button is
connected through a lambda because `clicked()` would otherwise pass `checked` into
`interactive`.

Exercised headless (offscreen Qt) against the real profiles: import of `cal_63_air_v2`
carries its 641-character notes forward attributed; a simulated completed sweep renders the
timestamp/duration line; interactive export writes the chosen basename into `name` with
operator text appended; both cancel paths (file dialog, notes dialog) write nothing;
`_build_profile()` bare still returns the three original keys. (2026-07-26)

---

### src/data/profiles/cal_63_air_bat_v3.json — v3 — new locked profile: battery supply epoch

New epoch **v3**, marking the move from bench PSU to the 6S 16650 battery pack. Locked
profile `src/data/profiles/cal_63_air_bat_v3.json`.

**Band plan is unchanged from `cal_63_air_v2`** — 7 bands (9 → 100 µs), 63 cells, verified
band for band. **The threshold ladder is not:** it moves in one position, to
4.9 / 4.8 / **4.75** / 4.4 / 4.2 / 3.8 / 2.4 / 1.5 / 0.5 V against v2's 4.70 in third place.
The 4.70 column started misbehaving after ~30 minutes in classviz, so the profile was
re-swept with that step raised. Of the 4.75/4.35/3.70 ladder trialled on 2026-07-24 only the
4.75 step is adopted — 4.40 and 3.80 keep their original values, having come back clean under
battery power. The two are unrelated observations: that trial's 4.40/3.80 elevation was
supply-borne (see the §14.7 entry below), this 4.75 move is separate and later.

Delays re-anchored for the supply change: **+40…+144 ns** against v2, band means +90 ns
(100 µs) to +125 ns (30 µs). The third column is the outlier at +40…+72 ns and is **not** a
like-for-like delta — that cell targets a different voltage, so its shift is threshold move
plus supply change, and the two are not separated here.

So this is **both a new calibration epoch and a threshold-geometry change**, which is weaker
than a clean epoch change. Corpora stay in separate files and the
`(profile_name, profile_sha8)` guard still hard-errors across them; cross-epoch comparison is
interpretable for the eight columns whose target voltage is unchanged, but the third column is
not comparable to v2's even feature-wise. That is exactly the §13 feature-level-portability
question the 1.10 consolidation deferred, now live rather than hypothetical.

Calibration conditions: pack 23.5 → 23.35 V, [FILL: thermal state / soak time].

**Revised delaycal parameters** (record these — without them the calibration isn't
reproducible): fine sweep 80 → 40, autonudge threshold 0.5 → 0.3 mV, nudge step 16 → 8 ns,
soak 20 → 40 s, std dev n = 16.

**Profile `name` corrected before locking.** As exported, the internal `name` field carried
the sweep stamp `cal_20260726_122638` rather than the filename — and that field is what
`pimd_features.py` records as `profile_name` in every corpus row, so it is the epoch identity
the cross-epoch guard reports. Set to `cal_63_air_bat_v3` to match the filename and the v1/v2
convention. The underlying trap — delaycal naming every export after the sweep timestamp, so
this needed correcting by hand at every lock — is fixed in delaycal v1.29 above.

**`notes` field written**, matching the v1/v2 convention (v3 as exported had none): epoch and
lock date, fw v4.26, pack voltage across the sweep, the 4.70 → 4.75 change and its reason,
what is and is not unchanged from v2, the re-anchoring figures with the third column called out
as not like-for-like, the sweep and Auto Nudge parameters, the 0.3 mV convergence result, the
grid-step thermal criterion, and the corpus rule. Recorded honestly as unknown: thermal soak
time at lock, and the originating cal-run stamp for the re-sweep.

All three edits (rename, notes, re-sweep) landed before any corpus was captured under v3, so no
existing capture is invalidated by the `profile_sha8` changes they cause. Final `profile_sha8`
for the locked file: **`4a2352d2`**. (2026-07-26)

---

### findings — battery supply lowered the achievable convergence threshold

The headline result of the epoch change. **Convergence at a 0.3 mV autonudge threshold was
never achievable under the bench PSU** — repeated attempts in earlier work failed to converge
at that setting, which is why 0.5 mV became the working value. Under 6S battery power the same
sweep converged at 0.3 mV with **only one cell of 63 requiring a single −8 ns nudge**; the
nudge count would often exceed 10 cells before.

Since the autonudge threshold is effectively a measurement of how tightly a cell can be placed
against the noise, this is a direct quantitative statement about the new supply: the floor
improved enough to make a previously unreachable calibration tolerance routine. Contributing
changes, not separated from one another: 6S pack, heavier cabling, ferrite common-mode chokes
on power and USB, 100 nF across the pack. (2026-07-26)

---

### findings — thermal convergence criterion replaces the thermistor check

The TX damping-resistor thermistor is no longer fitted since the shielded case was built, so
the documented "calibrate once the resistor reaches ~80 °C" precondition (§14.1) can't be
applied. Replaced with a direct measurement of the thing it was a proxy for — successive
calibrations compared cell by cell:

- 15 min after the first calibration: differences up to **−24 ns**, concentrated in the
  long-pulse bands.
- Subsequent runs ~10 min apart: **±8 ns in 6 of 63 cells**, all others zero.

8 ns is the PWM grid step, so those six cells are at the quantisation floor and the rig is as
stable as the hardware can express. Working criterion going forward: **converged when
successive calibrations differ by no more than one grid step, watching the 100 µs band**,
which is consistently the most drift-sensitive. Delaycal's Compare Profiles tab (v1.28) is the
tool for this. (2026-07-26)

---

### findings — the elevated threshold columns were supply-borne (partial §14.7 answer)

The 4.40 V and 3.80 V columns that read ~5× the free-air noise floor on 2026-07-24 (with the
bench PSU failed and an interim pack fitted) are **clean under the v3 battery supply**, which
is why **those two steps** could revert to their original values. Confirmed from a Std Dev
(rolling N) heatmap under v3. This narrows §14.7: that elevation was supply-borne, not
intrinsic to the front end or the 1N4732 clamp.

It does not close §14.7 — the original ~4.45–4.65 V keep-out zone is a separate,
longer-standing observation and is unaffected. Nor does the ladder revert wholesale: the third
step went to 4.75 V in the re-sweep after the 4.70 column misbehaved past ~30 minutes in
classviz, which is a *different* symptom on a different column and is not addressed by this
finding. [FILL: is the 4.70 misbehaviour drift into the ~4.45–4.65 keep-out zone as the rig
warms — i.e. the §14.1 fingerprint — or a fresh mechanism? A Std Dev heatmap on the old 4.70
cell after a 30 min soak would separate them.] (2026-07-26)

---

### USAGE.md — v1.16 — delaycal v1.25 → v1.28

Follows the three delaycal changes below. §4's Sweep sub-bullet now says the fine step is
set in ns down to the 8 ns PWM grid (100 ns default) rather than "0.1 µs"; the Thermal
sub-bullet notes it auto-starts on sweep completion and why that matters; and a new
Compare Profiles sub-bullet covers the tab — what a row is (same band, same intended
target V), the Δ-in-ns colouring against the grid, and the fact that the measured voltages
come from this session's soaks and do not survive a restart. §1 diagram: delaycal v1.25 →
v1.28. (2026-07-26)

---

### src/pimd_delaycal.py — v1.28 — Compare Profiles tab

There was no way to see how a freshly-swept profile differs from an earlier one short of
exporting the JSON and eyeballing it. A second tab now answers the question that actually
matters — **timing convergence**: for every cell the two profiles share, how far apart are
the delays, and does that gap move the measured voltage?

The window's content moved into a `QTabWidget` ("Calibration" / "Compare Profiles"); the
top bar (port, Run, Stop, exports) stays global above the tabs, and splitter/geometry
persistence is untouched. Two selectors list `data/profiles/*.json` plus a
`<current calibration table>` entry backed by `_build_profile()` — so a sweep can be
compared against a reference without exporting first, which is the point of doing this
in-app rather than as a CLI. The list rescans on tab activation.

Cells are matched on `(freq_hz, pulse_us, threshold_v)` — **matched rows only**, so every
row is a genuine like-for-like comparison at the same intended target voltage. Columns:
cell ident, target V, both delays (µs, 3 d.p.), **Δ in ns**, both measured voltages, their
difference in mV, and each profile's error against the intended target. The Δ cell is
coloured against the PWM grid — green within one 8 ns step, yellow within five, red
beyond — reusing the existing palette. A footer carries matched count, mean/RMS/max |Δ|
with the worst cell named, how many cells are measured on both sides, and a named list of
cells present in only one profile. Degenerate cases (unloadable profile, empty current
table, same profile twice, no shared cells) each set an explanatory footer instead of
rendering an empty table. The comparison exports to CSV.

Profiles store only `delays_us` and the intended `threshold_v` — no measured voltage — so
the voltage columns come from a new in-memory `_meas_cache`, keyed on `(freq_hz, pulse_us,
delay_ns)`. Keying on the physical cell rather than on a filename means a saved profile
whose delays match a run that was streamed this session picks its measurements up for
free. `_capture_measurement()` fills it at the end of every THERMAL run and every Auto
Nudge soak, averaging the last `Std dev N` frames rather than the single latest frame so
the value has settled. With v1.27 auto-starting THERMAL, a fresh sweep is measured without
asking. Cells never streamed show `—` on a grey background; nothing is fabricated.

Exercised headless against the real `cal_63_air_v1/v2` profiles: 63 matched cells, deltas
hand-checked against the JSON, mean |Δ| 17.0 ns / max 56 ns; voltage columns populate from
an injected capture and stay `—` where no measurement exists; CSV round-trips; all four
degenerate cases produce their message. (2026-07-26)

---

### src/pimd_delaycal.py — v1.27 — THERMAL auto-starts on sweep completion

A finished sweep left the board idle until THERMAL was pressed by hand, which also meant
the cells were never measured unless someone remembered. `_finish()` now starts thermal
monitoring itself, gated on a new "Auto on completion" checkbox beside the THERMAL button
(default on, persisted as `auto_thermal`). The call sits after the existing button/label
updates so `_start_thermal` gets the last word on button state, and is additionally gated
on the port being open; `_start_thermal`'s own guards on `_fp_pairs`/`_targets_v` are
unchanged. Nothing new goes to the wire — it is the same `E`/`D`/`Q`/`G` sequence the
button has always sent. Beyond saving the keypress this feeds the v1.28 measurement
cache, so every fresh profile arrives with its measured voltages. (2026-07-26)

---

### src/pimd_delaycal.py — v1.26 — fine step in ns, down to the 8 ns grid

The fine sweep step was a µs spinbox with a 0.01 µs floor — 10 ns, which is both off the
8 ns RP2040 PWM grid and unable to reach a single grid step. It is now a `QSpinBox` in ns:
range 8–5000, 8 ns increments, displayed with a ` ns` suffix, matching the existing
`sp_auto_nudge_ns` control. The sweep still carries `_step_size` internally in µs
(converted once in `run_calibration`), so the coarse/fine phase decision, the step-count
rebase after a coarse back-up, and the delay reconstruction are all untouched.

Settings persistence moves to a new `step_ns` key. The old `step_size` key held µs, and
loading `0.10` straight into a ns spinbox would clamp to 8 ns and silently change how a
sweep runs, so `_load_settings` migrates a `step_size` value by ×1000 when `step_ns` is
absent. Verified on the real settings file: a stored `0.08` µs comes back as 80 ns.
(2026-07-26)

---

### USAGE.md — v1.15 — below-gate frames leave no trail

Follows classviz v1.50. §5's SNR-gate sub-bullet now says a below-gate frame leaves no
trail at all rather than a yellow one, and notes that every frame still ages the trail
window along, so holding below-gate fades the trail out. §1 diagram and §5 heading:
classviz v1.49 → v1.50. (2026-07-25)

---

### src/pimd_classviz.py — v1.50 — below-gate frames leave no trail at all

v1.45 coloured trail points by their own SNR, yellow below the gate and green at or
above it. The yellow half is now dropped entirely: **a below-gate frame leaves no mark**,
so the trail draws only the part of a sweep that was worth reading and is green by
construction. Below the gate the unit shape is normalised noise that still wanders the
plane convincingly, and a trail drawn through it says "the target moved this way" about
a frame carrying no target — the same reasoning that already draws below-gate captures
hollow.

Two details that make it behave well on a real sweep. Below-gate frames still enter the
buffer and still **age the trail window along**, so a surviving mark keeps fading as
they push it back and holding off-target fades the whole trail out within `Trail`
frames — rather than freezing the last good pass on screen at full brightness, which is
what re-basing the fade on the drawn subset would have done. And membership, like the
cursor's colour, is decided against the **current** gate rather than the `gated` flag
stamped at ingest, so moving the SNR gate spinbox re-selects the trail already on
screen instead of only affecting later frames.

The live cursor is unchanged: still yellow below the gate, green at or above it. The
gate test moved out of `_shape_live_colour()` into `_shape_above_gate()`, which both
now share. The tab's header comment and the SNR-gate and Trail tooltips follow.

Exercised headless: a sweep of SNR 2→12→1.5 draws 4 of 10 frames, all green, with
alphas reflecting their true age in the window; an all-below-gate buffer draws nothing
while the cursor still shows yellow; an all-above-gate buffer draws every frame; three
good frames followed by five below-gate keep their three marks but at faded alpha; and
sliding the gate 5.0 → 3.0 → 1.0 → 20.0 re-selects 2 → 3 → 4 → 0 spots from an
unchanged buffer. (2026-07-25)

---

### USAGE.md — v1.14 — classviz v1.49 version references

Follows classviz v1.49. Version references only — §1 diagram and the §5 heading. The
custom band range behaves as §5 already described it; nothing user-facing changed.
(2026-07-25)

---

### src/pimd_classviz.py — v1.49 — FIX the custom band pair was lost on restart, clamped by the startup profile's narrower spin range

**Bench report:** the Family Plane's Y custom band range, set to 4–6, comes back as
4–4 after a restart. The settings file was innocent — it held `shape_band_y_hi: 6`
correctly. The restore was destroying it.

The band spinboxes are ranged `0 .. n_bands-1` of the **live** profile. At
`_load_settings()` time the app is still on the built-in startup profile
**CLASSIFY_EP, which has 5 bands**, so the spins are ranged 0..4 and
`setValue(6)` silently clamps to 4 — QSpinBox does that without complaint.
`_rebuild_shape_axes()` later widens the range to 0..6 when the real 7-band profile
arrives, but by then the value is 4 and there is nothing left to widen it back from.
The X pair survived only because 0..2 happens to fit inside 0..4, which is why this
looked like a Y-specific fault.

Worse, and the half that would have kept biting: `_save_settings()` wrote the
**spinbox**, so merely launching the app and quitting — without ever loading the
7-band profile — overwrote the saved 6 with the clamped 4. One clean start was enough
to lose the setting permanently.

The chosen pair is now held as a **preference** in `_shape_band_pref`, separate from
what the spinboxes are currently able to represent. `_load_settings()` records the raw
saved integers (after the `setValue` calls, which fire the range handler and would
otherwise overwrite it with the clamped values); `_rebuild_shape_axes()` re-applies the
preference clamped to whatever the live profile can show, so the pair reappears in full
the moment a wide enough profile lands, and clamping stays display-only; and
`_save_settings()` persists the preference rather than the spinbox. An operator edit
replaces the preference for **that pair only** — the shared range handler is scoped to
the edited pair, so adjusting X can no longer collapse a Y pair that is sitting clamped
under a narrow profile.

Exercised headless against a copy of the real settings file: the Y pair restores to 4–6
once the 7-band profile lands, a save taken from the 5-band startup profile still
writes 4–6, an operator edit to Y updates only Y's preference, a subsequent edit to X
leaves Y's alone, and the whole lot round-trips. (2026-07-25)

---

### USAGE.md — v1.13 — no gridlines on a rank axis

Follows classviz v1.48. §5's **Scale** sub-bullet gains the rank-axis grid rule and the
note that the two zero rails follow the spacing curve. (2026-07-25)

---

### src/pimd_classviz.py — v1.48 — Family Plane: no gridlines on a rank axis; the zero rails follow the spacing curve

**No gridlines on a rank axis (bench request).** Under the other scales a gridline
still marks a real feature value at its real position, so it stays. A rank axis is
ordinal — a grid over it draws a metric that is not there. Applied **per axis**, since
the scales are: rank on Y alone keeps the vertical gridlines. The two zero rails stay
in both cases; they are the family decision boundary, which is exactly the reference
worth keeping when the grid goes.

**The zero rails were in the wrong place under any curve.** They were static
`InfiniteLine`s pinned at *plot* coordinate 0, added at build and never touched — but a
v1.47 spacing curve maps the *feature* value 0 to wherever it falls between the drawn
min and max, which is generally not 0. On the 2026-07-23 corpus with X = custom bands
0–2 the X rail belonged at +0.064 under rank and −0.012 under cube, against the 0.0 it
was drawn at: the boundary line was visibly off, and it was off by more the more
skewed the drawn set. They are now held as attributes and repositioned on every static
redraw. A rail whose axis does not contain 0 (log₁₀ amplitude, distance) stays at a
literal 0 and therefore off-view — transforming an off-domain zero would clamp it to
the edge of the plot and draw a boundary where there is none.

**Colliding tick labels thinned.** The v1.47 ticks are round feature values, evenly
spaced in VALUE but not in position, so a curve that compresses the middle printed
−0.050 / 0.000 / 0.050 on top of each other — worst under rank, which is where the
dead middle collapses hardest. Candidates are now kept greedily by priority rather
than left to right, with 0 going in first so it always survives (it is the boundary and
carries a drawn rail). The minimum separation is measured in **pixels** off the
viewbox, because what collides is label text: a fixed fraction of the domain is either
wasteful on a wide dock or still overlapping on a narrow one. The fraction survives as
the fallback for the first pass, before layout has run.

Exercised headless against the real corpus: gridlines follow each axis's own scale
across the six linear/cube/rank combinations, each rail sits exactly where its axis
draws feature 0, an axis whose domain excludes 0 keeps its rail at a literal 0, and the
rank/rank view renders with readable non-overlapping ticks at both a wide and a narrow
dock size. (2026-07-25)

---

### USAGE.md — v1.12 — the Family Plane's per-axis Scale, and what those axes are

Follows classviz v1.47. §5's Family Plane bullet gains a **Scale** sub-bullet (the four
curves, the range-preserving invariant, ticks staying in real feature units, and why
no log is offered) and an **axis** sub-bullet spelling out what a band-range-mean axis
actually is — mean of the unit shape over a band range, hard-bounded at ±1/√(k·n_delays),
with the family colouring read off the signs of those same two numbers, which is why
the middle of the plane is empty. §1 diagram and §5 heading: classviz v1.46 → v1.47.
(2026-07-25)

---

### src/pimd_classviz.py — v1.47 — Family Plane per-axis Scale combo (expand-ends / rank spacing)

**The problem (bench report).** On the family plane both families pile up against
opposite ends of an axis with a wide void between them, so within-cluster structure is
unreadable. Measured on `src/data/corpora/gui_signatures_targets_v1_20260723.csv`
(66 drawn captures, cluster shares over the 55 gated 7×9 ones), Y = custom bands 4–6,
as a percentage of plot height:

| Y scale | non-ferrous | crossover | ferrous | dead middle |
|---|---|---|---|---|
| linear (was the only option) | 17.8 | 30.7 | 7.8 | **47.9** |
| signed log — measured, NOT shipped | 4.4 | 10.4 | 1.7 | 84.6 |
| cube | 36.7 | 38.5 | 20.0 | 14.9 |
| atanh | 39.9 | 17.4 | 33.8 | 14.3 |
| rank | 50.8 | 32.3 | 20.0 | 6.2 |

Two facts explain the squash, and both are in the maths rather than the drawing.
`band_range_mean()` over 3 of 7 bands is a mean of 27 elements of a **unit-L2**
63-vector, so it cannot exceed ±1/√27 = ±0.1925 — and the corpus reaches 0.160, 83% of
that ceiling. The clusters are pressed against a wall. And the empty middle is not a
data gap: `pimd_shape.family()` is read off the **signs of these same two axes**, so
the void is the decision boundary itself.

**A log axis was asked for and is deliberately not offered.** Log expands near zero and
compresses the extremes; here nothing lives near zero and everything lives at the
extremes, so it is exactly backwards — measured above, it drives the dead middle from
48% to 85%. What this data needs is expansion near the **ends**.

**What shipped.** A `Scale:` combo per axis — Linear, Expand ends (cube), Expand ends
(atanh), Rank — on one invariant that makes the rest tractable: *every curve maps the
drawn captures' [min, max] onto itself, and only the interior spacing changes.* So
auto-range is untouched, switching scales never moves the view, and a tick can always
be labelled with its true feature value. Implemented as normalise to [−1, 1] → curve
(t³, atanh(0.999t)/atanh(0.999), or ECDF position) → denormalise, all four verified
monotone and range-preserving against the real corpus.

The whole thing hangs off one seam: `_shape_plot_value()` already fed the capture
spots, the live cursor, the trail and the selection ring, so applying the curve there
needed no other wiring. The domain comes from the **captures only**, never the live
frame — the cursor moves every frame and folding it in would rescale the plane under
itself several times a second — and it spans every *drawn* capture, below-gate ones
included, since those are on the plot too. `rank` interpolates into the drawn set's
ECDF rather than taking a literal rank, so the live cursor and the selection ring,
neither of which is in that set, still land somewhere consistent; out-of-domain values
clamp to the edge rather than going infinite. The air-mode live-dot pin goes through
the curves as well — 0 maps to itself only when the drawn range happens to be
symmetric, which it generally is not.

The `crossing` axis is excluded and its combo greys out: it owns its ticks (the
profile's pulse ladder plus the `≤pos` / `never` sentinel rails) and a second transform
would leave those labels pointing at the wrong rails.

**Axis labelling.** A non-linear axis gets explicit ticks at round *feature* values
placed through the curve, so a tick reading `-0.150` sits wherever −0.150 actually
landed, and the label names the curve (`custom bands 4–6 [cube]`). That forces
`enableAutoSIPrefix(False)` on those axes: pyqtgraph had latched a `(x0.001)` suffix
that now flatly contradicts full-value tick strings. The standing warning in this file
— that the flag does not clear `autoSIPrefixScale` — still holds and is now recorded
as harmless in this case, because that scale only ever reaches `tickStrings()`, which
explicit ticks bypass. Linear axes get the prefix back.

Both selections persist (`shape_scale_x` / `shape_scale_y`). Colour-by continuous
ranges deliberately keep reading the raw linear value: spacing is an axis concern.

Exercised headless (offscreen Qt) against the real corpus with the live profile set to
`cal_63_air_v2`: every curve monotone in the raw value and range-preserving, the table
above reproduced, every tick sitting at the transformed position of the value it names,
a live frame landing exactly where a capture of the same value lands, out-of-range
values clamping without NaN, `crossing` keeping its sentinel ticks and greying the
combo, the SI prefix off on scaled axes and back on linear ones, and both combos
round-tripping through settings. No bench hardware involved. (2026-07-25)

---

### USAGE.md — v1.11 — a scratch save lands on the plane

Follows classviz v1.46. §5's Family Plane bullet gains a **Save Scratch…** sub-bullet:
the capture is plotted the moment it is written, as a **triangle**, and joins the
Analysis tab's signature list under a `△` prefix alongside any loaded corpus rather
than replacing it. The symbol legend in the mixed-geometry sentence changes star →
triangle. §1 diagram and §5 heading: classviz v1.45 → v1.46. (2026-07-25)

---

### src/pimd_classviz.py — v1.46 — a scratch save plots immediately, as a triangle

Saving a scratch capture wrote it to `src/data/scratch/` and nowhere else. The whole
reason for grabbing one — see where this object lands against the loaded corpus —
therefore needed a **Load signatures…** round trip to answer, and that round trip
would have replaced the reference corpus being compared against.

A save now merges the scratch file back into the shared template store under its own
**`scratch`** source. Its own source, not `loaded` or `editable`: `_merge_template_
list()` replaces a source wholesale, so reusing either would silently drop the corpus
the scratch is being compared against. All three now coexist in one list, and scratch
rows carry a `△` prefix the way editable rows carry `✎`. The whole file is re-read
rather than just the row written — the store is keyed per capture and re-reading is
also the only check that what went to disk reads back as a signature; a file that
cannot be re-read says so in the status bar instead of silently plotting nothing. The
new capture is marked auto-check first, so it lands ticked in the Analysis tab's
overlays too, matching the corpus save path (v1.38). The Family Plane scatter draws
every loaded capture regardless of tick state, so the point appears there either way.

**Scratch objects are triangles.** `_SHAPE_SYMBOLS[(live profile, scratch)]` goes
`star` → `t1`. Foreign-geometry scratch stays a diamond, so the geometry distinction
survives; the mixed-geometry banner and the Save Scratch tooltip name the new symbol.

Exercised headless (offscreen Qt, scratch dir redirected to a temp dir, two saves into
one file with a pre-loaded reference capture in the store): both land as triangles
with the reference still a circle, the second save does not clobber the first, the
`loaded` entry survives both merges, and both scratch rows come back ticked.
(2026-07-25)

---

### USAGE.md — v1.10 — the colorbar reads as a range slider; the live cursor's SNR colour

Follows classviz v1.45. §5's **Heatmap colour scale** sub-bullet is rewritten around
what the bar now shows — handles that sit at Min and Max, pale saturation tails
outside them, a domain wider than the window so a handle can be dragged either way —
replacing the v1.44 sentence that called the drag handles and the spinboxes "the same
control" when the handles could not in fact show where the limits were. §5's Family
Plane bullet: the live cursor is described as **yellow below the SNR gate, green at or
above it** rather than flatly "a yellow dot", and the SNR-gate sub-bullet says so too.
§1 diagram and §5 heading: classviz v1.44 → v1.45. (2026-07-25)

---

### src/pimd_classviz.py — v1.45 — FIX the heatmap colorbar's handles never showed Min/Max; live shape cursor and trail go green above the SNR gate

**The colorbar handles could not show the range (bench report).** With **Scale** on
Min 500 / Max 1000, the two handles under the bar sat at the same place they always
sit, showing nothing about the limits just typed. Not a wiring fault: `ColorBarItem`'s
handles are *relative* adjusters, not level markers — `_regionChanged()` calls
`setRegion((63, 191))` after every drag, hard-snapping them back to 25%/75% of the
bar. They encode drag *rate*, not value, so no amount of pushing levels at the widget
would have moved them.

The bar is now an absolute range slider. It is built with `interactive=False` and
driven by our own `LinearRegionItem`: the axis spans a **domain** wider than the
Min/Max window, the two handles sit at the values of Min and Max within it, and the
pale flat tails outside them are the values the scale saturates on. The strip is
painted clipped exactly as the image is (flat below Min, ramp across the window, flat
above Max), written onto the bar pixmap directly rather than through
`setColorMap()` — which would have pushed both the clipped map and the bar's domain
levels into the heatmap image. Dragging either handle writes straight into the
Min/Max spinboxes, rounded to what those spinboxes display so the two can never
disagree.

The domain is the window unioned with the data on screen, quantised, then held between
50% and 90% of the bar — never so wide that a tight window on a Δ field reaching
~500000 µV becomes an unreadable sliver, never so narrow that the handles pin to the
bar's ends with nowhere to be dragged outwards to. It is **sticky**: an existing domain
that still holds the window at a workable size is kept. Refitting every tick would
re-centre the window after each drag and spring the handles back to 25%/75% — the
exact behaviour being replaced. It is also frozen for the duration of a drag, so the
value under the cursor does not move while the window is being dragged, and it is
never taken unrounded off the live matrix, which would walk the axis a pixel a frame.
In **Auto** the bar spans exactly the auto-computed range and the handles are hidden:
there are no tails to show, and a drag would not survive the next tick anyway.

**Live cursor and trail colour the SNR gate.** On the Family Plane scatter the live
cursor and every trail point drew yellow unconditionally. They now draw **green at or
above the SNR gate and yellow below it**, so a sweep shows where the frame crossed
into being worth reading. This is not a family verdict — that still belongs to the
loaded captures the cursor is compared against, and the cursor still takes no family
colour. Colour is re-tested against the gate *as it stands at redraw*, not against the
`gated` flag stamped at ingest, so moving the **SNR gate** spinbox repaints the trail
already on screen. An infinite SNR (splithalf collapsed to zero) reads green; NaN
reads yellow. The Band Curves and Crossing Ladder live markers are unchanged. The
tab's header comment and the SNR-gate tooltip, both of which still described a live
dot that "greys out and stops trailing" below the gate, now match the code.

Exercised headless (offscreen Qt, synthetic 80-frame rolling buffer with two noisy
threshold columns): handles land on Min and Max to within a µV across Std Dev and Δ
modes, a drag writes back and the handles stay put across the following redraw ticks,
the domain holds still while the data moves, the painted strip is verifiably flat
outside the window, Auto hides the handles and leaves the image on the auto range —
and a trail spanning SNR 2→12 colours y,y,y,G,G at gate 5.0, repainting to y,G,G,G,G
at gate 3.0 and all-yellow at gate 20. No bench hardware involved. (2026-07-25)

---

### USAGE.md — v1.9 — the heatmap's Min/Max scale and the remembered signature directory

Follows classviz v1.44. §5 gains two sub-bullets under the Analysis tab: the explicit
**Min/Max** colour scale with the Std Dev reasoning (Auto anchors a rolling-σ field at
0 and flattens it), and the signature dialogs reopening in the last directory used —
with the note that **New file…** deliberately still defaults into
`src/data/corpora/`. §1 diagram and §5 heading: classviz v1.43 → v1.44. (2026-07-24)

---

### src/pimd_classviz.py — v1.44 — Analysis heatmap manual scale is an explicit Min/Max; signature dialogs remember their directory

**Min/Max colour scale.** The Analysis heatmap's manual scale was a single ± half-range
spinbox: symmetric about 0 for the diverging modes, and `(0, val)` for RAW and Std Dev.
That is the wrong window for **Std Dev (rolling N)**, which is where it matters most —
a rolling σ field lives in a narrow band well above zero (quiet cells ~600 µV, a noisy
threshold column ~3000 µV on the bench), so a range anchored at 0 spends most of the
colour ramp on values that never occur and the whole heatmap reads as one shade. It is
now two spinboxes, **Min** and **Max**, both signed and both stepping adaptively (one
fixed step cannot serve a Δ range of ~500000 µV and a σ range of ~500 µV). Unchecking
**Auto** seeds them from the levels currently on screen, so manual mode starts from
what the operator is already looking at rather than a stale pair saved under some
other display mode; the seed is on `clicked`, not `toggled`, so it cannot fire during
`_load_settings` and eat the restored values.

The spinboxes are now the single source of truth in manual mode and are re-applied
every redraw tick. That is safe with the colorbar's drag handles because a drag writes
the dragged values straight back into the spinboxes — what the tick re-applies is what
was just dragged. The mode-dependent floor is gone with the half-range: whether a
scale is symmetric or unipolar is the operator's call now, not a rule inferred from
the display mode. A v1.43-or-earlier settings file has only the old
`analysis_hm_scale_manual`, and migrates to the symmetric `(-half, +half)` pair it
used to mean.

**Signature dialogs remember their directory.** `Load signatures…` and `Open for
editing…` opened on the process CWD every time. They now start in the last directory a
signature file was picked from, persisted as `last_signature_dir` and validated at use
time (not at load — a directory that exists at startup can be gone or unmounted by the
time the dialog opens), falling back to `src/data/corpora/`. Only the directory is
remembered, never a file path: a remembered path is the stale-pointer foot-gun
`_load_settings` already refuses for the editable-file path. **New file…** still
defaults into `src/data/corpora/` regardless — that is where the capture pipeline
expects a corpus, and the last-used directory may well be somewhere a read-only corpus
was browsed from.

Exercised headless with a synthetic 80-frame rolling buffer carrying two deliberately
noisy threshold columns: Auto gives (0, 3657) µV and flattens the field, Min/Max at
(500, 3200) separates the noisy columns; a colorbar drag survives the next redraw
tick; min ≥ max nudges the other spinbox instead of snapping back; and the settings
round-trip, the v1.43 migration and the directory fallbacks all behave. (2026-07-24)

---

### USAGE.md — v1.8 — the fourth tab renamed, and its v1.43 additions

Follows classviz v1.43. §5's tab bullet is renamed **Shape Space → Family Plane
Analysis** (with the old name kept in parentheses, since every §5/§1 reference written
before today says Shape Space) and gains three sub-bullets: material tags and what `?`
means, the per-axis custom band ranges, and that a click on either the plane or the
ladder drives the Tile Inspector. §1 diagram and the §5 heading: classviz v1.42 →
v1.43. (2026-07-24)

---

### src/pimd_classviz.py — v1.43 — Shape Space renamed Family Plane Analysis; material tags, per-axis custom bands, ladder click

**Renamed.** The tab is now **Family Plane Analysis** (`SHAPE_TAB_TITLE`), in the tab
bar, its group box and the status lines it emits. Internal names stay `shape`/`_shape_*`
and `pimd_shape.py` is untouched — the rename is what the operator reads, not a
refactor. The v1.42 entries below, `DESIGN.md` §15/§17.9 and `USAGE.md` §5 all still
say "Shape Space"; they describe the same tab.

**Material on the plane.** Every capture now carries a material tag derived from the
target registry (`material_class`, plus `plating_material` as `base/plating` — `Fe/Zn`
for gal pipe, `SS/Ag` for the plated server). It is drawn beside the scatter point and
appended to each Crossing Ladder row, and added to the hover tip and the Tile
Inspector title in long form. Tags are drawn as text rather than as extra marker
shapes because marker shape is already spoken for: `_SHAPE_SYMBOLS` encodes
(foreign profile, scratch object), and colour encodes family/colour-by. Tag colour
follows the marker, so under colour-by family a red `Al` is visibly a non-ferrous
material reading ferrous — the comparison the tab exists to support. One tag per
(target, distance) group, not per capture, or repeats redraw the same string in the
same few pixels; suppressed above `SHAPE_LABEL_MAX` = 200 drawn points, and behind a
"Material tags" checkbox (persisted). A capture whose `target_id` is not in the
registry reads `?` rather than a guessed material — scratch objects are unregistered
by design and another rig's corpus may carry ids this registry has never seen.

**Custom band range is now per axis.** X and Y have their own inclusive lo/hi spin
pairs. With the single shared pair, selecting "custom band range" on both axes plotted
a feature against itself — every point on the y=x diagonal, which reads as a finding
and is an artefact. Colour-by "custom band range" reads the X pair (it has no third
pair). Axis labels now name the range they are reading (`custom bands 2–4`), since
"custom band range" on both axes says nothing about what is being compared. A v1.42
settings file restores the plane it was drawing: the new Y pair defaults to the saved
X values.

**Ladder points are clickable.** `shape_ladder_points` shares the scatter's
`sigClicked` handler and carries the same `key` payload, so the panel where an outlier
is spotted is now the panel it can be opened from. The selection ring is mirrored into
the ladder (`shape_ladder_sel`, keyed off a new `target_id -> row` map, since row order
is by median crossing width and cannot be derived anywhere else); a below-gate
selection has no ladder row and correctly rings nothing. `_shape_redraw_static()` calls
`_update_shape_selection_marker()` a second time after the ladder rebuild — the
scatter's earlier pass ringed the previous layout's row.

Exercised headless (offscreen Qt, synthetic captures across 12 registry targets plus a
scratch id, an unregistered id and `air`): tags resolve as expected, custom-vs-custom
gives two genuinely different axes, a ladder click drives the Tile Inspector and both
rings, and the tag checkbox clears both the scatter tags and the row suffixes. No
bench hardware involved. (2026-07-24)

---

### DESIGN.md — 1.10 — consolidation pass (§18)

Human-directed, read-only rule suspended per §18. Consolidates everything above the
previous marker that was not already folded in by the 1.9.1/1.9.2 correction passes.

**Supply epoch.** §4 diagram and §12 rewritten for the 6S LiPo pack (19.8–25.2 V,
working floor 21.0 V), with the dropout-headroom rationale for adding a cell rather
than replacing like-for-like, the ≈2.5 W → ≈4.6 W dissipation cost, and the
never-measured pulse-instant rail-sag check recorded as outstanding. §3's SoC bullet
gets a supply note. Deliberately **not** treated as a second measurement epoch: the
§17.10 regulation result shows the L7815 holds the operating point across the
regulated window, so §17.7–17.9 stand as taken — the §17 banner says so explicitly
rather than leaving a reader to assume the worst.

**Tooling.** §15: classviz row v1.39 → v1.42 (four tabs, Shape Space, mixed-geometry
marking, the tab's own two-mode air reference, scratch captures); new rows for
`src/pimd_shape.py` v1 and `src/data/scratch/`; delaycal row gains the
settings-persistence trap; corpora row updated from "rebuild in progress" to the
captured 66-capture corpus. §16 gains the `pimd_shape --selftest` invocation.

**Findings.** New §17.9 (the 2026-07-23 corpus campaign and the family-plane /
crossing-axis / decay-persistence geometry it established) and §17.10 (the 6S trial:
threshold-column survey, three-run calibration series, the regulation result, the
reference-age drift ceiling, the live family-plane knife-edge). §14.1 gains the 6S
thermal reproduction and the reference-age consequence; §14.3 flags the noise floor
as doubly stale; §14.7 gains the operating-point dependence and its two unresolved
anomalies; **new §14.9** — the family verdict must not be a hard sign test.

**Assets.** Six new §15 rows citing `References/Targets v1 Analysis/` — the analysis
CSV and five figures, captioned from the figures themselves rather than their
filenames.

§10 records the in-progress recalibration and the two things the next lock must carry
(a state-of-charge window; an explicit warning that identical cell count does not
imply comparability) but **no new profile section** — nothing is locked yet. Also
deferred for want of bench facts, and listed in the Doc-rev line so the next pass
picks them up: feature-level portability across a threshold-geometry change (§13) and
the delaycal fix-or-procedure decision. Header versions and the stale `targets v2`
reference corrected; Doc-rev 1.9.2 → 1.10 with the full prior history preserved.
(2026-07-24)

---

### USAGE.md — v1.7 — Shape Space, the amended profile-switch diagnostic, Import-Profile-first

Follows the 1.10 consolidation. New §5 bullet for the **Shape Space** tab covering the
parts an operator can get wrong: the two-mode air reference and that Space is the only
thing that moves between them, that the tab deliberately ignores the Heatmap tab's
baseline, that nothing auto-detects a target, why air age matters at 60 s rather than
600, that mixed geometries are marked but not calibrated against each other, and that
scratch saves never reach `src/data/corpora/`. §1 diagram: classviz v1.39 → v1.42 plus
a `pimd_shape.py` v1 node.

**§5's profile-switch diagnostic corrected.** It advised that a blank heatmap after a
profile switch means `G` went out before the board confirmed the profile. An unknown
share of those observations were the glitch-buffer bug fixed at v1.42 — the 64-frame
median started at zero, so every frame in the first ~10 s was flagged a glitch. The
note now distinguishes a *persistently* blank heatmap from the first ~10 s, and says
past bench notes resting on the old wording are suspect.

**§4:** Import Profile promoted from an optional convenience to the standard starting
point for any recalibration, with the settings-persistence trap that motivates it.
**§6:** corrected a stale note that listed `pimd_corpus_check.py` among the untracked
previous-epoch tools — it is tracked, v1.6, and current. (2026-07-24)

---

## Archive — consolidated 2026-07-24

### hardware/power — 6S LiPo supply — bench PSU failed, moved to 6-cell pack

The 1990s bench supply failed 2026-07-24. The detector moved to a 6-series LiPo pack
(19.8–25.2 V) in place of the documented 5-cell pack (§12, 16.5–21 V). Rationale for adding a
cell rather than replacing like-for-like: at 5S the pack falls below the L7815's dropout
headroom over the back half of its discharge, so coil drive — and therefore decay amplitude,
and therefore the voltage each amplitude-anchored delay actually lands on — sags with state of
charge. 6S holds the +15 V rail in regulation across the whole usable discharge. Cost is
roughly double the dissipation in the 7815 (≈2.5 W → ≈4.6 W at the §17.1 measured ~0.5 A
average) inside a sealed shielded enclosure, on a project whose first open problem is thermal
drift; warm-up is correspondingly longer than the historical 5S/bench-supply case. Field
deployment is battery-powered regardless, so this brings forward a supply epoch change the
soil phase would have forced anyway.

Working discharge floor **21.0 V** (3.5 V/cell), comfortably above the ≈18 V at which the 7815
loses headroom and coincident with the cells' own useful-capacity limit — there is no region
where the electronics still work but the pack is being damaged.
[FILL: scope measurement of the +15 V rail during a TX pulse, fresh pack vs near-flat, to
establish the real floor — a depleted pack's internal resistance may sag the rail at the pulse
instant in a way a DMM on the pack cannot show. This number has never been measured.]
(2026-07-24)

---

### findings — threshold noise zone is operating-point dependent, not fixed-voltage

First movement on §14.7 since the enclosure epoch. Running Mode 2 on the 6S pack at 22.4 V
with `cal_63_air_v2` loaded, the Std Dev (rolling N) heatmap showed the **4.40 V and 3.80 V
columns elevated across all seven bands** at roughly 5× the §12 free-air floor (values at or
near the 1284 µV display ceiling; only the 20 µs / 4.40 V cell fell short). The defect followed
the *threshold* axis, not the band axis — bands share the threshold ladder but sample it at
different absolute delays and different pulse energies, so a fault tracking the voltage label
localises the mechanism to the voltage domain (front end / 1N4732 clamp / preamp) rather than
to timing or drive energy.

Two observations resist the simple "the zone moved" reading and are recorded unresolved: the
**4.20 V column read clean between the two elevated columns** (a single shifted or widened
zone cannot produce noisy–clean–noisy), and **3.80 V sits well below the 1N4732 knee**, where
the clamp should not be participating. Either a second mechanism is present or the zone is
structured rather than contiguous. Needs a scope on the front end plus a fine threshold sweep
(§17.7 method, 4.70 → 3.60 V, all bands).
(2026-07-24)

---

### src/pimd_delaycal.py — [FILL: version if a code change is made] — stale settings silently reintroduced an excluded band plan

Run 1 of the 2026-07-24 recalibration exported a profile carrying an **eighth band (6 µs /
50 kHz)** — excluded back in `cal_63_air_v1` as carrying no unique target information and being
noisy — together with an **8-value threshold ladder missing 4.2 V**. Neither was intended: the
operator edited two threshold voltages and pressed run, and `delaycal_settings.json` supplied a
stale baseline for everything else. The result looked plausible and was nearly locked.

Both anomalies share one root cause: **delaycal's persisted settings are not anchored to the
currently locked profile.** The band-plan exclusion is a project decision recorded in DESIGN
§10, and nothing in the export path enforces or flags a departure from it. Documented
workaround is the existing **Import Profile** path (USAGE §4) — load the current locked profile
first, edit, then sweep — which produced the corrected runs 2 and 3.
[FILL: accept as an operator procedure, or add a warning when an exported band plan or
threshold count differs from the loaded/locked profile? If the latter, this entry needs a
version bump.]
(2026-07-24)

---

### findings — 6S warm-up reproduces the §14.1 thermal fingerprint; pack voltage does not reach the operating point

Two successive calibrations 37 minutes apart (runs 2 and 3 of the 2026-07-24 series), same
settings, no hardware change, pack falling 23.6 → 23.05 V, give a delay shift monotonic in
pulse width (r = −0.95 against log pulse width):

| Band (µs) | 9 | 13.44 | 20 | 30 | 45 | 67.2 | 100 |
|---|---|---|---|---|---|---|---|
| mean shift (ns) | +14 | +9 | +1 | −11 | −27 | −48 | −84 |

Light bands later, heavy bands progressively earlier, overall range −96…+16 ns. This reproduces
the §14.1 post-enclosure thermal fingerprint closely — that recalibration moved delays −56…+16
ns with heavy bands earliest and light bands high — confirming the signature survives the supply
change and that the rig was still warming. Magnitude is smaller than the preceding interval,
i.e. converging, but a single 37-minute interval still moved the 100 µs band ~10 grid steps
(order 100 mV of operating point), so settling under 6S takes longer than the historical case,
consistent with roughly doubled 7815 dissipation.

**Supply-regulation result (new).** Across that interval the pack fell 0.55 V, yet the light
bands moved *later* — a direction a falling supply cannot produce, since less drive means a
smaller flyback reaching every threshold sooner across all bands. No supply-direction component
is visible. Within the regulated window the L7815 is therefore holding coil drive constant and
**pack state of charge is not reaching the operating point**, at least down to 23.05 V. This
supports setting the capture-window floor from pulse-instant rail sag (the pending scope
measurement in the 6S supply entry above) rather than from gradual state of charge.
(2026-07-24)

---

### USAGE.md — [PENDING] — profile-switch diagnostic invalidated by the v1.42 glitch-buffer fix

`pimd_classviz v1.42` fixed a pre-existing defect: the 64-frame glitch-filter buffer
(`_ch_glitch_buf`) was zero-filled on first use, so its median sat near 0 until 33 real frames
had arrived and every one of those frames was flagged `|raw − 0| > 100 mV`, i.e. a glitch.
The consequence recorded there is display-side — the heatmap showed ~0 for roughly the first
10 s after connect or after a profile change.

The consequence **not** recorded is documentary: USAGE §5 currently advises that a blank heatmap
after a profile switch means `G` went out before the board confirmed the profile. An unknown
share of those observations were this bug, not a lost `G`. The diagnostic needs amending, and
any past bench note resting on it should be treated as suspect. **USAGE.md is not yet edited** —
this entry records the defect in the documentation, not its repair.
[FILL: were any corpus captures taken within ~10 s of a connect or profile change? The Training
cycle excludes glitch-flagged frames, so the failure mode would be a slow-filling air buffer
rather than corrupted data — but confirm rather than assume.]
(2026-07-24)

---

### findings — reference age sets a hard ceiling on measurement validity; quantified against real targets

Building the Shape Space air model produced a general measurement constraint that was not
previously written down. At the §17.2 drift rate of ~50 µV/s, an air reference accumulates
**0.5 mV/cell at 10 s, 3.0 mV at 60 s, 7.5 mV at 150 s**. Against mean |Δ| from the 2026-07-23
corpus:

| Target | mean \|Δ\| (mV) | reference age that matches it |
|---|---|---|
| Cu_pipe_01 @60 mm | 6.52 | ~130 s |
| Fe_spanner_01 @60 mm | 3.28 | ~65 s |
| Cu_pipe_01 @180 mm | 1.05 | ~21 s |
| Fe_spanner_01 @240 mm | 0.36 | ~7 s |
| Cu_Zn_brass_dome_01 @180 mm | 0.35 | ~7 s |

So a reference older than ~10 s already rivals a weak target and one minute exceeds a strong
target at close range. Measured directly on the bench during the build: a spanner @60 mm reads
|Δ| 2.8 mV while 150 s of drift reads 5.2 mV — **removing the object makes |Δ| go up**, which is
why no magnitude test against a frozen reference can detect removal, and why the auto-release
logic was abandoned by direction.

This is a property of the instrument, not of any one tab. It is the quantitative justification
for the Analysis tab's air-bracketed Training cycle (§17.5) — corpus captures are protected
because they bracket air on both sides — and it means any procedure that does not bracket is
unreliable beyond ~10 s. Retrospective note: a static baseline observed at 3381 s old carried
~169 mV/cell of accumulated drift, i.e. a live display dominated entirely by thermal history.
(2026-07-24)

---

### findings — family-plane early-band axis needs a confidence band, not a sign test

Two independent lines of evidence converge. Offline, in the 2026-07-23 corpus analysis, family
classification held at 97.8% under an SNR ≥ 5 gate, but the misclassifications were
directional: solid ferrous targets drift toward *crossover* as SNR falls, because the early-pulse
cells are a ferrous target's smallest signal and lose their sign first (`Fe_spanner_01` @240 mm
misread as crossover in leave-one-out). Live, during the Shape Space build, `Fe_spanner_01` was
measured flipping ferrous → crossover at a ~15 s hold, its early-band mean being just
**+0.045 mV** — a fraction of a millivolt from the axis.

The two agree on mechanism and on which targets are exposed. Consequence for the classification
layer: the family verdict must not be a hard sign test on the early-band axis. A "too close to
call" band around zero, scaled to the capture's own noise floor, is required — and the same
band is what a live cursor should display rather than asserting a family. Recorded now so the
classifier inherits it rather than rediscovering it a third time.
(2026-07-24)

---

### src/pimd_shape.py — v1 — shared signature-geometry feature maths

New module. Pure NumPy + stdlib, deliberately free of Qt/pyqtgraph imports so the
same functions serve both the ClassViz Shape Space tab and a future classifier.
Turns a baseline-corrected `delta_mV` signature into the small set of scalars the
2026-07-23 corpus analysis found to separate targets: `unit_shape` /`amp_l2` /`snr`,
`band_means`, `band_range_mean` (backs the early/mid/late and custom-range axes
alike), `crossing_us`, `decay_persistence`, and `family` /`family_gated`.

Conventions are fixed and documented in the header: `vec` is band-major, pulse
ascending, thresholds high→low — the same row sort `pimd_features` writes and
`pimd_corpus_check.load_corpus` /`pimd_classviz._scan_editable_signature_file` read,
which is what makes a live frame and a stored capture comparable at all. Geometry
is always passed explicitly (`pulses_us`, `n_delays`); nothing assumes 63 cells, and
`default_band_ranges()` derives early/mid/late from `n_bands` (outer thirds), which
reproduces the analysis's 0-1 / 2-4 / 5-6 split for the 7-band operating profile
without hard-coding it.

`crossing_us` interpolates log-linearly between bracketing bands — the pulse ladder
is geometric (DESIGN §10), so equal information sits in equal log-width steps — and
takes the *first* neg→pos transition so a noisy late band cannot move the answer.
The two outcomes that are not a crossing get sentinel values rather than NaN:
`CROSS_ALREADY_POS = 8.0` (band 0 already positive — a solid ferrous target) and
`CROSS_NEVER = 200.0` (non-ferrous). Both sit just outside the 9–100 µs ladder so
they land on their own rails on a log axis instead of dropping out of the plot.

`family` is a sign test and `decay_persistence` a magnitude test, and they are meant
to be read together: a ferrite toroid reads ferrous by sign and non-ferrous by decay,
and both readouts are true of it. Neither is allowed to overrule the other anywhere
in the tooling.

`--selftest <corpus csv>` runs the four acceptance groups against a known corpus.
Verified against `gui_signatures_targets_v1_20260723.csv` (cal_63_air_v2, 66 captures):
66 points / 46 gated / 20 below gate at SNR 5.0; families 26 non-ferrous, 12 crossover,
8 ferrous; crossing widths within ±1.5 µs of the analysis figures (trivet 34.35/33.85,
SS disc 26.4–30.9, gal RHS 20.8–23.4, gal pipe 14.9–21.1, D-shackle 14.61 as the
earliest crossover), every gated ferrous ≤ 11 µs, every gated non-ferrous at
CROSS_NEVER, ferrite at CROSS_ALREADY_POS; decay persistence ferrous/crossover
min 2.44, non-ferrous max 1.75, ferrite 1.37. (2026-07-24)

---

### src/pimd_classviz.py — v1.42 — Shape Space tab + scratch captures

New fourth tab, **Shape Space**: every loaded signature as a point in a selectable
2-D feature space, with the current frame moving through it as a live dot. Purpose is
human exploration of signature geometry — the 2026-07-23 corpus analysis's family
plane, crossing axis and decay-persistence separation, live instead of in static PNGs.
All feature maths comes from the new `pimd_shape.py`; this file is plumbing and drawing.

Layout is a `pyqtgraph.dockarea.DockArea` with five movable/floatable docks — Scatter,
Band Curves, Crossing Ladder, Tile Inspector, Gauges — rather than the Analysis tab's
nested splitters: each panel wants the whole screen at some point, so they need to be
re-orderable, not merely resizable. Layout persists as `shape_dock_state` in
`classviz_settings.json` (restored inside its own try, so a state written by a build
with different dock names degrades to the default instead of taking startup down);
"Reset layout" replays the default `addDock` sequence, which re-homes placed docks and
pulls floated ones back. Control bar: X/Y/Colour combos, custom band-range spin pair,
SNR gate, trail length, Load signatures…, Reacquire Air, Save Scratch…, Reset layout —
all except the buttons persisted.

**One store, one loader.** Points come from `self._analysis_templates`, the set the
Analysis tab already loads; the Shape Space "Load signatures…" button is wired to the
existing `_on_load_signatures_clicked` handler. `_scan_editable_signature_file` now also
returns each capture's own `pulses_us` /`n_delays` /`profile_name` (read off its rows,
not assumed), and `_merge_template_list` carries `target_id` /`distance_mm` /`short_name`
/geometry/profile into the template dict — they were previously formatted into the
display label and discarded.

**Mixed profile geometries are allowed here, and marked.** This is the one place in the
app that plots captures from more than one profile together, so the reasoning is worth
stating. `_refresh_analysis_overlays()` must keep refusing, because it draws raw
cell-by-cell curves where cell index N is a different (pulse, threshold) pair under a
different profile — superimposing those is meaningless. These features are not that:
every `pimd_shape` function takes its geometry explicitly and normalises through it, so
a crossing width is µs either way and a family verdict is a sign either way. They are
comparable in *kind*. They are **not** calibrated against each other — a crossing is
interpolated on that profile's own pulse ladder, and decay persistence reads that
profile's own threshold columns — so every foreign capture is marked on sight:

- **Marker shape** carries it, because colour is spoken for (family / colour-by) and
  fill is spoken for (gated). Circle = live profile, square = other profile; star and
  diamond are the respective scratch forms. A dashed outline was tried alone first and
  reads fine on a hollow marker but is nearly invisible on a filled 9 px one, so shape
  does the work and the dash stays as reinforcement.
- **A standing banner** in the Scatter dock, not a transient status line, naming the
  counts and profiles actually on screen ("66 from cal_45_other_v1 (5×9)"), the live
  profile, and the not-calibrated caveat. While foreign geometries are on the plane the
  fact has to stay visible, because the numbers look perfectly ordinary.
- **Tooltip, Tile Inspector title and Band Curves** each say so too. The tile's threshold
  axis falls back to bare column indices labelled "own ladder" for a foreign capture —
  the voltage labels come from the live profile and would otherwise be a quiet lie. Its
  band curve is dashed for the sharper reason that its vertices sit on its own pulse
  ladder and need not touch the live profile's x ticks at all.

DESIGN §10's "frames from different profile geometries must never be mixed in one
dataset" governs corpus builds; nothing in this tab writes one, and scratch saves still
refuse a geometry mismatch outright. Genuinely unusable captures — a shape that isn't a
rectangular n_bands × n_delays, or too few bands/delays for the features to be defined —
are still dropped, now with a message that says that rather than citing §11.

**Two rules the panels exist to enforce.** Below the SNR gate the unit shape is
normalised noise — it still has a family verdict and still wanders the plane
convincingly — so below the gate the live dot greys, shrinks and drops its trail, and
the Crossing Ladder omits ungated captures entirely. And `family` (sign) and
`decay_persistence` (magnitude) are always shown side by side, never reconciled.

**The air reference — the tab's own, and why a static baseline cannot serve.** First
bench run of the tab reported the live dot wandering across the plane, confidently
family-coloured, with nothing in front of the coil. Root-caused to referencing the shared
static air capture: thermal drift (DESIGN §3 ≈ −50 µV/s; §14.1 heavy bands −20…−31 mV,
monotonic with pulse width) accumulates into the delta as a large **coherent** term, and
the SNR gate cannot catch that *by construction* — `splithalf` measures short-timescale
scatter, so drift inflates `amp` while leaving `splithalf` flat. Simulated at the
documented rate against a fresh static baseline, coil in air:

| time since air capture | amp | splithalf | SNR | gated? |
|---|---|---|---|---|
| 30 s | 9.8 mV | 1.15 | 8.6 | **yes** |
| 90 s | 27.2 mV | 1.25 | 21.7 | **yes** |
| 270 s | 79.3 mV | 1.18 | 67.2 | **yes** |

The first round of offline verification could not have caught this: its synthetic stream
was stationary, so the drift term never existed. Any future test of this tab has to drift.

Replaced with a Shape-Space-owned rolling air reference, the same drift-cancelling
principle as the Analysis tab's air-bracketed Training cycle (DESIGN §17.5). Shape Space
no longer consults `_get_current_baseline()` at all — with the Heatmap tab's Baseline
combo on Rolling or Nominal the whole tab was silently meaningless.

**Two modes, and Space is the only thing that moves between them.**

- **air** — every glitch-free frame feeds a `frames`-deep buffer and the reference is its
  running median, so the live delta is ~0 by construction and the cursor sits at the
  origin. The indicator carries the frame counter and goes **yellow → green** the moment
  a full `frames` is collected.
- **measure** — Space snapshots that median as a fixed, timestamped reference and the
  cursor moves against it. Space again returns to air, clearing the buffer so the counter
  restarts at 0 and the indicator goes back to yellow: the mode is then unambiguous from
  across the room. Refused below 2 frames (a median needs two); the green indicator is
  what says the reference is properly deep.

Nothing auto-detects a target arriving or leaving. An intermediate revision did — a
settle gate, a Detect threshold, auto-freeze on arrival, auto-release on removal — and it
is gone by direction. One measured fact from building it is worth keeping, because it
says the auto-release half was never going to be reliable: an absolute |Δ| against a
frozen reference **cannot** detect removal under drift, since after a long hold the
accumulated drift exceeds the target's own |Δ| — a spanner @60 mm reads |Δ| 2.8 mV while
150 s of drift reads 5.2 mV, so taking the object away makes |Δ| go *up*.

**The cursor is always yellow**, one constant size, in both modes — no family colour, no
gated/ungated tint, no size change. The family verdict belongs to the loaded captures it
is being compared against; a cursor that recolours as it moves reads as the instrument
asserting something it was not asked to assert. The trail, the Crossing Ladder's LIVE
diamond and dashed line, and the Band Curves live trace follow the same rule. Stroked
elements use a darkened shade of the same hue (`_hl_ink`), because `_HL_YELLOW` is a
background colour — pale enough to be near-invisible as a 2 px line on pyqtgraph's white
canvas.

Pinning the air-mode cursor to the origin matters: its magnitude is ~0 but its unit shape
still has a definite direction (the reference's half-window drift lag), which parked it
at a consistent off-centre spot — measured, right inside the non-ferrous cluster. It is
pinned only on the signed-mean axes where 0 is the origin of anything, and hidden on the
others.

Fixed while testing the frame counter, in code that predates this tab: the 64-frame
glitch-filter buffer (`_ch_glitch_buf`) was zero-filled on first use, so its median sat
near 0 until 33 real frames had arrived and every one of those frames was flagged
`|raw − 0| > 100 mV`, i.e. a glitch. The heatmap therefore displayed ~0 for its first
~10 s after connect or after a profile change, and the air buffer — which excludes glitch
frames — filled at a crawl over the same window (10 of 40 frames in 44 sweeps). Seeded
with the first frame instead.

**Two frame counts, both Shape Space's own and persisted separately.** `window` sizes the
live cursor position and its split-half noise floor; `frames` sizes the air buffer and the
counter. Both defaults are deliberately unlike the Analysis tab's, for measured reasons:

- **Window 15 frames, not the Stats tab's 50.** A 50-frame window is ~15 s at the sweep
  rate, so a target does not fully register for 15 s — by which time drift has already
  spoiled the reading. Measured: a copper pipe registered at 8 s with a 15-frame window
  and not at all with 50.
- **Air buffer 40 frames, not the Analysis tab's 120.** A rolling reference is
  single-ended, so its median sits half a window in the past and that lag is baked into
  every measurement as drift. Measured against a spanner @60 mm: family read correctly out
  to a 15 s hold at 20–40 frames, and was already wrong at a 5 s hold at 80–120.

The Air-age gauge reads the age of the snapshot in measure mode and `air mode` otherwise,
amber past `SHAPE_AIR_AMBER_S` (60 s, not the 600 s a static baseline suggested: at
50 µV/s a 60 s-old reference already carries ~1 mV/cell, the order of a weak target). The
Settled gauge survives as a plain readout with no threshold line and a neutral bar —
there is no settle threshold to draw any more, but "is the rig quiet right now" is still
useful context.

**"Reacquire Air" → "Re-arm Air"**, and it no longer calls `_start_capture()`. This
departs from the task brief, which specified the shared static capture here; the bench
showed that baseline is the wrong reference for this tab, and a Shape Space button
mutating the Heatmap/Analysis tabs' baseline as a side effect is worse than not.

**Scratch captures.** "Save Scratch…", live in measure mode once enough frames have
arrived since the snapshot and blocked in air mode, takes a label/note/distance/medium
plus an air-anchor choice: the snapshotted air reference as a single flat anchor (quick),
or the Analysis tab's two-anchor training
capture (drift-corrected, offered only when one is pending). Both run through the same
`pimd_features` plateau/quality routines and the same `build_rows` provenance columns as
the corpus save path. Label slugifies to `scratch_<slug>`, validated against
`pimd_target_check.TARGET_ID_RE`. Rows append to `src/data/scratch/gui_scratch_<date>.csv`
in the CORPUS_HEADER schema, never into `src/data/corpora/` — a corpus build hard-errors
on an unregistered target_id and that guard is deliberate; promotion means registering
the object in `targets_v1.csv` and recapturing properly. Same channel-count guard as the
corpus path. The schema has no anchor column, so the anchor mode is recorded as an
`[anchor=flat]` /`[anchor=air2]` suffix in the free-text notes: a flat single-anchor
capture is not drift-corrected and that has to stay visible afterwards.

There is no hidden SNR or settledness threshold on the button: you save what you can see,
and a thin or noisy capture is stamped honestly by `pimd_features.quality_flags()`
instead of the button greying out for a reason the cursor does not show.

The flat path takes its target frames from the moment the air was snapshotted onward, capped
at `ceil(MIN_CENTRAL_FRAMES / CENTRAL_FRACTION)`. Two things a plain "last N frames" got
wrong: the window could reach back past the freeze and pick up air (it was stamping
captures `noisy` because it straddled the placement transient), and at the tab's short
live window it was always stamped `short`. A patient capture now clears
`MIN_CENTRAL_FRAMES` honestly and an impatient one is still told it is thin.

The Crossing Ladder shows the live frame on its own reserved **LIVE** row at the top
(family-coloured diamond, hover tip carrying family/crossing/decay/amp/SNR) with a
matching family-coloured line running down through the target rows, so the live
crossing can be read straight against every target's dots. The earlier plain black
dashed line alone was indistinguishable from grid. Below the gate both are hidden
rather than greyed — unlike the scatter, where a grey dot still usefully says "here is
the frame, don't trust it", an ungated crossing width placed on an ordered ladder would
imply a rank that isn't there.

One live-SNR defect, caught while testing that live row and worth spelling out because
it was silent: the live amplitude was taken from `_compute_analysis_matrix()` — a mean
over the Analysis tab's Avg-N frames, **default 1** — while the live noise floor came
from a 50-frame split-half. Amplitude and noise must be averaged over the same number of
frames or their ratio is not an SNR; the mismatch inflated it by roughly
√(N_window/N_avg), and in an offline sweep across the noise levels DESIGN §3/§17.8
reports, plain air cleared the 5.0 gate on its own. The live dot would have gone
confidently family-coloured, with a trail, on nothing at all — precisely what the gate
exists to prevent. Replaced by a single `_shape_live_window()` deriving both from one
window, mirroring `compute_plateau_stats` exactly: median frame minus baseline for the
shape, split-half of the same window for the noise. Air now reads SNR ≈ 1.0–1.3 at every
noise level from 0.05 to 2.0 mV (the correct answer for pure noise under matched
averaging) and stays ungated with no trail, while a presented spanner reads gated and
ferrous throughout; live amplitude reproduces the stored capture's 38.88 mV.

One performance defect, also caught offline: the Band Curves dock initially rebuilt
every curve — selection, all checked signatures, and the live frame — on each redraw
tick. With the full 66-capture corpus checked that measured **66 ms per tick against
the 33 ms REDRAW_MS budget**, i.e. a visible stall whenever the live dot moved. Split
into a static half (selection + checked, rebuilt only on load/selection/control
changes) and a single persistent live curve item updated in place: 66 ms → 0.5 ms per
tick, independent of how many signatures are checked.

One capture-identity defect found during offline verification, worth recording
separately because it is the **same class as the v1.40 corpus-path failure**: the
scratch save initially derived its session id from a `%Y%m%d_%H%M%S` timestamp and
used a fixed `_c01`, so two saves inside the same second produced identical
`(session, capture_id)` keys, `_scan_editable_signature_file()` folded their rows
into one capture, and the second save silently vanished. Reproduced (126 rows, 1
capture) before the fix. Now one session per scratch *file* (`scratch_<date>`, matching
the filename) with a running `_cNN` resumed above the highest already in the file,
plus the same collision while-loop the corpus path uses.

Three rendering defects found and fixed during the same pass, all worth recording
because each was silently wrong rather than broken: `QColor('#RRGGBB' + '22')`
is read by Qt as `#AARRGGBB`, so the ladder's shaded sentinel rails came out dark grey
and green instead of translucent red and blue (now `setAlpha`); the empty-state
`setXRange`/`setYRange` latched the scatter off auto-range, so switching axes put nearly
every point off screen (now re-enabled whenever there are points); and the gauge strips
were sized such that the GraphicsLayout margins plus the scale axis left the viewbox
4.5 px tall, rendering each bar as a hairline. Also noted, deliberately not "fixed":
pyqtgraph's `enableAutoSIPrefix(False)` does not clear the already-latched
`autoSIPrefixScale`, it only stops the label disclosing it — so the auto prefix is left
on (its default here and in every other plot in this file), and the axis says "(x0.001)"
rather than silently showing 150 for 0.15.

Verified offline against `gui_signatures_targets_v1_20260723.csv` under cal_63_air_v2:
66 points, 46 filled / 20 hollow at gate 5.0; 26/12/8 family split; ladder ordered by
median crossing; `Fe_spanner_01` @60 renders red intensifying toward 100 µs (7 of 63
cells marginally negative, ≤0.61 mV against a +14.16 mV peak, so they render near-white
— the brief's "all-positive" is a visual claim, not a literal one), `Cu_pipe_01` @60
strictly all-negative; dock layout survives a save/restore cycle byte-for-byte and Reset
restores the default; a scratch save round-trips back through "Load signatures…" and
renders with the scratch marker. Live-dot behaviour was exercised with a synthetic frame
stream: air reads below gate with no trail, a presented spanner shape reads gated,
ferrous, with its trail. Mixed geometry was exercised against a synthetic 5×9
`cal_45_other_v1` corpus folded down from the same captures: 132 points (66 native, 66
foreign) all plotting, foreign features sane on their own ladder (spanner ferrous /
already-positive / decay 6.76, copper pipe non-ferrous / never / decay 1.55), 66 squares
vs 66 circles, banner naming the profile and clearing again on unload, foreign band
curve carrying its own five vertices at 9/20/30/45/100 µs.

The two-mode air model has its own drifting-air harness, which is now the regression that
matters, since a stationary stream cannot see the defect that prompted all of this. Over
six simulated minutes of air at the DESIGN §3 rate the cursor stays exactly at the origin,
yellow, with no trail and no mode change (a static baseline reached SNR 67 on the same
input); the counter fills one frame per sweep and the indicator flips yellow→green
precisely at `frames`; a target appearing and then leaving changes nothing without Space;
Space enters measure and the cursor moves into the right quadrant for a spanner (ferrous)
and a copper pipe (non-ferrous) with the reference provably unchanged during the
measurement, every live marker yellow; Space returns to air with the buffer cleared and
the trail, ladder marker and live band curve gone; Space is refused with 0 frames and
accepted with 5, announcing the reference as thin; and taking the air *with* a target in
place then measuring it reads ~0 — asserted so that consequence of removing auto-freeze
is a known property rather than a surprise.

Reading accuracy against hold time was characterised rather than asserted, since it is
bounded by physics rather than code: four of five targets read correctly out to a 40–60 s
hold, and `Fe_spanner_01` flips ferrous→crossover at ~15 s because its own early-band mean
is +0.045 mV — a knife-edge on that plane, so a fraction of a mV of drift moves it.

Noted while running these: under `QT_QPA_PLATFORM=offscreen` this environment segfaults at
interpreter exit with no Python frame on the stack, reproducibly (10/10) in a script that
only constructs the window and feeds frames on the Heatmap tab — nothing to do with this
tab, and it happens after all work has completed. The harnesses now `os._exit()` so their
exit codes stay meaningful.

Confirmation on the bench with a real target is outstanding — everything above is
simulated. (2026-07-24)

---

### src/pimd_classviz.py — v1.41 — FIX Space-forced placement skipped the removal wait

Reported from the bench: on a target weak enough to need the Space override to get
out of `await_target`, the cycle jumped straight from the acquired target into the
trailing-air phase, with no chance to lift the target off the coil.

Deterministic, not intermittent. Both auto-detect transitions test the same
quantity — `_current_dev_from_air()`, mean |Δ| between the live settle window and
the locked leading air — against Detect: placement on `dev > Detect`, removal on
`dev < Detect`. The override is only ever needed because a target's |Δ| *never*
crosses Detect, so the removal test is already satisfied the moment `await_remove`
is entered, and the first settled frame advances to `air_trail`. Every target that
needs the manual placement was therefore guaranteed to skip the removal wait, and
any signature saved from that cycle has target frames in its trailing air —
corrupting the split-half floor and the SNR.

Fixed by latching the reason: `_sig_enter_target(manual=True)` from the Space
handler records that auto-detect never saw this target, and `await_remove` then
ignores the `dev < Detect` transition and waits for Space. Instruction B reads
"Remove target, then press Space" in that mode. The latch clears at every cycle
boundary (`_sig_finish_air_trail`, abort, start, reset), so a cycle whose placement
*was* auto-detected keeps full automation — that path is unaffected, since a
present target holds `dev` above Detect and cannot mis-fire on entry.

Untick-mid-cycle guard: once latched, Space keeps working for the rest of the cycle
even if "Space override" is cleared, which otherwise leaves no way out of
`await_remove` but the 30 s timeout abort. The countdown itself is unchanged — a
manual removal must still be done inside the same 30 s window. (2026-07-23)

---

### src/pimd_classviz.py — v1.40 — FIX capture_id reuse silently swallowed training saves

Field failure during a targets_v1 training capture: four targets saved and listed
fine, then the fifth (and every one after it) vanished — Save Sig cleared the
readout as if it had worked, but nothing appeared in the signature list.

The rows *were* written. `_reload_editable_signature_list()` set the next capture
sequence number to `len(sigs)`, the count of captures in the file. That is only
equal to the highest `_cNN` while the numbering is gap-free. Deleting a capture
opens a gap, after which the count hands the next save an id that already exists.
Nothing rejects a duplicate: the append succeeds, `_scan_editable_signature_file()`
groups on `(session, capture_id)` and folds the new rows into the existing capture,
`len(sigs)` doesn't move — so the same id is reissued forever and every subsequent
save disappears into it. In the failing file `c05` had accumulated 4 × 63 = 252
rows under one id.

Three changes. The sequence number now resumes above the highest `_cNN` actually
present (`_capture_id_seq()` parses the trailing index) rather than counting
captures, so a gap is harmless. `_on_sig_save_clicked()` additionally skips past any
id already in the file before writing, so a collision cannot happen even if the
seed is wrong. And the pre-save channel-count check now walks every capture instead
of sampling only the first — a folded capture has a wrong-length shape, so that
check now catches an already-corrupted file (it previously passed, because the
first capture was intact).

The affected corpus (`gui_signatures_targets_v1_20260723.csv`) was repaired in
place: the three orphaned captures — brass gear, and two crank-handle repeats —
were reissued as `c06`/`c07`/`c08` by regrouping on `captured_at`, and the second
crank-handle capture got `repeat_idx` 2 (both had been written as repeat 1, since
the repeat auto-increment reads the same merged scan). No measurement data was
lost; only `capture_id` and one `repeat_idx` changed. Original kept as `.bak`
alongside. (2026-07-23)

---

### .gitignore / DESIGN.md 1.9.2 — superseded profiles listed individually

The profiles rule was `src/data/profiles/*` plus `!src/data/profiles/cal_63_air_v2.json`.
Git handles that correctly — `git check-ignore -v` named the rule, and
`git status --ignored` reported the three superseded locks as `!!` — but VS Code's
Explorer kept showing all four profiles in normal (tracked) text rather than
greying the ignored three. The `dir/*` + negation idiom renders unreliably in some
editors' ignore decorations, and a working tree you can't trust at a glance is a
foot-gun in a repo where "which profile is the operating one" is a §10 contract.

Replaced with three explicit paths (`cal_63_air_v1`, `cal_72_air_v2`,
`cal_72_air_v3`). Net tracking is identical — only `cal_63_air_v2.json` is tracked,
all four stay on disk. The trade-off is deliberate and documented in both files:
new delaycal candidate profiles are **no longer ignored by default**, so they show
up as untracked until they are either locked (tracked) or retired (added here).
Arguably the safer default anyway — a new profile appearing in `git status` is a
prompt to decide about it, not noise.

DESIGN.md §15's `src/data/profiles/` row was describing the old mechanism, so it is
reworded to state the policy rather than the `.gitignore` implementation, and
Doc-rev bumped 1.9.1 → 1.9.2.

Verified: the three report `!!` under `git status --ignored` and `check-ignore -v`
names their new individual rules; `cal_63_air_v2.json` reports not-ignored and stays
tracked; a scratch `cal_TEST_new.json` correctly appears as `??` rather than being
silently hidden. (2026-07-23)

---

### src/pimd_target_check.py — v3 — renamed from pimd_targets.py

Module renamed `pimd_targets.py` → `pimd_target_check.py`, aligning it with
`pimd_corpus_check.py` (the two validators of the two human/tool data contracts).
`git mv` plus a mechanical `pimd_targets` → `pimd_target_check` rewrite across the
three consumers — `pimd_classviz.py`, `pimd_features.py`, `pimd_corpus_check.py` —
covering the `import`, every qualified call (`load_targets`,
`DEFAULT_REGISTRY_PATH`) and the user-facing strings that name the CLI. No
behaviour change: the import contract is the only thing that moved, so the
consumers are **not** version-bumped (CLAUDE.md: version tracks functional
change). The module keeps its dual library + CLI role — the new name reads
checker-ish, but it is still what classviz and features import at runtime to
validate the registry.

Verified: all four PC tools `py_compile` clean; `python pimd_target_check.py`
loads the 22-target registry with no issues; `pimd_features.py --help` resolves
its `--registry` default through the renamed module; `pimd_corpus_check.py` runs a
real corpus to a full table; the four headless suites pass 115/115.
(2026-07-23)

---

### Repo hygiene — profiles, profile8b captures and a stray delaycal CSV

Three tracking changes, all keeping files on disk except where noted:

- **`src/data/profiles/` is now tracked by exception.** Only the current
  operating profile, `cal_63_air_v2.json`, is in git; `cal_63_air_v1.json`,
  `cal_72_air_v2.json` and `cal_72_air_v3.json` are untracked but retained
  locally. `.gitignore` uses `src/data/profiles/*` + `!…/cal_63_air_v2.json`
  rather than listing the three, because delaycal writes candidate profiles into
  that directory routinely — the default should be "not repo source". Locking a
  new operating profile is a deliberate act: `git add -f` it and move the
  exception.
- **`References/profile8b-*` (3 previous-epoch captures) untracked**, kept on
  disk. Their DESIGN.md §15 rows were already dropped at Doc-rev 1.8, so they
  were tracked but uncited — flagged in the 1.9 consolidation pass.
- **`src/data/delaycal_1706-104844.csv` deleted.** A stray 2026-06-17 sweep
  output that predates the epoch reset; `src/data/delaycal*` was already
  gitignored, so it was only still tracked because it was added before that rule.

(2026-07-23)

---

### DESIGN.md — 1.9.1 — post-consolidation corrections

Human-directed, read-only rule suspended per §18. Follows the four changes above:
§15's registry row becomes `src/pimd_target_check.py` (**v3**, noting the former
name) and the classviz row's reference to it follows; the `src/data/profiles/` row
records the new track-by-exception policy. Doc-rev bumped 1.9 → 1.9.1 with the
existing history preserved. Nothing else touched — §3 and §17 remain untouched, as
in the 1.9 pass. (2026-07-23)

---

### USAGE.md — v1.6 — rename follow-through + stale version fixes

`pimd_targets` → `pimd_target_check` (v3) in the §1 pipeline diagram, the §6
heading and the §6 body/CLI examples. Two stale references corrected while there:
classviz v1.35 → v1.39 in the §1 diagram and the §5 heading, and the §5 Analysis
bullet no longer lists the `notes` placement field (removed at classviz v1.38) —
it now names the v1.38 per-parameter green/amber/red readout instead. (2026-07-23)

---

## Archive — consolidated 2026-07-23

### src/pimd_corpus_check.py — v1.6 — FIX air captures aborted the whole run

An **air** capture legitimately has no distance: classviz forces
`distance_mm=None` when `target_id == 'air'`, and `pimd_features.format_distance
(None)` writes an empty `distance_mm` column. v1.5's loader parsed that column
unconditionally (`int(round(float(...)))`), so a single air capture anywhere in
a corpus killed the entire run with an opaque
`ValueError: could not convert string to float: ''` — before a single check
could execute. Found while testing the classviz v1.39 work: the Analysis tab's
Training cycle can save air captures into the corpus, so the next re-profiling
run would have produced a corpus the checker refused to read at all.

New `_parse_distance_mm()` returns `None` for a blank column. Fixing the parse
alone only moved the crash, though: `check_splithalf_snr()` sorts every capture
by `distance_mm`, and one `None` among the ints raises
`TypeError: '<' not supported between instances of 'NoneType' and 'int'` as soon
as a corpus holds both an air capture and an object one — i.e. every real
corpus. Its sort key now substitutes -1 for a missing distance (real distances
are >= 0) so air sorts first within a label, and the row is labelled `@air`
rather than `@Nonemm`.

Air keeps its SNR row deliberately — its split-half floor is the most directly
meaningful noise reading in the corpus — and stays excluded from every
distance-keyed check (shape-invariance, falloff, repeat, cross-campaign), which
it already was via `NON_OBJECT_TARGET_IDS`. `one_per_distance()` additionally
skips any capture whose distance is `None`, so a hand-edited object row with a
blank distance is dropped from those checks instead of blowing up the
`sorted(grp)` every caller does.

Verified: a 14-check suite over synthetic corpora shaped like a real
re-profiling run (air anchors interleaved with an object at 60/120/180 mm plus a
repeat) — the air-only corpus that reproduced the v1.5 crash now loads; both air
captures appear as `@air` in the SNR check and nowhere else; no `None` leaks
into any label; the object still gets its shape-invariance rows, its repeat
comparison and a falloff fit recovering n=2.00 from an r^-2 fixture; a blank
distance on an object row is skipped without crashing; and the CLI exits 0 with
a full table. Against both real `src/data/corpora/gui_signatures_*.csv` files
(no air rows) v1.6's output is byte-identical to v1.5's, so this is a pure fix
with no behaviour change on existing data. (2026-07-23)

---

### src/pimd_targets.py — v2 — registry relocated to data/targets/targets_v1.csv

The target registry lived at `src/data/training_lists/targets.csv` — a directory
that otherwise held the Training Session tab's saved run-list JSONs, and that
classviz v1.39 has just made dead by removing that tab. The registry is not
training-list data and never was, so it moves to its own home:
`src/data/targets/targets_v1.csv` (moved with `git mv`, contents untouched — 22
targets, no validation issues).

One line changes: `DEFAULT_REGISTRY_PATH` in this module. `pimd_classviz.py`
(`TARGETS_REGISTRY_PATH`) and `pimd_features.py` (the `--registry` default) both
already derived from it, so neither needed a source edit and neither is version
bumped. The `--registry` CLI flag still overrides, and its help text prints the
new default. Header/docstring references updated; the CLI help no longer names
the file literally, since the filename now carries a version suffix.

Verified: `pimd_targets.py` CLI loads all 22 targets from the new path with no
issues; `pimd_features.--registry` resolves to it; classviz builds headless with
a 23-entry target combo (22 + air) and reports "Target registry loaded: 22
target(s)". (2026-07-23)

Note for the next DESIGN.md consolidation pass: §15 has two rows and one
`References/` caption still pointing at `src/data/training_lists/targets.csv`,
and the `src/pimd_targets.py` row still says v1. (2026-07-23)

---

### USAGE.md — v1.5 — Training Session tab removed; registry path updated

Follows classviz v1.39 and targets v2. The §5 "Training Session tab" bullet is
dropped and the classviz intent line no longer offers "quick signature captures
and guided training sessions" as two paths — the Analysis tab's automated
Training cycle is the only capture path now. The §7 registry path and the two
other `targets.csv` mentions become `src/data/targets/targets_v1.csv`. (2026-07-23)

---

### src/pimd_classviz.py — v1.39 — remove the Training Session tab

All corpus capture now happens through the Analysis tab's own Training group
(the automated auto-detect air/target/air cycle from v1.34–v1.35, refined in
v1.38), so the separate **Training Session** tab is redundant and is gone: the
guided run-list table, Start/Pause/Stop, Space step-advance, the per-row
Placement… dialog and the saved target-list JSON templates. That is one
contiguous 505-line block (`_build_training_session_tab` through
`_on_training_save_list`, 26 methods), plus the module-level
`TRAINING_LISTS_DIR` and its three saved-list file helpers, the `__init__`
state `_training_current_row` / `_training_row_start_wall` /
`_training_pause_started`, and the now-unused `QAbstractItemView` / `QDialog`
imports. Every removed method was verified to have no caller outside the block.

**Deliberately kept:** the session-recording machinery the tab shared with the
rest of the app — `_session_start` / `_session_stop` / `_append_mark` /
`_append_mark_target` and the `_recording` / `_session_file` state — which the
Analysis tab's Session sub-panel and the Stats tab's Record Session button both
drive. `_build_target_placement_widget_set()` also stays despite dropping to a
single call site: the field set *is* the corpus schema's placement tuple and
deserves one definition.

**Tab-index hazard fixed.** `_redraw` gated the Analysis charts on a hardcoded
`ANALYSIS_TAB_INDEX = 3` while `eventFilter` used the `_analysis_tab_index`
that `addTab()` actually returned. Removing a tab above Analysis moves it to
index 2, so the constant would have silently stopped matching and frozen the
charts. The constant is deleted and both sites now use the live index.

**Latent bug fixed as a consequence.** `_training_paused` (renamed to
`_session_paused`, now that no "training session" sets it) was only ever
cleared on stop by `_reset_training_ui()`, which ran solely when a *Training
Session tab* run was active. An Analysis-tab session that was paused and then
stopped therefore left the flag set — `_set_sig_session_active_ui(False)`
unchecks the Pause button with signals blocked, so the toggle handler never
fires — and the next recording silently wrote no frames, since process_packet
gates on it. Deleting the tab would have removed the only reset path entirely,
so `_session_stop()` now clears the flag directly.

Space is now bound only to an active Analysis training cycle while that tab is
visible (unchanged condition); with no Training Session step-advance to fall
through to, Space is otherwise left alone and reaches the focused widget as
normal. Settings drop `training_list` and `training_settle`; stale keys in an
existing settings file are ignored by `.get()`, so no migration. Also folds in
a v1.38 leftover: `_on_sig_session_mark()`'s dangling-target message still said
"reload targets", naming the button v1.38 deleted.

Verified headless (`QT_QPA_PLATFORM=offscreen`, 99 checks across three scripts,
all passing): three tabs remain in Heatmap/Stats/Analysis order with the
Analysis index now 2 and the stale constant gone; no `_training_*` attribute or
module-level list helper survives; a v1.38 settings file carrying the dropped
keys still loads and still applies the rest; and the shared session recorder
still starts, marks (writing both `# mark:` and `# mark_target:`), refuses a
mark while paused, resets the pause flag on stop, and records on the following
session. The v1.38 suites still pass unchanged. Bench confirmation of a full
Analysis training cycle and a Stats-tab Record Session still to be done.

Note for the next DESIGN.md consolidation pass: §15's `pimd_classviz.py` row
still advertises the Training Session tab. (2026-07-23)

---

### src/pimd_classviz.py — v1.38 — Analysis-tab capture ergonomics

Seven bench annoyances from using the Analysis tab as the primary capture
workbench (it grew into that role over v1.31–v1.37, but its layout still
reflected the older heatmap-first arrangement). No acquisition, wire-format or
profile-geometry change — DESIGN §11 untouched; `pimd_features.py` is read-only
here, imported for its constants only.

**(1) Shrinkable heatmap / growable signature list.** The heatmap owned a fixed
share of the left column (`addWidget(..., stretch=1)`) while the signature list
was capped at 46 px — ~2 visible rows, which made a 10+ capture corpus
unpickable for overlays. The left column is now a vertical `QSplitter`
(`self.analysis_left_split`): Controls/Signatures/Training above, heatmap below,
default `[620, 380]`. The heatmap child is collapsible and `analysis_gw` gained
a `setMinimumHeight(80)` so it can be dragged down to nothing; the controls
child is not collapsible. The list's 46 px maximum became a *minimum* and it now
takes the recovered space (`addWidget(..., stretch=1)` inside the Signatures
group). Sizes persist as `analysis_left_split_sizes`, guarded by a child-count
check on restore.

**(2) New captures land checked.** A freshly saved signature was unchecked, so
it wasn't on the charts until it had been found in that 2-row list. A new
in-memory `self._sig_autocheck_keys` set records each `(session, capture_id)`
saved this app session; `_merge_template_list` uses membership as the per-item
*default* check state. Only a default — `prev_checked` still wins for any item
already in the list, so unticking a fresh capture sticks across Save/Delete
reloads. Loading a reference corpus or reopening a file is unaffected (they
default unchecked), and the set is cleared on New file… / Open for editing… so
switching away and back brings rows back as they are on disk. This deliberately
covers the automated Training cycle too, which saves through the same handler —
everything captured this session is on the charts, with "Clear signatures" as
the way back out.

**(3) Black live traces.** The four "current" curves (chart-2, the 8- and
9-grids, the band-mean strip) were blue, the same visual family as whatever blue
`pg.intColor()` handed a template overlay, making live-vs-corpus ambiguous.
They're now black; overlays keep their intColor dashed pens.

**(4) Emphasised Target combo.** `_build_target_placement_widget_set()` takes an
`emphasise_target` kwarg, set only for the Analysis tab's inline capture set:
bold 12 pt label + combo, 300×30 minimum. That one combo decides what every Save
writes into the corpus and picking the wrong one silently mislabels a capture —
it shouldn't look like just another dropdown. The Training tab's Placement
dialog keeps the plain look.

**(5) Per-parameter quality colouring.** The readout was one flat string whose
*whole* label went yellow when `quality != 'ok'`, so "is this a good capture?"
meant mental arithmetic against constants living in `pimd_features`. Each field
now carries its own green/amber/red `<span>` background (QLabel renders HTML;
the palette rgb strings are factored into module-level `_HL_GREEN/_HL_YELLOW/
_HL_RED` that the `MY_*` stylesheet constants are now built from, so the two
can't drift). Bands come from three new "Green when:" spinboxes, defaulted from
`pimd_features` and persisted as `sig_q_amp_mv` / `sig_q_mean_mv` /
`sig_q_split_ratio`: Amp(L2) ≥ `AIR_THRESHOLD_MV_DEFAULT × √n_channels` (the L2
equivalent of the air threshold, per the L2 ≈ √n·mean|·| relation documented in
`compute_plateau_stats`); Mean|Δ| ≥ `AIR_THRESHOLD_MV_DEFAULT` (literally "below
this → air"); Splithalf ≤ `NOISY_RATIO_THRESHOLD` × Amp (the exact
`quality_flags()` 'noisy' rule). Amplitudes amber at half-threshold; Splithalf
and SNR share one verdict (same quantity, read two ways) with amber to 1.5× the
ratio; Quality is green on 'ok', amber with the flag text otherwise. Editing a
spinbox repaints the cached stats immediately. The None/'error' branches and the
"single air anchor" note are unchanged. *Flagged, not addressed:* the bands read
"more signal is better", so an intentional **air** capture — where a large
Amp/Mean|Δ| is the bad outcome — still colours green; inverting the sense for
`target_id == 'air'` is a separate decision.

**(6) Notes box removed** from the shared placement widget set, so it's gone
from both the Analysis tab and the Training Placement dialog — nothing was being
typed into it. `_placement_from_widgets()` returns `'notes': ''`, so the key,
the corpus `notes` column and the session dump's `# mark_target:` line keep
their exact shape (verified: `pimd_features.parse_mark_target_line()` still
round-trips the line). `sig_notes` is dropped from settings; a stale key in an
existing settings file is ignored by `.get()`.

**(7) Reload-targets button removed** along with `_on_reload_targets_registry_
clicked()`. The registry is a slow-moving reference file, not worth a permanent
control; `_load_targets_registry()` still runs at UI-build time. The
dangling-target message on Save now says to restart ClassViz to pick up registry
edits.

Verified headless (`QT_QPA_PLATFORM=offscreen`, 63 checks across two scripts):
UI builds; splitter collapses the heatmap to 0 and its sizes survive a restart;
thresholds default from the `pimd_features` constants, persist, and repaint the
readout live; good/mid/bad stats colour each field as specified; all four live
curves are black; a real Save writes an unchanged CORPUS_HEADER with an empty
`notes` column, is read back by `pimd_corpus_check.load_corpus()`, and lands
**checked** in the list, while a file-switch round-trip brings it back
unchecked. On-bench visual confirmation and live-capture colouring still to be
done by Mark. (2026-07-23)

---

### src/pimd_classviz.py — v1.37 — FIX Load signatures / Open for editing rejected the app's own files

Both Analysis-tab load buttons delegated schema sniffing/reading to
`pimd_corpus_check.py`, which is deliberately frozen on the legacy
`target`/`distance_cm` schema and hard-`SystemExit`s on the v1.32+
`target_id`/`distance_mm` schema — the exact schema this app now writes. So
`_on_load_signatures_clicked` (`load_corpus`) and `_on_sig_open_for_edit_clicked`
(`sniff_format` gate) both failed on every `gui_signatures_*.csv` the Training
flow produces, surfacing only a `Load failed:`/`Open failed:` line in the status
bar — i.e. nothing loaded. Confirmed against a real capture file. Fix: a new
`_sig_file_is_new_schema()` (checks the header for target_id/distance_mm/delta_mV)
dispatches both handlers to the app's own already-correct
`_scan_editable_signature_file()` reader for new-schema files. Load signatures
falls back to `pimd_corpus_check.load_corpus()` for legacy reference corpora
(still overlay-able read-only); Open for editing now requires the new schema
(editing appends v1.32+ rows via Save, so the file must already be that schema)
and gives a clear message pointing at New file… / Load signatures… otherwise.
`_merge_template_list` already handled the new schema's (session, capture_id)
2-tuple keys, so no list-rendering change was needed. Verified headless against
the real failing file: both buttons now parse its 3 signatures; a legacy-schema
header is correctly routed to the `pimd_corpus_check` path. (2026-07-22)

---

### src/pimd_classviz.py — v1.36 — persist the remaining preference controls

Audit of `_save_settings`/`_load_settings` after Mark noticed the top-bar
**Saved profile** dropdown wasn't remembered across launches. Four genuine
preference controls had no persistence and are now saved/restored: the
`cb_profile_file` (Saved profile) and `cb_training_list` (Training Session
Saved list) selectors, the Stats-tab Std colour thresholds
(`sp_std_lower`/`sp_std_upper`, 0.50/1.00) and the Training-tab settle window
(`sp_training_settle`, 50). Both dropdowns are already populated from disk in
`_build_ui` before `_load_settings` runs, so restore uses `findText` and falls
back to the default index if the saved file has since been deleted (verified);
restoring a profile selection only sets the dropdown — it does not auto Load &
Run, which still needs a live connection and an explicit click. Deliberately
left unpersisted (documented, not oversights): `cb_continuous` (Log
Continuously — an action toggle; auto-starting logging on launch is a foot-gun,
same stance as not restoring an in-progress recording or the editable-file
pointer), `le_csv` (its default is intentionally date-stamped per launch), and
`le_label` (per-capture free text). Everything else the operator sets was
already persisted. Verified headless: a five-value round-trip through a temp
settings file restores all five, and a settings blob naming a non-existent
profile leaves the combo at its default index without error. (2026-07-22)

---

### src/pimd_classviz.py — v1.35 — Training status labels + place/remove flash & beep

Two UX fixes to the v1.34 Training status line, in `_update_sig_train_indicator`
and the phase-entry/exit helpers. (1) The A (status) labels now name their
subject — `SETTLING air/target`, `COLLECTING air/target — k left`, `ACQUIRED air
— N/N (rolling)` — and the `await_remove` label, which wrongly read `ACQUIRED —
target on (rolling)`, is corrected to `ACQUIRED target — captured, remove now`:
the target signature is frozen at `_sig_finish_target` (the `await_remove` ingest
branch never appends to the buffer), so "rolling" was misleading; only the
leading air genuinely rolls. (2) The 30 s place/remove countdowns now signal
imminent action — the B instruction flashes (yellow, turning red in the final
5 s) via a new `_sig_await_flash_timer`, and `QApplication.beep()` fires once
when each prompt first appears (`_start_await_flash`, called from
`_sig_lock_leading_air` and `_sig_finish_target`; stopped by `_stop_await_flash`
on entering target/air_trail, on abort, and on Stop). No capture/stats change.
The beep uses the OS system bell, which is silent if the desktop bell is
disabled — a guaranteed tone would need a bundled audio asset + Qt Multimedia.
Verified headless (offscreen-Qt): the subject labels render per phase, the
target-held label has no "rolling", the await flash timer is active only during
await_target/await_remove (and stops on target-entry/abort/Stop), and
`_await_flash_style` returns red for ≤ 5 s remaining, yellow above. (2026-07-22)

---

### src/pimd_classviz.py — v1.34 — Training auto-detect capture cycle

Reworks the v1.33 Training group from a manual space-toggle into an automated
cycle per Mark's bench spec. The operator presses **Space once per cycle** to
lock the leading air; target **placement and removal are auto-detected**, with
30 s guard countdowns and a Save/Ignore decision. Layout: row 1 =
Start/Stop · Frames · Settle ≤ mV · new **Detect ≥ mV** · **Space override**
checkbox; row 2 = two status areas, **A** (colored state) and **B**
(instruction); row 3 = **Save Sig / Ignore Sig** (flash while a signature is
pending). The Acquire button is gone — Space is handled in `eventFilter`.

State machine (`_sig_train_phase`): `air_lead` (roll the leading air) →
`await_target` → `target` → `await_remove` → `air_trail`. Colour ladder for the
collecting phases is remapped from v1.33: yellow SETTLING → **blue COLLECTING**
(frames-left countdown) → **green ACQUIRED** (rolling). Auto-detect
(`_current_dev_from_air`): a transition fires only when the signal is settled
(the unchanged v1.31 `_current_settle_mv` gate) AND the mean per-channel |Δ|
from the locked leading-air reference crosses **Detect** — above for placement,
below for removal — so the hand transient (unsettled) is skipped naturally. The
30 s countdowns (`_sig_await_deadline`) show in B and, on expiry, **abort** the
in-progress signature (discard slots, flash red, restart the buffer, session
stays live). The trailing air **keeps rolling** as the next cycle's leading air
(same deque, never reset across the decision), so "space locks the last N frames
prior to space" holds and after Save/Ignore the next air is already good. The
**Space override** checkbox (default on, persisted) lets Space also force-advance
any phase as a manual fallback; a `_sig_can_commit` guard (≥2 frames) stops an
override of a barely-started window from snapshotting an empty buffer.

Capture math is untouched — `_compute_sig_stats`, `central_frames`,
`compute_plateau_stats`, `quality_flags`, glitch exclusion, the channel-count
guard (DESIGN §11) and the CSV save path (`_on_sig_save_clicked`) are all reused
verbatim; Save Sig routes through `_on_sig_save_clicked`, whose training-branch
tail now retires the decision and resets the readout (works for a direct
Signatures-group Save too). Two new persisted settings: `sig_detect_mv` (0.5),
`sig_train_override` (true). Verified headless (offscreen-Qt, synthetic frames):
full auto cycle place→profile→remove→signature with rolling reuse, Save writes
CSV rows + retires the decision, Ignore writes nothing, a past deadline aborts to
`air_lead` with slots cleared, Space override force-advances every phase, and
Stop preserves an unsaved signature for a manual Save. Not verified on hardware:
auto-detect behaviour under real placement/removal transients and noise.
(2026-07-22)

---

### Repo-wide — header changelogs slimmed to a terse version lineage; CLAUDE.md rule updated

The full-prose changelog embedded in every `.py` header duplicated `CHANGELOG.md`
paragraph-for-paragraph — `pimd_classviz.py` alone carried ~500 comment lines / 35
version paragraphs before any code (mcu 323, features 191, delaycal 180, gui 101).
On a solo, AI-driven repo that is triple-bookkeeping (git + header + this file) with no
reader. Headers now carry only a terse one-line-per-version lineage under a
`# History (full detail in CHANGELOG.md):` heading; the full narrative lives here alone,
which is also the curated feed `DESIGN.md` is regenerated from. The `CLAUDE.md`
"Versioning & changelog" section was rewritten to match: version number tracks functional
change (pure doc/reformat edits don't bump), headers stay terse, `CHANGELOG.md` is the
single detailed record. Non-changelog header content (purpose, protocol/interface notes,
`pimd_features.py`'s CORPUS_HEADER schema docstring) left untouched. No functional/code
change and no per-file version bump — this is a documentation reformat. Any version whose
prose lived only in a header was migrated here first so nothing is lost: `pimd_mcu.py`
v4.00/v4.01/v4.02, `pimd_delaycal.py` v1.00/v1.01, and `pimd_gui.py` v4.00/v4.01 (all absent
from this file, which began each of those tools at the next version) are added to the
archive — mcu beside its v4.03 entry, delaycal/gui in a "migrated from file headers" block
at the foot of this file. All other files' header versions (classviz v1.00–v1.33, features
v1–v7, classify v1.0–v1.2, targets v1) were already fully covered here. (2026-07-22)

---

### src/pimd_classviz.py — v1.33 — continuous training capture (Training group, space-bar air/target toggle)

Reworks the Analysis tab's signature capture per Mark's bench feedback: the
three capture buttons (Air before / Target / Air after, v1.26–v1.32) are
replaced by a dedicated **Training** QGroupBox beside Signatures (which
keeps the file row, placement metadata, readout and Save/Delete). Start
Training begins a continuous session alternating AIR and TARGET phases,
driven by a single Acquire button that the Space bar mirrors while the
Analysis tab is visible (the app-wide eventFilter now dispatches: active
Analysis training + Analysis tab visible → Acquire, otherwise the Training
Session tab's step-advance, unchanged; starting either session while the
other runs is refused). A colored status label steps yellow SETTLING →
green COLLECTING → blue READY, reusing the v1.31 settle-gate metric
verbatim; in READY the capture window is a rolling deque so Acquire always
commits the freshest N clean frames, and losing settledness mid-window
clears the whole window back to SETTLING (a disturbance contaminates the
window — same philosophy as the gate itself). Each committed air anchor
closes the pending target (air_after → stats snapshot → readout/Save) and
immediately shifts to become air_before for the next target, so the
operator just alternates place/remove target and taps Space — the app
works out the before/after airs; the shift happens at acquire-time with a
stats snapshot (not at save-time) because Save reads only the cached stats
+ placement widgets, making the flow race-free if the next target is
acquired before Save is pressed. Save no longer resets a running session;
Stop preserves an unsaved capture's readout so it can still be saved.
Stats math (`_compute_sig_stats`), glitch exclusion (incl. the >20 %
warning), the channel-count guard (DESIGN §11) and the CSV save path are
untouched. Also: the Supply combo becomes battery/psu ('usb' removed —
bench practice has moved off USB power; a persisted 'usb' setting silently
falls back to battery), and the Repeat # spinbox + label tooltip now
explains it is provenance-only metadata (same-placement disambiguator,
auto-suggested count+1, not used in matching). Verified headless
(QT_QPA_PLATFORM=offscreen) with injected frames: full air → target → air
cycle produces correct stats and the slot shift, settle-loss clears the
window, Start refusal without an editable file, Stop preserves unsaved
stats, gating and Space dispatch behave. Not verified on hardware: live
settle behaviour under real noise. (2026-07-21)

---

### src/pimd_features.py — v7 — doc-only: supply vocabulary battery|psu

Companion to classviz v1.33 dropping the 'usb' supply option: the module
docstring's `supply` column description now reads `battery|psu` and notes
the column stays free text, so older corpora with `supply=usb` remain
readable — no validation or behaviour change. TOOL_VERSION re-synced to v7.
(2026-07-21)

---

### USAGE.md — v1.2 — §5 rewritten for classviz v1.33's Training group

Pipeline diagram and §5/§6 headings follow classviz v1.32 → v1.33 and
features v6 → v7; the Analysis-tab bullet now describes the continuous
Training workflow (Start Training, space-bar Acquire, yellow/green/blue
status ladder, shared air anchors) and the battery|psu supply vocabulary.
(2026-07-21)

---

### DESIGN.md — 1.8.2 — §15 rows for all seven previously uncited References/ images

Human-directed §15 addition (read-only rule suspended for this task per
Mark's instruction): `pcb-coil-baseline.JPEG` (pre-enclosure board-on-coil
bench setup), `warmup-with-8ns-steps.jpg` (Mode 1 warm-up with 8 ns-grid
delay steps ≈ 5 mV apart), `new-training-data.jpg` (classviz v1.32
Analysis tab, first structured-regime capture session under cal_63_air_v1),
`training-targets-v3.JPEG` (physical target set behind targets.csv), and
`training-results-v1a/b/c` (previous-epoch cal_72_air_v2 17-target family/
staircase/cosine-similarity analyses, flagged historical). Captions written
from viewing the images, not guessed from filenames. (2026-07-15)

---

### References/ — asset reorganisation committed (2026-07-13/15 epoch)

All reference images now tracked in `References/` (the former `assets/`
directory is gone). Renamed: `scope-baseline.jpeg` →
`scope-pulse-baseline.jpeg` (same image; §15 row updated at Doc-rev 1.8).
Removed: `delaycal-screenshot.JPEG`, `profile8b-air.jpg` (previous-epoch;
the remaining profile8b captures stay on disk but their §15 rows were
dropped at Doc-rev 1.8). Added, not yet cited in DESIGN.md:
`new-training-data.jpg`, `training-results-v1a.jpg` / `v1b.png` / `v1c.png`,
`training-targets-v3.JPEG`, `warmup-with-8ns-steps.jpg`. (2026-07-15)

---

### .gitignore — TODO.md private; src/data/corpora/ untracked for now

`TODO.md` joins REDO.md under # Private. `src/data/corpora/` (classviz
signature captures) stays untracked while the post-enclosure corpus rebuild
is in progress — capture files are working data until a corpus is accepted.
(2026-07-15)

---

### USAGE.md — v1.1 — delaycal version references 1.24 → 1.25

Pipeline diagram and §4 heading follow the delaycal APP_VERSION re-sync.
(2026-07-15)

---

### src/pimd_corpus_check.py — v1.4 — re-tracked in the repo (.gitignore entry removed)

Untracked 2026-07-13 as a previous-epoch ML tool alongside pimd_classify.py
and pimd_v2_findings.py, but unlike those two it has been maintained since:
v1.4 (2026-07-14) is a deliberate companion to the v1.32 target-registry
schema change, and re-homing its consistency checks onto the new
target_id/repeat_idx columns is planned work (bounded follow-up). A tool
that is current-pipeline and documented in this changelog belongs in the
repo. No code change — v1.4 content as-is; .gitignore comment notes the
re-track. pimd_classify.py and pimd_v2_findings.py remain local-only.
(2026-07-15)

---

### src/pimd_delaycal.py — v1.25 — APP_VERSION constant re-synced with header

`APP_VERSION` was stuck at `'1.19'` while v1.20–v1.24 bumped the header
changelog only, so the window title has been reporting v1.19 since. Constant
now matches the header (bumped to 1.25 for this edit per convention). No
functional change. (2026-07-15)

---

### src/pimd_corpus_check.py — v1.5 — migrate to the v1.32+ target-registry schema

Real migration onto the v1.32+ `target_id`/`distance_mm` corpus schema that
pimd_classviz.py (Training capture) and pimd_features.py (corpus builder) both
write, replacing v1.4's deliberate stopgap `SystemExit` rejection of it. The
tool now reads that schema exclusively — legacy `target`/`distance_cm` files are
cleanly rejected with a message stating support was intentionally dropped (the
previous-epoch corpora were reset, so there is nothing legacy left to validate).
`load_corpus()` regroups per-cell rows into one signature per `(session,
capture_id)` and sorts each capture's cells by `pulse_us` then descending
`threshold_v` — the same regrouping as `pimd_classviz._scan_editable_signature_
file()` — and asserts the header carries `pimd_features.CORPUS_HEADER_FIELDS`.
The old `sniff_format`/`load_long`/`load_wide`/`dist_key` and the wide-format
path are gone.

Check changes: (1) the **canary-consistency check is retired entirely**
(`check_canary`/`strip_canary_suffix`/`CANARY_SUFFIX_RE`/`CANARY_*` removed, plus
its `CHECK_ORDER` entry) — per-capture air-before/after bracketing now does the
drift *correction* automatically in `pimd_features`, so the canary's audit role
is subsumed by the structured repeat check. (2) **Repeat consistency now keys
off the `repeat_idx` column**, not a `(rpt)` name suffix: captures are grouped by
the physical placement tuple `(target_id, distance_mm, long_axis, face_normal,
offset_x_mm, offset_y_mm, medium)` (mirror of `_placement_tuple_key`),
`repeat_idx == 1` is the base and `repeat_idx >= 2` are repeats compared against
it; this subsumes the old within-session and cross-session repeat checks in one
(the placement tuple is session-independent). A repeat with no base emits a
clear SKIP. `REPEAT_MARK_RE`/`find_repeat_base`/`check_repeat_cross_session` are
gone. (3) **Distances are data-driven** — a physical target (placement minus
distance) seen at ≥2 distances gets shape-invariance rows, ≥3 gets a falloff fit;
the hardcoded 5/10/15 cm logic is generalised to whatever `distance_mm` values
were captured, with a near-field/far-field split preserving v1.3's AMBER verdict
and all labels in mm. (4) **Cross-campaign** keys by the stable `target_id` (not
free-text name) per `(target_id, distance_mm)`, and joins the registry
(`pimd_targets.load_targets`, best-effort/optional) for a material-class label.

Verified: `py_compile` clean; runs against the real
`src/data/corpora/gui_signatures_*.csv` files printing the check table with no
`SystemExit` and no canary rows; the `repeat_idx` repeat path, orphan-repeat
SKIP, cross-campaign `--baseline` match, distance-falloff (r^-2 fixture → n=2.00)
and the AMBER near-field path were each exercised; a legacy `target`/
`distance_cm` file is cleanly rejected. (2026-07-22)

---


## Archive — consolidated 2026-07-15

### USAGE.md — v1 — new single-file usage guide; docs/ directory removed

New top-level USAGE.md: intent, operation and pipeline flow for every app —
overview/pipeline, pimd_mcu (fw v4.26), pimd_gui (v4.13), pimd_delaycal
(v1.24), pimd_classviz (v1.32), and the corpus pipeline (pimd_features v6 +
pimd_targets v1) — one page per app, versions taken from current source
headers. Replaces the five docs/ files (PIMD.md and the four per-tool cheat
sheets), which had drifted stale (mcu doc said v4.23, classviz v1.15,
delaycal v1.19, and the classviz sheet still described the removed Profile
Builder tab); `git rm -r docs/`. Facts point to DESIGN.md rather than
duplicating measured values. (2026-07-15)

---

### README.md — docs/ references repointed to USAGE.md

Repository-layout block, protocol note (now points at DESIGN.md §9),
Documentation list and the CC BY-SA licence scope updated from the removed
docs/ directory to USAGE.md. (2026-07-15)

---

### .gitignore — private-notes ignore renamed MM-NOTES.md → REDO.md

The private working-notes file was renamed by Mark; the ignore entry follows.
The `assets` entry is retained (directory currently deleted, may be
recreated). (2026-07-15)

---

### src/pimd_corpus_check.py — v1.4 — loud rejection of the v1.32+ target-registry schema

Companion to the target-metadata capture regime (pimd_classviz.py v1.32,
pimd_features.py v6): `sniff_format()` now detects a `target_id`/
`distance_mm`-schema file and raises `SystemExit` immediately, naming the
file and stating this tool doesn't support it yet. Without this, such a
file still passes the existing 'long'-format check (`pulse_us`/
`threshold_v`/`delta_mV` are unchanged column names) and only fails much
later with an opaque `KeyError` inside `load_long()`'s
`groupby(['session','target','distance_cm'])`, since those two columns no
longer exist. Deliberately **not** a full migration — a scope decision,
not an oversight: this tool's canary-consistency (`CANARY-START`/`END`
suffix matching on the target name) and repeat-consistency
(`REPEAT_MARK_RE`/`(rpt)` suffix, same column) both encode metadata into
the free-text target string, which the new schema replaces with a stable
`target_id` plus a separate structured `repeat_idx` column — re-homing
those checks onto the new columns is a real but bounded follow-up task,
deferred rather than bundled into this change. Old `target`/
`distance_cm`-schema files are completely unaffected; every existing
check still runs exactly as before (verified: a hand-built old-schema
fixture produces the same check table/exit behavior pre- and post-change).
`_on_sig_open_for_edit_clicked()` in `pimd_classviz.py` already wraps its
`sniff_format()` call in a `try/except SystemExit` and surfaces the
message in the status bar, so this fix also improves that call site for
free, with no code change needed there. (2026-07-14)

---

### src/pimd_classviz.py — v1.32 — structured target-metadata capture regime (registry-backed Analysis/Training capture)

Replaces the Analysis tab's free-text target field + distance_cm spinbox
with a registry-backed target combo (`pimd_targets.py`) plus structured
placement (distance_mm/long_axis/face_normal/offset_x_mm/offset_y_mm/
medium/repeat_idx/notes), built once by a new shared
`_build_target_placement_widget_set()` and reused both inline (Analysis
tab) and inside a new Training-tab "Placement…" dialog — one
implementation, not two. New `_load_targets_registry()` covers a
missing/broken registry: missing file → air-only with a status-bar
message; load errors → a dialog plus only the non-erroring targets
selectable; warnings-only → status-bar summary, fully populated. A
"Reload targets" button re-runs it on demand.
`gui_signatures_*.csv`'s column set moves to `pimd_features.py` v6's new
`CORPUS_HEADER` end-to-end (`target`/`distance_cm` dropped, not aliased)
and is now written via `csv.writer(QUOTE_MINIMAL)` instead of hand
comma-joining, since `notes`/`short_name` are free text and will contain
commas — `_scan_editable_signature_file()`'s grouping key also moves from
`(session, target, distance)` to `(session, capture_id)`, and the old
visit-count `(rpt)`-suffix scheme is replaced by a `repeat_idx`
auto-increment keyed on the full placement tuple (still user-editable).
A new `# mark_target:` session-dump comment line is written alongside the
existing `# mark:` line (byte-identical, untouched — zero risk to
`pimd_features.py`'s existing consumers) for both the Training tab's
row-advance marks and the Analysis tab's session-mark button, carrying
the same structured fields `pimd_features.py` v6 now parses. Training-tab
table: "Target" column becomes "Target ID" (validated against the loaded
registry, `_validate_training_table()` red-flags unknown ids), "Distance"
becomes mm; a new per-row `_training_row_placement` dict (keyed by a
stable token surviving Add/Remove Row, not row index) holds the remaining
placement fields, edited via the new Placement dialog. Training-list JSON
rows without `target_id` are loudly rejected on load, not migrated — the
4 existing `learn-v2-*.json` lists (old `target`/`distance_cm` schema)
need manual re-authoring against the registry as a follow-up.
New session-level `Supply` combo (battery/usb, top bar, DESIGN §12) feeds
both capture paths and is embedded in session-dump headers
(`# supply:`). `profile_sha8` (first 8 hex chars of SHA-256 of the
literal loaded profile JSON bytes) is computed once per profile load
(`_set_profile_dims`, now also caching the raw bytes via
`_load_profile_file`'s new `(profile, raw_bytes)` return) and threaded
through both capture paths and into session-dump headers
(`# profile_sha8:`); the built-in `_default_profile()` fallback (no file
on disk) uses a documented canonical-JSON surrogate since there's nothing
to hash literally. `fw_version` is parsed read-only from the existing raw
V-identify reply (`_parsed_fw_version()`), no protocol change. Settings
persistence of last-used `target_id` + placement is added, reversing the
v1.11-era "don't persist target/distance" decision — safe now because the
registry-validated combo makes a dangling `target_id` detectable (a dict
lookup against the freshly-loaded registry) and falls back to `air`
silently on a miss, rather than restoring stale free text.
Verified headless (`QT_QPA_PLATFORM=offscreen`): MainWindow construction,
registry load/degrade paths, a full Analysis-tab save (registry join,
quoted-comma notes round-trip through `_scan_editable_signature_file`,
`repeat_idx` auto-increment across two saves, delete), Training-tab
validation (unknown target_id rejected, missing air row rejected),
mark-target dict construction, list save/load round-trip, legacy-schema
list loud rejection, the Placement dialog's read-back into both the table
and the stored dict, and settings persistence including the
stale-target-falls-back-to-air path. Not verified (needs a physical
board or a mocked serial-frame injector): the live settledness-gated
capture flow itself and `fw_version` from a real `V` reply.
(2026-07-14)

---

### src/pimd_features.py — v6 — structured target-metadata capture regime (registry join + geometry guard rewrite)

Replaces the free-text `target`/`distance_cm` corpus columns with a
registry-backed `target_id` plus structured placement
(distance_mm/long_axis/face_normal/offset_x_mm/offset_y_mm/medium/
repeat_idx/notes) and capture provenance
(profile_name/profile_sha8/fw_version/tool_version/supply) — see
CORPUS_HEADER/JOINED_CORPUS_HEADER in the module docstring for the exact
column list. `Plateau` is redesigned around target_id/placement instead of a
free-text label; a plateau with no resolvable target_id (a no-marks
change-point segment, or an old-style '@distance' mark with no structured
`mark_target:` companion line) is loudly warned and excluded from output —
there is no free-text → target_id migration path, by design. New
`mark_target:` comment-line parsing is additive alongside the existing
`mark:` line (untouched, so pre-v1.32 session dumps stay readable);
`segment_from_marks()` nearest-timestamp-matches the two and retires the old
visit-count `(rpt)`-suffix scheme in favor of the structured `repeat_idx`
column. The profile-geometry gate is no longer a `--profile` reference-file
comparison that `[SKIP]`s mismatches (`load_reference_profile`/
`validate_profile`/`DEFAULT_PROFILE`/`--profile` removed) — every input
file's `(profile_name, profile_sha8)` is now grouped, and a corpus build
spanning more than one group is a hard error naming every offending file.
`profile_sha8` is SHA-256 of the profile JSON bytes as loaded, truncated to
8 hex chars; classviz computes and embeds it directly (a new
`# profile_sha8:` session-dump header line, or a literal gui_signatures
column) since only classviz has the literal loaded bytes — a session dump's
embedded `# profile_json:` text is a re-serialization that would hash
differently, so re-hashing it here is only a fallback for dumps predating
that line. New direct-ingest path for classviz's `gui_signatures_*.csv`
files (already at full per-cell granularity — no segmentation math, just
registry join); a pre-v1.32 file (`target`/`distance_cm` columns) is a hard,
clearly-worded error, no migration code. Unknown `target_id` is a hard
error naming the file and id; registry errors abort the whole run before
any file is processed. Row writing switches from hand `','.join()` with a
comma→semicolon replace to `csv.writer(quoting=QUOTE_MINIMAL)`, since
`notes`/`short_name` are free text and will contain commas — an intentional
on-disk convention change. No-marks change-point sessions can no longer
produce named corpus rows (a `segment_NN` placeholder was never a valid
registry `target_id`) — flagged as a real, forced consequence of the schema
redesign, not a bug. Verified against synthetic session-dump and
gui_signatures fixtures: registry join, quoted-notes round-trip, the
geometry guard (two sessions with different profile_sha8 correctly
refused), and the unknown-target_id and legacy-schema hard errors all fire
correctly; `pimd_corpus_check.py` is deliberately left unmigrated (see its
own changelog entry) — building a corpus from new-schema inputs works, but
`pimd_corpus_check.py` won't yet accept the result. (2026-07-14)

---

### src/pimd_targets.py — new — shared target registry loader/validator (v1)

New module: loads and validates `data/training_lists/targets.csv` (23
human-authored target objects), shared by `pimd_classviz.py` and
`pimd_features.py` as the single source of target physical metadata. Reads
and validates only — never writes the registry, which is human-owned data.
Errors: missing/misordered required column, empty/duplicate `target_id`,
`target_id` not matching `^[a-z0-9_]+$`, unparseable numeric, enum value
outside the documented sets. Warnings: dims not sorted
(`dim_a >= dim_b >= dim_c`), `wall_thickness_mm` present on a shape outside
the expected hollow-section set, `closed_loop=y` on a non-conductive
material, and a mass-plausibility check (`mass_g` vs. `1.05 ×
density × bounding-box volume`, converting mm³→cm³ before applying the
g/cm³ density table). CLI (`python pimd_targets.py [--registry PATH]`)
prints the full target table plus every issue found, exit 1 on any error,
0 on warnings-only. Verified against the real registry: correctly surfaces
`brass_block_01`'s dims-unsorted and mass-implausibility warnings and
`ferrite_toroid_01`'s closed_loop-on-non-conductive warning (plus several
legitimate bonus warnings on `cu_crimps_01`/`shackle_01`/`magnet_nd_01`),
0 errors, exit 0; a hand-crafted malformed registry (duplicate id, bad
regex, missing column, bad enum, unparseable numeric) correctly surfaces
all 5 planted errors in one pass; a missing `--registry` path produces a
clean error message and exit 1. (2026-07-14)

---

### src/data/profiles/cal_63_air_v2.json — new — locked; fresh soaked recal under fw v4.26

New locked operating profile from the 2026-07-14 delay recalibration (fully
warmed, fw v4.26). Same band plan and threshold ladder as cal_63_air_v1;
delays re-anchored — shifts of −56…+16 ns vs v1, heavy bands earliest
(thermal signature, decays arrive earlier warm). This retires the drift
that had pushed the 100 µs / 4.70 V cell onto the ~4.67 V upper edge of the
§17.7 threshold noise zone (σ 2.7 mV in session B); bench-confirmed fixed.
The delaycal export contained the full 8-band plan; the 6 µs / 50 kHz band
was stripped per the cal_63_air_v1 rationale before locking, and the name
field normalised. Same cell geometry as v1 but different delays — treat as
a new calibration epoch for corpus purposes. (2026-07-14)

---

### Bench observations — 2026-07-14 — fw v4.26 A/B verified; 100 µs / 4.70 V cell has drifted to the noise-zone edge

A/B session recordings under cal_63_air_v1 (`sessions/A.csv` fw v4.25
114 frames, `sessions/B.csv` fw v4.26 134 frames, ~10 min apart):

- **v4.26 fix verified.** Channel 1 (band 1, cell 2): σ 3050 → 284 µV.
  Discrete corruption events (single-frame jumps in the 32-deep rolling
  mean, threshold 400 µV ≈ a 13 mV single sample) fell from 9 per 114
  frames — up to ±5.7 mV jumps, i.e. single samples ~180 mV off — to 1
  small event (−477 µV) per 134 frames. The residual matches the low-rate
  ~±13 mV background events also seen on ch9/ch54/ch55 (1–6 each per
  session, both firmwares), so the CC-write race is closed; occasional
  live sightings of a small flicker at that cell are this background, an
  order of magnitude smaller and rarer than before.
- **New dominant σ cell is NOT a firmware artifact.** ch56 (100 µs band,
  4.70 V column, delay 7.6 µs): σ 605 (A) → 2693 µV (B). Its events are
  quantized at ±~2.0 mV in the rolling mean = single samples of ±64 mV,
  identical size under v4.25 (1 event) and v4.26 (10 events) — a
  pre-existing bimodal phenomenon whose RATE changed, not a new mechanism.
  Cause: operating-point drift into the §17.7 threshold noise zone. The
  cell is calibrated to sample at 4.70 V but sits at 4.673 V (A) / 4.669 V
  (B); heavy bands have drifted −20…−31 mV below nominal (monotonic with
  pulse width — thermal signature), light bands +9 mV high. Going 4.673 →
  4.669 V took the event rate 1 → 10 per session: the zone's upper edge is
  sharp and sits near ≈ 4.67 V on this band (the 2026-07-13 mapping used
  37.5 mV steps — 4.700 clean, 4.625 elevated — so an edge at 4.67 is
  consistent with it). The ±64 mV two-state character suggests the zone
  mechanism is discrete (ringing-phase-like), not broadband; mechanism
  still unknown (§14.7).
- **Follow-ups:** (1) confirm thermal state / warm-up and re-run delaycal
  fully soaked so the 4.7 V column re-anchors; (2) consider fine-mapping
  4.65–4.70 V on the heavy bands to locate the zone edge; (3) if the edge
  crowds 4.70 V warm, move the third threshold up (e.g. 4.75 V) in the
  next profile rev; (4) watch item: ch9 (13.44 µs band, first cell) shows
  6 small quantized events per session under v4.26 — band-head related,
  minor. (2026-07-14)

---

### mcu/pimd_mcu.py — v4.26 — post-emit IRQ burst mis-timed cell[1]'s CC write (channel-1 σ anomaly)

Root cause of the index-locked σ anomaly on the Analysis heatmap: channel 1
(band 1, cell 2) showed ~8× the σ of its neighbours, and stayed at the same
heatmap position when the first band changed from 6 µs/50 kHz (v3 profile)
to 9 µs/25 kHz (cal_63_air_v1) — i.e. locked to sweep position, not to the
physical band. PC side ruled out (the σ heatmap is a uniform per-channel
std over unfiltered W frames); the v3-era corpus
(`gui_signatures_20260713_212807.csv`) independently shows gross mean bias
at sweep positions 0–1 (e.g. copper ch1 +15.5 mV against a −1.2 mV band
trend). Mechanism: the W-record `print()` at sweep index 0 leaves USB CDC
TX-drain IRQs pending; `read_raw_sample()` re-enables IRQs immediately
after the SPI read, so at i==1 the queued burst (10–50 µs each, v4.21
measurement) fires exactly between the read and cell[1]'s `duty_u16` write
— and the outlier-gate/rolling bookkeeping added tens of µs of interpreter
time in the same gap for every cell. The RP2040 CC register is not
double-buffered (v4.13/v4.04): a write landing past the wrap leaves the
next conversion sampling at the previous cell's compare point (112 ns early
on the steep 4.8–4.9 V decay ≈ +100 mV raw — inside the outlier gate),
poisoning rolling[1] every sweep. The 6 µs band's 20 µs period gave the
tightest write budget of all bands — likely a contributor to its
"notoriously noisy" reputation. Fix: new `read_raw_bytes_hold()` keeps IRQs
disabled from the BUSY-synced read through the freq/CC writes (~2–6 µs on
top of the ≤36 µs v4.21 blackout), bookkeeping moved after the hardware
writes (the two identical branch copies deduplicated into one), decode
split into `raw14_from_bytes()` shared with `read_raw_sample()`. Read still
precedes all CC writes (v4.13). Needs bench A/B: channel 1's σ should
collapse to ~100 µV; `overrun_count` (B command) should not grow faster
than on v4.25. (2026-07-14)

---

### src/data/profiles/cal_63_air_v1.json — new — 6 µs band dropped from the operating profile

New operating profile derived from `cal_72_air_v3` (locked 2026-07-13): the
6 µs / 50 kHz band is removed on bench judgment — it contains no additional
target information not already present in the other bands and is notoriously
noisy. The remaining 7 bands are byte-identical to v3 (delays from cal run
`cal_20260713_210057`, top-dense threshold ladder 4.9 → 0.5 V), giving
7 bands × 9 delays = 63 cells. Shipped as a new file rather than an in-place
edit of v3 because the profile is the firmware↔ML contract (DESIGN §10) and
signature captures already exist under the v3 geometry — frames must never be
mixed across the two. `cal_72_air_v3.json` is retained unchanged as the
superseded locked profile. A `notes` field in the JSON records the rationale
(all loaders read only `averages`/`bands`; extra keys are ignored, and all
runtime code is geometry-driven, so no code changes were needed). (2026-07-14)

---

### mcu/pimd_mcu.py — v4.25 — outlier gate could permanently latch small-signal cells

Root cause of the "last cell flat at zero regardless of target" seen on the
Analysis-tab grids (channel 72 of cal_72_air_v3 — 100 µs band, 11.264 µs
delay, the deepest-decay cell): the v4.21 plausibility gate rejects samples
deviating more than `mean_raw // OUTLIER_GATE_FRAC` from the rolling mean,
but raw14 is signed. For a near-zero mean the threshold floors to 0 (any
nonzero deviation rejected); for a negative mean, floor division makes the
threshold negative, so `dev ≥ 0` always exceeds it and every sample is
rejected. The substituted mean is written back into the rolling buffer, so
once count ≥ 8 the cell freezes at its warm-up value forever — the plotted
baseline-delta is exactly 0 no matter the target. Fix: gate on
`abs(mean_raw)` with an absolute floor `OUTLIER_GATE_MIN = 164` raw14 counts
(≈ 100 mV, 1 % FS) — the bit-truncation glitches the gate exists for are
volts-scale and still caught, but a cell can no longer latch. Needs bench
verification: flash, run the operating profile, confirm the last cell tracks
a target. (2026-07-14)

---

### README.md — profile references updated to cal_63_air_v1 / 63 cells

Mode 2 description, highlights, bench-test example and Phase 3 roadmap
updated from `cal_72_air_v2` / 72 cells to the new `cal_63_air_v1` 63-cell
profile (6 µs band dropped, top-dense 4.9 → 0.5 V threshold ladder, keep-out
zone noted). Historical image caption and docs/PIMD.md's demo-profile band
table left unchanged — they describe profiles that really did have the 6 µs
band. (2026-07-14)

---

### src/pimd_classviz.py — v1.31 — Analysis-tab signature captures hardened to pipeline rigor

The first post-enclosure corpus test run (gui_signatures_20260713_212807.csv,
7 captures) showed split-half SNR of only 5–7 on several targets while the
best captures hit 10–20. The stats/baseline math is shared verbatim with
`pimd_features.py`, so the gap was in window collection, where the GUI
quick-capture skipped two robustness steps the session pipeline applies:
frames were collected the instant a capture button was pressed (the pipeline
trims `settle_s` = 2 s after every mark; the firmware's 32-deep rolling
average ramps for ~10 s after a target change, and ramp inside a window
inflates `splithalf_floor` directly since it compares first half vs second
half), and the window took raw unfiltered frames (the 64-frame-median glitch
mask was display-only; the pipeline drops flagged frames via
`drop_flagged()`). Two additions: (1) a settledness gate — pressing a
capture button now shows "Settling… X.XXX mV" and collection only opens once
the mean per-channel rolling std (the Training tab's Settledness metric,
window = the Stats tab's shared "Std dev N") drops to the new
"Settle ≤ (mV)" spinbox threshold (default 1.0 mV, persisted as
`sig_settle_mv`, raise to 50 to disable); (2) glitch-flagged frames are
excluded during collection and the window keeps filling until N clean
frames, with a status-bar warning if more than 20 % were skipped. Clicking
the active capture button now cancels the capture (no cancel existed).
Verified with an offscreen-Qt simulation: gate holds under 5 mV noise, opens
at 0.3 mV, an injected 500 mV glitch frame is excluded while the window
still reaches N clean frames, the >20 % warning fires, and cancel resets
state. (2026-07-13)

---

### src/pimd_targets.py — new — v1: shared target-registry loader/validator

New module, first of a three-file change replacing free-text `target`/
`distance_cm` capture metadata with a structured `target_id` + placement
regime (mission: rebuild the post-enclosure ML corpus from zero against
`src/data/training_lists/targets.csv`, the new human-maintained registry of
23 physical target objects). `load_targets()` parses the registry with the
`csv` module (not a hand `split(',')` — the file has a quoted comment line
containing a literal comma) and validates every row, collecting every issue
rather than stopping at the first: hard errors for missing/duplicate/
malformed `target_id`, unparseable numerics, and enum violations; warnings
for unsorted dims, `wall_thickness_mm` on an unexpected shape, `closed_loop`
on a non-conductive material, and mass implausible for the material's
density vs. the bounding box. Verified against the real registry: 0 errors,
7 warnings, including the three the task explicitly called for
(`brass_block_01` dims-unsorted + mass, `ferrite_toroid_01` closed_loop on
ferrite) plus four more genuine ones the generic rules also catch
(`cu_crimps_01`'s wall_thickness/mass on a `collection` shape,
`shackle_01`'s wall_thickness on an `irregular` shape, `magnet_nd_01`'s mass
narrowly exceeding its bounding-box limit). Also exercised against
hand-crafted malformed CSVs (bad id regex, duplicate id, empty id, bad enum,
short row, unparseable numeric) to confirm every error branch fires
correctly — an early cut treated any row with a blank first field as a
blank line, which silently ate the "empty target_id" error case entirely;
fixed to only skip rows where every field is blank. CLI:
`python pimd_targets.py [--registry PATH]`, prints a target table + all
issues, exit 1 on any error. Registry path note: the task brief named
`src/data/targets.csv`; the real, human-created file is at
`src/data/training_lists/targets.csv` (confirmed via `git status`) — this
and the other two files in the change use that real path as the shared
default. (2026-07-14)

---

## Archive — consolidated 2026-07-13

### Bench observations — 2026-07-13 — fw v4.24 verified; noisy threshold zone is ~4.45–4.65 V, not the whole top of the range

fw v4.24's time-floored boundary settling is confirmed on hardware: the
first-column noise (elevated σ in the first cell of each band regardless of
calibrated voltages, wandering on a seconds timescale) is gone.

With the position-dependent artifact removed, the remaining noise is tied to
the absolute threshold *voltage*, not the column position — but NOT as a
simple "avoid the top of the range" rule. Two captures:

1. Coarse list 4.90/4.80/4.70/4.50/3.80/3.20/2.40/1.50 V
   (`assets/Screenshot_2026-07-13_17-26-53.jpg`): the 4.50 V column is the
   noisiest across multiple bands (up to ~1.2 mV σ); 3.80 V down uniformly
   quiet.
2. Fine sweep 4.700 → 4.400 V in 37.5 mV steps, all 8 bands
   (`assets/Screenshot_2026-07-13_17-33-36.jpg`): the *endpoints* are clean —
   4.700/4.662 V and 4.438/4.400 V mostly ≤ 0.5 mV σ — while the interior
   4.625–4.513 V columns carry the noise (σ 0.5–2.24 mV, worst 2.24 mV at
   30 µs / 4.588 V and 1.85 mV at 100 µs / 4.513 V, elevated in nearly every
   band). The bad zone is roughly **4.45–4.65 V**; values above it (4.7, 4.8,
   4.9) and below it (≤ 4.4) both perform well.

This refines the earlier anchor-step-down story (4.8 → 4.5 → 4.2 V, DESIGN
§10/§17.5): the top of the curve is not inherently noisy — 4.5 V simply sat
inside this newly-mapped bad zone. The high-voltage/early-decay region is
informative and worth sampling: a reverse-geometric target progression
(steps densest near the top) gives more consistent patterns, and a list with
4.8/4.7/4.3/4.0 in the top region performs well. Practical rule for
calibration target lists: sample the top freely but keep targets out of
~4.45–4.65 V. Mechanism of the bad zone not yet identified (clamp-release
region; further tests planned). (2026-07-13)

---

### mcu/pimd_mcu.py — v4.24 — FIX: boundary settling now time-floored, not period-scaled

Root cause of the "first heatmap column is always noisy, whatever voltages I
calibrate" report (and of classviz v1.30's independently-confirmed noisiest
cell, band=9µs/cell=0): `acquire_mode2`'s band-boundary settling was
`BOUNDARY_PRIME = 15` PWM *periods*, so its absolute duration scaled with
band frequency — 25 kHz and 20 kHz bands got only 600/750 µs, below the
~1 ms+ the band-to-band energy-step transient needs (v4.20 itself measured
470 µs insufficient, 1.41 ms adequate — on a 94 µs-period band, which is why
the constant looked fine when it was set). The first cell of each band was
therefore sampled on a partially-decayed transient; ±1-period jitter in the
effective settle count turned that into telegraph-level alternation, which
the 32-deep (~9.2 s) rolling average smeared into the observed seconds-scale
oscillation. Band 1's first cell was clean only by accident: the 72-field
W-record print() at i==0 runs between that cell's CC write and its read
(after the settling sleep — the v4.20 comment claiming the print overlaps
the sleep was wrong, and has been corrected), donating milliseconds of
free-running settling every sweep. Fix: new `SETTLE_FLOOR_US = 3000`;
per-band settle periods are `max(BOUNDARY_PRIME, ceil(SETTLE_FLOOR_US /
period_us))`, precomputed into the flattened cell list, so every boundary
(including the band8→band1 wrap, whose old 320 µs budget could be entirely
consumed by the up-to-320 µs band-8 MCLK wait inside read_raw_sample) gets
≥ 3 ms of real settling. Sweep cost ≈ +12 ms on cal_72_air_v2 (289 → ~301 ms
refresh). No wire-format, PWM-slice, or profile changes. (2026-07-13)

---

### src/pimd_delaycal.py — v1.24 — Auto Nudge: down-only search past the signal-detect ceiling

Auto Nudge's zigzag search (v1.20) could keep alternating +offset/-offset
attempts even after a nudge pushed a channel's monitored voltage up to the
signal-detect ceiling (sp_signal_v, default 4.9 V — the same threshold used
by the coarse hunt, v1.15, to mean "no real signal present"). Once mean_v on
a channel reaches that ceiling, further +offset nudges just walk deeper into
no-signal territory, so it's a wasted (and potentially misleading) attempt.
New `_auto_check_ceiling(ch, mean_v)` latches a per-channel
`_auto_ceiling_flat` flag the first time this happens, and `_auto_nudge_channel()`
now checks that flag: once set, it drops the alternating sign and forces all
subsequent nudges for that channel to `-1` (down), with the magnitude
(`_auto_down_mult_flat`) continuing to grow by one nudge-step each attempt
from wherever the zigzag left off — no repeats, no jumps. Wired into both
evaluators (`_auto_evaluate_channel` for Sequential mode,
`_auto_evaluate_parallel` for Parallel mode). (2026-07-13)

---

### src/pimd_classviz.py — v1.30 — Fix: noisy reference cell contaminating whole-band normalize

User reported the Analysis tab's 8-grid (Per Pulse Width Cell Profiles)
showing ±5-10mV swings concentrated in the 9µs/13µs band panels, while Band
Mean vs Time showed only ~100µV of oscillation over the same period —
suspected as a bug. Investigation (code tracing, then 3 live screenshots
taken ~1 minute apart) found the data pipeline, reshape, and band/cell
ordering all correct; the swings traced to one genuinely noisy channel —
band=9µs, cell=0 (shortest delay / highest threshold) — independently
confirmed as the single highest-std-dev cell in the entire 8×9 grid via the
v1.28 Std Dev heatmap mode. That same cell is the literal subtraction
reference for `_normalize_group()`'s "Auto (− first element)" mode, shared
by the strip/chart2/8-grid/9-grid charts — so that one cell's frame-to-frame
jitter was being imposed at full strength onto every other point in its
group, producing the "whole curve translates as a block" pattern the user
correctly identified as diagnostic. Not a software defect — normalization
was doing exactly what it was built to do, against a genuinely noisy
reference — but worth hardening: `_normalize_group()`'s Auto mode now
subtracts the group's own mean instead of its first element, diluting one
outlier's contribution by ~1/group-size (verified: a 3.0mV reference-cell
jump between two frames now only moves its bandmates by ~0.33mV, down from
the full 3.0mV before) while still auto-zeroing each curve for at-a-glance
comparison. One shared `@staticmethod` fixes all four live-data consumers
plus the signature template-overlay path (same helper) in a single edit;
renamed the four "Auto (− first sample/point/cell/band)" checkbox labels to
"Auto (− group mean)" to match. No settings-persistence keys changed.

### src/pimd_classviz.py — v1.29 — Analysis heatmap colorbar legend + interactive range

Added a horizontal `pg.ColorBarItem` legend below the Analysis tab heatmap's
x-axis (via `setImageItem(insert_in=analysis_plot)`), answering "match value
with colour" — and, since the user asked for something that also lets them
set a threshold, made it double as an interactive range control: dragging
its handles sets the image's levels directly. This slots into the existing
Auto/Manual scale convention already used throughout the Analysis tab — the
Auto branch still recomputes and drives both the image and the bar every
redraw tick as before, but the Manual branch now leaves levels alone
(`autoLevels=False`) so a drag, or a typed value in the pre-existing
manual-range spinbox, survives across ticks instead of being stomped ~30x/
sec; a new `sigLevelsChanged` handler mirrors a drag back into the spinbox
and `_analysis_hm_manual_range_uv` so both stay consistent and the chosen
range persists across a settings save. Along the way, worked around a
pyqtgraph 0.14 quirk: `ColorBarItem.setImageItem()` calls the image's
`setLevels()` before it has any data, which pyqtgraph defers
(`ImageItem._defferedLevels`) and replays at the end of the *next*
`setImage()` call — silently clobbering the first real frame's computed
levels back to the colorbar's construction-time placeholder. A throwaway
zero-filled `setImage()` immediately after linking flushes that deferred
replay before any real data arrives, so the first live frame renders with
correct levels instead of a one-tick flash of the wrong scale.

### src/pimd_classviz.py — v1.28 — Heatmap Std Dev display mode + live throughput readout

Two additions. (1) A "Std Dev (rolling N)" display mode, added alongside the
existing Δ deviation/Z normalised/RAW abs modes on both the main Heatmap tab
and the Analysis tab's decoupled heatmap variant — shows each cell's
raw-signal std dev over the last N samples as a live noise/jitter monitor,
independent of any baseline capture. N is the Stats tab's existing "Std dev
N" spinbox (`sp_stats_window`), now documented as shared via tooltip rather
than duplicating a second N control; a new `_compute_rolling_stddev_nxn()`
reuses `_update_stats_table`'s exact rolling-window computation so the
heatmap and stats-table std dev always agree for the same N. Rendered with
the same sequential colormap and 0…max autoscale convention as RAW mode.
(2) A top-bar "Rate: X.X Hz (Y cells/s)" readout, visible on every tab
regardless of which is active, recomputed once/sec from an exact
frames-received-in-the-last-second delta (not a smoothed average, so a
stall reads as 0 Hz immediately instead of decaying into view) — added to
answer whether Mode 2 streaming is actually running at its ~100 Hz nominal
rate or has stalled somewhere. `read_from_serial()` now also counts how
many complete lines it drains in a single `readyRead` callback; a burst
of more than 3 (the GUI briefly falling behind the incoming stream between
events, with lines queuing up in Qt's internal serial buffer) appends a
"⚠ burst×N" warning to the readout instead of that backlog going unnoticed.

### src/pimd_classviz.py — v1.27 — Analysis tab: left-column grouping + 3-row right side

Cosmetic-only regrouping of the Analysis tab, no data/logic changes. The
Controls and Signatures boxes used to span the full tab width above
everything else; they now stack with the Heatmap group in one resizable
left column sharing the heatmap's width (reusing the existing `main_split`
`QSplitter`, previously the heatmap was its sole left-pane widget). That
frees the right side to start at the top of the tab and reorganizes its 4
stacked chart rows into 3: row 1 is a new nested horizontal `QSplitter`
holding "Band Mean vs Time" and "Pulse Width Mean" side by side (previously
2 separate stacked rows), rows 2/3 stay the unchanged 8-grid/9-grid.
Several rows in the narrower Signatures box (files, capture-inputs,
readout-save, session) and the two row-1 chart control rows (strip,
chart2 — now roughly half their old width) were wider than the columns
they'd land in; Qt's per-row minimum-content-width would otherwise refuse
to let the splitter shrink that far, so each of those rows was split onto
two stacked sub-rows to make the width reduction real instead of blocked.

### src/pimd_classviz.py — v1.26 — Analysis tab: settings persistence + in-GUI signature editor

Two additions. (1) All ~20 existing per-group Auto/Manual normalize+scale
controls (plus Avg N frames and the new signature capture-N) now persist to
`classviz_settings.json` and reload on launch, matching the convention
already used by `pimd_classify.py`/`pimd_delaycal.py` and this file's own
Heatmap-tab controls — the Analysis tab was the one place in the app that
still reset to defaults every restart. (2) An in-GUI signature file editor,
as a faster interactive alternative to the existing Record Session →
`pimd_features.py` CLI pipeline: "New file…"/"Open for editing…" make a
corpus CSV the active editable target (the existing read-only "Load
signatures…" stays browse-only — a loaded reference corpus and an active
editable file now coexist in one list, both overlay-able, since comparing a
new capture against an already-loaded reference was the point); "Capture Air
(before)"/"Capture Target"/"Capture Air (after)" capture a live N-frame
window into each of 3 slots (air-after optional — with only air-before, the
baseline flat-extrapolates, the same single-anchor fallback
`pimd_features.py` itself already has); "Save Signature" reuses
`pimd_features.Plateau`/`central_frames`/`compute_plateau_stats`/
`quality_flags`/`build_rows` verbatim to compute a real
`plateau_amp_mV`/`splithalf_floor`/`quality` from that live window, linearly
interpolating between the air anchors by timestamp like the CLI's own
thermal-drift correction — over a live 1-2 point window instead of a whole
recorded session's air visits, a real rigor trade-off flagged to the user
rather than presented as equivalent. "Delete Selected" only allows deleting
from the active editable file, by literal on-disk
`(session,target,distance_cm)` string match (not
`pimd_corpus_check.load_long()`'s `dist_key()`, which lossily casts distance
to `int`). Repeat target+distance saves in the same file auto-suffix
`(rpt)`/`(rpt3)` matching `pimd_features.segment_from_marks()`'s convention.
New files default into a new `data/corpora/` dir; GUI-captured signatures get
a `gui_YYYYMMDD_HHMMSS` session-id stamp so they're distinguishable from the
CLI pipeline's `session_...` stamp in any future audit. The signature list
now shows amp/SNR/quality per row (previously read from the file and
silently discarded) and shrank to a compact scrollable list to make room for
the new controls. Also added a peer alternate path — Session:
Start/Pause/Stop/Mark — recording a full raw session CSV byte-identical to
the Training Session tab's own output, for later conversion through
`pimd_features.py` exactly as today, driven from the Analysis tab's live
charts instead of the separate guided-list workflow; reuses
`_session_start`/`_session_write_row`/`_session_stop`/`_append_mark`/
`self._recording`/`self._training_paused` verbatim, so only one of the three
recording entry points (Stats tab, Training Session tab, Analysis tab) can
be active at a time. (2026-07-12)

### src/pimd_classviz.py — v1.25 — Analysis tab: relayout, single averaged strip, chart-2 controls

More bench feedback on the Analysis tab: (1) "Band Mean vs Time" moved above
"Pulse Width Mean" in the right-hand column and collapsed from two strips
(highest/lowest pulse width) to one showing the whole matrix's average
delta_mV vs time, with its own Auto/Manual normalize + Auto/Manual scale
controls and a Reset time button, matching the other chart groups — its
corpus overlay is now one reference line (the template's overall average)
instead of two per-band lines. (2) "Pulse Width Mean" (chart 2) gained the
same Auto/Manual normalize+scale controls as the two grids — previously
always auto-normalized with no manual override. (3) The 5 chart areas
(heatmap + the 4 in the right column) now fill all remaining vertical space
under the Controls box, no separate bottom section. (4) Renames: "Per-Band
Cell Profiles" → "Per Pulse Width Cell Profiles", "Per-Cell Band Profiles" →
"Sample Delay Band Profiles", "Band Mean vs Pulse Width" → "Pulse Width
Mean". (5) 8-grid's first panel no longer shows an x-axis title; 8-grid/
9-grid's first panel and chart 2 no longer show a y-axis label ("norm.") —
ticks still render, just without the title text repeated across 3 adjacent
charts. (6) Fixed 3 leftover "Auto (÷ first ...)" checkbox labels still
describing v1.23's divide/ratio convention after v1.24 switched the actual
math to subtract/offset — now "Auto (− first ...)". (7) Tightened layout
margins/spacing throughout the tab to reduce whitespace given the added
chart area. (2026-07-12)

### src/pimd_classviz.py — v1.24 — Analysis tab: per-group controls, bordered chart areas, Y-lock fix

Bench feedback on the new v1.23 Analysis tab, six changes: (1) the single
global "Normalize to first point" checkbox is replaced with independent
Auto/Manual normalize + Auto/Manual scale controls for each of the
heatmap/8-grid/9-grid chart groups. Per a follow-up clarification, "normalize
to first point" means an **offset** (first value → 0, rest referenced to it),
not the ratio/divide-by-first-point convention used elsewhere in this repo —
Auto subtracts each curve's own first point, Manual subtracts one shared,
user-entered reference value instead so the comparison scale doesn't drift
as the live first point moves. The heatmap's own Normalize control decouples
it from the main Heatmap tab's Δ/Z/raw display mode instead of always
mirroring it. (2) Every chart area is now a titled, bordered `QGroupBox`
with its controls inside that same box. (3) The two bottom strips' Reset
buttons are merged into one. (4) 8-grid's x-axis now shows each cell's
delay_us averaged across all bands (1 d.p.) instead of threshold_v; 9-grid's
per-panel titles show that same cell's delay_us *range* across bands
(matching the heatmap's threshold sub-label format) instead of threshold_v —
the two grids now surface different identifying dimensions instead of both
duplicating volts. (5) 8-grid/9-grid Y axes are locked to the first panel in
that row: tried pyqtgraph's `setYLink` first, but `ViewBox.linkedViewChanged()`
aligns ranges by on-screen pixel geometry rather than copying identical
numeric bounds — a scripted check showed genuinely different ranges across
same-size side-by-side panels — so replaced it with an explicit
`_lock_group_yaxis()` that copies panel 0's resulting range (auto-fit or
manual ±) onto every sibling panel every redraw tick; verified to match
exactly (both modes) in an offscreen-Qt re-test. (6) Fixed "Load signatures…"
opening a completely blank window — the native GTK/portal file dialog
doesn't render in this environment; added
`options=QFileDialog.Option.DontUseNativeDialog` to use Qt's own dialog
widget instead. (2026-07-12)

### src/pimd_classviz.py — v1.23 — new Analysis tab: real-time comparison charts + corpus overlay

New fourth tab, laid out to fill an ultrawide display with many small
pyqtgraph charts fed from the same live acquisition state the Heatmap tab
already maintains (no new serial/acquisition code): a heatmap variant
(y-axis renamed 'Pulse Width', integer µs, frequency dropped; x-axis stays
'Threshold' in volts at 2 d.p., with each column's delay_us range across all
8 bands added as a second tick-label line, since delay_us -- unlike
threshold_v -- isn't constant per column across bands, confirmed against
cal_72_air_v2.json); a normalized band-mean-vs-pulse-width curve; two
small-multiple grids (one panel per band showing its 9-cell profile, one
panel per cell showing its 8-band profile, each normalized to its first
point) decomposing the heatmap along each axis; two independently-resettable
band-mean-vs-time strips (highest/lowest pulse width); and a corpus-signature
overlay (Load signatures… button, reuses `pimd_corpus_check.load_corpus()`,
checkable per-target list, one colour per template) drawn on every chart
except the heatmap, skipped with a status-bar note rather than crashing if a
template's channel count doesn't match the live profile (DESIGN §11 — never
mix profile geometries). New `self._pulse_sort_order`/`_pulse_us_sorted`
(added to `_set_profile_dims()`) order all of these charts by pulse_us
ascending rather than assuming raw profile/channel order is already
pulse-ascending — the live default CLASSIFY_EP profile's band order is
actually pulse-*descending* (40→5µs), so that assumption would have silently
mis-ordered every one of these charts under the profile ClassViz connects
with by default. `_update_heatmap()` now also feeds a second heatmap image
(`self.analysis_img`) whenever it exists, from the exact same matrix/levels/
colormap already computed for the main Heatmap tab, so the two heatmaps
can't drift apart. New `_style_compact()` helper (small tick font, minimal
padding, optional small title) applied to all ~20 new plots, and axes hidden
on all but the leftmost panel of each small-multiple row, so the many panels
fit one screen. Verified end-to-end with a scripted offscreen-Qt run:
injected synthetic frames, switched to the `cal_72_air_v2` profile, captured
a baseline, confirmed chart 2 / both grids / both strips populate correctly
and the reset buttons work independently, then loaded the real
`PIMD_target_corpus_signatures_v2.csv` (44 signatures) and confirmed overlay
curves/lines draw on check and clear on uncheck. (2026-07-12)

### src/pimd_classify.py — v1.2 — configurable strip charts, per-delay normalized mode

The 4 lower strip charts are now independently configurable instead of
fixed to amp/continuum/cosine/baseline-band-8: each gets a mode combo
(module-level `STRIP_MODES`) and a band combo (shown only when the mode
needs one). The previous fixed content (amp, continuum, top-1 cosine,
baseline band-8) is preserved as the default selection for slots 1-4
respectively, generalized so any band can be picked, not just the last one.
Two new modes: "Band mean (mV)" (a chosen band's mean signal delta over
time -- the same quantity as one point on the existing snapshot band-mean
chart, now trackable over time) and "Per-delay normalized (9 cells)" (that
band's 9 individual cell readings, each divided by its own first sample so
all 9 curves start at 1.0 and separate as the session progresses -- shows
which delay cell drifts/responds most/least). Per-delay reads raw
(pre-baseline) per-cell values, not delta: delta's first sample is always
exactly 0 by construction (`BaselineTracker.bootstrap()` sets the baseline
to that very first frame), which would make "normalize to first entry"
degenerate -- discovered and fixed by scripted verification before
shipping (first sample would print 0.0 instead of 1.0 for every cell).
Slot mode/band selections persist to `classify_settings.json`
(`strip_modes`/`strip_bands`, -1 == last band). Verified end-to-end via a
scripted offscreen-Qt replay of `session_20260707_143723.csv`: all 6 modes
render correct data, per-delay-normalized curves all start at 1.0, and
switching a slot back to a single-curve mode correctly clears its other 8
curves. (2026-07-11)

### src/pimd_classify.py — v1.1 — heatmap range/axes, band-chart ticks, event log fix

Four fixes/additions from bench feedback on the Classify GUI: (1) added a
±mV range spinbox + Autoscale checkbox for the signature heatmap, mirroring
the existing band-mean chart's range control (persisted to
`classify_settings.json` as `heatmap_range_mV`/`heatmap_autoscale`,
defaulting to autoscale on so behaviour is unchanged unless the operator
turns it off). (2) Heatmap axes now show real values/labels instead of bare
pixel indices — bottom axis "Threshold" ticked with each cell's `threshold_v`
(4.2V…0.5V for cal_72_air_v2), left axis "Band" ticked with each band's
`freq_hz`/`pulse_us`, reusing the exact convention `pimd_classviz.py`'s
`_rebuild_heatmap_axes()` already established. (3) Band-mean chart's
log-scale x-axis now ticks only the profile's actual pulse widths (e.g.
6.0, 9.0, 13.44… µs) instead of generic log-decade ticks. (4) Fixed the
Event Log tab only ever populating the first row correctly, with every
event after it landing with blank cells in later columns — root cause was
`QTableWidget.setSortingEnabled(True)` re-sorting the table mid-way through
a new row's per-column `setItem()` calls (triggered once any column sort
was active, e.g. after the operator clicks a header), so later `setItem()`
calls landed on whichever row the resort moved into that row index instead
of the row being built. Reproduced in isolation (sort by column 1, append
rows one at a time -> later columns land on an already-populated row,
leaving the new row blank) and confirmed the fix (disable sorting for the
duration of each row's insert+populate, re-enable after) eliminates it.
Verified end-to-end via a scripted offscreen-Qt replay of
`session_20260707_143723.csv`: all 6 events now populate every column
correctly. (2026-07-11)

### src/pimd_knn_baseline.py — v1.1 — fix crash when output dir doesn't exist

`main()` now calls `os.makedirs(outdir, exist_ok=True)` before `fig.savefig()`.
Previously, running the script with a non-existent `<output_dir>` (e.g.
`python pimd_knn_baseline.py corpus.csv test`) ran the full LODO/LOTO
classification and printed all results, then crashed with
`FileNotFoundError` at the very last step trying to save the confusion
matrix PNG. (2026-07-04)

### src/pimd_features.py — v2 — add wide-format signatures output

Added `--out-wide <path>`: one row per (session, target, distance_cm)
plateau instead of one row per cell -- `session,target,distance_cm,
plateau_amp_mV,splithalf_floor,quality,c00..c71`, with `c00..c71` the
plateau's delta_mV vector. Long-format `--out` remains the canonical
output; wide rows are built in the same pass from the exact `delta_mV`/
`plateau_amp_mV`/`splithalf_floor`/`quality` values already computed for
the long rows in `process_session()` (now returns `(rows, wide_rows)`) --
never re-parsed or recomputed, so the two outputs can't drift apart for
the same plateau. Checked whether `c00..c71` needed reordering to satisfy
"pulse ascending / threshold descending within band": it doesn't --
`cal_72_air_v2.json`'s 8 bands are already stored pulse_us-ascending, and
each band's 9 cells are already stored threshold_v-descending, so the
existing channel index (`band_index*9+cell_index`, used everywhere else
in the file) already satisfies that ordering. New `wide_header_lines()`
(writes `# profile: <name>` plus a column-order comment line before the
CSV header), `open_wide_writer()` (same refuse-unless-`--append`
semantics as the long writer), and `build_wide_row()`. Verified: wide row
count = long row count / 72 across all 3 real sessions, and every c00..c71
value matches its corresponding long-row delta_mV exactly (scripted
cross-check, all 27 plateaus x 72 cells). (2026-07-03)

### src/pimd_features.py — v1 — session-CSV -> training-corpus feature extractor

New offline PC-side script (no GUI, no firmware touch): turns a raw ClassViz
session-dump CSV (pimd_classviz.py v1.16+ "Record Session" output) into rows
matching the existing hand-built PIMD_target_corpus_signatures.csv schema.
Validates each session's embedded profile_json against cal_72_air_v2
structurally (refusing, not crashing, on any mismatch, and continuing with
the rest of a multi-session batch -- DESIGN §11: never mix profile
geometries), drops glitch-filter-flagged frames, and segments the frame
stream into air/target plateaus: from '# mark:' ground-truth lines when
present (pimd_classviz.py v1.19+ hotkeys), else a rolling-window mean-abs-
diff change-point fallback with generic placeholder target labels (no
ground truth for *which* target a run is without marks, so it never guesses
from the free-text session_notes). Builds a piecewise-linear per-channel
baseline anchored on air segments to correct the thermal drift documented
in DESIGN §3/§17.5, and computes per-plateau delta_mV / plateau_amp_mV /
splithalf_floor / quality. Also emits one diagnostic PNG per session
(band-mean vs time, drift-corrected, with segment boundaries and the
session's free-text notes) for eyeballing a capture before trusting it.

Change-point defaults were hand-tuned against the 3 real sessions currently
in data/sessions/ (none of which have marks yet) -- the initially-spec'd
0.5 mV transition threshold found zero transitions in one 272 s session;
settled on 0.15 mV/1 s window/4 s min-segment after inspecting raw band-mean
traces. The no-marks air/target classifier assumes the standard capture
protocol (recording starts in air, before the first target) and anchors on
the chronologically first detected run; a session-wide median-of-segment-
medians was tried first and rejected as unreliable on real, sparsely-
segmented captures. Verified against all 3 real sessions plus a synthetic
marked session (marks path) and a deliberately profile-mismatched file
(refusal path). Noted for the record: plateau_amp_mV in the existing
PIMD_target_corpus_signatures.csv (e.g. 190.0 for steel pipe @5cm) is not
reproducible as mean(|delta_mV|) over the 72 cells (that computes to ~16.6
for the same row) -- this script implements the mean(|delta_mV|) definition
as specified, so --append-ing new rows into the legacy corpus will mix two
different plateau_amp_mV scales until that's reconciled. CLI takes one or
more session CSVs plus --out/--append. Plain numpy + matplotlib only, no
pandas, no csv module -- consistent with the rest of the repo. (2026-07-03)

### src/pimd_knn_baseline.py — v1.0 — first classifiers for the signature corpus

New offline analysis script (numpy/pandas/scikit-learn/matplotlib, no GUI):
two classification tasks over `PIMD_target_corpus_signatures.csv` — (a)
family classification (ferrous-rising / crossover / non-ferrous), (b)
per-target ID (16 classes). Models compared: 1-NN with cosine distance on
L2-normalized 72-cell shape vectors; multinomial logistic regression (L2,
C=1) on the same features; and a 2-feature physics baseline for family
(zero-crossing pulse width + band-8 sign). Validation is leave-one-distance-
out (LODO) for both tasks, plus leave-one-target-out (LOTO) for family — an
unseen-object test, never a random split (DESIGN/ML_FINDINGS convention:
random splits overstate accuracy on this corpus size). Outputs confusion
matrices and per-fold accuracy to `<output_dir>`. (2026-07-03)

### src/pimd_pca_explore.py — v1.0 — PCA exploration of the signature corpus

New offline analysis script (numpy/pandas/scikit-learn/matplotlib, no GUI):
loads `PIMD_target_corpus_signatures.csv`, applies the audited exclusion
policy (solder roll 260g dropped entirely — distance falloff only ~1.7x even
after drift correction; SS shackle 62g keeps 5cm only; brass 370g drops
15cm; SS disk 35g @15 and steel RHS 140g @15 kept but flagged low-confidence,
late-session drift-heaviest stretch), builds L2-normalized 72-cell shape
vectors, and runs PCA to produce: variance-explained scree plot + PC loading
heatmaps in the 8x9 matrix layout (so components read like signatures);
a PC1-PC2 scatter of all usable signatures coloured by family and sized by
distance; and a check of the engineered zero-crossing pulse-width feature
against PC1 score, to see whether blind statistics rediscover the bench-
derived material parameter. (2026-07-03)

### src/pimd_classviz.py — v1.19 — mark hotkey for session ground-truth timing

While recording a session (Record Session), the only way to know which
physical target was in front of the sensor at a given moment was to
reverse-engineer it after the fact from the signal shape. Added a persistent
"Mark label" text field (Stats tab) plus single-key hotkeys active during
capture: `1`/`2`/`3` append `<label> @5`/`@10`/`@15` (cm) to the open session
CSV as a `# mark: <iso-timestamp>, <text>` comment line; `0`/`Space` append
literal `air` (ignores the label). Hotkeys are suppressed while any QLineEdit/
QSpinBox/QDoubleSpinBox has focus (so normal typing is unaffected), are a
no-op with a status-bar message if no session is recording, and a distance
mark is skipped (with a message) if the label is empty. A small recent-marks
readout (last 5) was added below the label field so the user can confirm a
mark landed without opening the file. The write reuses the exact
write()+flush() pattern already used for per-frame rows, on the same open
file handle, so it can't stall the ~7.3 Hz frame-logging path. Purely
additive to the CSV format — `#`-prefixed lines are already skipped by every
existing parser; no change to colmap, profile_json, or per-frame columns.
(2026-07-03)

### src/pimd_classviz.py — v1.18 — pad saved profile JSON floats to 3 d.p.

Follow-up to v1.17: that fix made the Profile Builder's *display* and *editing*
consistently 3 d.p., but `_save_profile_file()`'s `json.dump()` still serialised
floats at Python's trimmed `repr()` precision (`6.8`, `9.0`, `3.22`) — confirmed
against a freshly re-exported `cal_72_air_v2.json`. `json.dump()` has no float-
formatting hook (its C encoder calls `float.__repr__` directly, so a float
subclass with a custom `__repr__` is silently ignored — verified empirically).
Added `_pad_json_floats()`, a regex pass over the `json.dumps()` text that pads
every decimal-point number to `.3f`; integer fields (`freq_hz`, `averages`) have
no decimal point so are untouched. `_save_profile_file()` now writes through it.
(2026-07-03)

### src/pimd_classviz.py — v1.17 — 3-decimal precision for voltage/timing fields

Profile export was silently losing precision: `_populate_profile_editor()` formatted
`delays_us`/`threshold_v` to `.2f` when loading a profile into the Profile Builder
table, so any profile that passed through the editor (loaded, or loaded-then-saved)
got re-saved at 2 d.p. instead of the source precision. Confirmed against
`cal_72_air_v1.json` (2 d.p., editor round-tripped) vs. a delaycal-direct export
(3 d.p., bypassed the editor). Fixed the editor's format strings to `.3f`, and made
3 d.p. the consistent default for every other voltage/timing readout in the app:
`_fmt()` mV columns, `_band_labels` pulse_us, `_cell_labels` threshold_v (heatmap
axis / Stats "Threshold" column / mouse tooltip), Stats "Std" column, the crossings
label, the heatmap tooltip's delay readout, `_build_d_command()`'s pulse_us field
(was a bare `str()`, now `.3f`), and the Δ/Z/raw scale labels. Left UI-control
fields (rolling-window seconds, std colour thresholds, manual µV range,
baseline-age labels) at existing precision since they aren't calibration data.
(2026-07-03)

### README.md — Fixed broken build diary link

Both "Build diary" links pointed to `https://makies.com.au/pimd/`, which 404s.
Corrected to `https://makies.com.au/pulse-induction-metal-detector/`, the
actual live URL. Checked all other `*.md` files in the repo for broken links —
none found. (2026-07-01)

### src/pimd111.ui — v4.08's slider/QLineEdit changes applied for real

The v4.08 changelog entry (below, "8 ns grid snapping") claimed `pimd111_ui.py
also updated`, but `pimd111.ui` was never actually edited — none of the three
sub-changes ((a) QLineEdit fields, (b) frequency slider re-range, (c)
pulse/delay slider re-range) landed in the Designer source. This went
unnoticed for 5 versions because most of the mismatch was silent or benign
until now:

- **(a)** `lFreq`/`lPulse`/`lSample` stayed `QLabel`. `.text()`/`.setText()`
  work on both classes, but `editingFinished` (QLineEdit-only) doesn't — app
  crashed on startup (`AttributeError: 'QLabel' object has no attribute
  'editingFinished'`) since it's wired in `_setup_ui_connections()`.
- **(b)** `slFreq` stayed ranged 40–400 (old 0.1 kHz-unit scheme, default
  250) instead of 0–17 (index into `CLEAN_FREQS_KHZ`, default 10). Any slider
  move raised `IndexError: list index out of range` in the
  `valueChanged` lambda (`CLEAN_FREQS_KHZ[value]`).
- **(c)** `slPulse`/`slSample` stayed ranged in old 0.1 µs units (50–400/50–300)
  instead of 8 ns counts (625–5000/625–3750). This one was silent but wrong:
  the Python side reads the slider integer directly as an 8 ns count, so an
  old-scheme value like `slPulse=100` would have been sent to the MCU as
  0.8 µs instead of the intended 10.0 µs — a real pulse-width hazard, not just
  a display bug.

Fixed by changing `lFreq`/`lPulse`/`lSample` to `QLineEdit` (dropping
`lFreq`'s QLabel-only `textFormat` property) and correcting the three
sliders' `minimum`/`maximum`/`value` to match `apply_soc_defaults()`
(`slFreq`: 0–17, default 10 → 10.0 kHz; `slPulse`: 625–5000, default 2500 →
20.0 µs; `slSample`: 625–3750, default 1250 → 10.0 µs). `pimd111_ui.py`
regenerated from the corrected `.ui` via `pyuic6` (previously PyQt6-generated;
found already regenerated with `pyside6-uic`/PySide6 imports mid-session by
an untraced process — possibly an IDE auto-compile-on-save watcher pointed at
the wrong tool — which would have been its own crash: `pimd_gui.py` imports
PyQt6, not PySide6. Worth checking your editor's Qt tooling config if this
recurs.) Verified via `QT_QPA_PLATFORM=offscreen python pimd_gui.py`: starts
clean, no traceback, process stays up. (2026-07-02)

---

### src/pimd_delaycal.py — v1.20 — 3-decimal voltage headers + zigzag Auto Nudge

**(a)** Voltage column headers (main results table, both thermal tables, CSV export)
now show 3 decimal places (`4.000 V`) instead of 1 (`4.0 V`), for finer-grained
target-voltage sets. Three call sites updated: `_rebuild_table()`,
`_rebuild_thermal_tables()`, `export_csv()`. `_ch_label()`'s voltage formatting
(used only in activity-log messages, not a column header) left at 1 decimal.

**(b)** Auto Nudge's per-channel search direction was effectively one-directional:
`_auto_nudge_channel()` walked cumulatively further in the same direction each
attempt (`cur += d * nudge_us`) until exceeding the cap from the calibrated delay,
then flipped direction exactly once and gave up if that was also capped. Replaced
with an expanding zigzag measured from the calibrated delay every attempt:
`+nudge, -nudge, +2×nudge, -2×nudge, +3×nudge, ...`, continuing until the offset
exceeds the cap (existing best-std fallback in `_auto_finish()` still applies) or
the outer loop's max iterations/attempts is reached (unchanged). Per-channel state
`_auto_dir_flat`/`_auto_dir_flipped` replaced by a single attempt counter
`_auto_attempt_flat`. (2026-07-02)

### cal profile — cal_20260702_165109 — new profile geometry: geometric pulse ladder + geometric thresholds

Replaced the old profile (cal_profile_8b, pulse widths 6/10/20/30/40/50/75/100 µs,
linear thresholds 4.8→0.5 V) with a geometric pulse ladder
6/9/13.44/20/30/45/67.2/100 µs (×1.5 per step) and geometric thresholds
4.5→0.5 V (×0.76 per step). Frequencies snapped to the CLEAN_FREQS list
(50/31.25/20/15.625/10/6.25/4/3.125 kHz), duty held at 26.9–31.25%.
Rationale: pulse width and threshold each sample log-space; constant-ratio
spacing removes near-duplicate cells (old profile bunched 30–50 µs bands and
the top three threshold cells). NOTE: geometry change — frames from this
profile are not comparable with data logged under cal_profile_8b; per
DESIGN §10 the profile is the firmware↔ML contract. (2026-07-02)

### bench finding — decay is non-exponential across the sample window

Delay-cal data (runs 16:39 and 16:51, 2026-07-02) shows local decay time
constant shrinking monotonically from ≈3 µs near 4.5 V to ≈1.2 µs near
0.5 V; both linear- and geometric-threshold cals agree on the shape.
Suspected clamp-release proximity stretching the apparent τ at the top of
the window. (2026-07-02)

### open question — possible coil-current plateau above ~67 µs

In both cals the 67.2→100 µs band-to-band first-delay increment is the
smallest on the ladder (0.44–0.51 µs vs 0.56+ mid-ladder), consistent with
TX coil current flattening. Not confirmed — needs a scope measurement of
coil current vs pulse width (τ_coil). Bears on whether the 100 µs band
justifies its frame-time and thermal cost. (2026-07-02)

### src/pimd_delaycal.py — v1.21 — Auto Nudge log lines now identify the channel

Auto Nudge's zigzag nudge log (added in v1.20) printed `nudge #k: ±N ns from cal →
... µs` with no channel identifier. In parallel mode, several channels nudge per
iteration and each has its own independent attempt counter, so lines like
`nudge #11: +240 ns from cal → 7.480 µs` and `nudge #11: +240 ns from cal →
6.760 µs` appeared back-to-back with no way to tell which channel was which.
Both log lines in `_auto_nudge_channel()` (the nudge line and the "cap reached"
line) now prefixed with `self._ch_label(ch)`, matching the convention already
used elsewhere in the file (`_auto_evaluate_initial`, `_auto_finish`, etc.).
(2026-07-02)

### src/pimd_delaycal.py — v1.22 — Auto Nudge locks a channel's delay once it passes

In parallel mode, `_auto_evaluate_parallel()` re-measured every active channel's
std-dev on every iteration, including channels that had already passed. If a
passed channel's live std later drifted above threshold — noise, thermal drift,
or cross-talk while other channels were still being nudged and re-soaked — it
was pushed back into `still_bad` and re-nudged, silently moving a delay that had
already been accepted as good. New per-channel `_auto_locked_flat` sticks the
first time a channel passes; locked channels are excluded from `still_bad` and
`_auto_nudge_channel()` for the rest of the run, so their delay is frozen for
good. Their cell colour still tracks live pass/fail for visibility: green
(`_COL_DONE`) while still reading within threshold, new lavender
`_COL_AUTO_DRIFTED` if the live reading drifts back above threshold post-lock.
Sequential mode is unaffected — `_auto_evaluate_channel()` already permanently
advances past a channel the moment it passes and never revisits it. (2026-07-02)

### src/pimd_delaycal.py — v1.23 — Max iterations range raised 20 → 100

`sp_auto_max_iter`'s range was 1–20; raised to 1–100. The zigzag nudge search
(v1.20) needs more attempts than a single-direction walk to sweep out to the
cap at small step sizes — Sequential mode's per-channel max-attempts use in
particular was capping out before reaching the cap. (2026-07-02)

### cal profile — cal_2-7-26-base.json — FROZEN as operating profile

Final calibration of the new geometry (geometric pulse ladder
6/9/13.44/20/30/45/67.2/100 µs, geometric thresholds 4.5→0.5 V ×0.76/step).
Renamed from cal_20260702_180813 to cal_2-7-26-base.json. Conditions:
coil in air 500 mm above floor, bench-top PSU, extended warm-up to
thermal stability (repeat-cal deltas collapsed to within 8–32 ns of the
8 ns grid across all bands, vs up to −248 ns when run after only
minutes). All 72 cells passed auto-cal, 13 delays adjusted (mostly a
coherent +40 ns shift of the 4.5 V clamp-release column). This profile
supersedes cal_profile_8b; frames are not comparable with earlier
geometry (firmware↔ML contract, DESIGN §10). (2026-07-02)

### bench finding — 31.25 kHz is a noisy rep rate; band 2 moved to 25 kHz

With the 9 µs pulse unchanged, band 2 at 31.25 kHz showed row-wide noise
(σ 2–5 mV, three cells never settled); moving only the frequency to
25 kHz cured it (σ 0.02–0.10 mV). Noise followed the operating point,
not pulse/decay alignment — consistent with DESIGN §8 rep-rate/beat
sensitivity. Band 2 duty is now 22.5%. (2026-07-02)

### watch list — 4.5 V column and band 8 (3.125 kHz/100 µs)

4.5 V column sits at clamp-release (flattest part of decay): highest σ
and the column that needed the +40 ns nudge; fallback is a 4.4 V top
anchor if it misbehaves in the field. Band 8 means run a few % above
the column family with the highest band σ — heaviest, slowest-settling
band, same band as the suspected coil-current plateau (see earlier
open-question entry). No action; to be judged by labelled target data.
(2026-07-02)

### pimd_classviz.py — v1.16 — session dump recorder

Reworked the existing v1.06 "Record Frames" toggle (RAM-buffered raw W-frame
capture, flushed once on stop to `data/frames_*.csv`) into a self-describing
"Record Session" recorder for an AI analyst to work from as a standalone
file — no external profile file or operator memory required. Extended in
place per the request rather than adding a parallel recording path: same
button, same tap point (raw values before the 64-frame glitch filter and
before any baseline/display scaling), same auto-stop-on-profile-change/
stream-stop guards.

Saves to `data/sessions/session_YYYYMMDD_HHMMSS.csv`. Rows are now written
and flushed incrementally as each W frame arrives instead of buffered in RAM
and flushed once at stop — a crash or serial dropout mid-session loses at
most the last unflushed row, and because the file's lifecycle is tied only
to the explicit Start/Stop toggle, a transient gap in the frame stream never
restarts the file (it just shows up as a `firmware_time_ms` gap). The file
opens with a `#`-prefixed comment header: session start time, tool version,
the raw firmware `V` response (a `V` command is now sent on connect,
alongside the existing `E`/`Q4`, and parsed in `process_packet`), the
complete active profile embedded as one-line JSON, an explicit per-column
band/freq/pulse/delay/threshold map, and free-text session notes entered via
a small dialog when recording starts. Data rows: `pc_wallclock_iso`,
`firmware_time_ms`, all cell means in µV as received, plus a new `flagged`
column (1 if the existing 64-frame glitch filter marked any channel that
frame — previously computed and discarded, now surfaced instead of the
frame being dropped). Button text and status bar show frame count + elapsed
time while recording. (2026-07-02)

### src/pimd_classviz.py — v1.20 — replace Profile Builder tab with top-bar Load & Run

Removed the editable Profile Builder tab (`_build_profile_tab` and its band-table
editor/validation/save machinery — `_populate_profile_editor`, `_read_profile_from_editor`,
`_validate_profile_editor`, `_on_add_band_row`/`_on_remove_band_row`,
`_on_save_profile_file[_as]`/`_save_current_editor_as`, plus module-level
`_save_profile_file`/`_pad_json_floats`, now dead since `pimd_delaycal.py` already owns
profile authoring/saving independently). In its place, the top bar (above the tabs) now
has a "Saved profile:" `QComboBox` (populated from `data/profiles/*.json` via the existing
`_list_profile_files`/`_load_profile_file`) and a single "Load && Run" button
(`_on_load_run_profile`) that loads the selected file, sends it as a dynamic RAM-only
profile (`E`/D-command/`Q<DYNAMIC_PROFILE_INDEX>`/`G`), and calls `_apply_profile` —
collapsing the old two-step Load-then-Send&Run flow into one action, since there's no
longer an in-app editing step in between. `_build_d_command` is unchanged and reused as-is.
Editing a profile's bands/delays/thresholds is now delaycal-only. (2026-07-07)

### src/pimd_classviz.py — v1.21 — Training Session tab for guided corpus capture

Added a "Training Session" tab (index 2) to replace the ad hoc Stats-tab mark hotkeys
(`1`/`2`/`3`/`0`/Space, hardcoded to 5/10/15cm) with a proper guided-capture workflow for
building an ML signature corpus. A 5-column table (Index/Target/Distance(cm)/Time-at-
Target/Settledness; Index and the two live columns are read-only, Target/Distance are
double-click-editable) lets the operator build an ordered list of targets/distances (default
single row: `air`/`0`). Start/Pause/Stop buttons plus a Space-bar step-advance drive the
capture: Start opens a session (reusing `_toggle_record_frames`/`_session_start` verbatim,
same as the existing Record Session button) and immediately writes the first row's
`# mark: <iso-ts>, <text>` line (reusing `_append_mark` verbatim); each Space press writes
the next row's mark and advances, so every row's mark lands at the *start* of its own dwell
window (`pimd_features.py`'s `segment_from_marks` needs this — a mark written on *leaving* a
target would silently lose that target's own dwell data). Mark text is the literal `air`
(no `@` suffix — exact-match requirement of the downstream parser's `is_air` check) when
Target is "air", else `<target> @<distance>`. Pressing Space on the last row auto-finalizes
and saves the session (the explicit "ensure session is saved" requirement) by toggling the
same `pb_record` checkbox the Stats tab's Record Session button uses. Pause freezes the
Time-at-Target column and gates `process_packet`'s frame-row write (`and not
self._training_paused`) so a pause doesn't attribute movement-artifact frames to the current
target's plateau, while Settledness (rolling per-channel std over a tunable frame window,
same statistic `_update_stats_table` already uses, aggregated to one mV number) keeps
updating live so the operator can watch the signal restabilize before resuming. Validation
(green ✓/red ✗ label) requires every row have a non-empty target and numeric distance, and
at least one row's target be exactly "air" (case-insensitive) — a hard requirement of
`pimd_features.py`, which skips any session with zero air marks entirely.

Target lists are independently saveable/loadable as reusable templates
(`data/training_lists/*.json`, mirrors the existing Saved-profile pattern:
`_list_training_list_files`/`_load_training_list_file`/`_save_training_list_file`) — Save
does not require an "air" row (a template is just a shape; the air-row rule is about a
session being valid for the extractor, checked at Start).

`_session_stop()` now centrally resets the Training tab's UI state (`_reset_training_ui`)
whenever a training session was active, regardless of which of its three call sites
triggered the stop (the Stats-tab toggle, `_apply_profile`'s force-stop on a profile change,
`start_stop`'s force-stop on serial disconnect) — a single source of truth instead of
duplicating the reset at each site, so a profile switch or disconnect mid-training-session
can't leave the tab stuck showing "started" with a closed file underneath it.

Also: merged the top bar's separate "Saved profile" row into the same row as
Port/Connect/Start (one row instead of two), and removed the Stats tab's manual mark UI
(`le_mark_label`, `lbl_mark_log`, `_on_mark_hotkey`, `_update_mark_log_display`, `_mark_log`
deque) now that the Training Session tab's Space-bar workflow replaces it — `eventFilter`'s
Space dispatch is repurposed to `_on_training_space()` (the `1`/`2`/`3`/`0` dispatch is
removed outright; new `QAbstractItemView` import for the table's `DoubleClicked`-only edit
trigger, chosen specifically so a table-focused Space keypress can never enter cell-edit
mode). (2026-07-07)

### src/pimd_features.py — v3 — fix parser dropping every marked session (0 rows)

`parse_session_file()`'s single pass flipped `header_done = True` on the first non-`#`
line (the CSV data-header row) and never checked for a leading `#` again afterward. But
`# mark: ...` lines are written live as the operator advances targets mid-recording
(`pimd_classviz.py`'s hotkey feature since v1.19, and its Training Session tab since
v1.21), so in any real session they land interspersed among data rows, not batched before
the first one. Every mark after the first data row was therefore comma-split as if it were
a data row and crashed on `int(' air')` / `int(' copper pipe @5')`, causing the whole
session to be `[SKIP]`ped with 0 rows written and no hard error — surfaced when a user ran
the tool against the first real Training-Session-tab-recorded session
(`session_20260707_125642.csv`) and got a header-only output file. Fixed by recognizing
and parsing `#`-prefixed mark lines in the post-header data-row branch too (new shared
`_parse_mark_content()` helper used by both the pre- and post-header branches, so they
can't drift apart). Verified against that session (13 marks, 9 non-air plateaus × 72
channels = 648 rows, correct target/distance breakdown) and against all pre-existing
no-marks sessions (no regression). This bug predates the file's v1 and had never been
exercised against a genuinely marked session before now. (2026-07-07)

### src/pimd_corpus_check.py — v1.0 — corpus-level acceptance checks

Brought over from the separate `pca-explore-fix` worktree/branch (commits `0038810`,
`e4ed27a`, both 2026-07-04), where it was originally authored — not a new change, just
merging it onto `main`. New script (Stage 1 of `ML/PIMD_v2_acceptance_checklist.md`). Runs
six checks against one or two corpus CSVs (long format like
`assets/PIMD_target_corpus_signatures.csv`, or the wide `c00..c71` format, auto-detected):
shape distance-invariance (cosine 5v10/5v15 per capture, plus a per-corpus pass count),
split-half SNR per signature, canary-session consistency (`CANARY-START`/`CANARY-END`
target rows), repeat consistency (targets marked `(rpt)` or `REPEAT`, matched to their base
capture by name — falls back to a first-word + shared-weight-token match since real corpus
naming isn't always a clean suffix strip, e.g. "brass block 370g (rpt)" vs "brass 370g"),
distance falloff (log-log power fit over 5/10/15 cm plus an explicit solder 5cm/15cm
contamination ratio), and cross-campaign 5cm shape repeatability (only when two corpora are
given). Everything prints as one flat table (check, metric, value, pass band, PASS/FAIL/SKIP);
exits nonzero on any FAIL so it can gate a capture day. Re-verified on `main` against
`assets/PIMD_target_corpus_signatures.csv`: 128 checks, 109 PASS/18 FAIL/1 SKIP, reproducing
the same figures as the original run (e.g. solder's 1.21x 5→15cm amplitude ratio) — no path
or behavior differences between the two branches. Plain numpy/pandas only. (2026-07-07)

### src/requirements.txt — add pandas, scikit-learn, matplotlib

Also brought over from the same worktree/branch (commit `0038810`, 2026-07-04).
`pimd_pca_explore.py`, `pimd_knn_baseline.py`, and now `pimd_corpus_check.py` import
`pandas`/`sklearn`/`matplotlib`, but `src/requirements.txt` never listed them on `main` —
`pip install -r src/requirements.txt` in a clean venv would leave all three scripts failing
on the first import. (2026-07-07)

### src/pimd_features.py — v4 — auto-suffix repeat visits within a session

A guided Training Session run can legitimately revisit the same target/distance more than
once in one session (e.g. running a saved target list twice to check repeatability), but
`segment_from_marks()` gave every plateau's target label only `(session, target,
distance_cm)` as its identity in the output corpus. A second visit to, say, "copper pipe"
@5cm therefore had the exact same identity as the first, and any groupby-style corpus tool
would silently merge the two into one 144-cell group instead of two distinct 72-cell
captures. Surfaced by `pimd_corpus_check.py`'s `load_corpus()` correctly refusing a real
two-visit session (`session_20260707_125642.csv`: "copper pipe" visited twice, "steel
spanner" once) with "mixed cell counts across rows [72, 144] — refusing to mix profile
geometries (DESIGN §11)" — that guard was doing its job; the underlying data was genuinely
ambiguous, not a false positive. Fixed: repeat visits within a session are now auto-suffixed
`(rpt)` for the 2nd visit, `(rpt3)`/`(rpt4)`/... beyond that — `(rpt)` for the 2nd visit
matches the pre-existing hand-corpus naming convention `pimd_corpus_check.py`'s repeat-
consistency check already looks for, so the common two-visit case needs no other tool
changes. Verified: re-running against that session now gives three distinct 72-row groups
(`copper pipe` / `copper pipe (rpt)` / `steel spanner`) and `pimd_corpus_check.py`'s
repeat-consistency check correctly compares the repeat against its base capture at all 3
distances instead of crashing. (2026-07-07)

### src/pimd_corpus_check.py — v1.1 — recognize numbered repeat suffixes

Companion to the `pimd_features.py` v4 fix above: widened `REPEAT_MARK_RE` from `\(rpt\)`
to `\(rpt\d*\)` so `(rpt3)`, `(rpt4)`, etc. (3rd+ same-session repeat visits) are also
recognized by the repeat-consistency check, not just a bare `(rpt)` for the 2nd visit.
(2026-07-07)

### src/pimd_corpus_check.py — v1.2 — remove solder-specific falloff sub-check

Removed the solder-specific 5cm/15cm amplitude-ratio sub-check from check 5
(distance falloff): it always printed a row — PASS/FAIL when a "solder"-named
target was present, else an uninformative "n/a (no solder target)" SKIP on
every other corpus — which read as clutter on any corpus not built around
that specific canary. The general per-target falloff fit (n exponent, worst
fit/measured ratio) is unaffected and still runs for every target regardless
of name, solder included — verified against `assets/PIMD_target_corpus_signatures.csv`
(128 → 127 checks, 18 → 17 FAIL, exactly the one removed row; "solder roll
260g"'s own falloff-fit rows unchanged). Removed `SOLDER_FALLOFF_MIN` along
with it. (2026-07-07)

### src/pimd_classviz.py — v1.22 — clear stale columns + auto-derive session notes

Two Training Session tab fixes. First: pressing Start no longer leaves the previous run's
Time-at-Target/Settledness values sitting in rows the new run hasn't reached yet — new
`_clear_training_live_columns()` resets every row's Time and Settledness cells to `—`
before the run begins (`_reset_training_ui()` on stop/finalize cleared the button/table
*enablement* state but never touched these cell values, so a re-run of the same saved list
showed stale numbers until the operator physically stepped past each row again). Second:
Start no longer pops up the interactive "Session notes" `QInputDialog` — there's nothing to
type that isn't already in the table, so notes are now auto-derived from the run list itself
(new `_build_training_notes()`: "Training Session run list:" followed by one "N. target
@distancecm" line per row) and passed straight through a new optional `notes` parameter on
`_session_start()` (still prompts interactively when called with `notes=None`, unchanged for
the plain Stats-tab "Record Session" button, which has no run list to derive anything from).
Since `_session_start()` is now called directly rather than triggered indirectly via
`pb_record.setChecked(True)`, the checkbox's checked state is synced afterward through
`blockSignals` so a later click still reads as "stop" rather than double-firing
`_session_start()`. Verified headlessly: `QInputDialog.getMultiLineText` is never invoked
during a Training start, the auto-derived notes lines land correctly in the session CSV's
`# session_notes:` header, and a row not yet reached in a fresh run shows `—`/`—` rather than
a previous run's leftover values. (2026-07-07)

### src/pimd_features.py — v5 — plateau_amp_mV restored to v1 L2-norm convention

`plateau_amp_mV` was emitting `mean(|delta_mV|)` per cell while the v1 hand-built corpus
and the canary-strength unit definition (1 unit ≡ copper pipe 120g @10cm ≡ 45 mV L2) use
the L2 norm of the 72-cell drift-corrected delta vector — the same column name, two
different quantities, ~9x apart (measured: copper pipe 120g @5cm read 4.96 here vs. 113.7
(L2) in the v1 corpus, a ~23x apparent gap — only ~9x of which was this bug; the remaining
~2.3–3x is a separate, already-known, out-of-scope bench-geometry difference between the
v1/v2 setups). This corrupted any cross-campaign amplitude comparison and the canary-unit
definition. Restored the L2 convention; `splithalf_floor` changed to match (L2 norm of the
split-half-median difference vector, still halved) so floor/amp stays a meaningful,
consistent fraction for the noisy-quality gate. The old `mean(|delta_mV|)` quantity is
still useful, so it's kept — appended as a new `amp_mean_abs_mV` column at the end of both
the long and wide row schemas (existing readers that select columns by name are
unaffected). Documented in a comment block above `compute_plateau_stats()` and in
`wide_header_lines()`'s `# columns:` comment.

Checked `pimd_corpus_check.py` for absolute-mV thresholds assuming the old convention: none
exist — every amplitude-adjacent check is ratio- or cosine-based, so no threshold values
needed changing; no code edit made there. Verified against `session_20260707_134922.csv`
(regenerated corpus, before/after this fix): all 29 `pimd_corpus_check.py` verdicts
(PASS/FAIL/SKIP) are identical before vs. after. Flagging honestly: not all the underlying
ratio *values* are identical — SNR (amp/splithalf), the falloff n-exponent, and repeat
amp-ratios shifted somewhat (e.g. copper pipe @5cm SNR: 67.0 → 34.5, still comfortably
above the 10.0 gate), because L2 norm and mean-abs aren't exactly proportional between two
*different* vectors (amp's delta_mV vs splithalf's half-difference vector, or the same
target's vector at a different distance) — only cosine-similarity checks and same-vector
ratios are exactly convention-invariant; these particular ratios are empirically
verdict-stable on this dataset, not mathematically guaranteed to stay so on all future data.

One row, before → after (`session_20260707_134922, copper pipe, 5cm`):
```
before: ...,delta_mV=-7.105,plateau_amp_mV=4.957, splithalf_floor=0.074,quality=ok,amp_mean_abs_mV=4.957
after:  ...,delta_mV=-7.105,plateau_amp_mV=49.503,splithalf_floor=1.436,quality=ok,amp_mean_abs_mV=4.957
```
(2026-07-07)

### campaign — C2 — rig change declared

The bench rig changed since the v1 campaign (builder-confirmed, 2026-07-07). Per the
never-mix-geometries principle (DESIGN §10), captures made on the new rig start a new
campaign: campaign 2 (rig 2). Measured consequences, from `session_20260707_134922` and
`session_20260707_143723`: absolute amplitudes ~2.3× below v1 at nominal distances, falloff
exponents 1.0–1.15 vs v1's 1.3–1.6, uniformly across all targets; and extended targets
(spanner, cast iron trivet, galvanized pipe) show a real, repeatable @5cm shape change
(cos(5,15) 0.936–0.969) while cos(10,15) stays high, absent from v1 at the same nominal
distances (compact copper unaffected, cos(5,15) 0.990). Consequence: v1-derived absolute
constants (F1's 12/17 statistic, F9's falloff exponents, the 45 mV canary-unit constant,
acceptance-checklist row 1.6) are rig-1 facts, not predictions for rig 2 — retired as such,
detailed in `ML/V2/ML_FINDINGS.md` F11. The v1 corpus itself is untouched and remains valid
for rig 1. The physical question of *what* changed on the rig is declared, not diagnosed —
out of scope here. (2026-07-07)

### src/pimd_corpus_check.py — v1.3 — campaign 2 support: canary pairing, cross-session repeat, near-field AMBER, --baseline gating

Four changes, all driven by the campaign 2 (rig change) declaration above. **(A)** Fixed
`check_canary()`: it matched target names by bare exact-match against `{"CANARY-START",
"CANARY-END"}`, so real canary rows named `"copper pipe CANARY-START"`/`"copper pipe
CANARY-END"` (`train-s1.csv`) were invisible to it ("0 pairs found") even though the SNR
check already proved both were captured. Now matches by suffix (new `strip_canary_suffix()`
helper, replaces `CANARY_LABELS`) so any `"<base> CANARY-START"`/`"<base> CANARY-END"` pairs
correctly, and adds a `drift status` row per pair reporting protocol v2's drift-flag
criterion (either the shape-cos or amp-ratio check failing ⇒ session drift-flagged, 15cm
rows downgraded — `pimd_features.py`'s quality column handles the actual downgrade, this
just reports). Canary rows are now also excluded from `check_shape_invariance()` and
`check_falloff()` (5cm-only; would otherwise pollute per-target checks). **(B)** New
`check_repeat_cross_session()`: the same target+distance captured in two different sessions
(e.g. a capture plan revisiting "copper pipe" in session s1 and again in s4) now gets its
own shape-cos/amp-ratio repeat-consistency rows labelled with both session IDs — additional
to, and independent of, the existing within-session `(rpt)` handling (unchanged). **(C)**
`check_shape_invariance()` adds a `cos(10v15)` row per target. Extended objects genuinely
change shape at 5cm on this rig while agreeing at 10/15cm — physics, not capture error — so
`cos(5,15) < 0.97` but `cos(10,15) >= 0.97` now verdicts `AMBER (near-field @5, extended
target?)` instead of `FAIL`; both low is still `FAIL`. The `cos(5,15)` roll-up is now
report-only; a new `cos(10,15)` roll-up is the real per-corpus gate. AMBER is tracked
alongside PASS/FAIL/SKIP in the summary line and never contributes to the exit code.
**(D)** Cross-campaign comparison is now gated behind an explicit `--baseline <corpus_csv>`
argument (replaces the old ambiguous positional 2nd-corpus-file convention — only the
primary corpus gets the full acceptance suite). No baseline (default): one SKIP row,
"cross-campaign checks skipped (campaign 2; no rig-1 baseline applicable)". With one:
results are labelled "(informational, cross-rig)" and excluded from the exit-code gate — a
different rig/campaign is a reference point, not a same-rig acceptance criterion. Checked
for absolute-mV thresholds elsewhere in this file assuming the old `plateau_amp_mV`
mean-abs convention (per `pimd_features.py` v5): none exist, every amplitude-adjacent check
here is already ratio- or cosine-based.

Verified against `train-s1.csv` (`session_20260707_143723`): canary shape-cos=0.9983/amp
ratio=0.952 now report real values (previously invisible/SKIPped); spanner/trivet/galvanized
`cos(5,15)` FAILs correctly flip to AMBER (their `cos(10,15)` = 0.9887/0.9863/0.9963, all
≥ 0.97); copper pipe/SNR/falloff rows are byte-for-byte identical to the pre-this-change run
(diffed directly against a saved copy of the prior file version); `--baseline
PIMD_target_corpus_signatures_v1.csv` runs without error (0 common 5cm target names — v1
uses weight-suffixed names like "copper pipe 120g", a naming-convention mismatch between
corpora, not a code defect; fixing that fuzzy-matching is out of scope here). (2026-07-07)

### ML/V2/ML_FINDINGS.md — v1.1 — F11: rig change declared, v1 constants retired

Added F11 (see the "campaign — C2" entry above for the full context): the v2 capture rig
differs from v1's, uniformly across all targets in amplitude, falloff exponent, and a
repeatable extended-target near-field shape change at 5cm. Retires v1's absolute-constant
predictions (F1's 12/17 statistic, F9's exponents, the 45 mV canary-unit constant,
acceptance-checklist row 1.6) as rig-1 facts, not rig-2 predictions — v1's corpus and
shape/ratio findings are untouched and remain valid for rig 1. Canary strength unit
redefined on rig 2: 1 unit ≡ copper pipe @10cm = 26.123 mV (`plateau_amp_mV`, L2 convention,
`train-s1.csv`). (2026-07-07)

### src/pimd_v2_findings.py — v1.0 — replaces pimd_knn_baseline.py / pimd_pca_explore.py

`pimd_v2_findings.py` is the reproduction script for `ML_Findings_v2.md` — every number in
findings F12-F21 is printed by this script from the campaign-2 corpus alone, closing the
"open gaps" pattern flagged in `ML_FINDINGS.md` v1.0 (open gap 3: "v2 comparison run").
Removed `src/pimd_knn_baseline.py` (v1.1, LODO/LOTO 1-NN and logistic-regression baseline
classifiers) and `src/pimd_pca_explore.py` (v1.0, PCA scree/loading/PC1-PC2 exploration) —
both were v1-corpus-specific one-off analysis scripts superseded by this single script's
campaign-2 reproduction of the same PCA/classification-adjacent findings plus the new F12-F21
material; keeping the old scripts around next to a v1-only corpus they were written against
would be dead weight. Neither file was imported by anything else in the repo (verified: no
other reference across `*.py`/`*.md` outside their own headers and their own historical
`CHANGELOG.md` entries above, which are left untouched as history). (2026-07-07)

### src/pimd_classify.py — v1.0 — new PyQt6 live/replay Mode 2 signature classifier

New tool, fourth in the gui/classviz/delaycal/classify family: classifies Mode 2 frames from
either a live serial port or a recorded ClassViz session CSV through one shared, Qt-free
pipeline (`Engine.process_frame`), so replay and live are provably the same code path — a
`--headless <session.csv>` CLI mode runs the identical `Engine` with zero PyQt6/pyqtgraph
import at runtime, for CI/no-hardware testing. Implements the two-stage architecture from
`ML_Findings_v2.md`'s "Consequences for pimd_classify" section: Stage A is a causal EMA air
baseline (F2) feeding an amplitude-hysteresis + min-duration event state machine; Stage B1 is
`pimd_v2_findings.py`'s continuum rule (F13/F16, reused verbatim — not reimplemented) reporting
family + the ladder-clamped continuum value; Stage B2 is 1-NN cosine against the corpus usable
set (SNR≥10 gate, F12), reporting margin in repeat-floor units (0.0062, F15) with pile-level
fallback below 2× floor and open-set "unknown object" reject above 8× floor (K, F15/F17).
Canary rows are folded into their base target name in the identity pool (design decision,
flagged for review — canaries are the same physical object and F20 shows high repeatability,
so folding adds real samples rather than discarding them). Reuses rather than reimplements:
`pimd_features.py`'s session parser (marks-anywhere-safe, the v3 fix), profile-geometry guard
(DESIGN §11), and wide-format signature writer (feeds "Dump signatures" straight back into
`pimd_corpus_check.py`); `pimd_corpus_check.py`'s corpus loader, cosine primitive, and
canary-suffix stripper; `pimd_v2_findings.py`'s band-mean/crossing/continuum functions.

Verification: `--headless` replay of all four 2026-07-07 sessions gives 6/6/5/5 (all-events)
family-correctness against `pimd_v2_findings.FAM3` (verification-only, never consulted by the
live classifier itself, which stays a physics rule with no fixed target list) — a perfect
score. Event counts (6, 6, 6, 4) match each session's real object-visit groups; the amplitude
hysteresis correctly merges a single visit's 5/10/15cm distance changes into one event (the
target is never fully removed between distances) rather than splitting per mark, which is the
physically correct behaviour for a threshold detector, not a segmentation bug. Tuned
`enter_amp_mV`/`exit_amp_mV`/`min_duration_s`/`exit_debounce_s` empirically against these four
sessions (no spec-given seed values existed for these, unlike the floor/K/canary/SNR-gate
constants) — found and fixed a baseline-staleness interaction during tuning: the EMA baseline
freezes while non-air, so thermal drift accumulated during a long detection run must not
exceed the exit threshold or the detector can never register a genuine return to air; the
final defaults (enter=6.0, exit=4.0 mV, min_duration=0.5s, exit_debounce=0.3s) clear this
session set's measured air-noise floor (~1.2-2mV) and drift-during-typical-dwell margin.
Confirmed via a LODO-style sweep across the whole corpus that with only 26-34 usable rows
across ~10 objects, individual-row 1-NN margins are frequently thin project-wide (top-1 label
is correct roughly half the time per row-level LODO, matching the ballpark of F17's own
pooled 58%; comfortable 2×-floor margins are rare) — the "identified" bucket firing rarely in
favour of the deliberately conservative "pile-level" fallback is the open-set safety margin
working as designed against a still-small corpus, not a classifier bug; documented rather than
loosened, since forcing more "identified" verdicts would risk overconfident misclassification.
Confirmed `--speed` (a headless test aid that sleeps between `process_frame()` calls without
touching the timestamps fed to the pipeline) produces byte-identical event logs, proving
replay speed cannot change a decision. Confirmed "Dump signatures" output round-trips cleanly
through `pimd_corpus_check.sniff_format`/`load_wide`. Confirmed a hand-edited mismatched
profile is cleanly refused (exit code 2, no traceback) in headless mode. GUI smoke-tested
under `QT_QPA_PLATFORM=offscreen`: full session load + frame-by-frame replay + all three
exports + Settings dialog + seek-driven engine rebuild, all exception-free; caught and fixed a
real crash found this way (`_redraw()`'s "current frame" heatmap branch read a placeholder
zero-vector expression that blew up with a reshape error before the engine had processed its
first frame — now tracks the actual last-computed per-frame delta and guards the no-frame-yet
case). Live-serial and interactive visual correctness were not (and cannot be) exercised here
and still need a human bench test — the code is structured so the session-replay path already
exercises the entire pipeline above the frame-source adapter. (2026-07-11)

Live-hardware bench test surfaced two real bugs the offscreen smoke test couldn't reach.
(1) `_on_start_live_clicked` sent a bare `Q<n>`/`G` against a placeholder profile index instead
of loading cal_72_air_v2 onto the board first -- cal_72_air_v2 is not one of the board's
compiled static profiles (those are the 45-channel CLASSIFY_EP family), so a bare `Q<n>` either
selected the wrong, already-active (lighter-duty) profile or nothing at all. Measured effect:
~50mA supply draw instead of cal_72_air_v2's expected ~200mA, and every incoming `W` frame
silently dropped because its profile index never matched the placeholder. Fixed by adding
`build_d_command()`/`DYNAMIC_PROFILE_INDEX=5` (ported verbatim from `pimd_classviz.py`'s
`_build_d_command`/`_on_load_run_profile`) and a new `LiveFrameSource.load_and_start(profile)`
that sends the same `E` / `D<cmd>` / `Q5` / `G` sequence ClassViz's "Load and Run" uses --
pushing the profile as a RAM-only dynamic profile (no flash writes, DESIGN §11) rather than
guessing at a pre-existing static index. (2) The Start button never reflected running state
(stayed yellow/"Start" regardless) and firmware `V`/`L` responses were parsed and then silently
discarded (`line_received` had no connected slot) -- made it checkable with proper
Running/green ↔ Start/yellow toggling and wired `line_received` to surface raw board responses
on the status bar, since there was previously no live feedback at all that the board was
talking back. (2026-07-11)

The D-command fix alone did not resolve a live bench report of unchanged (low) supply current
and no data reaching the GUI, and no exception was raised, so the fault sits somewhere between
"bytes never leave the PC" and "bytes arrive but never make it to a rendered frame" with no
visibility into which. Added counter-based diagnostics rather than guessing further:
`LiveFrameSource` now counts every raw line received, every `W`-prefixed line seen, and splits
non-matches by cause (wrong profile index / wrong channel count / parse error); `send()` now
checks its `QSerialPort.write()` return value against the encoded length and reports short
writes; a new `command_sent` signal echoes each transmitted command to the status bar; and
`_redraw()` shows the running `rx N lines, M W-frames (...)` counter summary in the status bar
whenever Start is checked, independent of whether any frame has been fed to the pipeline yet
(the previous code path only updated the footer after a frame reached the engine, so a fully
silent link looked identical to a working one that just hadn't rendered yet). This turns "no
data" into one of: rx 0 lines (nothing coming back at all -- port/wiring/firmware-not-running),
rx N lines but 0 W-frames (board responding but not streaming, or a different frame type),
W-frames arriving but all wrong-idx (profile index still mismatched), or W-frames matched but
still nothing on screen (a GUI-side rendering bug, now isolated from the link itself). Not yet
confirmed against hardware -- next bench attempt should report which bucket the counters land
in. (2026-07-11)


### src/pimd_classviz.py — v1.15 — Stats: Std colour bands + row-height +/−

Stats tab controls row: two QDoubleSpinBox widgets (lower/upper, default 0.50/1.00 mV)
set colour thresholds for the Std (mV) column — green (< lower), yellow (between), red
(> upper) using the same RGB values as MY_GREEN/YELLOW/RED used throughout the app.
Two +/− QPushButtons adjust `tbl_stats` default row section height in 4 px steps
(clamped 12–48 px) so all rows stay visible at any density.  QBrush/QColor imported
from PyQt6.QtGui. (2026-06-21)

---

## Archive — consolidated 2026-06-21

### src/pimd_scope.py — removed — superseded by pimd_classviz.py

pimd_scope.py (v4.02, Mode 2 streaming visualiser) removed from the repository.
All functionality is covered by pimd_classviz.py. (2026-06-21)

---

### src/pimd_delaycal.py — v1.19 — Auto Nudge parallel / sequential toggle

Re-introduces parallel Auto Nudge mode (the v1.07 architecture) alongside the
existing sequential mode, selectable with a new "Sequential" checkbox in the
Auto row.  Default (unchecked) = parallel: all bad channels are nudged together
before each shared soak, completing in 1 + max_iterations soaks regardless of
how many channels are bad (vs 1 + N×max_attempts for sequential).  New
`_auto_evaluate_parallel()` evaluates all active channels, tracks best-std/delay
per channel, nudges all still-bad channels via the existing `_auto_nudge_channel()`
(which handles direction, cap, and flip), then re-soaks.  The "Max att/cell:"
label dynamically renames to "Max iterations:" in parallel mode.  Mode is logged
at run start and persisted in settings as `'auto_sequential'`. (2026-06-21)

---

### src/pimd_delaycal.py — v1.18 — draggable left/right splitter

Left column (config panel + activity log) was fixed at 420 px and did not grow
when the window was resized.  Replaced the `QHBoxLayout` content row with a
horizontal `QSplitter` (`h_splitter`); the left column is now a `QWidget` with
`setMinimumWidth(300)` and the right pane takes `stretchFactor=1`.  Removed both
`setFixedWidth(420)` calls from `cfg_box` and `log_box_grp`.  Splitter position
is saved as `'h_splitter'` in settings and restored on startup alongside the
existing vertical splitter. (2026-06-21)

---

### src/pimd_delaycal.py — v1.17 — thermal monitoring tables rows in ascending pulse_us order

"Latest mean" and "Std dev" thermal monitoring tables now display rows sorted
ascending by pulse_us (shortest delay first); the calibration table row order is
unchanged (run order).  `_rebuild_thermal_tables()` computes `_thermal_display_order`
(display_row → protocol_band) and `_thermal_proto_to_display` (inverse) and uses
the sorted order for row labels.  `_update_thermal_tables()` iterates by display
row `d` (mapping back to protocol band `b` for channel data), so value and colour
updates remain correct.  `_auto_color_cell()` applies colour to the calibration
table at row `b` and to the thermal tables at row `d = _thermal_proto_to_display[b]`,
preserving Auto Nudge cell highlighting. (2026-06-21)

---

### src/pimd_classviz.py — v1.14 — stats table and profile editor rows in ascending delay order

Stats table and Profile Builder table rows are now sorted by first delay value
ascending (lowest delay / highest frequency first).  Added `_band_stats_order`
and `_stats_band_labels` to `_set_profile_dims()` (ascending, the reverse of
`_band_display_order`); `_rebuild_stats_table()` and `_update_stats_table()` now
use these, preserving the correct row↔protocol-channel mapping so per-cell values
continue to track the right channel.  `_populate_profile_editor()` sorts bands by
`delays_us[0]` ascending before filling the table.  Heatmap display order is
unchanged (still descending, highest delay at top). (2026-06-21)

---

### src/pimd_classviz.py — v1.13 — remove single-cell isolation tab section

Removed the Single-cell isolation group box from the Stats tab (now renamed 'Stats'
from 'Stats && Isolation') and all supporting code: `_rebuild_single_cell_combos()`,
`_on_sc_band_changed()`, `_update_sc_info()`, `_run_single_cell()`, `_resume_sweep()`,
`_update_sc_button_states()`, and the Mode-1 `*` packet branch in `process_packet()`.
`self._mode` and `self._sc_buf` state removed from `__init__()`.  `start_stop()`
and `_on_send_run_profile()` simplified — no longer need to exit single-cell mode
before starting/stopping.  `sc_ds` removed from settings persistence. (2026-06-21)

---

### src/pimd_classviz.py — v1.12 — heatmap row sort by delay descending + updated band label format

Added `_band_display_order` (sorted by `delays_us[0]` descending) so that heatmap
rows are always shown in decreasing delay order regardless of the profile's stream
order — required for new profiles that interleave high/low pulse-width bands to
flatten thermal characteristics.  `_display_band_labels` is the display-ordered
copy used by the heatmap axes, stats table, and mouse tooltip; `_band_labels` and
`_bands_meta` remain in protocol order so single-cell commands and CSV logging are
unaffected.  `_redraw()` applies the permutation to raw data, mean, and std before
passing to `_compute_display_matrix()`; `_update_crossings()` maps display band
index back to protocol index when accessing `_nominal_baseline_uv`.  Band label
format changed from `'40.000µs/10.601kHz'` to `'10,601Hz / 40.0µs'` (freq in Hz
with thousands separator, pulse in µs to 1 d.p.), matching pimd_delaycal.py.
(2026-06-21)

---

### src/pimd_delaycal.py — v1.16 — row-label format: Hz with thousands separator, pulse to 1 d.p.

_row_label() rewritten: converts freq_khz × 1000 to an integer Hz value, formats
it with Python's {:,} thousands separator, and formats pulse_us to exactly 1
decimal place.  Produces labels like '31,250Hz / 6.2us' instead of the previous
'31.25kHz/6us'.  All three tables (calibration, thermal mean, thermal std-dev)
and the activity-log / progress-label references update automatically as they all
call _row_label(). (2026-06-21)

---

### src/pimd_delaycal.py — v1.15 — coarse+fine two-phase sweep per freq/pulse pair

For each freq/pulse pair, a fast coarse hunt (new sp_coarse_step spinbox, default
1 µs) now steps up from the start delay until the ADC reading drops below a
configurable signal-detect voltage (new sp_signal_v spinbox, default 4.9 V),
indicating real signal is present.  The sweep then backs up to the last clean
coarse position and switches to the existing fine step for accurate threshold
interpolation.  This avoids tens of wasted serial round-trips for long-pulse pairs
(e.g. 1.6 kHz / 100 µs) where the first real signal may only appear at 10 µs or
beyond.  If signal appears at the very first coarse step, the backup target falls
back to start_delay.  When coarse_step <= fine step, the coarse phase is skipped
entirely (pure fine scan, backward compatible).  Log lines show 'COARSE' prefix
during hunt; progress label shows "Coarse scan" instead of threshold count.
_advance_pair() now resets _coarse_phase for each new pair.  'Step size:' label
renamed 'Fine step:' for clarity.  Settings keys 'coarse_step' and 'signal_v'
added to _load_settings() / _save_settings(). (2026-06-21)

---

### src/pimd_gui.py — v4.13 — settings persistence (port, freq, pulse, delay, toggles, scale, geometry)

Added _load_settings() / _save_settings() following the identical pattern used
by pimd_delaycal.py.  Saves to data/gui_settings.json on close; restores on
startup at end of my_init() (after apply_soc_defaults()) so saved values
override SOC defaults.  Fields persisted: port, freq_hz (exact lFreq text),
pulse_us, delay_us, down_sample factor, avg_n, Boxcar and Raw-Avg toggle states,
VoltageButtonGroup and TimeButtonGroup checked IDs, and window width/height/x/y.
Added json and os imports; added SETTINGS_PATH constant. (2026-06-21)

---

### src/pimd_classviz.py — v1.11 — settings persistence (port, heatmap controls, geometry)

Added _load_settings() / _save_settings() following the identical pattern used
by pimd_delaycal.py.  Saves to data/classviz_settings.json on close; restores
at end of __init__() after _build_ui().  Fields persisted: port, capture N,
rolling T, display mode index, baseline mode index, stats std-dev window,
single-cell downsample, manual range µV, autoscale flag, and window
width/height/x/y.  Removed the hardcoded window.resize(1100, 900) from
__main__ — first-run default is now handled by the except branch of
_load_settings(). (2026-06-21)

---

### src/pimd_delaycal.py — v1.14 — dynamic thermal-table minimum height; all rows always visible

_rebuild_thermal_tables now computes each table's minimumHeight as
28 px (header) + n_rows × 30 px + 4 px (border), floored at 120 px.  With 6
freq/pulse bands the minimum becomes 212 px, ensuring all rows are visible
without a scrollbar regardless of band count.  Previously the static 120 px
floor was not enough to show > 4-5 rows and the bottom row(s) were cut off.
(2026-06-21)

---

### src/pimd_delaycal.py — v1.13 — 'Latest delay (us):' label; top-pane-first splitter shrink

Added a bold 'Latest delay (us):' label directly above the calibration table to
match the 'Latest mean (mV):' and 'Std dev (mV):' labels already present on the
lower two tables.  Changed splitter stretch factors from (2, 1) to (1, 0) so the
top (calibration) pane absorbs all window-resize slack first — when the window is
made smaller the empty space inside the calibration table compresses before the
monitoring section is touched, so the lower thermal tables never need scrollbars
at typical band counts.  Thermal table minimum height raised from 80 to 120 px to
enforce enough room for header + 3–5 rows without a scrollbar. (2026-06-21)

---

### src/pimd_gui.py — v4.12 — Avg n field; no auto-connect; remove sub-200uV V/div; fix A<n> serial backlog

Root-cause fix for the A<n> serial write-buffer backlog that caused streaming to continue
20–30 s after quitting and parameter changes to be delayed up to 2 minutes at slow rates
(e.g. 6250 Hz / DS 256). At that rate the firmware takes ~245 ms per A256 — barely inside
the 250 ms poll timer — so any latency let queued A<n> commands pile up. closeEvent and the
start_stop stop path now call serial.clear(Direction.Output) before sending E, and
waitForBytesWritten is extended from 200 ms to 500 ms.

Root cause also addressed: A<n> sample count is now a user-editable "Avg n" field
(default 64) between the Boxcar and Raw Avg toggles. Field turns orange whenever the current
n > freq/30, meaning A<n> would exceed 80 % of the 250 ms poll timer (re-evaluated on every
frequency change as well as on direct n edits).

App no longer auto-connects at startup — user presses ENT / Connect explicitly, consistent
with pimd_classviz and pimd_delaycal. The 10 uV, 20 uV, 50 uV and 100 uV V/div options are
removed from the left sidebar (minimum is now 200 uV/div); v_div arrow-key clamp updated
from −15 to −11 accordingly. (2026-06-20)

---

### src/pimd_delaycal.py — v1.12 — QSplitter; uniform table colours; window/splitter geometry persistence

Four UI fixes. (1) Calibration table and "Live Monitoring & Auto Nudge" section now share a QVSplitter (2:1 default ratio), so the bottom section maintains its size when the window shrinks — the user drags the handle to adjust the split; splitter state is persisted in settings. (2) _auto_color_cell extended to update all three tables (cal + mean + std) identically; _update_thermal_tables likewise mirrors calibration table cell background to both thermal tables during Auto, replacing the previous independent value-based std-dev colouring; _auto_finish uses _auto_color_cell so the final colours are also applied consistently to all three tables. (3) Window width, height, x, y saved on close and restored on startup via settings JSON; QTimer.singleShot(0,...) defers splitter size restoration until after first layout pass. (4) Section labels "Latest mean (mV):" and "Std dev (mV):" set to bold weight for visual parity. Minimum table height increased 60→80 px. Noted in v1.12 header: "nudging every cell" is expected behaviour — calibrated delays sit at threshold crossings with nonzero signal slope, converting amplitude noise to σ > 0.5 mV; Auto Nudge relocates to quieter nearby delays, which is its design purpose. (2026-06-20)

---

### src/pimd_delaycal.py — v1.11 — post-nudge settling gate eliminates false yellow flicker

After each nudge the rolling std-dev buffer mixes transition frames (delay still changing) with settled frames, causing most cells to briefly go yellow before settling — a false noise signal. Fix: _auto_run_soak now sets _auto_settling=True and arms QTimer.singleShot(1000, _auto_settle_done) immediately after sending G. While the flag is set, _on_thermal_w_record discards all incoming W records and skips display updates. _auto_settle_done clears the flag and calls _thermal_buf.clear() to ensure std-dev accumulation begins from clean post-settle frames only. _stop_auto also resets _auto_settling. The 1 s gate is fixed; minimum soak is 5 s so effective measurement window is always ≥ 4 s. (2026-06-20)

---

### src/pimd_delaycal.py — v1.10 — wider log; thermal box resizable; live table colours; settings persistence

Four enhancements. (1) Left column widened 320→420 px and window grown 1200×1000→1440×1200 so activity log entries (which include long ch-label strings and µs/ns values) fit on one line without wrapping. (2) GroupBox renamed "Live Monitoring & Auto Nudge"; setMaximumHeight(140) removed from both thermal tables and replaced with setMinimumHeight(60) and stretch=1 inside the layout — the box now occupies half the right-column height and resizes with the window. (3) During Auto Nudge (tracked by new _auto_running flag set True in _start_auto, False in _auto_finish/_stop_auto), _update_thermal_tables mirrors the calibration table's status colour onto the mean table (queued/amber/green/red) and colours each std-dev cell green if ≤ threshold, yellow if ≤ 2× threshold, red otherwise. (4) All parameter fields (port, delays, freq/pulse, targets, thermal secs, std-dev N, auto soak/iter/threshold/nudge/cap) saved to data/delaycal_settings.json via _save_settings() in closeEvent and restored via _load_settings() called at the end of __init__ after _build_ui(). (2026-06-20)

---

### src/pimd_delaycal.py — v1.09 — real-time Auto cell colours; Import Profile; adjusted-delays summary

Three enhancements to pimd_delaycal. (1) Real-time cell colouring during Auto Nudge: after the initial soak, cells in the calibration table are immediately coloured yellow (queued for nudging) or green (already within threshold); the cell being actively soaked turns amber; it turns green on pass or red on flag — giving a live progress view without waiting for the final summary pass. (2) "Import Profile" button in the top bar loads any JSON profile (same format as Export Profile) directly into the calibration table, setting _fp_pairs / _targets_v / _thresholds and enabling Thermal / Auto / Export without requiring a full calibration sweep first. (3) At the end of Auto Nudge, _auto_finish now appends a compact "Adjusted delays" block to the activity log listing only the channels whose delay actually changed (cal → best µs, Δ ns, PASS/FLAGGED), and updates progress_label with the one-line summary plus the count of adjusted cells. (2026-06-20)

---

### src/pimd_delaycal.py — v1.08 — activity log panel; sequential Auto Nudge

Scrolling activity log panel (QPlainTextEdit, read-only) added to the left column
below the Configuration group box, reporting calibration steps (each delay tested,
each threshold crossing), thermal start/stop, and auto-nudge decisions per channel.
Auto Nudge logic changed from parallel to sequential per-channel processing: an
initial soak identifies bad channels, then each bad channel is tackled one at a
time — up to "Max attempts/cell" nudges — before advancing to the next. The
_auto_iter global iteration counter is replaced by _auto_phase / _auto_targets /
_auto_target_idx / _auto_ch_attempts. "Max iter" spinbox label changed to "Max
attempts/cell". Window height bumped 950→1000 px. (2026-06-20)

---

### src/pimd_delaycal.py — v1.07 — Auto Nudge: iterative per-cell delay correction

New "Auto" button in the Thermal Monitoring panel.  After calibration, Auto runs
soak→evaluate iterations using the existing Mode 2 / D+Q5+G / W-record path:
streams the calibrated profile, measures per-cell std dev over the last N W-frames
(reuses the existing Std dev N spinbox), then nudges cells whose std dev exceeds
the threshold (default 0.5 mV) by a configurable step (default 80 ns) toward
earlier delays.  On cap hit (default ±960 ns from calibrated delay), resets to
the calibrated delay and explores the opposite direction; flags the cell if both
directions are capped.  Best-std delay kept per cell across all soaks.  At finish,
calibration table updated (green = passed, red = still bad after max_iter); ΔV per
nudged cell logged in status; Export Profile runs automatically.  N/R cells
excluded.  All I/O via QTimer.singleShot + W-record callbacks — no blocking loops.
Window height bumped 850→950 px. (2026-06-20)

---

### OBS — P2006-113356.csv — 80 ns delay sweep, 20 kHz / 20 µs pulse, v4.23 firmware

First data set recorded with MCU v4.23 (freq Hz / pulse+delay ns protocol). Warm-up 30 s,
then 13 delay steps from 7088 ns to 8048 ns in 80 ns increments, ~5 s per step.
All 13 delays land exactly on the 8 ns PWM grid (total_ns = delay_ns + 904 divisible by 8).

| delay (ns) | delay (µs) | V mean (mV) | V σ (µV) | fw_sd (µV) | status |
|---:|---:|---:|---:|---:|:---|
|  7088 | 7.088 | 4877.3 | 1835 |  242 | settled — slow filter tail |
|  7168 | 7.168 | 4809.2 |   71 |   65 | **clean** |
|  7248 | 7.248 | 4736.3 |  378 |  125 | settled — moderate |
|  7328 | 7.328 |    —   |   —  | 500–1400 | **never settled** |
|  7408 | 7.408 |    —   |   —  | 500–1400 | **never settled** |
|  7488 | 7.488 | 4477.5 |  227 |  158 | settled — ok |
|  7568 | 7.568 | 4379.3 |  177 |  161 | settled — ok |
|  7648 | 7.648 | 4273.8 |  179 |  111 | settled — ok |
|  7728 | 7.728 | 4161.5 |  176 |  139 | settled — ok |
|  7808 | 7.808 |    —   |   —  | 500–1400 | **never settled** |
|  7888 | 7.888 |    —   |   —  | 500–1400 | **never settled** |
|  7968 | 7.968 | 3795.4 |  180 |  105 | settled — ok |
|  8048 | 8.048 | 3666.1 |  319 |  143 | settled — moderate |

Key findings: (1) Grid fix confirmed — no two-stage settling artefact seen in previous
dataset (P2006-103607.csv, v4.21 off-grid). (2) Four delays never settle: 7328+7408 and
7808+7888, forming two 160 ns wide noisy zones exactly 480 ns apart. This points to a
~2.08 MHz LC ringing in the coil/preamp after TX cutoff: the ring-down still has enough
amplitude at 7–8 µs to cause persistent fw_sd > 400 µV when the sample point lands near
a ringing peak. (3) 7088 ns shows high V σ (1835 µV) but low fw_sd (242 µV) — slow
voltage drift of ~5.6 mV over 24 s, consistent with the 256-sample rolling window still
flushing the previous step (3.28 s flush time); not physical noise. (4) Best operating
window at this freq/pulse: 7488–7728 ns (320 ns clean band). (2026-06-20)

---

### src/pimd_delaycal.py — v1.06 · src/pimd_classviz.py — v1.10 · src/pimd_scope.py — v4.02 — protocol update and title standardisation

* command in delaycal and classviz (single-cell Mode 1) updated to match MCU v4.23:
freq now sent as integer Hz (was kHz to 1 d.p.), pulse and delay now sent as integer ns
(was µs to 1 d.p.). All four PC apps now share the same title format:
'PIMD <AppName> v<N> by Mark Makies'. Scope has no protocol changes — title only. (2026-06-20)

---

### mcu/pimd_mcu.py — v4.23 · src/pimd_gui.py — v4.11 — serial protocol: freq in Hz, pulse/delay in ns

Protocol change to eliminate decimal-place rounding ambiguity in the serial wire format.
All timing fields previously reported in kHz (1 d.p.) or µs (1 d.p.) now use exact integers:
freq in Hz, pulse and delay in ns. No decimal points, no conversion arithmetic on the PC side.
At the 8 ns PWM grid, all values are exact multiples of 8, so integer ns is both lossless and
unambiguous. Affects * record output, R record output, V response, L response, and the inbound
* config command. GUI title standardised to 'PIMD GUI v4.11 by Mark Makies'. (2026-06-20)

---

### src/pimd_gui.py — v4.10 — fix display lag and file-write spam after stop

Two serial-handling bugs fixed:

**(a) Growing display lag** — `read_from_serial` now collects all available
lines before dispatching rather than calling `process_packet` inside the drain
loop.  Only the last `*` packet per `readyRead` call gets the full chart/UI
update (`skip_display=False`); earlier packets in the burst still write to file
then return early (`skip_display=True`).  At 39 SPS the event loop previously
had to complete a full chart redraw per packet; if any redraw took >25 ms the
backlog grew, producing 10–30 s display lag after extended running.  Now display
cost is O(1) per `readyRead` regardless of burst size.

**(b) "File write error, probably last packet after stop" spam** — `start_stop`
stop branch, `closeEvent`, and `setup_file_logging` all now set `self.file =
None` immediately after `self.file.close()`.  A closed file object is truthy so
`if self.file:` previously passed and triggered `ValueError: I/O operation on
closed file` for every lingering buffered packet after stop. (2026-06-20)

---

### src/pimd_classviz.py — v1.09 — 3 d.p. for pulse width, frequency and delay in stats table

_band_labels format changed from `{:.0f}µs/{:.1f}kHz` to `{:.3f}µs/{:.3f}kHz` so pulse
width and frequency are displayed to 3 decimal places throughout (heatmap axis labels,
stats table Band column, single-cell combo, status bar).  Stats table Delay (µs) column
changed from 2 d.p. to 3 d.p.  All three now consistent with the 8 ns PWM grid
(0.008 µs precision). (2026-06-20)

---

### src/pimd_delaycal.py — v1.05 — snap calibrated delays to 8 ns PWM clock grid

Interpolated threshold-crossing delays are now snapped to the nearest 8 ns boundary
(the RP2040 PWM clock period) before being stored in the results table and exported
to profiles.  Formula: round the delay to the nearest 8 ns integer count.  Off-grid
values cause ±1 LSB alternating PWM jitter, documented in pimd_gui.py v4.08 and
pimd_mcu.py v4.22 — the same fix applied there for the GUI sliders is now applied
to the calibration output.  Table cells now display to 3 decimal places (0.008 µs
resolution) instead of 2.  The belt-and-suspenders snap in _build_profile() also
covers the N/R fallback (max_delay). (2026-06-19)

---

### src/pimd_classviz.py — v1.08 · src/pimd_delaycal.py — v1.04 — std dev window: samples not seconds; 2 d.p.

Stats-tab std dev window in classviz changed from time-based (QDoubleSpinBox 0.5–60 s,
filtering `_rolling_buf` by timestamp cutoff) to sample-count-based (QSpinBox 2–2000,
default 50, slicing the last N entries) to match the equivalent control in pimd_delaycal.py
— both now show "Std dev N:" so values are directly comparable. Std dev column in classviz
and the thermal std table in delaycal both now display to 2 decimal places (was 1 d.p.
in classviz, integer in delaycal). (2026-06-19)

---

### src/pimd_delaycal.py — v1.03 — profile export + thermal monitoring mode

Three additions to close the calibration-to-measurement loop:

**(a) Export Profile button** — builds a classviz-compatible JSON profile from the
calibrated delay table: one band per freq/pulse pair, `delays_us` from the crossing
cells (N/R cells fall back to max_delay), `threshold_v` from the target voltages list.
Autosaves to `data/profiles/cal_YYYYMMDD_HHMMSS.json` with no file dialog.
Format is identical to `pimd_classviz.py`'s `_default_profile()` so the file loads
directly in the classviz Profile Builder tab.

**(b) THERMAL button** — streams Mode 2 using the calibrated profile (sends `D` +
`Q5` + `G`, same as classviz's dynamic-profile mechanism), counts down from a
configurable duration (default 240 s), then stops automatically. Lets the user warm
up the electronics on the exact profile that will be used for the final measurement run.
Stop button aborts early.

**(c) Two live monitoring tables** — displayed below the calibration results while
THERMAL is running: Latest mean (mV, no decimal) and Std dev over the last N samples
(N settable, default 50). W-record parsing added to `read_from_serial`; updates
rate-limited to 10 Hz to avoid UI lag.

Also: config panel widened 280→320 px; window resized 1050×620→1200×850.
(2026-06-19)

---

### src/pimd_gui.py — v4.08 — 8 ns grid snapping; boxcar defaults ON; responsiveness fixes

Six changes in one version bump:

**(a) QLineEdit precision display** (pimd111_ui.py also updated): `lFreq`, `lPulse`,
`lSample` replaced as editable QLineEdit fields. Frequency shown as integer Hz;
pulse/delay shown in µs to 3 dp. Orange highlight when not on the 8 ns PWM clock
grid (or, for frequency, not a clean 125 MHz divisor). `change_parameters()` reads
from QLineEdit text; sliders remain for coarse adjustment.

**(b) Frequency slider re-ranged to 18 clean 125 MHz divisors, 1–50 kHz** (index
0–17 in `CLEAN_FREQS_KHZ`): 1.0, 1.25, 1.6, 2.0, 2.5, 3.125, 4.0, 5.0, 6.25,
8.0, 10.0, 12.5, 15.625, 20.0, 25.0, 31.25, 40.0, 50.0 kHz. The +/- buttons
and keyboard shortcuts (E/W, R/Q) step through this list by index; every position
is an exact clean frequency. `apply_soc_defaults()` sets index 10 (10.0 kHz).

**(c) Pulse/delay sliders re-ranged in 8 ns counts** (1 unit = 8 ns = 0.008 µs):
`slPulse` 625–5000 (5–40 µs), `slSample` 625–3750 (5–30 µs). Every slider
position is inherently on-grid; +/- buttons step by one 8 ns count. SOC defaults:
slPulse 2500 (20 µs), slSample 1250 (10 µs). `_on_pulse_edited` / `_on_delay_edited`
sync with `round(us * 125)`. Motivation: `pimd_mcu.py v4.22` shows that off-grid
values (old 0.1 µs steps = 12.5 × 8 ns) caused ±1 LSB alternating anomalies.

**(d) Boxcar and Raw Avg default ON** — both toggle buttons `setChecked(True)` at
startup; the poll timer only starts once Running, so no side-effect at init.

**(e) `read_from_serial` drains buffer in a `while canReadLine` loop** — the
previous single-line read caused a serial-buffer backlog and readyRead event storm
at ~39 SPS that progressively froze the UI and made Ctrl+C / window-close
unresponsive. Fixed to match the pattern already used in `pimd_scope.py`.

**(f) `closeEvent` added; fragile `aboutToQuit` lambda removed** — on window
close or F12 quit, stops the poll timer, sends `E`, flushes serial with
`waitForBytesWritten(200)`, closes port and log file. Also fixes a file-handle
leak in `setup_file_logging()` (previous handle now closed before opening new one)

---

### src/pimd_gui.py — v4.09 — fix quit_app: self.close() instead of QApplication.exit()

`quit_app()` (F12 shortcut) called `QApplication.instance().exit()`, which exits
the event loop without sending a `QCloseEvent` to the window. `closeEvent()` —
added in v4.08 to replace the removed `aboutToQuit` lambda — was therefore never
triggered by F12. Result: F12 exited without stopping `raw_poll_timer`, sending `E`
to firmware, flushing serial, or closing the log file.

Changed to `self.close()`, which sends a `QCloseEvent` → `closeEvent()` runs
cleanup → `super().closeEvent(event)` accepts → window destroyed → app exits via
`quitOnLastWindowClosed=True`. The OS × button path was already correct and is
unchanged.

---

### mcu/pimd_mcu.py — v4.22 — SAMPLE_PULSE_CORRECTION 0.908 → 0.904 µs

Updated `SAMPLE_PULSE_CORRECTION` from 0.908 µs to 0.904 µs. At the 10 µs
GUI delay setting, total delay is now 10.904 µs = 1363 × 8 ns exactly —
landing on a clean PWM clock-count boundary. The previous value placed the
delay exactly halfway between two adjacent 8 ns counts (1363.5 × 8 ns),
causing `delay_CC` to alternate ±1 LSB on every 0.1 µs GUI step and producing
an every-other-step ~13 mV / ~0 mV alternating anomaly in pulse-width sweep
recordings.


### mcu/pimd_mcu.py — v4.21 — IRQ critical section in read_raw_sample; plausibility gate

Wrapped the BUSY poll + SPI read in `machine.disable_irq()` /
`machine.enable_irq()` to prevent USB CDC IRQs firing between the BUSY-low
edge and the SPI clock start. Eliminates two Mode 2 anomaly types confirmed
in a quiet 45-channel recording (8 events, all exactly 32 frames = M=32
rolling-buffer depth):

- **Type 1 — SDOB bit-truncation** (value ≈ 50 % of true): USB IRQ delays
  SPI start past the next MCLK; partial conversion shifts into the read,
  producing half/quarter values. IRQ blackout ≤ 36 µs; safe for USB SOF.
- **Type 2 — Cell-value bleed** (value > normal): USB IRQ starves the
  BUSY-high poll long enough to miss the current cell's MCLK; lands on the
  previous cell's SDOB output.

Also adds a per-cell 10 % plausibility gate: if `raw14` deviates > 10 % from
the rolling mean (after ≥ 8 samples), the mean is substituted. All 8 observed
events caught. `FW_VERSION` constant synced to file header (was stuck at 4.15).

---

### mcu/pimd_mcu.py — v4.20 — FIX acquire_mode2: boundary settling and first/last cell timing

Two bugs fixed:

1. `BOUNDARY_PRIME` 5 → 15 (470 µs → 1410 µs): shorter period was
   insufficient for the 5 µs → 40 µs wrap-around thermal transient (8×
   pulse-energy step), producing a 3.1 → 1.6 → 0.6 mV gradient in band-0
   cells 0–2.

2. `emit/poll` moved from after the for-loop to inside it at `i == 0`:
   previously `print()` ran between cell[n-1]'s write and its read; USB CDC
   IRQs (10–50 µs) exceed the 2.5 µs BUSY-LOW window at 57 kHz, causing §7
   bit-truncated outliers in cell[n-1]. Cell[n-1] now reads cleanly; USB noise
   overlaps the already-running cell[0] settling sleep.

---

### src/pimd_classviz.py — v1.07 — 64-frame circular median glitch filter on display path

`process_packet`: added a 64-frame circular buffer per channel. When a
channel's latest value deviates > 100 mV from its 64-frame median, the median
is substituted for `_latest_raw` (→ heatmap, stats tab). `_rolling_buf` and
`_record_buf` retain unfiltered raw values. The 64-frame window ensures ≥ 33
clean frames remain throughout any 32-frame glitch event, keeping the median
stable. Targets the 32-frame flat-step ADC artifacts (fw v4.21 is the primary
fix; this is the independent PC-side complementary layer).

---

### src/pimd_classviz.py — v1.06 — Record Frames toggle button

Stats tab: added "Record Frames" toggle button. When active, raw W-record
frames (`fw_time_ms`, `wall_time_s`, `ch0`…`chN-1` in µV) are appended to
`data/frames_YYYYMMDD_HHMMSS.csv`. Recording auto-stops when streaming stops
or the active profile changes.

---

### src/pimd_classviz.py — v1.05 — fix _fmt(): CSV thousands-separator bug

Removed the thousands-separator from `_fmt()`'s format string. Saved CSV
files previously contained values like `4,373.6` instead of `4373.6`,
breaking machine parsing.

---

## Archive — consolidated 2026-06-18

---

### src/pimd_gui.py — v4.04 — min/max range from R record

`acquire_raw_average()` now returns `(mean_uV, std_uV, min_uV, max_uV)` (see
mcu v4.15 below). The GUI parses the two new fields from the R record
defensively (falls back to `None` if the firmware is older). When available,
the footer raw-path status string now shows `min…max uV` alongside mean and
std dev, making it immediately visible whether a single outlier sample (e.g.
a bimodal distribution within one boxcar window) explains the large reported
std dev and oscillating mean. No chart changes.

---

### mcu/pimd_mcu.py — v4.19 — revert v4.18; re-apply BUSY edge sync; fix missing data_bytes

Reverted v4.18's `sleep_us` pacing + post-read-retry approach — it reintroduced
the outlier corruption that v4.17 had solved. Re-applied v4.17's full BUSY edge
sync (`while not busy_pin.value(): pass` → `while busy_pin.value(): pass` → read).
Also fixed a `NameError` introduced during the revert edit: the `data_bytes =
adc_raw_spi.read(4)` line had been accidentally dropped from `read_raw_sample()`.

Accepted known side-effect (carried from v4.17): BUSY-high pulse at 10 kHz is
≈ 15 µs — MicroPython polling catches ≈ 1-in-6, giving ≈ 1.6 kHz effective raw
sample rate (vs 10 kHz configured). Accepted tradeoff for accuracy over rate.

---

### src/pimd_gui.py — v4.07 — remove range from footer; fix horizontal grid line color

- Footer raw status: removed `range: <min> to <max> uV` field (and associated
  `raw_min_uV`/`raw_max_uV` instance vars and R-record parsing). Footer now
  shows only `Raw avg: ... uV, sd: ... uV (N=...)`.
- Chart: `axis_z` (right/horizontal-grid axis) `setGridLineColor` changed from
  `QColor("blue")` back to `QColor("#cccccc")` (light gray), matching the
  vertical grid lines from `axis_x`.

---

### src/pimd_gui.py — v4.06 — range-based chart trim, boxcar mode button, remove Raw σ

Three changes bundled:

1. **Chart polyline corruption fix** — `series_v` and `series_raw_mean` are now
   trimmed by x-axis range (`axis_x.min()`) instead of a point-count threshold.
   The old `removePoints(0, 100)` when count > 5000 left warmup-spike points just
   outside the visible window; QLineSeries drew a connecting segment from the last
   removed point's neighbour to the newest point, producing a large vertical
   artifact early in each run. The range-based trim removes all points whose
   x-coordinate is less than the current left edge of the axis, so no off-screen
   point can ever produce a phantom segment.

2. **Boxcar mode toggle** — new `pb_boxcar_mode` button ("Boxcar: OFF/ON") in the
   bottom-left area (formLayout_10). When OFF (default), the A<n> poll timer does
   not start when Mode 1 starts — raw boxcar data is not collected and the orange
   trace is not shown. When ON, poll timer starts (or resumes) on Mode 1 start.
   The F1/F2/F3/F4 preset labels (label_9, label_11, label_8, label_12, label_14,
   label_15, label_18, label_19) are removed programmatically; `pb_show_raw_mean`
   ("Raw Avg") is moved into formLayout_10 alongside the new boxcar button.
   F1–F4 QShortcut bindings and `f1()`–`f4()` handler methods are removed.

3. **Remove Raw σ** — `pb_show_raw_stddev`, `show_raw_stddev`, `_raw_stddev_max_seen`,
   `series_stddev`, `series_stddev_slope`, `axis_stddev`, `_on_toggle_raw_stddev()`,
   and `STDDEV_MAX_SCALE` are all removed. The raw std dev value (`raw_stddev_uV`)
   parsed from the R record is still shown in the footer status string.

---

### src/pimd_gui.py — v4.05 — clear raw series on Mode 1 start

`series_raw_mean` and `series_stddev` are now cleared every time Mode 1 starts
(Start button → S command), not only on DEL/Clear or toggle-off. Previously,
stale data from the previous session remained in the series; when the new
session started, the QLineSeries polyline connected the last old point (at an
old x-timestamp, off the visible window) to the first new point, drawing
diagonal phantom traces that appeared as multiple overlapping orange plots on
the chart.

---

### mcu/pimd_mcu.py — v4.18 — restore sleep_us pacing, add post-read retry

v4.17's full BUSY edge sync (`while not busy_pin.value()` → `while busy_pin.value()`)
was correct in principle but the BUSY-high pulse at 10 kHz is only ~15 µs —
too short for MicroPython's polling loop to catch reliably. Only ~1 in 6 pulses
were detected, dropping effective sample rate from ~10 kHz to ~1.6 kHz (Sa/s
fell from 9.8 to 6.4; footer showed "Rx 1.6 kHz" instead of "10.0 kHz").

**Fix:** restore `sleep_us(period_us)` pacing in `acquire_raw_average()` and
change `read_raw_sample()` to:
1. Wait for BUSY low before reading (handles landing mid-conversion)
2. Read SDOB
3. Post-read check: if BUSY went high during the 3.2 µs SPI transfer (MCLK
   fired mid-read), wait for BUSY low and read again once. This catches the
   "just-before-MCLK" case that caused the 1/4 and 1/2 discrete outliers.

Double-retry probability is negligible (retry happens right after BUSY falls,
well before the next MCLK). `busy_high_count` (B command) now counts mid-SPI
races rather than edge-sync calls.

---

### mcu/pimd_mcu.py — v4.17 — BUSY-edge sync in read_raw_sample()

v4.16 guarded against reading SDOB while BUSY was already high, but left a
second corruption window: when `read_raw_sample()` is called just before MCLK
fires, BUSY is low (previous conversion done), the guard passes, and the SPI
read starts — then MCLK fires mid-transfer and the LTC2508-32 invalidates the
SDOB register, producing a bit-truncated result.

**Evidence:** v4.15/v4.16 min/max showed outliers at ~375k µV and ~750k µV
alongside normal samples at ~1511k µV — ratios of exactly 1/4 and 1/2,
consistent with 1–2 bits of the SPI transfer being cut off mid-read and the
remaining bits being zero-filled. The partial v4.16 fix (direction constraint
lifted but discrete outliers persisted) confirmed the mid-read corruption
theory.

**Fix:** replace "wait only if BUSY already high" with full edge sync:
1. `while not busy_pin.value(): pass` — wait for MCLK to fire (BUSY rises)
2. `while busy_pin.value(): pass` — wait for conversion complete (BUSY falls)
3. Read SDOB — maximum margin from both edges, fully hardware-locked

`acquire_raw_average()`'s `sleep_us(period_us)` removed — each
`read_raw_sample()` call now naturally takes exactly one MCLK period via the
BUSY waits, so the software timer is no longer needed and can't drift.

---

### mcu/pimd_mcu.py — v4.16 — fix BUSY race in read_raw_sample()

`read_raw_sample()` was checking `busy_pin.value()` but reading SDOB immediately
regardless — the `if` only incremented a counter. The `sleep_us()`-paced loop in
`acquire_raw_average()` drifts relative to the free-running PWM hardware; when
drift places the software read mid-conversion, BUSY is high and SDOB returns
corrupt/low data.

**Evidence (v4.15 diagnostic):** under SoC conditions, min/max in the R record
showed the occasional sample dropping from the normal cluster of ~1,511,000 µV
to ~375,000 µV — a ~1,136,000 µV (75%) drop. A handful of such outliers per
256-sample window are enough to swing the boxcar mean by several mV and produce
the sawtooth oscillation visible in `pimd_gui.py`'s "Raw Avg" chart toggle. The
mean never *exceeded* the Mode 1 filtered value because all outliers go low, not
high (an incomplete conversion reads a partial/stale register, never an inflated
one).

**Fix:** add `while busy_pin.value(): pass` immediately after the existing counter
increment. The counter (`busy_high_count`, read via `B`) now measures how often
the wait was needed rather than how often a bad read occurred — useful for
confirming drift rate drops to near zero with the fix applied.

No change to `acquire_mode2()` — its SPI reads are done inline with their own
timing (not via `read_raw_sample()`).

---

### mcu/pimd_mcu.py — v4.15 — per-call min/max in R record

`acquire_raw_average(n_samples)` now computes and returns `min_uV` and
`max_uV` across the `n_samples` collected in one call (converted to µV via the
same `RAW_FULL_SCALE_UV / 2**14` scale as mean and std). The `R` record format
gains two trailing fields:

```
R<t>, <mean_uV>, <std_uV>, <n>, <freq_kHz>, <pulse_us>, <delay_us>, <min_uV>, <max_uV>
```

**Motivation**: the raw boxcar-average path (`A<n>`) shows a sawtooth oscillation
in reported mean (up to ±mV scale) and std dev up to 70,000 µV under SoC
conditions, while the filtered path stays at ~50 µV. If even a handful of the
`n` samples are wildly off (bimodal distribution), `max − min` will be
disproportionately large relative to the std dev, pinpointing the same
read-before-write race suspected from the v4.13 Mode-2 fix but now in the
static-config `sleep_us()`-paced loop. No functional change to acquisition
logic — diagnostic only.

---

### src/pimd_gui.py — v4.03 — visualise the raw boxcar-average path

Under SoC conditions, the top-right Std Dev box (filtered path) reads ~50 µV
as expected, but the footer's raw-path figure (`A<n>` boxcar average) was
seen up to 70,000 µV — far beyond what the oversampling-mismatch fix in v4.02
explains. This is now suspected to be the **same unresolved mechanism** as
the Mode 2 single-cell noise investigated earlier (mcu/pimd_mcu.py v4.08-
v4.14): both are a static/unchanging PWM config read repeatedly via
`read_raw_sample()` in a `sleep_us()`-paced loop, with no `BUSY` check. That
investigation was closed with "use Mode 1 instead" — but Mode 1's own `A<n>`
path showing the same magnitude of anomaly suggests the earlier conclusion
was premature and there's a real, shared bug still to find.

**Added two chart toggles** to make the anomaly visible for further
diagnosis, reusing existing-but-previously-unused chart infrastructure:
- **"Raw Avg"** — overlays `raw_value_uV` (orange) on the existing voltage
  axis next to the filtered-path blue trace, for visually comparing the two
  means.
- **"Raw σ"** — plots `raw_stddev_uV` (red) on the existing `series_stddev`/
  `axis_stddev`, previously wired up but never actually fed data. The axis
  range now auto-expands (`_raw_stddev_max_seen`) as larger values are seen,
  since the old fixed 0-1000 µV range can't show a 70,000 µV spike — was a
  silent display ceiling, not just a stddev problem.

Both default off; `DEL`/Clear resets them along with the rest of the chart.
No firmware change yet — this is the visualisation step before attempting a
fix, per the plan to look at the pattern before guessing at the mechanism
again.

---

### Standard Operating Conditions (SoC) — established 2026-06-18

**TODO: roll this section into DESIGN.md §3 ("Measured operating envelope")
once confirmed stable — DESIGN.md is read-only for agents, left here per
existing policy.**

For repeatable bench testing/comparison, the reference test condition is:

- **Mode 1**, 10.0 kHz / 20.0 µs pulse / 10.0 µs sample delay / 256 decimation
- Coil in air, no targets
- 20 V bench supply
- **From cold, allow 4 minutes to settle** — expect roughly a 50 µV/s drop
  during this warm-up. Don't take noise-floor readings as representative
  before this point.
- `src/pimd_gui.py` now defaults to these values at startup (v4.02, below).

**Reference capture:** `AI refs/SteadyState.jpg` — first half of the plot at
256 decimation, second half (after a DS Factor toggle) at 1024. Shows the
settled noise floor and the slow thermal drift; this is the trace future
comparisons should be checked against. (File currently lives in the scratch
`AI refs/` folder — move into `pics/` if it's to become a permanent DESIGN.md
asset.)

---

### mcu/pimd_mcu.py — v4.14 — same-freq boundary leakage + averages=256 crash

User testing of a 2-band, same-frequency-different-pulse-width dynamic
profile (`D128;5000,50.0,<9 delays>;5000,10.0,<9 delays>`) found two issues:

**1) Cross-band leakage at same-frequency boundaries.** First cell of each
band showed std dev 55-65 mV vs 2-12 mV for the rest of that band (user's
`stats_20260617_212108.csv`) — the same signature as the original v4.06
cross-band leakage. Cause: `needs_settling` (the flag that triggers
`BOUNDARY_PRIME` extra coil-settling periods) was gated on `at_boundary`,
which only checks for a *frequency* change. This profile's two bands share
5000 Hz but differ in pulse width (50 µs vs 10 µs) — a real drive-energy
change that `at_boundary` didn't see, so settling never applied. Fix:
`needs_settling = at_boundary or dd != cells[prev][2]` — also fires when
drive duty (`dd`, which `pulse_us` feeds into) changes, independent of
frequency. `pwm.freq()` itself is still only called when frequency actually
changes (unrelated concern, unchanged). Verified: re-running the same profile
post-fix, the first-cell std devs dropped to 1.7-5.7 mV, in line with the
rest of each band.

**2) Board crash at averages=256** (averages=128 was fine — a scaling issue).
`acquire_mode2`'s rolling buffers were plain Python lists using
`append()`+`pop(0)`, an O(avg_depth) shift on every sample, for every cell,
every period — scaling badly and almost certainly the cause (heap churn /
CPU starvation) of an unhandled exception that previously crashed the board
outright (the main loop only caught `KeyboardInterrupt`, nothing else). Fix:
replaced with pre-allocated fixed-size circular buffers (`rolling_idx`) and
an incrementally-maintained `rolling_sum`/`rolling_count` per cell — O(1) per
sample regardless of `averages`, no list resizing. Also wrapped the Mode 2
call in the main loop in `try/except Exception` so any future unhandled
error reports over serial (`Mode 2 ERROR: ...`) and returns to a safe state
instead of crashing silently. Verified: the exact profile that crashed before
now runs cleanly for 5+ seconds at averages=256 with the board remaining
responsive afterward (`V` command still answers normally).

---

### mcu/pimd_mcu.py — v4.13 — Mode 2 cell-misattribution bug found and fixed

**The real bug, found after v4.08–v4.12 investigated and ruled out PWM-rewrite
jitter, command-poll overrun, BUSY-violation rate, and overrun rate (none
correlated with the anomaly — see that section below for the full trail).**

LTC2508-32 datasheet review (`LTC2508-32.pdf`, "MCLK Timing" p.20) plus a raw
(`averages=1`) capture revealed the real signature: a 2-cell dynamic profile's
two channels weren't *noisy* — at 57 kHz they reported **exactly swapped**
values (deterministic, not random), and at 25 kHz they **randomly flipped**
between the two cells' true values. Reversing the delay order in the `D`
command reversed which channel reported which value, proving array-order-
following mis-indexing rather than measurement noise. Averaging blended the
two true values into a clean-looking but wrong mean with deceptively low std
dev — worse than visible noise, because it hides the error.

**Root cause:** `acquire_mode2()`'s non-boundary cells wrote the new CC (duty)
value *before* reading SDOB (a deliberate v4.01 design choice). Writing a new
compare value while the PWM counter has already passed it can fire an
immediate spurious trigger — the same family of issue as the already-fixed
v4.04 freq/WRAP bug, but for `duty_u16`'s compare register instead of `freq`'s
WRAP register. The read immediately after a write-first then captures *this*
cell's own just-triggered conversion instead of the *previous* cell's
already-completed one — a clean off-by-one that only shows up when consecutive
cells' duty values actually differ (explaining why the single-cell case was
immune — nothing to swap with — and why this was missed for so long).

**Fix:** read SDOB before writing new CC values for *all* cells, not just
boundary cells (which already did this for a different reason — the v4.04
WRAP race). Verified margin: read (~6-7 µs) + write (~2 µs) ≈ 9 µs must precede
the new cell's own trigger; the smallest delay in any compiled profile is
band4's ≈11.8 µs (drive_duty + 6.03 µs + 0.752 µs correction), so all existing
profiles are safe.

**Verification:**
- 57 kHz, delays 6.03/9.71 µs, both array orders: now correctly tracks
  delay→value regardless of position (was backwards/order-following before).
- 25 kHz, delays 7.6/10.0 µs: stable per-cell values (~3518 mV / ~820 mV), no
  more bimodal swapping (was randomly flipping between the two before).
- Full CLASSIFY_EP sweep (Q4): values now track nominal thresholds tightly
  across nearly every cell (e.g. 5 µs/57.0 kHz band: 4480/3994/3515/2987/2510
  mV vs nominal 4500/4000/3500/3000/2500), std devs mostly single-digit to
  ~20 mV (down from up to 58 mV pre-fix). Band 0 (10.6 kHz) still shows some
  elevated std dev (22–138 mV) — not yet investigated, lower priority since
  absolute values are sane.
- The original single-cell (n=1) noise (~24–30 mV) is **unchanged** by this
  fix, as expected — a never-changing duty value can't trigger this race.
  That remains a separate, lower-priority gap: Mode 1 already covers genuine
  single-point measurement well (<100 µV), so Mode 2's dynamic single-cell
  profiles aren't the right tool for that use case.

`busy_high_count` (v4.11) and `overrun_count` (v4.12) diagnostics are kept
(harmless) but did not correlate with this bug — candidates for removal in a
future cleanup pass.

---

### mcu/pimd_mcu.py — v4.08–v4.10 — Mode 2 single-cell noise investigation

**Trigger:** a 1-band/1-cell dynamic profile (`averages=16`, 25 kHz/10 µs/7.6 µs
— built via the new Profile Builder tab) showed std dev up to 30 mV, vs Mode 1's
<100 µV at the *identical* parameters (waveforms verified identical on scope).
Scope-measured pulse-to-sample delay jitter: 60 ns in this Mode 2 case vs <10 ns
in Mode 1 (DESIGN §8 documents ~15–20 ns for the static-PWM baseline).

**First diagnostic (no code):** the existing `A32` raw boxcar-average command
(same raw SPI0 ADC path as Mode 2, but with a static, never-rewritten PWM
config) measured ~100 µV–1 mV at the same parameters — ruled out "raw vs
filtered ADC path" as the dominant cause (DESIGN §7 already expected ~350 µV
for M=16 raw averaging).

**v4.08 (hypothesis 1, falsified):** theorised that rewriting `duty_u16()` with
unchanged values every period was adding PWM edge jitter. Added `last_dd`/
`last_sd` tracking to skip the rewrite when unchanged. Re-tested: std dev
unchanged (~24 mV). Disproved by direct A/B.

**v4.09 (hypothesis 2, falsified):** theorised that `check_for_commands()`
running on every single 40 µs period (unique to n=1, normally amortized over
many cells) could occasionally exceed the period's time budget and cause
`read_raw_sample()` (no BUSY check) to catch a stale value. Throttled the poll
to once per `COMMAND_POLL_MS` (1 ms). Re-tested: std dev unchanged (~24 mV).
Also disproved.

**Isolated by elimination — the actual finding:** compared n=1 (~24–30 mV)
against an n=2 profile with two *different* delays (different `sample_duty`
each period → ~310 µV, matching the A32/DESIGN expectation) against an n=2
profile with two *identical* delays (same `dd`/`sd` every period, just like
n=1 → back to ~25 mV). The deciding factor is not n=1 vs n>1, write-frequency,
or poll-throttling — it is specifically whether the **PWM compare value
actually changes between periods**. Holding it constant (whether by skipping
the write or rewriting the identical value) gives high noise; alternating
between genuinely different values gives the expected low noise. The exact
RP2040 PWM hardware mechanism for *why* isn't confirmed (would need datasheet/
register-level investigation beyond what code reading and serial A/B testing
can establish) — this is documented as the empirical, reproducible finding.

**Practical conclusion:** Mode 2 (interleaved sweep) is not suited to genuine
single-point / repeated-identical-cell measurement — that's exactly what Mode 1
already does well (<100 µV, confirmed). Multi-cell sweeps (Mode 2's actual
purpose, including CLASSIFY_EP) are unaffected since cells legitimately differ
period to period — confirmed by both the n=2-different-delays test above and
the original 45-cell CLASSIFY_EP testing (v4.06).

v4.08/v4.09's code changes are kept (harmless, mildly beneficial) but their
in-file comments have been corrected in v4.10 to not claim a fix they didn't
provide; no functional code changed in v4.10.

---

### src/pimd_classviz.py — v1.04

**Profile dimensions are now runtime state, not module constants.** `N_BANDS`,
`N_CELLS`, `N_CHANNELS`, `BANDS_META`, `BAND_LABELS`, `CELL_LABELS`,
`THRESHOLDS_V`, `NOMINAL_BASELINE_UV`, `PROFILE_IDX` all moved into instance
attributes set by `_set_profile_dims()`/`_apply_profile()`. The heatmap axes, 3D
surface, stats table, and single-cell band/cell combos all rebuild from these
(`_rebuild_heatmap_axes`, `_rebuild_3d_surface`, `_rebuild_stats_table`,
`_rebuild_single_cell_combos`). Default on-connect behaviour is unchanged — it
still sends `Q4` and shows the same 5×9 CLASSIFY_EP view.

**New "Profile Builder" tab.** Lets you edit a profile's bands (freq Hz / pulse
µs / delays µs / optional threshold V, one row per band — all bands must share
the same delay count), save/load named profiles as JSON in `src/data/profiles/`,
preview the exact `D...` command that will be sent, and **Send & Run** it: `E`,
`D<averages>;<bands...>`, `Q{DYNAMIC_PROFILE_INDEX}` (=5, must match firmware's
`NUM_PROFILES`), `G`, then resizes the whole UI to match via `_apply_profile()`.
Seeded with `src/data/profiles/CLASSIFY_EP_baseline.json` — the current
profile-4 band/delay data, the same one used to diagnose the v4.06 leakage fix —
so a known-good profile is the first thing you can load, tweak, and re-send
without editing firmware or reflashing.

`_resume_sweep()` / single-cell auto-exit now send `Q{self._active_profile_idx}`
instead of a hardcoded `Q4`, so resuming after a single-cell run correctly
returns to whichever profile (static or dynamic) was actually running.

---

### mcu/pimd_mcu.py — v4.07

**New `D` command — RAM-only "dynamic" profile.** Lets a PC app define a new band/
pulse/delay/averages combination and run it immediately without editing `PROFILES`
and reflashing. Motivated by the v4.06 leakage fix requiring a reflash per
`BOUNDARY_PRIME` trial — too slow for iterating on profile shapes generally.

```
D<averages>;<freq_hz>,<pulse_us>,<d1>,<d2>,...;<freq_hz>,<pulse_us>,<d1>,...;...
```

Parses into the same `{'name', 'bands', 'averages'}` shape as a `PROFILES` entry,
rejects bands with differing delay counts (rectangular only), validates with the
existing `validate_profile()` (unchanged — already iterates generically), and
stores the result in a new `dynamic_profile` global. **Not persisted** — lost on
reset, exactly like Mode 1's `*` configure command. Select it with
`Q<DYNAMIC_PROFILE_INDEX>` (= `NUM_PROFILES`, currently 5) same as any static
profile; `G`/`E` behave identically once selected.

**`get_profile(idx)`** added as the single profile-lookup point — `PROFILES[idx]`
for static indices, `dynamic_profile` for `DYNAMIC_PROFILE_INDEX`, else `None`.
Replaces direct `PROFILES[active_profile_index]` indexing in the main loop and the
`Q`/`G` command handlers. `L` listing includes the dynamic profile (if defined) as
an extra line at index `DYNAMIC_PROFILE_INDEX`.

---

### src/pimd_gui.py — v4.02

**Defaults to Standard Operating Conditions at startup** (see SoC section
above): 10.0 kHz / 20.0 µs pulse / 10.0 µs delay / 256 decimation. New
`apply_soc_defaults()` sets the slider/DS-factor state (same pattern as the
existing F1-F4 presets); the `*` command itself still only goes out when
Start is pressed, unchanged.

**Removed the footer's redundant "std dev: ... uV" entry.** It duplicated
the top-right **Std Dev** box — both were showing the firmware's own
filtered-path `p_stddev` (from the `*` record's 3rd field), just via two
different code paths (`luVsd` direct vs. a GUI-side recomputation over its
own `voltage_buffer` of the same incoming values). The GUI-side
recomputation added no information, so the whole `voltage_buffer`/
`computed_stddev` mechanism behind it was removed too (`NUMBER_STDDEV_POINTS`,
the buffer, the calc, and its `clear_chart()` entry).

**Raw-path boxcar average (`A<n>`) sample count now tracks DS Factor**
instead of a hardcoded `A32`. This was the real cause of "the std dev values
should be a lot closer": the footer's `Raw avg: ..., sd: ... uV (x32)` figure
comes from a *different* acquisition path than the Std Dev box — `(x32)` is
literally the `n_samples` argument echoed back from firmware's `A<n>`
handler, i.e. how many raw (undecimated) SDOB samples were boxcar-averaged —
relabelled `(N=...)` in the footer since `(x32)` wasn't self-explanatory.
At a 256 or 1024 DS Factor, the **filtered** path (Std Dev box) gets 8-32×
more oversampling than the raw path's fixed 32 samples — noise scales as
1/√N, so that alone predicts the raw figure being several × higher even with
identical underlying noise. `poll_raw_average()` now sends
`A{min(down_sample, 1000)}` (firmware caps `A<n>` at 1000, so 1024 clamps to
1000) so the two paths use comparable oversampling, making the comparison
meaningful instead of measuring mostly-unrelated averaging depths. Expect
the raw-path figure to still run somewhat higher than the filtered figure —
the LTC2508's onboard decimation filter is a proper sinc/FIR design, more
effective per sample than a plain boxcar average of single-shot raw
conversions (DESIGN §7: raw SDOB single-sample noise ≈ ±1400 µV) — but it
should no longer be off by orders of magnitude.

Values like "30,000 µV" seen before this fix were likely the combination of
the 32-sample raw average *and* not yet being past the 4-minute SoC warm-up
window (large thermal transients land harder on a smaller sample count) —
worth re-checking under SoC conditions now that both are addressed.

**v4.01:** Added editable port field, mirroring `pimd_classviz.py`'s pattern. Was
hardcoded to `'ttyACM0'`; now a `QLineEdit` (default `/dev/ttyACM0`) sits below the
existing Connect/Start/filename rows in the same grid layout. `serial_open()` reads
`self.le_port.text()`, stripping a leading `/dev/` if present, same as classviz.

---

### mcu/pimd_mcu.py — v4.06

**`acquire_mode2()` inter-band leakage fix.** Bands 3 and 4 showed systematic
~500 mV underreads on cells 0–7 and elevated std devs (25–58 mV) compared to
single-cell mode (<4 mV). The last cell of each band (cell 8) read correctly.

**Root cause — cascade contamination:** the sweep visits cells in band-major
order. Cell 8 of each band has its SDOB read at the start of the *next* cycle's
boundary processing (before the frequency changes), giving it a full sweep cycle
(~2 ms) to reach steady state — hence it reads correctly. Cells 0–7 of each
band have their SDBOs read within the same sweep cycle, only 1 PWM period after
the frequency change. When power drops sharply at a boundary (e.g. B3→B4:
P ∝ 10²×43003 → 5²×56992, a 3× drop), the previous band's excess coil energy
contaminates cell 0's initial conditions; cell 0's corrupt drive output then
feeds cell 1's initial conditions, and so on — cascading through cells 0–7. The
rolling average (depth 32) permanently locks in this contaminated value because
the contamination is fresh on every sweep cycle.

**Fix:** add `BOUNDARY_PRIME = 5` extra PWM periods of sleep at each band
boundary. Cell 0 of the new band now runs for 6 total periods before its SDOB
is read, giving the coil time to settle at the new frequency. This breaks the
cascade at source; subsequent cells chain from good initial conditions.

**Tuning:** `BOUNDARY_PRIME` is a named constant at the top of the file (near
`MIN_EMIT_MS`). Increase to 10 or 15 if std dev remains elevated after flashing.
The overhead scales with `period_i`, so the constant works for all boundaries.

**Performance:** 5 boundaries × 5 extra periods × ~35 µs avg ≈ 875 µs/cycle
overhead; cycle rate ~344 Hz; `MIN_EMIT_MS = 10 ms` means emit rate unchanged
at 100 Hz.

---

### src/pimd_classviz.py — v1.03

**Stats tab:** added "Save table CSV…" button. Saves whatever is currently displayed in
the 45-row table (Band, Threshold, Delay, Latest mV, Mean mV, Std mV) — works correctly
when the table is frozen, capturing the snapshot at the time of freeze. Default filename
`src/data/stats_YYYYMMDD_HHMMSS.csv`; file dialog allows changing path.

---

### src/pimd_classviz.py — v1.02

**Resume Sweep now auto-restarts** — previously sent `E` + `Q4` but left the user to click
Start manually, so the sweep never came back. Now also sends `G` and sets the Start button
to Running immediately.

---

### src/pimd_classviz.py — v1.01

Added Stats & Isolation tab.

**Stats table:** 45-row table (band-major, one row per cell) showing Band, Threshold,
Delay (µs), Latest (mV), Mean (mV), Std (mV). Values update at ~30 Hz from the rolling
buffer; window configurable (default 3 s). Freeze button. All values in mV to 1 d.p.
with comma thousands separators (e.g. `4,597.6`).

**Single-cell isolation mode:** stops the Mode 2 profile-4 sweep and fires a single
fixed freq/pulse/delay via Mode 1 (`*<kHz>,<pulse>,<delay>,<ds>` + `S`). Selectable
from Band + Cell combos (dropdown shows `threshold/delay` pairs per band); Downsample
spinbox (default 256). Parses Mode 1 `*` output records and displays:
- **Value** — current averaged reading (mV)
- **HW σ** — per-reading std dev reported by firmware (intra-average noise)
- **Run mean / Run σ** — running mean and std over up to 1000 readings (inter-reading
  drift and noise)
- **N** — count since last Run Single Cell click

"Resume Sweep" sends `E`, re-selects `Q4`, and re-enables the Start button. Clicking
Start while in single-cell mode also auto-resumes. Purpose: isolate noise per cell
without frequency switching, to determine whether noise is frequency-change-induced.

---

### src/pimd_classviz.py — v1.00

New PC tool: real-time signature visualiser + labelled-data logger for Mode 2
profile 4 (CLASSIFY_EP).

- **5×9 pyqtgraph heatmap** (bands = rows, threshold-voltage cells = columns) of
  signed cell deviations (Δ = raw − baseline). Per-band delay shown in status bar
  on mouse hover.
- **Display modes:** Δ deviation (default) | Z normalised | RAW abs µV.
  Δ and Z use a diverging blue–white–red colormap centred at zero so polarity and
  sign-flips across cells/bands are immediately visible; RAW uses sequential.
- **Symmetric autoscale** (±max|value|) toggled by checkbox; manual range entry when off.
- **Baseline source modes:**
  - *Static capture* — average N frames (default 64), stores per-cell mean + std.
  - *Rolling median* — per-cell median over last T seconds (default 3 s),
    continuously recalculated; drift-corrects bench without user intervention.
  - *Nominal thresholds* — (4.5 − 0.5·j) V × 1e6 µV per cell, all bands.
  Baseline info label shows mode, frame count, and age.
- **Freeze toggle.** Zero-crossing display: per-band polarity sign and interpolated
  threshold voltage where Δ flips sign — useful ML feature (silver/stainless crossover).
- **ML bridge:** label field + "Record Snapshot" appends one CSV row; "Log Continuously"
  toggle appends every incoming W4 frame with the current label (for target passes).
  Configurable CSV path (default `src/data/signatures_YYYYMMDD.csv`); stable header
  written once; header comment documents all 137 columns.
- **Phase 2 — 3D surface:** GLSurfacePlotItem of the current display matrix (Δ by
  default), orbit camera. Toggled with "Switch to 3D Surface" button. The 5-band axis
  is coarse — interpolation is cosmetic only.
- Serial seam matches `pimd_scope.py` exactly (QSerialPort `readyRead` signal, editable
  port field defaulting to `/dev/ttyACM0 @115200`). On connect sends `E` then `Q4`;
  on close/disconnect sends `E`.

---

### mcu/pimd_mcu.py — v4.05

**CLASSIFY_EP (profile 4) band frequencies updated to prime-ish actuals.** Round numbers
replaced with the PWM-achievable prime-ish frequencies from the §17.1 equal-power sweep:

| Band | Old Hz | New Hz | Pulse |
|------|--------|--------|-------|
| 0 | 10600 | **10601** | 40 µs |
| 1 | 17600 | **17599** | 30 µs |
| 2 | 29200 | **29201** | 20 µs |
| 3 | 43000 | **43003** | 10 µs |
| 4 | 57000 | **56992** | 5 µs |

These are the measured operating points from the bench power sweep (2026-06-17). Using
prime-ish rates avoids beat-frequency noise (same principle as the 3719 Hz choice noted
in §8). Delays and averages unchanged.

---

### mcu/pimd_mcu.py — v4.04

**`acquire_mode2()` band-boundary SDOB corruption fix.** The last delay cell of each band
(d8 for P0–P3 in CLASSIFY_EP) read an incorrect, unstable value while all other cells were
clean and monotonic.

**Root cause:** when `pwm.freq()` increases the PWM frequency, the RP2040 hardware shrinks
the WRAP register. If the running counter already exceeds the new WRAP it wraps immediately,
generating a spurious falling edge on GPIO5 (MCLK). The LTC2508 treats this as a new
conversion trigger, overwriting the previous cell's SDOB result before the firmware reads it.
The four increasing-freq boundaries (bands 0→1, 1→2, 2→3, 3→4) were all affected; the
decreasing-freq wrap-around (band 4→0, i=0) was immune because enlarging WRAP never causes
an immediate wrap.

**Fix:** at band boundaries, read SDOB **before** calling `pwm.freq()`, then change freq,
then write CC. Non-boundary cells retain the original CC-write-first order unchanged.
Timing margin at the tightest boundary (band 4, 5 µs pulse): CC is written ~2 µs after the
counter resets on the freq change; drive trigger fires at 5 µs — 3 µs margin, safe.

---

### mcu/pimd_mcu.py — v4.03

**Profile structure changed** — replaced flat `freq_hz` / `pulses_us` / `delays_us` top-level
keys with `bands: [(freq_hz, pulse_us, delays_us), …]` to support per-band frequencies
within a single profile. All existing profiles (0–3) converted; profile structure is now a
tuple of `(freq_hz, pulse_us, delays_us_tuple)` per band.

**New profile 4 — CLASSIFY_EP** (5 equal-power bands × 9 calibrated sample delays = 45 cells).
Delays sourced from `src/data/delaycal_1706-104844.csv` (voltage-threshold crossing times
at 4.5 V → 0.5 V in 0.5 V steps).

| Idx | Freq | Pulse | Sample delays (µs) |
|-----|-----------|-------|--------------------|
| 0 | 10601 Hz | 40 µs | 8.56 8.98 9.37 9.72 10.08 10.49 10.96 11.57 12.53 |
| 1 | 17599 Hz | 30 µs | 8.12 8.54 8.92 9.27  9.63 10.02 10.50 11.10 12.03 |
| 2 | 29201 Hz | 20 µs | 7.62 8.03 8.40 8.75  9.11  9.50  9.96 10.55 11.46 |
| 3 | 43003 Hz   | 10 µs | 6.80 7.22 7.58 7.93  8.28  8.66  9.11  9.70 10.57 |
| 4 | 56992/Hz   |  5 µs | 6.03 6.43 6.78 7.12  7.46  7.84  8.28  8.85  9.71 |

**`acquire_mode2()` rewritten** — flattens all bands into a single cell list at entry;
updates PWM freq only at band boundaries (detected by comparing `cells[i][0]` to
`cells[(i-1)%n][0]`); the interleaved one-period-per-cell rolling-average loop is
otherwise unchanged.

**`validate_profile()`** updated to iterate over `bands` tuples.

**L command** updated: record format now emits `n_bands` and `n_cells` in place of the
former `n_pulses` / `n_delays` fields:
```
L<idx>,<first_freq_khz>,<n_bands>,<n_cells>,<averages>,<name>
```

**`acquire_raw_average()` primed** (v4.02, carried into v4.03) — 5-sample discard at the
start of each `A<n>` call to allow PWM + front-end to settle after any freq/duty change
from a prior `*` command. Overhead ≤ 5% at 10 kHz; negligible at higher frequencies.

---

### mcu/pimd_mcu.py — v4.02 / v4.01 / v4.00 — migrated from the file header (2026-07-22)

These three earliest entries predated `CHANGELOG.md` and lived only in the file's
header changelog; migrated verbatim here when the per-file headers were slimmed to a
terse version lineage (see the 2026-07-22 header-slim entry above the marker line).

**v4.02** — `acquire_raw_average`: discard the first 5 samples (priming) so the PWM
wrap-register glitch after a frequency change settles before the averaged window begins;
fixes near-zero readings on `A<n>` when the frequency changes between `*` commands. (Also
recorded in the v4.03 entry above as "carried into v4.03".)

**v4.01** — `acquire_mode2`: CC written first at period start (~1–2 µs) before the SPI
read — eliminates the CC-write race on multi-cell profiles; precompute `cell_duties`;
prime now fires `cell[n-1]` (removes the startup transient in `rolling[n-1]`); command
poll moved out of the W-emit gate so `E` stops within one `n_pulses*n_delays` cycle.

**v4.00** — complete serial protocol rewrite: two non-concurrent modes, `W` streaming,
`Q`/`G` commands; file renamed from `pimd_mcu_302.py` to `pimd_mcu.py`.

---

### src/pimd_scope.py — v4.01

- `PROFILES_META` converted from flat per-profile dict to `{bands: [(freq_khz, pulse_us,
  delays_us), …]}` format, matching firmware v4.03 structure.
- Profile 4 `CLASSIFY_EP` added to `PROFILES_META`.
- `_update_titles()` updated: detects multi-band profiles; header shows `multi-freq` when
  bands have different frequencies; each subplot labelled `{freq}kHz/{pulse}us d={delay}us`
  for multi-band profiles, `d={delay}us` for single-band; fontsize=7 when >12 channels.

---

### src/pimd_delaycal.py — v1.02 (new tool, not yet in DESIGN §15)

New PC tool for calibrating `A<n>` delay pairs. Sends sequential `*` + `A<n>` commands
across user-specified (freq_kHz, pulse_us) pairs and delay ranges, records threshold
crossings, and exports a CSV.

**Double-send bug fixed (v1.01 → v1.02):** `_on_r_record()` was calling `_send_next_step()`
twice on pair transitions — once via `_check_thresholds()` → `_advance_pair()`, and again
at the end of `_on_r_record()`. Result: `_prev_delay` was reset to `start_delay` on every
other pair; rows 3, 5 showed all cells equal to start_delay. Fix: save `current_pair_idx`
and `current_delay` before calling `_check_thresholds()`; only advance state if `_pair_idx`
is unchanged after the call.

**Known cosmetic issue:** docstring title line still reads "v1.01"; `APP_VERSION = '1.02'`
and the inline changelog entries are correct. Reconcile on next edit.

---

### Bench observations — 2026-06-17

**CLASSIFY_EP (profile 4) confirmed streaming:** firmware flashed, 45-channel W4 records
verified. Two consecutive records (50 ms apart):

```
W4,47439,4597625,4120578,...,562667,227699
W4,47489,4597492,4120426,...,562667,227699
```

Values in µV. Channels decrease monotonically across each band's delay sweep (shortest
delay → highest signal ~4.5 V; longest delay → lowest signal ~0.23 V). Values stable
between records. All 5 bands × 9 cells populated correctly.

---

## Archive — migrated from file headers (2026-07-22)

These earliest entries predated `CHANGELOG.md` and lived only in their file's header
changelog; migrated here verbatim when the per-file headers were slimmed to a terse
version lineage (see the header-slim entry above the marker line at the top of this file).

### src/pimd_delaycal.py — v1.01 / v1.00 — migrated from the file header

**v1.01** — freq and pulse width are now paired as tuples (freq/pulse input field, e.g.
`25/10`).

**v1.00** — initial version.

### src/pimd_gui.py — v4.01 / v4.00 — migrated from the file header

**v4.01** — added an editable port field (mirrors `pimd_classviz.py`); was hardcoded to
`ttyACM0`. `serial_open()` now reads `self.le_port.text()`, stripping a leading `/dev/`
if present.

**v4.00** — renamed from `pimd302.py`; `W` (Mode 2 stream) records silently ignored; window
title updated.

---
