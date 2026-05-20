# -*- coding: utf-8 -*-
"""
Created on Wed May 17 09:30:04 2023

@author: rhanusa
"""
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from plant_components import pph
import math
import weather_energy_components as wec
import plant_components as pc
import input_specs as ins

# Tab 1

graph_margin = dict(b=60, l=20, r=20, t=60)
bat_start_charge = 0.5*ins.battery_specs["max_charge"]

# Length of graphs' x axes.
idle_start_length = 500
x = [i*60/pph for i in range(-idle_start_length,1)]

num_periods = wec.data_length*pph + idle_start_length

# Create arrays to store all calculated data that will be displayed.
# This helps minimize the calculations occuring in the callback function and
# lets the dashboard update more smoothly
r2_sx_out = np.zeros(num_periods)
r1_e = np.zeros(num_periods)
r2_e = np.zeros(num_periods)
condenser_e = np.zeros(num_periods)
generated_kw = np.zeros(num_periods)
generated_kw_forecast = np.zeros(num_periods)
consumed_kw = np.zeros(num_periods)
battery_charge = [bat_start_charge]*(num_periods)
kw_to_battery_arr = np.zeros(num_periods)
grid_e = np.zeros(num_periods) 
r_1_1_sat = np.zeros(num_periods)
r_1_2_sat = np.zeros(num_periods)
r_1_3_sat = np.zeros(num_periods)
sx_sat = np.zeros(num_periods)
sx_filter_changes = np.zeros(num_periods)
r1_changovers = np.zeros(num_periods)
r1_1_state = ["idle"]*(num_periods)
r1_2_state = ["idle"]*(num_periods)
r1_3_state = ["idle"]*(num_periods)

bat_sp_arr = np.zeros(num_periods)
e_t_arr = np.zeros(num_periods)
d_arr = np.zeros(num_periods)

total_grid_hourly = np.zeros([24,12])
hour_tally = np.zeros([24,12])
month_tally = np.zeros(12)

# Initiate necessary variables
r2_prev = 0 
sx_sat_prev = 0
r1_changeovers_tally = 0
sx_sat_current = 0
sx_filter_tally = 0
reactor1_1 = pc.Reactor1()
reactor1_2 = pc.Reactor1()
reactor1_1.state = "active"
reactor2 = pc.Reactor2()
sx_filter = pc.Sx_filter()
battery = pc.Battery(bat_start_charge, ins.battery_specs)
energy_flow = wec.Energy_flow()
energy_tally = pph
r2_e_prev = 0
prev_month = 0
prev_hour = 0

forecast_arr = np.zeros(6)

# Calculate conditions at each hourly state and store in arrays
for hour in range(wec.data_length-12):
    state = wec.Hourly_state(hour, ins.solar_panel_specs, ins.wind_turbine_specs)

    # Forecast data
    for j in range(6):
        future_state = wec.Hourly_state(hour+j+1, ins.solar_panel_specs, ins.wind_turbine_specs)
        forecast_arr[j] = wec.calc_generated_kw(future_state)
    
    forecast_aggregated = (sum(forecast_arr[0:3]), sum(forecast_arr[3:7]))

    # Allow for multiple periods per hour
    for i in range(pph):
        period = hour*pph + i + idle_start_length
            
        # Energy flowing to the plant
        energy_generated = wec.calc_generated_kw(state)
        generated_kw[period] = energy_generated
        
        # Energy distribution for current period
        energy_tally, r2_e_prev, energy_flow = wec.distribute_energy(energy_generated,
                                                        generated_kw[period-pph],
                                                        energy_tally, 
                                                        r2_e_prev, 
                                                        energy_flow, 
                                                        battery, 
                                                        ins.b_sp_constants,
                                                        reactor2,
                                                        forecast_aggregated)
        
        # Update battery charge
        battery.charge += wec.battery_charge_differential(energy_flow.to_battery, battery)
        
        # Update arrays for battery charge, energy consumed by plant, 
        # energy directed to battery, and energy from grid
        battery_charge[period] = battery.charge
        consumed_kw[period] = energy_flow.to_r1 + energy_flow.to_r2 + energy_flow.to_condenser
        kw_to_battery_arr[period] = energy_flow.to_battery
        grid_e[period] = energy_flow.from_grid
        
        # Update array for condenser energy
        condenser_e[period] = energy_flow.to_condenser
        
        # Calculate reactor 2 state
        r2_sx_current = reactor2.react(energy_flow.to_r2, r2_prev)
        r2_sx_out[period] = r2_sx_current
        r2_e[period] = energy_flow.to_r2
        r2_prev = r2_sx_current
        
        # Calculate reactor 1 states and tally changeovers
        r1_changeovers_tally = pc.update_reactor_1(r2_sx_current, r1_changeovers_tally, reactor1_1, reactor1_2)
        r_1_1_sat[period] = reactor1_1.saturation
        r_1_2_sat[period] = reactor1_2.saturation
        r1_1_state[period] = reactor1_1.state
        r1_2_state[period] = reactor1_2.state
        r1_e[period] = energy_flow.to_r1
        r1_changovers[period] = r1_changeovers_tally
        
        # Update Sx filter saturation and tally filter changes
        sx_sat_current, sx_filter_tally = pc.update_sx_filter(sx_sat_current, sx_filter_tally, sx_filter, r2_sx_current)
        sx_filter_changes[period] = sx_filter_tally
        sx_sat[period] = sx_sat_current
        
        # Add up energy taken from grid. This will be used for graph in Tab 2
        if energy_flow.from_grid > 0: 
            total_grid_hourly[state.hour_of_day][state.month-1] += energy_flow.from_grid/pph
        
        if prev_hour != state.hour_of_day: hour_tally[state.hour_of_day][state.month-1] += 1
        if prev_month != state.month: month_tally[state.month-1] += 1
        
        prev_hour = state.hour_of_day
        prev_month = state.month

# Energy allocation figure
fig_e_allo = make_subplots(rows=1,cols=1,
                           specs=[[dict(secondary_y= True)]])
fig_e_allo.add_trace(go.Scatter(x=[], y=[], mode="lines", 
                                name="Energy produced by renewables"),
                     row=1, col=1, secondary_y=False)
fig_e_allo.add_trace(go.Scatter(x=[], y=[], mode= "lines", 
                                name="Energy allocated to plant"),
                     row=1, col=1, secondary_y=False)
fig_e_allo.add_trace(go.Scatter(x=[], y=[], mode= "lines", 
                                name="Battery charge"),
                     row=1, col=1, secondary_y=True)
fig_e_allo.update_xaxes(title_text="Minutes before present", 
                        range=[-idle_start_length,0],
                        row=1, col=1)
fig_e_allo.update_yaxes(title_text="kW produced/consumed", range=[0,1500], 
                        secondary_y=False, row=1, col=1)
fig_e_allo.update_yaxes(title_text="kWh stored in battery", range=[0,battery.max_charge*1.05], 
                        secondary_y=True, row=1, col=1)
fig_e_allo.update_layout(title_text="Energy Allocation", title_x=0.5,
                         title=dict(yref="paper",
                                    y=1, 
                                    yanchor="bottom", 
                                    pad=dict(b=20)),
                         legend=dict(yanchor="top", 
                                     xanchor="left", 
                                     y=0.99, 
                                     x=0.01),
                         margin=graph_margin)

# Reactor 2 output figure
fig_r2 = make_subplots(rows=1,cols=1, specs=[[dict(secondary_y= True)]])
fig_r2.add_trace(go.Scatter(x=[], y=[], mode= "lines", name="Sx produced"),
                     row=1, col=1, secondary_y=False)
fig_r2.add_trace(go.Scatter(x=[], y=[], mode= "lines", name="Energy input"),
                     row=1, col=1, secondary_y=True)
fig_r2.update_xaxes(title_text="Minutes before present", range=[-500,0],
                          row=1, col=1)
fig_r2.update_yaxes(title_text="mol Sx per hour", range=[0,200], 
                    secondary_y=False, row=1, col=1)
fig_r2.update_yaxes(title_text="kW", range=[0,1200], 
                    secondary_y=True, row=1, col=1)
fig_r2.update_layout(title_text="Sx production over time", title_x=0.5,
                     title=dict(yref="paper", 
                                y=1, 
                                yanchor="bottom", 
                                pad=dict(b=20)),
                     legend=dict(yanchor="top", xanchor="left", y=0.99, x=0.01),
                     margin=graph_margin)

# Reactor 2 reaction curve figure
r2_rxn_curve_x = np.linspace(0,600,20)
r2_rxn_curve_y= [reactor2.ss_output(i) for i in r2_rxn_curve_x]

fig_r2_rxn = make_subplots(rows=1,cols=1)
fig_r2_rxn.add_trace(go.Scatter(x=[], y=[], mode="lines", 
                                name="R2 reaction curve"), row=1, col=1)
fig_r2_rxn.add_trace(go.Scatter(x=[], y=[], marker=dict(color="red", size=20),
                                mode="markers", name="Current state"), 
                     row=1, col=1)
fig_r2_rxn.update_xaxes(title_text="kW", range=[0,600], row=1, col=1)
fig_r2_rxn.update_yaxes(title_text="mol Sx per hour", range=[0,60], 
                        row=1, col=1)
fig_r2_rxn.update_layout(title_text="Steady state Sx output versus energy", 
                         title_x=0.5,
                         title=dict(yref="paper", 
                                    y=1, 
                                    yanchor="bottom", 
                                    pad=dict(b=20)),
                         legend=dict(yanchor="bottom", 
                                     xanchor="right", 
                                     y=0.02, 
                                     x=0.99),
                         margin=graph_margin)


def update(n_intervals, start_watch, counter):
    
    def data_update(counter):
        period = counter + idle_start_length
        
        # Energy to battery
        kw_to_battery = kw_to_battery_arr[period]
        
        # Create timestamp
        state = wec.Hourly_state(math.floor(counter/pph), ins.solar_panel_specs, ins.wind_turbine_specs)
        time = state.time
        
        # Energy generated by renewables
        kw_gen = generated_kw[period]
        
        # Battery level figure
        bat_lvl_full = battery_charge[period]
        bat_lvl_empty = battery.max_charge - battery_charge[period]
        fig_bat_lvl = go.Figure(data=[go.Bar(x=[1], y=[bat_lvl_full], 
                                              marker_color="green"),
                                      go.Bar(x=[1], y=[bat_lvl_empty],  
                                              marker_color="gray")])
        fig_bat_lvl.update_layout(title_text="Battery Level", 
                                  title_x=0.5, title_y=0.96,
                                  barmode='stack', paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor='rgba(0,0,0,0)', showlegend=False,
                                  margin=dict(l=20, r=20, t=20, b=20), height=200,
                                  width=150,
                                  autosize=False)
        fig_bat_lvl.update_xaxes(showticklabels=False)
        fig_bat_lvl.update_yaxes(tickmode="array", tickvals=[round(bat_lvl_full)])
        
        # Image for energy flow to/from battery
        if kw_to_battery > 0:
            img_bat = "assets/to_bat.png"
        elif kw_to_battery < 0:
            img_bat = "assets/from_bat.png"
        else:
            img_bat = "assets/idle_bat.png"
            
        # Image for energy from renewables
        if kw_gen == 0:
            img_windmill = "assets/idle_renew.png"
        else:
            img_windmill = "assets/from_renew.png"
            
        # Image for energy from grid
        if grid_e[period] == 0:
            img_grid = "assets/idle_grid.png"
        elif grid_e[period] > 0:
            img_grid = "assets/from_grid.png"
        else:
            img_grid = "assets/to_grid.png"
            
        # Image for reactor 1 status's
        if r1_1_state[period] == "active" and \
            r1_2_state[period] == "idle":
                img_r1_status = "assets/1active_2idle_3idle.png"
        elif r1_1_state[period] == "active" and \
            r1_2_state[period] == "cleaning":
                img_r1_status = "assets/1active_2cleaning_3idle.png"
        elif r1_1_state[period] == "cleaning" and \
            r1_2_state[period] == "active":
                img_r1_status = "assets/1cleaning_2active_3idle.png"
        elif r1_1_state[period] == "idle" and \
            r1_2_state[period] == "active":
                img_r1_status = "assets/1idle_2active_3idle.png"
        else:
            img_r1_status = "assets/1idle_2idle_3idle.png"

        # Figure for 1st r1 saturation
        r1_1_saturation = r_1_1_sat[period]
        r1_1_available = 100 - r1_1_saturation
        fig_lvl_r1_1 = go.Figure(data=[go.Bar(x=[1], y=[r1_1_saturation], 
                                              marker_color="aqua"),
                                      go.Bar(x=[1], y=[r1_1_available],  
                                              marker_color="silver")])
        fig_lvl_r1_1.update_layout(title_text="", title_x=0.5, title_y=0.96,
                                  barmode='stack', paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor='rgba(0, 0, 0, 0)', showlegend=False,
                                  margin=dict(l=20, r=20, t=20, b=20), height=150,
                                  width=100)
        fig_lvl_r1_1.update_xaxes(showticklabels=False)
        fig_lvl_r1_1.update_yaxes(tickmode="array", 
                                  tickvals=[round(r1_1_saturation)])
        
        # Figure for 2nd r1 saturation
        r1_2_saturation = r_1_2_sat[period]
        r1_2_available = 100 - r1_2_saturation
        fig_lvl_r1_2 = go.Figure(data=[go.Bar(x=[1], y=[r1_2_saturation], 
                                              marker_color="aqua"),
                                      go.Bar(x=[1], y=[r1_2_available], 
                                              marker_color="silver")])
        fig_lvl_r1_2.update_layout(title_text="", title_x=0.5, title_y=0.96,
                                  barmode='stack', paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor='rgba(0, 0, 0, 0)', showlegend=False,
                                  margin=dict(l=20, r=20, t=20, b=20), height=150,
                                  width=100)
        fig_lvl_r1_2.update_xaxes(showticklabels=False)
        fig_lvl_r1_2.update_yaxes(tickmode="array", 
                                  tickvals=[round(r1_2_saturation)])
        
        # Figure for 3rd r1 saturation
        r1_3_saturation = r_1_3_sat[period]
        r1_3_available = 100 - r1_3_saturation
        fig_lvl_r1_3 = go.Figure(data=[go.Bar(x=[1], y=[r1_3_saturation], 
                                              marker_color="aqua"),
                                      go.Bar(x=[1], y=[r1_3_available],  
                                              marker_color="silver")])
        fig_lvl_r1_3.update_layout(title_text="", title_x=0.5, title_y=0.96,
                                  barmode='stack', paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor='rgba(0, 0, 0, 0)', showlegend=False,
                                  margin=dict(l=20, r=20, t=20, b=20), height=150,
                                  width=100)
        fig_lvl_r1_3.update_xaxes(showticklabels=False)
        fig_lvl_r1_3.update_yaxes(tickmode="array", 
                                  tickvals=[round(r1_3_saturation)])
        
        # Tally for r1 changeovers
        r1_changeover_tally = r1_changovers[period]
        
        # Counter for Sx filter changes
        sx_changeovers = sx_filter_changes[period]
        
        # Figure for Sx filter saturation
        sx_saturation = sx_sat[period]
        sx_available = 100 - sx_saturation
        fig_sx_sat = go.Figure(data=[go.Bar(x=[1], y=[sx_saturation], 
                                            marker_color="yellow"),
                                      go.Bar(x=[1], y=[sx_available], 
                                              marker_color="silver")])
        fig_sx_sat.update_layout(title_text="", title_x=0.5, title_y=0.96,
                                  barmode='stack', paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor='rgba(0, 0, 0, 0)', showlegend=False,
                                  margin=dict(l=20, r=20, t=20, b=20), height=150,
                                  width=100)
        fig_sx_sat.update_xaxes(showticklabels=False)
        fig_sx_sat.update_yaxes(tickmode="array", tickvals=[round(sx_saturation)])
        
        # Update the data on the 5 bottom graphs. Since extendData property is used,
        # only the data is refreshed and the whole graphs don't need to be updated.

        e_allocation = [
            dict(x=[x, x, x], 
                  y=[
                      [generated_kw[i] for i in range(counter,period + 1)],
                      [consumed_kw[i] for i in range(counter,period + 1)],
                      [battery_charge[i] for i in range(counter,period + 1)]
                    ]
                  ),
                [0,1,2], 
                idle_start_length + 1, 
                idle_start_length + 1, 
                idle_start_length + 1]
        
        r2_updates = [
            dict(x=[x, x], 
                  y=[
                      [r2_sx_out[i] for i in range(counter,period + 1)],
                      [r2_e[i] for i in range(counter,period + 1)]
                    ]
                  ),
                [0,1], 
                idle_start_length + 1, 
                idle_start_length + 1] 

        r2_rxn_updates = [
                dict(x=[r2_rxn_curve_x, [r2_e[period]]*20], 
                      y=[
                          r2_rxn_curve_y,
                          [reactor2.ss_output(r2_e[period])]*20
                        ]
                      ),
                    [0,1], 
                    20, 
                    1]

        return (round(kw_to_battery,1), 
                time.strftime("%d-%m-%Y %H:%M"), 
                fig_bat_lvl, 
                img_bat,
                img_windmill,
                img_grid, 
                round(kw_gen,1), 
                round(grid_e[period],1), 
                round(r1_e[period],2), 
                round(r2_e[period],1),
                round(condenser_e[period],2), 
                img_r1_status,
                fig_lvl_r1_1, 
                fig_lvl_r1_2, 
                fig_lvl_r1_3, 
                r1_changeover_tally, 
                sx_changeovers, 
                fig_sx_sat, 
                e_allocation, 
                r2_updates,
                r2_rxn_updates,
                counter)
    
    if start_watch:
        return data_update(counter+1)
    
    else:
        return data_update(counter)

#-----------------------------------------------------------------------------
# Tab 2: Plot grid consumption 

months = ['January',
          'February',
          'March',
          'April',
          'May',
          'June',
          'July',
          'August',
          'September',
          'October',
          'November',
          'December']

# Colors for legend
colors = ['#1e00ff',
        '#a300e5',
        '#dd00c6',
        '#ff00a5',
        '#ff0085',
        '#ff0067',
        '#ff0067',
        '#ff0085',
        '#ff00a5',
        '#dd00c6',
        '#a300e5',
        '#1e00ff']

# y axis values
ave_grid_hourly = total_grid_hourly / hour_tally

fig_grid_cons = make_subplots(rows=1,cols=1)
for i in range(len(months)):
    fig_grid_cons.add_trace(go.Scatter(x=[x for x in range(24)], y=ave_grid_hourly[:,i], 
                             mode="lines", name=months[i], line_color=colors[i]),
                            row=1, col=1)
    
fig_grid_cons.update_xaxes(title_text="Time of day (hour)", row=1, col=1)
fig_grid_cons.update_yaxes(title_text="Average kWh from grid", range=[-1,15], row=1, col=1)
fig_grid_cons.update_layout(title_text="Average energy needed from grid per hour by month", 
                            title_x=0.5, height=650)