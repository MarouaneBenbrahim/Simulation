# sumo_pypsa_integration_fixed.py
"""
FIXED Integration module for SUMO traffic simulation and PyPSA power system analysis.
This module creates a bidirectional relationship between traffic patterns and power grid dynamics.
"""

import traci
import pypsa
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging
from config import CHARGING_STATIONS, POWER_ZONES, EV_PERCENTAGE, TRAFFIC_LIGHT_POWER, EV_CHARGING_POWER

class SUMOPyPSAIntegration:
    """Main integration class for SUMO and PyPSA"""
    
    def __init__(self, city: str):
        """Initialize the integration system"""
        self.city = city
        self.network = pypsa.Network()
        
        # Component mappings
        self.traffic_lights_to_buses = {}
        self.charging_stations = {}
        self.ev_vehicles = set()
        self.power_zones = {}
        
        # Metrics tracking
        self.power_demand_history = []
        self.traffic_density_history = []
        self.charging_events = []
        self.current_timestep = 0
        
        # Power consumption parameters from config
        self.traffic_light_power = TRAFFIC_LIGHT_POWER
        self.ev_percentage = EV_PERCENTAGE
        
        # Charging parameters from config
        self.fast_charge_power = EV_CHARGING_POWER['fast']
        self.medium_charge_power = EV_CHARGING_POWER['medium']
        self.slow_charge_power = EV_CHARGING_POWER['slow']
        
        # Grid state
        self.grid_operational = True
        self.outage_zones = []
        self.grid_congestion_level = 0.0
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def initialize_pypsa_network(self):
        """Initialize or load PyPSA network for the city"""
        # Use the city name directly (newyork, miami, losangeles)
        pypsa_dir = f'pypsa_network/{self.city}'
        
        if os.path.exists(pypsa_dir):
            # Try to load existing network
            buses_file = os.path.join(pypsa_dir, 'buses.csv')
            lines_file = os.path.join(pypsa_dir, 'lines.csv')
            
            if os.path.exists(buses_file) and os.path.exists(lines_file):
                self.logger.info(f"Loading existing PyPSA network for {self.city}")
                self._load_existing_network(pypsa_dir)
            else:
                self.logger.info(f"Creating synthetic PyPSA network for {self.city}")
                self._create_synthetic_network()
        else:
            self.logger.info(f"Creating synthetic PyPSA network for {self.city}")
            self._create_synthetic_network()
            
        self._initialize_charging_stations()
        self._map_traffic_lights_to_buses()
        
        # Log network summary
        self.logger.info(f"Network initialized with {len(self.network.buses)} buses, "
                        f"{len(self.network.lines)} lines, {len(self.network.generators)} generators")
        
    def _create_synthetic_network(self):
        """Create a synthetic power network for the city"""
        if self.city == "newyork":
            # Focus on Jersey City area where traffic actually is
            buses = [
                ("Jersey_City", 40.735, -74.030),
                ("Newport", 40.740, -74.028),
                ("Exchange_Place", 40.738, -74.032),
                ("Liberty_State", 40.745, -74.025),
            ]
        elif self.city == "miami":
            buses = [
                ("Wynwood", 25.805, -80.200),
                ("Design_District", 25.810, -80.190),
                ("Midtown", 25.808, -80.195),
                ("Downtown", 25.774, -80.193),
            ]
        else:  # los angeles - Vernon area
            buses = [
                ("Vernon_West", 34.018, -118.225),
                ("Vernon_Central", 34.020, -118.220),
                ("Vernon_East", 34.025, -118.215),
                ("Commerce", 34.023, -118.218),
            ]
        
        # Add buses to network
        for bus_name, lat, lon in buses:
            self.network.add("Bus", bus_name, x=lon, y=lat, v_nom=138)
        
        # Add generators
        for i, (bus_name, _, _) in enumerate(buses):
            # Conventional generator
            self.network.add("Generator", 
                           f"Gen_{bus_name}",
                           bus=bus_name,
                           p_nom=100,  # MW
                           marginal_cost=50 + i*5)
            
            # Solar generator
            if i % 2 == 0:  # Add solar to every other bus
                self.network.add("Generator",
                               f"Solar_{bus_name}",
                               bus=bus_name,
                               p_nom=30,  # MW peak
                               marginal_cost=0)
        
        # Add transmission lines
        for i in range(len(buses) - 1):
            self.network.add("Line",
                           f"Line_{i}",
                           bus0=buses[i][0],
                           bus1=buses[i+1][0],
                           x=0.01,
                           r=0.01,
                           s_nom=100)  # MVA
        
        # Add loads
        for bus_name, _, _ in buses:
            self.network.add("Load",
                           f"Load_{bus_name}",
                           bus=bus_name,
                           p_set=20)  # MW base load
    
    def _load_existing_network(self, pypsa_dir):
        """Load existing PyPSA network from files"""
        try:
            buses_df = pd.read_csv(os.path.join(pypsa_dir, 'buses.csv'))
            lines_df = pd.read_csv(os.path.join(pypsa_dir, 'lines.csv'))
            
            # Check for generators and loads files
            generators_file = os.path.join(pypsa_dir, 'generators.csv')
            loads_file = os.path.join(pypsa_dir, 'loads.csv')
            
            # Add buses
            for _, bus in buses_df.iterrows():
                self.network.add("Bus", bus['id'], 
                               x=bus.get('x', 0), 
                               y=bus.get('y', 0),
                               v_nom=bus.get('v_nom', 138))
            
            # Add lines
            for _, line in lines_df.iterrows():
                self.network.add("Line", line['id'],
                               bus0=line['bus0'],
                               bus1=line['bus1'],
                               x=line.get('x', 0.01),
                               r=line.get('r', 0.01),
                               s_nom=line.get('s_nom', 100))
            
            # Load generators if file exists
            if os.path.exists(generators_file):
                generators_df = pd.read_csv(generators_file)
                for _, gen in generators_df.iterrows():
                    self.network.add("Generator", gen['id'],
                                   bus=gen['bus'],
                                   p_nom=gen.get('p_nom', 100),
                                   marginal_cost=gen.get('marginal_cost', 50),
                                   carrier=gen.get('carrier', 'gas'))
            else:
                # Add default generators
                for bus in self.network.buses.index:
                    self.network.add("Generator", f"Gen_{bus}", 
                                   bus=bus, p_nom=50, marginal_cost=50)
            
            # Load loads if file exists
            if os.path.exists(loads_file):
                loads_df = pd.read_csv(loads_file)
                for _, load in loads_df.iterrows():
                    self.network.add("Load", load['id'],
                                   bus=load['bus'],
                                   p_set=load.get('p_set', 20))
            else:
                # Add default loads
                for bus in self.network.buses.index:
                    self.network.add("Load", f"Load_{bus}", 
                                   bus=bus, p_set=20)
                    
        except Exception as e:
            self.logger.error(f"Error loading network: {e}")
            self._create_synthetic_network()
    
    def _initialize_charging_stations(self):
        """Initialize EV charging stations from config"""
        if self.city in CHARGING_STATIONS:
            stations = CHARGING_STATIONS[self.city]
            
            for station in stations:
                self.charging_stations[station["id"]] = {
                    "position": (station["lat"], station["lon"]),
                    "bus": self._find_nearest_bus(station["lat"], station["lon"]),
                    "capacity": station["capacity"],
                    "vehicles_charging": [],
                    "power_available": self.fast_charge_power * station["capacity"]
                }
            
            self.logger.info(f"Initialized {len(self.charging_stations)} charging stations")
    
    def _map_traffic_lights_to_buses(self):
        """Map traffic lights to their nearest power buses"""
        # This will be done dynamically when we receive traffic light data
        pass
    
    def _find_nearest_bus(self, lat, lon):
        """Find the nearest power bus to a given position"""
        if len(self.network.buses) == 0:
            return None
            
        min_dist = float('inf')
        nearest_bus = None
        
        for bus in self.network.buses.index:
            bus_data = self.network.buses.loc[bus]
            # Calculate distance using Haversine approximation
            dist = np.sqrt((bus_data.y - lat)**2 + (bus_data.x - lon)**2)
            if dist < min_dist:
                min_dist = dist
                nearest_bus = bus
        
        return nearest_bus if nearest_bus else self.network.buses.index[0]
    
    def update_power_demand(self, traffic_lights, vehicles, time_step):
        """Update power demand based on current traffic state"""
        self.current_timestep = time_step
        
        # Calculate traffic light power consumption
        tl_power = self._calculate_traffic_light_power(traffic_lights)
        
        # Calculate street lighting (varies with time of day)
        street_power = self._calculate_street_lighting_power(time_step)
        
        # Calculate EV charging demand
        ev_power = self._calculate_ev_charging_power(vehicles)
        
        # Update loads in PyPSA network
        total_power_by_bus = {}
        
        # Initialize with zeros
        for bus in self.network.buses.index:
            total_power_by_bus[bus] = 0
        
        # Add traffic light power (distributed across buses)
        tl_total = sum(tl_power.values()) / 1000  # Convert kW to MW
        for bus in self.network.buses.index:
            total_power_by_bus[bus] += tl_total / len(self.network.buses)
        
        # Add street lighting power
        for bus, power in street_power.items():
            if bus in total_power_by_bus:
                total_power_by_bus[bus] += power / 1000  # Convert kW to MW
        
        # Add EV charging power
        ev_total = sum(ev_power.values()) / 1000  # Convert kW to MW
        for station_id, power in ev_power.items():
            if station_id in self.charging_stations:
                bus = self.charging_stations[station_id]["bus"]
                if bus in total_power_by_bus:
                    total_power_by_bus[bus] += power / 1000  # Convert kW to MW
        
        # Update PyPSA loads
        for bus, power in total_power_by_bus.items():
            # Find the load connected to this bus
            for load_id in self.network.loads.index:
                if self.network.loads.at[load_id, 'bus'] == bus:
                    # Base load + traffic-related load
                    self.network.loads.at[load_id, 'p_set'] = 20 + power
                    break
        
        # Store metrics
        total_demand = sum(total_power_by_bus.values())
        self.power_demand_history.append({
            'timestep': time_step,
            'total_demand': total_demand,
            'tl_demand': sum(tl_power.values()) / 1000,
            'ev_demand': sum(ev_power.values()) / 1000,
            'street_demand': sum(street_power.values()) / 1000
        })
        
        # Log every 100 timesteps
        if time_step % 100 == 0:
            self.logger.info(f"Step {time_step}: Total demand = {total_demand:.2f} MW, "
                           f"EVs charging = {len([s for s in self.charging_stations.values() if s['vehicles_charging']])}")
        
        return {
            'total_demand': total_demand,
            'by_bus': total_power_by_bus,
            'traffic_lights': sum(tl_power.values()) / 1000,
            'ev_charging': sum(ev_power.values()) / 1000,
            'street_lighting': sum(street_power.values()) / 1000
        }
    
    def _calculate_traffic_light_power(self, traffic_lights):
        """Calculate power consumption of traffic lights"""
        tl_power = {}
        
        for tl in traffic_lights:
            tl_id = tl['id']
            state = tl['state']
            
            # Calculate power based on signal state
            power = 0
            green_count = state.count('G') + state.count('g')
            yellow_count = state.count('Y') + state.count('y')
            red_count = state.count('R') + state.count('r')
            
            power += green_count * self.traffic_light_power['green']
            power += yellow_count * self.traffic_light_power['yellow']
            power += red_count * self.traffic_light_power['red']
            
            tl_power[tl_id] = power
        
        return tl_power
    
    def _calculate_street_lighting_power(self, time_step):
        """Calculate street lighting power (varies with time of day)"""
        # Simple model: lights on from 6 PM to 6 AM
        hour = (time_step * 0.5 / 3600) % 24  # Convert timestep to hour of day
        
        street_power = {}
        for bus in self.network.buses.index:
            if hour < 6 or hour > 18:  # Night time
                street_power[bus] = 50  # kW base street lighting per zone
            else:
                street_power[bus] = 10  # Reduced lighting during day
        
        return street_power
    
    def _calculate_ev_charging_power(self, vehicles):
        """Calculate EV charging power demand"""
        ev_power = {}
        
        # Mark EVs based on hash (deterministic)
        for vehicle_id in vehicles:
            if hash(vehicle_id) % 100 < (self.ev_percentage * 100):
                self.ev_vehicles.add(vehicle_id)
        
        # Simulate charging at stations
        for station_id, station in self.charging_stations.items():
            charging_power = 0
            vehicles_at_station = []
            
            # Simulate some vehicles charging (simplified)
            # In real implementation, would check actual vehicle positions
            for i, vehicle_id in enumerate(list(self.ev_vehicles)[:station["capacity"]]):
                if vehicle_id in vehicles:
                    vehicles_at_station.append(vehicle_id)
                    # Vary charging speed based on station load
                    if len(vehicles_at_station) <= station["capacity"] // 3:
                        charging_power += self.fast_charge_power
                    elif len(vehicles_at_station) <= 2 * station["capacity"] // 3:
                        charging_power += self.medium_charge_power
                    else:
                        charging_power += self.slow_charge_power
            
            station["vehicles_charging"] = vehicles_at_station
            ev_power[station_id] = charging_power
        
        return ev_power
    
    def run_pypsa_optimization(self):
        """Run PyPSA power flow optimization"""
        try:
            # Set snapshot for optimization
            self.network.set_snapshots([pd.Timestamp.now()])
            
            # Try to run optimal power flow
            try:
                # Use GLPK if available, otherwise fallback to basic power flow
                self.network.lopf(solver_name='glpk', pyomo=False)
            except:
                # Fallback to simple power flow calculation
                self.network.pf()
            
            # Check for congestion and constraints
            line_loading = {}
            max_loading = 0
            
            for line in self.network.lines.index:
                try:
                    # Get power flow on the line
                    if hasattr(self.network.lines_t, 'p0') and len(self.network.lines_t.p0) > 0:
                        flow = abs(self.network.lines_t.p0.iloc[0].get(line, 0))
                    else:
                        flow = 0
                    
                    capacity = self.network.lines.at[line, 's_nom']
                    loading = flow / capacity if capacity > 0 else 0
                    line_loading[line] = loading
                    max_loading = max(max_loading, loading)
                except:
                    line_loading[line] = 0
            
            self.grid_congestion_level = max_loading
            
            # Check for potential outages (if loading > 95%)
            overloaded_lines = [line for line, loading in line_loading.items() if loading > 0.95]
            
            # Get total generation and load
            try:
                total_generation = sum([self.network.generators.at[gen, 'p_nom'] 
                                      for gen in self.network.generators.index])
                total_load = sum([self.network.loads.at[load, 'p_set'] 
                                for load in self.network.loads.index])
            except:
                total_generation = 0
                total_load = 0
            
            grid_state = {
                'operational': len(overloaded_lines) == 0,
                'congestion_level': self.grid_congestion_level,
                'overloaded_lines': overloaded_lines,
                'total_generation': total_generation,
                'total_load': total_load,
                'line_loading': line_loading
            }
            
            return grid_state
            
        except Exception as e:
            self.logger.warning(f"PyPSA optimization warning: {e}")
            # Return default state if optimization fails
            return {
                'operational': True,
                'congestion_level': 0.2,  # Assume 20% loading
                'overloaded_lines': [],
                'total_generation': 100,
                'total_load': 80
            }
    
    def apply_grid_feedback_to_traffic(self, grid_state):
        """Apply power grid state feedback to traffic simulation"""
        
        # If grid is overloaded, implement demand response
        if grid_state['congestion_level'] > 0.8:
            self._implement_demand_response()
            self.logger.info(f"Implementing demand response at {grid_state['congestion_level']:.1%} congestion")
        
        # If there are outages, affect traffic lights
        if not grid_state['operational']:
            self._handle_power_outage(grid_state['overloaded_lines'])
        
        # Adjust EV charging based on grid state
        self._adjust_ev_charging(grid_state['congestion_level'])
    
    def _implement_demand_response(self):
        """Implement demand response measures"""
        # Temporarily reduce power consumption
        pass
    
    def _handle_power_outage(self, affected_lines):
        """Handle power outage affecting traffic lights"""
        # In real implementation, would affect traffic lights
        self.logger.warning(f"Power outage on lines: {affected_lines}")
    
    def _adjust_ev_charging(self, congestion_level):
        """Adjust EV charging based on grid congestion"""
        for station in self.charging_stations.values():
            if congestion_level > 0.7:
                # Limit to medium charging during high congestion
                station["power_available"] = self.medium_charge_power * station["capacity"]
            elif congestion_level < 0.3:
                # Allow fast charging during low congestion
                station["power_available"] = self.fast_charge_power * station["capacity"]
            else:
                # Normal operation
                station["power_available"] = (self.fast_charge_power * 0.5 + 
                                             self.medium_charge_power * 0.5) * station["capacity"]
    
    def get_visualization_data(self):
        """Get data for visualization"""
        # Prepare charging station data
        charging_stations_data = []
        for sid, station in self.charging_stations.items():
            charging_stations_data.append({
                'id': sid,
                'lat': station['position'][0],
                'lon': station['position'][1],
                'vehicles_charging': len(station['vehicles_charging']),
                'capacity': station['capacity'],
                'utilization': len(station['vehicles_charging']) / station['capacity'] if station['capacity'] > 0 else 0
            })
        
        # Prepare power grid data
        grid_buses = []
        for bus in self.network.buses.index:
            bus_data = self.network.buses.loc[bus]
            # Get load at this bus
            bus_load = 0
            for load_id in self.network.loads.index:
                if self.network.loads.at[load_id, 'bus'] == bus:
                    bus_load = self.network.loads.at[load_id, 'p_set']
                    break
            
            grid_buses.append({
                'id': bus,
                'x': bus_data.x,
                'y': bus_data.y,
                'load': bus_load,
                'voltage': bus_data.v_nom
            })
        
        # Prepare transmission lines data
        grid_lines = []
        for line in self.network.lines.index:
            line_data = self.network.lines.loc[line]
            grid_lines.append({
                'id': line,
                'from': line_data.bus0,
                'to': line_data.bus1,
                'capacity': line_data.s_nom,
                'loading': 0  # Will be updated after power flow
            })
        
        return {
            'power_demand': self.power_demand_history[-1] if self.power_demand_history else {
                'total_demand': 0,
                'tl_demand': 0,
                'ev_demand': 0,
                'street_demand': 0
            },
            'grid_congestion': self.grid_congestion_level,
            'charging_stations': charging_stations_data,
            'grid_operational': self.grid_operational,
            'grid_buses': grid_buses,
            'grid_lines': grid_lines,
            'total_evs': len(self.ev_vehicles)
        }