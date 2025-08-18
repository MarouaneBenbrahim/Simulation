#!/usr/bin/env python3
"""
Fix route files by regenerating them with correct edge IDs from current network
"""

import os
import sys
import subprocess
import random
from config import SUMO_PATH

# Path to SUMO tools
SUMO_TOOLS = os.path.join(SUMO_PATH, "tools")
sys.path.append(SUMO_TOOLS)

def generate_random_trips(city_dir, city_name):
    """Generate random trips for a city"""
    
    net_file = os.path.join(city_dir, "osm.net.xml.gz")
    output_trips = os.path.join(city_dir, "osm.passenger.trips.xml")
    
    if not os.path.exists(net_file):
        print(f"Network file not found: {net_file}")
        return False
    
    print(f"\nGenerating routes for {city_name}...")
    
    # Use randomTrips.py from SUMO tools
    random_trips_script = os.path.join(SUMO_TOOLS, "randomTrips.py")
    
    if not os.path.exists(random_trips_script):
        print(f"randomTrips.py not found at {random_trips_script}")
        return False
    
    # Generate trips with proper parameters
    cmd = [
        "python", random_trips_script,
        "-n", net_file,  # Network file
        "-o", output_trips,  # Output file
        "-b", "0",  # Begin time
        "-e", "3600",  # End time (1 hour)
        "--fringe-factor", "10",  # Prefer trips from/to edges at fringe
        "-p", "2.0",  # Period between vehicles (2 seconds)
        "--trip-attributes", 'departLane="best" departSpeed="max" departPos="random"',
        "--prefix", "flow",  # Vehicle ID prefix
        "--validate",  # Validate edges exist
        "-L"  # Use lanes instead of edges (more accurate)
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=city_dir)
        
        if result.returncode == 0:
            print(f"✅ Successfully generated routes for {city_name}")
            
            # Count the trips generated
            with open(output_trips, 'r') as f:
                content = f.read()
                trip_count = content.count('<trip ')
                print(f"   Generated {trip_count} trips")
            
            return True
        else:
            print(f"❌ Error generating routes:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def generate_simple_trips(city_dir, city_name):
    """Generate simple valid trips using Python (fallback method)"""
    
    import gzip
    import xml.etree.ElementTree as ET
    
    net_file = os.path.join(city_dir, "osm.net.xml.gz")
    output_trips = os.path.join(city_dir, "osm.passenger.trips.xml")
    
    print(f"\nGenerating simple routes for {city_name} (fallback method)...")
    
    # Parse network to get valid edges
    valid_edges = []
    
    with gzip.open(net_file, 'rt') as f:
        tree = ET.parse(f)
        root = tree.getroot()
        
        for edge in root.findall('edge'):
            edge_id = edge.get('id')
            # Skip internal edges and pedestrian edges
            if not edge_id.startswith(':') and edge.get('function') != 'internal':
                # Check if edge allows cars
                allow = edge.get('allow', '')
                disallow = edge.get('disallow', '')
                
                if 'passenger' in allow or (not disallow and not allow):
                    valid_edges.append(edge_id)
    
    print(f"Found {len(valid_edges)} valid edges")
    
    if len(valid_edges) < 2:
        print("❌ Not enough valid edges found")
        return False
    
    # Generate trips
    trips_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    trips_xml += '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n'
    
    # Generate 50 random trips
    for i in range(50):
        depart_time = i * 10  # Every 10 seconds
        from_edge = random.choice(valid_edges)
        to_edge = random.choice(valid_edges)
        
        # Make sure from and to are different
        while to_edge == from_edge:
            to_edge = random.choice(valid_edges)
        
        trips_xml += f'    <trip id="vehicle_{i}" depart="{depart_time}" from="{from_edge}" to="{to_edge}" departLane="best" departSpeed="max"/>\n'
    
    trips_xml += '</routes>\n'
    
    # Write file
    with open(output_trips, 'w') as f:
        f.write(trips_xml)
    
    print(f"✅ Generated 50 simple trips for {city_name}")
    return True

def main():
    """Fix routes for all cities"""
    
    cities = {
        "new_york": "New York",
        "miami": "Miami", 
        "los_angeles": "Los Angeles"
    }
    
    print("=" * 60)
    print("FIXING ROUTE FILES FOR ALL CITIES")
    print("=" * 60)
    
    for city_dir, city_name in cities.items():
        if not os.path.exists(city_dir):
            print(f"⚠️  Directory {city_dir} not found, skipping...")
            continue
        
        # Try the proper method first
        success = generate_random_trips(city_dir, city_name)
        
        # If that fails, use fallback
        if not success:
            print(f"Trying fallback method for {city_name}...")
            success = generate_simple_trips(city_dir, city_name)
        
        if success:
            print(f"✅ {city_name} routes fixed!")
        else:
            print(f"❌ Failed to fix {city_name} routes")
    
    print("\n" + "=" * 60)
    print("Route generation complete!")
    print("Restart your simulation to use the new routes.")
    print("=" * 60)

if __name__ == "__main__":
    main()