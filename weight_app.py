import streamlit as st
from utils.weight_analysis import wana

st.set_page_config(page_title='Weight Control', layout="wide")
st.title('Weight Control')

st.markdown("""
Welcome, here is your weekly summary:
""")

analysis = wana('data/weight.csv')

tab1, tab2, tab3 = st.tabs(['Summary', 'Data Input', 'Forecast'])

with tab1:
    st.markdown('## Weight Evolution')
    missing = analysis.find_missing()
    if len(missing)>0:
        st.markdown('Missing Dates:')
        for m in missing:
            st.markdown(m.date())

    col1, col2, col3 = st.columns([0.1, 0.1, 1])
    with col1:
        if st.button('Kgs'):
            analysis.change_measurement('kgs')
            st.session_state.clear()

    with col2:
        if st.button('Lbs'):
            analysis.change_measurement('lbs')
            st.session_state.clear()
    with col3:
        if st.button('Refresh'):
            st.session_state.clear()

    fig = analysis.plot()
    st.pyplot(fig)
    
with tab2:
    st.markdown('## Input Data')
    date = st.date_input("Select Date", value=None)
    weight = st.number_input("Enter your weight (lbs)", min_value=0.0, step=0.1)
    food_score = st.number_input("Enter your food score", min_value=0, step=1)
    exercise = st.checkbox("Did you exercise yesterday?")
    if st.button("Update table"):
        st.markdown(analysis.update_data(date, weight, food_score, exercise))
with tab3:
    weeks = st.number_input("Number of weeks to forecast", min_value=1, max_value=10, value=2, step=1, key="week_input")
    plot = analysis.forecast_graph(weeks)
    st.pyplot(plot)

