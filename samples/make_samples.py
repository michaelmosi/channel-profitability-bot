"""Regenerates deterministic sample data. As-of date: 2026-11-30.

Planted channels (spend over Sep to Nov 2026, new users, revenue per user per month):
  podcast             moderate spend, few users, high revenue  -> strong LTV:CAC
  finance_influencers moderate spend, more users, modest revenue -> thin but profitable
  instagram_ads       high spend, many users, tiny revenue      -> LTV below CAC
  referral            no spend, high revenue, growing           -> free channel
"""
import csv
import datetime
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
AS_OF = datetime.date(2026, 11, 30)
rng = random.Random(11)

# channel: (monthly spend, users per month, active share, monthly revenue per paying user)
PLAN = {
    "podcast": (600.0, 12, 0.9, 40.0),
    "finance_influencers": (900.0, 30, 0.6, 9.0),
    "instagram_ads": (1500.0, 60, 0.35, 3.0),
    "referral": (0.0, 25, 0.8, 22.0),
}

spend_rows, users, revenue = [], [], []
uid = 0
for month in (9, 10, 11):
    for ch, (spend, per_month, _, _) in PLAN.items():
        spend_rows.append([f"2026-{month:02d}", ch, spend])

for ch, (spend, per_month, active, rev) in PLAN.items():
    for month in (9, 10, 11):
        for _ in range(per_month):
            uid += 1
            signup = datetime.date(2026, month, rng.randint(1, 27))
            users.append([f"u{uid:04d}", signup.isoformat(), ch])
            if rng.random() < active:
                # revenue every month from signup to the as-of date
                m = signup.month
                while m <= 11:
                    boost = 1.6 if (ch == "referral" and m == 11) else 1.0   # referral grows in November
                    when = datetime.date(2026, m, min(28, max(signup.day, 1))) if m > signup.month else signup
                    if when <= AS_OF:
                        revenue.append([f"u{uid:04d}", when.isoformat(), round(rev * boost * rng.uniform(0.8, 1.2), 2)])
                    m += 1

for name, header, rows in (("spend.sample.csv", ["month", "channel", "spend"], spend_rows),
                           ("users.sample.csv", ["user_id", "signup_date", "channel"], users),
                           ("revenue.sample.csv", ["user_id", "date", "revenue"], revenue)):
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows)
print(len(users), "users,", len(revenue), "revenue rows")
