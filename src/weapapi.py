# -*- coding: utf-8 -*-
"""
Created on Tue Oct  8 11:52:08 2024
Functions to interact with weapapi
@author: zzhang
"""

import warnings
import pythoncom
from pathlib import Path
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import win32com.client

WEAP = win32com.client.Dispatch("WEAP.WEAPApplication")
WEAP.Verbose = 0
keys = ['Demand Sites and Catchments', 'Hydrology', 'Key', 'Other',
       'Supply and Resources', 'User Defined LP Constraints']

def create_object():
    """
    Create a WEAP object.
    Returns
    -------
    WEAP : WEAP object.

    """
    WEAP = win32com.client.Dispatch("WEAP.WEAPApplication")
    return WEAP

def get_key(branch):
    """
    Get level 1 (or key) of a branch.
    Parameters
    ----------
    branch : branch with/without variable.

    Returns
    -------
    branch key.

    """
    return branch.split("\\")[0]

def get_keys():
    """
    Get keys for the entire WEAP data tree.
    Note that this function can be slow.

    Returns
    -------
    keys : list
        A list of branch keys.

    """
    branchlist = get_branchlist()
    keys = np.unique([b.split("\\")[0] for b in branchlist])
    return keys

def get_branchlist(key=None):
    """
    Export full branch list in WEAP or a high level object branch

    Parameters
    ----------
    key : branch key or a higher level branch

    Returns
    -------
    branchlist : List
        A list of branches under the key or high level branch.

    """
    if key is None:
        branches = WEAP.Branches
        namelist = branches.FullNameList.split(",")
    else:
        branches = WEAP.Branch("\%s"%key)
        namelist = branches.Descendants.FullNameList.split(",")
    keys = np.unique([b.split("\\")[0] for b in namelist])
    # remove the key branches: these will cause an error when trying to retrieve values.
    [namelist.remove(k) for k in keys if k in namelist]
    # remove water quality
    [namelist.remove(k) for k in namelist if get_key(k)=="Water Quality"]
    branchlist = np.array(namelist)
    return branchlist

def read_value_stats(branch,scenario,start_wy=None,start_ts=None,end_wy=None,
                     end_ts=None,method=None,percentage=None):
    """
    read values within a time range and apply a statistic method to obtain a
    single value. Default method is sum. Other available methods include:
    average, and percentile (percentage is required as input)

    Parameters
    ----------
    branch : STRING
        Branch with variable name.
    scenario : str
    start_wy : int, optional
        Start water year. The default is WEAP base year.
    start_ts : int, optional
        Start time step The default is 1.
    end_wy : int, optional
        End water year. The default is WEAP end year.
    end_ts : int, optional
        End time step. The default is 12.
    method : str, optional
        'sum','average',or percentile. The default is sum.
    percentage : str, optional
        Only required if method=='percentile'. The default is None.

    Returns
    -------
    value : float
    unit : str

    """
    b,var = branch.split(":")
    b = b.strip()
    var = var.strip()
    if not WEAP.BranchExists(b):
        raise ValueError("Branch %s does not exist!"%b)
    br = WEAP.Branch(b)
    if not br.VariableExists(var):
        raise ValueError("Value %s does not exist!"%var)

    if start_wy is None:
        start_wy = WEAP.BaseYear
    if end_wy is None:
        end_wy = WEAP.EndYear
    if start_ts is None:
        start_ts = 1
    if end_ts is None:
        end_ts = WEAP.NumTimeSteps
    if method is None:  # None means sum.
        try:
            #value = WEAP.ResultValue(b,start_wy,start_ts,scenario,end_wy,
            #                 end_ts)
            value = br.Variable(var).ResultValue(start_wy,start_ts,scenario,
                                                 end_wy,end_ts)
            unit = br.Variable(var).Unit
            scale = br.Variable(var).Scale
            value = value*scale
        except pythoncom.com_error:
            value = np.nan
            print("None value found for %s"%b)
    elif method == "Average":
        try:
            #value = WEAP.ResultValue(b,start_wy,start_ts,scenario,end_wy,
            #                 end_ts,method)
            value = br.Variable(var).ResultValue(start_wy,start_ts,scenario,
                                                 end_wy,end_ts,method)
            unit = br.Variable(var).Unit
            scale = br.Variable(var).Scale
            value = value*scale
        except pythoncom.com_error:
            value = np.nan
            print("None value found for %s"%b)
    elif method == "Percentile":
        try:
            #value = WEAP.ResultValue(b,start_wy,start_ts,scenario,end_wy,
            #                 end_ts,method,percentage)
            value = br.Variable(var).ResultValue(start_wy,start_ts,scenario,
                                                 end_wy,end_ts,method,percentage)
            unit = br.Variable(var).Unit
            scale = br.Variable(var).Scale
            value = value*scale
        except pythoncom.com_error:
            value = np.nan
            unit = ''
            print("None value found for %s"%b)
    else:
        raise("Invalid method: only accepts Average and Percentile")
    return value,unit

def get_varnames(branch,result=None):
    """
    Retrieve all variable names for a given branch (branch without variable)

    Parameters
    ----------
    branch : str
        Input branch without variable.
    result : optional, Default is None
        True, False or None. The default is False.
        True: only shows variable names related to result.
        False: only shows variable names unrelated to result.
        None: shows all variable names.
    Returns
    -------
    varname : list
        A list of variable names

    """
    varname = []
    for v in WEAP.Branch(branch).Variables:
        if result is None:
            varname.append(v.Name)
        elif result:
            if (not v.IsReadOnly) and (v.IsResultVariable):
                varname.append(v.Name)
        else:
            if (not v.IsReadOnly) and (not v.IsResultVariable):
                varname.append(v.Name)
    return varname


def get_children(branch):
    """
    Get children of a high level branch

    """
    branches = [b.FullName for b in WEAP.Branch(branch).Children]
    return branches

def compare_inputs(input1,input2):
    """
    Compare two input expression tables generated by WEAP.

    Parameters
    ----------
    input1 : str
        csv filename for input 1.
    input2 : str
        csv filename for input 2.

    Returns
    -------
    pandas dataframe
        The difference between the two inputs

    """
    if isinstance(input1,str):
        df1 = pd.read_csv(input1)
    else:
        df1 = input1
    if isinstance(input2,str):
        df2 = pd.read_csv(input2)
    else:
        df2 = input2
    ds1 = df1.set_index('branches')['expressions']
    ds2 = df2.set_index('branches')['expressions']
    ds1 = ds1.drop_duplicates(keep='first')
    ds2 = ds2.drop_duplicates(keep='first')
    dfc = pd.concat([ds1,ds2],axis=1,keys=['df1','df2'],join="outer")
    return dfc[dfc.df1!=dfc.df2]

def weapym2ym(wy,timestep):
    """
    calculate calendar year month based on sacwam water year and time step.

    Parameters
    ----------
    wy : int
        Water year.
    timestep : int
        Time step (1 to 12).

    Returns
    -------
    yc : int
        Calendar year.
    mc : int
        Calendar month.

    """
    #
    mc = timestep+WEAP.WaterYearStart - 1
    if mc>WEAP.NumTimeSteps:
        mc = mc-WEAP.NumTimeSteps
        yc = wy
    else:
        yc = wy-1
    return yc,mc

def ym2weapym(yc,mc):
    """
    calculate sacwam water year and timestep based on calendar year month

    Parameters
    ----------
    yc : int
        Calendar year.
    mc : int
        Calendar month.

    Returns
    -------
    wy : int
        Water year.
    timestep : int
        Time step.

    """
    if mc< WEAP.WaterYearStart:
        wy = yc
        timestep = mc+(WEAP.NumTimeSteps-WEAP.WaterYearStart+1)
    else:
        wy = yc+1
        timestep = mc-WEAP.WaterYearStart +1
    return wy,timestep

def read_value(branch,yr,mr,scen):
    """
    retrieve a single value for a particular scenario, calendar year, month, and branch.

    Parameters
    ----------
    branch : str
        branch with variable name.
    yr : int
        calendar year.
    mr : int
        calendar month.
    scen : str
        Scenario.

    Returns
    -------
    value : float
    unit : str

    """
    b,var = branch.split(":")
    b = b.strip()
    var = var.strip()
    if not WEAP.BranchExists(b):
        raise ValueError("Branch %s does not exist!"%b)
    br = WEAP.Branch(b)
    if not br.VariableExists(var):
        raise ValueError("Value %s does not exist!"%var)
    wy,ts = ym2weapym(yr,mr)
    value = br.Variable(var).ResultValue(wy,ts,scen)
    unit = br.Variable(var).Unit
    scale = br.Variable(var).Scale
    value = value*scale
    return value,unit

def read_value_ts(branch,scenario,start_date=None,end_date=None):
    """
    retrieve a timeseries for a particular scenario, calendar year, month, and branch.

    Parameters
    ----------
    branch : str
        branch with variable name.
    scen : str
        Scenario.
    start_date : str, optional
        '1998-10-01'. The default is the begining of the simulation.
    end_date : str, optional
        '2000-10-01'. The default is the end of the simulation.

    Returns
    -------
    df : Pandas DataFrame
        with column 'values' and 'units'.

    """
    b,var = branch.split(":")
    b = b.strip()
    var = var.strip()
    if not WEAP.BranchExists(b):
        raise ValueError("Branch %s does not exist!"%b)
    br = WEAP.Branch(b)
    if br.VariableExists(var):
        if start_date is None:
            yr,mr = weapym2ym(WEAP.BaseYear, 1)
            start_date = pd.to_datetime("%s-%s-01"%(yr,mr))
        if end_date is None:
            yr,mr = weapym2ym(WEAP.EndYear,WEAP.NumTimeSteps)
            end_date = pd.to_datetime("%s-%s-01"%(yr,mr))
        datetimes = pd.date_range(start_date,end_date,freq='M')
        values = []
        units = []
        for d in datetimes:
            wy,timestep = ym2weapym(d.year,d.month)
            value = br.Variable(var).ResultValue(wy,timestep,scenario)
            unit = br.Variable(var).Unit
            scale = br.Variable(var).Scale
            values.append(value*scale)
            units.append(unit)
        df = pd.DataFrame({'values':values,'units':units},
                          index=datetimes)
    else:
        raise ValueError("Variable %s does not exist!"%var)
    return df

def tocfs(df):
    """
    Unit convertion from m^3 or taf to cfs
    Input dataframe must have column fields: values and units, with datatime as index.
    """
    secondsinmonth = df.name.days_in_month*24*3600
    if df['units'].lower() == "m^3":
        df['values'] = df['values']*35.3147/secondsinmonth
    elif (df['units'].lower() == 'cfs') or \
        (df['units'].lower() == 'cubic feet per second'):
        pass
    elif (df['units'].lower() == 'taf') or \
        ((df['units'].lower() == 'thousand acre feet') )\
            ((df['units'].lower() == 'thousand af') ):
        cfs2taf = 2.29569e-8*secondsinmonth
        df['values'] = df['values']/cfs2taf
    else:
        raise NotImplementedError("unit conversion for %s not Implemented"%df.unit)
    df['units'] = 'cfs'
    return df

def totaf(df):
    """
    Unit convertion from m^3 or cfs to taf
    Input dataframe must have column fields: values and units, with datatime as index.
    """
    if (df['units'].lower() =='taf') or \
        ((df['units'].lower() == 'thousand acre feet') ) or \
        ((df['units'].lower() == 'thousand af') ):
        pass
    elif df['units'].lower() =='m^3':
        df['values'] = df['values']*0.8107132*1e-6
    elif (df['units'].lower() =='cfs') or \
        (df['units'].lower() =='cubic feet per second'):
        secondsinmonth = df.name.days_in_month*24*3600
        cfs2taf = 2.29569e-8*secondsinmonth
        df['values'] = df['values']*cfs2taf
    elif df['units'].lower() == 'af':
        df['values'] = df['values']/1000.0
    else:
        raise NotImplementedError("unit conversion for %s not Implemented"%df['units'])
    df['units'] = 'taf'
    return df

def get_demand(demand_site,scenario,unit="cfs",start_date=None,end_date=None,
               include_loss=False):
    """
    Retrieve water demand for a particular demand site

    Parameters
    ----------
    demand_site : str
    scenario : str
    unit : str, optional
        Output unit. The default is "cfs".
    start_date : str, optional
        '1998-10-01'. The default is the begining of the simulation.
    end_date : str, optional
        '2000-10-01'. The default is the end of the simulation.
    include_loss : boolean, optional
        If transmission loss is included. The default is False.

    Returns
    -------
    df : Pandas DataFrame
        with column 'values' and 'units'.

    """
    b = "Demand Sites and Catchments\\" + demand_site
    if not include_loss:
        var = 'Water Demand'
    else:
        var = 'Supply Requirement'
    branch = "%s:%s"%(b,var)
    df = read_value_ts(branch,scenario,start_date,end_date)
    if unit=='cfs':
        df = df.apply(tocfs,axis=1)
    elif unit=='taf':
        df = df.apply(totaf,axis=1)
    return df

def favorites_names():
    """
    Returns
    -------
    fnames : list
        Return a list of favorites defined in WEAP
    """

    fnames = []
    for f in WEAP.Favorites:
        fnames.append(f.Name)
    return fnames

def export_favorite(favorite,scenario,filename,run=None):
    """
    Export a favorite (note that this function cannot run in parallel)

    Parameters
    ----------
    favorite : str
    scenario : str
    filename : str
        Output filename in csv.
    run : str, optional
        The run name for an archive run. The default is None.

    Returns
    -------
    None.

    """
    filename = os.path.abspath(filename) #weap cannot recognize relative path and will default to a different path compared to cmd
    fnames = favorites_names()
    if favorite not in fnames:
        raise ValueError("input favorite does not exist: %s"%favorite)
    WEAP.Scenario(scenario).Activate()
    WEAP.LoadFavorite(favorite)
    #WEAP.ResultsExportPrecision = 4
    if run is not None:
        WEAP.SetResultSetting("Run",run)
    WEAP.ExportResults(filename, True, True,True,True,IncludeColUnits=True)
    return

def rename_branch(branch):
    """
    Rename the branch based on the actual keys in WEAP.
    """
    top_branch = Path(branch).parts[0]
    valid_branch = False
    if top_branch in keys:
        valid_branch = True
    if top_branch == 'Other Assumptions':
        branch = branch.replace('Other Assumptions','Other')
        valid_branch = True
    elif top_branch == 'Key Assumptions':
        branch = branch.replace('Key Assumptions','Key')
        valid_branch = True

    if valid_branch:
        return branch
    else:
        raise ValueError("The input branch is not valid. ")

def get_expression(branch,scenario="Existing",var=None):
    """
    Get the expression of a branch
    """
    branch = rename_branch(branch)
    varname = WEAP.Branch(branch).Variables
    b = WEAP.Branch(branch)
    WEAP.Scenario(scenario).Activate()
    if var is None and len(b.Variables)==1:
        return b.Variable(1).Expression
    elif var is not None:
        return b.Variable(var).Expression
    else:
        varname = get_varnames(branch,result=None)
        varnamelist = " ".join(varname)
        raise ValueError("please specify one variable name:" + varnamelist)

def set_expression(branch,new_expression,scenario="Existing",var=None):
    """
    Set the expression of a branch
    """
    branch = rename_branch(branch)
    varname = WEAP.Branch(branch).Variables
    b = WEAP.Branch(branch)
    WEAP.Scenario(scenario).Activate()
    if var is None and len(b.Variables)==1:
        b.Variable(1).Expression = new_expression
    elif var is not None:
        if b.VariableExists(var):
            b.Variable(var).Expression = new_expression
        else:
            varname = get_varnames(branch,result=None)
            varnamelist = " ".join(varname)
            raise ValueError("The input var does not exist. Choose one of the following: "+varnamelist)
    else:
        varname = get_varnames(branch,result=None)
        varnamelist = " ".join(varname)
        raise ValueError("please specify one variable name:" + varnamelist)

def rename_transmissionlink(branch):
    """
    Rename branch path to transmission link name in a style that matches export_favorite format.
    """
    branch = branch.split(":")[0]
    parts =  Path(branch).parts
    newname = "_".join(["transmission_link",parts[3],parts[2]]).lower().replace(" ","_")
    return newname

def get_storage(br_list,scenario):
    """
    Create a table with reservoir storage
    Parameters
    ----------
    br_list : LIST
        A list of branches for reservoirs.
    scenario : STR
        Model scenarios

    Returns
    -------
    df_sto : DataFrame
        Reservoir storage in TAF
    """

    df_list = []
    for l in br_list:
        b,var = l.split(":")
        name = b.split("\\")[-1]
        branch = "%s:%s"%(b,var)
        df = read_value_ts(branch,var,scenario)
        df = df.apply(totaf,axis=1)
        ds = df['values']
        ds.attrs['unit'] = 'taf'
        df_list.append(ds.to_frame(name))
    df_sto = pd.concat(df_list,axis=1)
    return df_sto

def get_unit(cname):
    """
    read the csv by export_favorites and derive units from column name
    """
    if '[' in cname:
        df_unit = cname.split("[")[1].split("]")[0]
    elif '(' in cname:
        df_unit = cname.split("(")[1].split(")")[0]
    else:
        df_unit = None
    return df_unit

def read_favorite(filename,unit=None):
    """
    read the csv file created by ExportFavorite.
    """
    with open(filename, 'r') as f:
        unit_line = None
        for i, line in enumerate(f):
            if '$Unit' in line:
                unit_line = line
            elif '$Columns' in line:
                #header = line
                linenum = i
                break
    df = pd.read_csv(filename,skiprows=linenum)
    df.loc[:,'datetime'] = pd.to_datetime(
        df['$Columns = Year'].astype(str) + '-' + df['Timestep'].astype(str) + '-01')
    df = df.set_index('datetime')
    df = df.drop(columns=['$Columns = Year','Timestep'])
    if unit is not None:
        if unit_line is not None:
            df_unit = unit_line.split("=")[1].split("\\")[0].strip().lower()
        else:
            df_unit = None
        for i, c in enumerate(df.columns):
            df_old = df[c].to_frame(name='values')
            if df_unit is None:
                df_unit = get_unit(c)
            if unit == 'taf':
                new_unit = 'Thousand Acre Feet'
                if (not new_unit in c) and (df_unit is not None):
                    old_unit = get_unit(c)
                    df_old.loc[:,'units'] = df_unit
                    df_new = df_old.apply(totaf,axis=1)
                    df.loc[:,c] = df_new['values']
                    if old_unit is not None:
                        df = df.rename(columns={
                            c:c.replace(old_unit,new_unit)})
            elif unit == 'cfs':
                new_unit = 'Cubic Feet per Second'
                if (not new_unit in c) and (df_unit is not None):
                    old_unit = get_unit(c)
                    df_new = df_old.apply(tocfs,axis=1)
                    df.loc[:,c] = df_new['values']
                    if old_unit is not None:
                        df = df.rename(columns={
                            c:c.replace(old_unit,new_unit)})
            else:
                if i==0:
                    warnings.warn(
                        "the input unit %s is ignored in read_favorite."%unit)
        if df_unit is None:
            warnings.warm("No unit found in file %s"%filename)
    return df

def exceedance_plot(data):
    """
    Create exceedance plot
    """
    # Sort data in descending order
    sorted_data = np.sort(data)[::-1]

    # Calculate exceedance probability
    exceedance_prob = np.arange(1, len(data) + 1) / len(data)

    # Create the plot
    plt.plot(exceedance_prob, sorted_data, marker='o')
    plt.ylabel('Value')
    plt.xlabel('Exceedance Probability')
    plt.title('Exceedance Plot')
    plt.show()


# def valid_expression(expression,b):
#     """
#     Check if an expression is valid

#     """
#     pathlist = ['Other'] + expression.split("\\")[1:-1]
#     cb = "\\".join(pathlist)
#     names = []
#     for n in WEAP.Branch(cb).Children:
#         names.append(n.Name)
#     if b.split("\\")[-1] in names:
#         return True
#     else:
#         return False

# def get_inputs(branchlist,scenario,get_value=False,drop_zero=True):
#     # get inputs either as expression or a mean value depending on the input.
#     expressions = []
#     branch_varlist = []
#     values = []
#     dtypes = []
#     for b in branchlist:
#         #if WEAP.Branch(b).TypeName=='Catchment':
#         #if get_key(b) in ['Supply and Resources','Demand Sites and Catchments']:
#         if not WEAP.Branch(b).IsVisible:
#             print("Branch %s invisible: skip this branch"%b)
#             continue
#         print("retrieving data from branch %s"%b)

#         if get_key(b) in ['Key','Hydrology']:
#             if get_value:
#                 value = read_value_stats(b,method="Average")
#                 dtype = "unknown"
#                 values.append(value)
#                 dtypes.append(dtype)
#             branch_varlist.append(b)
#             expressions.append("inaccessible")
#         else:
#             for v in WEAP.Branch(b).Variables:
#                 if v.IsResultVariable: #Getting inputs only for now
#                     #print("%s IsResultVariable: False"%v.Name)
#                     continue
#                 newb = b +":"+v.Name
#                 expression = v.Expression
#                 print(newb)
#                 if get_value:
#                     if v.Name=="Loss to Groundwater":
#                         valid = valid_expression(expression,b)
#                         if not valid:
#                             continue

#                     try:
#                         value = float(expression)
#                         dtype = "value"
#                         if value==0.0:
#                             continue #skip the 0 values (these variables are not assigned)
#                     except ValueError:
#                         value = read_value_stats(newb,method="Average")
#                         if value==0:
#                             value2 = read_value_stats(newb,method="Percentile",percentage=90)
#                             if value2==0:
#                                 continue # skip all zero values.
#                         dtype = "array"
#                 expressions.append(expression)
#                 branch_varlist.append(newb)
#                 if get_value:
#                     values.append(value)
#                     dtypes.append(dtype)
#     df = pd.DataFrame({'branches':branch_varlist,
#                        'expressions':expressions})
#     if get_value:
#         df['value'] = values
#         df['dtype'] = dtypes
#     if drop_zero:
#         df = df[df.expressions!='0']
#         if get_value:
#             df = df[df['value']!=0]
#     return df
# def get_all_inputs(scenario,output=None):
#     branchlist_key = get_branchlist('Key')
#     df_key = get_inputs(branchlist_key,scenario,get_value=True)
#     df_key['expressions'] = df_key['value']
#     df_key = df_key.drop('dtype',axis=1)

#     branchlist_hydrology = get_branchlist('Hydrology')
#     df_hydrology = get_inputs(branchlist_hydrology,scenario,get_value=True)
#     df_hydrology['expressions'] = df_hydrology['value']
#     df_hydrology = df_hydrology.drop('dtype',axis=1)

#     # The following only have expression and no value.
#     branchlist_other = get_branchlist('Other')
#     df_other = get_inputs(branchlist_other,scenario)

#     branchlist_demand = get_branchlist('Demand Sites and Catchments')
#     df_demand = get_inputs(branchlist_demand,scenario)

#     branchlist_supply = get_branchlist("Supply and Resources")
#     df_supply = get_inputs(branchlist_supply,scenario)

#     branchlist_udc = get_branchlist("User Defined LP Constraints")
#     df_udc = get_inputs(branchlist_udc,scenario)

#     df_all = pd.concat([df_key,df_hydrology,df_demand,df_supply,df_udc])
#     df_all = df_all.dropna(subset='expressions')
#     if output is not None:
#         df_all.to_csv(output,index=False)
