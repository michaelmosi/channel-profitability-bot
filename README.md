# Channel profitability bot

Tells you whether each acquisition channel actually makes money. For every channel it works out:

| Measure | Formula |
| --- | --- |
| **CAC** | channel spend / new users from that channel |
| **LTV** (projected) | revenue per user-month x margin x expected lifetime in months |
| **LTV : CAC** | healthy when LTV is above CAC; 3x or more is the usual "scale it" bar |
| **Payback** | CAC / (revenue per user-month x margin), in months |
| **Value growth %** | (this month's value - average of the previous two months) / average of the previous two months x 100 |

Value growth reads: above 20% growing, 0 to 20% stable, below 0 declining.

The verdict per channel is one of: *Scale*, *Optimise* (profitable but thin), *Unprofitable* (LTV below CAC), *Free channel* or *No users acquired*.

## Usage
```bash
python profitability_bot.py spend.sample.csv users.sample.csv revenue.sample.csv --as-of 2026-11-30 --md report.md
```

Options: `--window-months 3`, `--margin 1.0` (share of revenue kept as profit), `--lifetime-months 12`, `--out channels.csv`.

| File | Columns |
| --- | --- |
| spend | `month` (YYYY-MM), `channel`, `spend` |
| users | `user_id`, `signup_date`, `channel` |
| revenue | `user_id`, `date`, `revenue` (what the business earns from the user, such as fees, not the amount invested) |

## Read this before trusting a number
- **LTV is a projection.** It assumes the observed revenue per user-month continues for the lifetime you set. Use a margin and lifetime that match your business, and compare channels with the same settings.
- Channels with no spend have no CAC, so judge them on activation and value growth.
- Recent cohorts have little history, so early numbers move a lot.

## Credit
The measures follow the growth-model definitions (CAC vs LTV, channel-model fit, value extraction) from a growth-marketing framework document by Adeola Adesina. This repo is an implementation of those definitions, not the framework itself.

## Tests
```bash
python -m unittest discover tests
```
