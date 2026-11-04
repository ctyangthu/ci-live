"""Sanity-check the timetable: block time from local times + time zones, against great-circle distance.

    python3 tools/check_schedule.py          # flags suspicious segments
    python3 tools/check_schedule.py -v       # prints every segment

A segment is flagged when its implied average speed is implausible, which catches a wrong +1/+2 or a
typo in a time. Each line is measured on its own first flying date, so the daylight-saving timings of
North American flights are judged in their own period. Eastbound transpacific flights ride the jet
stream (~930 km/h). Cross-strait flights fly set detours, so the short ones average very little:
Songshan–Fuzhou is 213 km in 1h40 (128 km/h).
"""
import datetime as dt, json, math, sys
from zoneinfo import ZoneInfo
from schedule import ROOT, SEASON, operates, parse

AP = json.loads((ROOT / "data" / "airports.json").read_text(encoding="utf-8"))["airports"]
S0 = dt.date.fromisoformat(SEASON[0])


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (AP[a][5], AP[a][6], AP[b][5], AP[b][6]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def first_day(s):
    for n in range(160):
        day = S0 + dt.timedelta(days=n)
        if operates(s, day): return day
    raise SystemExit(f"{s['no']} {s['o']}-{s['d']}: never operates")


def block(s):
    day = first_day(s)
    t = lambda hm: dt.time(*map(int, hm.split(":")))
    d0 = dt.datetime.combine(day, t(s["dep"]), ZoneInfo(AP[s["o"]][7]))
    d1 = dt.datetime.combine(day + dt.timedelta(days=s["plus"]), t(s["arr"]), ZoneInfo(AP[s["d"]][7]))
    return (d1 - d0).total_seconds() / 60


def main(verbose):
    segs, bad = parse(), 0
    for s in segs:
        for c in (s["o"], s["d"]):
            if c not in AP: raise SystemExit(f"{s['no']}: unknown airport {c}")
        mins, dist = block(s), km(s["o"], s["d"])
        v = dist / (mins / 60) if mins > 0 else 0
        strait = "cn" in (AP[s["o"]][4], AP[s["d"]][4])
        low = 100 if dist < 500 else 280 if dist < 1000 else 400 if strait else 450
        flag = not (low <= v <= 1000)
        bad += flag
        if verbose or flag:
            print(f"{'!!' if flag else '  '} {s['no']:7} {s['o']}-{s['d']}  {s['dep']}-{s['arr']}+{s['plus']}  "
                  f"{int(mins // 60):2d}h{int(mins % 60):02d}  {dist:6.0f} km  {v:4.0f} km/h")
    routes = {tuple(sorted((s["o"], s["d"]))) for s in segs}
    print(f"{len(segs)} segments, {len(routes)} routes, {bad} flagged")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main("-v" in sys.argv) else 0)
