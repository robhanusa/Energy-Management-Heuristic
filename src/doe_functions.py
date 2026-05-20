# -*- coding: utf-8 -*-
"""
Created on Wed Aug  9 07:55:36 2023

@author: rhanusa
"""

import numpy as np
import plant_components as pc
from plant_components import pph
import weather_energy_components as wec
from weather_energy_components import years
import time

# Capex lifetime to calculate value of capex per year
capex_life = 10

def generate_wt_specs(wt):
    wind_turbine_specs = {
        "cut_in": 13, # km/h
        "rated_speed": 50, # km/h
        "cut_out": 100, # km/h
        "max_energy": 1000, # kW
        "count": wt,
        "cost": wt*1.5*10**6 # EUR/MW 
        }
    
    return wind_turbine_specs

def generate_sp_specs(sp):
    solar_panel_specs = {
        "area": sp, # m^2
        "efficiency": 0.1,
        "cost": sp*200/1.1 # $200/m2 (/1.1 eur to usd)
        }
    
    return solar_panel_specs

def generate_b_specs(b):
    battery_specs = { 
        "max_charge": b, # kWh
        "cost": 1000*b
        }
    
    return battery_specs

# Pre-calculate forecast data. The forecast contains the total predicted energy generation
# over (1) the next 3 hours, and (2) hours 4-6 after the present. As the energy generation
# is dependent on solar panel coverage and number of wind turbines, forecasts are made
# for every combination of sp and wt values input in the DOE. Here, a perfect forecast
# is assumed, so real weather data is used.
def prep_forecast(parameters):
    wt_list = parameters["wt_list"]
    sp_list = parameters["sp_list"]
    
    forecast_store = np.zeros([len(wt_list), len(sp_list), wec.data_length-6, 2])
    forecast_arr = np.zeros(6)
    
    for i in range(len(wt_list)):
        wt = wt_list[i]
        wind_turbine_specs = generate_wt_specs(wt)
        
        for j in range(len(sp_list)):
            sp = sp_list[j]
            solar_panel_specs = generate_sp_specs(sp)
    
            for hour in range(wec.data_length-6):
                for k in range(6): 
                    future_state = wec.Hourly_state(hour+k+1, solar_panel_specs, wind_turbine_specs)
                    forecast_arr[k] = wec.calc_generated_kw(future_state)
                
                forecast_store[i][j][hour][0] = sum(forecast_arr[0:3])
                forecast_store[i][j][hour][1] = sum(forecast_arr[3:7])
                
    return forecast_store


# Run a single DOE scenario to calculate profit at specified conditions in 'run'
def run_scenario(forecast_store, parameters, run):
    
    # factor levels are between 0 and 2 to match indicies 
    # wt is a special case because only 2 levels are considered
    wt_index = int(run["wt_level"]) if int(run["wt_level"]) == 0 else 1
    sp_index = int(run["sp_level"]) 
    b_index = int(run["b_level"])
    c1_index = int(run["c1_level"])
    c2_index = int(run["c2_level"])
    c3_index = int(run["c3_level"])
    
    wt_list = parameters["wt_list"]
    sp_list = parameters["sp_list"]
    b_list = parameters["b_list"]
    c1_list = parameters["c1_list"]
    c2_list = parameters["c2_list"]
    c3_list = parameters["c3_list"]
    
    wt = wt_list[wt_index]
    sp = sp_list[sp_index]
    b = b_list[b_index]
    c1 = c1_list[c1_index]
    c2 = c2_list[c2_index]
    c3 = c3_list[c3_index]
    
    battery_specs = generate_b_specs(b)

    solar_panel_specs = generate_sp_specs(sp)
    
    wind_turbine_specs = generate_wt_specs(wt)
    
    b_sp_constants = {
        "c1": c1,
        "c2": c2,
        "c3": c3
        }

    # initialize counters
    e_from_grid = 0 # kwh
    e_to_grid = 0 # kwh
    total_renewable = 0 # kwh
    total_sx = 0 # mol
    
    # Initiate other necessary variables
    r2_prev = 0 
    reactor1_1 = pc.Reactor1()
    reactor1_1.state = "active"
    reactor2 = pc.Reactor2()
    battery = pc.Battery(0.5*battery_specs["max_charge"], battery_specs)
    energy_flow = wec.Energy_flow()
    energy_tally = pph
    r2_e_prev = 0
    p_renew_tmin1 = 0
    
    # Calculate conditions at each hourly state and add to previous state
    for hour in range(wec.data_length-12):
        state = wec.Hourly_state(hour, solar_panel_specs, wind_turbine_specs)
        
        # Energy flowing to the plant
        p_renew_t_actual = wec.calc_generated_kw(state)
        total_renewable += p_renew_t_actual
        
        forecast = (forecast_store[wt_index][sp_index][hour][0],
                    forecast_store[wt_index][sp_index][hour][1])
        
        # Allow for multiple periods per hour
        for i in range(pph):
            
            # Energy distribution for current period
            energy_tally, r2_e_prev, energy_flow = wec.distribute_energy(p_renew_t_actual,
                                                            p_renew_tmin1,
                                                            energy_tally, 
                                                            r2_e_prev, 
                                                            energy_flow, 
                                                            battery, 
                                                            b_sp_constants,
                                                            reactor2,
                                                            forecast)
                   
            # Update battery charge
            battery.charge += wec.battery_charge_differential(energy_flow.to_battery, battery)
            
            # Calculate reactor 2 state
            r2_sx_current = reactor2.react(energy_flow.to_r2, r2_prev)
            
            # Calculate total sulfur production
            total_sx += r2_sx_current/pph
            
            r2_prev = r2_sx_current
            
            # Add up energy taken from grid
            if energy_flow.from_grid > 0:
                e_from_grid += energy_flow.from_grid/pph
                
            if energy_flow.from_grid < 0:
                e_to_grid -= energy_flow.from_grid/pph
                
        p_renew_tmin1 = p_renew_t_actual
    
    # spread capex cost over 'capex_life' in years
    capex = (battery_specs["cost"] + solar_panel_specs["cost"] + wind_turbine_specs["cost"])/capex_life
    
    # Target production is 240 kmol S per year, so it is assumed that S above this 
    # value is worth 0
    revenue = (9.6*min(total_sx, 240000*years) + 0.1*e_to_grid)/years # revenue / year
    
    # Roughly 15 kW required to make 1 mol S
    opex = 0.25*e_from_grid/years # opex / year
    
    profit = revenue - opex - capex # profit / year
    
    return profit, revenue, opex, capex, total_sx, e_to_grid, e_from_grid

# This is the most CPU intensive function that runs run_scenario function for each 
# run in the DOE
def run_doe(doe, parameters, forecast_store = 0, show_run_status = True ):
    
    doe[["profit", "revenue", "opex", "capex", "total_sx", "e_to_grid", "e_from_grid"]] = np.zeros([len(doe), 7])
    
    # To save time, the forecast_store may be input into run_doe if it exists
    if not isinstance(forecast_store, np.ndarray):
        forecast_store = prep_forecast(parameters)
    
    for i in range(len(doe)):
        
        start = time.time()
        
        run = doe.iloc[i]
        
        profit, revenue, opex, capex, total_sx, e_to_grid, e_from_grid = run_scenario(forecast_store, parameters, run)
        doe["profit"][i] = profit
        doe["revenue"][i] = revenue
        doe["opex"][i] = opex
        doe["capex"][i] = capex
        doe["total_sx"][i] = total_sx
        doe["e_to_grid"][i] = e_to_grid
        doe["e_from_grid"][i] = e_from_grid
        
        end = time.time()
        
        if show_run_status: 
            print("Run: ", i)
            print("Time elapsed: ", end - start)
        
    return doe, forecast_store