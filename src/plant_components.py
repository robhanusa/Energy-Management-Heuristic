# -*- coding: utf-8 -*-
"""
Created on Wed May 17 07:44:15 2023

@author: rhanusa
"""
import math

# periods per hour. Reactor states will be calculated "pph" times per hour. eg
# if pph = 10, states are calculated every 1hr/10 = 6 min. This is necessary because 
# the weather data hourly, but plant state is calculated more frequently
pph = 1

class Battery:
    def __init__(self, charge, specs):
        self.charge = charge
        self.max_charge = specs['max_charge']
        self.cost = specs['cost']
        
        # Note that battery efficiency (below) is normally dependent on charge. 
        # Assume this efficiency is correct for 20-80% charge, which will be our
        # operating range.
        self.efficiency = 0.95
    
class Reactor1():
    def __init__(self):
        self.state = "idle"
        self.saturation = 0
        self.sat_factor = .01 # How fast r1 gets saturated per mol COS produced
        self.clean_speed = 10 # How fast r1 gets cleaned
        
    @classmethod 
    def react(cls, sx_produced):
        cos_produced = sx_produced
        Reactor1.state = "active"
        return cos_produced
         
class Reactor2: 
    ku = .5/pph
    kd = .5/pph
    
    def __init__(self):
        self.state = "idle"
        
    @classmethod
    def ss_output(cls, energy):
        return 140/(1 + math.exp(-energy/200 + 3)) - 6 #reduced this by a factor of 10
    
    def react(cls, energy, prev):
        Reactor2.state = "active"
        e_t = Reactor2.ss_output(energy)-prev
        if e_t > 0:
            return prev + e_t*(1-1/(math.exp(1/(pph*Reactor2.ku))))
        else:
            return prev + e_t*(1-1/(math.exp(1/(pph*Reactor2.kd))))
        
class Sx_filter:
    sat_factor = .003 # Sx filter saturation speed
    
def update_reactor_1(r2_sx_current, r1_changeovers_tally, reactor1_1, reactor1_2):
    r1_sat_factor = reactor1_1.sat_factor
    r1_clean_speed = reactor1_1.clean_speed
    if reactor1_1.state == "active":
        r1_cos_current = reactor1_1.react(r2_sx_current) / 0.9 # Project assumption is 90% conversion rate for r2
        reactor1_1.saturation += r1_cos_current / pph * r1_sat_factor
        if reactor1_1.saturation >= 100:
            reactor1_1.saturation -= r1_cos_current / pph * r1_sat_factor
            reactor1_1.state = "cleaning"
            reactor1_2.state = "active"
            r1_changeovers_tally += 1
            
    elif reactor1_2.state == "active":
        r1_cos_current = reactor1_2.react(r2_sx_current) / 0.9 # Project assumption is 90% conversion rate for r2
        reactor1_2.saturation += r1_cos_current/pph*r1_sat_factor
        if reactor1_2.saturation >= 100:
            reactor1_2.saturation -= r1_cos_current/pph*r1_sat_factor
            reactor1_2.state = "cleaning"
            reactor1_1.state = "active"
            r1_changeovers_tally += 1

    # Switch state from 'cleaning' to 'idle' when reactor is clean
    if reactor1_2.state == "cleaning":
        reactor1_2.saturation = max(0, reactor1_2.saturation - r1_clean_speed/pph)
        if reactor1_2.saturation == 0: reactor1_2.state = "idle"
        
    if reactor1_1.state == "cleaning":
        reactor1_1.saturation = max(0, reactor1_1.saturation - r1_clean_speed/pph)
        if reactor1_1.saturation == 0: reactor1_1.state = "idle"
    
    return r1_changeovers_tally


# Update Sx filter saturation and tally filter changes
def update_sx_filter(sx_sat_current, sx_filter_tally, sx_filter, r2_sx_current):
    sx_sat_factor = sx_filter.sat_factor
    sx_sat_current = sx_sat_current + r2_sx_current/pph*sx_sat_factor
    if sx_sat_current >= 100:
        sx_sat_current = 0
        sx_filter_tally += 1
    
    return sx_sat_current, sx_filter_tally