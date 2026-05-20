# -*- coding: utf-8 -*-
"""
Created on Mon Jun 26 08:47:37 2023

@author: rhanusa
"""
import numpy as np
from weather_energy_components import years
import pandas as pd
import doe_functions as doef 

# # Capex lifetime to calculate value of capex per year
# capex_life = 10

# def generate_wt_specs(wt):
#     wind_turbine_specs = {
#         "cut_in": 13, # km/h
#         "rated_speed": 50, # km/h
#         "cut_out": 100, # km/h
#         "max_energy": 1000, # kW
#         "count": wt,
#         "cost": wt*1.5*10**6 # EUR/MW 
#         }
    
#     return wind_turbine_specs

# def generate_sp_specs(sp):
#     solar_panel_specs = {
#         "area": sp, # m^2
#         "efficiency": 0.1,
#         "cost": sp*200/1.1 # $200/m2 (/1.1 eur to usd)
#         }
    
#     return solar_panel_specs

# def generate_b_specs(b):
#     battery_specs = { 
#         "max_charge": b, # kWh
#         "cost": 1000*b
#         }
    
#     return battery_specs

# # Pre-calculate forecast data. The forecast contains the total predicted energy generation
# # over (1) the next 3 hours, and (2) hours 4-6 after the present. As the energy generation
# # is dependent on solar panel coverage and number of wind turbines, forecasts are made
# # for every combination of sp and wt values input in the DOE. Here, a perfect forecast
# # is assumed, so real weather data is used.
# def prep_forecast(parameters):
#     wt_list = parameters["wt_list"]
#     sp_list = parameters["sp_list"]
    
#     forecast_store = np.zeros([len(wt_list), len(sp_list), wec.data_length-6, 2])
#     forecast_arr = np.zeros(6)
    
#     for i in range(len(wt_list)):
#         wt = wt_list[i]
#         wind_turbine_specs = generate_wt_specs(wt)
        
#         for j in range(len(sp_list)):
#             sp = sp_list[j]
#             solar_panel_specs = generate_sp_specs(sp)
    
#             for hour in range(wec.data_length-6):
#                 for k in range(6): 
#                     future_state = wec.Hourly_state(hour+k+1, solar_panel_specs, wind_turbine_specs)
#                     forecast_arr[k] = wec.calc_generated_kw(future_state)
                
#                 forecast_store[i][j][hour][0] = sum(forecast_arr[0:3])
#                 forecast_store[i][j][hour][1] = sum(forecast_arr[3:7])
                
#     return forecast_store


# # Run a single DOE scenario to calculate profit at specified conditions in 'run'
# def run_scenario(forecast_store, parameters, run):
    
#     # factor levels are between 0 and 2 to match indicies 
#     # wt is a special case because only 2 levels are considered
#     wt_index = int(run["wt_level"]) if int(run["wt_level"]) == 0 else 1
#     sp_index = int(run["sp_level"]) 
#     b_index = int(run["b_level"])
#     c1_index = int(run["c1_level"])
#     c2_index = int(run["c2_level"])
#     c3_index = int(run["c3_level"])
    
#     wt_list = parameters["wt_list"]
#     sp_list = parameters["sp_list"]
#     b_list = parameters["b_list"]
#     c1_list = parameters["c1_list"]
#     c2_list = parameters["c2_list"]
#     c3_list = parameters["c3_list"]
    
#     wt = wt_list[wt_index]
#     sp = sp_list[sp_index]
#     b = b_list[b_index]
#     c1 = c1_list[c1_index]
#     c2 = c2_list[c2_index]
#     c3 = c3_list[c3_index]
    
#     battery_specs = generate_b_specs(b)

#     solar_panel_specs = generate_sp_specs(sp)
    
#     wind_turbine_specs = generate_wt_specs(wt)
    
#     b_sp_constants = {
#         "c1": c1,
#         "c2": c2,
#         "c3": c3
#         }

#     # initialize counters
#     e_from_grid = 0 # kwh
#     e_to_grid = 0 # kwh
#     total_renewable = 0 # kwh
#     total_sx = 0 # mol
    
#     # Initiate other necessary variables
#     r2_prev = 0 
#     reactor1_1 = pc.Reactor1()
#     reactor1_1.state = "active"
#     reactor2 = pc.Reactor2()
#     battery = pc.Battery(0.5*battery_specs["max_charge"], battery_specs)
#     energy_flow = wec.Energy_flow()
#     energy_tally = pph
#     r2_e_prev = 0
#     p_renew_tmin1 = 0
    
#     # Calculate conditions at each hourly state and add to previous state
#     for hour in range(wec.data_length-12):
#         state = wec.Hourly_state(hour, solar_panel_specs, wind_turbine_specs)
        
#         # Energy flowing to the plant
#         p_renew_t_actual = wec.calc_generated_kw(state)
#         total_renewable += p_renew_t_actual
        
#         forecast = (forecast_store[wt_index][sp_index][hour][0],
#                     forecast_store[wt_index][sp_index][hour][1])
        
#         # Allow for multiple periods per hour
#         for i in range(pph):
            
#             # Energy distribution for current period
#             energy_tally, r2_e_prev, energy_flow = wec.distribute_energy(p_renew_t_actual,
#                                                             p_renew_tmin1,
#                                                             energy_tally, 
#                                                             r2_e_prev, 
#                                                             energy_flow, 
#                                                             battery, 
#                                                             b_sp_constants,
#                                                             reactor2,
#                                                             forecast)
                   
#             # Update battery charge
#             battery.charge += wec.battery_charge_differential(energy_flow.to_battery, battery)
            
#             # Calculate reactor 2 state
#             r2_sx_current = reactor2.react(energy_flow.to_r2, r2_prev)
            
#             # Calculate total sulfur production
#             total_sx += r2_sx_current/pph
            
#             r2_prev = r2_sx_current
            
#             # Add up energy taken from grid
#             if energy_flow.from_grid > 0:
#                 e_from_grid += energy_flow.from_grid/pph
                
#             if energy_flow.from_grid < 0:
#                 e_to_grid -= energy_flow.from_grid/pph
                
#         p_renew_tmin1 = p_renew_t_actual
    
#     # spread capex cost over 'capex_life' in years
#     capex = (battery_specs["cost"] + solar_panel_specs["cost"] + wind_turbine_specs["cost"])/capex_life
    
#     # Target production is 240 kmol S per year, so it is assumed that S above this 
#     # value is worth 0
#     revenue = (9.6*min(total_sx, 240000*years) + 0.1*e_to_grid)/years # revenue / year
    
#     # Roughly 15 kW required to make 1 mol S
#     opex = 0.25*e_from_grid/years # opex / year
    
#     profit = revenue - opex - capex # profit / year
    
#     return profit, revenue, opex, capex, total_sx, e_to_grid, e_from_grid

# # This is the most CPU intensive function that runs run_scenario function for each 
# # run in the DOE
# def run_doe(doe, parameters, forecast_store = 0, show_run_status = True ):
    
#     doe[["profit", "revenue", "opex", "capex", "total_sx", "e_to_grid", "e_from_grid"]] = np.zeros([len(doe), 7])
    
#     # To save time, the forecast_store may be input into run_doe if it exists
#     if not isinstance(forecast_store, np.ndarray):
#         forecast_store = prep_forecast(parameters)
    
#     for i in range(len(doe)):
        
#         start = time.time()
        
#         run = doe.iloc[i]
        
#         profit, revenue, opex, capex, total_sx, e_to_grid, e_from_grid = run_scenario(forecast_store, parameters, run)
#         doe["profit"][i] = profit
#         doe["revenue"][i] = revenue
#         doe["opex"][i] = opex
#         doe["capex"][i] = capex
#         doe["total_sx"][i] = total_sx
#         doe["e_to_grid"][i] = e_to_grid
#         doe["e_from_grid"][i] = e_from_grid
        
#         end = time.time()
        
#         if show_run_status: 
#             print("Run: ", i)
#             print("Time elapsed: ", end - start)
        
#     return doe, forecast_store

parameters = {
    "wt_list" : [0, 1], # number of 1MW wind turbines
    "sp_list" : [5000, 10000, 15000], # area in m2 of solar panels
    "b_list" : [516, 1144, 2288], # battery sizes in kW
    "c1_list" : [0, 1, 2], # constants for r2_max eqn
    "c2_list" : [0, 1, 2],
    "c3_list" : [-1, 0, 1]
    }

# DOE input is a 2-level full factorial plus a Box-Behnken to capture curvature
doe = pd.read_excel("DOE.xlsx")

# Run DOE
doe_results, forecast_store = doef.run_doe(doe, parameters) 

#%% Necessary functions

def get_index(a, b):
    for i in range(len(a)):
       if a[i] == b:
           return i

# Create boolean array that indicates thes lower order terms for each term in the model
def make_lot_array(feature_names):
    lower_order_terms = np.full((len(feature_names), len(feature_names)), False)

    for i in range(len(feature_names)):
        feature = feature_names[i]
        
        # find 1st order terms for squared features
        if "^" in feature:
            first_order_term = re.search("^[a-z0-9_]*",feature).group(0)  
            first_order_term_index = get_index(feature_names, first_order_term)
            lower_order_terms[i, first_order_term_index] = True
                
        # find 1st order terms for interactions
        if " " in feature:
            first_order_term1 = re.search("^[a-z0-9_]*",feature).group(0)
            first_order_term2 = re.search("[a-z0-9_]*$",feature).group(0)      
            first_order_term1_index = get_index(feature_names, first_order_term1)
            first_order_term2_index = get_index(feature_names, first_order_term2)
            lower_order_terms[i, first_order_term1_index] = True
            lower_order_terms[i, first_order_term2_index] = True
            
            # find interactions that contain a 1st order term also present in squared term
            feature1_squared = first_order_term1 + "^2"
            feature2_squared = first_order_term2 + "^2"
            feature1_squared_index = get_index(feature_names, feature1_squared)
            feature2_squared_index = get_index(feature_names, feature2_squared)
            lower_order_terms[feature1_squared_index, i] = True
            lower_order_terms[feature2_squared_index, i] = True
            
    return lower_order_terms

#%%
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import statsmodels.api as sm
import re

# Note that some variables have the suffix _f (for fixed) or _uf for unfixed.
# This indicates whether the list/array shrinks as variables are eliminated.

def fit_results(doe_results, remove_var=None):
    X_features = doe_results[["wt_level", "sp_level", "b_level", "c1_level", "c2_level", "c3_level"]]
    y = doe_results["profit"]
    
    model = PolynomialFeatures(degree=2)
    
    fit_tr_model = model.fit_transform(X_features)
    features = model.get_feature_names_out()
    X = pd.DataFrame(fit_tr_model, columns=features)
    
    indicies_to_remove = []
    
    # Remove higher order terms of 'remove_var'. Leave the first order term.
    if remove_var:
        for i in range(len(features)):
            feature = features[i] 
            
            # Searching for " " or "^" ensures only higher-order terms are removed
            if remove_var in feature and (" " in feature or "^" in feature):
                indicies_to_remove.append(i) 
                X.drop(columns=[feature], inplace=True)
                    
        features = np.delete(features, indicies_to_remove)
    
    lr_model = LinearRegression()
    lr_model.fit(fit_tr_model, y)
    
    est = sm.OLS(y, X)
    est_fit = est.fit()
    print("Initial results:")
    print(est_fit.summary())

    return X, y, est_fit, features

X, y, est_fit, feature_names = fit_results(doe_results)

#%%

# According to https://www.biostat.jhsph.edu/~iruczins/teaching/jf/ch10.pdf
# we shouldn't remove a lower-order feature that is a factor of a higher order
# term. Also, interactions are a form of lower-order term and should not be removed 
# unless all higher order terms also are. (e.g. don't remove x1*x2 unless x1^2 and
# x2^2 are also gone) To enable this, we make the lower_order_term matrix.

lower_order_terms_f = make_lot_array(feature_names)
inds_of_remaining_terms = list(range(len(feature_names)))

# Matches index to feature in lower_order_terms_f
feature_index_dict_f = {feature_names[i]:i for i in range(len(feature_names))}

feature_names_uf = feature_names

# Deletes highest p-value terms one at a time, if no higher-order terms exist,
# until all (elegible) terms have a p-value of < 0.05
def backward_elimination(est_fit, X, y, feature_names_uf):
    pvals = est_fit.pvalues
    
    while max(pvals[1:]) > 0.05:

        highest_pval_index = np.argmax(pvals[1:]) + 1
        feature_to_remove = feature_names_uf[highest_pval_index]
        feature_index = feature_index_dict_f[feature_to_remove]
        
        if not any(lower_order_terms_f[inds_of_remaining_terms, feature_index]):
            X.drop(columns=[feature_to_remove], inplace=True)
            feature_names_uf = np.delete(feature_names_uf, highest_pval_index)
            inds_of_remaining_terms[feature_index] = 0
            
            est_fit = sm.OLS(y, X).fit()
            pvals = est_fit.pvalues
            print(est_fit.summary())
        else:
            pvals[highest_pval_index] = 0
        
    return est_fit, feature_names_uf

        
est_fit, feature_names_uf = backward_elimination(est_fit, X, y, feature_names)

print(est_fit.summary())


#%% Generate a model for profit as a function of the input parameters

# Generate a pd.Series of coefficients for only the significant factors and 
# their 1st-order terms
def generate_sig_model(doe_results, remove_var=None):
    
    X, y, est_fit, feature_names = fit_results(doe_results, remove_var=remove_var)  
    est_sig_fit, feature_names = backward_elimination(est_fit, X, y, feature_names)
    
    coefs = est_sig_fit.params
    
    return coefs

coefs = generate_sig_model(doe_results)

#%% Create Gurobi model to optimize DOE results
import gurobipy as gp
from gurobipy import GRB

# Create Gurobi environment and suppress output
env = gp.Env(empty=True)
env.setParam("OutputFlag", 0)
env.start()

# Optimizes model based on the series of coefficients for each factor.
# Returns a Gurobi Model object and prints the optimal factor values
def optimize_model(coefs):
    model = gp.Model(env=env)
    model.setParam('NonConvex', 2) # To allow for quadratic equality constraints
    
    factors_dict = {}
    
    # Create gurobi variables
    for factor in coefs.index:
        if '^' not in factor and ' ' not in factor:
            factors_dict[factor] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=2, name=factor)
        else:
            factors_dict[factor] = model.addVar(vtype=GRB.CONTINUOUS, name=factor)
    
    # Add equality constraints
    for f in factors_dict:
        if f == '1': # Must maintain constant term, constrain this to 1
            factor = factors_dict[f]
            model.addConstr(factor == 1)
        if '^' in f: # Squared terms must be equal to the square of the first-order term
            first_order_f = re.search("^[a-z0-9_]*", str(f)).group(0) 
            first_order_factor = factors_dict[first_order_f]
            factor = factors_dict[f]
            model.addConstr(factor == first_order_factor**2)
        if ' ' in f: # Interaction terms must be the product of the first-order terms
            first_order_f1 = re.search("^[a-z0-9_]*", str(f)).group(0)
            first_order_f2 = re.search("[a-z0-9_]*$", str(f)).group(0)
            first_order_factor1 = factors_dict[first_order_f1]
            first_order_factor2 = factors_dict[first_order_f2]
            factor = factors_dict[f]
            model.addConstr(factor == first_order_factor1 * first_order_factor2)
            
    # Objective function
    model.setObjective(gp.quicksum(coefs[factor]*factors_dict[factor] for factor in factors_dict),
                        GRB.MAXIMIZE)    
    
    model.optimize()
    
    for var in model.getVars():
        print(var.varName, '=', var.x)
    print('objective value: ', model.objVal)
    
    return model

model = optimize_model(coefs)

#%% Optimal model is at corner point, so re-run with new parameter values, 
# setting wind turbine equal to 1. The results of the first DOE
# make it clear that 1 wind turbine is better than 0. Because they're so expensive,
# we'll assume that a 2nd isn't an option. In practice, a 2nd wind turbine might
# increase revenue by producing a large excess of energy for the grid. As the goal
# of this plant is to produce Sx and not energy, it is reasonable to limit the 
# model to 1 wind turbine
# Because of this, we can also reduce the size of the DOE to eliminate wt = 0.
# This is saved in DOE2.xlsx

parameters2 = {
    "wt_list" : [1], # number of 1MW wind turbines
    "sp_list" : [2000, 5000, 8000], # area in m2 of solar panels
    "b_list" : [263, 516, 1144], # battery sizes in kW
    "c1_list" : [1, 2, 3], # constants for battery setpoint eqn
    "c2_list" : [1, 2, 3],
    "c3_list" : [0, 1, 2]
    }

# New DOE which removes the wind turbine feature and assumes it is fixed at 1
doe2 = pd.read_excel("DOE2.xlsx")

# Run DOE
doe_results2, _ = doef.run_doe(doe2, parameters2)

coefs2 = generate_sig_model(doe_results2, remove_var='wt_level')

model2 = optimize_model(coefs2)

#%%

parameters3 = {
    "wt_list" : [1], # Only the case with 1 wind turbine is considered
    "sp_list" : [4000, 6500, 9000], # area in m2 of solar panels
    "b_list" : [0, 263, 516], # battery sizes in kW
    "c1_list" : [2, 3, 4], # constants for battery setpoint eqn
    "c2_list" : [2, 3, 4],
    "c3_list" : [-1, 0, 1]
    }

# DOE form doesn't change, so no new DOE is loaded

# Run DOE
doe_results3, _ = doef.run_doe(doe2, parameters3)

coefs3 = generate_sig_model(doe_results3, remove_var='wt_level')

model3 = optimize_model(coefs3)

#%% Results suggest it is optimal to have no battery. This is reasonable, as it
# suggests the cost of the battery is too high to be offset by the energy from 
# grid we must buy when renewable energy production is low.
# As all the constants relate to parameters for determining battery set point, 
# they are no longer relevant in the model and will be set to 0 for the next 
# calculation.
# Below, we calculate the expected results at this optimal level

parameters_final = {
    "wt_list" : [1], # Only the case with 1 wind turbine is considered
    "sp_list" : [6500], # area in m2 of solar panels
    "b_list" : [0], # battery sizes in kW
    "c1_list" : [0], # constants for battery setpoint eqn
    "c2_list" : [0],
    "c3_list" : [0]
    }

run = pd.Series([0, 0, 0, 0, 0, 0], ["wt_level", "sp_level", "b_level", "c1_level",
                                     "c2_level", "c3_level"])

profit, revenue, opex, capex, total_sx, e_to_grid, e_from_grid \
    = doef.run_scenario(forecast_store, parameters_final, run)
    
print("Profit (€/yr): ", round(profit))
print("Revenue (€/yr): ", round(revenue))
print("Opex (€/yr): ", round(opex))
print("Capex (€/yr): ", round(capex))
print("Sulfur (kmol/yr): ", round(total_sx/years/1000))
print("Energy sold to grid (MW/yr): ", round(e_to_grid/years/1000, 1))
print("Energy purchased from grid (MW/yr): ", round(e_from_grid/years/1000, 1))