import streamlit as st
from utils.weight_analysis import wana

st.set_page_config(page_title='Weight Control', layout="wide")
st.title('Weight Control')

st.markdown("""
This app helps users track, analyze, and forecast their weight data while providing insights and visualizations based on user inputs.
""")

analysis = wana('1P3JHnDkMMWf_xeGBaTHdEcAoYzTMIvU4')

tab1, tab2, tab3, tab4  = st.tabs(['Summary', 'Data Input', 'Forecast', 'View Data'])

with tab1:
    st.markdown('## Weight Evolution\nThis is your weight evolution:')
    missing = analysis.find_missing()
    if len(missing)>0:
        st.markdown('Missing Dates:')
        for m in missing:
            st.markdown(m.date())

    col1, col2, col3 = st.columns([1, 1, 17])
    with col1:
        if st.button('Kgs', key='tab1_kgs_button'):
            analysis.change_measurement('kgs')
            st.session_state.clear()

    with col2:
        if st.button('Lbs', key='tab1_lbs_button'):
            analysis.change_measurement('lbs')
            st.session_state.clear()
    with col3:
        if st.button('Refresh', key='tab1_refresh_button'):
            st.session_state.clear()

    fig = analysis.plot()
    st.pyplot(fig)
    
with tab2:
    st.markdown('## Input Data')
    col1, col2, col3, col4 = st.columns([1, 1, 1, 5])
    with col1:
        date = st.date_input("Select Date", value=analysis.today, key='date_input')
    with col2:
        weight = st.number_input("Enter your weight (lbs)", value=analysis.last_weight , min_value=0.0, step=0.2, key='weight_input')
    with col3:
        food_score = st.number_input("Enter your food score", value=5, min_value=0, step=1, key='food_input')
    exercise = st.checkbox("Did you exercise yesterday?", key='exercise_input')
    if st.button("Update table"):
        result = analysis.update_data(
            st.session_state.date_input,
            st.session_state.weight_input,
            st.session_state.food_input,
            st.session_state.exercise_input
        )
        st.markdown(result)

with tab3:
    col1, col2, col3 = st.columns([1, 1, 15])
    with col1:   
        if st.button('Kgs', key='tab3_kgs_button'):
            analysis.change_measurement('kgs')
            st.session_state.clear()                              
    with col2:
        if st.button('Lbs', key='tab3_lbs_button'):
            analysis.change_measurement('lbs')
            st.session_state.clear()                                  
    col1, col2 = st.columns([1, 8])
    with col1:
        weeks = st.number_input("Weeks?", min_value=1, max_value=10, value=2, step=1, key="week_input")
    if st.button('Refresh', key='tab3_refresh_button'):
            st.session_state.clear()
    plot = analysis.forecast_graph(weeks)
    st.pyplot(plot)

with tab4:
    st.markdown('## Last Inputs\nSelect how many days you want to visualize and the measurement (Kgs or Lbs)')
    col1, col2 = st.columns([1, 4])
    with col1:
        n = st.slider("How many days?", min_value=5, max_value=100, value=20, step=5, key="last_n_slider")
    col1, col2 = st.columns([1, 17])
    last = None
    with col1:
        if st.button('Kgs', key='tab4_kgs_button'):
            analysis.change_measurement('kgs')
            st.session_state.clear()
            last = analysis.last_n(n=n)

    with col2:
        if st.button('Lbs', key='tab4_lbs_button'):
            analysis.change_measurement('lbs')
            st.session_state.clear()
            last = analysis.last_n(n=n)
    if last is not None:
        st.dataframe(last)
    
    


