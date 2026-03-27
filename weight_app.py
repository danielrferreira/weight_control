import datetime
import pandas as pd
import streamlit as st
from utils.weight_analysis import wana, read_csv_from_drive
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
</style>
""", unsafe_allow_html=True)

st.title('Weight Control')

FILE_ID = '1P3JHnDkMMWf_xeGBaTHdEcAoYzTMIvU4'

with st.sidebar:
    st.markdown("### Settings")
    st.radio("Unit", options=['lbs', 'kgs'], key='measurement')
    if st.button('Refresh Data'):
        read_csv_from_drive.clear()
        st.rerun()

raw_df = read_csv_from_drive(FILE_ID)
measurement = st.session_state.get('measurement', 'lbs')
analysis = wana(FILE_ID, raw_df, measurement=measurement)

tab1, tab2, tab3, tab4 = st.tabs(['Log', 'Analysis', 'Forecast', 'Data'])

@st.fragment
def input_tab():
    # Defaults from last entry
    last_weight_lbs = float(analysis.last_weight)
    if analysis.measurement == 'kgs':
        last_weight = round(last_weight_lbs * 0.453592, 2)
        step = 0.1
    else:
        last_weight = round(last_weight_lbs, 1)
        step = 0.2

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
        unit=analysis.measurement,
        step=step,
        existing_dates=existing_dates,
        key="log_form",
        height=440,
    )

    if result is not None:
        entry_date = datetime.date.fromisoformat(result["date"])
        weight_received = float(result["weight"])
        # convert to lbs if user is in kgs
        if analysis.measurement == 'kgs':
            weight_lbs = round(weight_received / 0.453592, 1)
        else:
            weight_lbs = weight_received

        update_result = analysis.update_data(
            entry_date,
            weight_lbs,
            int(result["food"]),
            bool(result["exercise"]),
        )
        if update_result == "Table Updated":
            read_csv_from_drive.clear()
            st.toast("Saved!", icon="✅")
            st.rerun(scope="app")
        else:
            st.error(update_result)

with tab1:
    input_tab()

with tab2:
    st.subheader('Weight Evolution')
    st.caption('Your weight trends, food & exercise averages, and volatility over time.')
    fig = analysis.plot()
    st.pyplot(fig, use_container_width=True)

@st.fragment
def forecast_tab():
    weeks = st.number_input("Weeks?", min_value=1, max_value=10, value=2, step=1, key="week_input")
    plot = analysis.forecast_graph(weeks)
    st.pyplot(plot, use_container_width=True)

with tab3:
    forecast_tab()

with tab4:
    st.subheader('Last Inputs')
    st.caption('Recent entries — select how many days to display.')
    n = st.slider("How many days?", min_value=5, max_value=100, value=20, step=5, key="last_n_slider")
    last = analysis.last_n(n=n)
    st.dataframe(last, use_container_width=True)
