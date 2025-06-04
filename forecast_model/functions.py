import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
import matplotlib.pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.stattools import adfuller, kpss
import warnings

def all_ac(Y, lags=15):
    fig, ax = plt.subplots(1, 2, figsize=(16, 5))
    plot_acf(Y, zero=False, ax=ax[0], lags=lags)
    ax[0].set_title('ACF')
    plot_pacf(Y, zero=False, ax=ax[1], lags=lags)
    ax[1].set_title('PACF')
    plt.show()

def plot_forecast(original, prediction):
    plt.plot(original, label='Actual', linestyle='-')
    plt.plot(prediction, label='Prediction', linestyle='--')
    plt.xlabel('Date')
    plt.ylabel('Values')
    plt.title('Actual + Prediction')
    plt.legend()
    plt.show()

def stationarity_test(s):
    warnings.simplefilter("ignore", category=UserWarning)
    kps = kpss(s)
    adf = adfuller(s)
    warnings.simplefilter("default", category=UserWarning)
    kpss_pv, adf_pv = kps[1], adf[1]
    kpssh, adfh = 'Stationarity', 'Non-Stationarity'
    if adf_pv < 0.05:
        adfh = 'Stationarity'
    if kpss_pv < 0.05:
        kpssh = 'Non-Stationarity'
    return (kpssh, adfh)

def diagnostic(model, lags=15):
    print(model.summary())
    model.plot_diagnostics()
    plt.show()
    resid = model.resid
    resid = resid[1:]
    all_ac(resid, lags=lags)
    plt.show()

def compare_predictions(actual, prediction_list, model_list):
    plt.plot(actual, label='Actual', linestyle='-')
    colors = ['blue', 'green', 'red', 'cyan', 'magenta', 'yellow', 'black']
    for i, (p, m) in enumerate(zip(prediction_list, model_list)):
        plt.plot(p, label=m, linestyle='--', color=colors[i % len(colors)])
    plt.xlabel('Date')
    plt.ylabel('Value')
    plt.title('Actual + Prediction')
    plt.legend()
    plt.show()

def cross_correl(y,x, max_lags = 24, titulo = 'Cross Correlation'):
    correl = []
    lags = range(-max_lags, max_lags + 1)
    for l in lags:
        c = y.corr(x.shift(l))
        correl.append(c)
    plt.figure(figsize=(10, 5))
    plt.stem(lags, correl)
    plt.xlabel('Lag')
    plt.title(titulo)
    conf_interval = 1.96 / np.sqrt(len(y))
    plt.axhline(-conf_interval, color='k', ls='--')
    plt.axhline(conf_interval, color='k', ls='--')
    plt.show()
    
def compare_stats(model_list, model_list_names):
    for m,n in zip(model_list, model_list_names):
        rmse = round(np.sqrt(np.mean(m.resid**2)))
        bic = round(m.bic)
        aic = round(m.aic)
        print(f'BIC = {bic} -- AIC = {aic} --  RMSE = {rmse} - {n}')