# -*- coding: utf-8 -*-
"""
Created on Mon Jul  3 14:24:51 2023

@author: rhanusa
"""

# Inputs
battery_specs = { # Using battery at https://www.backupbatterypower.com/products/1-144-kwh-industrial-battery-backup-and-energy-storage-systems-ess-277-480-three-phase?pr_prod_strat=use_description&pr_rec_id=97fba9aea&pr_rec_pid=6561192214696&pr_ref_pid=6561191100584&pr_seq=uniform
    "max_charge": 1144, # kWh
    "cost": 1.2*10**6 
    }

solar_panel_specs = {
    "area": 10000, # m^2
    "efficiency": 0.1,
    "cost": 10000*200/1.1 # $200/m2 (/1.1 eur to usd) https://www.sunpal-solar.com/info/how-much-does-a-solar-panel-cost-per-square-me-72064318.html
    }

wind_turbine_specs = {
    "cut_in": 13, # km/h
    "rated_speed": 50, # km/h
    "cut_out": 100, # km/h
    "max_energy": 1000, # kW
    "count": 1,
    "cost": 1.5*10**6 # EUR/MW (https://www.windustry.org/how_much_do_wind_turbines_cost)
    }

r2_max_constants = {
    "c1": 0.2,
    "c2": 0.2,
    "c3": 4*10**(-5)
    }

b_sp_constants = {
    "c1": 1, # when these become 2, it energy consumption gets choppier, and grid consumption remains about the same
    "c2": 1,
    "c3": 0
    }