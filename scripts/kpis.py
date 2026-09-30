"""Generate the profile KPI card (light + dark SVG) from the GitHub contribution calendar."""

import json
import os
import urllib.request
from collections import OrderedDict
from datetime import date
from pathlib import Path

USER = os.environ.get("GH_USER", "n-pizzetta")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path(__file__).resolve().parent.parent / "assets"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

THEMES = {
    "light": dict(bg="#f6f8fa", border="#d0d7de", ink="#1f2328", muted="#59636e", grid="#d0d7de", bar="#1a7f37"),
    "dark": dict(bg="#161b22", border="#30363d", ink="#e6edf3", muted="#9198a1", grid="#30363d", bar="#3fb950"),
}
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
W, H = 840, 290


def fetch_calendar():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def compute(cal):
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]][-52:]
    months = OrderedDict()
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["contributionCount"]
    return {
        "total": cal["totalContributions"],
        "last90": sum(d["contributionCount"] for d in days[-90:]),
        "active_weeks": sum(1 for w in weeks if w),
        "n_weeks": len(weeks),
        "best_day": max(d["contributionCount"] for d in days),
        "months": list(months.items())[-12:],
    }


def fmt(n):
    return f"{n:,}"


def render(k, t):
    stats = [
        (fmt(k["total"]), "contributions", "last 12 months"),
        (fmt(k["last90"]), "contributions", "last 90 days"),
        (f"{k['active_weeks']}/{k['n_weeks']}", "active weeks", "last 12 months"),
        (fmt(k["best_day"]), "best day", "contributions"),
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="{FONT}" role="img" aria-label="GitHub activity: {fmt(k["total"])} contributions in the last 12 months">',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="{t["bg"]}" stroke="{t["border"]}"/>',
    ]

    col = (W - 48) / len(stats)
    for i, (value, label, sub) in enumerate(stats):
        x = 24 + i * col
        out.append(f'<text x="{x:.0f}" y="58" font-size="30" font-weight="600" fill="{t["ink"]}">{value}</text>')
        out.append(f'<text x="{x:.0f}" y="82" font-size="13" fill="{t["ink"]}">{label}</text>')
        out.append(f'<text x="{x:.0f}" y="100" font-size="12" fill="{t["muted"]}">{sub}</text>')

    # Monthly contributions, one bar per month, baseline-anchored.
    top, base = 140, 250
    out.append(f'<text x="24" y="{top - 12}" font-size="12" fill="{t["muted"]}">Contributions per month</text>')
    out.append(f'<line x1="24" y1="{base + 0.5}" x2="{W - 24}" y2="{base + 0.5}" stroke="{t["grid"]}"/>')
    months = k["months"]
    peak = max(v for _, v in months) or 1
    slot = (W - 48) / len(months)
    bw = slot - 12
    for i, (m, v) in enumerate(months):
        x = 24 + i * slot + 6
        h = max((v / peak) * (base - top - 16), 2 if v else 0)
        if h:
            # Rounded top, square bottom on the baseline.
            r = min(4, bw / 2, h)
            y = base - h
            out.append(
                f'<path d="M{x:.1f},{base} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
                f'H{x + bw - r:.1f} Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + r:.1f} V{base} Z" fill="{t["bar"]}">'
                f"<title>{m}: {fmt(v)}</title></path>"
            )
        if v == peak or i == len(months) - 1:
            out.append(
                f'<text x="{x + bw / 2:.1f}" y="{base - h - 6:.1f}" font-size="12" text-anchor="middle" '
                f'fill="{t["ink"]}">{fmt(v)}</text>'
            )
        label = date.fromisoformat(m + "-01").strftime("%b")
        out.append(
            f'<text x="{x + bw / 2:.1f}" y="{base + 18}" font-size="11" text-anchor="middle" fill="{t["muted"]}">{label}</text>'
        )

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    k = compute(fetch_calendar())
    OUT.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f"kpis-{name}.svg").write_text(render(k, theme))
    print(json.dumps({key: val for key, val in k.items() if key != "months"}))


if __name__ == "__main__":
    main()
