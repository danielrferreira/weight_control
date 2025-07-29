import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from sklearn.preprocessing import MinMaxScaler
import json
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

service_account_info = st.secrets["google_drive"]

credentials = Credentials.from_service_account_info(service_account_info, scopes=["https://www.googleapis.com/auth/drive"])
drive_service = build("drive", "v3", credentials=credentials)

def read_csv_from_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    return pd.read_csv(fh)

class wana:
    def __init__(self, file_id, measurement='lbs', param='forecast_model/model_parameters_reg_prod.json'):
        self.file_id = file_id
        self.param = param
        self.measurement = measurement
        df = read_csv_from_drive(file_id)
        df.index = pd.to_datetime(df['date'])
        self.raw_df = df
        df['weight_kgs'] = df['weight_lbs'] * 0.453592
        df = df.drop(['date'], axis=1)
        df = df.sort_index()
        if self.measurement=='kgs':
            self.weight_col = 'weight_kgs'
            self.weight_goal = 70
            self.weight_min = df['weight_kgs'].min()
        else:
            self.weight_col = 'weight_lbs'
            self.weight_goal = 154.324
            self.weight_min = df['weight_lbs'].min()
        for col in ['weight_lbs', 'weight_kgs', 'food', 'exer']:
            df[f'{col}_avg_7d'] = df[col].rolling(window=7).mean()
        scaler = MinMaxScaler()
        for col in ['food_avg_7d','exer_avg_7d']:
            df[col] = scaler.fit_transform(df[col].values.reshape(-1, 1))
        df['food_exercise_avg_7d'] = 0.7*df['food_avg_7d'] + 0.3*df['exer_avg_7d']
        self.df = df
        self.today = pd.Timestamp('today')
        self.last_weight = df['weight_lbs'].iloc[-1]
    
    def last_n(self, n):
        df_n = self.df.sort_index(ascending=False).head(n)
        output = df_n[[self.weight_col, 'food', 'exer', f'{self.weight_col}_avg_7d',  'food_avg_7d', 'exer_avg_7d']]
        return output

    def change_measurement(self, measurement):
        self.measurement = measurement
        self.weight_col = 'weight_kgs' if measurement == 'kgs' else 'weight_lbs'
        self.weight_goal = 70 if measurement == 'kgs' else 154.324
        return
    
    def find_missing(self):
        today = self.today
        full_date_range = pd.date_range(start=self.df.index.min(), end=today, freq='D')
        missing_dates = full_date_range.difference(self.df.index)
        return missing_dates

    def plot(self):
        fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, figsize=(12, 15), sharex=True)
        ax1.plot(self.df.index, self.df[self.weight_col], label=f'Weight ({self.measurement})', color='blue', linewidth=2)
        ax1.plot(self.df.index, self.df[f'{self.weight_col}_avg_7d'], label='Weight (7-day Avg)', color='red', linestyle='--', linewidth=2)
        ax1.axhline(y=self.weight_goal, color='gray', linestyle=':')
        ax1.axhline(y=self.weight_min, color='red', linestyle=':')
        ax1.set_ylabel(f'Weight ({self.measurement})', fontsize=12)
        ax1.set_title('Weight Trends', fontsize=14)
        
        ax2.plot(self.df.index, self.df['food_exercise_avg_7d'], label='Food and Exercise (7-day Avg)', color='green', linewidth=2)
        ax2.set_ylabel('Food & Exercise Averaged', fontsize=12)
        ax2.legend(loc='upper left', fontsize=10)
        ax2.set_title('Food and Exercise Average Trends', fontsize=14)

        ax3.plot(self.df.index, self.df['food_avg_7d'], label='Food (7-day Avg)', color='blue', linewidth=2)
        ax3.plot(self.df.index, self.df['exer_avg_7d'], label='Exercise (7-day Avg)', color='green', linewidth=2)
        ax3.set_ylabel('Food & Exercise (scaled)', fontsize=12)        
        ax3.set_title('Food and Exercise Trends', fontsize=14)

        for ax in (ax1, ax2, ax3):
            ax.legend(loc='upper left', fontsize=10)
            ax.grid(alpha=0.3)

        plt.xlabel('Date', fontsize=12)
        plt.tight_layout()
        plt.show()
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
        drive_service.files().update(fileId=self.file_id, media_body=media).execute()
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
        plt.figure(figsize=(10, 6))
        plt.plot(self.df.index, self.df[f'{self.weight_col}_avg_7d'], label=f'Weight {self.measurement} Avg (7d)', color='blue')
        plt.plot(interpolated_df.index, interpolated_df['weight_gain_expected'], label='Expected Weight Gain', linestyle='--', color='green')
        plt.plot(interpolated_df.index, interpolated_df['weight_gain_bad'], label='Weight Gain (Bad Food and Exercise)', linestyle='--', color='red')
        plt.plot(interpolated_df.index, interpolated_df['weight_gain_good'], label='Weight Gain (Good Food and Exercise)', linestyle='--', color='orange')
        plt.axhline(y=self.weight_goal, color='gray', linestyle=':')
        plt.text(future_date, future_weight_expected, f'{future_weight_expected:.2f}', color='green', fontsize=10, ha='left')
        plt.text(future_date, future_weight_bad, f'{future_weight_bad:.2f}', color='red', fontsize=10, ha='left')
        plt.text(future_date, future_weight_good, f'{future_weight_good:.2f}', color='orange', fontsize=10, ha='left')
        plt.xlabel('Date')
        plt.ylabel(f'Weight ({self.measurement})')
        plt.title('Weight Analysis with Interpolation')
        plt.legend()
        plt.grid(True)
        return plt

        




        