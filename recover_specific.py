#!/usr/bin/env python3
"""
Extract ONLY the specific events listed in an error log from the original ICS file.
"""

import sys
import os
import re
from pathlib import Path

def extract_uids_from_log(log_content):
    """
    Parses the error log text to find UIDs.
    Looks for patterns like "Afspraak <UUID>:" or "Element <UUID>:"
    """
    # Regex to capture UUIDs (8-4-4-4-12 hex format)
    uuid_pattern = re.compile(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', re.IGNORECASE)
    
    uids = set()
    for match in uuid_pattern.finditer(log_content):
        uids.add(match.group(1).upper()) # Normalize to uppercase for comparison
    
    return uids

def parse_ics_for_uids(filepath, target_uids):
    """
    Scans the ICS file and returns events that match the target UIDs.
    Also collects VTIMEZONE blocks needed for valid ICS.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    
    vtimezones = []
    matching_events = {} # Map UID -> event lines
    
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
                    elif current_type == "VEVENT" and current_uid:
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
            elif comp_name == "VEVENT":
                current_type = "VEVENT"
                current_lines = [line]
                sub_depth = 0
                current_uid = None # Reset UID for new event

        elif current_type == "VEVENT" and stripped.startswith("UID:"):
            # Extract UID from the line "UID:something"
            uid_val = stripped.split(":", 1)[1].strip()
            current_uid = uid_val.upper()

        elif stripped == "END:VCALENDAR":
            pass

    return vtimezones, matching_events

def sanitize_filename(uid):
    """Create a safe filename."""
    return f"recovered_{uid}.ics"

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
        print("Usage: python3 recover_specific.py <error_log.txt> <original_file.ics> [output_dir]")
        print("Example: python3 recover_specific.py errors.txt personal.ics recovered_fixes")
        sys.exit(1)

    log_file = sys.argv[1]
    ics_file = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "recovered_fixes"

    # 1. Read the error log
    print(f"Reading error log: {log_file}")
    with open(log_file, "r", encoding="utf-8") as f:
        log_content = f.read()

    target_uids = extract_uids_from_log(log_content)
    
    if not target_uids:
        print("ERROR: No UIDs found in the log file. Check the format.")
        sys.exit(1)

    print(f"Found {len(target_uids)} unique failing UIDs to recover.")

    # 2. Scan the original ICS
    print(f"Scanning original file: {ics_file}")
    vtimezones, found_events = parse_ics_for_uids(ics_file, target_uids)

    if not found_events:
        print("WARNING: None of the failing UIDs were found in the original ICS file.")
        print("They might have been deleted or the UIDs in the log are different.")
        sys.exit(1)

    print(f"Found {len(found_events)} matching events in the original file.")

    # 3. Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 4. Write files
    written_count = 0
    for uid, event_lines in found_events.items():
        filename = sanitize_filename(uid)
        filepath = os.path.join(output_dir, filename)
        write_single_event(filepath, event_lines, vtimezones)
        written_count += 1
        print(f"  -> Created {filename}")

    # Report missing ones
    missing = target_uids - set(found_events.keys())
    if missing:
        print(f"\nWARNING: The following UIDs were in the log but NOT found in the ICS file:")
        for m in missing:
            print(f"   - {m}")
        print("These events might be completely missing from your export.")

    print(f"\nDone! {written_count} files created in '{output_dir}'.")
    print("You can now try importing these specific files into Proton.")

if __name__ == "__main__":
    main()