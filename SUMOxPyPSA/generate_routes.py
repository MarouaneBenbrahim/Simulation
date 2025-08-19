import os
import random
import xml.etree.ElementTree as ET

def generate_routes(net_file, route_file, num_vehicles=500):
    """Generate random routes for vehicles"""
    
    # Parse network to get edges
    import sumolib
    net = sumolib.net.readNet(net_file)
    edges = net.getEdges()
    
    # Filter out internal edges
    normal_edges = [e for e in edges if not e.isSpecial()]
    edge_ids = [e.getID() for e in normal_edges]
    
    # Create routes XML
    root = ET.Element('routes')
    
    # Add vehicle type definitions
    vtype_normal = ET.SubElement(root, 'vType')
    vtype_normal.set('id', 'normal_car')
    vtype_normal.set('vClass', 'passenger')
    vtype_normal.set('maxSpeed', '30')
    vtype_normal.set('accel', '2.6')
    vtype_normal.set('decel', '4.5')
    vtype_normal.set('length', '5')
    
    vtype_ev = ET.SubElement(root, 'vType')
    vtype_ev.set('id', 'electric_car')
    vtype_ev.set('vClass', 'passenger')
    vtype_ev.set('maxSpeed', '30')
    vtype_ev.set('accel', '3.0')
    vtype_ev.set('decel', '4.5')
    vtype_ev.set('length', '5')
    vtype_ev.set('color', '0,1,0')  # Green for EVs
    
    # Generate vehicles with random routes
    for i in range(num_vehicles):
        # Random start and end edges
        from_edge = random.choice(edge_ids)
        to_edge = random.choice(edge_ids)
        
        # Make sure they're different
        while to_edge == from_edge:
            to_edge = random.choice(edge_ids)
        
        # Create vehicle
        vehicle = ET.SubElement(root, 'vehicle')
        vehicle.set('id', f'veh_{i}')
        vehicle.set('type', 'electric_car' if random.random() < 0.3 else 'normal_car')
        vehicle.set('depart', str(random.uniform(0, 300)))  # Depart in first 5 minutes
        
        # Create route
        route = ET.SubElement(vehicle, 'route')
        route.set('edges', f'{from_edge} {to_edge}')
    
    # Write to file
    tree = ET.ElementTree(root)
    tree.write(route_file, encoding='utf-8', xml_declaration=True)
    print(f"Generated {num_vehicles} vehicles in {route_file}")

# Run if called directly
if __name__ == "__main__":
    generate_routes('osm.net.xml', 'osm.passenger.trips.xml', 500)