"""Project Natural Earth 1:50m land and country borders into data/map.json.

    python3 tools/build_map.py land-50m.json countries-50m.json

Inputs are the world-atlas TopoJSON files:
  https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/land-50m.json
  https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json

Projection: Miller cylindrical centred on 143°E, so the network from London to
New York fits without crossing the map edge (the cut falls in the mid-Atlantic).
src/app.html repeats the same formula with the parameters stored in map.json.
"""
import json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LON0, LAT_TOP, LAT_BOT, W = 143.0, 78.0, -48.0, 2000.0
R = W / (2 * math.pi)
TOL = 0.3          # Douglas–Peucker tolerance in map units (1 unit ≈ 0.18° of longitude)
MIN_AREA = 0.12    # drop islands smaller than this (map units²)
TAIWAN_ID = "158"

miller = lambda lat: 1.25 * math.log(math.tan(math.pi / 4 + 0.4 * math.radians(lat)))
TOP = miller(LAT_TOP)
H = (TOP - miller(LAT_BOT)) * R


def xy(lon, lat):
    return (math.radians(lon) * R + W / 2, (TOP - miller(max(-85, min(85, lat)))) * R)


def decode_arcs(topo):
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring_coords(ring, arcs):
    out = []
    for i in ring:
        pts = arcs[i] if i >= 0 else arcs[~i][::-1]
        out.extend(pts if not out else pts[1:])
    return out


def unwrap(pts):
    """Rotate to LON0 and make longitudes continuous (may leave the ±180 range)."""
    res, prev = [], None
    for lon, lat in pts:
        l = ((lon - LON0 + 180) % 360) - 180
        if prev is not None:
            while l - prev > 180: l -= 360
            while l - prev < -180: l += 360
        res.append((l, lat)); prev = l
    return res


def copies(pts):
    """The unwrapped line plus a shifted copy for whatever spills past the map edge."""
    lo, hi = min(p[0] for p in pts), max(p[0] for p in pts)
    out = [pts]
    if hi > 180: out.append([(l - 360, a) for l, a in pts])
    if lo < -180: out.append([(l + 360, a) for l, a in pts])
    return out


def dp(pts, tol):
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1e-9
        best, idx = -1, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / L if L > 1e-9 else math.hypot(x - x1, y - y1)
            if d > best: best, idx = d, i
        if best > tol:
            keep[idx] = True; stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def path(pts, close):
    """Relative SVG path with one decimal: much smaller than absolute coordinates."""
    q = [(round(x * 10), round(y * 10)) for x, y in pts]
    s = [f"M{q[0][0] / 10:g} {q[0][1] / 10:g}"]
    px, py = q[0]; rel = []
    for x, y in q[1:]:
        if (x, y) == (px, py): continue
        rel.append(f"{(x - px) / 10:g} {(y - py) / 10:g}".replace(" -", "-"))
        px, py = x, y
    if rel: s.append("l" + " ".join(rel))
    if close: s.append("z")
    return "".join(s)


def polys(geom):
    if geom["type"] == "Polygon": return [geom["arcs"]]
    if geom["type"] == "MultiPolygon": return geom["arcs"]
    return []


def project_rings(rings, arcs):
    out = []
    for ring in rings:
        pts = ring_coords(ring, arcs)
        if max(a for _, a in pts) < LAT_BOT - 10: continue      # Antarctica
        for c in copies(unwrap(pts)):
            p = dp([xy(l, a) for l, a in c], TOL)
            if len(p) >= 4 and area(p) >= MIN_AREA: out.append(path(p, True))
    return out


def main(land_file, countries_file):
    land = json.loads(pathlib.Path(land_file).read_text())
    ctry = json.loads(pathlib.Path(countries_file).read_text())

    larcs = decode_arcs(land)
    land_d = []
    for g in land["objects"]["land"]["geometries"]:
        for poly in polys(g): land_d += project_rings(poly, larcs)

    carcs = decode_arcs(ctry)
    users, taiwan = {}, []
    for g in ctry["objects"]["countries"]["geometries"]:
        for poly in polys(g):
            for ring in poly:
                for i in ring: users.setdefault(i if i >= 0 else ~i, set()).add(g.get("id"))
            if g.get("id") == TAIWAN_ID: taiwan += project_rings(poly, carcs)
    borders = []
    for i, ids in users.items():
        if len(ids) < 2: continue
        pts = carcs[i]
        if max(a for _, a in pts) < LAT_BOT - 10: continue
        for c in copies(unwrap(pts)):
            p = dp([xy(l, a) for l, a in c], TOL)
            if len(p) >= 2: borders.append(path(p, False))

    out = {"proj": {"lon0": LON0, "R": R, "top": TOP, "w": W, "h": round(H, 1)},
           "land": "".join(land_d), "borders": "".join(borders), "taiwan": "".join(taiwan)}
    dst = ROOT / "data" / "map.json"
    dst.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{dst.relative_to(ROOT)}: {dst.stat().st_size / 1024:.0f} KB, "
          f"{len(land_d)} land rings, {len(borders)} border lines, W={W:g} H={H:.0f}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
