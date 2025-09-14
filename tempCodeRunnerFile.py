# Step 1: Add modules
import os
import sys

# Step 2: Establish path to SUMO (SUMO_HOME)
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

# Step 3: Import TraCI
import traci

# Step 4: Define SUMO configuration
Sumo_config = [
    'sumo-gui',
    '-c', r"E:\Programming\Projects\SIH 2025\Traffic Simulation\TLS\Traci\Traci2\Traci2.sumocfg",
    '--step-length', '0.05',
    '--delay', '1000',
    '--lateral-resolution', '0.1'
]

# Step 5: Start SUMO with TraCI
traci.start(Sumo_config)

# Step 6: Track adjusted TLS
adjusted_tls = {}
step = 0

# Step 7: Helper function – find which phase gives green to a specific lane
def find_phase_for_lane(tlsID, laneID):
    programs = traci.trafficlight.getCompleteRedYellowGreenDefinition(tlsID)
    for prog in programs:
        for phase_index, phase in enumerate(prog.phases):
            controlled_lanes = traci.trafficlight.getControlledLanes(tlsID)
            for i, l in enumerate(controlled_lanes):
                if l == laneID and phase.state[i] == 'G':
                    return phase_index
    return None

# Step 8: Emergency vehicle processor
def process_emergency_vehicles(adjusted_tls, step):
    emergency_vehicles = [
        veh for veh in traci.vehicle.getIDList()
        if traci.vehicle.getTypeID(veh) == "emergency"
    ]

    active_tls = set()

    for veh in emergency_vehicles:
        next_tls = traci.vehicle.getNextTLS(veh)
        print(f"next_tls for {veh}: {next_tls}")

        if next_tls:
            tlsID, linkIndex, distance, state = next_tls[0]

            laneID = traci.vehicle.getLaneID(veh)
            desired_phase = find_phase_for_lane(tlsID, laneID)

            if desired_phase is not None:
                current_phase = traci.trafficlight.getPhase(tlsID)
                print(f"{veh} approaching {tlsID}, "
                      f"Lane: {laneID}, Current phase: {current_phase}, "
                      f"Desired phase: {desired_phase}")

                active_tls.add(tlsID)

                if tlsID not in adjusted_tls or adjusted_tls[tlsID] != desired_phase:
                    adjusted_tls[tlsID] = desired_phase
                    if current_phase == desired_phase:
                        new_duration = max(20, traci.trafficlight.getPhaseDuration(tlsID) + 10)
                        traci.trafficlight.setPhaseDuration(tlsID, new_duration)
                        print(f"Extended phase {current_phase} of {tlsID} to {new_duration} seconds")
                    else:
                        traci.trafficlight.setPhase(tlsID, desired_phase)
                        traci.trafficlight.setPhaseDuration(tlsID, 10)
                        print(f"Switched {tlsID} to phase {desired_phase} for emergency")

    for tlsID in list(adjusted_tls.keys()):
        if tlsID not in active_tls:
            del adjusted_tls[tlsID]
            print(f"Resetting traffic light {tlsID} to normal operation.")

    step += 1
    return step

# Step 9: Simulation loop
while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()

    if step == 0:
        print("=== Debug: Controlled Lanes per TLS ===")
        for tls in traci.trafficlight.getIDList():
            print(f"{tls}: {traci.trafficlight.getControlledLanes(tls)}")

    step = process_emergency_vehicles(adjusted_tls, step)

# Step 10: Close TraCI
traci.close()
