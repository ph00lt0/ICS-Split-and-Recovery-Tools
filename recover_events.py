#!/usr/bin/env python3
"""
Extract every VEVENT from a large ICS file into individual .ics files.
This helps isolate corrupted recurring events for manual recovery.
"""

import sys
import os
import re
from pathlib import Path

def parse_ics_for_recovery(filepath):
    """
    Parse ICS file to extract:
    1. Global VTIMEZONE blocks (needed for correct date rendering)
    2. Individual VEVENT blocks
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    
    vtimezones = []
    events = []
    
    current_type = None
    sub_depth = 0
    current_lines = []
    
    # Regex to extract UID for naming
    uid_pattern = re.compile(r'UID:(.*)')

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
                    elif current_type == "VEVENT":
                        events.append(current_lines[:])
                    
                    current_type = None
                    current_lines = []
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
            # Ignore other components like VTODO for now, or add them if needed

        elif stripped == "END:VCALENDAR":
            # End of file
            pass
        else:
            # Skip global header lines, we will rebuild them
            pass

    return vtimezones, events

def sanitize_filename(uid):
    """Create a safe filename from a UID."""
    # Remove special characters that might break filenames on some OS
    safe_uid = re.sub(r'[^\w\-]', '_', uid)
    return f"recovered_{safe_uid}.ics"

def write_single_event(filepath, event_lines, vtimezones):
    """Write a single event with necessary VTIMEZONE blocks."""
    with open(filepath, "w", encoding="utf-8") as f:
        # Write minimal header
        f.write("BEGIN:VCALENDAR\r\n")
        f.write("VERSION:2.0\r\n")
        f.write("PRODID:-//Recovery Script//EN\r\n")
        
        # Write all VTIMEZONE blocks found in original file
        # This ensures dates are interpreted correctly
        for tz_lines in vtimezones:
            f.writelines(tz_lines)
            
        # Write the single event
        f.writelines(event_lines)
        
        # Write footer
        f.write("END:VCALENDAR\r\n")

def recover_events(input_file, output_dir):
    print(f"Scanning {input_file}...")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    vtimezones, events = parse_ics_for_recovery(input_file)
    
    if not events:
        print("No VEVENTs found in the file.")
        return

    print(f"Found {len(events)} events. Extracting to individual files...")
    
    success_count = 0
    for i, event_lines in enumerate(events):
        # Try to find UID for naming
        uid = "unknown"
        for line in event_lines:
            if line.strip().startswith("UID:"):
                uid = line.strip().split(":", 1)[1]
                break
        
        filename = sanitize_filename(uid)
        filepath = os.path.join(output_dir, filename)
        
        # Avoid overwriting if duplicate UIDs exist (rare but possible in bad exports)
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filename)
            filepath = os.path.join(output_dir, f"{base}_{i}{ext}")

        write_single_event(filepath, event_lines, vtimezones)
        success_count += 1
        
        # Optional: Print progress every 100 events
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(events)}...")

    print(f"\nDone! Recovered {success_count} events into '{output_dir}'.")
    print("You can now try importing these files one by one into Proton.")
    print("Note: If an event was 'broken' (missing master), it might still fail,")
    print("but at least you have the isolated data to inspect or fix manually.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.ics [output_directory]")
        print("  Example: python3 recover_events.py personal.ics recovered_events")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "recovered_events"

    recover_events(input_file, output_dir)