import os

# SUMO Configuration
SUMO_PATH = "C:\\Program Files (x86)\\Eclipse\\Sumo"  # Windows path

# Web Server Configuration
HOST = "0.0.0.0"  # Allow external connections
PORT = 8080       # Web server port

# Simulation Configuration
SIMULATION_SPEED = 0.025  # Reduced for smoother movement
UPDATE_FREQUENCY = 2     # Update every 2 frames for smoother movement

# City paths are relative to the config file location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NYC_PATH = os.path.join(BASE_DIR, "new_york")
MIAMI_PATH = os.path.join(BASE_DIR, "miami")
LA_PATH = os.path.join(BASE_DIR, "los_angeles")

# City configurations
CITY_CONFIGS = {
    "newyork": {
        "cfg_file": os.path.join(NYC_PATH, "osm.sumocfg"),
        "name": "New York, USA",
        "working_dir": NYC_PATH
    },
    "miami": {
        "cfg_file": os.path.join(MIAMI_PATH, "osm.sumocfg"),
        "name": "Miami, USA",
        "working_dir": MIAMI_PATH
    },
    "losangeles": {
        "cfg_file": os.path.join(LA_PATH, "osm.sumocfg"),
        "name": "Los Angeles, USA",
        "working_dir": LA_PATH
    }
}

# PyPSA Integration Configuration
PYPSA_UPDATE_FREQUENCY = 1200  # Run PyPSA optimization every 600 timesteps

# Electric Vehicle Configuration
EV_PERCENTAGE = 0.3  # 30% of vehicles are electric

# Power Consumption Parameters (in kW)
TRAFFIC_LIGHT_POWER = {
    "green": 0.5,
    "yellow": 0.4,
    "red": 0.3
}

STREET_LIGHT_POWER = {
    "base": 0.15,  # kW per segment
    "night": 50,    # kW per zone at night
    "day": 10       # kW per zone during day
}

EV_CHARGING_POWER = {
    "fast": 150,    # kW
    "medium": 50,   # kW  
    "slow": 7.4     # kW
}

# CHARGING STATIONS - PLACED EXACTLY WHERE YOUR TRAFFIC IS!
# CHARGING STATIONS - EXACTLY WHERE YOUR VEHICLES ARE!
CHARGING_STATIONS = {
    "newyork": [
        # WEST SIDE / JERSEY CITY AREA - YOUR ACTUAL VEHICLE CLUSTER
        {"id": "CS_West_1", "lat": 40.735, "lon": -74.030, "capacity": 10},
        {"id": "CS_West_2", "lat": 40.740, "lon": -74.028, "capacity": 8},
        {"id": "CS_West_3", "lat": 40.745, "lon": -74.025, "capacity": 8},
        {"id": "CS_West_4", "lat": 40.738, "lon": -74.032, "capacity": 10},
        {"id": "CS_West_5", "lat": 40.742, "lon": -74.029, "capacity": 6},
        {"id": "CS_West_6", "lat": 40.737, "lon": -74.027, "capacity": 8}
    ],
    "miami": [
        # KEEP YOUR WORKING MIAMI STATIONS AS THEY ARE
        {"id": "CS_Downtown", "lat": 25.774, "lon": -80.193, "capacity": 6},
        {"id": "CS_Beach", "lat": 25.790, "lon": -80.130, "capacity": 8},
        {"id": "CS_Airport", "lat": 25.795, "lon": -80.287, "capacity": 10},
        {"id": "CS_Brickell", "lat": 25.761, "lon": -80.195, "capacity": 5}
    ],
    "losangeles": [
        # VERNON/DOWNTOWN INDUSTRIAL - YOUR ACTUAL CLUSTER
        {"id": "CS_Vernon_1", "lat": 34.020, "lon": -118.220, "capacity": 10},
        {"id": "CS_Vernon_2", "lat": 34.025, "lon": -118.215, "capacity": 8},
        {"id": "CS_Vernon_3", "lat": 34.018, "lon": -118.225, "capacity": 8},
        {"id": "CS_Vernon_4", "lat": 34.023, "lon": -118.218, "capacity": 10},
        {"id": "CS_Vernon_5", "lat": 34.022, "lon": -118.222, "capacity": 6},
        {"id": "CS_Vernon_6", "lat": 34.019, "lon": -118.217, "capacity": 8}
    ]
}

# Power Grid Zones - matching where traffic actually is
POWER_ZONES = {
    "newyork": {
        "Tribeca": {"bounds": [[40.715, -74.015], [40.730, -74.000]], "bus": "Tribeca"},
        "Hudson": {"bounds": [[40.720, -74.015], [40.730, -74.005]], "bus": "Hudson"},
        "Greenwich": {"bounds": [[40.715, -74.010], [40.725, -74.000]], "bus": "Greenwich"},
        "Canal": {"bounds": [[40.715, -74.008], [40.723, -74.002]], "bus": "Canal"}
    },
    "miami": {
        "Wynwood": {"bounds": [[25.795, -80.205], [25.815, -80.185]], "bus": "Wynwood"},
        "Design": {"bounds": [[25.805, -80.195], [25.815, -80.185]], "bus": "Design"},
        "Midtown": {"bounds": [[25.800, -80.200], [25.810, -80.188]], "bus": "Midtown"}
    },
    "losangeles": {
        "Downtown": {"bounds": [[34.045, -118.255], [34.055, -118.245]], "bus": "Downtown"},
        "Bunker": {"bounds": [[34.048, -118.253], [34.053, -118.247]], "bus": "Bunker"},
        "Historic": {"bounds": [[34.045, -118.248], [34.050, -118.243]], "bus": "Historic"},
        "Financial": {"bounds": [[34.050, -118.254], [34.055, -118.248]], "bus": "Financial"}
    }
}

# Grid operational parameters
GRID_CONGESTION_THRESHOLD = 0.8  # 80% loading triggers demand response
OUTAGE_THRESHOLD = 0.95  # 95% loading risks outage

# Demand Response Settings
DEMAND_RESPONSE = {
    "lighting_reduction": 0.7,  # Reduce to 70% during high demand
    "ev_charging_limit": "medium",  # Limit to medium speed during congestion
    "critical_threshold": 0.9  # Critical congestion level
}

# Default city
DEFAULT_CITY = "losangeles"