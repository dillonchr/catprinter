#!/usr/bin/env python3
import urllib.request
import json
import re
import sys
from datetime import datetime, timedelta

EVENT_ID = 66

def fetch_api(endpoint):
    url = f"https://tracker.gamesdonequick.com/tracker/api/v2/events/{EVENT_ID}/{endpoint}/"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def get_schedule(min_date=None, max_date=None):
    if min_date is None:
        min_date = datetime.now().astimezone()
    if max_date is None:
        max_date = min_date + timedelta(hours=24)

    runs_data = fetch_api('runs')
    runs = runs_data.get('results', [])

    try:
        interviews_data = fetch_api('interviews')
        interviews = interviews_data.get('results', [])
    except Exception:
        interviews = []

    results = []
    run_by_id = {}

    for run in runs:
        starttime_str = run.get('starttime')
        endtime_str = run.get('endtime')
        if not starttime_str or not endtime_str:
            continue

        # Parse ISO strings with support for UTC 'Z' or offset
        if starttime_str.endswith('Z'):
            starttime_str = starttime_str[:-1] + '+00:00'
        if endtime_str.endswith('Z'):
            endtime_str = endtime_str[:-1] + '+00:00'

        start = datetime.fromisoformat(starttime_str).astimezone()
        ends = datetime.fromisoformat(endtime_str).astimezone()

        # Save run for interview anchor lookup
        run_by_id[run['id']] = {
            'ends': ends,
            'order': run.get('order', 0)
        }

        done = min_date > ends
        if not done:
            is_today = max_date > start
            if is_today:
                title = run.get('display_name', '') or ''
                title = title.replace('\\n', ' ').replace('\\r', ' ')
                title = ' '.join(title.split())
                runners = ", ".join(r.get('name', '') for r in run.get('runners', []))
                results.append({
                    'type': 'run',
                    'order': run.get('order', 0),
                    'suborder': 0,
                    'start': start,
                    'title': title,
                    'runners': runners,
                    'estimate': run.get('run_time', ''),
                    'ends': ends,
                    'done': done,
                    'onsite': run.get('onsite', '')
                })

    for interview in interviews:
        anchor_run = run_by_id.get(interview.get('anchor'))
        if not anchor_run:
            continue

        start = anchor_run['ends']
        length_str = interview.get('length', '0:00:00')
        parts = length_str.split(':')
        duration = timedelta(
            hours=int(parts[0]),
            minutes=int(parts[1]),
            seconds=int(parts[2]) if len(parts) > 2 else 0
        )
        ends = start + duration

        done = min_date > ends
        if not done:
            is_today = max_date > start
            if is_today:
                title = interview.get('topic', '') or ''
                title = title.replace('\\n', ' ').replace('\\r', ' ')
                title = ' '.join(title.split())
                interviewers = ", ".join(i.get('name', '') for i in interview.get('interviewers', []))
                has_sent = any(i.get('type') == 'talent' and i.get('id') == 351 for i in interview.get('interviewers', []))
                results.append({
                    'type': 'interview',
                    'order': anchor_run['order'],
                    'suborder': interview.get('suborder', 0),
                    'start': start,
                    'title': title,
                    'runners': interviewers,
                    'estimate': length_str,
                    'ends': ends,
                    'done': done,
                    'onsite': '',
                    'hasSent': has_sent
                })

    results.sort(key=lambda x: (x['order'], x['suborder']))
    return results

def space_between(w1, w2, max_width=32):
    pad_len = max(max_width - (len(w1) + len(w2)), 0)
    return w1 + " " * pad_len + w2

def format_estimate(estimate_str):
    parts = estimate_str.split(":")
    result = ""
    if len(parts) > 0:
        try:
            val = int(parts[0])
            if val > 0:
                result = f"{val}h"
        except ValueError:
            pass
    if len(parts) > 1:
        try:
            val_min = int(parts[1])
            result = f"{result}{val_min}m"
        except ValueError:
            result = f"{result}{parts[1]}m"
    return result

def receipt_formatter(text, max_width=32):
    lines = text.split("\n")
    formatted_lines = []
    for line in lines:
        if len(line) > max_width:
            words = line.split(" ")
            if not words:
                formatted_lines.append(line)
                continue

            whole = words[0]
            for word in words[1:]:
                last_newline = whole.rfind("\n")
                if last_newline == -1:
                    line_so_far = whole
                else:
                    line_so_far = whole[last_newline + 1:]

                would_be_next_line_length = len(line_so_far) + 1 + len(word)
                if would_be_next_line_length > max_width:
                    whole = f"{whole}\n    {word}"
                else:
                    whole = f"{whole} {word}"
            formatted_lines.append(whole)
        else:
            formatted_lines.append(line)
    return "\n".join(formatted_lines)

def main():
    try:
        runs = get_schedule()
    except Exception as e:
        print(f"Error fetching GDQ schedule: {e}", file=sys.stderr)
        sys.exit(1)

    if not runs:
        # Exit silently if no runs are scheduled
        return

    now = datetime.now().astimezone()
    a_or_s = "S" if now.month > 1 else "A"

    dt_2h = now + timedelta(hours=2)
    day_str = str(dt_2h.day)
    date_str = f"{dt_2h.strftime('%a %b')} {day_str}"

    header = space_between(f"{a_or_s}GDQ {now.year}", date_str) + "\n"

    content_parts = [header]
    bonus_game_pattern = re.compile(r"Bonus Game \d")

    for item in runs:
        estimate = format_estimate(item['estimate'])

        start_time_str = f"{item['start'].hour}:{item['start'].minute:02d}"
        ends_time_str = f"{item['ends'].hour}:{item['ends'].minute:02d}"
        run_times = f"    {start_time_str} - {ends_time_str}"

        space_padding = max(32 - (len(estimate) + len(run_times)), 0)

        prefix = "(I)" if item.get('type') == 'interview' else "( )"

        if item.get('type') == 'run' and bonus_game_pattern.search(item['title']):
            run_title = "??? Bonus\n    ???"
        else:
            run_title = item['title']

        if item.get('onsite', '').upper() == 'ONLINE':
            run_title = f"[ONLINE] {run_title}"

        if item.get('hasSent'):
            run_title = f"{run_title}\n    (feat. SENT!)"

        part = (
            f"\n{prefix} {run_title}\n"
            f"{run_times}{' ' * space_padding}{estimate}\n\n"
            f"--------------------------------"
        )
        content_parts.append(part)

    full_text = "".join(content_parts)
    formatted_receipt = receipt_formatter(full_text)
    print(formatted_receipt)

if __name__ == "__main__":
    main()
