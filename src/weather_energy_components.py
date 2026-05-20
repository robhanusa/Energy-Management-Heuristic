# -*- coding: utf-8 -*-
"""
Created on Wed May 17 07:53:37 2023

@author: rhanusa
"""
import pandas as pd
from plant_components import pph

years = 8 # Number of years the training data spans 

data_length = round(87671*years/10) # use first 8 years out of 10 total years of data

cols = ["time","windspeed_100m (km/h)","shortwave_radiation (W/m²)"]

df_weather = pd.read_csv("wind_solar_2013-2022_open-meteo.com.csv",
                         skiprows=3,
                         usecols=cols,
                         nrows=data_length)

df_weather["time"] = pd.to_datetime(df_weather["time"])

condenser_constant = 0.02

# calc kw's generated from solar panels
def calc_solar_energy(solar_radiation, solar_panel_specs):
    sp_area = solar_panel_specs['area']
    sp_efficiency = solar_panel_specs['efficiency']
    return solar_radiation*sp_area*sp_efficiency/1000

# calc kw's generated from wind turbines
# for simplicity, assuming linear relationship between cut-in and rated speeds
# for complex relationships, look at (Sohoni 2016)
def calc_wind_energy(windspeed, wind_turbine_specs):
    wt_cut_in = wind_turbine_specs['cut_in']
    wt_cut_out = wind_turbine_specs['cut_out']
    wt_rated_speed = wind_turbine_specs['rated_speed']
    wt_max_energy = wind_turbine_specs['max_energy']
    wt_number = wind_turbine_specs['count']
    if windspeed < wt_cut_in or windspeed > wt_cut_out: 
        return 0
    elif windspeed > wt_rated_speed: 
        return wt_number*wt_max_energy
    else:
        return wt_number*(wt_max_energy*(windspeed - wt_cut_in)/(wt_rated_speed - wt_cut_in))

# each system state comprises of a period of 1 hour / pph
class Hourly_state:
    def __init__(self,hour, solar_panel_specs, wind_turbine_specs):
        self.time = df_weather["time"][hour]
        self.wind = df_weather["windspeed_100m (km/h)"][hour] #km/h
        self.wind_energy = calc_wind_energy(self.wind, wind_turbine_specs) #kW
        self.wind_power = self.wind_energy*pph #kWh
        self.solar = df_weather["shortwave_radiation (W/m²)"][hour] #W/m2
        self.solar_energy = calc_solar_energy(self.solar, solar_panel_specs) #kW
        self.solar_power = self.solar_energy*pph #kWh
        self.month = df_weather["time"][hour].month
        self.hour_of_day = df_weather["time"][hour].hour
        
class Energy_flow():
    def __init__(self):
        self.to_r1 = 0
        self.to_r2 = 0 
        self.to_condenser = 0 
        self.to_battery = 0
        self.from_grid = 0
        
def calc_generated_kw(state):
    return state.wind_power/pph + state.solar_power/pph

def allocate_p_to_condenser(to_r2, reactor2):
    condenser_constant = 0.5
    r2_sx_ss = reactor2.ss_output(to_r2)
    to_condenser = condenser_constant * r2_sx_ss
    return to_condenser


def calc_b_sp(b_sp_constants, forecast_aggregated, battery, p_min, p_max):
    hrs_0_3, hrs_4_6 = forecast_aggregated
    c1 = b_sp_constants["c1"]
    c2 = b_sp_constants["c2"]
    c3 = b_sp_constants["c3"]
    
    p_ave = (p_max + p_min) / 2
    
    ratio_0_3 = 1 - hrs_0_3 / (3 * p_ave)
    ratio_4_6 = 1 - hrs_4_6 / (3 * p_ave)
    
    sp_default = battery.max_charge * 0.5
    
    return min(battery.max_charge * 0.8, 
               max(battery.max_charge * 0.2, 
                   sp_default * (c1 * ratio_0_3 + c2 * ratio_4_6 + c3 * ratio_0_3 * ratio_4_6)))


def distribute_energy(p_renew_t_actual,
                      p_renew_tmin1,
                      energy_tally, 
                      r2_e_prev, 
                      energy_flow, 
                      battery, 
                      b_sp_constants,
                      reactor2, 
                      forecast_aggregated):
    
    r1_max = 50
    r1_min = 50
    
    r2_max = 1000 
    r2_min = 50

    p_min = r1_min + r2_min + allocate_p_to_condenser(r2_min, reactor2)
    
    p_max = r1_max + r2_max + allocate_p_to_condenser(r2_max, reactor2)
    
    # For the moment we assume perfect forecasting, but the line below is where
    # we can adapt for different levels of forecasting accuracy.
    p_renew_t_forecasted = p_renew_t_actual
    b_sp = calc_b_sp(b_sp_constants, forecast_aggregated, battery, p_min, p_max)
    e_t = b_sp - battery.charge
    d = p_renew_tmin1 - p_renew_t_forecasted
    
    # Below is essentially a P controller (e_t) with a feed-forward term (d)
    p_total = p_renew_tmin1 - e_t - d
    
    # Check if there has already been a change in energy distribution in the last
    # hour. If so, don't change current distribution.
    if energy_tally < pph : 
        energy_tally += 1

    else:
        energy_flow.to_r1 = r1_min
        energy_flow.to_r2 = min(r2_max, max(r2_min, (p_total - r1_min) / (1 + condenser_constant)))
        energy_flow.to_condenser = energy_flow.to_r2 * condenser_constant
        
    energy_flow.to_battery = allocate_p_to_battery(energy_flow, battery, p_renew_t_actual)
    energy_flow.from_grid = energy_flow.to_r1 + energy_flow.to_r2 \
                            + energy_flow.to_condenser + energy_flow.to_battery \
                            - p_renew_t_actual
    
    if r2_e_prev != energy_flow.to_r2: energy_tally = 1
    
    r2_e_prev = energy_flow.to_r2

    return energy_tally, r2_e_prev, energy_flow 

def allocate_p_to_battery(energy_flow, battery, p_renew_t_actual):
    power_consumption = energy_flow.to_r1 + energy_flow.to_r2 + energy_flow.to_condenser
    power_surplus = p_renew_t_actual - power_consumption
    battery_limit = 0.8 * battery.max_charge
    
    # confirm there is room for battery to be charged or discharged
    if power_surplus > 0 and battery.charge + power_surplus / pph > battery_limit:
        return (battery_limit - battery.charge) * pph
    elif power_surplus < 0 and battery.charge + power_surplus / pph < battery.max_charge * 0.2:
        return -(battery.charge - battery.max_charge * 0.2) * pph
    else:
        return power_surplus

def battery_charge_differential(power_to_battery, battery):
    battery_limit = 0.8 * battery.max_charge
    if power_to_battery > 0:
        if power_to_battery * battery.efficiency / pph + battery.charge > battery_limit:
            return battery_limit - battery.charge
        else:
            return power_to_battery * battery.efficiency / pph
    else:
        return power_to_battery / pph