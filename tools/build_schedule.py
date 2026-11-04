"""Merge the official timetable with TDX into data/schedule-nw26.txt and write data/audit-sources.json.

    python3 tools/build_schedule.py

The official PDF (Issue 1, dated 2026/10/20) is the backbone. TDX is newer and agrees with what the airports
display, so day by day:
  - a flight in both takes its times from TDX;
  - a flight only in TDX is added and marked ex=1 when the PDF does not list that flight on that date;
  - a flight only in the PDF is dropped when TDX covers that leg on both sides of the date (TDX has taken it
    off), and kept otherwise, because TDX loads Kaohsiung, Songshan and Taichung only to 2027/1/3;
  - a date TDX does not cover keeps the PDF row, with the times TDX shows for that row on the same weekday.
The dated flights are then folded back into one line per flight, timing and aircraft.
"""
import collections, datetime as dt, json, re
from schedule import ROOT, SCHEDULE, SEASON, kind, parse

S0, S1 = dt.date.fromisoformat(SEASON[0]), dt.date.fromisoformat(SEASON[1])
ONE = dt.timedelta(days=1)
# CI 9800–9807 are Philippine Airlines per the PDF's footnote, but TDX adds 9802/9803, which it does not list
OP_RANGE = {"CI9802": "PR", "CI9803": "PR"}
# TDX has no aircraft types; these come from Taoyuan's published flights. Other TDX-only flights stay unknown.
AC_SEEN = {"CI7528": "32Q", "CI7529": "32Q"}
# CI54 flies Auckland–Brisbane–Taipei; on those days TDX gives the Brisbane arrival (21:25) as the departure.
# The PDF's 23:10 is right: it leaves about 1h45 later and its flying time matches the other days.
KEEP_PDF_DEP = {("CI54", "BNE", "TPE")}


def split_time(arr):
    m = re.fullmatch(r"(\d\d:\d\d)(?:\+(\d))?", arr)
    return m.group(1), int(m.group(2) or 0)


def load_pdf():
    doc = json.loads((ROOT / "data" / "timetable-pdf.json").read_text(encoding="utf-8"))
    cancelled = {tuple(k.split("-")): set(v) for k, v in doc["cancelled"].items()}
    out = {}
    for r in doc["rows"]:
        spans = [(dt.date.fromisoformat(a), dt.date.fromisoformat(b)) for a, b in r["ranges"]] or [(S0, S1)]
        for a, b in spans:
            for n in range((b - a).days + 1):
                day = a + n * ONE
                if str(day.isoweekday()) not in r["days"]: continue
                if day.isoformat() in cancelled.get((r["no"], r["o"], r["d"]), ()): continue
                out[day, r["no"], r["o"], r["d"]] = r
    return doc, out


def load_tdx():
    doc = json.loads((ROOT / "data" / "tdx-snapshot.json").read_text(encoding="utf-8"))
    out = {}
    for no, op, o, d, dep, arr, start, end, days in doc["rows"]:
        a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        for n in range((b - a).days + 1):
            day = a + n * ONE
            if S0 <= day <= S1 and str(day.isoweekday()) in days:
                out[day, no, o, d] = (dep, arr, op)
    return doc, out


def fold(dates):
    """Dates → [(weekdays, from, to, skip, only)], one entry per line, with the shortest description.
    A long gap starts a new line: the daylight-saving timings run in October and again in March."""
    dates = sorted(dates)
    if len(dates) <= 6:
        wds = {d.isoweekday() for d in dates}
        a, b = dates[0], dates[-1]
        full = [a + n * ONE for n in range((b - a).days + 1) if (a + n * ONE).isoweekday() in wds]
        if len(full) != len(dates): return [(wds, None, None, [], dates)]
    runs, cur = [], [dates[0]]
    for d in dates[1:]:
        if (d - cur[-1]).days > 21: runs.append(cur); cur = []
        cur.append(d)
    runs.append(cur)
    out = []
    for run in runs:
        wds = {d.isoweekday() for d in run}
        a, b = run[0], run[-1]
        full = [a + n * ONE for n in range((b - a).days + 1) if (a + n * ONE).isoweekday() in wds]
        skip = sorted(set(full) - set(run))
        if len(skip) >= len(run): out.append((wds, None, None, [], run)); continue
        # a bound is only needed if the flight would otherwise run on more days of the season
        before = any((S0 + n * ONE).isoweekday() in wds for n in range((a - S0).days))
        after = any((b + (n + 1) * ONE).isoweekday() in wds for n in range((S1 - b).days))
        out.append((wds, a if before else None, b if after else None, skip, []))
    return out


def load_eqv():
    out = {}
    for line in (ROOT / "data" / "aircraft-eqv.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].split()
        if len(line) == 2: out[line[0]] = line[1]
    return out


def main():
    pdf_doc, pdf = load_pdf()
    tdx_doc, tdx = load_tdx()
    today = dt.date.fromisoformat(tdx_doc["fetched"])
    eqv = load_eqv()

    span = {}   # TDX's first and last date for each leg, today onward
    for day, no, o, d in tdx:
        if day < today: continue
        a, b = span.get((no, o, d), (day, day))
        span[no, o, d] = (min(a, day), max(b, day))
    pdf_legs = {k[1:] for k in pdf}

    # the times TDX gives a PDF row, by weekday, for the dates TDX does not cover
    votes = collections.defaultdict(collections.Counter)
    for key, r in pdf.items():
        t = tdx.get(key)
        if t:
            dep = r["dep"] if key[1:] in KEEP_PDF_DEP else t[0]
            votes[key[1], key[2], key[3], r["dep"], r["arr"], key[0].isoweekday()][dep, t[1]] += 1

    def mapped(key, r):
        c = votes.get((key[1], key[2], key[3], r["dep"], r["arr"], key[0].isoweekday()))
        return c.most_common(1)[0][0] if c else (r["dep"], r["arr"])

    final, dropped, added = {}, [], []
    for key, r in pdf.items():
        day, no, o, d = key
        t = tdx.get(key)
        if t:
            dep = r["dep"] if (no, o, d) in KEEP_PDF_DEP else t[0]
            final[key] = (dep, t[1], r["ac"], r["op"], False)
        else:
            sp = span.get((no, o, d))
            if sp and day >= today and sp[0] <= day <= sp[1]:
                dropped.append((no, o, d, day)); continue
            dep, arr = mapped(key, r)
            final[key] = (dep, arr, r["ac"], r["op"], False)
    ac_of = {(r["no"], r["o"], r["d"]): r["ac"] for r in pdf.values()}
    op_of = {(r["no"], r["o"], r["d"]): r["op"] for r in pdf.values()}
    for key, t in tdx.items():
        if key in pdf: continue
        day, no, o, d = key
        added.append((no, o, d, day, t[0], t[1]))
        ac = ac_of.get((no, o, d)) or AC_SEEN.get(no, "EQV")
        final[key] = (t[0], t[1], ac, t[2] or op_of.get((no, o, d)) or OP_RANGE.get(no), True)

    # fold
    groups = collections.defaultdict(list)
    for (day, no, o, d), (dep, arr, ac, op, ex) in final.items():
        groups[no, o, d, dep, arr, ac, op, ex].append(day)

    lines = []
    for (no, o, d, dep, arr, ac, op, ex), dates in groups.items():
        hhmm, plus = split_time(arr)
        if ac == "EQV" and no in eqv: ac = eqv[no]
        for wds, a, b, skip, only in fold(dates):
            days = "D" if len(wds) == 7 else "".join(str(x) for x in sorted(wds))
            opts = []
            if a: opts.append(f"from={a}")
            if b: opts.append(f"to={b}")
            if skip: opts.append("skip=" + ",".join(map(str, skip)))
            if only: opts.append("only=" + ",".join(map(str, only)))
            if op: opts.append(f"op={op}")
            if ex: opts.append("ex=1")
            first = min(only) if only else (a or min(dates))
            lines.append(((int(no[2:]), no, o, dep, first),
                          f"{no:7}{o} {dep}  {d} {hhmm}{'+' + str(plus) if plus else '':3} {days:8}{ac:12}{' '.join(opts)}".rstrip()))
    lines.sort()

    head = f"""# 中華航空國際線班表 · 2026/27 冬季（2026/10/25–2027/3/27）
# 由 tools/build_schedule.py 產生，請勿手動修改；手動補充的航班寫在 data/extra-flights.txt。
#
# 每行一個航段：航班  出發機場 表定起飛  抵達機場 表定抵達[+天數]  星期  機型  [選項]
#   時間皆為當地時間；+1、+2 表示抵達日為起飛日（出發地日期）後一、二天
#   星期：D＝每日；數字為行駛星期（1＝週一 … 7＝週日），以出發地日期計
#   選項：from=/to= 只在該期間行駛；skip= 該日停飛；only= 只在這些日期行駛
#         op= 實際執飛的航班（CI 8xxx、CI 9xxx、AE 5xxx 為他航執飛的共掛班號）
#         ex=1 這個日期的航班不在官方時刻表上，是機場端公布的
# 同一航班依星期或期間有不同時刻時分行記錄；CI53、CI54 經停布里斯本，分成兩個航段。
#
# 來源：中華航空電子班表（Issue 1，2026/10/20）、TDX 國際定期航班（{tdx_doc['fetched']} 抓取）。
"""
    extra = (ROOT / "data" / "extra-flights.txt").read_text(encoding="utf-8")
    extra_lines = [re.sub(r"\s+only=", "  ex=1 only=", l) for l in extra.splitlines() if l.strip() and not l.startswith("#")]
    SCHEDULE.write_text(head + "\n" + "\n".join(l for _, l in lines) + "\n\n# 只見於機場公布資料（data/extra-flights.txt）\n" + "\n".join(extra_lines) + "\n", encoding="utf-8")

    # what the two sources disagree on, for the audit
    gather = collections.defaultdict(list)
    for no, o, d, day, dep, arr in added: gather[no, o, d, dep, arr].append(day.isoformat())
    in_pdf = [dict(no=k[0], o=k[1], d=k[2], dep=k[3], arr=k[4], dates=sorted(v), known=(k[0], k[1], k[2]) in pdf_legs) for k, v in sorted(gather.items(), key=lambda kv: (int(kv[0][0][2:]), kv[0][1], kv[0][3]))]
    gather = collections.defaultdict(list)
    for no, o, d, day in dropped: gather[no, o, d].append(day.isoformat())
    off = [dict(no=k[0], o=k[1], d=k[2], dates=sorted(v)) for k, v in sorted(gather.items(), key=lambda kv: int(kv[0][0][2:]))]
    no_tdx = sorted({k[1:] for k in pdf if k[1:] not in span and k[0] >= today}, key=lambda k: (int(k[0][2:]), k[1]))
    moved = collections.defaultdict(list)
    for key, r in pdf.items():
        t = tdx.get(key)
        if t and key[0] >= today and (t[0], t[1]) != (r["dep"], r["arr"]) and not r["op"] and key[1:] not in KEEP_PDF_DEP:
            moved[key[1], key[2], key[3], f"{r['dep']}-{r['arr']}", f"{t[0]}-{t[1]}"].append(key[0].isoformat())
    time_diffs = [dict(no=k[0], o=k[1], d=k[2], pdf=k[3], tdx=k[4], n=len(v), first=min(v), last=max(v)) for k, v in sorted(moved.items(), key=lambda kv: (int(kv[0][0][2:]), kv[0][3]))]
    last = {}
    for day, no, o, d in tdx:
        for ap in (o, d):
            if ap in ("TPE", "TSA", "KHH", "RMQ"): last[ap] = max(last.get(ap, day), day)
    out = dict(pdf=dict(issue=pdf_doc["issue"], created=pdf_doc["created"], valid=pdf_doc["valid"], rows=len(pdf_doc["rows"]), flight_days=len(pdf)),
               tdx=dict(fetched=tdx_doc["fetched"], rows=len(tdx_doc["rows"]), flight_days=len(tdx), last={k: v.isoformat() for k, v in last.items()}),
               not_in_pdf=in_pdf, tdx_removed=off, not_in_tdx=[dict(no=k[0], o=k[1], d=k[2]) for k in no_tdx], time_diffs=time_diffs,
               cancelled=pdf_doc["cancelled"])
    (ROOT / "data" / "audit-sources.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    segs = parse()
    print(f"{len(segs)} lines; {len(final)} dated flights; PDF only and dropped: {len(dropped)}; TDX only and added: {len(added)}; "
          f"time differences: {len(time_diffs)} rows")
    print("kinds:", dict(collections.Counter(s['kind'] for s in segs)))


if __name__ == "__main__":
    main()
