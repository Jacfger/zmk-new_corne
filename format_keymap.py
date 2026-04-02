#!/usr/bin/env python3
"""
Formatter for the Eyelash Corne ZMK keymap file.

Parses bindings in each layer and aligns them into a readable grid
matching the physical keyboard layout.

Usage:
    python format_keymap.py [keymap_file]
    python format_keymap.py                    # defaults to config/eyelash_corne.keymap
    python format_keymap.py --check            # check only, exit 1 if changes needed
"""

import re
import sys
from pathlib import Path

# Eyelash Corne physical layout — groups per row:
#   Row 0: 6 left  |  1 encoder  |  6 right              = 13
#   Row 1: 6 left  |  3 encoder  |  6 right              = 15
#   Row 2: 6 left  |  1 extra  |  1 encoder  |  6 right  = 14
#   Row 3:         3 left thumb  |  3 right thumb         =  6
ROW_GROUPS = [
    [6, 1, 6],
    [6, 3, 6],
    [6, 1, 1, 6],
    [3, 3],
]

ROW_SIZES = [sum(g) for g in ROW_GROUPS]

# Section definitions for rows 0-2: (left_group_indices, mid_group_indices, right_group_indices)
ROW_SECTIONS = [
    ([0], [1], [2]),
    ([0], [1], [2]),
    ([0], [1, 2], [3]),
]

MID_GAP = 4  # spaces between left↔mid and mid↔right


def parse_bindings(text: str) -> list[str]:
    tokens = text.split()
    bindings, current = [], []
    for tok in tokens:
        if tok.startswith("&") and current:
            bindings.append(" ".join(current))
            current = [tok]
        else:
            current.append(tok)
    if current:
        bindings.append(" ".join(current))
    return bindings


def split_into_rows(bindings: list[str]) -> list[list[str]]:
    rows, offset = [], 0
    for size in ROW_SIZES:
        rows.append(bindings[offset : offset + size])
        offset += size
    return rows


def split_into_groups(row: list[str], group_sizes: list[int]) -> list[list[str]]:
    groups, offset = [], 0
    for size in group_sizes:
        groups.append(row[offset : offset + size])
        offset += size
    return groups


def format_group(group: list[str], widths: list[int], pad_last: bool = True) -> str:
    parts = []
    for i, (b, w) in enumerate(zip(group, widths)):
        if i == len(group) - 1 and not pad_last:
            parts.append(b)
        else:
            parts.append(b.ljust(w))
    return " ".join(parts)


def group_width(widths: list[int]) -> int:
    return sum(widths) + max(0, len(widths) - 1)


def format_keymap(content: str) -> str:
    pattern = re.compile(r"(bindings\s*=\s*<\s*\n)(.*?)(>\s*;)", re.DOTALL)

    all_bindings = []
    for match in pattern.finditer(content):
        bindings = parse_bindings(match.group(2))
        if len(bindings) == sum(ROW_SIZES):
            all_bindings.append(bindings)

    if not all_bindings:
        print("No binding blocks found with expected size", file=sys.stderr)
        return content

    # Compute per-row per-group column widths
    col_widths = []
    for row_idx, groups_def in enumerate(ROW_GROUPS):
        row_w = [[0] * g for g in groups_def]
        for bindings in all_bindings:
            rows = split_into_rows(bindings)
            groups = split_into_groups(rows[row_idx], groups_def)
            for gi, grp in enumerate(groups):
                for ci, b in enumerate(grp):
                    row_w[gi][ci] = max(row_w[gi][ci], len(b))
        col_widths.append(row_w)

    # Unify left-6 column widths across rows 0-2 (all have 6-col left group at index 0)
    left_unified = [0] * 6
    for row_idx in range(3):
        for ci in range(6):
            left_unified[ci] = max(left_unified[ci], col_widths[row_idx][0][ci])
    for row_idx in range(3):
        col_widths[row_idx][0] = list(left_unified)

    # Unify right-6 column widths across rows 0-2 (last group in each row)
    right_unified = [0] * 6
    for row_idx in range(3):
        right_gi = len(col_widths[row_idx]) - 1
        for ci in range(6):
            right_unified[ci] = max(right_unified[ci], col_widths[row_idx][right_gi][ci])
    for row_idx in range(3):
        right_gi = len(col_widths[row_idx]) - 1
        col_widths[row_idx][right_gi] = list(right_unified)

    # Compute section widths for alignment
    def section_w(row_idx: int, group_indices: list[int]) -> int:
        w = 0
        for i, gi in enumerate(group_indices):
            w += group_width(col_widths[row_idx][gi])
            if i < len(group_indices) - 1:
                w += 2
        return w

    max_mid_w = max(section_w(ri, sec[1]) for ri, sec in enumerate(ROW_SECTIONS))
    left_w = group_width(left_unified)  # same for all rows now

    def format_alpha_row(row_idx: int, row_bindings: list[str]) -> str:
        groups = split_into_groups(row_bindings, ROW_GROUPS[row_idx])
        left_gi, mid_gi, right_gi = ROW_SECTIONS[row_idx]

        # Left section
        left_parts = [format_group(groups[gi], col_widths[row_idx][gi]) for gi in left_gi]
        left_str = "  ".join(left_parts)

        # Mid section
        mid_parts = [format_group(groups[gi], col_widths[row_idx][gi]) for gi in mid_gi]
        mid_str = "  ".join(mid_parts)
        mid_pad = max_mid_w - len(mid_str)

        # Right section (don't pad last column of last group)
        right_parts = []
        for i, gi in enumerate(right_gi):
            right_parts.append(
                format_group(groups[gi], col_widths[row_idx][gi], pad_last=(i < len(right_gi) - 1))
            )
        right_str = "  ".join(right_parts)

        return left_str + " " * MID_GAP + mid_str + " " * (mid_pad + MID_GAP) + right_str

    def format_thumb_row(row_bindings: list[str]) -> str:
        groups = split_into_groups(row_bindings, ROW_GROUPS[3])
        left_str = format_group(groups[0], col_widths[3][0])
        right_str = format_group(groups[1], col_widths[3][1], pad_last=False)

        # Center the thumb gap on the mid section
        mid_start = left_w + MID_GAP
        mid_end = mid_start + max_mid_w + MID_GAP
        thumb_gap = mid_end - mid_start
        thumb_total = len(left_str) + thumb_gap + len(right_str)

        # Indent so thumb cluster is centered under the full row width
        full_row_w = left_w + MID_GAP + max_mid_w + MID_GAP + group_width(right_unified)
        indent = max(0, (full_row_w - thumb_total) // 2)

        return " " * indent + left_str + " " * thumb_gap + right_str

    def format_layer(bindings: list[str]) -> str:
        rows = split_into_rows(bindings)
        lines = [format_alpha_row(i, rows[i]) for i in range(3)]
        lines.append(format_thumb_row(rows[3]))
        return "\n".join(lines)

    def replacer(match: re.Match) -> str:
        prefix, raw, suffix = match.group(1), match.group(2), match.group(3)
        bindings = parse_bindings(raw)
        if len(bindings) != sum(ROW_SIZES):
            return match.group(0)
        return prefix + format_layer(bindings) + "\n" + suffix

    return pattern.sub(replacer, content)


def main():
    check_only = "--check" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--check"]

    keymap_path = Path(args[0]) if args else Path(__file__).parent / "config" / "eyelash_corne.keymap"

    if not keymap_path.exists():
        print(f"File not found: {keymap_path}", file=sys.stderr)
        sys.exit(1)

    original = keymap_path.read_text()
    formatted = format_keymap(original)

    if check_only:
        if original != formatted:
            print(f"Keymap needs formatting: {keymap_path}")
            sys.exit(1)
        print(f"Keymap is formatted: {keymap_path}")
        sys.exit(0)

    if original == formatted:
        print("Already formatted, no changes needed.")
    else:
        keymap_path.write_text(formatted)
        print(f"Formatted: {keymap_path}")


if __name__ == "__main__":
    main()
