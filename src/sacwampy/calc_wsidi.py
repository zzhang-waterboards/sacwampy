# -*- coding: utf-8 -*-
"""
Created on Tue Sep 17 11:49:51 2024
Calculate wsi-di curve
@author: zzhang
"""
import os
from time import strptime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import weapapi


class calc_act_wsidi():
    def __init__(self,scenario,project,wsidi_ini=None,disi_ini=None):
        self.scenario = scenario
        self.project = project
        self.WEAP = weapapi.create_object()
        self.start_wy = self.WEAP.BaseYear
        self.end_wy = self.WEAP.EndYear
        self.start_ts = 1
        self.end_ts = self.WEAP.NumTimeSteps
        self.wy_range = range(self.start_wy+1,self.end_wy-1,1)
        self.wsidi_ini = wsidi_ini # initial wsi-di curve
        self.disi_ini = disi_ini # initial di-delivery curve
        self._carryover = None
        self._wsi = None
        self._delivery = None
        self._di = None

    def month2index(self,month):
        # convert calendar month to index month
        if isinstance(month,str):
            try:
                calendar_month =  strptime(month,'%b').tm_mon
            except ValueError:
                calendar_month =  strptime(month,'%B').tm_mon
        #tindex = calendar_month + (self.end_ts-self.WEAP.WaterYearStart+1)
        return calendar_month

    def get_value_bymonth(self,branch,calendar_month):
        # read the branch value for a particular calendar month of a year.
        timestep = self.month2index(calendar_month) + (
            self.end_ts-self.WEAP.WaterYearStart+1)
        values_sum = []
        units = []
        for wy in self.wy_range:
            if wy == self.WEAP.BaseYear:
                scen = "Current Accounts"
            else:
                scen = self.scenario
            scen = self.scenario
            values = []
            if isinstance(branch,list):
                for br in branch:
                    values.append(self.WEAP.ResultValue(br,wy,timestep,scen))
                br1, br2 = br.split(":")
                br2 = br2.lstrip()
                unit = self.WEAP.Branch(br1).Variable(br2).Unit
                units.append(unit)
                scale = self.WEAP.Branch(br1).Variable(br2).scale
                if scale!=1:
                    values = np.array(values)*scale
                values_sum.append(sum(values))
            else:
                values = self.WEAP.ResultValue(branch,wy,timestep,self.scenario)
                br1, br2 = branch.split(":")
                br2 = br2.lstrip()
                unit = self.WEAP.Branch(br1).Variable(br2).Unit
                units.append(unit)
                scale = self.WEAP.Branch(br1).Variable(br2).Scale
                if scale!=1:
                    values*=scale
                values_sum.append(values)

        df = pd.DataFrame({'values': values_sum,
                           'units': units},
                           index=self.wy_range)

        df = df.apply(weapapi.totaf,axis=1)
        return df['values']

    @property
    def carryover(self):
        if self._carryover is None:
            if self.project=='CVP':
                cvpsto_SL = "Supply and Resources\River\CVP San Luis Conveyance\Reservoirs\CVP San Luis Reservoir: Storage Volume"
                cvpsto_Fol = "Supply and Resources\River\American River\Reservoirs\Folsom Lake: Storage Volume"
                cvpsto_Sha = "Supply and Resources\River\Sacramento River\Reservoirs\Shasta Lake: Storage Volume"
                cvpsto_Tri = "Supply and Resources\River\Trinity River\Reservoirs\Trinity Reservoir: Storage Volume"
                sto_list = [cvpsto_SL,cvpsto_Fol,cvpsto_Sha,cvpsto_Tri]
            elif self.project=='SWP':
                swpsto_sl = "Supply and Resources\River\SWP San Luis Conveyance\Reservoirs\SWP San Luis Reservoir: Storage Volume"
                swpsto_orr = "Supply and Resources\River\Feather River\Reservoirs\Oroville Reservoir: Storage Volume"
                sto_list = [swpsto_sl,swpsto_orr]
            else:
                raise ValueError("project % does not exist. SelectSWP or CVP"%self.project)
            df = pd.Series(self.get_value_bymonth(sto_list,"Sep"), #the last value is not used.
                           index=self.wy_range)
            df = np.repeat(df,2 )
            self._carryover = df
        return self._carryover

    @property
    def wsi(self):
        if self._wsi is None:
            if self.project == 'CVP':
                branch = "Other\Ops\CVPSWP\CVP Allocations\System\WaterSupplyEst: Annual Activity Level"
            elif self.project == 'SWP':
                branch = "Other\Ops\CVPSWP\SWP Allocations\Initial_Allocation\WaterSupplyEst: Annual Activity Level"
            else:
                raise ValueError("project % does not exist. Select SWP or CVP"%self.project)

            df_Apr = self.get_value_bymonth(branch,'Apr')
            df_Apr.index.name = "datetime"
            df_May = self.get_value_bymonth(branch,'May')
            df_May.index.name = 'datetime'
            df = pd.concat([df_Apr,df_May]).sort_index()
            self._wsi = df
        return self._wsi # the last wsi values are removed, since no corresponding DI values exit

    @property
    def delivery(self):
        # all_links=True: calculate delivery by all project related links
        if self._delivery is None:
            df_tr_links = pd.read_csv("transmission_links_appendix_mapping_tablea.csv",
                                      comment='#')
            project_links = df_tr_links.query("project=='%s'"%self.project.lower())
            #tablea = [c for c in project_links.branch if 'table a' in c.lower()]
            #project_links = project_links[project_links.branch.isin(tablea)]
            #project_links = project_links[project_links.delivery_group !='conveyance_loss']
            values = []
            units = []
            values2 = []
            for wy in self.wy_range:
                if wy == self.WEAP.BaseYear:
                    scen = "Current Accounts"
                else:
                    scen = self.scenario
                scen = self.scenario
                value_yr = []
                for i, r in project_links.iterrows():
                    m1 = self.month2index(r.start)
                    m2 = self.month2index(r.end)
                    wy1 = wy
                    if m2<m1:
                        wy2 = wy + 1
                    else:
                        wy2 = wy
                    wy1,ts1 = weapapi.ym2weapym(wy1,m1)
                    wy2,ts2 = weapapi.ym2weapym(wy2,m2)
                    v,unit = weapapi.read_value_stats(r.branch,scen,
                                            start_wy=wy1,start_ts=ts1,
                                            end_wy=wy2,end_ts=ts2)
                    value_yr.append(v*r.sign)
                br1, br2 = r.branch.split(":")
                br2 = br2.lstrip()
                #unit = self.WEAP.Branch(br1).Variable(br2).Unit
                #scale = self.WEAP.Branch(br1).Variable(br2).Scale
                values.append(sum(value_yr))
                units.append(unit)
                values2.append(value_yr)

            df_delivery = pd.DataFrame({'values':values,
                                      'units':units},
                                      index=self.wy_range)
            df_delivery = df_delivery.apply(weapapi.totaf,axis=1)
            df_delivery = df_delivery['values']
            df = np.repeat(df_delivery,2)
            self._delivery = df
        return self._delivery

    @property
    def di(self):
        if self._di is None:
            di = self.delivery + self.carryover
            self._di = di
        return self._di

    @staticmethod
    def rename_colnames(col):
        return col.split("[")[0].lower().replace(" ","_")

    def save_data(self,filename):
        df = pd.concat([self.wsi.to_frame('wsi'),
                        self.di.to_frame('di'),
                        self.delivery.to_frame('delivery'),
                        self.carryover.to_frame('carryover')],
                       axis=1)
        df.to_csv(filename,float_format="%.2f")

    def plot_wsidi(self):
        wsi = self.wsi
        di = self.di
        delivery = self.delivery
        fig,ax = plt.subplots(1,2,figsize=[12,6])
        if self.wsidi_ini is not None:
            x = self.wsidi_ini[::2]
            y = self.wsidi_ini[1::2]
            ax[0].plot(x,y,label="initial curve",
                       color='k',linewidth=4)
        ax[0].plot(wsi,di,'.',color='k', label='wsi-di',
                markersize=12, alpha=0.3,
                markeredgecolor='k')
        ax[0].set_xlabel("WSI (TAF)")
        ax[0].set_ylabel("DI (TAF)")

        if self.disi_ini is not None:
            x = self.disi_ini[::2]
            y = self.disi_ini[1::2]
            ax[1].plot(x,y,linewidth=4, label="initial curve",color='k')
        ax[1].plot(di,delivery,'.',color='k', label="di-delivery",
                markersize=12, alpha=0.3,markeredgecolor='k')
        ax[1].set_xlabel("Demand or DI (TAF)")
        ax[1].set_ylabel("delivery (TAF)")
        ax[0].legend()
        ax[1].legend()
        ax[0].set_xlim(xmin=0)
        ax[1].set_xlim(xmin=0)
        ax[0].set_ylim(ymin=0)
        ax[1].set_ylim(ymin=0)
        plt.suptitle("%s (%s)"%(self.project,self.scenario),fontsize=16)
        plt.tight_layout()
        return

if __name__ == "__main__":
    # CVP initial curve in Sacwam
    wsi_di = dict()
    wsi_di['Existing'] = [0, 0, 500, 4171, 5000, 4171, 5500, 4348, 6000, 4726,
                          6500, 5207, 7000, 5980, 7500, 6753, 8000, 7287, 8500,
                          7704, 9000, 8268, 9500, 8868, 10000, 9613, 10500, 10281,
                          11000, 10959, 11500, 11274, 12000, 11550, 12500, 11660,
                          13000, 11734, 13500, 11967, 14000, 11967, 20000, 11967]
    wsi_di['35'] = [0, 0, 500, 4171, 5000, 4171, 5500, 4348, 6000, 4726, 6500, 5207,
              7000, 5980, 7500, 6753, 8000, 7287, 8500, 7704, 9000, 8268, 9500,
              8868, 10000, 9613, 10500, 10281, 11000, 10959, 11500, 11274, 12000,
              11550, 12500, 11660, 13000, 11734, 13500, 11967, 14000, 11967,
              20000, 11967]
    wsi_di['45'] = [ 0, 0, 500, 4171, 5000, 4171, 5500, 4348, 6000, 4726, 6500,
                    5207, 7000, 5980, 7500, 6753, 8000, 7287, 8500, 7704, 9000,
                    8268, 9500, 8868, 10000, 9613, 10500, 10281, 11000, 10959,
                    11500, 11274, 12000, 11550, 12500, 11660, 13000, 11734, 13500,
                    11967, 14000, 11967, 20000, 11967]
    wsi_di['55'] =  [0, 0, 500, 4171, 5000, 4171, 5500, 4348, 6000, 4726, 6500,
                      5207, 7000, 5980, 7500, 6753, 8000, 7287, 8500, 7704, 9000,
                      8268, 9500, 8868, 10000, 9613, 10500, 10281, 11000, 10959,
                      11500, 11274, 12000, 11550, 12500, 11660, 13000, 11734, 13500,
                      11967, 14000, 11967, 20000, 11967]
    wsi_di['65'] = [0, 0, 557, 1660, 2750, 2110, 4790, 2330, 6060, 2830, 6650,
                    3170, 7000, 3450, 7500, 4180, 7790, 5210, 8500, 7704, 9030,
                    8190]
    wsi_di['75'] = [0, 0, 614, 993, 4820, 1010, 5500, 1840, 5940, 2840, 6380, 3660,
                    6760, 4510, 7500, 6520, 8000, 7050, 8500, 7704, 9000, 8268,
                    9500, 8868, 10000, 9613, 10500, 10281, 11000, 10959, 11500,
                    11274, 12000, 11550, 12500, 11660, 13000, 11734, 13500, 11967,
                    14000, 11967, 20000, 11967]


    di_si = [0, 0, 3990, 3055, 5442, 3402, 7162, 4122, 8717, 4637,
              10434, 5704, 11395, 6515, 15099, 9999]

    # SWP initial curve in Sacwam
    wsi_di['Existing'] = [0, 0, 500, 1206, 1000, 1206, 1500, 1206, 2000, 1206,
                          2500, 1440, 3000, 1999, 3500, 2665, 4000, 3397, 4500,
                          4415, 5000, 5243, 5500, 5901, 6000, 6985, 6500, 7480,
                          7000, 7909, 7500, 8039, 8000, 8039, 8500, 8039, 9000,
                          8039, 9500, 8039, 10000, 8039, 10500, 8039, 11000,
                          8039, 11500, 8039, 12000, 8039, 12500, 8039, 13000,
                          8039, 13500, 8039, 14000, 8039, 14500, 8039, 15000,
                          8039, 15500, 8039, 16000, 8039, 16500, 8039, 17000,
                          8039, 17500, 8039, 18000, 8039, 18500, 8039, 19000,
                          8039, 19500, 8039, 20000, 8039]

    # # Calculate wsidi curve
    scenario = 'Existing'
    project = 'SWP'
    wsidi_ini = wsi_di[scenario]
    disi_ini = di_si
    wsidi_cl = calc_act_wsidi(scenario, project, wsidi_ini,disi_ini)
    wsidi_cl.plot_wsidi()
    wsidi_cl.save_data("../wsi-di/wsidi_%s_%s.csv"%(project,scenario))

    #plot wsidi curve
    # project = 'SWP'
    # wsidi_cl = calc_act_wsidi(scenario, project, wsidi_ini,disi_ini)
    # wsidi_cl.plot_wsidi()

    # Exceedance plot
    #weapapi.exceedance_plot(wsidi_cl.delivery)

