import datetime
import pandas as pd
import streamlit as st
from utils.weight_analysis import wana, read_csv_from_drive
from utils import charts, goals
from components.progress_panel import panel_html
from components.log_form import log_form

st.set_page_config(page_title='Weight Control', layout="centered")

st.markdown("""
<style>
/* Reduce top padding */
.block-container { padding-top: 1.5rem !important; }
/* Hide Streamlit chrome on mobile */
@media (max-width: 768px) {
  #MainMenu, footer, header { visibility: hidden; }
}
/* Tab bar: bigger touch targets */
.stTabs [data-baseweb="tab"] { padding: 10px 16px; font-size: 15px; }
/* Plotly draws text with baked-in fills. The server cannot read the browser's
   Appearance setting, so let the chart chrome inherit the page text colour and
   render correctly in light and dark alike. Annotations keep their own colours. */
.stPlotlyChart .gtitle,
.stPlotlyChart .xtitle,
.stPlotlyChart .ytitle,
.stPlotlyChart .xtick text,
.stPlotlyChart .ytick text,
.stPlotlyChart .legendtext { fill: currentColor !important; }
.stPlotlyChart .xtick text,
.stPlotlyChart .ytick text,
.stPlotlyChart .legendtext { opacity: .70; }
</style>
""", unsafe_allow_html=True)

st.title('Weight Control')

FILE_ID = '1P3JHnDkMMWf_xeGBaTHdEcAoYzTMIvU4'

with st.sidebar:
    if st.button('Refresh Data'):
        read_csv_from_drive.clear()
        st.rerun()

raw_df = read_csv_from_drive(FILE_ID)
if raw_df is None:
    st.error("Could not load data from Google Drive. Check your connection and credentials.")
    st.stop()
measurement = st.session_state.get('measurement', 'lbs')
analysis = wana(FILE_ID, raw_df, measurement=measurement)

st.segmented_control("Unit", options=['lbs', 'kgs'], key='measurement', default='lbs')

tab1, tab_goals, tab2, tab3, tab4 = st.tabs(['Log', 'Goals', 'Analysis', 'Forecast', 'Data'])

@st.fragment
def input_tab():
    # Log tab always uses lbs
    last_weight = round(float(analysis.last_weight), 1)

    last_food     = int(analysis.df['food'].iloc[-1]) if not analysis.df.empty else 5
    last_exercise = bool(analysis.df['exer'].iloc[-1]) if not analysis.df.empty else False
    existing_dates = analysis.df.index.strftime("%Y-%m-%d").tolist()

    missing = analysis.find_missing()
    if len(missing) > 0:
        with st.expander(f"⚠️ {len(missing)} missing date(s)"):
            for m in missing:
                st.markdown(f"- {m.date()}")
    else:
        st.success("No missing dates.", icon="✅")

    result = log_form(
        last_weight=last_weight,
        last_food=last_food,
        last_exercise=last_exercise,
        unit='lbs',
        step=0.2,
        existing_dates=existing_dates,
        key="log_form",
        height=440,
    )

    if result is not None:
        entry_date = datetime.date.fromisoformat(result["date"])
        weight_lbs = float(result["weight"])

        update_result = analysis.update_data(
            entry_date,
            weight_lbs,
            int(result["food"]),
            bool(result["exercise"]),
        )
        if update_result == "Table Updated":
            read_csv_from_drive.clear()
            del st.session_state["log_form"]
            st.toast("Saved!", icon="✅")
            st.rerun(scope="app")
        else:
            st.error(update_result)

with tab1:
    input_tab()

@st.fragment
def analysis_tab():
    st.subheader('Weight Evolution')
    st.caption('Your weight trends, food & exercise averages, and volatility over time.')
    # Filters live in one row above everything they scope.
    range_key = st.segmented_control(
        'Range', options=list(charts.RANGE_OPTIONS.keys()),
        default=charts.DEFAULT_RANGE, key='analysis_range',
    ) or charts.DEFAULT_RANGE
    for fig in analysis.plot(range_key):
        st.plotly_chart(fig, use_container_width=True, config=charts.PLOTLY_CONFIG)


@st.fragment
def goals_tab():
    df = analysis.df
    mask = charts.imputed_mask(df.index)
    status = goals.milestone_status(df, mask, measurement)
    current = goals.current_average(df)
    nxt = goals.next_milestone(status)
    this_year, last_year = goals.ghost_race(df)
    pace = goals.ghost_pace(last_year)
    zone = goals.zone_status(current)
    lo, hi = goals.zone_bounds(measurement)

    # -- hero: the next target, never the far one ---------------------------
    if nxt is None:
        if zone == 'in':
            st.success(f"In the zone at {goals.to_display(current, measurement):.1f} "
                       f"{measurement}. Goal reached — now hold it between {lo:.1f} and {hi:.1f}.",
                       icon="🎯")
        elif zone == 'below':
            st.info(f"Below the zone at {goals.to_display(current, measurement):.1f} "
                    f"{measurement}. Ease back up into {lo:.1f}–{hi:.1f}.", icon="⬆️")
        else:
            st.success("Every milestone reached.", icon="🏁")
    else:
        gap = goals.to_display(nxt['remaining_lbs'], measurement)
        st.markdown(f"### {gap:.1f} {measurement} to {nxt['label']}")
        cap = f"next target {nxt['target_display']}"
        when = goals.eta(nxt['remaining_lbs'], pace)
        if when:
            cap += f" · around {when:%b %d} at last year's pace"
        st.caption(cap)

    # -- one HTML block: stats, bar, milestones -----------------------------
    cmp_ = goals.ghost_comparison(this_year, last_year)
    delta = goals.to_display(current - goals.CAMPAIGN_START_LBS, measurement)
    stats = [(f"7-day avg ({measurement})",
              f"{goals.to_display(current, measurement):.1f}", f"{delta:+.1f} since day 0")]
    if cmp_:
        stats.append(("Day", f"{cmp_['day']}", "since Brazil"))
        stats.append(("vs last year",
                      f"{goals.to_display(cmp_['delta'], measurement):+.1f}",
                      "ahead" if cmp_['delta'] > 0 else "behind"))
    best_lbs, _ = goals.personal_best(df)
    st.markdown(
        panel_html(status, goals.overall_progress(df), current, best_lbs,
                   measurement, zone, stats),
        unsafe_allow_html=True)

    # -- the ghost race -----------------------------------------------------
    if len(last_year) > 1:
        st.caption(f"Last year you left Brazil at "
                   f"{goals.to_display(last_year.iloc[0], measurement):.1f} {measurement} and reached "
                   f"{goals.to_display(last_year.min(), measurement):.1f} in {int(last_year.idxmin())} days"
                   f" — {abs(goals.to_display(pace, measurement)):.2f} {measurement}/week off the same "
                   f"trip. That is the pace to beat.")
    # days 0-7 still carry imputed values inside the 7-day window
    fig = charts.build_ghost_race_figure(this_year, last_year, goals.MILESTONES,
                                         measurement, inflated_days=7,
                                         zone=(goals.ZONE_LOW_LBS, goals.ZONE_HIGH_LBS))
    st.plotly_chart(fig, use_container_width=True, config=charts.PLOTLY_CONFIG)

with tab_goals:
    goals_tab()

with tab2:
    analysis_tab()

@st.fragment
def forecast_tab():
    weeks = st.number_input("Weeks?", min_value=1, max_value=10, value=2, step=1, key="week_input")
    plot = analysis.forecast_graph(weeks)
    st.plotly_chart(plot, use_container_width=True, config=charts.PLOTLY_CONFIG)

with tab3:
    forecast_tab()

with tab4:
    st.subheader('Last Inputs')
    st.caption('Recent entries — select how many days to display.')
    n = st.slider("How many days?", min_value=5, max_value=100, value=20, step=5, key="last_n_slider")
    last = analysis.last_n(n=n)
    st.dataframe(last, use_container_width=True)
