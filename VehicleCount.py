import traci
import time
import sys

class SimpleTrafficController:
    def __init__(self):
        # Traffic light IDs
        self.traffic_lights = ["Node2", "Node5"]

        # Phase mapping for Node2/Node5 (adjust if needed)
        self.main_road_phase = 0   # EB/WB
        self.side_road_phase = 2   # NB/SB
        self.third_road_phase = 4  # From Node3

        # Timing constraints
        self.min_green_time = 15
        self.max_green_time = 60
        self.yellow_time = 3

        # Track intersection states
        self.intersection_state = {}
        for tl_id in self.traffic_lights:
            self.intersection_state[tl_id] = {
                'current_phase': 0,
                'phase_start_time': 0,
                'last_switch_time': 0
            }

    def connect_to_sumo(self, sumo_config_file):
        try:
            traci.start(["sumo-gui", "-c", sumo_config_file])
            print("✅ Connected to SUMO successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to SUMO: {e}")
            return False

    def get_traffic_data(self, tl_id):
        """Get traffic data grouped by approach"""
        try:
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)

            main_count = 0
            side_count = 0
            third_count = 0

            for lane in controlled_lanes:
                waiting_count = traci.lane.getLastStepHaltingNumber(lane)

                if "EB" in lane or "WB" in lane:
                    main_count += waiting_count
                elif "SB" in lane or "NB" in lane:
                    side_count += waiting_count
                else:
                    third_count += waiting_count

            return {
                'main_road_waiting': main_count,
                'side_road_waiting': side_count,
                'third_road_waiting': third_count,
                'total_waiting': main_count + side_count + third_count
            }
        except Exception as e:
            print(f"❌ Error getting traffic data for {tl_id}: {e}")
            return {'main_road_waiting': 0, 'side_road_waiting': 0, 'third_road_waiting': 0, 'total_waiting': 0}

    def should_switch_phase(self, tl_id, traffic_data):
        """Decide if we should switch"""
        current_time = traci.simulation.getTime()
        state = self.intersection_state[tl_id]
        current_phase = traci.trafficlight.getPhase(tl_id)
        elapsed = current_time - state['phase_start_time']

        if elapsed < self.min_green_time:
            return None
        if elapsed >= self.max_green_time:
            # cycle through phases
            if current_phase == self.main_road_phase:
                return self.side_road_phase
            elif current_phase == self.side_road_phase:
                return self.third_road_phase
            else:
                return self.main_road_phase

        # Adaptive switching
        if current_phase == self.main_road_phase:
            if traffic_data['side_road_waiting'] > traffic_data['main_road_waiting'] * 1.5:
                return self.side_road_phase
            if traffic_data['third_road_waiting'] > traffic_data['main_road_waiting'] * 1.5:
                return self.third_road_phase

        elif current_phase == self.side_road_phase:
            if traffic_data['main_road_waiting'] > traffic_data['side_road_waiting']:
                return self.main_road_phase
            if traffic_data['third_road_waiting'] > traffic_data['side_road_waiting']:
                return self.third_road_phase

        elif current_phase == self.third_road_phase:
            if traffic_data['main_road_waiting'] >= traffic_data['third_road_waiting']:
                return self.main_road_phase
            if traffic_data['side_road_waiting'] >= traffic_data['third_road_waiting']:
                return self.side_road_phase

        return None

    def control_intersection(self, tl_id):
        traffic_data = self.get_traffic_data(tl_id)
        current_time = traci.simulation.getTime()

        if self.intersection_state[tl_id]['phase_start_time'] == 0:
            self.intersection_state[tl_id]['phase_start_time'] = current_time

        switch_to = self.should_switch_phase(tl_id, traffic_data)
        if switch_to is not None:
            traci.trafficlight.setPhase(tl_id, switch_to)
            self.intersection_state[tl_id]['current_phase'] = switch_to
            self.intersection_state[tl_id]['phase_start_time'] = current_time
            self.intersection_state[tl_id]['last_switch_time'] = current_time
            print(f"🚦 {tl_id}: switched to phase {switch_to} | "
                  f"Main={traffic_data['main_road_waiting']}, Side={traffic_data['side_road_waiting']}, Third={traffic_data['third_road_waiting']}")

    def collect_metrics(self):
        total_waiting_time = 0
        total_vehicles = 0
        try:
            vehicle_ids = traci.vehicle.getIDList()
            total_vehicles = len(vehicle_ids)
            for vehicle_id in vehicle_ids:
                waiting_time = traci.vehicle.getWaitingTime(vehicle_id)
                total_waiting_time += waiting_time
            avg_waiting_time = total_waiting_time / total_vehicles if total_vehicles > 0 else 0
            return {
                'total_vehicles': total_vehicles,
                'total_waiting_time': total_waiting_time,
                'avg_waiting_time': avg_waiting_time,
                'simulation_time': traci.simulation.getTime()
            }
        except:
            return {'total_vehicles': 0, 'total_waiting_time': 0, 'avg_waiting_time': 0, 'simulation_time': traci.simulation.getTime()}

    def run_simulation(self, sumo_config_file, simulation_duration=3600):
        if not self.connect_to_sumo(sumo_config_file):
            return
        print(f"🚀 Starting simulation for {simulation_duration} seconds...")
        print(f"📊 Controlling intersections: {self.traffic_lights}")
        metrics_history = []
        last_metrics_time = 0
        try:
            while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < simulation_duration:
                for tl_id in self.traffic_lights:
                    self.control_intersection(tl_id)
                current_time = traci.simulation.getTime()
                if current_time - last_metrics_time >= 60:
                    metrics = self.collect_metrics()
                    metrics_history.append(metrics)
                    last_metrics_time = current_time
                    print(f"⏱️ Time: {current_time:.0f}s | Vehicles: {metrics['total_vehicles']} | Avg Wait: {metrics['avg_waiting_time']:.2f}s")
                traci.simulationStep()
            print("\n📈 Simulation Complete!")
            if metrics_history:
                final_metrics = metrics_history[-1]
                print(f"🎯 Final Results:")
                print(f"   Total Vehicles: {final_metrics['total_vehicles']}")
                print(f"   Average Waiting Time: {final_metrics['avg_waiting_time']:.2f} seconds")
                print(f"   Total Simulation Time: {final_metrics['simulation_time']:.0f} seconds")
        except KeyboardInterrupt:
            print("\n⏹️ Simulation stopped by user")
        except Exception as e:
            print(f"❌ Simulation error: {e}")
        finally:
            traci.close()
            print("✅ SUMO connection closed")


def main():
    controller = SimpleTrafficController()
    sumo_config = r"E:\Programming\Projects\SIH 2025\Traffic Simulation\TLS\Traci\Traci 2 GitHub\Smart-Traffic-Managment-System\Traci2.sumocfg"
    controller.run_simulation(sumo_config, simulation_duration=3600)

if __name__ == "__main__":
    main()
