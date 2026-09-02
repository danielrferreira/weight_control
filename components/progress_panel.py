"""The Goals tab's progress panel: stat strip, journey bar, milestone list.

Rendered as one HTML block rather than Streamlit columns and metrics, because
`st.columns` collapses to full-width stacked blocks on a phone — a five-row
milestone list became five screenfuls.

Everything here is theme-adaptive. Streamlit's per-browser Appearance setting
overrides `config.toml`, and this Streamlit version gives the server no way to
read it, so the panel must work in either theme: text uses `color: inherit`,
and every surface is a translucent neutral that reads on light and dark alike.
"""

from utils import goals

FILL_FROM = '#D2743F'
FILL_TO = '#E0A05F'
BEST = '#5B8FCC'
ZONE_FILL = 'rgba(85, 168, 104, 0.18)'
ZONE_EDGE = 'rgba(85, 168, 104, 0.50)'
ZONE_INK = '#4E9668'
NEUTRAL = 'rgba(127, 135, 150, 0.22)'
TICK = 'rgba(127, 135, 150, 0.60)'
RING = 'rgba(127, 135, 150, 0.30)'

_CSS = f"""
<style>
.pp {{ font-family: sans-serif; color: inherit; }}
.pp-muted {{ opacity: .62; }}

.pp-stats {{ display: flex; gap: 6px; margin: 2px 0 4px; }}
.pp-stat {{ flex: 1 1 0; min-width: 0; padding: 8px 10px; border-radius: 10px;
            background: {NEUTRAL}; }}
.pp-stat .k {{ font-size: 10px; opacity: .62; white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; }}
.pp-stat .v {{ font-size: 19px; font-weight: 650; line-height: 1.25; }}
.pp-stat .s {{ font-size: 10px; opacity: .62; }}

.pp-rail {{ position: relative; height: 14px; border-radius: 7px;
            background: {NEUTRAL}; margin: 34px 0 0; }}
.pp-fill {{ position: absolute; left: 0; top: 0; bottom: 0; border-radius: 7px;
            background: linear-gradient(90deg, {FILL_FROM}, {FILL_TO}); }}
.pp-zone {{ position: absolute; top: 0; bottom: 0; border-radius: 7px;
            background: {ZONE_FILL}; border: 1px solid {ZONE_EDGE};
            box-sizing: border-box; }}
.pp-tick {{ position: absolute; top: -4px; width: 2px; height: 22px;
            border-radius: 1px; }}
.pp-you  {{ position: absolute; top: -8px; width: 13px; height: 30px;
            margin-left: -6px; border-radius: 7px; background: {FILL_FROM};
            box-shadow: 0 0 0 3px {RING}; }}
.pp-lab  {{ position: absolute; font-size: 10px; opacity: .62;
            white-space: nowrap; }}
.pp-above {{ bottom: 24px; }}
.pp-below {{ top: 24px; }}
.pp-ends {{ display: flex; justify-content: space-between; font-size: 11px;
            opacity: .62; margin-top: 40px; }}

.pp-row {{ display: flex; align-items: baseline; gap: 8px; padding: 9px 0;
           border-top: 1px solid {NEUTRAL}; }}
.pp-row:first-child {{ border-top: none; }}
.pp-name {{ flex: 1 1 auto; min-width: 0; }}
.pp-name b {{ font-size: 13.5px; }}
.pp-sub {{ font-size: 10.5px; opacity: .62; }}
.pp-right {{ flex: 0 0 auto; text-align: right; font-size: 13px; }}
.pp-right .u {{ font-size: 10.5px; opacity: .62; }}
.pp-done {{ color: {ZONE_INK}; font-size: 12.5px; }}
</style>
"""


def _edge_shift(pct):
    """Keep end labels inside the rail instead of overflowing it."""
    if pct < 0.08:
        return 'translateX(0)'
    if pct > 0.92:
        return 'translateX(-100%)'
    return 'translateX(-50%)'


def _stats(items):
    cells = []
    for label, value, sub in items:
        sub_html = f'<div class="s">{sub}</div>' if sub else ''
        cells.append(f'<div class="pp-stat"><div class="k">{label}</div>'
                     f'<div class="v">{value}</div>{sub_html}</div>')
    return f'<div class="pp-stats">{"".join(cells)}</div>'


def _bar(status, progress, current_lbs, best_lbs, measurement):
    ticks = []
    for s in status:
        pct = goals.position_pct(s['target_lbs'])
        colour = FILL_FROM if s['reached'] else TICK
        ticks.append(
            f'<div class="pp-tick" style="left:{pct * 100:.2f}%;margin-left:-1px;'
            f'background:{colour}"></div>'
            f'<div class="pp-lab pp-above" style="left:{pct * 100:.2f}%;'
            f'transform:{_edge_shift(pct)}">{s["milestone"].display(measurement)}</div>')

    z0 = goals.position_pct(goals.ZONE_HIGH_LBS)
    z1 = goals.position_pct(goals.ZONE_LOW_LBS)
    zone = (f'<div class="pp-zone" style="left:{z0 * 100:.2f}%;'
            f'width:{(z1 - z0) * 100:.2f}%"></div>')

    best = ''
    if best_lbs is not None:
        bp = goals.position_pct(best_lbs)
        best = (f'<div class="pp-tick" style="left:{bp * 100:.2f}%;margin-left:-1px;'
                f'background:{BEST}"></div>'
                f'<div class="pp-lab pp-below" style="left:{bp * 100:.2f}%;'
                f'transform:{_edge_shift(bp)};color:{BEST};opacity:.9">'
                f'best {goals.to_display(best_lbs, measurement):.1f}</div>')

    you = goals.position_pct(current_lbs)
    lo, hi = goals.zone_bounds(measurement)
    start = goals.to_display(goals.CAMPAIGN_START_LBS, measurement)
    return (
        f'<div class="pp-rail">{zone}'
        f'<div class="pp-fill" style="width:{progress * 100:.2f}%"></div>'
        f'{"".join(ticks)}{best}'
        f'<div class="pp-you" style="left:{you * 100:.2f}%"></div></div>'
        f'<div class="pp-ends"><span>start {start:.1f}</span>'
        f'<span style="color:{ZONE_INK}">hold {lo:.1f}–{hi:.1f} {measurement}</span></div>')


def _rows(status, zone_state, current_lbs, measurement):
    out = []
    for s in status:
        mark = '✅' if s['reached'] else '○'
        if s['reached']:
            right = '<span class="pp-done">reached</span>'
        else:
            right = (f'<b>{goals.to_display(s["remaining_lbs"], measurement):.1f}</b>'
                     f'<span class="u"> {measurement} to go</span>')
        held = (f'held {s["last_held"]}' if s['last_held'] else 'new territory')
        out.append(
            f'<div class="pp-row"><div class="pp-name"><b>{mark} {s["label"]}</b>'
            f'<div class="pp-sub">{s["target_display"]} · {held}</div></div>'
            f'<div class="pp-right">{right}</div></div>')

    lo, hi = goals.zone_bounds(measurement)
    if zone_state == 'in':
        zright = '<span class="pp-done">holding</span>'
    elif zone_state == 'below':
        zright = f'<span style="color:{BEST}">below</span>'
    else:
        gap = goals.to_display(current_lbs - goals.ZONE_HIGH_LBS, measurement)
        zright = f'<b>{gap:.1f}</b><span class="u"> {measurement} to enter</span>'
    zmark = '🎯' if zone_state == 'in' else '○'
    out.append(
        f'<div class="pp-row"><div class="pp-name"><b>{zmark} Hold zone</b>'
        f'<div class="pp-sub">{lo:.1f}–{hi:.1f} {measurement} · settle here and stay</div></div>'
        f'<div class="pp-right">{zright}</div></div>')
    return ''.join(out)


def panel_html(status, progress, current_lbs, best_lbs, measurement,
               zone_state, stats):
    """One block: stat strip, journey bar, milestone list."""
    return (_CSS + '<div class="pp">'
            + _stats(stats)
            + _bar(status, progress, current_lbs, best_lbs, measurement)
            + _rows(status, zone_state, current_lbs, measurement)
            + '</div>')
