# sumo_pypsa_integration.py
"""
Integration module for SUMO traffic simulation and PyPSA power system analysis.
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

class SUMOPyPSAIntegration:
    """Main integration class for SUMO and PyPSA"""
    
    def __init__(self, city: str):
        """
        Initialize the integration system
        
        Args:
            city: Name of the city (newyork, miami, losangeles)
        """
        self.city = city
        self.network = pypsa.Network()
        
        # Component mappings
        self.traffic_lights_to_buses = {}  # Map traffic lights to power buses
        self.charging_stations = {}  # EV charging station locations
        self.ev_vehicles = set()  # Track electric vehicles
        self.power_zones = {}  # Power grid zones mapped to geographic areas
        
        # Metrics tracking
        self.power_demand_history = []
        self.traffic_density_history = []
        self.charging_events = []
        self.current_timestep = 0
        
        # Power consumption parameters (kW)
        self.traffic_light_power = {
            'green': 0.5,
            'yellow': 0.4, 
            'red': 0.3
        }
        self.street_light_base_power = 0.15  # kW per segment
        self.ev_percentage = 0.3  # 30% of vehicles are electric
        
        # Charging parameters
        self.fast_charge_power = 150  # kW
        self.medium_charge_power = 50  # kW
        self.slow_charge_power = 7.4  # kW
        
        # Grid state
        self.grid_operational = True
        self.outage_zones = []
        self.grid_congestion_level = 0.0
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def initialize_pypsa_network(self):
        """Initialize or load PyPSA network for the city"""
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
        
    def _create_synthetic_network(self):
        """Create a synthetic power network for the city"""
        # Create buses based on city zones
        if self.city == "newyork":
            buses = [
                ("Manhattan_North", 40.785, -73.968),
                ("Manhattan_South", 40.758, -73.985),
                ("Times_Square", 40.758, -73.985),
                ("Central_Park", 40.782, -73.965),
            ]
        elif self.city == "miami":
            buses = [
                ("Downtown", 25.774, -80.193),
                ("Beach", 25.790, -80.130),
                ("Airport", 25.795, -80.287),
            ]
        else:  # los angeles
            buses = [
                ("Downtown", 34.052, -118.243),
                ("Hollywood", 34.092, -118.328),
                ("Santa_Monica", 34.019, -118.491),
                ("LAX", 33.942, -118.408),
            ]
        
        # Add buses to network
        for bus_name, lat, lon in buses:
            self.network.add("Bus", bus_name, x=lon, y=lat, v_nom=138)
        
        # Add generators (mix of conventional and renewable)
        for i, (bus_name, _, _) in enumerate(buses):
            # Conventional generator
            self.network.add("Generator", 
                           f"Gen_{bus_name}",
                           bus=bus_name,
                           p_nom=100,  # MW
                           marginal_cost=50 + i*5)  # $/MWh
            
            # Solar generator (only during day)
            self.network.add("Generator",
                           f"Solar_{bus_name}",
                           bus=bus_name,
                           p_nom=30,  # MW peak
                           marginal_cost=0)
        
        # Add transmission lines between buses
        for i in range(len(buses) - 1):
            self.network.add("Line",
                           f"Line_{i}",
                           bus0=buses[i][0],
                           bus1=buses[i+1][0],
                           x=0.01,
                           r=0.01,
                           s_nom=100)  # MVA
        
        # Add initial loads
        for bus_name, _, _ in buses:
            self.network.add("Load",
                           f"Load_{bus_name}",
                           bus=bus_name,
                           p_set=20)  # MW base load
    
    def _load_existing_network(self, pypsa_dir):
        """Load existing PyPSA network from files"""
        buses_df = pd.read_csv(os.path.join(pypsa_dir, 'buses.csv'))
        lines_df = pd.read_csv(os.path.join(pypsa_dir, 'lines.csv'))
        
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
        
        # Add default generators and loads
        for bus in self.network.buses.index:
            self.network.add("Generator", f"Gen_{bus}", bus=bus, p_nom=50, marginal_cost=50)
            self.network.add("Load", f"Load_{bus}", bus=bus, p_set=20)
    
    def _initialize_charging_stations(self):
        """Initialize EV charging stations for the city"""
        if self.city == "newyork":
            stations = [
                {"id": "CS_TimesSquare", "lat": 40.758, "lon": -73.985, "bus": "Times_Square", "capacity": 10},
                {"id": "CS_CentralPark", "lat": 40.782, "lon": -73.965, "bus": "Central_Park", "capacity": 8},
            ]
        elif self.city == "miami":
            stations = [
                {"id": "CS_Downtown", "lat": 25.774, "lon": -80.193, "bus": "Downtown", "capacity": 6},
                {"id": "CS_Beach", "lat": 25.790, "lon": -80.130, "bus": "Beach", "capacity": 8},
            ]
        else:  # los angeles
            stations = [
                {"id": "CS_Hollywood", "lat": 34.092, "lon": -118.328, "bus": "Hollywood", "capacity": 10},
                {"id": "CS_LAX", "lat": 33.942, "lon": -118.408, "bus": "LAX", "capacity": 12},
            ]
        
        for station in stations:
            self.charging_stations[station["id"]] = {
                "position": (station["lat"], station["lon"]),
                "bus": station.get("bus", self._find_nearest_bus(station["lat"], station["lon"])),
                "capacity": station["capacity"],
                "vehicles_charging": [],
                "power_available": self.fast_charge_power * station["capacity"]
            }
    
    def _map_traffic_lights_to_buses(self):
        """Map traffic lights to their nearest power buses"""
        try:
            for tl_id in traci.trafficlight.getIDList():
                # Get traffic light position
                controlled_links = traci.trafficlight.getControlledLinks(tl_id)
                if controlled_links and controlled_links[0]:
                    first_link = controlled_links[0][0]
                    from_edge = first_link[0]
                    edge_shape = traci.edge.getShape(from_edge)
                    if edge_shape:
                        pos = traci.simulation.convertGeo(*edge_shape[0])
                        nearest_bus = self._find_nearest_bus(pos[1], pos[0])
                        self.traffic_lights_to_buses[tl_id] = nearest_bus
        except:
            # If SUMO is not connected yet, we'll map them when we first get traffic light data
            pass
    
    def _find_nearest_bus(self, lat, lon):
        """Find the nearest power bus to a given position"""
        min_dist = float('inf')
        nearest_bus = None
        
        for bus in self.network.buses.index:
            bus_data = self.network.buses.loc[bus]
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
        
        # Aggregate power by bus
        for bus in self.network.buses.index:
            total_power_by_bus[bus] = 0
        
        # Add traffic light power
        for tl_id, power in tl_power.items():
            if tl_id in self.traffic_lights_to_buses:
                bus = self.traffic_lights_to_buses[tl_id]
                total_power_by_bus[bus] += power / 1000  # Convert kW to MW
        
        # Add street lighting power
        for bus, power in street_power.items():
            total_power_by_bus[bus] += power / 1000  # Convert kW to MW
        
        # Add EV charging power
        for station_id, power in ev_power.items():
            if station_id in self.charging_stations:
                bus = self.charging_stations[station_id]["bus"]
                total_power_by_bus[bus] += power / 1000  # Convert kW to MW
        
        # Update PyPSA loads
        for bus, power in total_power_by_bus.items():
            load_name = f"Load_{bus}"
            if load_name in self.network.loads.index:
                # Base load + traffic-related load
                self.network.loads.at[load_name, 'p_set'] = 20 + power
        
        # Store metrics
        total_demand = sum(total_power_by_bus.values())
        self.power_demand_history.append({
            'timestep': time_step,
            'total_demand': total_demand,
            'tl_demand': sum(tl_power.values()) / 1000,
            'ev_demand': sum(ev_power.values()) / 1000,
            'street_demand': sum(street_power.values()) / 1000
        })
        
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
        # ========== ADD THIS DEBUG CODE ==========
        print(f"Total vehicles: {len(vehicles)}")
        print(f"EV percentage: {self.ev_percentage}")
        
        # Mark some vehicles as EVs
        for vehicle_id in vehicles:
            if hash(vehicle_id) % 100 < (self.ev_percentage * 100):
                self.ev_vehicles.add(vehicle_id)
        
        print(f"Total EVs identified: {len(self.ev_vehicles)}")
        print(f"Charging stations available: {len(self.charging_stations)}")
        # ========== END DEBUG CODE ==========       
        # Mark some vehicles as EVs
        for vehicle_id in vehicles:
            if hash(vehicle_id) % 100 < (self.ev_percentage * 100):
                self.ev_vehicles.add(vehicle_id)
        
        # Simulate charging at stations
        for station_id, station in self.charging_stations.items():
            charging_power = 0
            
            # Check if any EVs are near the station
            for vehicle_id in self.ev_vehicles:
                try:
                    pos = traci.vehicle.getPosition(vehicle_id)
                    gps_pos = traci.simulation.convertGeo(*pos)
                    
                    # Check if vehicle is within 50m of station
                    dist = np.sqrt((gps_pos[1] - station["position"][0])**2 + 
                                 (gps_pos[0] - station["position"][1])**2)
                    
                    if dist < 0.0005:  # Roughly 50m in degrees
                        speed = traci.vehicle.getSpeed(vehicle_id)
                        if speed < 1:  # Vehicle is stopped
                            # Add to charging if capacity available
                            if len(station["vehicles_charging"]) < station["capacity"]:
                                if vehicle_id not in station["vehicles_charging"]:
                                    station["vehicles_charging"].append(vehicle_id)
                                charging_power += self.medium_charge_power
                except:
                    continue
            
            # Remove vehicles that have left
            station["vehicles_charging"] = [v for v in station["vehicles_charging"] 
                                           if v in vehicles]
            
            ev_power[station_id] = charging_power
        
        return ev_power
    
    def run_pypsa_optimization(self):
        """Run PyPSA power flow optimization"""
        try:
            # Set snapshot for optimization
            self.network.set_snapshots([pd.Timestamp.now()])
            
            # Run optimal power flow
            self.network.lopf(solver_name='glpk')
            
            # Check for congestion and constraints
            line_loading = {}
            for line in self.network.lines.index:
                flow = abs(self.network.lines_t.p0.at[self.network.snapshots[0], line])
                capacity = self.network.lines.at[line, 's_nom']
                loading = flow / capacity if capacity > 0 else 0
                line_loading[line] = loading
            
            # Determine grid state
            max_loading = max(line_loading.values()) if line_loading else 0
            self.grid_congestion_level = max_loading
            
            # Check for potential outages (if loading > 95%)
            overloaded_lines = [line for line, loading in line_loading.items() if loading > 0.95]
            
            grid_state = {
                'operational': len(overloaded_lines) == 0,
                'congestion_level': self.grid_congestion_level,
                'overloaded_lines': overloaded_lines,
                'total_generation': self.network.generators_t.p.sum().sum(),
                'total_load': self.network.loads_t.p.sum().sum(),
                'line_loading': line_loading
            }
            
            self.logger.info(f"Grid congestion level: {self.grid_congestion_level:.2%}")
            
            return grid_state
            
        except Exception as e:
            self.logger.error(f"Error in PyPSA optimization: {e}")
            return {
                'operational': True,
                'congestion_level': 0,
                'overloaded_lines': [],
                'total_generation': 0,
                'total_load': 0
            }
    
    def apply_grid_feedback_to_traffic(self, grid_state):
        """Apply power grid state feedback to traffic simulation"""
        
        # If grid is overloaded, implement demand response
        if grid_state['congestion_level'] > 0.8:
            self._implement_demand_response()
        
        # If there are outages, affect traffic lights
        if not grid_state['operational']:
            self._handle_power_outage(grid_state['overloaded_lines'])
        
        # Adjust EV charging based on grid state
        self._adjust_ev_charging(grid_state['congestion_level'])
    
    def _implement_demand_response(self):
        """Implement demand response measures"""
        # Reduce street lighting
        self.street_light_base_power *= 0.7
        
        # Reduce charging rates
        for station in self.charging_stations.values():
            station["power_available"] = self.slow_charge_power * station["capacity"]
        
        self.logger.info("Implementing demand response due to grid congestion")
    
    def _handle_power_outage(self, affected_lines):
        """Handle power outage affecting traffic lights"""
        # Find affected buses
        affected_buses = set()
        for line in affected_lines:
            line_data = self.network.lines.loc[line]
            affected_buses.add(line_data.bus0)
            affected_buses.add(line_data.bus1)
        
        # Set traffic lights in affected areas to flashing/all red
        for tl_id, bus in self.traffic_lights_to_buses.items():
            if bus in affected_buses:
                try:
                    # Get current state length
                    current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    # Set to all red (emergency mode)
                    emergency_state = 'r' * len(current_state)
                    traci.trafficlight.setRedYellowGreenState(tl_id, emergency_state)
                    self.logger.warning(f"Traffic light {tl_id} set to emergency mode due to power outage")
                except:
                    pass
    
    def _adjust_ev_charging(self, congestion_level):
        """Adjust EV charging based on grid congestion"""
        if congestion_level > 0.7:
            # Limit fast charging
            for station in self.charging_stations.values():
                station["power_available"] = self.medium_charge_power * station["capacity"]
        elif congestion_level < 0.3:
            # Allow fast charging
            for station in self.charging_stations.values():
                station["power_available"] = self.fast_charge_power * station["capacity"]
    
    def get_visualization_data(self):
        """Get data for visualization"""
        return {
            'power_demand': self.power_demand_history[-1] if self.power_demand_history else None,
            'grid_congestion': self.grid_congestion_level,
            'charging_stations': [
                {
                    'id': sid,
                    'position': station['position'],
                    'vehicles_charging': len(station['vehicles_charging']),
                    'capacity': station['capacity']
                }
                for sid, station in self.charging_stations.items()
            ],
            'grid_operational': self.grid_operational
        }