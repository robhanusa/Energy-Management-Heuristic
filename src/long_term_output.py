# -*- coding: utf-8 -*-
"""
Created on Mon Jun 26 08:47:37 2023

@author: rhanusa
"""
import re
import numpy as np
import pandas as pd
import gurobipy as gp
import statsmodels.api as sm
from gurobipy import GRB
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from . import doe_functions as doef
from .weather_energy_components import years

parameters = {
    "wt_list": [0, 1],  # Number of 1MW wind turbines
    "sp_list": [5000, 10000, 15000],  # Area in m2 of solar panels
    "b_list": [516, 1144, 2288],  # Battery sizes in kW
    "c1_list": [0, 1, 2],  # Constants for r2_max eqn
    "c2_list": [0, 1, 2],
    "c3_list": [-1, 0, 1]
    }

# DOE input is a 2-level full factorial plus a Box-Behnken to capture curvature
doe = pd.read_excel("data/DOE.xlsx")

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

# Note that some variables have the suffix _f (for fixed) or _uf for unfixed.
# This indicates whether the list/array shrinks as variables are eliminated.


def fit_results(doe_results, remove_var=None):
    X_features = doe_results[["wt_level", "sp_level", "b_level", "c1_level", "c2_level", "c3_level"]]
    y = doe_results["profit"]
    
    model = PolynomialFeatures(degree=2)
    
    fit_tr_model = model.fit_transform(X_features)
    features = model.get_feature_names_out()
    X = pd.DataFrame(fit_tr_model, columns=features)
    
    indices_to_remove = []
    
    # Remove higher order terms of 'remove_var'. Leave the first order term.
    if remove_var:
        for i in range(len(features)):
            feature = features[i] 
            
            # Searching for " " or "^" ensures only higher-order terms are removed
            if remove_var in feature and (" " in feature or "^" in feature):
                indices_to_remove.append(i)
                X.drop(columns=[feature], inplace=True)
                    
        features = np.delete(features, indices_to_remove)
    
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



def backward_elimination(est_fit, X, y, feature_names_uf):
    """
        Deletes highest p-value terms one at a time, if no higher-order terms exist,
        until all (elegible) terms have a p-value of < 0.05
    """
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


def generate_sig_model(doe_results, remove_var=None):
    """
        Generate a pd.Series of coefficients for only the significant factors and
        their 1st-order terms
    """
    
    X, y, est_fit, feature_names = fit_results(doe_results, remove_var=remove_var)  
    est_sig_fit, feature_names = backward_elimination(est_fit, X, y, feature_names)
    
    coefs = est_sig_fit.params
    
    return coefs

coefs = generate_sig_model(doe_results)

#%% Create Gurobi model to optimize DOE results

# Create Gurobi environment and suppress output
env = gp.Env(empty=True)
env.setParam("OutputFlag", 0)
env.start()


def optimize_model(coefs):
    """
        Optimizes model based on the series of coefficients for each factor.
        Returns a Gurobi Model object and prints the optimal factor values
    """
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