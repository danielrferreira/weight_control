import pandas as pd
import streamlit as st
from sklearn.preprocessing import MinMaxScaler
import json
import io

from utils import charts

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

@st.cache_resource
def get_drive_service():
    service_account_info = st.secrets["google_drive"]
    credentials = Credentials.from_service_account_info(service_account_info, scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=credentials)

@st.cache_data(ttl=300)
def read_csv_from_drive(file_id):
    try:
        request = get_drive_service().files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        fh.seek(0)
        return pd.read_csv(fh)
    except Exception as e:
        return None

class wana:
    def __init__(self, file_id, raw_df, measurement='lbs', param='forecast_model/model_parameters_reg_prod.json'):
        self.file_id = file_id
        self.param = param
        self.measurement = measurement
        df = raw_df.copy()
        df.index = pd.to_datetime(df['date'])
        self.raw_df = df
        df['weight_kgs'] = df['weight_lbs'] * 0.453592
        df = df.drop(['date'], axis=1)
        df = df.sort_index()
        if self.measurement=='kgs':
            self.weight_col = 'weight_kgs'
            self.weight_goal = 67
            self.weight_goal_band = 1
            self.weight_min = df['weight_kgs'].min()
        else:
            self.weight_col = 'weight_lbs'
            self.weight_goal = 147.7097157
            self.weight_goal_band = 2.2
            self.weight_min = df['weight_lbs'].min()
        for col in ['weight_lbs', 'weight_kgs', 'food', 'exer']:
            df[f'{col}_avg_7d'] = df[col].rolling(window=7).mean()
        for col in ['weight_lbs', 'weight_kgs', 'food', 'exer']:
            df[f'{col}_std_21d'] = df[col].rolling(window=21).std()
        scaler = MinMaxScaler()
        for col in ['food_avg_7d','exer_avg_7d']:
            df[col] = scaler.fit_transform(df[col].values.reshape(-1, 1))
        df['food_exercise_avg_7d'] = 0.7*df['food_avg_7d'] + 0.3*df['exer_avg_7d']
        self.df = df
        self.today = pd.Timestamp.now(tz='America/New_York').normalize().tz_localize(None)
        self.last_weight = df['weight_lbs'].iloc[-1]
    
    def last_n(self, n):
        df_n = self.df.sort_index(ascending=False).head(n)
        output = df_n[[self.weight_col, 'food', 'exer', f'{self.weight_col}_avg_7d',  'food_avg_7d', 'exer_avg_7d']]
        return output

    def change_measurement(self, measurement):
        self.measurement = measurement
        self.weight_col = 'weight_kgs' if measurement == 'kgs' else 'weight_lbs'
        self.weight_goal = 67 if measurement == 'kgs' else 147.7097157
        self.weight_goal_band = 1 if measurement == 'kgs' else 2.2
        self.weight_min = self.df['weight_kgs'].min() if measurement == 'kgs' else self.df['weight_lbs'].min()
        return
    
    def find_missing(self):
        today = self.today
        full_date_range = pd.date_range(start=self.df.index.min(), end=today, freq='D')
        missing_dates = full_date_range.difference(self.df.index)
        return missing_dates

    def plot(self, range_key=charts.DEFAULT_RANGE):
        """Return the analysis charts as a list of Plotly figures."""
        df = charts.slice_range(self.df, range_key)
        return charts.build_analysis_figures(
            df,
            weight_col=self.weight_col,
            measurement=self.measurement,
            weight_goal=self.weight_goal,
            weight_goal_band=self.weight_goal_band,
            weight_min=self.weight_min,
        )

    def update_data(self, date, weight, food, exercise):
        if pd.to_datetime(date) in self.raw_df.index:
            return f"Date {date} already exists in the data. No update performed."
        temp = pd.DataFrame({'date': [date], 'weight_lbs': [weight], 'exer': [exercise], 'food': [food]})
        temp.index = pd.to_datetime(temp['date'])
        df = pd.concat([self.raw_df, temp])
        df = df.sort_index()
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)

        media = MediaIoBaseUpload(io.BytesIO(buffer.getvalue().encode()), mimetype='text/csv')
        try:
            get_drive_service().files().update(fileId=self.file_id, media_body=media).execute()
        except Exception as e:
            return f"Failed to save data to Drive: {type(e).__name__}"
        self.raw_df = df
        return "Table Updated"
    
    def estimate_gain_weight(self):
        with open(self.param, 'r') as f:
            param = json.load(f)
        last_week_food = self.df['food'].tail(7).mean()
        last_week_exer = self.df['exer'].tail(7).sum()
        last_week_food_n = (last_week_food - param['food_min']) / param['food_range']
        last_week_exer_n = (last_week_exer - param['exer_min']) / param['exer_range']
        weighted_average = param['w1']*last_week_exer_n + (1-param['w1'])*last_week_food_n
        weight_gain_expected = param['intercept']+param['slope']*weighted_average
        weight_gain_bad = param['intercept']+param['slope']*0.1
        weight_gain_good = param['intercept']+param['slope']*0.9
        return weight_gain_expected, weight_gain_bad, weight_gain_good
    
    def forecast_graph(self, num_weeks):
        weight_gain_expected, weight_gain_bad, weight_gain_good = self.estimate_gain_weight()
        if self.measurement == 'kgs':
            weight_gain_expected = weight_gain_expected * 0.453592
            weight_gain_bad = weight_gain_bad * 0.453592
            weight_gain_good = weight_gain_good * 0.453592
        last_date = self.df.index[-1]
        future_date = last_date + pd.Timedelta(weeks=num_weeks)
        last_weight = self.df[f'{self.weight_col}_avg_7d'].iloc[-1]
        future_weight_expected = last_weight + (weight_gain_expected * num_weeks)
        future_weight_bad = last_weight + (weight_gain_bad * num_weeks)
        future_weight_good = last_weight + (weight_gain_good * num_weeks)
        interpolation_df = pd.DataFrame({
                'date': [last_date, future_date],
                'weight_gain_expected': [last_weight, future_weight_expected],
                'weight_gain_bad': [last_weight, future_weight_bad],
                'weight_gain_good': [last_weight, future_weight_good]
            }).set_index('date')
        interpolated_df = interpolation_df.resample('D').interpolate()
        return charts.build_forecast_figure(
            self.df, interpolated_df,
            weight_col=self.weight_col,
            measurement=self.measurement,
            weight_goal=self.weight_goal,
            weight_goal_band=self.weight_goal_band,
            weight_min=self.weight_min,
            future_date=future_date,
            future_expected=future_weight_expected,
            future_bad=future_weight_bad,
            future_good=future_weight_good,
        )
