#!/usr/bin/env python3
"""
SUMOxPyPSA Integrated Application
Professional Real-time Traffic-Power Grid Simulation
"""

from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import traci
import time
import threading
import os
import sys
import random
import math
from config import *
from sumo_config import SUMO_COMMON_CONFIG, CITY_CONFIGS as SUMO_CITY_CONFIGS

# Import power network components
from pypsa_network_builder import NYCPowerNetworkSimple
from traffic_power_integration import TrafficPowerCoupler

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'A34F6g7JK0c5N'
socketio = SocketIO(app, async_mode='threading')

# Get SUMO binary path from config
SUMO_BINARY = os.path.join(SUMO_PATH, "bin/sumo")

# Global variables
simulation_running = False
simulation_thread = None
stop_event = threading.Event()
CURRENT_CITY = DEFAULT_CITY

# Power network components
power_network = None
power_coupler = None

# Traffic light tracking
traffic_light_cycles = {}  # Track actual cycle times
traffic_light_locations = []

# EV Stations and tracking
EV_STATIONS_NYC = []
ev_station_vehicles = {}  # Track ACTUAL vehicles at each station
power_consumption_history = []

def initialize_power_network():
    """Initialize the power network for NYC"""
    global power_network, power_coupler
    
    print("Initializing NYC Power Network...")
    power_network = NYCPowerNetworkSimple()
    power_network.build_network()
    
    # Realistic line capacities
    power_network.lines['DL_Manhattan_Traffic']['capacity_mw'] = 250
    power_network.lines['DL_Brooklyn_Traffic']['capacity_mw'] = 180
    power_network.lines['DL_Queens_Traffic']['capacity_mw'] = 200
    
    print("Initializing Traffic-Power Coupler...")
    power_coupler = TrafficPowerCoupler(power_network)
    
    print("Power network initialized successfully!")
    return power_network, power_coupler

def create_temp_sumocfg(city):
    """Create a temporary SUMO configuration file for the city"""
    city_dir = CITY_CONFIGS[city]["working_dir"]
    city_sumo_config = SUMO_CITY_CONFIGS[city.upper()]
    
    temp_path = os.path.join(city_dir, "temp.sumocfg")
    with open(temp_path, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">\n')
        
        f.write('    <input>\n')
        f.write(f'        <net-file value="{os.path.basename(city_sumo_config["net-file"])}"/>\n')
        f.write(f'        <route-files value="{os.path.basename(city_sumo_config["route-files"])}"/>\n')
        f.write(f'        <additional-files value="{os.path.basename(city_sumo_config["additional-files"])}"/>\n')
        f.write('    </input>\n')
        
        f.write('    <processing>\n')
        f.write('        <ignore-route-errors value="true"/>\n')
        f.write('        <lateral-resolution value="0.8"/>\n')
        f.write('        <collision.action value="none"/>\n')
        f.write('        <time-to-teleport value="300"/>\n')
        f.write('        <max-depart-delay value="900"/>\n')
        f.write('        <routing-algorithm value="dijkstra"/>\n')
        f.write('        <device.rerouting.probability value="0.5"/>\n')
        f.write('        <scale value="0.7"/>\n')  # Moderate traffic
        f.write('    </processing>\n')
        
        f.write('    <time>\n')
        f.write('        <begin value="0"/>\n')
        f.write('        <end value="3600"/>\n')
        f.write('        <step-length value="0.1"/>\n')
        f.write('    </time>\n')
        
        f.write('</configuration>\n')
    
    return temp_path

def get_traffic_lights_with_proper_states():
    """Get traffic lights with PROPER state detection"""
    global traffic_light_locations, traffic_light_cycles
    traffic_lights = []
    traffic_light_locations = []
    
    try:
        for tl_id in traci.trafficlight.getIDList():
            try:
                # Initialize cycle tracking
                if tl_id not in traffic_light_cycles:
                    traffic_light_cycles[tl_id] = {
                        'phase': 0,
                        'duration': 0,
                        'max_duration': random.randint(30, 60)
                    }
                
                # Get position
                controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                position = None
                
                if controlled_lanes:
                    lane_id = controlled_lanes[0]
                    try:
                        lane_shape = traci.lane.getShape(lane_id)
                        if lane_shape:
                            position = lane_shape[-1]
                    except:
                        pass
                
                if position:
                    gps_position = traci.simulation.convertGeo(*position)
                    
                    # Get current state from SUMO
                    current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    
                    # Determine dominant color
                    green_count = current_state.count('G') + current_state.count('g')
                    red_count = current_state.count('R') + current_state.count('r')
                    yellow_count = current_state.count('Y') + current_state.count('y')
                    
                    # Set state based on majority
                    if green_count > red_count and green_count > yellow_count:
                        display_state = 'G' * len(current_state)
                    elif red_count > green_count and red_count > yellow_count:
                        display_state = 'r' * len(current_state)
                    elif yellow_count > 0:
                        display_state = 'y' * len(current_state)
                    else:
                        display_state = current_state
                    
                    traffic_lights.append({
                        'id': tl_id,
                        'x': gps_position[0],
                        'y': gps_position[1],
                        'state': display_state
                    })
                    
                    traffic_light_locations.append({
                        'id': tl_id,
                        'lat': gps_position[1],
                        'lon': gps_position[0]
                    })
                    
            except:
                continue
                
    except Exception as e:
        print(f"Error getting traffic lights: {e}")
    
    return traffic_lights

def set_realistic_traffic_light_cycles():
    """Set realistic traffic light cycles with proper green-yellow-red transitions"""
    try:
        current_time = int(traci.simulation.getTime())
        
        for tl_id in traci.trafficlight.getIDList()[:100]:  # Limit for performance
            try:
                if tl_id not in traffic_light_cycles:
                    traffic_light_cycles[tl_id] = {
                        'phase': random.randint(0, 2),
                        'duration': 0,
                        'max_duration': random.randint(20, 40)
                    }
                
                cycle = traffic_light_cycles[tl_id]
                cycle['duration'] += 1
                
                # Get current state
                current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                state_len = len(current_state)
                
                # Phase transitions
                if cycle['duration'] >= cycle['max_duration']:
                    cycle['phase'] = (cycle['phase'] + 1) % 3
                    cycle['duration'] = 0
                    
                    if cycle['phase'] == 1:  # Yellow phase
                        cycle['max_duration'] = 3  # Short yellow
                    else:
                        cycle['max_duration'] = random.randint(20, 40)
                
                # Set state based on phase
                if cycle['phase'] == 0:  # Green
                    pattern = ['G', 'r'] * (state_len // 2 + 1)
                    new_state = ''.join(pattern[:state_len])
                elif cycle['phase'] == 1:  # Yellow
                    pattern = ['y', 'r'] * (state_len // 2 + 1)
                    new_state = ''.join(pattern[:state_len])
                else:  # Red
                    pattern = ['r', 'G'] * (state_len // 2 + 1)
                    new_state = ''.join(pattern[:state_len])
                
                # Apply state
                if new_state != current_state:
                    traci.trafficlight.setRedYellowGreenState(tl_id, new_state)
                    
            except:
                continue
    except:
        pass

def create_ev_stations_at_intersections():
    """Create EV stations at major intersections ONLY"""
    global EV_STATIONS_NYC
    
    if not traffic_light_locations or len(traffic_light_locations) < 20:
        return
    
    EV_STATIONS_NYC = []
    station_names = [
        "Times Square Supercharger", "Grand Central Fast Charge", "Columbus Circle Station",
        "Financial District Hub", "SoHo Charging Plaza", "Barclays Center Station",
        "Brooklyn Heights Charger", "Prospect Park Station", "LaGuardia Area Station",
        "JFK Express Charger", "Flushing Meadows Station", "Yankee Stadium Charger",
        "Fordham Station", "Central Park West", "Union Square Hub"
    ]
    
    # Select 15 well-distributed locations
    step = len(traffic_light_locations) // 15
    
    for i in range(0, min(len(traffic_light_locations), 15 * step), step):
        if i < len(traffic_light_locations) and len(EV_STATIONS_NYC) < 15:
            tl = traffic_light_locations[i]
            station_name = station_names[len(EV_STATIONS_NYC)]
            
            EV_STATIONS_NYC.append({
                'id': f'ev_station_{len(EV_STATIONS_NYC)}',
                'lat': tl['lat'],
                'lon': tl['lon'],
                'name': station_name,
                'power': random.choice([150, 250, 350]),
                'capacity': random.randint(8, 12)  # 8-12 charging spots
            })
    
    print(f"Created {len(EV_STATIONS_NYC)} EV charging stations")

def calculate_actual_ev_charging():
    """Calculate ACTUAL vehicles charging at stations based on real positions"""
    global ev_station_vehicles
    
    ev_station_vehicles = {station['id']: [] for station in EV_STATIONS_NYC}
    
    # Get all vehicles
    all_vehicles = []
    for vid in traci.vehicle.getIDList():
        try:
            pos = traci.vehicle.getPosition(vid)
            gps = traci.simulation.convertGeo(*pos)
            speed = traci.vehicle.getSpeed(vid)
            
            # 30% of vehicles are EVs
            is_ev = hash(vid) % 100 < 30
            
            all_vehicles.append({
                'id': vid,
                'lat': gps[1],
                'lon': gps[0],
                'speed': speed,
                'is_ev': is_ev
            })
        except:
            continue
    
    # Check which EVs are at stations
    for vehicle in all_vehicles:
        if not vehicle['is_ev']:
            continue
            
        for station in EV_STATIONS_NYC:
            # Simple distance check (in degrees, roughly)
            lat_diff = abs(vehicle['lat'] - station['lat'])
            lon_diff = abs(vehicle['lon'] - station['lon'])
            
            # Very close to station and stopped/slow
            if lat_diff < 0.001 and lon_diff < 0.001 and vehicle['speed'] < 1.0:
                # Check capacity
                if len(ev_station_vehicles[station['id']]) < station['capacity']:
                    ev_station_vehicles[station['id']].append(vehicle['id'])
                    break  # Vehicle can only charge at one station
    
    return all_vehicles

def calculate_realistic_power_consumption(vehicles, traffic_lights, ev_charging_total):
    """Calculate realistic, dynamic power consumption"""
    global power_consumption_history
    
    current_time = traci.simulation.getTime() if simulation_running else 0
    
    # Base load with time-of-day variation
    hour_of_day = (int(current_time) // 3600) % 24
    if 6 <= hour_of_day < 9:  # Morning peak
        base_load = 2400
    elif 17 <= hour_of_day < 20:  # Evening peak
        base_load = 2500
    elif 0 <= hour_of_day < 6:  # Night
        base_load = 1900
    else:  # Normal hours
        base_load = 2200
    
    # Add variation
    time_variation = math.sin(current_time / 200) * 50
    random_variation = random.uniform(-20, 20)
    
    # Traffic infrastructure load
    traffic_base = 8.0  # Base traffic systems
    traffic_lights_load = len(traffic_lights) * 0.003  # 3kW per intersection
    street_lights = 12.0 if hour_of_day < 6 or hour_of_day > 18 else 0
    
    # Vehicle-related load
    vehicle_load = len(vehicles) * 0.2  # Traffic management systems
    
    # Total calculation
    total_load = (base_load + time_variation + random_variation + 
                 traffic_base + traffic_lights_load + street_lights + 
                 vehicle_load + ev_charging_total)
    
    # Store history
    power_consumption_history.append(total_load)
    if len(power_consumption_history) > 100:
        power_consumption_history.pop(0)
    
    # Calculate trend
    if len(power_consumption_history) > 10:
        recent_avg = sum(power_consumption_history[-10:]) / 10
        older_avg = sum(power_consumption_history[-20:-10]) / 10
        trend = "increasing" if recent_avg > older_avg else "decreasing"
    else:
        trend = "stable"
    
    return {
        'total_load_mw': total_load,
        'traffic_infrastructure_mw': traffic_base + traffic_lights_load + street_lights,
        'ev_charging_mw': ev_charging_total,
        'base_load_mw': base_load,
        'trend': trend
    }

def sumo_simulation(city=DEFAULT_CITY):
    global simulation_running, power_coupler, power_network, EV_STATIONS_NYC, ev_station_vehicles
    
    if city not in CITY_CONFIGS:
        print(f"City {city} not found")
        return
    
    city_config = CITY_CONFIGS[city]
    working_dir = city_config["working_dir"]
    
    print(f"Starting PROFESSIONAL simulation for {city_config['name']}")
    
    original_dir = os.getcwd()
    temp_cfg = None
    
    try:
        os.chdir(working_dir)
        temp_cfg = create_temp_sumocfg(city)
        
        simulation_running = True
        stop_event.clear()
        
        sumo_cmd = [SUMO_BINARY, "-c", os.path.basename(temp_cfg)]
        
        traci.start(sumo_cmd)
        print("Connected to SUMO successfully")
        
        step_counter = 0
        stations_created = False
        
        while traci.simulation.getMinExpectedNumber() > 0 and not stop_event.is_set():
            traci.simulationStep()
            step_counter += 1
            simulation_time = traci.simulation.getTime()
            
            # Update traffic lights every 5 steps
            if step_counter % 5 == 0:
                set_realistic_traffic_light_cycles()
            
            # Main update cycle
            if step_counter % UPDATE_FREQUENCY == 0:
                
                # Get traffic lights with proper states
                traffic_lights = get_traffic_lights_with_proper_states()
                
                # Create EV stations once
                if not stations_created and len(traffic_lights) > 20:
                    create_ev_stations_at_intersections()
                    stations_created = True
                
                # Get all vehicles and calculate actual EV charging
                all_vehicles_data = calculate_actual_ev_charging()
                
                # Prepare vehicle data for frontend
                vehicles = []
                ev_count = 0
                
                for v_data in all_vehicles_data:
                    try:
                        vid = v_data['id']
                        angle = traci.vehicle.getAngle(vid)
                        vehicle_type = traci.vehicle.getTypeID(vid)
                        
                        vehicles.append({
                            'id': vid,
                            'x': v_data['lon'],
                            'y': v_data['lat'],
                            'angle': angle,
                            'speed': v_data['speed'],
                            'type': vehicle_type,
                            'is_ev': v_data['is_ev']
                        })
                        
                        if v_data['is_ev']:
                            ev_count += 1
                    except:
                        continue
                
                # Calculate EV station data with ACTUAL vehicles
                ev_stations = []
                total_ev_charging_mw = 0
                
                for station in EV_STATIONS_NYC:
                    charging_vehicles = ev_station_vehicles.get(station['id'], [])
                    num_charging = len(charging_vehicles)
                    
                    # Only count vehicles that actually exist
                    num_charging = min(num_charging, station['capacity'])
                    
                    utilization = (num_charging / station['capacity']) * 100
                    station_power_mw = (num_charging * 50) / 1000  # 50kW per vehicle
                    total_ev_charging_mw += station_power_mw
                    
                    ev_stations.append({
                        'id': station['id'],
                        'lat': station['lat'],
                        'lon': station['lon'],
                        'name': station['name'],
                        'power': station['power'],
                        'evs_charging': num_charging,
                        'max_capacity': station['capacity'],
                        'utilization': utilization,
                        'charging_vehicles': charging_vehicles[:5]  # Show first 5 IDs
                    })
                
                # Calculate realistic power consumption
                power_data = calculate_realistic_power_consumption(
                    vehicles, traffic_lights, total_ev_charging_mw
                )
                
                # Line utilization based on actual load
                total_traffic_load = power_data['traffic_infrastructure_mw']
                line_utilization = {
                    'DL_Manhattan_Traffic': min(95, (total_traffic_load / 250) * 100 * 1.2),
                    'DL_Brooklyn_Traffic': min(90, (total_traffic_load / 180) * 100 * 1.1),
                    'DL_Queens_Traffic': min(85, (total_traffic_load / 200) * 100 * 1.0)
                }
                
                power_data['line_utilization'] = line_utilization
                
                # Debug output
                if step_counter % 100 == 0:
                    total_charging = sum(len(v) for v in ev_station_vehicles.values())
                    print(f"\n--- Step {step_counter} ---")
                    print(f"Vehicles: {len(vehicles)} total, {ev_count} EVs")
                    print(f"EV Charging: {total_charging} vehicles at stations")
                    print(f"Power: {power_data['total_load_mw']:.1f} MW total")
                    print(f"Traffic lights: {len(traffic_lights)} detected")
                    
                    # Show station details
                    for station in ev_stations[:3]:  # Show first 3
                        if station['evs_charging'] > 0:
                            print(f"  {station['name']}: {station['evs_charging']}/{station['max_capacity']} vehicles")
                
                # Send data to frontend
                emit_data = {
                    'vehicles': vehicles,
                    'traffic_lights': traffic_lights,
                    'ev_stations': ev_stations,
                    'simulation_time': simulation_time,
                    'vehicle_count': len(vehicles),
                    'ev_count': ev_count,
                    'power': power_data,
                    'power_events': []
                }
                
                socketio.emit('update', emit_data)
            
            time.sleep(SIMULATION_SPEED)
            
        traci.close()
        
    except Exception as e:
        print(f"Simulation error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if temp_cfg and os.path.exists(temp_cfg):
            os.unlink(temp_cfg)
        os.chdir(original_dir)
        simulation_running = False

@socketio.on('connect')
def handle_connect():
    print("Client connected")
    if power_network:
        socketio.emit('power_network_structure', {
            'buses': list(power_network.buses.keys()),
            'generators': list(power_network.generators.keys()),
            'lines': list(power_network.lines.keys()),
            'ev_stations': EV_STATIONS_NYC
        })

@socketio.on('change_city')
def handle_change_city(data):
    global simulation_thread, CURRENT_CITY, EV_STATIONS_NYC
    
    city = data.get('city', DEFAULT_CITY)
    CURRENT_CITY = city
    
    # Reset
    EV_STATIONS_NYC = []
    
    if city == 'newyork' and not power_network:
        initialize_power_network()
    
    if simulation_running:
        stop_event.set()
        if simulation_thread:
            simulation_thread.join(timeout=2)
    
    simulation_thread = threading.Thread(target=sumo_simulation, args=(CURRENT_CITY,))
    simulation_thread.start()

@socketio.on('restart')
def handle_restart(data):
    global simulation_thread, EV_STATIONS_NYC
    
    EV_STATIONS_NYC = []
    
    if simulation_running:
        stop_event.set()
        if simulation_thread:
            simulation_thread.join(timeout=2)
    
    simulation_thread = threading.Thread(target=sumo_simulation, args=(CURRENT_CITY,))
    simulation_thread.start()

@socketio.on('power_event')
def handle_power_event(data):
    event_type = data.get('type')
    if event_type == 'ev_station_click':
        station_id = data.get('station_id')
        # Send actual vehicle IDs charging at this station
        vehicles_at_station = ev_station_vehicles.get(station_id, [])
        socketio.emit('station_vehicles', {
            'station_id': station_id,
            'vehicles': vehicles_at_station
        })

@app.route('/')
def index():
    return render_template('index_integrated.html')

if __name__ == "__main__":
    if DEFAULT_CITY == 'newyork':
        initialize_power_network()
    
    print("=" * 60)
    print("SUMOxPyPSA PROFESSIONAL SIMULATION SYSTEM")
    print("=" * 60)
    print("Features:")
    print("✓ Realistic traffic light cycles (Green → Yellow → Red)")
    print("✓ ACTUAL vehicle tracking at EV stations")
    print("✓ Dynamic power consumption with time-of-day variation")
    print("✓ Real vehicle-to-station proximity detection")
    print("✓ Professional-grade simulation accuracy")
    print("=" * 60)
    
    socketio.run(app, debug=True, host=HOST, port=PORT)