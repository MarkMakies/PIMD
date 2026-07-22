#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# PIMD Target Registry (pimd_targets.py) v1
# — loads and validates data/training_lists/targets.csv, the human-maintained
#   registry of physical target objects captured by the PIMD detector. Shared
#   by pimd_classviz.py's Analysis/Training tabs and pimd_features.py's
#   corpus builder -- one implementation, so both tools agree on what a valid
#   target row looks like.
# Runs on Ubuntu desktop / laptop, standalone CLI script (no GUI, no Qt).
#
# The registry is human-owned data -- this module reads and validates it,
# never writes it. Comment lines start with '#'; some are quoted (they
# contain a literal comma), so the file is parsed with the csv module, not a
# hand split(','). Columns and enums are documented in the registry file's
# own header comment block; the validation rules below (dims-sorted,
# wall_thickness-on-shape, closed_loop-on-material, mass-plausibility) are
# warnings, not errors -- the registry owner has judgment calls on physical
# measurements that this tool can't second-guess.
#
# History (full detail in CHANGELOG.md):
#   v1 initial version
###############################################################################

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY_PATH = os.path.join(SCRIPT_DIR, 'data', 'training_lists', 'targets.csv')

TARGET_ID_RE = re.compile(r'^[A-Za-z0-9_]+$')

REQUIRED_COLUMNS = ['target_id', 'short_name', 'shape_class', 'dim_a_mm', 'dim_b_mm',
                    'dim_c_mm', 'wall_thickness_mm', 'closed_loop', 'mass_g',
                    'magnet_test', 'material_class', 'plating_material', 'substrate']

SHAPE_CLASS_ENUM = {'rod', 'tube', 'ring', 'disc', 'plate', 'dome', 'block', 'sphere',
                     'bolt', 'wire_coil', 'collection', 'composite', 'irregular'}
CLOSED_LOOP_ENUM = {'y', 'n', 'na', 'unk'}
MAGNET_TEST_ENUM = {'strong', 'weak', 'none', 'unk'}

# Shapes for which a wall_thickness_mm value is expected and unremarkable
# (hollow sections / bores; for rings this is the radial wall). Any other
# shape carrying a wall_thickness_mm is flagged -- a warning, not an error,
# since the registry owner has judgment calls here.
NO_WARN_WALL_THICKNESS_SHAPES = {'tube', 'block', 'dome', 'ring', 'wire_coil'}

# material_class values that are not electrically conductive -- closed_loop
# 'y' (a macroscopic closed conductive ring path) doesn't make physical
# sense for these; 'na' is the registry's own convention for that case.
NON_CONDUCTIVE_MATERIALS = {'ferrite'}

MASS_TOLERANCE_FACTOR = 1.05   # mass_g may exceed the solid bounding-box mass by at most this factor

# g/cm^3 -- a solid bounding box of this material can't weigh less than
# mass_g implies. Figures are the task brief's own density table; do not
# re-derive or approximate.
DENSITY_G_PER_CM3 = {
    'steel': 7.85, 'stainless': 7.9, 'cast_iron': 7.2, 'copper': 8.96,
    'brass': 8.5, 'cu_alloy': 8.8, 'lead': 11.34, 'aluminium': 2.70,
    'silver': 10.49, 'solder_sn_pb': 8.5, 'ferrite': 4.9, 'ndfeb': 7.5,
}


@dataclass(frozen=True)
class Target:
    target_id: str
    short_name: str
    shape_class: str
    dim_a_mm: float
    dim_b_mm: float
    dim_c_mm: float
    wall_thickness_mm: object   # float or None
    closed_loop: str
    mass_g: float
    magnet_test: str
    material_class: str
    plating_material: object    # str or None
    substrate: object           # str or None


@dataclass(frozen=True)
class Issue:
    severity: str     # 'error' | 'warning'
    row: object        # int or None -- 1-based physical CSV line
    target_id: object  # str or None
    message: str


def _optional_str(s):
    s = s.strip()
    return s if s else None


def load_targets(path=DEFAULT_REGISTRY_PATH):
    """Load and validate the target registry. Returns (targets, issues):
    targets is dict[target_id -> Target] (always usable; empty only if the
    header itself is unreadable). issues is list[Issue] -- errors and
    warnings both collected, never stops at the first problem, so a single
    CLI run surfaces everything wrong with the file at once. Raises
    FileNotFoundError/OSError unchanged if `path` can't be opened -- callers
    that need a degraded "missing registry" UI state catch that themselves."""
    targets = {}
    issues = []

    with open(path, newline='') as f:
        header, header_row_no, data_rows = None, None, []
        for row_no, fields in enumerate(csv.reader(f), start=1):
            if not fields or all(not v.strip() for v in fields):
                continue   # genuinely blank line -- not the same as a data row with an empty target_id
            if fields[0].lstrip().startswith('#'):
                continue
            if header is None:
                header, header_row_no = fields, row_no
                continue
            data_rows.append((row_no, fields))

    if header is None:
        issues.append(Issue('error', None, None, 'no header row found (every row is blank or a comment)'))
        return targets, issues

    ncols = len(REQUIRED_COLUMNS)
    if header[:ncols] != REQUIRED_COLUMNS:
        issues.append(Issue('error', header_row_no, None,
                             'header does not match required columns {0}: got {1}'.format(
                                 REQUIRED_COLUMNS, header[:ncols])))
        return targets, issues

    seen_ids = {}   # target_id -> first row_no seen

    for row_no, fields in data_rows:
        if len(fields) < ncols:
            issues.append(Issue('error', row_no, None,
                                 'row has {0} columns, expected at least {1}'.format(len(fields), ncols)))
            continue
        (target_id, short_name, shape_class, dim_a_s, dim_b_s, dim_c_s, wall_s,
         closed_loop, mass_s, magnet_test, material_class, plating_material, substrate) = fields[:ncols]

        target_id = target_id.strip()
        row_ok = True

        if not target_id:
            issues.append(Issue('error', row_no, None, 'empty target_id'))
            row_ok = False
        elif not TARGET_ID_RE.match(target_id):
            issues.append(Issue('error', row_no, target_id,
                                 "target_id '{0}' does not match ^[a-z0-9_]+$".format(target_id)))
            row_ok = False

        if target_id:
            if target_id in seen_ids:
                issues.append(Issue('error', row_no, target_id,
                                     'duplicate target_id (first seen at row {0})'.format(seen_ids[target_id])))
                row_ok = False
            else:
                seen_ids[target_id] = row_no

        if shape_class not in SHAPE_CLASS_ENUM:
            issues.append(Issue('error', row_no, target_id,
                                 "shape_class '{0}' not in {1}".format(shape_class, sorted(SHAPE_CLASS_ENUM))))
            row_ok = False
        if closed_loop not in CLOSED_LOOP_ENUM:
            issues.append(Issue('error', row_no, target_id,
                                 "closed_loop '{0}' not in {1}".format(closed_loop, sorted(CLOSED_LOOP_ENUM))))
            row_ok = False
        if magnet_test not in MAGNET_TEST_ENUM:
            issues.append(Issue('error', row_no, target_id,
                                 "magnet_test '{0}' not in {1}".format(magnet_test, sorted(MAGNET_TEST_ENUM))))
            row_ok = False

        dims = {}
        for name, raw in (('dim_a_mm', dim_a_s), ('dim_b_mm', dim_b_s), ('dim_c_mm', dim_c_s)):
            try:
                dims[name] = float(raw.strip())
            except ValueError:
                issues.append(Issue('error', row_no, target_id, "unparseable {0}: '{1}'".format(name, raw)))
                row_ok = False
                dims[name] = None

        wall_mm = None
        if wall_s.strip():
            try:
                wall_mm = float(wall_s.strip())
            except ValueError:
                issues.append(Issue('error', row_no, target_id,
                                     "unparseable wall_thickness_mm: '{0}'".format(wall_s)))
                row_ok = False

        mass_g = None
        try:
            mass_g = float(mass_s.strip())
        except ValueError:
            issues.append(Issue('error', row_no, target_id, "unparseable mass_g: '{0}'".format(mass_s)))
            row_ok = False

        # -- warnings (only meaningful once the relevant values parsed) --
        dim_a, dim_b, dim_c = dims['dim_a_mm'], dims['dim_b_mm'], dims['dim_c_mm']
        if dim_a is not None and dim_b is not None and dim_c is not None:
            if not (dim_a >= dim_b >= dim_c):
                issues.append(Issue('warning', row_no, target_id,
                                     'dims not sorted: dim_a_mm={0} dim_b_mm={1} dim_c_mm={2} '
                                     '(expected dim_a >= dim_b >= dim_c)'.format(dim_a, dim_b, dim_c)))

        if wall_mm is not None and shape_class not in NO_WARN_WALL_THICKNESS_SHAPES:
            issues.append(Issue('warning', row_no, target_id,
                                 "wall_thickness_mm={0} set on shape_class '{1}', outside the usual "
                                 '{2}'.format(wall_mm, shape_class, sorted(NO_WARN_WALL_THICKNESS_SHAPES))))

        if closed_loop == 'y' and material_class in NON_CONDUCTIVE_MATERIALS:
            issues.append(Issue('warning', row_no, target_id,
                                 "closed_loop='y' on non-conductive material_class '{0}' "
                                 "(consider 'na')".format(material_class)))

        if (mass_g is not None and dim_a is not None and dim_b is not None and dim_c is not None
                and material_class in DENSITY_G_PER_CM3):
            # dims are in mm -> mm^3; /1000.0 converts to cm^3 before
            # multiplying by g/cm^3 density. Dropping this factor is a
            # 1000x error -- the single most likely implementer mistake.
            bbox_mass_g = DENSITY_G_PER_CM3[material_class] * (dim_a * dim_b * dim_c) / 1000.0
            if mass_g > MASS_TOLERANCE_FACTOR * bbox_mass_g:
                issues.append(Issue('warning', row_no, target_id,
                                     'mass_g={0} exceeds {1}x the solid bounding-box mass ({2:.1f} g at '
                                     '{3} g/cm^3) -- implausible unless hollow/composite is expected'.format(
                                         mass_g, MASS_TOLERANCE_FACTOR, bbox_mass_g,
                                         DENSITY_G_PER_CM3[material_class])))

        if not row_ok:
            continue

        targets[target_id] = Target(
            target_id=target_id, short_name=short_name.strip(), shape_class=shape_class,
            dim_a_mm=dim_a, dim_b_mm=dim_b, dim_c_mm=dim_c, wall_thickness_mm=wall_mm,
            closed_loop=closed_loop, mass_g=mass_g, magnet_test=magnet_test,
            material_class=material_class, plating_material=_optional_str(plating_material),
            substrate=_optional_str(substrate),
        )

    return targets, issues


def _format_dim(x):
    if x is None:
        return ''
    return str(int(x)) if float(x).is_integer() else str(x)


def print_target_table(targets, issues):
    header = ('target_id', 'short_name', 'shape_class', 'dim_a', 'dim_b', 'dim_c',
              'mass_g', 'material_class')
    rows = [(t.target_id, t.short_name, t.shape_class, _format_dim(t.dim_a_mm),
              _format_dim(t.dim_b_mm), _format_dim(t.dim_c_mm), _format_dim(t.mass_g),
              t.material_class)
             for t in sorted(targets.values(), key=lambda t: t.target_id)]

    print('{0} target(s):'.format(len(targets)))
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
              for i, h in enumerate(header)]

    def fmt_row(vals):
        return '  '.join(str(v).ljust(w) for v, w in zip(vals, widths))

    print(fmt_row(header))
    print(fmt_row(['-' * w for w in widths]))
    for r in rows:
        print(fmt_row(r))

    print()
    if not issues:
        print('No issues.')
        return
    n_errors = sum(1 for i in issues if i.severity == 'error')
    n_warnings = sum(1 for i in issues if i.severity == 'warning')
    print('Issues: {0} error(s), {1} warning(s)'.format(n_errors, n_warnings))
    for i in issues:
        where = 'row {0}'.format(i.row) if i.row is not None else 'row ?'
        who = ' ({0})'.format(i.target_id) if i.target_id else ''
        print('  [{0}] {1}{2}: {3}'.format(i.severity, where, who, i.message))


def build_arg_parser():
    p = argparse.ArgumentParser(description='Load and validate the PIMD target registry.')
    p.add_argument('--registry', default=DEFAULT_REGISTRY_PATH,
                    help='Path to targets.csv (default: {0}).'.format(DEFAULT_REGISTRY_PATH))
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        targets, issues = load_targets(args.registry)
    except OSError as e:
        print('Could not read registry {0}: {1}'.format(args.registry, e), file=sys.stderr)
        return 1
    print_target_table(targets, issues)
    return 1 if any(i.severity == 'error' for i in issues) else 0


if __name__ == '__main__':
    sys.exit(main())
