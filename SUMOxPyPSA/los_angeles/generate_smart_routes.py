#!/usr/bin/env python3
"""
Generate smart routes with EVs, time-based traffic, and charging behavior
"""

import os
import random
import xml.etree.ElementTree as ET
import gzip

def generate_smart_routes():
    """Generate routes with proper EV distribution and time-based traffic"""
    
    # Read compressed network file
    net_file = 'osm.net.xml.gz'
    
    if not os.path.exists(net_file):
        print(f"Error: Network file {net_file} not found!")
        return
    
    print("Reading network file...")
    
    # Extract edge IDs from compressed network
    edge_ids = []
    with gzip.open(net_file, 'rt', encoding='utf-8') as f:
        tree = ET.parse(f)
        root = tree.getroot()
        
        # Get all edges
        for edge in root.findall('edge'):
            edge_id = edge.get('id')
            # Skip internal edges
            if edge_id and not edge_id.startswith(':'):
                function = edge.get('function', '')
                if function != 'internal':
                    edge_ids.append(edge_id)
    
    if not edge_ids:
        print("Error: No edges found in network!")
        return
    
    print(f"Found {len(edge_ids)} edges in network")
    
    # Charging station locations (simplified - pick random edges)
    charging_edges = random.sample(edge_ids, min(10, len(edge_ids)//20))
    
    root = ET.Element('routes')
    
    # Vehicle types
    vtype_normal = ET.SubElement(root, 'vType')
    vtype_normal.set('id', 'normal_car')
    vtype_normal.set('vClass', 'passenger')
    vtype_normal.set('maxSpeed', '16.67')  # 60 km/h
    vtype_normal.set('accel', '3.0')
    vtype_normal.set('decel', '4.5')
    vtype_normal.set('length', '5')
    vtype_normal.set('color', '0.2,0.5,1')  # Blue
    
    vtype_ev = ET.SubElement(root, 'vType')
    vtype_ev.set('id', 'electric_car')
    vtype_ev.set('vClass', 'passenger')
    vtype_ev.set('maxSpeed', '16.67')
    vtype_ev.set('accel', '4.0')  # EVs accelerate faster
    vtype_ev.set('decel', '4.5')
    vtype_ev.set('length', '5')
    vtype_ev.set('color', '0,1,0')  # Green
    
    vehicle_id = 0
    
    # Generate vehicles for a full day simulation
    print("Generating vehicles...")
    
    for hour in range(24):
        current_time = hour * 3600
        
        # Determine number of vehicles based on time
        if 6 <= hour < 9:  # Morning rush
            vehicles_this_hour = random.randint(100, 150)
            print(f"Hour {hour}: Morning rush - {vehicles_this_hour} vehicles")
        elif 17 <= hour < 20:  # Evening rush
            vehicles_this_hour = random.randint(100, 150)
            print(f"Hour {hour}: Evening rush - {vehicles_this_hour} vehicles")
        elif 9 <= hour < 17:  # Normal day
            vehicles_this_hour = random.randint(50, 100)
            print(f"Hour {hour}: Day time - {vehicles_this_hour} vehicles")
        else:  # Night
            vehicles_this_hour = random.randint(1, 50)
            print(f"Hour {hour}: Night time - {vehicles_this_hour} vehicles")
        
        # Generate vehicles for this hour
        for _ in range(vehicles_this_hour):
            # 30% EVs
            is_ev = random.random() < 0.3
            
            # Choose random edges for route
            from_edge = random.choice(edge_ids)
            to_edge = random.choice(edge_ids)
            
            # Make sure they're different
            attempts = 0
            while to_edge == from_edge and attempts < 10:
                to_edge = random.choice(edge_ids)
                attempts += 1
            
            # Create vehicle
            vehicle = ET.SubElement(root, 'vehicle')
            vehicle.set('id', f'veh_{vehicle_id}')
            vehicle.set('type', 'electric_car' if is_ev else 'normal_car')
            vehicle.set('depart', str(current_time + random.randint(0, 3600)))
            
            # Create route
            route = ET.SubElement(vehicle, 'route')
            
            # For EVs, sometimes include charging station
            if is_ev and random.random() < 0.3 and charging_edges:
                # Route via charging station
                charging_edge = random.choice(charging_edges)
                route.set('edges', f'{from_edge} {charging_edge} {to_edge}')
            else:
                # Direct route
                route.set('edges', f'{from_edge} {to_edge}')
            
            vehicle_id += 1
    
    # Write file
    output_file = 'osm.passenger.trips.xml'
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    
    print(f"\nSuccessfully generated {output_file}")
    print(f"Total vehicles: {vehicle_id}")
    print(f"- {int(vehicle_id * 0.3)} EVs (30%)")
    print(f"- {int(vehicle_id * 0.7)} normal cars (70%)")
    print(f"- {len(charging_edges)} charging station locations")

if __name__ == "__main__":
    generate_smart_routes()