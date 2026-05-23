#!/usr/bin/env python3
"""
Extract ONLY the specific failed events from the original ICS file.
Handles ICS line folding (long lines broken across multiple lines).
"""

import sys
import os
import re
from pathlib import Path


def extract_uids_from_log(log_content):
    """Parse the error log to find UIDs."""
    pattern = re.compile(
        r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
        re.IGNORECASE,
    )
    return set(m.group(1).upper() for m in pattern.finditer(log_content))


def unfold_ics(content):
    """Unfold ICS line continuations (lines starting with space/tab)."""
    return re.sub(r'\r?\n[ \t]', '', content)


def parse_ics_for_uids(filepath, target_uids):
    """Scan the ICS file and return events matching target UIDs."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Unfold first so multi-line UIDs become single lines
    content = unfold_ics(content)
    lines = content.splitlines(keepends=True)

    vtimezones = []
    matching_events = {}

    current_type = None
    sub_depth = 0
    current_lines = []
    current_uid = None

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
                    if current_type == "VTIMEZONE":
                        vtimezones.append(current_lines[:])
                    elif current_type in ("VEVENT", "VTODO") and current_uid:
                        if current_uid in target_uids:
                            matching_events[current_uid] = current_lines[:]

                    current_type = None
                    current_lines = []
                    current_uid = None
                    sub_depth = 0

        elif stripped.startswith("BEGIN:"):
            comp_name = stripped.split(":", 1)[1]
            if comp_name == "VTIMEZONE":
                current_type = "VTIMEZONE"
                current_lines = [line]
                sub_depth = 0
            elif comp_name in ("VEVENT", "VTODO"):
                current_type = comp_name
                current_lines = [line]
                sub_depth = 0
                current_uid = None

        elif current_type in ("VEVENT", "VTODO") and stripped.upper().startswith("UID:"):
            uid_val = stripped.split(":", 1)[1].strip().upper()
            # Strip common prefixes like URN:UUID:
            uid_val = uid_val.replace("URN:UUID:", "")
            current_uid = uid_val

    return vtimezones, matching_events


def write_single_event(filepath, event_lines, vtimezones):
    """Write a valid ICS file with the event and timezones."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("BEGIN:VCALENDAR\r\n")
        f.write("VERSION:2.0\r\n")
        f.write("PRODID:-//Recovery Script//EN\r\n")

        for tz_lines in vtimezones:
            f.writelines(tz_lines)

        f.writelines(event_lines)
        f.write("END:VCALENDAR\r\n")


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 recover_failed.py <errors.txt> <original.ics> [output_dir]")
        sys.exit(1)

    log_file = sys.argv[1]
    ics_file = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "recovered_failed"

    # 1. Read error log
    print(f"Reading error log: {log_file}")
    with open(log_file, "r", encoding="utf-8") as f:
        log_content = f.read()

    target_uids = extract_uids_from_log(log_content)
    print(f"Found {len(target_uids)} unique failed UIDs to recover.")

    # 2. Scan ICS file
    print(f"Scanning original file: {ics_file}")
    vtimezones, found_events = parse_ics_for_uids(ics_file, target_uids)

    print(f"Found {len(found_events)} matching events in the ICS file.")

    if not found_events:
        print("ERROR: No matching events found despite UIDs being present.")
        print("There may be a parsing issue. Check the file manually.")
        sys.exit(1)

    # 3. Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 4. Write individual files
    written = 0
    for uid, event_lines in found_events.items():
        filename = f"failed_{uid}.ics"
        filepath = os.path.join(output_dir, filename)
        write_single_event(filepath, event_lines, vtimezones)
        written += 1
        print(f"  -> {filename}")

    # 5. Report missing
    missing = target_uids - set(found_events.keys())
    if missing:
        print(f"\nWARNING: {len(missing)} UIDs from the log were NOT found:")
        for m in sorted(missing):
            print(f"   - {m}")

    print(f"\nDone! {written} files created in '{output_dir}'.")
    print("Try importing these one by one into Proton Calendar.")


if __name__ == "__main__":
    main()
