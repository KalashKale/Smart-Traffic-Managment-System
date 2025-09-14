import os
import sys
import traci

# Make sure SUMO_HOME is set
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

# Path to your config file
config_file = r"E:\Programming\Projects\SIH 2025\Traffic Simulation\TLS\Traci\Traci2\Traci2.sumocfg"

# Start SUMO
sumo_cmd = ["sumo-gui", "-c", config_file, "--step-length", "0.05"]
traci.start(sumo_cmd)

# Get controlled links for Node2
links = traci.trafficlight.getControlledLinks("Node2")

print("Controlled links at Node2:")
for i, link in enumerate(links):
    print(f"{i}: {link}")

# Close TraCI
traci.close()
