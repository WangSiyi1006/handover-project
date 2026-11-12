"""Synthetic radio observations for the policy tests."""

import math


def observation(serving_power=0.1, target_power=1.0, time_ms=0):
    powers={'serving':serving_power,'target':target_power,'other':0.01}
    total=sum(powers.values())+0.001
    return {'time_ms':time_ms,'measurement_time_ms':time_ms,'serving_cell_id':'serving',
            'serving_rsrp_dbm':10*math.log10(serving_power)-80,
            'candidates':[{'cell_id':cid,'rsrp_dbm':10*math.log10(power)-80,
                           'rs_sinr_db':10*math.log10(power/(total-power)),'eligible':True}
                          for cid,power in powers.items() if cid!='serving'],
            'ho_phase':'idle','recent_events':[]}
