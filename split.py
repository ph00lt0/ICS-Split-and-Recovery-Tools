#!/usr/bin/env python3
"""Split a large ICS file into chunks under a specified size limit."""

import sys
from pathlib import Path

# Top-level components that get split across files
SPLIT_COMPONENTS = {"VEVENT", "VTODO", "VJOURNAL", "VFREEBUSY"}
# Components that stay in the header (shared by all output files)
HEADER_COMPONENTS = {"VTIMEZONE"}


def parse_ics(filepath):
    """Parse ICS file into header lines, splittable components, and footer.
    Properly handles nested sub-components like VALARM inside VEVENT."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_lines = []
    components = []
    footer_lines = []

    current_type = None
    sub_depth = 0
    current_lines = []

    for line in lines:
        stripped = line.strip()

        if current_type is not None:
            current_lines.append(line)

            if stripped.startswith("BEGIN:"):
                sub_depth += 1
            elif stripped.startswith("END:"):
                if sub_depth > 0:
                    sub_depth -= 1
                elif stripped == f"END:{current_type}":
                    if current_type in HEADER_COMPONENTS:
                        header_lines.extend(current_lines)
                    else:
                        components.append(current_lines[:])
                    current_type = None
                    current_lines = []
                    sub_depth = 0

        elif stripped.startswith("BEGIN:"):
            comp_name = stripped.split(":", 1)[1]
            if comp_name in SPLIT_COMPONENTS or comp_name in HEADER_COMPONENTS:
                current_type = comp_name
                current_lines = [line]
                sub_depth = 0
            else:
                header_lines.append(line)
        elif stripped == "END:VCALENDAR":
            footer_lines.append(line)
        else:
            header_lines.append(line)

    return header_lines, components, footer_lines


def estimate_size(header_lines, components, footer_lines):
    total = sum(len(l.encode("utf-8")) for l in header_lines)
    for comp in components:
        total += sum(len(l.encode("utf-8")) for l in comp)
    total += sum(len(l.encode("utf-8")) for l in footer_lines)
    return total


def write_ics(filepath, header_lines, components, footer_lines):
    p = Path(filepath)
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(header_lines)
        for comp in components:
            f.writelines(comp)
        f.writelines(footer_lines)
    return p.stat().st_size


def split_ics(input_path, output_prefix, max_size_mb=9.0):
    max_bytes = int(max_size_mb * 1024 * 1024)

    header, components, footer = parse_ics(input_path)

    if not components:
        print("No splittable components (VEVENT/VTODO/VJOURNAL) found!")
        sys.exit(1)

    print(f"Found {len(components)} events")

    for i, comp in enumerate(components):
        s = sum(len(l.encode("utf-8")) for l in comp)
        if s > max_bytes:
            print(f"WARNING: Event {i+1} alone is {s/(1024*1024):.2f} MB (exceeds limit)")

    # Don't overwrite input
    input_resolved = Path(input_path).resolve()

    # Check existing output files
    n = 1
    existing = []
    while True:
        t = f"{output_prefix}_{n}.ics"
        if Path(t).exists():
            existing.append(t)
            n += 1
        else:
            break
    if existing:
        print(f"Warning: Existing files: {existing}")
        resp = input("Overwrite? (y/n): ").strip().lower()
        if resp != "y":
            print("Aborted.")
            sys.exit(0)

    # Build chunks
    chunks = []
    current_chunk = []

    for comp in components:
        new_size = estimate_size(header, current_chunk + [comp], footer)
        if current_chunk and new_size > max_bytes:
            chunks.append(current_chunk)
            current_chunk = [comp]
        else:
            current_chunk.append(comp)

    if current_chunk:
        chunks.append(current_chunk)

    # Write
    for i, chunk in enumerate(chunks):
        filename = f"{output_prefix}_{i+1}.ics"
        if Path(filename).resolve() == input_resolved:
            print(f"ERROR: Output {filename} would overwrite input! Skipping.")
            continue
        size = write_ics(filename, header, chunk, footer)
        print(f"Created {filename}: {size/(1024*1024):.2f} MB ({len(chunk)} events)")

    print(f"\nDone! {len(chunks)} files created. Original untouched.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.ics [output_prefix] [max_size_mb]")
        sys.exit(1)

    input_file = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else Path(input_file).stem + "_split"
    max_mb = float(sys.argv[3]) if len(sys.argv) > 3 else 9.0

    split_ics(input_file, prefix, max_mb)