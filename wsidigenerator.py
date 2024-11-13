# -*- coding: utf-8 -*-
"""
Created on Thu Oct  3 10:54:13 2024
Test script to generate a new wsidi curve based on the model output
This script is based on WsiDiGen.py from WRIMS GUI - Wsi-Di Generator - California Natural Resources Agency Open Data
@author: zzhang
"""

import copy
from math import sqrt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# WsiDiCl class
class wsidi_gen:

   # constructor: initialize class parameters
    def __init__(self,name,datafn=None, wsi_var='wsi',di_var='di',
                wsi_max=20000,offset0=1.2):
        # assign passed constructor arguments
        self.name = name   # wsi-di profile name: CVP or SWP
        self.wsi_var = wsi_var   # user-defined colum name for wsi variable
        self.di_var = di_var   # user-defined colum name for di variable
        self.wsi_max_ub = wsi_max
        self.wsi_max = wsi_max  # maximum wsi value (TAF) for the wsidi curve, e.g., 20000
        self.offset1 = offset0  #default offset 1.2
        #self.stdyDvName = dvName   # study DV name
        #self.lookupName = lookupName  # lookup folder name
        #self.launchName = launchName # launch file name

        # set other class variables
        value = 0.0
        self.report = True
        self.step = 500.0   # Distance between data points on the WSI axis
        self.lookahead = 1.0*self.step   # Distance to look ahead for data beyond segment endpoint to determine coordinates of segment endpoint
        self.mult = 1.0   # standard deviation multiplier for wsidi pair search
        self.wsi_min = 0.0   # minimum wsi value
        self.di_min = self.step   # minimum di value
        self.di_max = 0.0   # maximum di value, set to actual value when WSI-DI data is analyzed
        self.threshold = 0.1   # threshold above which to count wsi-di data pts
        self.nseg = int(wsi_max/self.step)   #  number of wsi-di segments
        self.ndata = 0   # number of wsi-di data points, set to actual value when WSI-DI data is analyzed

        # temporary variables defined by ZZ
        if datafn is not None:
            self.load_ini(datafn)

    def load_ini(self,fname):
        """
        Load initial wsi and di.

        Parameters
        ----------
        fname : str
            csv data file for the wsidi curve calcluated from calc_wsidi.py

        """
        data = pd.read_csv(fname)  # input wsi-di data array
        self.data_ini = data[data[self.wsi_var]>self.threshold]  # only take the values above the threshold
        self.ndata = len(self.data_ini)
        self.wsi_init = self.data_ini[self.wsi_var].values
        self.wsi_max = self.wsi_init.max()
        self.wsi_min = self.wsi_init.min()
        self.di_init = self.data_ini[self.di_var].values
        self.di_max = self.di_init.max()
        self.di_min = self.di_init.min()
        return


    def get_slope(self, wsi0, di0, offset):
        """
        Calculates slope for a particular data point (wsi0, di0)

        Parameters
        ----------
        wsi0 : float
        di0 : float
        offset : float

        Returns
        -------
        slope : float

        """
        wsiend = wsi0 + self.step
        npoints=0
        wsiin = self.data_ini[self.wsi_var].values
        diin = self.data_ini[self.di_var].values
        slope = 0.0
        delwsi = 0.0
        sumdelwsi = 0.0
        sumdiwsi = 0.0
        sumwsi2 = 0.0
        # The input offset here equals to the intersect on the di axis if you extend the line along the slope.
        # self.offset1 is a mofication factor (dimensionless) that changes the input offest, and the modified offset will be used as the final offset.
        if wsi0 < (0.33*(self.wsi_max-self.wsi_min)+self.wsi_min):
            offset *= self.offset1
        elif wsi0 < (0.5*(self.wsi_max-self.wsi_min)+self.wsi_min):
            offset *= 1.0
        else:
            offset *= 0.0
        for i in range(self.ndata):
            if wsiin[i] > wsi0 and wsiin[i] <= (wsiend + self.lookahead):
                npoints += 1
       	    delwsi = wsiin[i] - wsi0
       	    sumdelwsi = sumdelwsi + wsiin[i] - wsi0
       	    sumdiwsi = sumdiwsi + (diin[i]-offset)*delwsi
       	    sumwsi2 = sumwsi2 + delwsi*delwsi
        if npoints > 1:
            slope = (sumdiwsi - di0*sumdelwsi)/sumwsi2
        else:
            slope = 0.0
        if slope < 0.0:
            slope = 0.0
        return slope

    def get_function_pair(self, wsi0, di0, offset):
        """
        Get function pair returns a single point on the wsi-di curve
        """
        wsiend = wsi0 + self.step
        slope = self.get_slope(wsi0,di0,offset)
        diend = di0 + slope*(wsiend - wsi0)
        # if wsi0 minimal, set first di equal to the min of the set
        if wsi0 < 1.0:
            diend=self.di_min
        pair = (wsiend,diend)   # assign wsi/di variables for return
        return pair

    #
    def get_std(self,data):
        """
        Gets cumulative step-wise standard deviation for input data set as projected from initial wsi-di curve

        Parameters
        ----------
        data : Pandas DataFrame
            new wsi-di curve dataframe different from self.data_ini.

        Returns
        -------
        stdev : float

        """
        # data:
        slope = 0.0
        dist = 0.0
        sumdist = 0.0
        sumdist2 = 0.0
        stdev = 0.0
        npoints=0
        wsiin = self.wsi_init
        diin = self.di_init
        for i in range(0,self.nseg):
            wsi0 = data[i][0]
            di0 = data[i][1]
            slope = self.get_slope(wsi0,di0,0.0)
            for j in range(0,self.ndata):
                if wsiin[j] >= wsi0 and wsiin[j] < (wsi0 + self.step):
                    npoints += 1
                    dist = diin[j] - (di0 + slope*(wsiin[j] - wsi0))
                    sumdist = sumdist + dist
                    sumdist2 = sumdist2 + dist**2
        if npoints > 0:
            stdev = sqrt((npoints*sumdist2 - sumdist*sumdist)/(npoints*(npoints-1)))
        else:
            stdev = 0.0
        return stdev

    def get_all_function_pairs(self):
        """
        Returns
        -------
        Final wsi-di curve in Pandas DataFrame
        """
        data = []
        wsi0 = 0.0
        di0 = 0.0
        data.append((wsi0,di0))
        for i in range (1,self.nseg+1):
            data.append(self.get_function_pair(wsi0,di0,0.0))
            wsi0 = data[i][0]
            di0 = data[i][1]
        stdev = self.get_std(data)
        offset = self.mult*stdev
        wsi0 = 0.0
        di0 = 0.0
        data[0] = (wsi0,di0)
        for i in range (1,self.nseg+1):
            data[i] = self.get_function_pair(wsi0,di0,offset)
            wsi0 = data[i][0]
            di0 = data[i][1]
        return data

    def get_all_function_pairs_ext(self):
        data = []
        wsi0 = 0.0
        di0 = 0.0
        data.append((wsi0,di0))
        for i in range (1,self.nseg+1):
            data.append(self.get_function_pair(wsi0,di0,0.0))
            wsi0 = data[i][0]
            di0 = data[i][1]
        stdev = self.get_std(data)
        offset = -1*self.mult*stdev
        wsi0 = 0.0
        di0 = 0.0
        data[0] = (wsi0,di0)
        slope1 = self.di_min/self.wsi_min  # the initial slope
        prev_slope = copy.deepcopy(slope1)
        for i in range (1,self.nseg+1):
            if wsi0<=self.wsi_min:
                wsiend = wsi0+self.step
                diend = slope1*wsiend
                data[i] = (wsiend,diend)
            else:
                slope = self.get_slope(wsi0, di0, offset)
                print(slope)
                if slope == 0.0:
                    wsiend = wsi0+self.step
                    diend = di0+self.step*1.0
                    data[i] = (wsiend,diend)
                else:
                    data[i] = self.get_function_pair(wsi0,di0,offset)
                    prev_slope = copy.deepcopy(slope)
            wsi0 = data[i][0]
            di0 = data[i][1]
        return data




if __name__ == "__main__":
    # wsidi curve example
    wsidi_cl1 = wsidi_gen('CVP','..\wsi-di\CVP_75_1.csv',offset0=2.0)
    new_wsidi1 = wsidi_cl1.get_all_function_pairs()
    new_wsidi1 = np.array(new_wsidi1)

    wsidi_cl2 = wsidi_gen('CVP','..\wsi-di\CVP_75_1.csv',offset0=1.2)
    new_wsidi2 = wsidi_cl2.get_all_function_pairs()
    new_wsidi2 = np.array(new_wsidi2)

    plt.plot(wsidi_cl1.wsi_init,wsidi_cl1.di_init,'o',alpha=0.5,
              label='sacwam calculated')
    plt.plot(new_wsidi1[1:,0],new_wsidi1[1:,1],label='offset=2.0')
    plt.plot(new_wsidi2[1:,0],new_wsidi2[1:,1],label='offset=1.2')
    plt.legend()
    plt.xlabel('WSI (TAF)')
    plt.ylabel('DI (TAF)')
    plt.tight_layout()

    # #%% disi curve example
    # di_si = [0, 0, 3990, 3055, 5442, 3402, 7162, 4122, 8717, 4637,
    #           10434, 5704, 11395, 6515, 15099, 9999]
    # x = di_si[::2]
    # y = di_si[1::2]
    # plt.plot(x,y,linewidth=4, label="initial curve",color='k')
    # for s in ['Existing','35','45','55','65','75']:
    #     wsidi_cl2 = wsidi_gen('CVP','..\wsi-di\CVP_%s_1.csv'%s,offset0=1.0,
    #                           wsi_var='di',di_var='supply',wsi_max=14000,)
    #     new_wsidi2 = wsidi_cl2.get_all_function_pairs_ext()
    #     new_wsidi2 = np.array(new_wsidi2)
    #     plt.scatter(wsidi_cl2.wsi_init,wsidi_cl2.di_init,alpha=0.5,
    #               label='calculated di-si (scen %s)'%s)
    #     plt.plot(new_wsidi2[1:,0],new_wsidi2[1:,1],label='curve (scen %s)'%s,
    #              linewidth=4,alpha=0.7)
    # plt.xlabel('DI (TAF)')
    # plt.ylabel('delivery (TAF)')
    # plt.tight_layout()
    # plt.legend()