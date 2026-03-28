import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from sklearn.preprocessing import MinMaxScaler
import json
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

_PALETTE = {
    'weight':      '#4C72B0',  # steel blue    — raw weight line
    'avg_7d':      '#DD8452',  # warm orange   — 7-day moving average
    'goal_band':   '#C8E6C9',  # soft green    — goal band fill
    'min_line':    '#E57373',  # muted rose    — personal minimum
    'food':        '#55A868',  # sage green    — food avg
    'exercise':    '#C44E52',  # muted crimson — exercise avg
    'combined':    '#8172B2',  # violet        — food+exercise combined
    'std':         '#64B5CD',  # sky blue      — std deviation
    'goal_line':   '#B0BEC5',  # light slate   — goal reference lines
    'fc_hist':     '#4C72B0',  # steel blue    — historical in forecast
    'fc_expected': '#55A868',  # sage green    — expected forecast
    'fc_bad':      '#C44E52',  # muted crimson — bad scenario
    'fc_good':     '#8172B2',  # violet        — good scenario
}

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

    def plot(self):
        with plt.style.context('dark_background'):
            fig, (ax1, ax2, ax3, ax4) = plt.subplots(nrows=4, ncols=1, figsize=(14, 20), sharex=True)
            fig.patch.set_facecolor('#0E1117')
            for ax in (ax1, ax2, ax3, ax4):
                ax.set_facecolor('#1C2231')

            ax1.plot(self.df.index, self.df[self.weight_col], label=f'Weight ({self.measurement})', color=_PALETTE['weight'], linewidth=1.5, alpha=0.6)
            ax1.plot(self.df.index, self.df[f'{self.weight_col}_avg_7d'], label='7-day Avg', color=_PALETTE['avg_7d'], linewidth=2.5)
            x_end = self.df.index[-1] + pd.Timedelta(weeks=2)
            ax1.fill_between([self.df.index[0], x_end], self.weight_goal - self.weight_goal_band, self.weight_goal + self.weight_goal_band, color=_PALETTE['goal_band'], alpha=0.2, label='Goal range')
            ax1.axhline(y=self.weight_min, color=_PALETTE['min_line'], linestyle=':', linewidth=1.5, label='Personal min')
            ax1.set_ylabel(f'Weight ({self.measurement})', fontsize=12)
            ax1.set_title('Weight Trends', fontsize=14, fontweight='semibold')

            ax2.plot(self.df.index, self.df['food_exercise_avg_7d'], label='Food & Exercise (7-day Avg)', color=_PALETTE['combined'], linewidth=2.5)
            ax2.set_ylabel('Food & Exercise Averaged', fontsize=12)
            ax2.set_title('Food and Exercise Average Trends', fontsize=14, fontweight='semibold')

            ax3.plot(self.df.index, self.df['food_avg_7d'], label='Food (7-day Avg)', color=_PALETTE['food'], linewidth=2.5)
            ax3.plot(self.df.index, self.df['exer_avg_7d'], label='Exercise (7-day Avg)', color=_PALETTE['exercise'], linewidth=2.5)
            ax3.set_ylabel('Food & Exercise (scaled)', fontsize=12)
            ax3.set_title('Food and Exercise Trends', fontsize=14, fontweight='semibold')

            ax4.plot(self.df.index, self.df[f'{self.weight_col}_std_21d'], label='21-day Std Dev', color=_PALETTE['std'], linewidth=2.5)
            ax4.set_ylabel('Weight Standard Deviation', fontsize=12)
            ax4.set_title('Weight Volatility (21-day Std Dev)', fontsize=14, fontweight='semibold')

            for ax in (ax1, ax2, ax3, ax4):
                ax.legend(loc='upper right', fontsize=10, framealpha=0.3)
                ax.spines[['top', 'right']].set_visible(False)
                ax.grid(color='#2A3347', linewidth=0.8)

            plt.xlabel('Date', fontsize=12)
            plt.tight_layout()
            return fig
    
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
        if self.measurement=='kgs':
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
        with plt.style.context('dark_background'):
            fig, ax = plt.subplots(figsize=(14, 5))
            fig.patch.set_facecolor('#0E1117')
            ax.set_facecolor('#1C2231')
            ax.plot(self.df.index, self.df[f'{self.weight_col}_avg_7d'], label=f'Weight {self.measurement} Avg (7d)', color=_PALETTE['avg_7d'], linewidth=2.5)
            ax.plot(interpolated_df.index, interpolated_df['weight_gain_expected'], label='Expected', linestyle='--', color=_PALETTE['fc_expected'], linewidth=2)
            ax.plot(interpolated_df.index, interpolated_df['weight_gain_bad'], label='Pessimistic', linestyle='--', color=_PALETTE['fc_bad'], linewidth=2)
            ax.plot(interpolated_df.index, interpolated_df['weight_gain_good'], label='Optimistic', linestyle='--', color=_PALETTE['fc_good'], linewidth=2)
            ax.fill_between(interpolated_df.index, interpolated_df['weight_gain_bad'], interpolated_df['weight_gain_good'], alpha=0.08, color=_PALETTE['fc_expected'], label='_nolegend_')
            x_end = future_date + pd.Timedelta(weeks=4)
            ax.fill_between([self.df.index[0], x_end], self.weight_goal - self.weight_goal_band, self.weight_goal + self.weight_goal_band, color=_PALETTE['goal_band'], alpha=0.2, label='_nolegend_')
            ax.axhline(y=self.weight_min, color=_PALETTE['min_line'], linestyle=':', linewidth=1.5, label='Personal min')
            ax.set_xlim(right=x_end)
            ax.text(future_date, future_weight_expected, f'{future_weight_expected:.2f}', color=_PALETTE['fc_expected'], fontsize=10, ha='left', fontweight='semibold')
            ax.text(future_date, future_weight_bad, f'{future_weight_bad:.2f}', color=_PALETTE['fc_bad'], fontsize=10, ha='left', fontweight='semibold')
            ax.text(future_date, future_weight_good, f'{future_weight_good:.2f}', color=_PALETTE['fc_good'], fontsize=10, ha='left', fontweight='semibold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel(f'Weight ({self.measurement})', fontsize=12)
            ax.set_title('Weight Forecast', fontsize=14, fontweight='semibold')
            ax.legend(loc='upper right', fontsize=10, framealpha=0.3)
            ax.spines[['top', 'right']].set_visible(False)
            ax.grid(color='#2A3347', linewidth=0.8)
            plt.tight_layout()
            return fig

        




        
