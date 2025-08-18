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
from enhanced_pypsa_integration import EnhancedSUMOPyPSAIntegration
import logging
import json

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'A34F6g7JK0c5N'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get SUMO binary path from config
SUMO_BINARY = os.path.join(SUMO_PATH, "bin/sumo")

# Global variables
simulation_running = False
simulation_thread = None
stop_event = threading.Event()
CURRENT_CITY = "losangeles"  # Focus on LA
pypsa_integration = None
simulation_stats = {
    'step': 0,
    'vehicles': 0,
    'ev_count': 0,
    'traffic_lights': 0,
    'grid_state': 'normal',
    'total_demand': 0
}

def create_temp_sumocfg(city):
    """Create a temporary SUMO configuration file for the city"""
    city_dir = CITY_CONFIGS[city]["working_dir"]
    city_sumo_config = SUMO_CITY_CONFIGS.get(city.upper(), SUMO_CITY_CONFIGS["LOSANGELES"])
    
    temp_path = os.path.join(city_dir, "temp.sumocfg")
    with open(temp_path, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ')
        f.write('xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">\n')
        
        # Input files
        f.write('    <input>\n')
        f.write(f'        <net-file value="{os.path.basename(city_sumo_config["net-file"])}"/>\n')
        f.write(f'        <route-files value="{os.path.basename(city_sumo_config["route-files"])}"/>\n')
        if "additional-files" in city_sumo_config:
            f.write(f'        <additional-files value="{os.path.basename(city_sumo_config["additional-files"])}"/>\n')
        f.write('    </input>\n')
        
        # Processing
        f.write('    <processing>\n')
        for key, value in SUMO_COMMON_CONFIG.get("processing", {}).items():
            f.write(f'        <{key} value="{value}"/>\n')
        f.write('    </processing>\n')
        
        # Time
        f.write('    <time>\n')
        f.write('        <begin value="0"/>\n')
        f.write('        <end value="3600"/>\n')
        f.write('        <step-length value="0.1"/>\n')
        f.write('    </time>\n')
        
        f.write('</configuration>\n')
    
    return temp_path

def sumo_simulation(city="losangeles"):
    """Enhanced SUMO simulation with advanced PyPSA integration"""
    global simulation_running, pypsa_integration, simulation_stats
    
    if city not in CITY_CONFIGS:
        logger.error(f"City {city} not found in configurations.")
        return
    
    city_config = CITY_CONFIGS[city]
    working_dir = city_config["working_dir"]
    
    logger.info(f"Starting simulation for {city_config['name']}")
    logger.info(f"Working directory: {working_dir}")
    
    original_dir = os.getcwd()
    temp_cfg = None
    
    try:
        # Change to city directory
        os.chdir(working_dir)
        logger.info(f"Changed to directory: {os.getcwd()}")
        
        # Create temporary SUMO configuration
        temp_cfg = create_temp_sumocfg(city)
        logger.info(f"Created temporary config at: {temp_cfg}")
        
        simulation_running = True
        stop_event.clear()
        
        # Start SUMO
        sumo_cmd = [SUMO_BINARY, "-c", os.path.basename(temp_cfg)]
        logger.info(f"Running command: {' '.join(sumo_cmd)}")
        
        try:
            traci.start(sumo_cmd)
            logger.info("Successfully connected to SUMO")
            
            # Initialize enhanced PyPSA integration
            pypsa_integration = EnhancedSUMOPyPSAIntegration(city)
            logger.info(f"Initialized enhanced PyPSA integration for {city}")
            
        except Exception as e:
            logger.error(f"Failed to connect to SUMO: {str(e)}")
            raise
        
        # Simulation loop counters
        step_counter = 0
        power_flow_counter = 0
        demand_response_active = False
        last_grid_state = 'normal'
        
        while traci.simulation.getMinExpectedNumber() > 0 and not stop_event.is_set():
            traci.simulationStep()
            step_counter += 1
            simulation_stats['step'] = step_counter
            
            # Get current vehicles
            vehicles = traci.vehicle.getIDList()
            simulation_stats['vehicles'] = len(vehicles)
            
            # Estimate EVs
            ev_count = int(len(vehicles) * EV_PERCENTAGE)
            simulation_stats['ev_count'] = ev_count
            
            # Get traffic lights
            traffic_lights = []
            for tl_id in traci.trafficlight.getIDList():
                if not tl_id.startswith('GS_') and not tl_id.startswith('cluster_'):
                    try:
                        # Get junction position
                        junction_pos = traci.junction.getPosition(tl_id)
                        
                        if junction_pos and junction_pos[0] != -1073741824.0:
                            gps_position = traci.simulation.convertGeo(*junction_pos)
                            state = traci.trafficlight.getRedYellowGreenState(tl_id)
                            
                            traffic_lights.append({
                                'id': tl_id,
                                'x': gps_position[0],
                                'y': gps_position[1],
                                'state': state
                            })
                    except Exception as e:
                        logger.debug(f"Error processing traffic light {tl_id}: {e}")
            
            simulation_stats['traffic_lights'] = len(traffic_lights)
            
            # Update power demand based on traffic
            if pypsa_integration:
                power_demand = pypsa_integration.update_traffic_infrastructure(
                    traffic_lights, vehicles
                )
                simulation_stats['total_demand'] = power_demand.total
                
                # Run power flow analysis periodically
                power_flow_counter += 1
                if power_flow_counter >= PYPSA_UPDATE_FREQUENCY:
                    power_flow_counter = 0
                    
                    logger.info(f"Running power flow analysis at step {step_counter}")
                    grid_analysis = pypsa_integration.run_power_flow_analysis()
                    
                    if grid_analysis['status'] == 'success':
                        new_grid_state = grid_analysis['grid_state']
                        simulation_stats['grid_state'] = new_grid_state
                        
                        # Check if grid state changed
                        if new_grid_state != last_grid_state:
                            logger.info(f"Grid state changed: {last_grid_state} -> {new_grid_state}")
                            last_grid_state = new_grid_state
                            
                            # Emit grid state change event
                            socketio.emit('grid_state_change', {
                                'old_state': last_grid_state,
                                'new_state': new_grid_state,
                                'timestamp': step_counter
                            })
                        
                        # Apply demand response if needed
                        response = grid_analysis.get('response')
                        if response and response.traffic_light_mode != 'normal':
                            if not demand_response_active:
                                logger.info(f"Activating demand response: {response.traffic_light_mode}")
                                demand_response_active = True
                            pypsa_integration.apply_demand_response(response)
                        elif demand_response_active:
                            logger.info("Deactivating demand response")
                            demand_response_active = False
                        
                        logger.info(f"Grid state: {new_grid_state}, "
                                  f"Congestion: {grid_analysis['congestion_level']:.1%}")
            
            # Send updates to frontend
            if step_counter % UPDATE_FREQUENCY == 0:
                # Get vehicle positions (limit for performance)
                vehicle_data = []
                for i, vehicle_id in enumerate(vehicles):
                    if i >= 100:  # Limit to 100 vehicles
                        break
                    try:
                        position = traci.vehicle.getPosition(vehicle_id)
                        if position and position[0] != -1073741824.0:
                            gps_position = traci.simulation.convertGeo(*position)
                            angle = traci.vehicle.getAngle(vehicle_id)
                            speed = traci.vehicle.getSpeed(vehicle_id)
                            
                            # Determine if EV (simple hash-based assignment)
                            is_ev = hash(vehicle_id) % 100 < (EV_PERCENTAGE * 100)
                            
                            vehicle_data.append({
                                'id': vehicle_id,
                                'x': gps_position[0],
                                'y': gps_position[1],
                                'angle': angle,
                                'speed': speed,
                                'is_ev': is_ev
                            })
                    except Exception as e:
                        logger.debug(f"Error processing vehicle {vehicle_id}: {e}")
                
                # Get comprehensive visualization data
                viz_data = {}
                if pypsa_integration:
                    viz_data = pypsa_integration.get_visualization_data()
                
                # Prepare update data
                update_data = {
                    'vehicles': vehicle_data,
                    'traffic_lights': traffic_lights,
                    'power': viz_data,
                    'stats': simulation_stats,
                    'timestamp': step_counter
                }
                
                socketio.emit('update', update_data)
            
            # Control simulation speed
            time.sleep(SIMULATION_SPEED)
        
        traci.close()
        logger.info("Simulation ended normally")
        
    except Exception as e:
        logger.error(f"Error in simulation: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Cleanup
        if temp_cfg and os.path.exists(temp_cfg):
            try:
                os.unlink(temp_cfg)
            except:
                pass
        os.chdir(original_dir)
        simulation_running = False
        
        # Notify frontend that simulation stopped
        socketio.emit('simulation_stopped', {'reason': 'ended'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connection_status', {'status': 'connected', 'city': CURRENT_CITY})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('start_simulation')
def handle_start_simulation(data):
    """Start the simulation"""
    global simulation_thread, CURRENT_CITY
    
    city = data.get('city', 'losangeles')
    if city not in CITY_CONFIGS:
        emit('error', {'message': f'Invalid city: {city}'})
        return
    
    CURRENT_CITY = city
    logger.info(f"Starting simulation for {CITY_CONFIGS[CURRENT_CITY]['name']}")
    
    if simulation_running:
        emit('error', {'message': 'Simulation already running'})
        return
    
    # Start simulation in background thread
    simulation_thread = threading.Thread(target=sumo_simulation, args=(CURRENT_CITY,))
    simulation_thread.start()
    
    emit('simulation_started', {'city': CURRENT_CITY})

@socketio.on('stop_simulation')
def handle_stop_simulation():
    """Stop the simulation"""
    global simulation_thread
    
    logger.info("Stopping simulation")
    
    if simulation_running:
        stop_event.set()
        if simulation_thread:
            simulation_thread.join(timeout=5)
    
    emit('simulation_stopped', {'reason': 'user_requested'})

@socketio.on('restart_simulation')
def handle_restart_simulation(data):
    """Restart the simulation"""
    global simulation_thread, CURRENT_CITY
    
    city = data.get('city', CURRENT_CITY)
    logger.info(f"Restarting simulation for {city}")
    
    # Stop current simulation
    if simulation_running:
        stop_event.set()
        if simulation_thread:
            simulation_thread.join(timeout=5)
    
    # Start new simulation
    CURRENT_CITY = city
    simulation_thread = threading.Thread(target=sumo_simulation, args=(CURRENT_CITY,))
    simulation_thread.start()
    
    emit('simulation_restarted', {'city': CURRENT_CITY})

@socketio.on('get_status')
def handle_get_status():
    """Get current simulation status"""
    status = {
        'running': simulation_running,
        'city': CURRENT_CITY,
        'stats': simulation_stats
    }
    emit('status_update', status)

if __name__ == "__main__":
    logger.info(f"Starting SUMO x PyPSA server on {HOST}:{PORT}")
    logger.info(f"SUMO path: {SUMO_PATH}")
    logger.info(f"Default city: {DEFAULT_CITY}")
    
    # Run the Flask-SocketIO server
    socketio.run(app, debug=True, host=HOST, port=PORT)