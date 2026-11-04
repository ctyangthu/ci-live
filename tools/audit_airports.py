"""Compare the timetable with what the four Taiwanese airports publish, and record the result.

    python3 tools/audit_airports.py

Live boards: Taoyuan publishes yesterday to tomorrow; Songshan, Kaohsiung and Taichung publish today.
Timetables: Kaohsiung publishes the next four weeks, Songshan a weekday table, Taichung a one-week table.
Run it on different weekdays: the boards only show the days they list. The result goes to
data/audit-airports.json, which tools/build.py puts on the 查核 tab. A flight number with a letter (CI35D) is a
delayed operation and is read as the plain number. Domestic flights are not looked at. Kaohsiung's live board
lists partners' flights under the partner's number (VN580), so code-shares are not expected on it.
"""
import datetime as dt, json, re, urllib.request
from zoneinfo import ZoneInfo
from schedule import ROOT, kind, operates, parse

UA = {"User-Agent": "Mozilla/5.0 (compatible; ci-live timetable audit)"}
AP = json.loads((ROOT / "data" / "airports.json").read_text(encoding="utf-8"))["airports"]
TSA_BOARD = "https://www.tsa.gov.tw/api/airFlyTab/Paging"
TSA_TABLE = "https://www.tsa.gov.tw/api/airWeekMonth/Paging"
WD = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def get(url, data=None):
    headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=headers)
    return urllib.request.urlopen(req, timeout=40).read()


def ours(no):
    """CI123 / AE123 from a published flight number, None for anyone else's."""
    m = re.fullmatch(r"(CI|AE)\s*0*(\d{1,4})[A-Z]?", no.strip().upper())
    return m.group(1) + m.group(2) if m else None


def hhmm(t):
    t = t.strip()
    return t[:2] + ":" + t[-2:] if ":" not in t else t[:5]


def taoyuan():
    rows = [[c.strip() for c in l.split(",")] for l in get("https://www.taoyuan-airport.com/uploads/flightx/a_flight_v4.txt").decode("big5", "replace").splitlines() if l.strip()]
    for r in rows:
        no = ours(r[2] + r[4]) if r[2] in ("CI", "AE") else None
        if no: yield "TPE", dt.date(*map(int, r[6].split("/"))), "dep" if r[1] == "D" else "arr", no, r[7][:5], r[10], r[14]


def kaohsiung(today):
    for io, name, code in (("dep", "INTDEP", "goalAirportCode"), ("arr", "INTARR", "upAirportCode")):
        for r in json.loads(get(f"https://www.kia.gov.tw/Announce/NewsArea/InstantSchedule_{name}.json").decode("utf-8-sig")):
            no = ours(r["airLineNum"])
            if no: yield "KHH", today, io, no, hhmm(r["expectTime"]), r[code], r.get("airPlaneType", "")


def songshan(today):
    for io, n, sort, other in (("dep", 1, "ExpectDepartureTime", "GoalAirportName"), ("arr", 2, "ExpectArrivalTime", "UpAirportName")):
        body = {"AirFlyLine": 1, "AirFlyIO": n, "Limit": 999, "Culture": 1, "FlightNumber": None, "AirLineCode": None, "AirportCode": None, "Sort": sort, "Order": "asc"}
        for r in json.loads(get(TSA_BOARD, body))["rows"]:
            no = ours(r["FlightNumber"])
            if no: yield "TSA", today, io, no, hhmm(r[sort]), r[other][-3:], r.get("AirPlaneType", "")


def taichung(today):
    for io, n, code, key in (("dep", 1, "goalAirportCode", "expectDepartureTime"), ("arr", 2, "upAirportCode", "expectArrivalTime")):
        for r in json.loads(get(f"https://www.tca.gov.tw/?act=fids&code=airflytab&Flyline=1&FlyIO={n}").decode("utf-8-sig"))["Data"]:
            no = ours(r["AirLineIATA"] + r["airLineNum"])
            if no: yield "RMQ", today, io, no, hhmm(r[key]), r[code], ""


def kaohsiung_table(today):
    """Next four weeks; partners' flights count when the code-share column carries a CI/AE number."""
    for r in json.loads(get("https://www.kia.gov.tw/data/flightplan.json").decode("utf-8-sig")):
        codes = [ours(r["airLineNum"])] + [ours(c) for c in (r.get("CodeShareInfo") or "").split(";")]
        codes = [c for c in codes if c and not (r["airLineNum"][:2] == "CI" and c.startswith("AE"))]
        o, d = r["upAirportCode"], r["goalAirportCode"]
        if not codes or not (o in AP and d in AP) or (AP[o][4] == "tw" and AP[d][4] == "tw"): continue
        a, b = dt.date.fromisoformat(r["ScheduleStartDate"]), dt.date.fromisoformat(r["ScheduleEndDate"])
        for n in range((b - a).days + 1):
            day = a + dt.timedelta(days=n)
            if r[WD[day.weekday()]] != "Y" or day < today: continue
            for no in codes:
                yield "KHH", day, "dep" if o == "KHH" else "arr", no, hhmm(r["expectDepartureTime" if o == "KHH" else "expectArrivalTime"].split("+")[0]), d if o == "KHH" else o, r["airPlaneType"]


def songshan_table(today):
    """A weekday table with no dates of its own: read as the coming seven days."""
    for io, n, st, sort, other in (("dep", 1, "departures", "ExpectDepartureTime", "GoalAirportName"), ("arr", 2, "arrivals", "ExpectArrivalTime", "UpAirportName")):
        body = {"Status": st, "Category": "0", "AirFlyLine": 1, "AirFlyIO": n, "Limit": 999, "Culture": 1, "FlightNumber": None, "AirLineCode": None, "AirportCode": None, "Sort": sort, "Order": "asc"}
        for r in json.loads(get(TSA_TABLE, body))["rows"]:
            no = ours(r["FlightNumber"])
            if not no: continue
            for k in range(7):
                day = today + dt.timedelta(days=k)
                if r[WD[day.weekday()]] == "Y":
                    yield "TSA", day, io, no, hhmm(r[sort]), r[other][-3:], r.get("AirPlaneType", "")


def taichung_table(today):
    """A one-week table of flight numbers. Times are not compared here: the live board covers those."""
    for io, n in (("dep", 1), ("arr", 2)):
        html = get(f"https://www.tca.gov.tw/?act=fids&code=regular_flight&airFlyIO={n}").decode("utf-8", "replace")
        for no in sorted({ours(x) for x in re.findall(r"(?:CI|AE)\s*\d{2,4}", html)}):
            yield "RMQ", today, io, no, None, None, ""


def expected(segs, airport, day, io):
    for s in segs:
        if io == "dep" and s["o"] == airport and operates(s, day):
            yield s["no"], s["dep"], s["d"]
        if io == "arr" and s["d"] == airport and operates(s, day - dt.timedelta(days=s["plus"])):
            yield s["no"], s["arr"], s["o"]


def compare(segs, title, feed, days_all=None, codeshares=True, numbers_only=False):
    seen = {}
    for airport, day, io, no, time, other, _ in feed:
        seen[airport, day, io, no] = (time, other)
    days = sorted({k[:3] for k in seen} | (days_all or set()))
    missing, extra, moved = [], [], []
    for airport, day, io in days:
        exp = {no: (t, o) for no, t, o in expected(segs, airport, day, io) if codeshares or kind(no) != "CS"}
        got = {k[3]: v for k, v in seen.items() if k[:3] == (airport, day, io)}
        tag = dict(day=day.isoformat(), airport=airport, io=io)
        missing += [dict(tag, no=n, time=got[n][0], other=got[n][1]) for n in sorted(set(got) - set(exp))]
        extra += [dict(tag, no=n, time=exp[n][0], other=exp[n][1]) for n in sorted(set(exp) - set(got))]
        if not numbers_only:
            moved += [dict(tag, no=n, published=got[n][0], ours=exp[n][0], other=got[n][1], other_ours=exp[n][1]) for n in sorted(set(got) & set(exp)) if got[n] != exp[n]]
    print(f"\n── {title}: {len(seen)} flights published ──")
    for name, rows in (("published but not in the timetable", missing), ("in the timetable but not published", extra), ("different time or airport", moved)):
        print(f"  {name}: {len(rows)}")
        for r in rows[:60]: print("    ", " ".join(str(v) for v in r.values()))
    return dict(title=title, flights=len(seen), days=sorted({d.isoformat() for _, d, _ in days}), missing=missing, extra=extra, moved=moved)


def main():
    segs, today = parse(), dt.datetime.now(ZoneInfo("Asia/Taipei")).date()
    window = {(a, today, io) for a in ("KHH", "TSA", "RMQ") for io in ("dep", "arr")}
    out = dict(checked=today.isoformat(), sources=[])
    add = lambda *a, **k: out["sources"].append(compare(segs, *a, **k))
    add("桃園機場 即時航班", taoyuan())
    add("松山機場 當日航班", songshan(today), {w for w in window if w[0] == "TSA"})
    add("松山機場 定期班表（週表）", songshan_table(today))
    add("清泉崗機場 當日航班", taichung(today), {w for w in window if w[0] == "RMQ"})
    add("清泉崗機場 定期班表（班號）", taichung_table(today), {w for w in window if w[0] == "RMQ"}, numbers_only=True)
    add("高雄機場 當日航班", kaohsiung(today), {w for w in window if w[0] == "KHH"}, codeshares=False)
    add("高雄機場 定期班表（四週）", kaohsiung_table(today))
    (ROOT / "data" / "audit-airports.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
