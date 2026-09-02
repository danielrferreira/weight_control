"""Plotly chart builders for the weight tracker.

Kept separate from `weight_analysis.py` so that module stays focused on data
loading, analysis and forecasting while all presentation lives here.

Colours were validated with the dataviz palette checker against the dark chart
surface (#1C2231): every categorical pair that co-occurs in a single chart
clears the CVD and normal-vision separation floors.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# -- surfaces -----------------------------------------------------------------
PAPER_BG = '#0E1117'   # app background
PLOT_BG  = '#1C2231'   # chart surface
GRID     = '#2A3347'
INK      = '#FAFAFA'
INK_MUTE = '#9AA5B8'

# -- data series --------------------------------------------------------------
_PALETTE = {
    'weight':      '#4C72B0',  # steel blue    — raw weight line
    'avg_7d':      '#D2743F',  # warm orange   — 7-day moving average
    'food':        '#55A868',  # sage green    — food avg
    'exercise':    '#C44E52',  # muted crimson — exercise avg
    'combined':    '#8567C4',  # violet        — food+exercise combined
    'std':         '#3E9DC4',  # sky blue      — std deviation
    # forecast reads as a diverging scale: pessimistic <- expected -> optimistic
    'fc_expected': '#B0BEC5',  # light slate   — neutral midpoint (most prominent on dark)
    'fc_bad':      '#BE2F4A',  # red pole      — pessimistic
    'fc_good':     '#8567C4',  # violet pole   — optimistic
}

# -- reference marks (recessive, never data hues) -----------------------------
REFERENCE  = '#8A94A6'   # personal-min line
GOAL_FILL  = 'rgba(200, 230, 201, 0.13)'   # goal band
GOAL_EDGE  = 'rgba(200, 230, 201, 0.35)'
BAND_FILL  = 'rgba(138, 148, 166, 0.16)'   # imputed / travel periods
BAND_TEXT  = '#A8B2C4'

# -- periods where weight was imputed rather than measured --------------------
# (start, end, label) — inclusive. Add a line per trip.
IMPUTED_PERIODS = [
    ('2025-08-01', '2025-08-31', 'Brazil'),
    ('2026-08-01', '2026-08-31', 'Brazil'),
]

# Range presets for the filter row above the charts.
RANGE_OPTIONS = {'1M': 30, '3M': 90, '6M': 180, '1Y': 365, 'All': None}
DEFAULT_RANGE = '3M'

PLOTLY_CONFIG = {
    'displayModeBar': False,
    'displaylogo': False,
    'scrollZoom': False,     # don't hijack page scroll on mobile
    'doubleClick': 'reset',
}


def slice_range(df, range_key):
    """Return the tail of `df` covering the selected preset."""
    days = RANGE_OPTIONS.get(range_key)
    if days is None or df.empty:
        return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index >= cutoff]


def imputed_mask(index):
    """Boolean mask marking rows that fall inside an imputed period."""
    mask = pd.Series(False, index=index)
    for start, end, _ in IMPUTED_PERIODS:
        mask |= (index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))
    return mask


def _split_measured_imputed(series, mask):
    """Split a series into measured/imputed halves for solid vs dashed drawing.

    Both halves keep the full index with NaN elsewhere, so Plotly breaks the
    line at the gaps. Boundary points are duplicated into both halves so the
    solid and dashed runs visually join instead of leaving a hole.
    """
    measured = series.where(~mask)
    imputed = series.where(mask)
    m = mask.to_numpy()
    if m.any():
        idx = np.flatnonzero(m)
        # Extend each contiguous imputed run by one point on either side so the
        # dashed run starts at the last real reading and ends at the next one.
        # `measured` is left untouched: imputed days must never render solid.
        starts = idx[np.r_[True, np.diff(idx) > 1]]
        ends = idx[np.r_[np.diff(idx) > 1, True]]
        for s in starts:
            if s - 1 >= 0:
                imputed.iloc[s - 1] = series.iloc[s - 1]
        for e in ends:
            if e + 1 < len(series):
                imputed.iloc[e + 1] = series.iloc[e + 1]
    return measured, imputed


def _base_layout(fig, title, height, show_legend, legend_rows=1):
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=14,
                    t=(44 + 22 * legend_rows) if show_legend else 44, b=28),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=INK, size=13, family='sans-serif'),
        title=dict(text=title, font=dict(size=15, color=INK),
                   x=0, xanchor='left', y=0.97, yanchor='top'),
        hovermode='x unified',
        dragmode='pan',
        showlegend=show_legend,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0,
                    font=dict(size=11, color=INK_MUTE), bgcolor='rgba(0,0,0,0)',
                    itemsizing='constant'),
        hoverlabel=dict(bgcolor='#141A26', bordercolor=GRID,
                        font=dict(color=INK, size=12)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, showline=False,
                     tickfont=dict(size=11, color=INK_MUTE),
                     showspikes=True, spikemode='across', spikethickness=1,
                     spikedash='dot', spikecolor=INK_MUTE)
    # automargin reserves room for the tick labels; without it a 3-digit weight
    # loses its leading digit to the left edge on narrow screens.
    fig.update_yaxes(gridcolor=GRID, zeroline=False, showline=False,
                     tickfont=dict(size=11, color=INK_MUTE), automargin=True)
    return fig


def _add_imputed_bands(fig, df, label_bands=True):
    """Shade the periods where data was imputed rather than weighed."""
    if df.empty:
        return
    lo, hi = df.index.min(), df.index.max()
    for start, end, label in IMPUTED_PERIODS:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        if e < lo or s > hi:
            continue          # band is outside the visible window
        fig.add_vrect(
            x0=max(s, lo), x1=min(e, hi),
            fillcolor=BAND_FILL, line_width=0, layer='below',
            annotation_text=f'{label} (imputed)' if label_bands else None,
            annotation_position='top left',
            annotation_font=dict(size=10, color=BAND_TEXT),
        )


def _line(fig, x, y, name, color, width=2, dash=None, opacity=1.0,
          hover_fmt='%{y:.1f}', show_legend=True):
    fig.add_trace(go.Scatter(
        x=x, y=y, name=name, mode='lines',
        line=dict(color=color, width=width, dash=dash),
        opacity=opacity, showlegend=show_legend,
        hovertemplate=f'{name}: <b>{hover_fmt}</b><extra></extra>',
        connectgaps=False,
    ))


def build_analysis_figures(df, weight_col, measurement, weight_goal,
                           weight_goal_band, weight_min, height=300):
    """Build the four analysis charts as separate responsive figures."""
    figs = []
    mask = imputed_mask(df.index)

    # 1 — weight trends -------------------------------------------------------
    f1 = go.Figure()
    if not df.empty:
        f1.add_hrect(y0=weight_goal - weight_goal_band, y1=weight_goal + weight_goal_band,
                     fillcolor=GOAL_FILL, line_width=0, layer='below',
                     annotation_text='Goal range', annotation_position='bottom left',
                     annotation_font=dict(size=10, color=GOAL_EDGE))
        f1.add_hline(y=weight_min, line=dict(color=REFERENCE, width=1.5, dash='dot'),
                     annotation_text=f'Personal min {weight_min:.1f}',
                     annotation_position='bottom right',
                     annotation_font=dict(size=10, color=REFERENCE))
    raw_measured, raw_imputed = _split_measured_imputed(df[weight_col], mask)
    _line(f1, df.index, raw_measured, f'Weight ({measurement})',
          _PALETTE['weight'], width=1.5, opacity=0.65)
    if mask.any():
        _line(f1, df.index, raw_imputed, 'Weight (imputed)',
              _PALETTE['weight'], width=1.5, dash='dot', opacity=0.4)
    _line(f1, df.index, df[f'{weight_col}_avg_7d'], '7-day avg', _PALETTE['avg_7d'], width=2.5)
    _add_imputed_bands(f1, df)
    _base_layout(f1, f'Weight Trends ({measurement})', height, True)
    figs.append(f1)

    # 2 — combined food & exercise -------------------------------------------
    f2 = go.Figure()
    _line(f2, df.index, df['food_exercise_avg_7d'], 'Food & exercise',
          _PALETTE['combined'], width=2.5, hover_fmt='%{y:.2f}', show_legend=False)
    _add_imputed_bands(f2, df)
    _base_layout(f2, 'Food & Exercise Combined (7-day avg)', height, False)
    figs.append(f2)

    # 3 — food vs exercise ----------------------------------------------------
    f3 = go.Figure()
    _line(f3, df.index, df['food_avg_7d'], 'Food', _PALETTE['food'],
          width=2.5, hover_fmt='%{y:.2f}')
    _line(f3, df.index, df['exer_avg_7d'], 'Exercise', _PALETTE['exercise'],
          width=2.5, hover_fmt='%{y:.2f}')
    _add_imputed_bands(f3, df)
    _base_layout(f3, 'Food & Exercise Trends (7-day avg, scaled)', height, True)
    figs.append(f3)

    # 4 — volatility ----------------------------------------------------------
    f4 = go.Figure()
    _line(f4, df.index, df[f'{weight_col}_std_21d'], '21-day std dev',
          _PALETTE['std'], width=2.5, hover_fmt='%{y:.2f}', show_legend=False)
    _add_imputed_bands(f4, df)
    _base_layout(f4, f'Weight Volatility (21-day std dev, {measurement})', height, False)
    figs.append(f4)

    return figs


def build_forecast_figure(df, interpolated_df, weight_col, measurement,
                          weight_goal, weight_goal_band, weight_min,
                          future_date, future_expected, future_bad, future_good,
                          height=380):
    """Historical 7-day average plus the three forecast scenarios."""
    fig = go.Figure()
    fig.add_hrect(y0=weight_goal - weight_goal_band, y1=weight_goal + weight_goal_band,
                  fillcolor=GOAL_FILL, line_width=0, layer='below',
                  annotation_text='Goal range', annotation_position='bottom left',
                  annotation_font=dict(size=10, color=GOAL_EDGE))
    fig.add_hline(y=weight_min, line=dict(color=REFERENCE, width=1.5, dash='dot'),
                  annotation_text=f'Personal min {weight_min:.1f}',
                  annotation_position='bottom right',
                  annotation_font=dict(size=10, color=REFERENCE))

    # uncertainty band between the two poles
    fig.add_trace(go.Scatter(
        x=list(interpolated_df.index) + list(interpolated_df.index[::-1]),
        y=list(interpolated_df['weight_gain_bad']) + list(interpolated_df['weight_gain_good'][::-1]),
        fill='toself', fillcolor='rgba(138, 148, 166, 0.12)',
        line=dict(width=0), hoverinfo='skip', showlegend=False,
    ))

    _line(fig, df.index, df[f'{weight_col}_avg_7d'], f'Actual 7-day avg',
          _PALETTE['avg_7d'], width=2.5)
    _line(fig, interpolated_df.index, interpolated_df['weight_gain_bad'],
          'Pessimistic', _PALETTE['fc_bad'], width=1.8, dash='dash')
    _line(fig, interpolated_df.index, interpolated_df['weight_gain_good'],
          'Optimistic', _PALETTE['fc_good'], width=1.8, dash='dash')
    _line(fig, interpolated_df.index, interpolated_df['weight_gain_expected'],
          'Expected', _PALETTE['fc_expected'], width=2.8, dash='dash')

    # direct labels on the scenario endpoints
    for value, color in ((future_expected, _PALETTE['fc_expected']),
                         (future_bad, _PALETTE['fc_bad']),
                         (future_good, _PALETTE['fc_good'])):
        fig.add_annotation(x=future_date, y=value, text=f'<b>{value:.1f}</b>',
                           showarrow=False, xanchor='left', xshift=6,
                           font=dict(size=11, color=color))

    _add_imputed_bands(fig, df)
    _base_layout(fig, f'Weight Forecast ({measurement})', height, True, legend_rows=2)
    fig.update_xaxes(range=[df.index.max() - pd.Timedelta(days=90),
                            future_date + pd.Timedelta(days=10)])
    return fig
