"""Download the week-by-week international schedule from TDX into data/tdx-snapshot.json.

    TDX_TOKEN=... python3 tools/fetch_tdx.py        # token from a TDX account
    python3 tools/fetch_tdx.py ci.json ae.json cs.json     # or from responses already saved, one per query

Without a token TDX answers a few queries a day, then "401 Valid API Key Required". A flight flown by a
partner under a CI or AE number is filed either under CI/AE (Taoyuan) or under the partner with a code-share
entry (Songshan, Kaohsiung); the second form is kept here under its CI/AE number, with the partner's flight in op.
"""
import datetime as dt, json, os, pathlib, re, sys, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://tdx.transportdata.tw/api/basic/v2/Air/GeneralSchedule/International?"
QUERIES = ["AirlineID eq 'CI'", "AirlineID eq 'AE'", "CodeShare/any(c: c/AirlineID eq 'CI' or c/AirlineID eq 'AE')"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get(flt):
    url = BASE + urllib.parse.urlencode({"$filter": flt, "$format": "JSON"})
    headers = {"User-Agent": "ci-live timetable audit"}
    if os.environ.get("TDX_TOKEN"): headers["Authorization"] = "Bearer " + os.environ["TDX_TOKEN"]
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120).read())


def short(no):
    return re.sub(r"^([A-Z0-9]{2})0*", r"\1", no)


def main(files):
    rows, seen = [], set()
    for response in ([json.loads(pathlib.Path(f).read_text(encoding="utf-8")) for f in files] or [get(q) for q in QUERIES]):
        for r in response:
            days ="".join(str(i + 1) for i, d in enumerate(DAYS) if r[d])
            airline = r["AirlineID"]
            if airline in ("CI", "AE"):
                ids = [(short(r["FlightNumber"]), None)]
            else:
                ids = [(c["AirlineID"] + c["FlightNumber"].lstrip("0"), short(r["FlightNumber"])) for c in r["CodeShare"] if c["AirlineID"] in ("CI", "AE")]
            for no, op in ids:
                row = [no, op, r["DepartureAirportID"], r["ArrivalAirportID"], r["DepartureTime"], r["ArrivalTime"], r["ScheduleStartDate"], r["ScheduleEndDate"], days]
                key = tuple(row)
                if key not in seen:
                    seen.add(key); rows.append(row)
    rows.sort(key=lambda r: (r[0], r[6], r[4]))
    out = dict(fetched=dt.date.today().isoformat(), fields=["no", "op", "o", "d", "dep", "arr", "start", "end", "days"], rows=rows)
    (ROOT / "data" / "tdx-snapshot.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace('],[', '],\n['), encoding="utf-8")
    print(f"{len(rows)} TDX rows, {out['fetched']}")


if __name__ == "__main__":
    main(sys.argv[1:])
