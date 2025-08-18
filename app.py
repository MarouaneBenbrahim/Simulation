from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import traci
import time
import threading
import os
import sys
import tempfile
from config import *
from sumo_config import SUMO_COMMON_CONFIG, CITY_CONFIGS as SUMO_CITY_CONFIGS
# new Imports
from sumo_pypsa_integration import SUMOPyPSAIntegration

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'A34F6g7JK0c5N'
socketio = SocketIO(app, async_mode='threading')

# Get SUMO binary path from config
SUMO_BINARY = os.path.join(SUMO_PATH, "bin/sumo")  # or "sumo-gui" for the GUI version

# Global variables
simulation_running = False
simulation_thread = None
stop_event = threading.Event()
CURRENT_CITY = DEFAULT_CITY
# New Global Variable
pypsa_integration = None
# Traffic light state tracking
traffic_light_states = {}  # Store current state for each traffic light
traffic_light_phases = {}  # Store phase information for each traffic light

def create_temp_sumocfg(city):
    """Create a temporary SUMO configuration file for the city"""
    city_dir = CITY_CONFIGS[city]["working_dir"]
    city_sumo_config = SUMO_CITY_CONFIGS[city.upper()]
    
    # Create temporary file in the city directory
    temp_path = os.path.join(city_dir, "temp.sumocfg")
    with open(temp_path, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">\n')
        
        # Input files
        f.write('    <input>\n')
        f.write(f'        <net-file value="{os.path.basename(city_sumo_config["net-file"])}"/>\n')
        f.write(f'        <route-files value="{os.path.basename(city_sumo_config["route-files"])}"/>\n')
        f.write(f'        <additional-files value="{os.path.basename(city_sumo_config["additional-files"])}"/>\n')
        f.write('    </input>\n')
        
        # Processing
        f.write('    <processing>\n')
        for key, value in SUMO_COMMON_CONFIG["processing"].items():
            f.write(f'        <{key} value="{value}"/>\n')
        f.write('    </processing>\n')
        
        # Time
        f.write('    <time>\n')
        for key, value in SUMO_COMMON_CONFIG["time"].items():
            f.write(f'        <{key} value="{value}"/>\n')
        f.write('    </time>\n')
        
        f.write('</configuration>\n')
        return temp_path

def sumo_simulation(city=DEFAULT_CITY):
    global simulation_running
    
    if city not in CITY_CONFIGS:
        print(f"City {city} not found in configurations.")
        return
    
    city_config = CITY_CONFIGS[city]
    working_dir = city_config["working_dir"]
    
    print(f"Starting simulation for {city_config['name']}")
    print(f"Working directory: {working_dir}")
    
    # Store current directory to restore later
    original_dir = os.getcwd()
    temp_cfg = None
    
    try:
        # Change to the city's working directory
        os.chdir(working_dir)
        print(f"Changed to directory: {os.getcwd()}")
        
        # Create temporary SUMO configuration
        temp_cfg = create_temp_sumocfg(city)
        print(f"Created temporary config at: {temp_cfg}")
        
        simulation_running = True
        stop_event.clear()
        
        # Start SUMO with the temporary config
        sumo_cmd = [SUMO_BINARY, "-c", os.path.basename(temp_cfg)]
        print(f"Running command: {' '.join(sumo_cmd)}")
        
        try:
            traci.start(sumo_cmd)
            print("Successfully connected to SUMO")
            
            # Initialize PyPSA integration
            global pypsa_integration
            pypsa_integration = SUMOPyPSAIntegration(city)
            pypsa_integration.initialize_pypsa_network()
            print(f"Initialized PyPSA integration for {city}")
            
            # Switch to our randomized traffic light program (programID '1')
            for tl_id in traci.trafficlight.getIDList():
                try:
                    traci.trafficlight.setProgram(tl_id, "1")
                except:
                    pass  # Ignore errors if program doesn't exist
            
        except Exception as e:
            print(f"Failed to connect to SUMO: {str(e)}")
            raise
        
        # Counter for controlling update frequency
        step_counter = 0
        
        while traci.simulation.getMinExpectedNumber() > 0 and not stop_event.is_set():
            traci.simulationStep()
            step_counter += 1
            
            # Fix traffic light logic to ensure proper cycling
            fix_traffic_light_logic()
            
            # Update power demand based on traffic state
            if pypsa_integration:
                # Get current vehicle list
                current_vehicles = traci.vehicle.getIDList()
                
                # Get traffic lights data for power calculation
                current_traffic_lights = []
                for tl_id in traci.trafficlight.getIDList():
                    # Include ALL traffic lights for power calculation (even GS_ ones)
                    try:
                        state = traci.trafficlight.getRedYellowGreenState(tl_id)
                        current_traffic_lights.append({'id': tl_id, 'state': state})
                    except:
                        pass
                
                # Update power demand
                power_data = pypsa_integration.update_power_demand(
                    traffic_lights=current_traffic_lights,
                    vehicles=current_vehicles,
                    time_step=step_counter
                )
                
                # Run PyPSA optimization periodically
                if step_counter % PYPSA_UPDATE_FREQUENCY == 0:
                    print(f"Running PyPSA optimization at step {step_counter}")
                    grid_state = pypsa_integration.run_pypsa_optimization()
                    pypsa_integration.apply_grid_feedback_to_traffic(grid_state)
                    print(f"Grid congestion level: {grid_state.get('congestion_level', 0):.2%}")
            
            # Send updates based on configured frequency
            if step_counter % UPDATE_FREQUENCY == 0:
                # ========== FIXED TRAFFIC LIGHT POSITIONING ==========
                traffic_lights = []
                for tl_id in traci.trafficlight.getIDList():
                    # Skip guessed signals and cluster junctions
                    if tl_id.startswith('GS_') or tl_id.startswith('cluster_'):
                        continue
                    
                    try:
                        # Simple approach - just use junction position directly
                        junction_pos = traci.junction.getPosition(tl_id)
                        
                        # Check if position is valid (not the invalid marker)
                        if junction_pos and junction_pos[0] != -1073741824.0:
                            gps_position = traci.simulation.convertGeo(*junction_pos)
                            state = traci.trafficlight.getRedYellowGreenState(tl_id)
                            
                            traffic_lights.append({
                                'id': tl_id,
                                'x': gps_position[0],
                                'y': gps_position[1],
                                'state': state
                            })
                    except:
                        # Skip any problematic traffic lights silently
                        pass
                # ========== END FIXED SECTION ==========
                
                # Get vehicle information
                vehicles = []
                for vehicle_id in traci.vehicle.getIDList():
                    try:
                        position = traci.vehicle.getPosition(vehicle_id)
                        # Check for valid position
                        if position and position[0] != -1073741824.0:
                            gps_position = traci.simulation.convertGeo(*position)
                            angle = traci.vehicle.getAngle(vehicle_id)
                            vehicles.append({
                                'id': vehicle_id, 
                                'x': gps_position[0], 
                                'y': gps_position[1], 
                                'angle': angle
                            })
                    except:
                        # Skip vehicles with position errors
                        pass
                
                # Send both vehicles and traffic lights
                update_data = {
                    'vehicles': vehicles,
                    'traffic_lights': traffic_lights
                }
                
                # Add power data if available
                if pypsa_integration:
                    visualization_data = pypsa_integration.get_visualization_data()
                    update_data['power'] = visualization_data
                
                socketio.emit('update', update_data)
            
            # Use configured simulation speed
            time.sleep(SIMULATION_SPEED)
            
        traci.close()
        
    except Exception as e:
        print(f"Error in simulation: {e}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
    finally:
        # Clean up temporary file
        if temp_cfg and os.path.exists(temp_cfg):
            os.unlink(temp_cfg)
        # Restore original directory
        os.chdir(original_dir)
        simulation_running = False

@socketio.on('connect')
def handle_connect():
    """Handle client connection - don't start simulation automatically"""
    pass

@socketio.on('change_city')
def handle_change_city(data):
    global simulation_thread, CURRENT_CITY
    
    city = data.get('city', DEFAULT_CITY)
    if city not in CITY_CONFIGS:
        return
    
    CURRENT_CITY = city
    print(f"Changing city to {CITY_CONFIGS[CURRENT_CITY]['name']}")
    
    # Stop current simulation if running
    if simulation_running:
        stop_event.set()
        if simulation_thread:
            simulation_thread.join(timeout=2)
    
    # Start a new simulation with the selected city
    simulation_thread = threading.Thread(target=sumo_simulation, args=(CURRENT_CITY,))
    simulation_thread.start()

@socketio.on('restart')
def handle_restart(data):
    global simulation_thread, CURRENT_CITY
    
    city = data.get('city', CURRENT_CITY)
    if city not in CITY_CONFIGS:
        return
    
    CURRENT_CITY = city
    print(f"Restarting simulation for {CITY_CONFIGS[CURRENT_CITY]['name']}")
    
    # Stop current simulation if running
    if simulation_running:
        stop_event.set()
        if simulation_thread:
            simulation_thread.join(timeout=2)
    
    # Start a new simulation
    simulation_thread = threading.Thread(target=sumo_simulation, args=(CURRENT_CITY,))
    simulation_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

def fix_traffic_light_logic():
    """Fix traffic light logic to ensure proper green-yellow-red-green cycling"""
    global traffic_light_states, traffic_light_phases
    
    for tl_id in traci.trafficlight.getIDList():
        if tl_id not in traffic_light_states:
            traffic_light_states[tl_id] = {
                'current_state': None,
                'last_state': None,
                'state_duration': 0,
                'phase_index': 0
            }
            traffic_light_phases[tl_id] = []
        
        current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
        tl_state = traffic_light_states[tl_id]
        
        # If state changed, update tracking
        if current_state != tl_state['current_state']:
            tl_state['last_state'] = tl_state['current_state']
            tl_state['current_state'] = current_state
            tl_state['state_duration'] = 0
        else:
            tl_state['state_duration'] += 1
        
        # Check for improper transitions and fix them
        if (tl_state['last_state'] and 
            'y' in tl_state['last_state'].lower() and 
            'g' in current_state.lower() and 
            'r' not in tl_state['last_state'].lower()):
            
            # This is a yellow-to-green transition without red - fix it
            print(f"Fixing improper transition for {tl_id}: {tl_state['last_state']} -> {current_state}")
            
            # Force a red state for 2 seconds before allowing green
            if tl_state['state_duration'] < 20:  # 2 seconds at 0.1s step length
                # Create a red state for all lanes
                red_state = 'r' * len(current_state)
                try:
                    traci.trafficlight.setRedYellowGreenState(tl_id, red_state)
                except:
                    pass  # Ignore errors if we can't set the state

if __name__ == "__main__":
    print(f"NYC path: {NYC_PATH}")
    socketio.run(app, debug=True, host=HOST, port=PORT) 