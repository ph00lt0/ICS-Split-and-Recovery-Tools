# ICS Recovery Tools

A collection of Python scripts to help recover, split, and repair ICS (iCalendar) files, particularly useful for migrating calendars between services like Nextcloud → Proton Calendar.

## 😤 Why Does This Even Exist?

Migrating your calendar from one service to another should be simple: export an `.ics` file, import it somewhere else, done. That's literally what the iCalendar standard was designed for. But here we are.

**Proton Calendar** imposes a **10MB import limit**. If you've been using a calendar for more than a couple of years — with recurring events, exceptions, reminders, and attachments — your export will easily exceed that. A typical Nextcloud calendar export from someone who actually uses their calendar? 10–30MB without breaking a sweat. So you're stuck: you can't import your own data into a service you're paying for, and there's no official tool to help you work around it.

And it's not just Proton. Google Calendar has had similar import quirks for years — silent failures on recurring events, mysterious "unable to import" errors with no details, and a hard limit on the number of events per import. Outlook.com? Good luck getting recurring events with exceptions to survive the trip. Apple Calendar? It silently drops events it doesn't like. The whole ecosystem treats ICS import as an afterthought, despite it being the **one** standardized format we all agree on.

What's particularly frustrating is that the **export side** is often just as broken. Nextcloud's calendar exports frequently contain malformed recurrence rules, orphaned exception events (exceptions whose master event is missing or has an empty series), and `VTODO` components mixed in with `VEVENT`s. These aren't edge cases — they happen routinely with real-world calendar usage. You edit a recurring event once, move an instance, delete another, and suddenly your export contains a tangled mess of master events, overridden instances, and broken cross-references that no importer can make sense of.

So instead of just clicking "import" and moving on with your life, you end up writing Python scripts at 11pm to parse, split, extract, sanitize, and hand-hold your own calendar data across the finish line. These scripts are the result of that journey.

**TL;DR:** Calendar migration is broken. Import limits are too low. Exports are often malformed. Nobody warns you until it fails. These scripts are the duct tape.

## 📋 Overview

When importing large calendar exports (especially from Nextcloud), you may encounter:
- **File size limits** (e.g., Proton's 10MB import limit)
- **Corrupted recurring events** with missing master events
- **Malformed recurrence rules** that fail to import
- **Line folding issues** in ICS files
- **Silent failures** with no useful error messages

This toolkit provides scripts to:
1. Split large ICS files into smaller chunks
2. Extract specific failed events from error logs
3. Bundle master events with their exceptions
4. Sanitize broken recurrence rules
5. Diagnose UID matching issues

## 📁 Scripts

| Script | Purpose |
|--------|---------|
| `split_ics.py` | Split large ICS files by size (for import limits) |
| `recover_failed.py` | Extract specific failed events by UID from error log |
| `recover_events.py` | Extract all events to individual .ics files |
| `sanitize_recovered.py` | Remove broken RRULE/EXDATE from master events |
| `diagnose_uids.py` | Debug UID matching between error log and ICS file |
| `extract_recurring.py` | Extract only recurring events (with RRULE) |

## 🔧 Requirements

- Python 3.7 or higher
- No external dependencies (uses only standard library)

```bash
# No installation needed - just clone and run
git clone https://github.com/yourusername/ics-recovery-tools.git
cd ics-recovery-tools
```

## 🚀 Usage
1. Split Large ICS Files
Split a large export into chunks under a specific size limit:


python3 split_ics.py personal-2026-05-23.ics protonimport 9.0
Output: protonimport_1.ics, protonimport_2.ics, etc. (each under 9MB)

2. Extract Failed Events from Error Log
If Proton/other service gives you an error log with failed UIDs:

Save the error log to errors.txt
Run:

python3 recover_failed.py errors.txt personal-2026-05-23.ics recovered_failed
Output: Individual .ics files for each failed event, bundled with their master events

3. Sanitize Broken Recurring Events
If you get "Original recurring appointment not found" errors:


python3 sanitize_recovered.py recovered_failed
This removes problematic RRULE, EXDATE, and RELATED-TO lines from master events, allowing exceptions to import correctly.

4. Diagnose UID Matching Issues
If events aren't being found despite appearing in the error log:


python3 diagnose_uids.py errors.txt personal-2026-05-23.ics
Shows which UIDs match and which don't, helping debug parsing issues.

5. Extract All Events Individually
For manual inspection of every event:


python3 recover_events.py personal-2026-05-23.ics recovered_events
Output: One .ics file per event in the recovered_events/ directory

6. Extract Only Recurring Events
For focusing on complex recurring events:


python3 extract_recurring.py personal-2026-05-23.ics recovered_recurring
Output: Only events with RRULE or EXDATE properties

## 📖 Typical Workflow
Here's a recommended workflow for recovering failed imports:


┌─────────────────────────────────────────────────────────────┐
│  1. Export calendar from source (Nextcloud, etc.)           │
│     → personal-2026-05-23.ics                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Try importing to destination (Proton, etc.)             │
│     → Get error log with failed UIDs                        │
│     → Save as errors.txt                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Extract failed events                                   │
│     python3 recover_failed.py errors.txt personal-2026-05-23.ics recovered_failed
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Sanitize broken recurrence rules                        │
│     python3 sanitize_recovered.py recovered_failed          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Import sanitized files one by one                       │
│     → Most should succeed now                               │
└─────────────────────────────────────────────────────────────┘

## ⚠️ Common Errors & Solutions
Error Message	Cause	Solution
Oorspronkelijke terugkerende afspraak kan niet worden gevonden	Master event missing or has empty series	Run sanitize_recovered.py
Misvormde periodieke afspraak	Malformed RRULE	Manually inspect/edit the .ics file
Herhalingsvoorwaarde niet ondersteund	Unsupported recurrence syntax	Remove RRULE line to convert to single event
File too large (>10MB)	Import size limit	Use split_ics.py to chunk the file
No matching events found	UID parsing issue	Run diagnose_uids.py to debug

## 🛠️ Troubleshooting
Events still fail after sanitization?
Some events have genuinely broken data. Open the .ics file in a text editor and:

Remove the RRULE: line entirely
Remove EXDATE: lines
Remove RELATED-TO: lines
Keep RECURRENCE-ID: on exception events
Line folding issues?
The scripts automatically handle ICS line folding (long lines broken across multiple lines). If you still have issues, ensure your original file follows RFC 5545 standards.

Missing VTODO items?
Some scripts focus on VEVENT. To include VTODO (to-do items), modify the regex pattern:


#### Change this:
event_pattern = re.compile(r'(BEGIN:VEVENT.*?END:VEVENT)', ...)

#### To this:
event_pattern = re.compile(r'(BEGIN:(?:VEVENT|VTODO).*?END:(?:VEVENT|VTODO))', ...)

## 📄 License
MIT License - Feel free to use, modify, and distribute.

## 🤝 Contributing
Pull requests welcome! Especially for:

Supporting additional calendar providers
Better error message parsing
GUI interface
Additional recovery strategies


## 🙏 Credits
Built for migrating calendars from Nextcloud to Proton Calendar. Inspired by various ICS parsing libraries and RFC 5545 specification.


## Need help?
You can hire me as consultant. 
