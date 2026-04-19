---
name: delete-entry
description: Delete a single date's entry from the weight tracker CSV on Google Drive. Use when the user asks to remove, delete, or undo a specific day's log entry.
---

# Delete Weight Entry

Runs `scripts/delete_entry.py` to remove one date's row from the Drive CSV.

## Usage

Expect the user to provide a date in `YYYY-MM-DD` form. If they say "today" or similar, convert using `currentDate` from session context.

Run:

```bash
python scripts/delete_entry.py <YYYY-MM-DD>
```

The script is interactive: it shows the matching row and asks `[y/N]` before writing back. Do not pipe input — let the user confirm directly in the terminal.

## After the script succeeds

Remind the user:

> The running Streamlit app caches Drive reads for 5 minutes. Click **Refresh Data** in the sidebar to see the deletion immediately.

## Error handling

- Exit 1 → no row for that date (not an error, just nothing to delete).
- Exit 2 → invalid date format.
- Any other non-zero → Drive API or auth problem; surface the stderr to the user.
