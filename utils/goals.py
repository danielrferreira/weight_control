"""Milestone tracking for the post-Brazil recovery campaign.

Pure data and arithmetic — no Streamlit, no figures. The Goals tab renders
what this module computes.

The framing: coming out of Brazil in 2025 the same recovery was run and won
(157.9 -> 150.7 over 53 days), so this year's progress is raced against that
run rather than against an abstract target.
"""

import datetime as _dt

import pandas as pd

LBS_PER_KG = 1 / 0.453592

# -- campaign anchors ---------------------------------------------------------
# Day 0 is the last day of each Brazil trip, so the two years line up.
CAMPAIGN_START_DATE = pd.Timestamp('2026-08-31')
GHOST_START_DATE = pd.Timestamp('2025-08-31')

# Declared by the user rather than derived: the computed 7-day average on
# 2026-08-31 is 161.1, but the imputed ramp was deliberately worst-case and
# 161.4 is taken as the starting average for this campaign.
CAMPAIGN_START_LBS = 161.4

GHOST_HORIZON_DAYS = 100


class Milestone:
    __slots__ = ('key', 'label', 'note', 'lbs')

    def __init__(self, key, label, note, lbs):
        self.key, self.label, self.note, self.lbs = key, label, note, lbs

    def value(self, measurement):
        return self.lbs * 0.453592 if measurement == 'kgs' else self.lbs

    def display(self, measurement):
        return f'{self.value(measurement):.1f} {measurement}'


# Ordered heaviest -> lightest; the first unreached one is the "next" target.
MILESTONES = [
    Milestone('worst_week', 'Worst week ever',
              'your highest real 7-day average, set 2025-01-17', 160.4),
    Milestone('pre_brazil', 'Pre-Brazil',
              'your 7-day average the day before you flew out', 157.3),
    Milestone('kg70', '70 kg', None, 70 * LBS_PER_KG),
    Milestone('kg68', '68 kg', None, 68 * LBS_PER_KG),
]

# 68 kg is the finish line. The bar deliberately runs on to 66 kg so there is
# room below the goal: 66-68 is the zone to settle into and hold, which is why
# 66 kg is the end of the axis rather than a milestone of its own.
GOAL_LBS = 68 * LBS_PER_KG
ZONE_HIGH_LBS = GOAL_LBS            # entering the zone == reaching the goal
ZONE_LOW_LBS = 66 * LBS_PER_KG      # bottom of the zone, and end of the axis
AXIS_END_LBS = ZONE_LOW_LBS

# kept as the bar's right-hand end
FINAL_LBS = AXIS_END_LBS


def to_display(lbs, measurement):
    """Convert a lbs quantity into the unit currently selected in the app."""
    return lbs * 0.453592 if measurement == 'kgs' else lbs


def current_average(df):
    """Latest 7-day average, in lbs."""
    series = df['weight_lbs_avg_7d'].dropna()
    return float(series.iloc[-1]) if len(series) else float('nan')


def _fully_real_average(df, imputed_mask):
    """7-day average restricted to windows containing no imputed days.

    A window that overlaps a Brazil month is fabricated, so it must not count
    as evidence that a milestone was genuinely held.
    """
    clean = (~imputed_mask).rolling(7).sum() == 7
    return df['weight_lbs_avg_7d'][clean.fillna(False)]


def milestone_status(df, imputed_mask, measurement='lbs'):
    """Per-milestone progress, distance and prior-achievement history."""
    current = current_average(df)
    real_avg = _fully_real_average(df, imputed_mask)
    out = []
    for m in MILESTONES:
        reached = current <= m.lbs
        held = real_avg[real_avg <= m.lbs]
        span = max(CAMPAIGN_START_LBS - m.lbs, 1e-9)
        out.append({
            'milestone': m,
            'label': m.label,
            'note': m.note,
            'target_lbs': m.lbs,
            'target_display': m.display(measurement),
            'reached': reached,
            'remaining_lbs': max(current - m.lbs, 0.0),
            'remaining_display': to_display(max(current - m.lbs, 0.0), measurement),
            # how far along the leg from campaign start to this milestone
            'pct': min(max((CAMPAIGN_START_LBS - current) / span, 0.0), 1.0),
            'last_held': held.index[-1].date() if len(held) else None,
        })
    return out


def next_milestone(status):
    """The first milestone not yet reached, or None when all are done."""
    for s in status:
        if not s['reached']:
            return s
    return None


def overall_progress(df):
    """How far the fill has travelled along the bar's axis (start -> 66 kg)."""
    return position_pct(current_average(df))


def goal_progress(df):
    """Progress toward the actual goal of 68 kg, 0-1 (100% on entering the zone)."""
    current = current_average(df)
    span = CAMPAIGN_START_LBS - GOAL_LBS
    return min(max((CAMPAIGN_START_LBS - current) / span, 0.0), 1.0)


def position_pct(lbs):
    """Where a weight sits on the campaign-start -> 66 kg axis, 0-1."""
    span = CAMPAIGN_START_LBS - AXIS_END_LBS
    return min(max((CAMPAIGN_START_LBS - lbs) / span, 0.0), 1.0)


def zone_status(current_lbs):
    """Where the current average sits relative to the 66-68 kg hold zone.

    Returns 'above' (still working toward 68), 'in' (goal met, hold here) or
    'below' (under 66 — past the band rather than failing at it).
    """
    if current_lbs > ZONE_HIGH_LBS:
        return 'above'
    if current_lbs >= ZONE_LOW_LBS:
        return 'in'
    return 'below'


def zone_bounds(measurement):
    """(low, high) of the hold zone in the displayed unit."""
    return to_display(ZONE_LOW_LBS, measurement), to_display(ZONE_HIGH_LBS, measurement)


def personal_best(df):
    """Best (lowest) 7-day average ever recorded, and when."""
    series = df['weight_lbs_avg_7d'].dropna()
    if not len(series):
        return None, None
    return float(series.min()), series.idxmin().date()


def _leg(df, start_date, horizon, declared_start=None):
    """One year's post-Brazil 7-day average, indexed by days since day 0."""
    seg = df.loc[df.index >= start_date, 'weight_lbs_avg_7d'].dropna()
    seg = seg[seg.index <= start_date + pd.Timedelta(days=horizon)]
    if not len(seg):
        return pd.Series(dtype=float)
    days = (seg.index - start_date).days
    out = pd.Series(seg.to_numpy(), index=days)
    if declared_start is not None:
        out.loc[0] = declared_start
    return out.sort_index()


def ghost_race(df):
    """Align last year's recovery against this year's, by days since Brazil.

    Returns (this_year, last_year) Series indexed by day offset.
    """
    this_year = _leg(df, CAMPAIGN_START_DATE, GHOST_HORIZON_DAYS,
                     declared_start=CAMPAIGN_START_LBS)
    last_year = _leg(df, GHOST_START_DATE, GHOST_HORIZON_DAYS)
    return this_year, last_year


def ghost_pace(last_year):
    """Realised lbs/week of last year's run, from day 0 to its lowest point."""
    if len(last_year) < 2:
        return 0.0
    trough_day = last_year.idxmin()
    if trough_day <= 0:
        return 0.0
    drop = last_year.loc[trough_day] - last_year.iloc[0]
    return drop / trough_day * 7.0


def ghost_comparison(this_year, last_year):
    """Where you stand against the ghost today, as change since day 0.

    Compared on change-from-day-0 rather than absolute weight, because the two
    years start from different averages.
    """
    if len(this_year) < 2 or len(last_year) < 2:
        return None
    day = int(this_year.index.max())
    mine = this_year.loc[day] - this_year.iloc[0]
    if day not in last_year.index:
        return None
    theirs = last_year.loc[day] - last_year.iloc[0]
    return {'day': day, 'mine': mine, 'theirs': theirs, 'delta': theirs - mine}


def eta(remaining_lbs, pace_per_week, today=None):
    """Date a target is met at last year's realised pace, or None."""
    if pace_per_week >= 0 or remaining_lbs <= 0:
        return None
    weeks = remaining_lbs / abs(pace_per_week)
    if weeks > 260:                     # beyond ~5 years: not a useful promise
        return None
    today = today or _dt.date.today()
    return today + _dt.timedelta(days=round(weeks * 7))
