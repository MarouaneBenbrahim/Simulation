#!/usr/bin/env python3
"""
Traffic-Power Integration Module
Connects SUMO traffic simulation with PyPSA power network
"""

import threading
import time
import json
from datetime import datetime
import numpy as np

class TrafficPowerCoupler:
    def __init__(self, power_network):
        """Initialize the traffic-power coupling system"""
        self.power_network = power_network
        
        # Traffic data from SUMO
        self.vehicle_count = 0
        self.traffic_light_states = {}
        self.vehicle_positions = []
        self.traffic_density_by_area = {
            'Manhattan': 0,
            'Brooklyn': 0,
            'Queens': 0,
            'Bronx': 0
        }
        
        # Power impact factors
        self.traffic_light_power = 0.0005  # MW per traffic light
        self.street_light_dimming_factor = 1.0  # Adaptive street lighting
        self.ev_charging_probability = 0.05  # 5% of vehicles are charging EVs
        
        # Metrics for visualization
        self.metrics_history = []
        self.power_events = []
        
    def update_from_sumo(self, sumo_data):
        """Update coupling based on SUMO simulation data"""
        # Extract data from SUMO
        vehicles = sumo_data.get('vehicles', [])
        traffic_lights = sumo_data.get('traffic_lights', [])
        
        self.vehicle_count = len(vehicles)
        self.vehicle_positions = vehicles
        
        # Update traffic light states
        self.traffic_light_states = {}
        for tl in traffic_lights:
            self.traffic_light_states[tl['id']] = tl['state']
        
        # Calculate traffic density by area
        self._calculate_traffic_density()
        
        # Update power network loads
        self._update_power_loads()
        
        # Check for power events
        self._check_power_events()
        
        return self.get_current_status()
    
    def _calculate_traffic_density(self):
        """Calculate traffic density for each borough"""
        # Reset densities
        for area in self.traffic_density_by_area:
            self.traffic_density_by_area[area] = 0
        
        # Count vehicles in each area based on coordinates
        for vehicle in self.vehicle_positions:
            lat, lon = vehicle.get('y', 0), vehicle.get('x', 0)
            
            # Simplified borough boundaries
            if 40.7 < lat < 40.85 and -74.02 < lon < -73.93:
                self.traffic_density_by_area['Manhattan'] += 1
            elif 40.57 < lat < 40.7 and -74.04 < lon < -73.83:
                self.traffic_density_by_area['Brooklyn'] += 1
            elif 40.7 < lat < 40.8 and -73.93 < lon < -73.7:
                self.traffic_density_by_area['Queens'] += 1
            elif lat > 40.85:
                self.traffic_density_by_area['Bronx'] += 1
    
    def _update_power_loads(self):
        """Update power network loads based on traffic conditions"""
        # Update traffic light loads based on states
        total_tl_power = len(self.traffic_light_states) * self.traffic_light_power
        
        # More complex state = more power (controllers working harder)
        yellow_count = sum(1 for state in self.traffic_light_states.values() if 'y' in state.lower())
        red_count = sum(1 for state in self.traffic_light_states.values() if 'r' in state.lower())
        
        # Power factor increases with more yellow/red (active control)
        control_factor = 1.0 + (yellow_count + red_count) / max(len(self.traffic_light_states), 1) * 0.2
        
        # Update traffic light loads by area
        if 'TL_Manhattan' in self.power_network.traffic_light_loads:
            density_factor = min(2.0, 1.0 + self.traffic_density_by_area['Manhattan'] / 1000)
            self.power_network.traffic_light_loads['TL_Manhattan']['current_mw'] = \
                self.power_network.traffic_light_loads['TL_Manhattan']['base_mw'] * control_factor * density_factor
        
        if 'TL_Brooklyn' in self.power_network.traffic_light_loads:
            density_factor = min(2.0, 1.0 + self.traffic_density_by_area['Brooklyn'] / 1000)
            self.power_network.traffic_light_loads['TL_Brooklyn']['current_mw'] = \
                self.power_network.traffic_light_loads['TL_Brooklyn']['base_mw'] * control_factor * density_factor
        
        if 'TL_Queens' in self.power_network.traffic_light_loads:
            density_factor = min(2.0, 1.0 + self.traffic_density_by_area['Queens'] / 1000)
            self.power_network.traffic_light_loads['TL_Queens']['current_mw'] = \
                self.power_network.traffic_light_loads['TL_Queens']['base_mw'] * control_factor * density_factor
        
        # Update EV charging loads based on vehicle count and density
        self._update_ev_charging()
        
        # Update street lighting (adaptive based on traffic)
        self._update_street_lighting()
        
        # Run power flow simulation
        self.power_network.simulate_power_flow()
    
    def _update_ev_charging(self):
        """Update EV charging loads based on traffic patterns"""
        # Estimate EVs charging based on stopped vehicles and density
        base_ev_count = self.vehicle_count * 0.15  # 15% of vehicles are EVs
        
        # Calculate charging demand by area
        manhattan_evs = self.traffic_density_by_area['Manhattan'] * 0.15
        brooklyn_evs = self.traffic_density_by_area['Brooklyn'] * 0.15
        queens_evs = self.traffic_density_by_area['Queens'] * 0.15
        
        # Charging probability increases in high-density areas (more likely to find chargers)
        manhattan_charging = manhattan_evs * 0.1 * 0.05  # 10% charging, 50kW average
        brooklyn_charging = brooklyn_evs * 0.08 * 0.05
        queens_charging = queens_evs * 0.06 * 0.05
        
        # Update EV loads
        if 'EV_Manhattan' in self.power_network.ev_charging_loads:
            self.power_network.ev_charging_loads['EV_Manhattan']['current_mw'] = min(
                manhattan_charging,
                self.power_network.ev_charging_loads['EV_Manhattan']['capacity_mw']
            )
        
        if 'EV_Brooklyn' in self.power_network.ev_charging_loads:
            self.power_network.ev_charging_loads['EV_Brooklyn']['current_mw'] = min(
                brooklyn_charging,
                self.power_network.ev_charging_loads['EV_Brooklyn']['capacity_mw']
            )
        
        if 'EV_Queens' in self.power_network.ev_charging_loads:
            self.power_network.ev_charging_loads['EV_Queens']['current_mw'] = min(
                queens_charging,
                self.power_network.ev_charging_loads['EV_Queens']['capacity_mw']
            )
    
    def _update_street_lighting(self):
        """Update street lighting based on traffic density (smart lighting)"""
        hour = self.power_network.current_hour
        
        # Base lighting schedule
        if hour < 6 or hour > 18:  # Night time
            base_factor = 1.0
        else:  # Day time
            base_factor = 0.0
        
        # Adaptive lighting based on traffic
        for area in ['Manhattan', 'Brooklyn', 'Queens']:
            sl_key = f'SL_{area}'
            if sl_key in self.power_network.street_light_loads:
                # More traffic = brighter lights (safety)
                traffic_factor = min(1.5, 1.0 + self.traffic_density_by_area[area] / 2000)
                
                self.power_network.street_light_loads[sl_key]['current_mw'] = \
                    self.power_network.street_light_loads[sl_key]['base_mw'] * base_factor * traffic_factor
    
    def _check_power_events(self):
        """Check for power events that affect traffic"""
        events = []
        
        # Check for overload conditions
        for line_name, line in self.power_network.lines.items():
            utilization = (line['current_flow'] / line['capacity_mw']) * 100 if line['capacity_mw'] > 0 else 0
            
            if utilization > 90:
                events.append({
                    'type': 'line_overload',
                    'severity': 'warning',
                    'line': line_name,
                    'utilization': utilization,
                    'message': f"Line {line_name} at {utilization:.1f}% capacity"
                })
            
            if utilization > 100:
                events.append({
                    'type': 'line_trip',
                    'severity': 'critical',
                    'line': line_name,
                    'utilization': utilization,
                    'message': f"Line {line_name} tripped! Traffic lights may fail.",
                    'traffic_impact': self._calculate_outage_impact(line_name)
                })
        
        # Check generation adequacy
        balance = self.power_network.total_generation - self.power_network.total_load
        if balance < 0:
            events.append({
                'type': 'generation_shortage',
                'severity': 'critical',
                'shortage_mw': abs(balance),
                'message': f"Generation shortage: {abs(balance):.1f} MW",
                'action': 'load_shedding'
            })
        
        self.power_events = events
        return events
    
    def _calculate_outage_impact(self, line_name):
        """Calculate traffic impact from power line outage"""
        impact = {
            'affected_traffic_lights': 0,
            'affected_areas': [],
            'estimated_delay_minutes': 0
        }
        
        # Map lines to affected areas
        line_area_map = {
            'DL_Manhattan_Traffic': {'area': 'Manhattan', 'lights': 500, 'delay': 15},
            'DL_Brooklyn_Traffic': {'area': 'Brooklyn', 'lights': 350, 'delay': 10},
            'DL_Queens_Traffic': {'area': 'Queens', 'lights': 300, 'delay': 8}
        }
        
        if line_name in line_area_map:
            impact['affected_areas'].append(line_area_map[line_name]['area'])
            impact['affected_traffic_lights'] = line_area_map[line_name]['lights']
            impact['estimated_delay_minutes'] = line_area_map[line_name]['delay']
        
        return impact
    
    def simulate_power_outage(self, area):
        """Simulate a power outage in a specific area"""
        print(f"⚠️ Simulating power outage in {area}...")
        
        # Set loads to zero in affected area
        if area == 'Manhattan':
            self.power_network.traffic_light_loads['TL_Manhattan']['current_mw'] = 0
            self.power_network.street_light_loads['SL_Manhattan']['current_mw'] = 0
            return {'affected_lights': 500, 'message': 'Manhattan traffic lights offline'}
        
        return {'affected_lights': 0, 'message': 'No impact'}
    
    def get_current_status(self):
        """Get current status of the coupled system"""
        power_status = self.power_network.get_status()
        
        status = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'traffic': {
                'vehicle_count': self.vehicle_count,
                'traffic_lights': len(self.traffic_light_states),
                'density_by_area': self.traffic_density_by_area
            },
            'power': {
                'total_generation_mw': power_status['total_generation_mw'],
                'total_load_mw': power_status['total_load_mw'],
                'traffic_infrastructure_mw': power_status['traffic_light_load_mw'] + power_status['street_light_load_mw'],
                'ev_charging_mw': power_status['ev_charging_load_mw'],
                'line_utilization': power_status['line_utilization']
            },
            'coupling_metrics': {
                'traffic_power_ratio': self.vehicle_count / max(power_status['total_load_mw'], 1),
                'ev_penetration': (power_status['ev_charging_load_mw'] / max(self.vehicle_count * 0.001, 1)) if self.vehicle_count > 0 else 0,
                'infrastructure_efficiency': (power_status['traffic_light_load_mw'] / max(len(self.traffic_light_states) * 0.001, 1)) if len(self.traffic_light_states) > 0 else 0
            },
            'events': self.power_events
        }
        
        # Store in history
        self.metrics_history.append(status)
        if len(self.metrics_history) > 100:  # Keep last 100 records
            self.metrics_history.pop(0)
        
        return status
    
    def get_optimization_recommendations(self):
        """Get recommendations for optimizing the coupled system"""
        recommendations = []
        status = self.get_current_status()
        
        # Check EV charging optimization
        if status['power']['ev_charging_mw'] > status['power']['total_generation_mw'] * 0.1:
            recommendations.append({
                'type': 'ev_charging',
                'priority': 'medium',
                'message': 'Consider time-of-use EV charging to reduce peak demand',
                'potential_savings_mw': status['power']['ev_charging_mw'] * 0.3
            })
        
        # Check traffic light efficiency
        if status['coupling_metrics']['infrastructure_efficiency'] > 1.5:
            recommendations.append({
                'type': 'traffic_lights',
                'priority': 'low',
                'message': 'Traffic light power consumption higher than normal',
                'action': 'Check for malfunctioning controllers'
            })
        
        # Check line utilization
        for line, util in status['power']['line_utilization'].items():
            if util > 80:
                recommendations.append({
                    'type': 'grid_congestion',
                    'priority': 'high',
                    'message': f'Line {line} approaching capacity ({util:.1f}%)',
                    'action': 'Consider load redistribution or demand response'
                })
        
        return recommendations

def test_integration():
    """Test the traffic-power integration"""
    print("=" * 60)
    print("Testing Traffic-Power Integration")
    print("=" * 60)
    
    # Import the power network
    from pypsa_network_builder import NYCPowerNetworkSimple
    
    # Create power network
    power_network = NYCPowerNetworkSimple()
    power_network.build_network()
    
    # Create coupler
    coupler = TrafficPowerCoupler(power_network)
    
    # Simulate SUMO data
    test_sumo_data = {
        'vehicles': [
            {'id': f'veh_{i}', 'x': -73.98 + i*0.001, 'y': 40.75 + i*0.001, 'angle': 0}
            for i in range(1000)
        ],
        'traffic_lights': [
            {'id': f'tl_{i}', 'x': -73.98, 'y': 40.75, 'state': 'GGrr' if i % 2 == 0 else 'rrGG'}
            for i in range(100)
        ]
    }
    
    # Update coupling
    status = coupler.update_from_sumo(test_sumo_data)
    
    print("\nIntegration Status:")
    print(f"Vehicles: {status['traffic']['vehicle_count']}")
    print(f"Traffic Lights: {status['traffic']['traffic_lights']}")
    print(f"Total Power Load: {status['power']['total_load_mw']} MW")
    print(f"Traffic Infrastructure: {status['power']['traffic_infrastructure_mw']} MW")
    print(f"EV Charging: {status['power']['ev_charging_mw']} MW")
    
    # Get recommendations
    recommendations = coupler.get_optimization_recommendations()
    if recommendations:
        print("\nOptimization Recommendations:")
        for rec in recommendations:
            print(f"- [{rec['priority']}] {rec['message']}")
    
    print("\n✅ Traffic-Power Integration ready!")
    return coupler

if __name__ == "__main__":
    test_integration()