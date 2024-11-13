# -*- coding: utf-8 -*-
"""
Created on Thu Oct 31 10:56:15 2024
Export defined favorites from WEAP for multiple runs, compare them, and produce
regression testing results.
@author: zzhang
"""

import os
import string
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_percentage_error,mean_squared_error
from scipy.stats import linregress
import openpyxl
from openpyxl.styles import Font
import weapapi

#%% Input Section
# Defines a list of favorites to compare.
favorites = ["Canal Flows","COA","SW Storage","SWRCB IFR Flows"]
# Defines a list of scenarios to compare.
scenarios = ["Existing"]
# Define the thresholds for anomaly detection; comment out the metrics if not needed.
metrics_threshold = {"mean squared error":2.0,   #mean squared error
                     #"mape":0.1, #mean_absolute_percentage_error
                     "mean error": 2.0,  # mean error
                     "mean percent error": 0.05, #mean percent error
                     "correcoef":0.9, # correlation coefficient
                     "skill score":0.9} # Nash-Sutcliffe-like skill score based on mean squared error
# by default, comparisons between only two runs are allowed.
runs = ['2024-10-24 (1)','2024-10-24 (2)']
#Define output path for the favorites.
output_path = "../results"
#If results already exist, overwrite or not.
overwrite_results = False
# set favorite unit: this will slow down the script by about 10 seconds.
favorite_unit = 'taf' # Only 'taf' and 'cfs' are implemented. When favorite units are inconsistent across different varaibles, set it to None.

#%% export WEAP favorites for different scenarios and runs.
# WEAP.export_favorite does not seem to support parallel operation.
for s in scenarios:
    for f in favorites:
        for r in runs:
            path = os.path.join(output_path,r)
            # Inser the command to choose a particular run.
            if not os.path.exists(path):
                os.mkdir(path)
            filename = os.path.join(path,"%s_%s.csv"%(f,s))
            write = True
            if os.path.exists(filename):
                if not overwrite_results:
                    write = False
            if write:
                weapapi.export_favorite(f,s,filename,run=r)

#%% Section with metrics functions from vtools
def mse(targets,predictions):
    """Mean squared error

        This function is taken from vtools3: https://github.com/CADWRDeltaModeling/vtools3/blob/master/vtools/functions/skill_metrics.py

       Parameters
       ----------
       predictions, targets : array_like
           Time series or arrays to analyze

       Returns
       -------
       mse : vtools.data.timeseries.TimeSeries
           Mean squared error between predictions and targets
    """
    return ((predictions - targets)**2.).mean()


def skill_score(targets,predictions,ref=None):
    """Calculate a Nash-Sutcliffe-like skill score based on mean squared error

       As per the discussion in Murphy (1988) other reference forecasts (climatology,
       harmonic tide, etc.) are possible.
       For some reason r2_score from scipy gives the same results as this function.

       This function is taken from vtools3: https://github.com/CADWRDeltaModeling/vtools3/blob/master/vtools/functions/skill_metrics.py

       Parameters
       ----------
       predictions, targets : array_like
           Time series or arrays to be analyzed

       Returns
       -------
       rmse : float
           Root mean squared error
    """
    if (targets==predictions).all(): #in case some values are zero
        return 1.0
    else:
        if not ref:
            ref = targets.mean()
        return 1.0 - (mse(predictions,targets)/mse(ref,targets))

def mape(targets,predictions):
    if (targets==predictions).all(): #in case some values are zero
        return 0.0
    else:
        return mean_absolute_percentage_error(targets,predictions)

def me(targets,predictions):
    return (predictions.mean()-targets.mean())

def mpe(targets,predictions):
    if (targets==predictions).all(): #in case some values are zero
        return 0.0
    else:
        return (predictions.mean()-targets.mean())/predictions.mean()

def correcoef(targets,predictions):
    if (targets==predictions).all(): #in case some values are zero
        return 1.0
    else:
        result = linregress(ytrue,ypred)
        return result.rvalue

def metrics_calculator(options):
    metrics = {
    'mean squared error': mean_squared_error,
    "mean percent error": mpe,
    "mean error": me,
    'correcoef': correcoef,
    'skill score': skill_score
    }
    methods = [metrics[m] for m in options]
    return methods

methods = metrics_calculator(metrics_threshold.keys())

#%% Load and perform metrics calculations to all scenarios
metrics_path = os.path.join(output_path,'metrics')
if not os.path.exists(metrics_path):
    os.mkdir(metrics_path)

alphabet = string.ascii_uppercase
excel_cols = [alphabet[i+1] for i in range(len(methods))]
for s in scenarios:
    dfm_list = []
    hl_list = []
    for f in favorites:
        df_list = []
        for r in runs:
            path = os.path.join(output_path,r)
            filename = os.path.join(path,"%s_%s.csv"%(f,s))
            if favorite_unit is None:
                df = weapapi.read_favorite(filename)
            else:
                df = weapapi.read_favorite(filename,unit=favorite_unit)
            df_list.append(df)
        # make sure that we are only comparing two runs.
        assert(len(df_list)==2)

        df1 = df_list[0]
        df2 = df_list[1]
        # Convert to numeric, coercing non-numeric values to NaN
        df1 = df1.apply(pd.to_numeric, errors='coerce').dropna(axis=1)
        df2 = df2.apply(pd.to_numeric, errors='coerce').dropna(axis=1)
        vind = (df1-df2).dropna().index
        #make sure that the two time series have the same time dimension
        df1 = df1.loc[vind]
        df2 = df2.loc[vind]
        # if df1 and df2 do not have the same columns, only compare those exist in both
        if not (df1.columns == df2.columns).all():
            common_columns = df1.columns.intersection(df2.columns)
            df1 = df1[common_columns]
            df2 = df2[common_columns]
        cols = df1.columns

        dfm_all = []
        cindex = [] # the row index with values that exceed the thresholds
        for method,k, excel_col in zip(methods,metrics_threshold.keys(),
                                       excel_cols):
            names = []
            values = []
            for ci,c in enumerate(cols):
                ytrue = df1[c]
                ypred = df2[c]
                name = ytrue.name
                value = method(ytrue,ypred)
                names.append(name)
                values.append(value)
                if k.endswith('score') or k=="correcoef":
                    if value<metrics_threshold[k]:
                        cindex.append("%s%s"%(excel_col,ci+2))
                elif (k=='mean error') or (k=='mean percent error'):
                    if np.abs(value)>metrics_threshold[k]:
                        cindex.append("%s%s"%(excel_col,ci+2))
                else:
                    if value>metrics_threshold[k]:
                        cindex.append("%s%s"%(excel_col,ci+2))
            df_metrics = pd.DataFrame({'columns':names,k:values})
            dfm_all.append(df_metrics.set_index('columns'))
        dfm_joined = pd.concat(dfm_all,join='outer',axis=1)
        dfm_list.append(dfm_joined)
        hl_list.append(cindex)

    fn_metrics = os.path.join(metrics_path,"full_report_%s.xlsx"%s)
    with pd.ExcelWriter(fn_metrics) as writer:
        for i,f in enumerate(favorites):
            dfm_list[i].to_excel(writer,
                              float_format="%.3f",sheet_name=f)

    # highlight those cells that exceed the threshold
    # Load the workbook
    workbook = openpyxl.load_workbook(fn_metrics)
    for i, f in enumerate(favorites):
        # Select the sheet
        sheet = workbook[f]
        #auto fit
        for column in sheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            sheet.column_dimensions[column_letter].width = adjusted_width

        # change the cell font
        for  chl in hl_list[i]:
            cell = sheet[chl]
            cell.font = Font(color='FF0000', bold=True)  # Red color
    # Save the workbook
    workbook.save(fn_metrics)