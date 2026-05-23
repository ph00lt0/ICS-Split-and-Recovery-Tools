#!/usr/bin/env python3
"""
Extract failed events AND their master/related events from the original ICS file.
Handles recurring events where exceptions need their master event to import correctly.
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
    """Unfold ICS line continuations."""
    return re.sub(r'\r?\n[ \t]', '', content)


def extract_all_events_by_uid(filepath, target_uids):
    """
    For each target UID, find ALL events with that UID:
    - The master event (has RRULE, no RECURRENCE-ID)
    - Exception instances (have RECURRENCE-ID)
    They all share the same UID and must be bundled together.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = unfold_ics(content)

    # Collect VTIMEZONE blocks
    vtimezones = []
    tz_pattern = re.compile(r'(BEGIN:VTIMEZONE.*?END:VTIMEZONE)', re.DOTALL | re.IGNORECASE)
    for tz_match in tz_pattern.finditer(content):
        vtimezones.append(tz_match.group(1))

    # Find ALL VEVENT blocks and group by UID
    event_pattern = re.compile(r'(BEGIN:VEVENT.*?END:VEVENT)', re.DOTALL | re.IGNORECASE)

    # uid -> list of event blocks
    events_by_uid = {}

    for event_match in event_pattern.finditer(content):
        event_block = event_match.group(1)

        uid_match = re.search(r'UID:([^\r\n]+)', event_block, re.IGNORECASE)
        if uid_match:
            uid_val = uid_match.group(1).strip().upper().replace('URN:UUID:', '')

            if uid_val not in events_by_uid:
                events_by_uid[uid_val] = []
            events_by_uid[uid_val].append(event_block)

    # Now collect: for each target UID, grab all events with that UID
    matching_groups = {}  # uid -> list of event blocks
    found_count = 0

    for uid in target_uids:
        if uid in events_by_uid:
            matching_groups[uid] = events_by_uid[uid]
            found_count += 1

    return vtimezones, matching_groups


def classify_events(event_blocks):
    """Classify events as master or exception for reporting."""
    masters = []
    exceptions = []
    for block in event_blocks:
        if re.search(r'RECURRENCE-ID', block, re.IGNORECASE):
            exceptions.append(block)
        else:
            masters.append(block)
    return masters, exceptions


def write_event_group(filepath, event_blocks, vtimezones):
    """Write a valid ICS file with all events for a UID (master + exceptions)."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("BEGIN:VCALENDAR\r\n")
        f.write("VERSION:2.0\r\n")
        f.write("PRODID:-//Recovery Script//EN\r\n")

        for tz_block in vtimezones:
            f.write(tz_block)
            f.write("\r\n")

        for block in event_blocks:
            f.write(block)
            f.write("\r\n")

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
    vtimezones, matching_groups = extract_all_events_by_uid(ics_file, target_uids)

    print(f"Found {len(matching_groups)} UIDs with matching events.")

    if not matching_groups:
        print("ERROR: No matching events found.")
        sys.exit(1)

    # 3. Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 4. Write files
    written = 0
    for uid, event_blocks in matching_groups.items():
        masters, exceptions = classify_events(event_blocks)

        filename = f"failed_{uid}.ics"
        filepath = os.path.join(output_dir, filename)
        write_event_group(filepath, event_blocks, vtimezones)
        written += 1

        label_parts = []
        if masters:
            label_parts.append(f"{len(masters)} master")
        if exceptions:
            label_parts.append(f"{len(exceptions)} exception(s)")
        label = ", ".join(label_parts)

        print(f"  -> {filename} ({label})")

    # 5. Report missing
    missing = target_uids - set(matching_groups.keys())
    if missing:
        print(f"\nWARNING: {len(missing)} UIDs from the log were NOT found in the ICS file:")
        for m in sorted(missing):
            print(f"   - {m}")
        print("These events may be completely missing from your export.")

    print(f"\nDone! {written} files created in '{output_dir}/'.")
    print("Each file contains the master event + all its exceptions together.")
    print("Try importing these into Proton Calendar.")


if __name__ == "__main__":
    main()