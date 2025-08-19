# config.py - Updated for LA focus with realistic power grid
import os

# SUMO Configuration
SUMO_PATH = "C:\\Program Files (x86)\\Eclipse\\Sumo"

# Web Server Configuration
HOST = "0.0.0.0"
PORT = 8080

# Simulation Configuration
SIMULATION_SPEED = 0.01
UPDATE_FREQUENCY = 1

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
# Region of Interest - Downtown LA area only
REGION_OF_INTEREST = {
    "min_lat": 34.020,
    "max_lat": 34.080,
    "min_lon": -118.280,
    "max_lon": -118.220
}

# Filter charging stations to only those in region
CHARGING_STATIONS = {
    "losangeles": [
        # Only DTLA stations
        {"id": "CS_DTLA_1", "lat": 34.050, "lon": -118.250, 
         "capacity": 20, "type": "level_2_ac", "grid_bus": "DTLA_138kV"},
        {"id": "CS_DTLA_2", "lat": 34.045, "lon": -118.245, 
         "capacity": 10, "type": "level_3_dc", "grid_bus": "DTLA_138kV"},
        # Remove Vernon, Harbor, LAX stations - they're outside the region
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
# Add these to your config.py

# Time-based configuration
import datetime

def get_time_of_day_factor(simulation_step):
    """Get time of day from simulation step (0.1s per step)"""
    # Convert simulation step to hour of day
    seconds = simulation_step * 0.1
    hour = (seconds / 3600) % 24
    
    # Return period
    if 6 <= hour < 9:
        return "morning_rush", 1.5  # 150% traffic
    elif 17 <= hour < 20:
        return "evening_rush", 1.5  # 150% traffic
    elif 9 <= hour < 17:
        return "day", 1.0  # Normal traffic
    else:
        return "night", 0.2  # 20% traffic

# Update simulation speed for better performance
SIMULATION_SPEED = 0.001  # Much faster updates
UPDATE_FREQUENCY = 1      # Update every step

# Street lighting schedule
STREET_LIGHT_SCHEDULE = {
    "dawn": 6,      # 6 AM - lights start dimming
    "sunrise": 7,   # 7 AM - lights off
    "sunset": 18,   # 6 PM - lights start turning on
    "dusk": 19,     # 7 PM - full brightness
}

# Power consumption modifiers
POWER_MODIFIERS = {
    "morning_rush": 1.3,   # 30% more power during rush hour
    "evening_rush": 1.4,   # 40% more power (lights + traffic)
    "day": 1.0,           # Normal power
    "night": 0.6,         # 60% power at night (less traffic, dimmed lights)
}

# Blackout thresholds
BLACKOUT_THRESHOLDS = {
    "warning": 0.75,      # 75% grid capacity
    "critical": 0.90,     # 90% grid capacity
    "blackout": 1.0,      # 100% grid capacity - rolling blackouts
}

# EV Charging patterns
EV_CHARGING_PATTERNS = {
    "morning_rush": 0.1,   # 10% charging (people arriving at work)
    "day": 0.3,           # 30% charging (during work)
    "evening_rush": 0.4,   # 40% charging (home charging starts)
    "night": 0.2,         # 20% charging (overnight charging)
}
# Default city
DEFAULT_CITY = "losangeles"