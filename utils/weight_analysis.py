import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from sklearn.preprocessing import MinMaxScaler

class wana:
    def __init__(self, file):
        self.file = file 
        df = pd.read_csv(file)
        df.index = pd.to_datetime(df['date'])
        self.raw_df = df
        df = df.drop(['date', 'avg_7d'], axis=1)
        df = df.sort_index()
        for col in ['weight_lbs', 'food', 'exer']:
            df[f'{col}_avg_7d'] = df[col].rolling(window=7).mean()
        scaler = MinMaxScaler()
        for col in ['food_avg_7d','exer_avg_7d']:
            df[col] = scaler.fit_transform(df[col].values.reshape(-1, 1))
        df['food_exercise_avg_7d'] = (df['food_avg_7d'] + df['exer_avg_7d']) / 2
        self.df = df
    
    def find_missing(self):
        today = pd.Timestamp('today')
        full_date_range = pd.date_range(start=self.df.index.min(), end=today, freq='D')
        missing_dates = full_date_range.difference(self.df.index)
        return missing_dates

    def plot(self):
        fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, figsize=(12, 15), sharex=True)
        ax1.plot(self.df.index, self.df['weight_lbs'], label='Weight (lbs)', color='blue', linewidth=2)
        ax1.plot(self.df.index, self.df['weight_lbs_avg_7d'], label='Weight (7-day Avg)', color='red', linestyle='--', linewidth=2)
        ax1.set_ylabel('Weight (lbs)', fontsize=12)
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
        temp = pd.DataFrame({'date': [date], 'weight_lbs':[weight], 'exer':[exercise], 'food': [food], 'avg_7d':[pd.NA] })
        temp.index = pd.to_datetime(temp['date'])
        df = pd.concat([self.raw_df, temp])
        df = df.sort_index()
        df.to_csv(self.file, index=False)
        return "Table Updated"


        