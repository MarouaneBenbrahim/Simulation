#!/usr/bin/env python3
"""
Create simple working routes that will definitely spawn vehicles
"""

import random

def create_simple_routes():
    # These are common edges in LA network that should exist
    edges = [
        "134461170", "134461171", "134461172", "134461173",
        "31784377", "31784378", "31784379", "31784380",
        "122633611", "122633612", "122633613", "122633614",
        "60720277", "60720278", "60720279", "60720280",
        "23615145", "23615146", "23615147", "23615148",
        "404666310", "404666311", "404666312", "404666313"
    ]
    
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n'
    
    # Vehicle types
    xml_content += '    <vType id="normal_car" vClass="passenger" color="0,0,1" length="5" maxSpeed="16.67"/>\n'
    xml_content += '    <vType id="electric_car" vClass="passenger" color="0,1,0" length="5" maxSpeed="16.67"/>\n\n'
    
    # Generate 500 vehicles over first hour
    for i in range(500):
        is_ev = i % 3 == 0  # Every 3rd vehicle is EV
        veh_type = "electric_car" if is_ev else "normal_car"
        depart_time = i * 2  # One vehicle every 2 seconds
        
        # Pick random edges
        from_edge = random.choice(edges)
        to_edge = random.choice(edges)
        while to_edge == from_edge:
            to_edge = random.choice(edges)
        
        xml_content += f'    <vehicle id="veh_{i}" type="{veh_type}" depart="{depart_time}">\n'
        xml_content += f'        <route edges="{from_edge} {to_edge}"/>\n'
        xml_content += f'    </vehicle>\n'
    
    xml_content += '</routes>\n'
    
    # Write file
    with open('osm.passenger.trips.xml', 'w') as f:
        f.write(xml_content)
    
    print("Created osm.passenger.trips.xml with 500 vehicles")
    print("- 167 EVs (green)")
    print("- 333 normal cars (blue)")

if __name__ == "__main__":
    create_simple_routes()