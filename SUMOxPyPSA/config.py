# config.py - Updated for LA focus with realistic power grid
import os

# SUMO Configuration
SUMO_PATH = "C:\\Program Files (x86)\\Eclipse\\Sumo"

# Web Server Configuration
HOST = "0.0.0.0"
PORT = 8080

# Simulation Configuration
SIMULATION_SPEED = 0.025
UPDATE_FREQUENCY = 2

# Focus on Los Angeles only
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LA_PATH = os.path.join(BASE_DIR, "los_angeles")

# Single city configuration
CITY_CONFIGS = {
    "losangeles": {
        "cfg_file": os.path.join(LA_PATH, "osm.sumocfg"),
        "name": "Los Angeles, USA",
        "working_dir": LA_PATH
    }
}

# PyPSA Integration Configuration
PYPSA_UPDATE_FREQUENCY = 100  # More frequent updates for better interaction

# Electric Vehicle Configuration
EV_PERCENTAGE = 0.3  # 30% of vehicles are electric

# Realistic Power Consumption Parameters (in kW)
TRAFFIC_LIGHT_POWER = {
    "green": {
        "led": 0.12,      # Modern LED traffic light
        "halogen": 0.35,  # Older halogen lights
        "consumption_factor": 1.0
    },
    "yellow": {
        "led": 0.10,
        "halogen": 0.30,
        "consumption_factor": 0.85
    },
    "red": {
        "led": 0.08,
        "halogen": 0.25,
        "consumption_factor": 0.7
    }
}

# Street lighting with time-of-day variations
STREET_LIGHT_POWER = {
    "led_per_km": 15,      # kW per km for LED street lights
    "hps_per_km": 40,      # kW per km for HPS lights
    "dawn": 6,             # 6 AM
    "dusk": 18,            # 6 PM
    "dimming_factor": 0.3  # 30% power during low traffic
}

# EV Charging with realistic power levels
EV_CHARGING_POWER = {
    "level_3_dc": 350,     # Ultra-fast DC charging (kW)
    "level_2_ac": 19.2,    # Level 2 AC charging (kW)
    "level_1_ac": 1.4,     # Level 1 AC charging (kW)
    "efficiency": 0.9      # Charging efficiency
}

# LA Power Grid Zones (simplified but realistic)
POWER_ZONES = {
    "losangeles": {
        "DTLA": {
            "bounds": [[34.040, -118.260], [34.060, -118.230]],
            "bus": "DTLA_138kV",
            "substation": "Main Street",
            "capacity_mw": 500
        },
        "Vernon": {
            "bounds": [[34.000, -118.230], [34.030, -118.200]],
            "bus": "Vernon_230kV",
            "substation": "Vernon",
            "capacity_mw": 800
        },
        "Harbor": {
            "bounds": [[33.720, -118.280], [33.750, -118.250]],
            "bus": "Harbor_500kV",
            "substation": "Harbor",
            "capacity_mw": 1200
        },
        "LAX": {
            "bounds": [[33.930, -118.420], [33.950, -118.390]],
            "bus": "LAX_138kV",
            "substation": "LAX",
            "capacity_mw": 400
        }
    }
}

# Realistic Charging Stations based on LA infrastructure
CHARGING_STATIONS = {
    "losangeles": [
        # Downtown LA cluster
        {"id": "CS_DTLA_1", "lat": 34.050, "lon": -118.250, 
         "capacity": 20, "type": "level_2_ac", "grid_bus": "DTLA_138kV"},
        {"id": "CS_DTLA_2", "lat": 34.045, "lon": -118.245, 
         "capacity": 10, "type": "level_3_dc", "grid_bus": "DTLA_138kV"},
        
        # Vernon Industrial area
        {"id": "CS_Vernon_1", "lat": 34.020, "lon": -118.220, 
         "capacity": 15, "type": "level_2_ac", "grid_bus": "Vernon_230kV"},
        {"id": "CS_Vernon_2", "lat": 34.015, "lon": -118.215, 
         "capacity": 8, "type": "level_3_dc", "grid_bus": "Vernon_230kV"},
        
        # LAX area
        {"id": "CS_LAX_1", "lat": 33.942, "lon": -118.408, 
         "capacity": 25, "type": "level_2_ac", "grid_bus": "LAX_138kV"},
        {"id": "CS_LAX_2", "lat": 33.940, "lon": -118.405, 
         "capacity": 12, "type": "level_3_dc", "grid_bus": "LAX_138kV"},
    ]
}

# Grid operational parameters
GRID_PARAMETERS = {
    "base_mva": 100,
    "frequency": 60,  # Hz
    "voltage_levels": [500, 230, 138, 69, 12.47],  # kV
    "congestion_threshold": 0.8,
    "critical_threshold": 0.95,
    "outage_threshold": 1.0
}

# Demand Response Settings
DEMAND_RESPONSE = {
    "levels": {
        "normal": {"factor": 1.0, "ev_charging": "all"},
        "warning": {"factor": 0.8, "ev_charging": "level_2_only"},
        "critical": {"factor": 0.6, "ev_charging": "emergency_only"},
        "blackout": {"factor": 0.0, "ev_charging": "none"}
    },
    "traffic_light_dimming": 0.7,  # Reduce brightness during high demand
    "street_light_dimming": 0.5,   # Reduce street lighting
    "ev_throttling": 0.5            # Reduce charging rate
}

# Default city
DEFAULT_CITY = "losangeles"