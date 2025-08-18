# enhanced_pypsa_integration.py
"""
Enhanced integration module for SUMO traffic simulation and PyPSA power system analysis.
This module creates a realistic bidirectional relationship between traffic patterns and power grid dynamics.
"""

import traci
import pypsa
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from enum import Enum

class GridState(Enum):
    """Power grid operational states"""
    NORMAL = "normal"
    STRESSED = "stressed"
    CRITICAL = "critical"
    BLACKOUT = "blackout"

@dataclass
class PowerDemand:
    """Structure for power demand data"""
    traffic_lights: float
    street_lights: float
    ev_charging: float
    total: float
    timestamp: datetime

@dataclass
class TrafficResponse:
    """Traffic system response to power grid conditions"""
    traffic_light_mode: str
    street_light_dimming: float
    ev_charging_limit: str
    affected_intersections: List[str]

class EnhancedSUMOPyPSAIntegration:
    """Advanced integration class for SUMO and PyPSA with realistic modeling"""
    
    def __init__(self, city: str = "losangeles"):
        """Initialize the enhanced integration system"""
        self.city = city
        self.network = pypsa.Network()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.traffic_lights = {}
        self.charging_stations = {}
        self.ev_vehicles = {}
        self.power_zones = {}
        
        # State tracking
        self.grid_state = GridState.NORMAL
        self.current_demand = None
        self.demand_history = []
        self.congestion_history = []
        
        # Time tracking
        self.simulation_time = 0
        self.time_of_day = 12  # Start at noon
        
        # Load configuration
        from config import (POWER_ZONES, CHARGING_STATIONS, 
                           GRID_PARAMETERS, EV_CHARGING_POWER)
        self.power_zones_config = POWER_ZONES[city]
        self.charging_config = CHARGING_STATIONS[city]
        self.grid_params = GRID_PARAMETERS
        self.ev_params = EV_CHARGING_POWER
        
        # Initialize network
        self._create_realistic_power_network()
        
    def _create_realistic_power_network(self):
        """Create a realistic power network for Los Angeles"""
        
        # Create buses for each zone
        for zone_name, zone_config in self.power_zones_config.items():
            # Main transmission bus
            self.network.add("Bus", 
                           f"{zone_name}_HV",
                           v_nom=zone_config.get('v_nom', 138),
                           x=zone_config['bounds'][0][1],
                           y=zone_config['bounds'][0][0])
            
            # Distribution bus
            self.network.add("Bus",
                           f"{zone_name}_MV",
                           v_nom=12.47,
                           x=zone_config['bounds'][0][1],
                           y=zone_config['bounds'][0][0])
            
            # Add transformer between HV and MV
            self.network.add("Transformer",
                           f"T_{zone_name}",
                           bus0=f"{zone_name}_HV",
                           bus1=f"{zone_name}_MV",
                           s_nom=zone_config['capacity_mw'] * 0.3,
                           x=0.1,
                           r=0.01)
        
        # Create transmission lines between zones
        self._create_transmission_lines()
        
        # Add generators (mix of renewable and conventional)
        self._add_generators()
        
        # Add base loads
        self._add_base_loads()
        
    def _create_transmission_lines(self):
        """Create realistic transmission lines between zones"""
        connections = [
            ("DTLA_HV", "Vernon_HV", 500, 138),
            ("Vernon_HV", "Harbor_HV", 800, 230),
            ("DTLA_HV", "LAX_HV", 400, 138),
            ("Harbor_HV", "LAX_HV", 600, 138)
        ]
        
        for i, (bus0, bus1, s_nom, v_nom) in enumerate(connections):
            self.network.add("Line",
                           f"L{i}_{bus0}_{bus1}",
                           bus0=bus0,
                           bus1=bus1,
                           s_nom=s_nom,
                           x=0.01 * (v_nom / 138),  # Scaled reactance
                           r=0.001 * (v_nom / 138),
                           b=0.0001)
    
    def _add_generators(self):
        """Add realistic generation mix for LA"""
        # Natural gas plants
        self.network.add("Generator",
                       "Harbor_Gas",
                       bus="Harbor_HV",
                       p_nom=800,
                       marginal_cost=50,
                       ramp_limit_up=100,
                       ramp_limit_down=100)
        
        # Solar farms (variable output based on time)
        self.network.add("Generator",
                       "LAX_Solar",
                       bus="LAX_HV",
                       p_nom=200,
                       marginal_cost=0,
                       p_max_pu=self._solar_profile())
        
        # Wind (offshore)
        self.network.add("Generator",
                       "Harbor_Wind",
                       bus="Harbor_HV",
                       p_nom=150,
                       marginal_cost=0,
                       p_max_pu=self._wind_profile())
        
        # Peaker plants for demand response
        for zone in ["DTLA", "Vernon"]:
            self.network.add("Generator",
                           f"{zone}_Peaker",
                           bus=f"{zone}_HV",
                           p_nom=100,
                           marginal_cost=150,  # Expensive peaker
                           ramp_limit_up=50)
    
    def _add_base_loads(self):
        """Add base loads for each zone"""
        base_loads = {
            "DTLA": 200,
            "Vernon": 150,
            "Harbor": 100,
            "LAX": 120
        }
        
        for zone, load in base_loads.items():
            self.network.add("Load",
                           f"Load_{zone}",
                           bus=f"{zone}_MV",
                           p_set=load)
    
    def _solar_profile(self):
        """Generate realistic solar generation profile"""
        hours = np.arange(24)
        # Peak at noon, zero at night
        profile = np.maximum(0, np.cos((hours - 12) * np.pi / 12))
        return profile[self.time_of_day % 24]
    
    def _wind_profile(self):
        """Generate realistic wind generation profile"""
        # More variable, stronger at night
        base = 0.4 + 0.3 * np.sin(self.time_of_day * np.pi / 12)
        variability = np.random.normal(0, 0.1)
        return np.clip(base + variability, 0, 1)
    
    def update_traffic_infrastructure(self, traffic_lights: List[Dict], 
                                    vehicles: List[str]) -> PowerDemand:
        """Calculate power demand from traffic infrastructure"""
        
        # Update time of day
        self.simulation_time += 1
        self.time_of_day = (12 + self.simulation_time * 0.1 / 3600) % 24
        
        # Calculate traffic light power
        tl_power = self._calculate_traffic_light_power_realistic(traffic_lights)
        
        # Calculate street lighting based on time and traffic density
        street_power = self._calculate_street_lighting_adaptive(vehicles)
        
        # Calculate EV charging with smart charging logic
        ev_power = self._calculate_ev_charging_smart(vehicles)
        
        # Total demand
        total_power = tl_power + street_power + ev_power
        
        # Create demand object
        demand = PowerDemand(
            traffic_lights=tl_power,
            street_lights=street_power,
            ev_charging=ev_power,
            total=total_power,
            timestamp=datetime.now()
        )
        
        self.current_demand = demand
        self.demand_history.append(demand)
        
        # Update PyPSA loads
        self._update_pypsa_loads(demand)
        
        return demand
    
    def _calculate_traffic_light_power_realistic(self, traffic_lights: List[Dict]) -> float:
        """Calculate realistic traffic light power consumption"""
        from config import TRAFFIC_LIGHT_POWER
        
        total_power = 0
        for tl in traffic_lights:
            tl_id = tl['id']
            state = tl['state'].lower()
            
            # Count bulbs by state
            green_count = state.count('g')
            yellow_count = state.count('y')
            red_count = state.count('r')
            
            # Assume 70% LED, 30% halogen in LA
            led_factor = 0.7
            halogen_factor = 0.3
            
            # Calculate power for each color
            green_power = green_count * (
                TRAFFIC_LIGHT_POWER['green']['led'] * led_factor +
                TRAFFIC_LIGHT_POWER['green']['halogen'] * halogen_factor
            )
            
            yellow_power = yellow_count * (
                TRAFFIC_LIGHT_POWER['yellow']['led'] * led_factor +
                TRAFFIC_LIGHT_POWER['yellow']['halogen'] * halogen_factor
            )
            
            red_power = red_count * (
                TRAFFIC_LIGHT_POWER['red']['led'] * led_factor +
                TRAFFIC_LIGHT_POWER['red']['halogen'] * halogen_factor
            )
            
            # Apply grid state factor
            if self.grid_state == GridState.STRESSED:
                power_factor = 0.8  # Dim lights
            elif self.grid_state == GridState.CRITICAL:
                power_factor = 0.6  # Further dimming
            else:
                power_factor = 1.0
            
            tl_power = (green_power + yellow_power + red_power) * power_factor
            total_power += tl_power
            
            # Store for later reference
            self.traffic_lights[tl_id] = {
                'power': tl_power,
                'state': state,
                'dimming': power_factor
            }
        
        return total_power / 1000  # Convert to MW
    
    def _calculate_street_lighting_adaptive(self, vehicles: List[str]) -> float:
        """Calculate adaptive street lighting based on traffic density"""
        from config import STREET_LIGHT_POWER
        
        # Estimate road network length (simplified)
        network_length_km = 50  # Simplified for demo
        
        # Base power consumption
        if self.time_of_day < STREET_LIGHT_POWER['dawn'] or \
           self.time_of_day > STREET_LIGHT_POWER['dusk']:
            # Night time - lights on
            base_power = network_length_km * STREET_LIGHT_POWER['led_per_km']
            
            # Adaptive dimming based on traffic density
            traffic_density = len(vehicles) / network_length_km
            if traffic_density < 5:  # Low traffic
                dimming_factor = STREET_LIGHT_POWER['dimming_factor']
            elif traffic_density < 20:  # Medium traffic
                dimming_factor = 0.6
            else:  # High traffic
                dimming_factor = 1.0
        else:
            # Day time - minimal lighting
            base_power = network_length_km * 2  # Emergency/tunnel lighting only
            dimming_factor = 1.0
        
        # Apply grid state adjustments
        if self.grid_state == GridState.CRITICAL:
            dimming_factor *= 0.5
        elif self.grid_state == GridState.STRESSED:
            dimming_factor *= 0.7
        
        return base_power * dimming_factor / 1000  # Convert to MW
    
    def _calculate_ev_charging_smart(self, vehicles: List[str]) -> float:
        """Smart EV charging with V2G capabilities"""
        from config import EV_PERCENTAGE
        
        total_charging_power = 0
        
        # Identify EVs (simplified - in reality would track specific vehicles)
        num_evs = int(len(vehicles) * EV_PERCENTAGE)
        
        for station in self.charging_config:
            station_id = station['id']
            
            # Check vehicles near station
            vehicles_at_station = min(
                np.random.poisson(2),  # Random arrivals
                station['capacity']
            )
            
            if vehicles_at_station > 0:
                # Determine charging rate based on grid state
                if self.grid_state == GridState.NORMAL:
                    if station['type'] == 'level_3_dc':
                        power_per_vehicle = self.ev_params['level_3_dc']
                    else:
                        power_per_vehicle = self.ev_params['level_2_ac']
                elif self.grid_state == GridState.STRESSED:
                    # Limit to Level 2 charging
                    power_per_vehicle = min(
                        self.ev_params['level_2_ac'],
                        self.ev_params.get(station['type'], 20)
                    )
                else:  # CRITICAL
                    # Emergency charging only
                    power_per_vehicle = self.ev_params['level_1_ac']
                
                # Calculate station power
                station_power = vehicles_at_station * power_per_vehicle * \
                               self.ev_params['efficiency']
                
                total_charging_power += station_power
                
                # Store station status
                if station_id not in self.charging_stations:
                    self.charging_stations[station_id] = {}
                
                self.charging_stations[station_id].update({
                    'vehicles_charging': vehicles_at_station,
                    'power_consumption': station_power,
                    'charging_rate': power_per_vehicle
                })
        
        return total_charging_power / 1000  # Convert to MW
    
    def _update_pypsa_loads(self, demand: PowerDemand):
        """Update PyPSA network with current demand"""
        
        # Distribute demand across zones
        zone_factors = {
            "DTLA": 0.35,
            "Vernon": 0.25,
            "Harbor": 0.15,
            "LAX": 0.25
        }
        
        for zone, factor in zone_factors.items():
            load_name = f"Load_{zone}"
            if load_name in self.network.loads.index:
                # Base load + traffic-dependent load
                base_load = self.network.loads.at[load_name, 'p_set']
                traffic_load = demand.total * factor
                self.network.loads.at[load_name, 'p_set'] = base_load + traffic_load
    
    def run_power_flow_analysis(self) -> Dict:
        """Run power flow analysis and determine grid state"""
        
        try:
            # Set up snapshots
            self.network.set_snapshots([pd.Timestamp.now()])
            
            # Run optimal power flow
            status = self.network.lopf(
                solver_name='glpk',
                pyomo=False,
                keep_shadowprices=True
            )
            
            # Analyze results
            grid_metrics = self._analyze_grid_state()
            
            # Determine operational state
            self._update_grid_state(grid_metrics)
            
            # Generate response
            response = self._generate_traffic_response()
            
            return {
                'status': 'success',
                'grid_state': self.grid_state.value,
                'metrics': grid_metrics,
                'response': response,
                'congestion_level': grid_metrics['max_line_loading']
            }
            
        except Exception as e:
            self.logger.error(f"Power flow analysis failed: {e}")
            return {
                'status': 'error',
                'grid_state': GridState.NORMAL.value,
                'metrics': {},
                'response': None
            }
    
    def _analyze_grid_state(self) -> Dict:
        """Analyze current grid state from power flow results"""
        
        # Line loading analysis
        line_loading = {}
        max_loading = 0
        congested_lines = []
        
        for line in self.network.lines.index:
            flow = abs(self.network.lines_t.p0.at[self.network.snapshots[0], line])
            capacity = self.network.lines.at[line, 's_nom']
            
            if capacity > 0:
                loading = flow / capacity
                line_loading[line] = loading
                max_loading = max(max_loading, loading)
                
                if loading > 0.8:
                    congested_lines.append(line)
        
        # Generation analysis
        total_generation = self.network.generators_t.p.sum().sum()
        renewable_generation = sum(
            self.network.generators_t.p[gen].sum()
            for gen in self.network.generators.index
            if 'Solar' in gen or 'Wind' in gen
        )
        
        # Cost analysis
        marginal_cost = self.network.buses_t.marginal_price.mean().mean()
        
        return {
            'max_line_loading': max_loading,
            'congested_lines': congested_lines,
            'total_generation': total_generation,
            'renewable_percentage': renewable_generation / total_generation if total_generation > 0 else 0,
            'marginal_cost': marginal_cost,
            'line_loading': line_loading
        }
    
    def _update_grid_state(self, metrics: Dict):
        """Update grid state based on metrics"""
        max_loading = metrics['max_line_loading']
        
        if max_loading < 0.7:
            self.grid_state = GridState.NORMAL
        elif max_loading < 0.85:
            self.grid_state = GridState.STRESSED
        elif max_loading < 0.95:
            self.grid_state = GridState.CRITICAL
        else:
            self.grid_state = GridState.BLACKOUT
        
        # Store in history
        self.congestion_history.append({
            'timestamp': datetime.now(),
            'state': self.grid_state,
            'loading': max_loading
        })
    
    def _generate_traffic_response(self) -> TrafficResponse:
        """Generate traffic system response based on grid state"""
        
        if self.grid_state == GridState.NORMAL:
            return TrafficResponse(
                traffic_light_mode="normal",
                street_light_dimming=1.0,
                ev_charging_limit="unlimited",
                affected_intersections=[]
            )
        elif self.grid_state == GridState.STRESSED:
            return TrafficResponse(
                traffic_light_mode="eco",
                street_light_dimming=0.8,
                ev_charging_limit="level_2_max",
                affected_intersections=[]
            )
        elif self.grid_state == GridState.CRITICAL:
            # Identify critical intersections to modify
            critical_intersections = self._identify_critical_intersections()
            
            return TrafficResponse(
                traffic_light_mode="emergency",
                street_light_dimming=0.5,
                ev_charging_limit="emergency_only",
                affected_intersections=critical_intersections
            )
        else:  # BLACKOUT
            return TrafficResponse(
                traffic_light_mode="flashing_red",
                street_light_dimming=0.0,
                ev_charging_limit="none",
                affected_intersections=list(self.traffic_lights.keys())
            )
    
    def _identify_critical_intersections(self) -> List[str]:
        """Identify intersections to modify during critical conditions"""
        # Sort intersections by power consumption
        sorted_intersections = sorted(
            self.traffic_lights.items(),
            key=lambda x: x[1].get('power', 0),
            reverse=True
        )
        
        # Return top 20% highest consumers
        num_critical = max(1, len(sorted_intersections) // 5)
        return [tl_id for tl_id, _ in sorted_intersections[:num_critical]]
    
    def apply_demand_response(self, response: TrafficResponse):
        """Apply demand response measures to traffic system"""
        
        if response.traffic_light_mode == "eco":
            # Reduce phase durations to save power
            self._apply_eco_traffic_lights()
        elif response.traffic_light_mode == "emergency":
            # Switch to flashing yellow on minor roads
            self._apply_emergency_traffic_lights(response.affected_intersections)
        elif response.traffic_light_mode == "flashing_red":
            # All lights to flashing red (4-way stop)
            self._apply_blackout_traffic_lights()
        
        # Apply street light dimming
        self._apply_street_light_dimming(response.street_light_dimming)
        
        # Apply EV charging limits
        self._apply_ev_charging_limits(response.ev_charging_limit)
    
    def _apply_eco_traffic_lights(self):
        """Apply eco mode to traffic lights"""
        try:
            for tl_id in self.traffic_lights:
                # Get current program
                current_program = traci.trafficlight.getProgram(tl_id)
                
                # Reduce green phase durations by 20%
                phases = traci.trafficlight.getAllProgramLogics(tl_id)
                if phases:
                    logic = phases[0]
                    for phase in logic.getPhases():
                        phase.duration = int(phase.duration * 0.8)
                    
                    traci.trafficlight.setProgramLogic(tl_id, logic)
                    
        except Exception as e:
            self.logger.warning(f"Could not apply eco mode: {e}")
    
    def _apply_emergency_traffic_lights(self, affected_intersections: List[str]):
        """Apply emergency mode to critical intersections"""
        try:
            for tl_id in affected_intersections:
                # Set to flashing yellow
                state = traci.trafficlight.getRedYellowGreenState(tl_id)
                yellow_state = 'y' * len(state)
                traci.trafficlight.setRedYellowGreenState(tl_id, yellow_state)
                
        except Exception as e:
            self.logger.warning(f"Could not apply emergency mode: {e}")
    
    def _apply_blackout_traffic_lights(self):
        """Apply blackout mode - all lights flashing red"""
        try:
            for tl_id in self.traffic_lights:
                state = traci.trafficlight.getRedYellowGreenState(tl_id)
                red_state = 'r' * len(state)
                traci.trafficlight.setRedYellowGreenState(tl_id, red_state)
                
        except Exception as e:
            self.logger.warning(f"Could not apply blackout mode: {e}")
    
    def _apply_street_light_dimming(self, dimming_factor: float):
        """Apply street light dimming (simulated)"""
        # In a real system, this would interface with street light controllers
        self.logger.info(f"Street lights dimmed to {dimming_factor * 100}%")
    
    def _apply_ev_charging_limits(self, limit: str):
        """Apply EV charging limitations"""
        # In a real system, this would communicate with charging stations
        for station_id in self.charging_stations:
            if limit == "level_2_max":
                max_power = self.ev_params['level_2_ac']
            elif limit == "emergency_only":
                max_power = self.ev_params['level_1_ac']
            elif limit == "none":
                max_power = 0
            else:
                max_power = self.ev_params['level_3_dc']
            
            self.charging_stations[station_id]['max_power'] = max_power
    
    def get_visualization_data(self) -> Dict:
        """Get comprehensive data for visualization"""
        
        # Prepare charging station data
        charging_data = []
        for station_config in self.charging_config:
            station_id = station_config['id']
            if station_id in self.charging_stations:
                station_data = self.charging_stations[station_id]
                charging_data.append({
                    'id': station_id,
                    'position': [station_config['lat'], station_config['lon']],
                    'type': station_config['type'],
                    'vehicles_charging': station_data.get('vehicles_charging', 0),
                    'capacity': station_config['capacity'],
                    'power_consumption': station_data.get('power_consumption', 0),
                    'status': self._get_station_status(station_data)
                })
        
        # Prepare grid data
        grid_data = {
            'state': self.grid_state.value,
            'zones': self._get_zone_status(),
            'transmission_lines': self._get_transmission_status()
        }
        
        # Prepare metrics
        if self.current_demand:
            metrics = {
                'total_demand': self.current_demand.total,
                'traffic_lights': self.current_demand.traffic_lights,
                'street_lights': self.current_demand.street_lights,
                'ev_charging': self.current_demand.ev_charging,
                'renewable_percentage': self._get_renewable_percentage(),
                'grid_congestion': self._get_current_congestion()
            }
        else:
            metrics = {}
        
        return {
            'charging_stations': charging_data,
            'grid': grid_data,
            'metrics': metrics,
            'demand_history': self._get_demand_history_summary(),
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_station_status(self, station_data: Dict) -> str:
        """Determine charging station status"""
        if station_data.get('vehicles_charging', 0) == 0:
            return 'available'
        elif station_data.get('vehicles_charging', 0) >= station_data.get('capacity', 1) * 0.8:
            return 'busy'
        else:
            return 'normal'
    
    def _get_zone_status(self) -> List[Dict]:
        """Get status of each power zone"""
        zones = []
        for zone_name, zone_config in self.power_zones_config.items():
            load_bus = f"Load_{zone_name}"
            if load_bus in self.network.loads.index:
                load = self.network.loads.at[load_bus, 'p_set']
                capacity = zone_config['capacity_mw']
                utilization = load / capacity if capacity > 0 else 0
                
                zones.append({
                    'name': zone_name,
                    'bounds': zone_config['bounds'],
                    'load': load,
                    'capacity': capacity,
                    'utilization': utilization,
                    'status': 'normal' if utilization < 0.8 else 'stressed'
                })
        
        return zones
    
    def _get_transmission_status(self) -> List[Dict]:
        """Get status of transmission lines"""
        lines = []
        for line in self.network.lines.index:
            if hasattr(self.network.lines_t, 'p0'):
                flow = abs(self.network.lines_t.p0.at[self.network.snapshots[0], line])
                capacity = self.network.lines.at[line, 's_nom']
                loading = flow / capacity if capacity > 0 else 0
                
                lines.append({
                    'id': line,
                    'from': self.network.lines.at[line, 'bus0'],
                    'to': self.network.lines.at[line, 'bus1'],
                    'flow': flow,
                    'capacity': capacity,
                    'loading': loading,
                    'congested': loading > 0.8
                })
        
        return lines
    
    def _get_renewable_percentage(self) -> float:
        """Calculate current renewable generation percentage"""
        if not hasattr(self.network.generators_t, 'p'):
            return 0.0
        
        total_gen = self.network.generators_t.p.sum().sum()
        renewable_gen = sum(
            self.network.generators_t.p[gen].sum()
            for gen in self.network.generators.index
            if 'Solar' in gen or 'Wind' in gen
        )
        
        return (renewable_gen / total_gen * 100) if total_gen > 0 else 0.0
    
    def _get_current_congestion(self) -> float:
        """Get current grid congestion level"""
        if self.congestion_history:
            return self.congestion_history[-1].get('loading', 0.0) * 100
        return 0.0
    
    def _get_demand_history_summary(self) -> List[Dict]:
        """Get summarized demand history for visualization"""
        # Return last 50 data points
        summary = []
        for demand in self.demand_history[-50:]:
            summary.append({
                'timestamp': demand.timestamp.isoformat(),
                'total': demand.total,
                'traffic_lights': demand.traffic_lights,
                'street_lights': demand.street_lights,
                'ev_charging': demand.ev_charging
            })
        return summary