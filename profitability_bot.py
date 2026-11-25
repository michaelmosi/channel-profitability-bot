#!/usr/bin/env python3
"""Channel profitability bot (standard library only).

Measures whether each acquisition channel makes money, using the growth-model checks:
  - CAC            = channel spend / new users from that channel
  - LTV            = revenue per user-month x margin x expected lifetime (months)
  - LTV : CAC      healthy when LTV > CAC (3 or more is the usual "scale it" bar)
  - Payback        = CAC / (revenue per user-month x margin)
  - Value growth % = (this month's value - average of the previous two months) / average of the previous two months x 100

    python profitability_bot.py spend.sample.csv users.sample.csv revenue.sample.csv --as-of 2026-11-30 --md report.md

Inputs
  spend.csv    month (YYYY-MM or YYYY-MM-DD), channel, spend
  users.csv    user_id, signup_date, channel
  revenue.csv  user_id, date, revenue   (what the business earns from the user, e.g. fees; not the amount invested)
"""
import argparse
import csv
from collections import defaultdict
from datetime import date, datetime

SCALE_RATIO = 3.0       # LTV:CAC at or above this means "scale it"
DAYS_PER_MONTH = 30.4


def parse_date(value):
    text = str(value).strip()
    if len(text) == 7:
        text += "-01"
    return datetime.strptime(text[:10], "%Y-%m-%d").date()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [{k.strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(fh)]


def month_start(d, back=0):
    y, m = d.year, d.month - back
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


# ------------------------------------------------------------------ formulas
def value_growth(current, previous_two):
    """Value Growth % = (current - avg(last 2 months)) / avg(last 2 months) x 100. None without a baseline."""
    baseline = sum(previous_two) / len(previous_two)
    return None if baseline == 0 else (current - baseline) / baseline * 100


def growth_label(growth, current):
    if growth is None:
        return "New value (no baseline)" if current > 0 else "No usage"
    if growth > 20:
        return "Growing (>20%)"
    return "Stable (0-20%)" if growth >= 0 else "Declining (<0%)"


def cac(spend, new_users):
    return spend / new_users if new_users else None


def ltv(revenue_per_user_month, margin, lifetime_months):
    return revenue_per_user_month * margin * lifetime_months


def payback_months(cac_value, revenue_per_user_month, margin):
    monthly_profit = revenue_per_user_month * margin
    return None if not cac_value or monthly_profit <= 0 else cac_value / monthly_profit


def verdict(spend, ratio):
    if spend == 0:
        return "Free channel: protect and grow it"
    if ratio is None:
        return "No users acquired: stop or fix targeting"
    if ratio >= SCALE_RATIO:
        return "Scale: LTV is at least 3x CAC"
    if ratio >= 1:
        return "Optimise: profitable but thin (LTV above CAC, under 3x)"
    return "Unprofitable: LTV is below CAC"


# ------------------------------------------------------------------ pipeline
def analyse(spend_rows, users, revenue_rows, as_of, window_months=3, margin=1.0, lifetime_months=12):
    window_start = month_start(as_of, window_months - 1)
    cur_m, m1, m2 = month_start(as_of), month_start(as_of, 1), month_start(as_of, 2)

    spend = defaultdict(float)
    for r in spend_rows:
        d = parse_date(r["month"])
        if window_start <= d <= as_of:
            spend[r["channel"]] += float(r.get("spend") or 0)

    channel_of, signup_of = {}, {}
    for u in users:
        channel_of[u["user_id"]] = u.get("channel") or "unknown"
        signup_of[u["user_id"]] = parse_date(u["signup_date"])

    acquired = defaultdict(list)       # channel -> users who signed up in the window
    for uid, d in signup_of.items():
        if window_start <= d <= as_of:
            acquired[channel_of[uid]].append(uid)

    revenue_by_user = defaultdict(list)
    for r in revenue_rows:
        d = parse_date(r["date"])
        if d <= as_of:
            revenue_by_user[r["user_id"]].append((d, float(r.get("revenue") or 0)))

    results = []
    for ch in sorted(set(spend) | set(acquired)):
        cohort = acquired.get(ch, [])
        cohort_revenue = sum(a for uid in cohort for _, a in revenue_by_user.get(uid, []))
        paying = sum(1 for uid in cohort if revenue_by_user.get(uid))
        exposure = sum(max((as_of - signup_of[uid]).days / DAYS_PER_MONTH, 1.0) for uid in cohort)
        rev_per_user_month = cohort_revenue / exposure if exposure else 0.0
        c = cac(spend[ch], len(cohort))
        lifetime_value = ltv(rev_per_user_month, margin, lifetime_months)
        ratio = (lifetime_value / c) if c else None

        # value growth for the channel's whole user base (the posted formula)
        base = [uid for uid, chn in channel_of.items() if chn == ch]

        def usage(month):
            return sum(a for uid in base for d, a in revenue_by_user.get(uid, []) if month_start(d) == month)

        cur, p1, p2 = usage(cur_m), usage(m1), usage(m2)
        growth = value_growth(cur, [p1, p2])
        results.append({
            "channel": ch, "spend": round(spend[ch], 2), "new_users": len(cohort),
            "cac": None if c is None else round(c, 2), "paying_users": paying,
            "activation_rate_pct": round(paying / len(cohort) * 100, 1) if cohort else 0.0,
            "revenue_per_user_month": round(rev_per_user_month, 2), "ltv": round(lifetime_value, 2),
            "ltv_to_cac": None if ratio is None else round(ratio, 2),
            "payback_months": None if payback_months(c, rev_per_user_month, margin) is None else round(payback_months(c, rev_per_user_month, margin), 1),
            "net_profit_to_date": round(cohort_revenue * margin - spend[ch], 2),
            "value_growth_pct": None if growth is None else round(growth, 1),
            "value_trend": growth_label(growth, cur), "verdict": verdict(spend[ch], ratio),
        })
    # paid channels first, ranked by LTV:CAC; free channels after
    results.sort(key=lambda r: (r["spend"] == 0, -(r["ltv_to_cac"] or -1)))
    return results


def fmt(v, suffix="", money=False):
    if v is None:
        return "n/a"
    return f"{v:,.2f}{suffix}" if money else f"{v}{suffix}"


def build_report(results, as_of, window_months, margin, lifetime_months):
    lines = ["# Channel profitability report",
             f"As of {as_of}. Window: last {window_months} months. Margin {margin * 100:.0f}%, expected lifetime {lifetime_months} months "
             "(change both with --margin and --lifetime-months; LTV is a projection, not an observed number).", "",
             "| Channel | Spend | New users | CAC | Activation | LTV | LTV:CAC | Payback (months) | Net profit to date | Value trend | Verdict |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        lines.append(f"| {r['channel']} | {r['spend']:,.2f} | {r['new_users']} | {fmt(r['cac'], money=True)} | {r['activation_rate_pct']}% | "
                     f"{r['ltv']:,.2f} | {fmt(r['ltv_to_cac'], 'x')} | {fmt(r['payback_months'])} | {r['net_profit_to_date']:,.2f} | "
                     f"{r['value_trend']} ({fmt(r['value_growth_pct'], '%')}) | {r['verdict']} |")
    paid = [r for r in results if r["spend"] > 0 and r["ltv_to_cac"] is not None]
    lines += ["", "## What to do", ""]
    if paid:
        best, worst = max(paid, key=lambda r: r["ltv_to_cac"]), min(paid, key=lambda r: r["ltv_to_cac"])
        lines.append(f"- Best paid channel: **{best['channel']}** at {best['ltv_to_cac']}x LTV:CAC. {best['verdict']}.")
        if worst["ltv_to_cac"] < 1:
            lines.append(f"- Fix or pause **{worst['channel']}**: it costs {worst['cac']:,.2f} to acquire a user who is worth {worst['ltv']:,.2f}.")
    declining = [r["channel"] for r in results if r["value_trend"].startswith("Declining")]
    if declining:
        lines.append("- Value is declining on: " + ", ".join(declining) + ". Look at retention before spending more there.")
    free = [r["channel"] for r in results if r["spend"] == 0]
    if free:
        lines.append("- Free channels with no spend to compare: " + ", ".join(free) + ". Their CAC is zero, so judge them on activation and value growth.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Per-channel CAC, LTV, LTV:CAC, payback and value growth.")
    ap.add_argument("spend"); ap.add_argument("users"); ap.add_argument("revenue")
    ap.add_argument("--as-of"); ap.add_argument("--window-months", type=int, default=3)
    ap.add_argument("--margin", type=float, default=1.0, help="share of revenue kept as profit, 0 to 1")
    ap.add_argument("--lifetime-months", type=float, default=12)
    ap.add_argument("--out", default="channels.csv"); ap.add_argument("--md")
    args = ap.parse_args(argv)
    as_of = parse_date(args.as_of) if args.as_of else date.today()
    results = analyse(read_csv(args.spend), read_csv(args.users), read_csv(args.revenue), as_of,
                      args.window_months, args.margin, args.lifetime_months)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0]))
        w.writeheader(); w.writerows(results)
    print(f"wrote {len(results)} channels to {args.out}")
    for r in results:
        print(f"{r['channel']:<20} CAC {fmt(r['cac'], money=True):>10}  LTV:CAC {fmt(r['ltv_to_cac'], 'x'):>7}  {r['verdict']}")
    if args.md:
        open(args.md, "w", encoding="utf-8").write(build_report(results, as_of, args.window_months, args.margin, args.lifetime_months))
        print("wrote", args.md)
    return results


if __name__ == "__main__":
    main()
