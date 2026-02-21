import pandas as pd
import streamlit as st
from utils.weight_analysis import wana, read_csv_from_drive

st.set_page_config(page_title='Weight Control', layout="wide")
st.title('Weight Control')

st.markdown("""
This app helps users track, analyze, and forecast their weight data while providing insights and visualizations based on user inputs.
""")

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

tab1, tab2, tab3, tab4 = st.tabs(['Summary', 'Data Input', 'Forecast', 'View Data'])

with tab1:
    st.subheader('Weight Evolution')
    st.caption('Your weight trends, food & exercise averages, and volatility over time.')
    missing = analysis.find_missing()
    if len(missing) > 0:
        st.warning(f"{len(missing)} missing date(s)")
        with st.expander("Show missing dates"):
            for m in missing:
                st.markdown(f"- {m.date()}")
    else:
        st.success("No missing dates.")

    fig = analysis.plot()
    st.pyplot(fig)

with tab2:
    st.subheader('Input Data')
    col1, col2, col3, col4 = st.columns([1, 1.5, 1.5, 4])
    with col1:
        date = st.date_input("Select Date", value=analysis.today, key='date_input')
    with col2:
        weight = st.number_input("Enter your weight (lbs)", value=analysis.last_weight , min_value=0.0, step=0.2, key='weight_input')
    with col3:
        food_score = st.number_input("Enter your food score", value=5, min_value=1, step=1, key='food_input')
    exercise = st.checkbox("Did you exercise yesterday?", key='exercise_input')
    if st.button("Update table"):
        if pd.Timestamp(st.session_state.date_input) > pd.Timestamp('today').normalize():
            st.error("Date cannot be in the future.")
        else:
            result = analysis.update_data(
                st.session_state.date_input,
                st.session_state.weight_input,
                st.session_state.food_input,
                st.session_state.exercise_input
            )
            if result == "Table Updated":
                st.toast("Data saved!")
                read_csv_from_drive.clear()
                st.rerun()
            else:
                st.error(result)

@st.fragment
def forecast_tab():
    col1, _ = st.columns([1, 8])
    with col1:
        weeks = st.number_input("Weeks?", min_value=1, max_value=10, value=2, step=1, key="week_input")
    plot = analysis.forecast_graph(weeks)
    st.pyplot(plot)

with tab3:
    forecast_tab()

with tab4:
    st.subheader('Last Inputs')
    st.caption('Recent entries — select how many days to display.')
    col1, col2 = st.columns([1, 4])
    with col1:
        n = st.slider("How many days?", min_value=5, max_value=100, value=20, step=5, key="last_n_slider")
    last = analysis.last_n(n=n)
    st.dataframe(last)
