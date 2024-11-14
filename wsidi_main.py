# -*- coding: utf-8 -*-
"""
Created on Tue Oct 15 11:59:22 2024
The main script to recursivly generate wsidi curve for all scenarios in Sacwam
Before running the script, sacwam has to be already loaded.
@author: zzhang
"""
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from multiprocessing import freeze_support, Pool
import calc_wsidi
import wsidigenerator
import weapapi


scenarios = ['Existing','35','45','55','65','75']
projects = ['CVP','SWP']
wsidi_fd = "../wsi-di"


def initial_wsidi():
    #intial wsi-di curve 1:1
    wsi_min = 0
    wsi_max= 20000
    wsi_step = 500
    wsi = range(wsi_min,wsi_max,wsi_step)
    wsidi = np.repeat(wsi,2)
    return wsidi

def set_wsidi(wsidi_ini,project,scenario):
    # set_wsidi expression for sacwam.
    #wsidi_ini = initial_wsidi()
    #scenario = 'Existing'
    #project = 'CVP'
    # set initial wsidi to 1:1
    if project == 'CVP':
        branch = "Other Assumptions\\Ops\\CVPSWP\\CVP Allocations\\System\\DemandIndex"
    elif project == 'SWP':
        branch = "Other\Ops\CVPSWP\SWP Allocations\Initial_Allocation\DemandIndex"
    else:
        raise ValueError("project % does not exist. Select SWP or CVP"%project)
    expression = weapapi.get_expression(branch,scenario)
    expression = expression.split(";")[0]  # ignore the text after ';'.
    strlist = re.findall(r'\(.*?\)',expression)[0].replace('(','').replace(')','').split(',')
    ini_str = ",".join(strlist[:4])
    wsidi_list = ['%.0f'%s for s in wsidi_ini]
    wsidi_str = ",".join(wsidi_list)
    new_expression = 'Lookup(' + ini_str + ','+ wsidi_str + ')'
    weapapi.set_expression(branch,new_expression,scenario)
    #weapapi.WEAP.SaveArea()
    return()

def set_ini_wsidi(projects,scenarios):
    # set 1:1 curves to all scenarios.
    wsidi = initial_wsidi()
    proj = np.tile(projects,len(scenarios))
    scen = np.repeat(scenarios,len(projects))
    for p, s in zip(proj,scen):
        set_wsidi(wsidi,p,s)

def calc_new_wsidi(num,project,scenario):
    # update new curves based on calculated values.
    wsidi_cl = calc_wsidi.calc_act_wsidi(scenario, project)
    #wsi = wsidi_cl.wsi.values
    #di = wsidi_cl.di.values
    fn = os.path.join(wsidi_fd,"%s_%s_%s.csv"%(project,scenario,num))
    wsidi_cl.save_data(fn)
    gen = wsidigenerator.wsidi_gen(project,fn,offset0=1.2)
    new_wsidi = gen.get_all_function_pairs()
    new_wsidi = np.ravel(new_wsidi)
    wsi_new = new_wsidi[::2]
    di_new = new_wsidi[1::2]
    df = pd.DataFrame({'wsi':wsi_new,'di':di_new})
    fn2 = os.path.join(wsidi_fd,"curve_%s_%s_%s.csv"%(project,scenario,num))
    df.to_csv(fn2)
    print("wsidi curve updated for scenario %s, project %s, and round %s"%(
        scenario,project,num))
    return

def update_wsidi(num,project,scenario):
    fn2 = os.path.join(wsidi_fd,"curve_%s_%s_%s.csv"%(project,scenario,num))
    df = pd.read_csv(fn2)
    new_wsidi =  np.ravel([df['wsi'].values,df['di'].values],'F')
    set_wsidi(new_wsidi,project,scenario)

def update_all_wsidi(projects,scenarios,num):
    # apply update_wsidi in parallel
    proj = np.tile(projects,len(scenarios))
    scen = np.repeat(scenarios,len(projects))
    runs = [(num,p,s) for p,s in zip(proj,scen)]
    print("Update wsidi curves for all runs!")
    # unfortunately the wsi-di curve didn't get updated in sacwam despite the curves
    # were calculated successfully. This might be related to how many processors are allowed to
    # interface with sacwam at once. Separating the calculation and writting into
    # two scripts.
    with Pool() as pool:
        pool.starmap(calc_new_wsidi, runs)
    for r in runs: # parallel does not work so well with writting to sacwam, so for now loop through all the runs instead.
        update_wsidi(r[0],r[1],r[2])
    return

def plot_wsidi(project,num):
    for s in scenarios:
        fn = os.path.join(wsidi_fd,"%s_%s_%s.csv"%(project,s,num))
        fn2 = os.path.join(wsidi_fd,"curve_%s_%s_%s.csv"%(project,s,num))
        df = pd.read_csv(fn)
        df_curve = pd.read_csv(fn2)
        plt.scatter(df['wsi'],df['di'],label="%s points"%s,s=50,
                    alpha=0.7)
        plt.plot(df_curve['wsi'],df_curve['di'],linewidth=4,alpha=0.5,
                 label="%s curve"%s)
        plt.xlabel('WSI (TAF)')
        plt.ylabel('DI (TAF)')
        plt.title("%s (Iteration %s)"%(project,num))
    plt.legend()

if __name__=='__main__':
    freeze_support()
    weapapi.WEAP.SaveVersion("before wsidi caclulation")
    #set 1:1 curves
    set_ini_wsidi(projects,scenarios)
    # run WEAP.
    weapapi.WEAP.Calculate(0, 0, False) #Only calculate scenarios that need calculation (for all years and timesteps)
    weapapi.WEAP.SaveVersion("one to one curve")
    # update wsidi curves
    update_all_wsidi(projects,scenarios,1)
    # run WEAP the second time.
    weapapi.WEAP.Calculate(0, 0, False)
    weapapi.WEAP.SaveVersion("1st round")
    # update wsidi curves the second time
    update_all_wsidi(projects,scenarios,2)
    # run WEAP the third time.
    weapapi.WEAP.Calculate(0, 0, False)
    weapapi.WEAP.SaveVersion("2nd round")
    plot_wsidi("CVP",1)


    # #%% sanity check to make sure the the curve generated matches with the calculated scatter plot
    # #calc_new_wsidi(1,"CVP",scenarios[-1])
    # #update_wsidi(1,"CVP",scenarios[-1])
    # #update_all_wsidi("CVP",scenarios,1)
    # project = "SWP"
    # plot_wsidi(project)
    # #%% update a single scenario
    # project = 'SWP'
    # s = '75'
    # calc_new_wsidi(1,project,s)
    # update_wsidi(1,project,s)
    # num = 1
    # fn = os.path.join(wsidi_fd,"%s_%s_%s.csv"%(project,s,num))
    # fn2 = os.path.join(wsidi_fd,"curve_%s_%s_%s.csv"%(project,s,num))
    # df = pd.read_csv(fn)
    # df_curve = pd.read_csv(fn2)
    # plt.scatter(df['wsi'],df['di'],label="%s points"%s,s=50,
    #             alpha=0.7)
    # plt.plot(df_curve['wsi'],df_curve['di'],linewidth=4,alpha=0.5,
    #          label="%s curve"%s)
    # plt.xlabel('WSI (TAF)')
    # plt.ylabel('DI (TAF)')
    # plt.title(project)