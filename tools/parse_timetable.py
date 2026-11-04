"""Parse China Airlines' official timetable PDF into data/timetable-pdf.json.

    python3 tools/parse_timetable.py CI-timetable.pdf

Needs pypdf. The PDF comes from the 電子班表 link on
https://www.china-airlines.com/tw/zh/fly/flight-status/timetable

In the extracted text a route block is a heading "<中文> <CITY>    <中文> <CITY> <flying time>" followed
by its columns one after another: flight numbers, operating days, times, aircraft, period. A block with
one flight is printed on a single line instead. The period column can wrap, so it may hold more lines
than the block has flights, or lose a trailing "-" at a column edge; assign() sorts that out from the
dates. Only routes touching Taiwan are kept: the later pages are partners' flights between foreign cities.
"""
import datetime as dt, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TW = {"TSA", "TPE", "KHH", "RMQ"}
CITY = {
    "TAIPEI SONGSHAN": "TSA", "TAIPEI TAOYUAN": "TPE", "KAOHSIUNG": "KHH", "TAICHUNG": "RMQ",
    "TOKYO HANEDA": "HND", "TOKYO NARITA": "NRT", "OSAKA KANSAI": "KIX", "SAPPORO NEW CHITOSE": "CTS", "NAGOYA": "NGO",
    "TOYAMA": "TOY", "HIROSHIMA": "HIJ", "TAKAMATSU": "TAK", "FUKUOKA": "FUK", "KUMAMOTO": "KMJ", "KAGOSHIMA": "KOJ",
    "OKINAWA": "OKA", "SEOUL GIMPO": "GMP", "SEOUL INCHEON": "ICN", "PUSAN": "PUS", "BANGKOK": "BKK", "CHIANG MAI": "CNX",
    "KUALA LUMPUR": "KUL", "PENANG": "PEN", "SINGAPORE": "SIN", "JAKARTA": "CGK", "DENPASAR BALI": "DPS",
    "HO CHI MINH CITY": "SGN", "DA NANG": "DAD", "HANOI": "HAN", "YANGON": "RGN", "PHNOM PENH KTI": "KTI",
    "KOROR PALAU": "ROR", "MANILA": "MNL", "CEBU": "CEB", "BRUNEI": "BWN", "HONG KONG": "HKG", "SHANGHAI HONGQIAO": "SHA",
    "FUZHOU": "FOC", "WUHAN": "WUH", "BEIJING CAPITAL": "PEK", "SHANGHAI PUDONG": "PVG", "GUANGZHOU": "CAN",
    "SHENZHEN": "SZX", "QINGDAO": "TAO", "CHENGDU SHUANGLIU": "CTU", "NANJING": "NKG", "NINGBO": "NGB", "XMN": "XMN",
    "XIAMEN": "XMN", "ZHENGZHOU": "CGO", "CHONGQING": "CKG", "LOS ANGELES": "LAX", "LA,ONTARIO": "ONT", "PHOENIX": "PHX",
    "SAN FRANCISCO": "SFO", "SEATTLE": "SEA", "NEW YORK JFK": "JFK", "VANCOUVER": "YVR", "SYDNEY": "SYD",
    "BRISBANE": "BNE", "AUCKLAND": "AKL", "MELBOURNE": "MEL", "FRANKFURT": "FRA", "AMSTERDAM": "AMS",
    "LONDON HEATHROW": "LHR", "VIENNA": "VIE", "PRAGUE": "PRG", "ROME": "FCO",
}
# The Brisbane–Auckland block is a two-line heading with its legs in one row; it is written out here.
TWO_LEG = [
    dict(no="CI53", op=None, o="BNE", d="AKL", days="24567", dep="12:55", arr="19:10", ac="359", ranges=[], page=9),
    dict(no="CI54", op=None, o="AKL", d="BNE", days="24567", dep="20:50", arr="21:25", ac="359", ranges=[], page=9),
]
# Printed in footnotes rather than in the period column.
CANCELLED = {
    ("CI61", "TPE", "FRA"): ["2026-12-24", "2026-12-31", "2027-01-12", "2027-01-19", "2027-01-27"],
    ("CI62", "FRA", "TPE"): ["2026-12-25", "2027-01-01", "2027-01-13", "2027-01-20", "2027-01-28"],
}
# Page 10 prints CI 2063 as days 2,6 on 08Mar27 / 13Mar27, but 8 March 2027 is a Monday and the return CI 2064
# leaves Vienna on 10Mar27 / 14Mar27, so the first date is taken to be 09Mar27.
TYPOS = [("08Mar27 / 13Mar27", "09Mar27 / 13Mar27")]

NO = r"(?:CI|AE)\s?\d{2,4}(?:\s?\([A-Z0-9]{2}\s?\d+\))?"
RE_NO = re.compile(rf"^({NO})\s*$")
RE_DAYS = re.compile(r"^[1-7 ]*[1-7][1-7 ]*$")
RE_TIME = re.compile(r"^\d\d:\d\d-\d\d:\d\d(?:\+\d)?\s*$")
RE_AC = re.compile(r"^[0-9A-Z]{3}(?:/[0-9A-Z]{3})*\s*$")
RE_PERIOD = re.compile(r"^(?:-|\d\d[A-Z][a-z]{2}\d\d.*)$")
RE_ONE = re.compile(rf"^({NO})\s*([1-7 ]*[1-7][1-7 ]*?)\s*(\d\d:\d\d-\d\d:\d\d(?:\+\d)?)\s+(\S+)\s+(-|\d\d[A-Z].*)$")
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
NAMES = sorted(CITY, key=len, reverse=True)


def heading(line):
    """(origin, destination) when the line is a route heading between two known cities."""
    latin, found, pos = re.sub(r"[^A-Z, ]+", " ", line), [], 0
    while pos < len(latin):
        for n in NAMES:
            if latin.startswith(n, pos) and (pos == 0 or not latin[pos - 1].isalpha()):
                found.append(n); pos += len(n) - 1
                break
        pos += 1
    return (CITY[found[0]], CITY[found[1]]) if len(found) >= 2 and re.search(r"\d+h", line) else None


def number(s):
    m = re.match(r"(CI|AE)\s?0*(\d+)(?:\s?\(([A-Z0-9]{2})\s?0*(\d+)\))?", s)
    return m.group(1) + m.group(2), m.group(3) + m.group(4) if m.group(3) else None


def days_of(s):
    return "".join(sorted(set(re.sub(r"\D", "", s))))


def date(s):
    return dt.date(2000 + int(s[5:7]), MON[s[2:5]], int(s[:2]))


def ranges(line):
    """A period line as [(from, to)]; "-" is the whole season."""
    line = line.strip()
    if line == "-": return []
    out = []
    for part in re.split(r"\s*/\s*", line):
        part = part.strip()
        m = re.fullmatch(r"(\d\d[A-Z][a-z]{2}\d\d)-(\d\d[A-Z][a-z]{2}\d\d)", part)
        if m: out.append((date(m.group(1)), date(m.group(2))))
        elif re.fullmatch(r"\d\d[A-Z][a-z]{2}\d\d", part): out.append((date(part), date(part)))
        else: raise ValueError("period: " + line)
    return out


def fits(days, rs):
    """Every range must hold at least one day the row operates."""
    for a, b in rs:
        if not any(str((a + dt.timedelta(n)).isoweekday()) in days for n in range((b - a).days + 1)): return False
    return True


def assign(rows, lines):
    """Share the period lines among the rows: consecutive lines per row, "-" alone, each range holds an
    operating day of its row, and a row's ranges run forward in time."""
    def rec(i, j):
        if i == len(rows): return [] if j == len(lines) else None
        for k in range(j + 1, len(lines) - (len(rows) - i - 1) + 1):
            group = lines[j:k]
            if "-" in [g.strip() for g in group] and len(group) > 1: continue
            rs = [r for g in group for r in ranges(g)]
            if rs and (not fits(rows[i], rs) or any(rs[x][0] >= rs[x + 1][0] for x in range(len(rs) - 1))): continue
            rest = rec(i + 1, k)
            if rest is not None: return [group] + rest
        return None
    out = rec(0, 0)
    if out is None: raise ValueError(f"cannot assign {lines} to {rows}")
    return out


def row(no, route, days, time, ac, group, page):
    dep, arr = time.strip().split("-")
    n, op = number(no)
    rs = [r for g in group for r in ranges(g)]
    return dict(no=n, op=op, o=route[0], d=route[1], days=days, dep=dep, arr=arr, ac=ac,
                ranges=[[a.isoformat(), b.isoformat()] for a, b in rs], page=page)


def parse(text):
    rows, page, route, i, lines = [], 0, None, 0, text.splitlines()
    while i < len(lines):
        raw, line = lines[i], lines[i].strip()
        if raw.startswith("=====PAGE"):
            page = int(re.search(r"\d+", raw).group()); i += 1; continue
        h = heading(line)
        if h:
            route = h; i += 1; continue
        if re.search(r"\d+h(\d+m)?\s*(~.*)?$", line) and re.search(r"[A-Z]{3,}", line):
            route = None; i += 1; continue   # partners' flights between cities not in CITY
        if not route:
            i += 1; continue
        one = RE_ONE.match(line)
        if one:
            period = one.group(5).strip()
            rows.append(row(one.group(1), route, days_of(one.group(2)), one.group(3), one.group(4), [period], page))
            i += 1; continue
        if not RE_NO.match(line):
            i += 1; continue
        nos, days, times, acs, pers = [], [], [], [], []
        while i < len(lines) and RE_NO.match(lines[i].strip()): nos.append(lines[i].strip()); i += 1
        while i < len(lines) and len(days) < len(nos) and RE_DAYS.match(lines[i]): days.append(days_of(lines[i])); i += 1
        while i < len(lines) and RE_TIME.match(lines[i].strip()): times.append(lines[i].strip()); i += 1
        while i < len(lines) and len(acs) < len(nos) and RE_AC.match(lines[i].strip()): acs.append(lines[i].strip()); i += 1
        while i < len(lines) and RE_PERIOD.match(lines[i].strip()): pers.append(lines[i].strip()); i += 1
        if not (len(nos) == len(days) == len(times) == len(acs)):
            if route[0] in TW or route[1] in TW: raise ValueError(f"page {page} {route}: {nos} {days} {times} {acs}")
            continue
        pers += ["-"] * (len(nos) - len(pers))
        for bad, good in TYPOS: pers = [p.replace(bad, good) for p in pers]
        try:
            groups = assign(days, pers)
        except ValueError:
            if route[0] in TW or route[1] in TW: raise
            continue   # a partner's flights abroad, not used
        rows += [row(nos[k], route, days[k], times[k], acs[k], groups[k], page) for k in range(len(nos))]
    return rows


def main(path):
    import pypdf
    reader = pypdf.PdfReader(path)
    text = "".join(f"\n=====PAGE {n + 1}=====\n{p.extract_text() or ''}" for n, p in enumerate(reader.pages))
    rows = [r for r in parse(text) if r["o"] in TW or r["d"] in TW] + TWO_LEG
    out = dict(source="https://cms-externalcontent-prod.s3.ap-northeast-1.amazonaws.com/ci/Prepare%20for%20the%20fly/CI-timetable.pdf",
               issue="Issue 1", valid=["2026-10-25", "2027-03-27"], created=str(reader.metadata.get("/CreationDate"))[2:10],
               cancelled={"-".join(k): v for k, v in CANCELLED.items()}, rows=rows)
    (ROOT / "data" / "timetable-pdf.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    kinds = {}
    for r in rows:
        k = "codeshare" if r["op"] else r["no"][:2]
        kinds[k] = kinds.get(k, 0) + 1
    print(f"{len(reader.pages)} pages, {len(rows)} rows touching Taiwan: {kinds}")


if __name__ == "__main__":
    main(sys.argv[1])
