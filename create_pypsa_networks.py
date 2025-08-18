#!/usr/bin/env python3
"""
Create PyPSA network files for each city based on their actual traffic simulation areas
"""

import os
import pandas as pd
import numpy as np

def create_newyork_network():
    """Create PyPSA network for New York (focusing on lower Manhattan/Jersey City area)"""
    
    # Based on your actual traffic area (around 40.735, -74.030)
    buses = pd.DataFrame([
        # WEST SIDE / JERSEY CITY AREA - WHERE YOUR TRAFFIC ACTUALLY IS
        {'id': 'Jersey_City', 'x': -74.030, 'y': 40.735, 'v_nom': 138, 'zone': 'West'},
        {'id': 'Newport', 'x': -74.028, 'y': 40.740, 'v_nom': 138, 'zone': 'West'},
        {'id': 'Exchange_Place', 'x': -74.032, 'y': 40.738, 'v_nom': 138, 'zone': 'West'},
        {'id': 'Liberty_State', 'x': -74.025, 'y': 40.745, 'v_nom': 138, 'zone': 'West'},
        
        # Substations for the area
        {'id': 'Substation_1', 'x': -74.027, 'y': 40.737, 'v_nom': 69, 'zone': 'West'},
        {'id': 'Substation_2', 'x': -74.029, 'y': 40.742, 'v_nom': 69, 'zone': 'West'},
        
        # Main generation station
        {'id': 'Hudson_Gen', 'x': -74.035, 'y': 40.750, 'v_nom': 345, 'zone': 'Generation'},
    ])
    
    # Transmission lines connecting the buses
    lines = pd.DataFrame([
        # Main transmission lines
        {'id': 'Line_1', 'bus0': 'Hudson_Gen', 'bus1': 'Liberty_State', 'x': 0.01, 'r': 0.005, 's_nom': 200},
        {'id': 'Line_2', 'bus0': 'Liberty_State', 'bus1': 'Newport', 'x': 0.008, 'r': 0.004, 's_nom': 150},
        {'id': 'Line_3', 'bus0': 'Newport', 'bus1': 'Jersey_City', 'x': 0.008, 'r': 0.004, 's_nom': 150},
        {'id': 'Line_4', 'bus0': 'Jersey_City', 'bus1': 'Exchange_Place', 'x': 0.008, 'r': 0.004, 's_nom': 150},
        {'id': 'Line_5', 'bus0': 'Exchange_Place', 'bus1': 'Liberty_State', 'x': 0.01, 'r': 0.005, 's_nom': 100},
        
        # Distribution lines to substations
        {'id': 'Dist_1', 'bus0': 'Jersey_City', 'bus1': 'Substation_1', 'x': 0.015, 'r': 0.008, 's_nom': 50},
        {'id': 'Dist_2', 'bus0': 'Newport', 'bus1': 'Substation_2', 'x': 0.015, 'r': 0.008, 's_nom': 50},
        {'id': 'Dist_3', 'bus0': 'Substation_1', 'bus1': 'Substation_2', 'x': 0.02, 'r': 0.01, 's_nom': 30},
    ])
    
    # Generators at each major bus
    generators = pd.DataFrame([
        {'id': 'Gen_Hudson', 'bus': 'Hudson_Gen', 'p_nom': 500, 'marginal_cost': 30, 'carrier': 'gas'},
        {'id': 'Gen_Liberty', 'bus': 'Liberty_State', 'p_nom': 100, 'marginal_cost': 40, 'carrier': 'gas'},
        {'id': 'Solar_Newport', 'bus': 'Newport', 'p_nom': 20, 'marginal_cost': 0, 'carrier': 'solar'},
        {'id': 'Solar_Jersey', 'bus': 'Jersey_City', 'p_nom': 15, 'marginal_cost': 0, 'carrier': 'solar'},
        {'id': 'Battery_Exchange', 'bus': 'Exchange_Place', 'p_nom': 30, 'marginal_cost': 10, 'carrier': 'battery'},
    ])
    
    # Base loads at each bus
    loads = pd.DataFrame([
        {'id': 'Load_Jersey_City', 'bus': 'Jersey_City', 'p_set': 40},
        {'id': 'Load_Newport', 'bus': 'Newport', 'p_set': 35},
        {'id': 'Load_Exchange', 'bus': 'Exchange_Place', 'p_set': 30},
        {'id': 'Load_Liberty', 'bus': 'Liberty_State', 'p_set': 25},
        {'id': 'Load_Sub1', 'bus': 'Substation_1', 'p_set': 15},
        {'id': 'Load_Sub2', 'bus': 'Substation_2', 'p_set': 15},
    ])
    
    return buses, lines, generators, loads

def create_miami_network():
    """Create PyPSA network for Miami"""
    
    buses = pd.DataFrame([
        {'id': 'Wynwood', 'x': -80.200, 'y': 25.805, 'v_nom': 138, 'zone': 'North'},
        {'id': 'Design_District', 'x': -80.190, 'y': 25.810, 'v_nom': 138, 'zone': 'North'},
        {'id': 'Midtown', 'x': -80.195, 'y': 25.808, 'v_nom': 138, 'zone': 'Central'},
        {'id': 'Edgewater', 'x': -80.188, 'y': 25.800, 'v_nom': 138, 'zone': 'Central'},
        {'id': 'Downtown', 'x': -80.193, 'y': 25.774, 'v_nom': 138, 'zone': 'South'},
        {'id': 'Brickell', 'x': -80.195, 'y': 25.761, 'v_nom': 138, 'zone': 'South'},
        {'id': 'Port_Miami', 'x': -80.170, 'y': 25.775, 'v_nom': 345, 'zone': 'Generation'},
    ])
    
    lines = pd.DataFrame([
        {'id': 'Line_1', 'bus0': 'Port_Miami', 'bus1': 'Downtown', 'x': 0.01, 'r': 0.005, 's_nom': 200},
        {'id': 'Line_2', 'bus0': 'Downtown', 'bus1': 'Brickell', 'x': 0.008, 'r': 0.004, 's_nom': 150},
        {'id': 'Line_3', 'bus0': 'Downtown', 'bus1': 'Edgewater', 'x': 0.008, 'r': 0.004, 's_nom': 150},
        {'id': 'Line_4', 'bus0': 'Edgewater', 'bus1': 'Midtown', 'x': 0.008, 'r': 0.004, 's_nom': 100},
        {'id': 'Line_5', 'bus0': 'Midtown', 'bus1': 'Wynwood', 'x': 0.008, 'r': 0.004, 's_nom': 100},
        {'id': 'Line_6', 'bus0': 'Midtown', 'bus1': 'Design_District', 'x': 0.008, 'r': 0.004, 's_nom': 100},
        {'id': 'Line_7', 'bus0': 'Wynwood', 'bus1': 'Design_District', 'x': 0.01, 'r': 0.005, 's_nom': 80},
    ])
    
    generators = pd.DataFrame([
        {'id': 'Gen_Port', 'bus': 'Port_Miami', 'p_nom': 400, 'marginal_cost': 35, 'carrier': 'gas'},
        {'id': 'Gen_Downtown', 'bus': 'Downtown', 'p_nom': 100, 'marginal_cost': 45, 'carrier': 'gas'},
        {'id': 'Solar_Wynwood', 'bus': 'Wynwood', 'p_nom': 25, 'marginal_cost': 0, 'carrier': 'solar'},
        {'id': 'Solar_Brickell', 'bus': 'Brickell', 'p_nom': 20, 'marginal_cost': 0, 'carrier': 'solar'},
        {'id': 'Battery_Midtown', 'bus': 'Midtown', 'p_nom': 25, 'marginal_cost': 15, 'carrier': 'battery'},
    ])
    
    loads = pd.DataFrame([
        {'id': 'Load_Wynwood', 'bus': 'Wynwood', 'p_set': 30},
        {'id': 'Load_Design', 'bus': 'Design_District', 'p_set': 25},
        {'id': 'Load_Midtown', 'bus': 'Midtown', 'p_set': 35},
        {'id': 'Load_Edgewater', 'bus': 'Edgewater', 'p_set': 20},
        {'id': 'Load_Downtown', 'bus': 'Downtown', 'p_set': 45},
        {'id': 'Load_Brickell', 'bus': 'Brickell', 'p_set': 30},
    ])
    
    return buses, lines, generators, loads

def create_losangeles_network():
    """Create PyPSA network for Los Angeles (focusing on Vernon/Downtown industrial area)"""
    
    # Based on your actual traffic area (around 34.020, -118.220)
    buses = pd.DataFrame([
        # VERNON/DOWNTOWN INDUSTRIAL - WHERE YOUR TRAFFIC ACTUALLY IS
        {'id': 'Vernon_West', 'x': -118.225, 'y': 34.018, 'v_nom': 138, 'zone': 'Industrial'},
        {'id': 'Vernon_Central', 'x': -118.220, 'y': 34.020, 'v_nom': 138, 'zone': 'Industrial'},
        {'id': 'Vernon_East', 'x': -118.215, 'y': 34.025, 'v_nom': 138, 'zone': 'Industrial'},
        {'id': 'Commerce', 'x': -118.218, 'y': 34.023, 'v_nom': 138, 'zone': 'Industrial'},
        {'id': 'Huntington_Park', 'x': -118.222, 'y': 34.022, 'v_nom': 138, 'zone': 'Industrial'},
        {'id': 'Maywood', 'x': -118.217, 'y': 34.019, 'v_nom': 69, 'zone': 'Industrial'},
        
        # Main generation
        {'id': 'Vernon_Power', 'x': -118.230, 'y': 34.015, 'v_nom': 345, 'zone': 'Generation'},
    ])
    
    lines = pd.DataFrame([
        # Main transmission
        {'id': 'Line_1', 'bus0': 'Vernon_Power', 'bus1': 'Vernon_West', 'x': 0.01, 'r': 0.005, 's_nom': 250},
        {'id': 'Line_2', 'bus0': 'Vernon_West', 'bus1': 'Vernon_Central', 'x': 0.008, 'r': 0.004, 's_nom': 150},
        {'id': 'Line_3', 'bus0': 'Vernon_Central', 'bus1': 'Vernon_East', 'x': 0.008, 'r': 0.004, 's_nom': 150},
        {'id': 'Line_4', 'bus0': 'Vernon_Central', 'bus1': 'Commerce', 'x': 0.008, 'r': 0.004, 's_nom': 120},
        {'id': 'Line_5', 'bus0': 'Vernon_Central', 'bus1': 'Huntington_Park', 'x': 0.008, 'r': 0.004, 's_nom': 120},
        {'id': 'Line_6', 'bus0': 'Commerce', 'bus1': 'Maywood', 'x': 0.015, 'r': 0.008, 's_nom': 80},
        {'id': 'Line_7', 'bus0': 'Vernon_East', 'bus1': 'Commerce', 'x': 0.01, 'r': 0.005, 's_nom': 100},
    ])
    
    generators = pd.DataFrame([
        {'id': 'Gen_Vernon', 'bus': 'Vernon_Power', 'p_nom': 600, 'marginal_cost': 32, 'carrier': 'gas'},
        {'id': 'Gen_Commerce', 'bus': 'Commerce', 'p_nom': 150, 'marginal_cost': 42, 'carrier': 'gas'},
        {'id': 'Solar_Vernon', 'bus': 'Vernon_Central', 'p_nom': 30, 'marginal_cost': 0, 'carrier': 'solar'},
        {'id': 'Solar_Industrial', 'bus': 'Vernon_East', 'p_nom': 25, 'marginal_cost': 0, 'carrier': 'solar'},
        {'id': 'Battery_Huntington', 'bus': 'Huntington_Park', 'p_nom': 40, 'marginal_cost': 12, 'carrier': 'battery'},
    ])
    
    loads = pd.DataFrame([
        {'id': 'Load_Vernon_West', 'bus': 'Vernon_West', 'p_set': 50},
        {'id': 'Load_Vernon_Central', 'bus': 'Vernon_Central', 'p_set': 60},
        {'id': 'Load_Vernon_East', 'bus': 'Vernon_East', 'p_set': 45},
        {'id': 'Load_Commerce', 'bus': 'Commerce', 'p_set': 40},
        {'id': 'Load_Huntington', 'bus': 'Huntington_Park', 'p_set': 35},
        {'id': 'Load_Maywood', 'bus': 'Maywood', 'p_set': 20},
    ])
    
    return buses, lines, generators, loads

def save_network_files(city, buses, lines, generators, loads):
    """Save network data to CSV files"""
    
    # Create directory if it doesn't exist
    output_dir = f'pypsa_network/{city}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to CSV files
    buses.to_csv(os.path.join(output_dir, 'buses.csv'), index=False)
    lines.to_csv(os.path.join(output_dir, 'lines.csv'), index=False)
    generators.to_csv(os.path.join(output_dir, 'generators.csv'), index=False)
    loads.to_csv(os.path.join(output_dir, 'loads.csv'), index=False)
    
    print(f"✅ Created PyPSA network files for {city}")
    print(f"   - {len(buses)} buses")
    print(f"   - {len(lines)} transmission lines")
    print(f"   - {len(generators)} generators")
    print(f"   - {len(loads)} loads")

def main():
    """Create PyPSA networks for all cities"""
    
    print("=" * 60)
    print("Creating PyPSA Power Grid Networks")
    print("=" * 60)
    
    # New York
    print("\n📍 Creating New York network (Jersey City area)...")
    buses, lines, generators, loads = create_newyork_network()
    save_network_files('newyork', buses, lines, generators, loads)
    
    # Miami
    print("\n📍 Creating Miami network...")
    buses, lines, generators, loads = create_miami_network()
    save_network_files('miami', buses, lines, generators, loads)
    
    # Los Angeles
    print("\n📍 Creating Los Angeles network (Vernon industrial area)...")
    buses, lines, generators, loads = create_losangeles_network()
    save_network_files('losangeles', buses, lines, generators, loads)
    
    print("\n" + "=" * 60)
    print("✅ All PyPSA networks created successfully!")
    print("Networks are properly located in your actual traffic areas")
    print("=" * 60)

if __name__ == "__main__":
    main()