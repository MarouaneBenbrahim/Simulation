#!/usr/bin/env python3
"""
Simplified PyPSA Network for NYC - Compatible with SUMO
This version focuses on network structure without complex optimization
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

class NYCPowerNetworkSimple:
    def __init__(self):
        """Initialize NYC Power Network"""
        self.name = "NYC Power Grid"
        
        # Network components
        self.buses = {}
        self.generators = {}
        self.loads = {}
        self.lines = {}
        self.transformers = {}
        
        # Time series (24 hours)
        self.time_steps = pd.date_range('2025-01-01', periods=24, freq='h')
        self.current_hour = 0
        
        # Traffic-related loads
        self.traffic_light_loads = {}
        self.ev_charging_loads = {}
        self.street_light_loads = {}
        
        # Network state
        self.total_generation = 0
        self.total_load = 0
        self.line_flows = {}
        
    def build_network(self):
        """Build the NYC power network"""
        print("Building Simplified NYC Power Network...")
        
        self._add_buses()
        self._add_generators()
        self._add_lines()
        self._add_base_loads()
        self._add_traffic_infrastructure()
        
        print("Network built successfully!")
        return self
    
    def _add_buses(self):
        """Add electrical buses (substations)"""
        self.buses = {
            # High voltage buses (138kV)
            'Manhattan_Central': {'lat': 40.7580, 'lon': -73.9855, 'voltage': 138, 'type': 'transmission'},
            'Manhattan_South': {'lat': 40.7074, 'lon': -74.0113, 'voltage': 138, 'type': 'transmission'},
            'Brooklyn_Central': {'lat': 40.6782, 'lon': -73.9442, 'voltage': 138, 'type': 'transmission'},
            'Queens_West': {'lat': 40.7282, 'lon': -73.8458, 'voltage': 138, 'type': 'transmission'},
            'Bronx_Central': {'lat': 40.8448, 'lon': -73.8648, 'voltage': 138, 'type': 'transmission'},
            
            # Distribution buses (13.8kV) for traffic infrastructure
            'Traffic_Manhattan': {'lat': 40.7489, 'lon': -73.9680, 'voltage': 13.8, 'type': 'distribution'},
            'Traffic_Brooklyn': {'lat': 40.6892, 'lon': -73.9502, 'voltage': 13.8, 'type': 'distribution'},
            'Traffic_Queens': {'lat': 40.7367, 'lon': -73.8203, 'voltage': 13.8, 'type': 'distribution'},
        }
        print(f"Added {len(self.buses)} electrical buses")
    
    def _add_generators(self):
        """Add power generators"""
        self.generators = {
            'Ravenswood_PowerPlant': {
                'bus': 'Queens_West',
                'capacity_mw': 2480,
                'type': 'gas',
                'cost_per_mwh': 50,
                'current_output': 0,
                'lat': 40.7666, 'lon': -73.9407
            },
            'Astoria_PowerPlant': {
                'bus': 'Queens_West',
                'capacity_mw': 1310,
                'type': 'gas',
                'cost_per_mwh': 55,
                'current_output': 0,
                'lat': 40.7720, 'lon': -73.9303
            },
            'Hudson_Avenue_Plant': {
                'bus': 'Brooklyn_Central',
                'capacity_mw': 420,
                'type': 'gas',
                'cost_per_mwh': 60,
                'current_output': 0,
                'lat': 40.7002, 'lon': -73.9659
            },
            'Solar_Brooklyn': {
                'bus': 'Brooklyn_Central',
                'capacity_mw': 50,
                'type': 'solar',
                'cost_per_mwh': 0,
                'current_output': 0,
                'lat': 40.6501, 'lon': -73.9496
            }
        }
        print(f"Added {len(self.generators)} generators")
    
    def _add_lines(self):
        """Add transmission lines"""
        self.lines = {
            'TL_Manhattan_Brooklyn': {
                'from': 'Manhattan_South', 'to': 'Brooklyn_Central',
                'capacity_mw': 500, 'resistance': 0.01, 'current_flow': 0
            },
            'TL_Manhattan_Queens': {
                'from': 'Manhattan_Central', 'to': 'Queens_West',
                'capacity_mw': 600, 'resistance': 0.01, 'current_flow': 0
            },
            'TL_Manhattan_Bronx': {
                'from': 'Manhattan_Central', 'to': 'Bronx_Central',
                'capacity_mw': 400, 'resistance': 0.008, 'current_flow': 0
            },
            'TL_Brooklyn_Queens': {
                'from': 'Brooklyn_Central', 'to': 'Queens_West',
                'capacity_mw': 450, 'resistance': 0.012, 'current_flow': 0
            },
            # Distribution lines to traffic infrastructure
            'DL_Manhattan_Traffic': {
                'from': 'Manhattan_Central', 'to': 'Traffic_Manhattan',
                'capacity_mw': 150, 'resistance': 0.02, 'current_flow': 0
            },
            'DL_Brooklyn_Traffic': {
                'from': 'Brooklyn_Central', 'to': 'Traffic_Brooklyn',
                'capacity_mw': 120, 'resistance': 0.025, 'current_flow': 0
            },
            'DL_Queens_Traffic': {
                'from': 'Queens_West', 'to': 'Traffic_Queens',
                'capacity_mw': 135, 'resistance': 0.022, 'current_flow': 0
            }
        }
        print(f"Added {len(self.lines)} transmission lines")
    
    def _add_base_loads(self):
        """Add base electrical loads"""
        self.loads = {
            'Load_Manhattan_Residential': {
                'bus': 'Manhattan_Central',
                'base_mw': 800,
                'current_mw': 800,
                'type': 'residential'
            },
            'Load_Manhattan_Commercial': {
                'bus': 'Manhattan_Central',
                'base_mw': 1200,
                'current_mw': 1200,
                'type': 'commercial'
            },
            'Load_Brooklyn_Mixed': {
                'bus': 'Brooklyn_Central',
                'base_mw': 600,
                'current_mw': 600,
                'type': 'mixed'
            },
            'Load_Queens_Mixed': {
                'bus': 'Queens_West',
                'base_mw': 500,
                'current_mw': 500,
                'type': 'mixed'
            },
            'Load_Bronx_Mixed': {
                'bus': 'Bronx_Central',
                'base_mw': 400,
                'current_mw': 400,
                'type': 'mixed'
            }
        }
        print(f"Added {len(self.loads)} base loads")
    
    def _add_traffic_infrastructure(self):
        """Add traffic-related electrical loads"""
        # Traffic lights (in MW)
        self.traffic_light_loads = {
            'TL_Manhattan': {'bus': 'Traffic_Manhattan', 'base_mw': 2.5, 'current_mw': 2.5},
            'TL_Brooklyn': {'bus': 'Traffic_Brooklyn', 'base_mw': 1.8, 'current_mw': 1.8},
            'TL_Queens': {'bus': 'Traffic_Queens', 'base_mw': 1.5, 'current_mw': 1.5}
        }
        
        # Street lights
        self.street_light_loads = {
            'SL_Manhattan': {'bus': 'Traffic_Manhattan', 'base_mw': 5.0, 'current_mw': 5.0},
            'SL_Brooklyn': {'bus': 'Traffic_Brooklyn', 'base_mw': 3.5, 'current_mw': 3.5},
            'SL_Queens': {'bus': 'Traffic_Queens', 'base_mw': 3.0, 'current_mw': 3.0}
        }
        
        # EV charging stations
        self.ev_charging_loads = {
            'EV_Manhattan': {'bus': 'Traffic_Manhattan', 'capacity_mw': 3.5, 'current_mw': 0},
            'EV_Brooklyn': {'bus': 'Traffic_Brooklyn', 'capacity_mw': 2.5, 'current_mw': 0},
            'EV_Queens': {'bus': 'Traffic_Queens', 'capacity_mw': 2.0, 'current_mw': 0}
        }
        
        print(f"Added {len(self.traffic_light_loads)} traffic light load zones")
        print(f"Added {len(self.street_light_loads)} street light load zones")
        print(f"Added {len(self.ev_charging_loads)} EV charging stations")
    
    def update_traffic_loads(self, vehicle_count, traffic_light_states):
        """Update loads based on SUMO traffic data"""
        # Update EV charging based on vehicle density
        # Assume 10% of vehicles are EVs, 5% are charging
        ev_ratio = 0.005
        charging_power_per_ev = 0.05  # 50kW average
        
        total_ev_charging = vehicle_count * ev_ratio * charging_power_per_ev
        
        # Distribute EV charging load
        self.ev_charging_loads['EV_Manhattan']['current_mw'] = min(
            total_ev_charging * 0.5, 
            self.ev_charging_loads['EV_Manhattan']['capacity_mw']
        )
        self.ev_charging_loads['EV_Brooklyn']['current_mw'] = min(
            total_ev_charging * 0.3,
            self.ev_charging_loads['EV_Brooklyn']['capacity_mw']
        )
        self.ev_charging_loads['EV_Queens']['current_mw'] = min(
            total_ev_charging * 0.2,
            self.ev_charging_loads['EV_Queens']['capacity_mw']
        )
        
        # Update traffic light loads based on states
        # More yellow/red states = slightly higher power (control systems active)
        green_ratio = sum(1 for state in traffic_light_states.values() if 'g' in state.lower()) / max(len(traffic_light_states), 1)
        power_factor = 1.0 + (1.0 - green_ratio) * 0.1  # Up to 10% more power when not green
        
        for tl_load in self.traffic_light_loads.values():
            tl_load['current_mw'] = tl_load['base_mw'] * power_factor
    
    def simulate_power_flow(self):
        """Simple power flow simulation"""
        # Calculate total load
        self.total_load = 0
        
        # Base loads
        for load in self.loads.values():
            # Apply time-of-day factor
            hour = self.current_hour
            if 0 <= hour < 6:
                factor = 0.6
            elif 6 <= hour < 9:
                factor = 0.8
            elif 9 <= hour < 17:
                factor = 0.9
            elif 17 <= hour < 21:
                factor = 1.0
            else:
                factor = 0.7
            
            load['current_mw'] = load['base_mw'] * factor
            self.total_load += load['current_mw']
        
        # Traffic infrastructure loads
        for tl_load in self.traffic_light_loads.values():
            self.total_load += tl_load['current_mw']
        
        for sl_load in self.street_light_loads.values():
            # Street lights on at night
            hour = self.current_hour
            if hour < 6 or hour > 18:
                sl_load['current_mw'] = sl_load['base_mw']
            else:
                sl_load['current_mw'] = 0
            self.total_load += sl_load['current_mw']
        
        for ev_load in self.ev_charging_loads.values():
            self.total_load += ev_load['current_mw']
        
        # Dispatch generators (simple merit order)
        self.total_generation = 0
        remaining_load = self.total_load
        
        # Solar first (if daytime)
        hour = self.current_hour
        if 6 <= hour <= 18:
            solar_output = self.generators['Solar_Brooklyn']['capacity_mw'] * np.sin((hour - 6) * np.pi / 12)
            self.generators['Solar_Brooklyn']['current_output'] = min(solar_output, remaining_load)
            self.total_generation += self.generators['Solar_Brooklyn']['current_output']
            remaining_load -= self.generators['Solar_Brooklyn']['current_output']
        
        # Then dispatch gas plants by cost
        for gen_name in ['Ravenswood_PowerPlant', 'Astoria_PowerPlant', 'Hudson_Avenue_Plant']:
            if remaining_load > 0:
                gen = self.generators[gen_name]
                gen['current_output'] = min(gen['capacity_mw'], remaining_load)
                self.total_generation += gen['current_output']
                remaining_load -= gen['current_output']
            else:
                self.generators[gen_name]['current_output'] = 0
        
        # Simple line flow calculation
        for line_name, line in self.lines.items():
            # Simplified: flow proportional to load difference
            line['current_flow'] = min(self.total_load * 0.1, line['capacity_mw'])
    
    def get_status(self):
        """Get current network status"""
        return {
            'timestamp': self.time_steps[self.current_hour].strftime('%Y-%m-%d %H:%M'),
            'total_generation_mw': round(self.total_generation, 2),
            'total_load_mw': round(self.total_load, 2),
            'balance_mw': round(self.total_generation - self.total_load, 2),
            'traffic_light_load_mw': round(sum(tl['current_mw'] for tl in self.traffic_light_loads.values()), 2),
            'street_light_load_mw': round(sum(sl['current_mw'] for sl in self.street_light_loads.values()), 2),
            'ev_charging_load_mw': round(sum(ev['current_mw'] for ev in self.ev_charging_loads.values()), 2),
            'generators': {name: round(gen['current_output'], 2) for name, gen in self.generators.items()},
            'line_utilization': {name: round((line['current_flow'] / line['capacity_mw']) * 100, 1) 
                               for name, line in self.lines.items()}
        }
    
    def advance_time(self):
        """Advance to next hour"""
        self.current_hour = (self.current_hour + 1) % 24
    
    def save_state(self, filepath="nyc_power_state.json"):
        """Save current state to JSON"""
        state = {
            'buses': self.buses,
            'generators': self.generators,
            'loads': self.loads,
            'lines': self.lines,
            'traffic_light_loads': self.traffic_light_loads,
            'street_light_loads': self.street_light_loads,
            'ev_charging_loads': self.ev_charging_loads,
            'current_hour': self.current_hour,
            'total_generation': self.total_generation,
            'total_load': self.total_load
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        print(f"State saved to {filepath}")

def test_network():
    """Test the simplified network"""
    print("=" * 60)
    print("Testing Simplified NYC Power Network")
    print("=" * 60)
    
    # Create and build network
    network = NYCPowerNetworkSimple()
    network.build_network()
    
    # Display network structure
    print("\n" + "=" * 60)
    print("Network Components Summary:")
    print(f"• Buses: {len(network.buses)}")
    print(f"• Generators: {len(network.generators)} (Total capacity: {sum(g['capacity_mw'] for g in network.generators.values())} MW)")
    print(f"• Base Loads: {len(network.loads)}")
    print(f"• Transmission Lines: {len(network.lines)}")
    print(f"• Traffic Light Zones: {len(network.traffic_light_loads)}")
    print(f"• EV Charging Stations: {len(network.ev_charging_loads)}")
    
    # Simulate different times of day
    print("\n" + "=" * 60)
    print("24-Hour Simulation:")
    print("-" * 60)
    
    for hour in range(24):
        network.current_hour = hour
        network.simulate_power_flow()
        status = network.get_status()
        
        if hour % 6 == 0:  # Print every 6 hours
            print(f"\nTime: {status['timestamp']}")
            print(f"Generation: {status['total_generation_mw']} MW")
            print(f"Total Load: {status['total_load_mw']} MW")
            print(f"Traffic Infrastructure: {status['traffic_light_load_mw'] + status['street_light_load_mw']} MW")
            print(f"EV Charging: {status['ev_charging_load_mw']} MW")
    
    # Test traffic integration
    print("\n" + "=" * 60)
    print("Testing Traffic Integration:")
    print("-" * 60)
    
    # Simulate rush hour traffic
    network.current_hour = 17  # 5 PM rush hour
    test_vehicles = 5000
    test_traffic_lights = {'tl_1': 'GGrr', 'tl_2': 'rrGG', 'tl_3': 'yyrr'}
    
    print(f"Simulating {test_vehicles} vehicles...")
    network.update_traffic_loads(test_vehicles, test_traffic_lights)
    network.simulate_power_flow()
    
    status = network.get_status()
    print(f"EV Charging Load: {status['ev_charging_load_mw']} MW")
    print(f"Traffic Light Load: {status['traffic_light_load_mw']} MW")
    
    # Save state
    network.save_state()
    
    print("\n✅ Simplified NYC Power Network ready for integration!")
    print("=" * 60)
    
    return network

if __name__ == "__main__":
    test_network()