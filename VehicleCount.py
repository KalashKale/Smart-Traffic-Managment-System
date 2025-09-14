import traci
import time
import sys

class SimpleTrafficController:
    def __init__(self):
        # Dummy traffic light IDs - replace with your actual IDs
        self.traffic_lights = ["Node2", "Node5"]  # Your two T-intersections
        
        # Traffic light phases for T-intersection
        # Phase 0: Main road (East-West) gets green
        # Phase 1: Side road (North or South) gets green
        self.main_road_phase = 0
        self.side_road_phase = 2
        # Timing constraints (seconds)
        self.min_green_time = 15  # Minimum green time for any direction
        self.max_green_time = 60  # Maximum green time for any direction
        self.yellow_time = 3      # Yellow light duration
        
        # Control variables for each intersection
        self.intersection_state = {}
        for tl_id in self.traffic_lights:
            self.intersection_state[tl_id] = {
                'current_phase': 0,
                'phase_start_time': 0,
                'last_switch_time': 0
            }
    
    def connect_to_sumo(self, sumo_config_file):
        """Connect to SUMO simulation"""
        try:
            # Start SUMO with GUI (change to "sumo" for non-GUI)
            traci.start(["sumo-gui", "-c", sumo_config_file])
            print("✅ Connected to SUMO successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to SUMO: {e}")
            return False
    
    def get_traffic_data(self, tl_id):
        """Get traffic data for a T-intersection"""
        try:
            # Get controlled lanes for this traffic light
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            
            # For T-intersection, typically we have 3 approaches
            # Group lanes by direction (main road vs side road)
            main_road_count = 0
            side_road_count = 0
            
            for lane in controlled_lanes:
                vehicle_count = traci.lane.getLastStepVehicleNumber(lane)
                waiting_count = traci.lane.getLastStepHaltingNumber(lane)
                
                # Custom grouping for your network
                if "EB" in lane or "WB" in lane:
                    main_road_count += waiting_count
                else:
                    side_road_count += waiting_count
            
            return {
                'main_road_waiting': main_road_count,
                'side_road_waiting': side_road_count,
                'total_waiting': main_road_count + side_road_count
            }
        except Exception as e:
            print(f"❌ Error getting traffic data for {tl_id}: {e}")
            return {'main_road_waiting': 0, 'side_road_waiting': 0, 'total_waiting': 0}
    
    def calculate_optimal_timing(self, traffic_data):
        """Simple algorithm to calculate optimal green time"""
        main_waiting = traffic_data['main_road_waiting']
        side_waiting = traffic_data['side_road_waiting']
        
        # If no one is waiting, use minimum times
        if main_waiting == 0 and side_waiting == 0:
            return {'main_green': self.min_green_time, 'side_green': self.min_green_time}
        
        # Calculate ratio-based timing
        total_waiting = main_waiting + side_waiting
        if total_waiting > 0:
            main_ratio = main_waiting / total_waiting
            side_ratio = side_waiting / total_waiting
            
            # Calculate green times (60 seconds total cycle time)
            total_green_time = 60 - 2 * self.yellow_time  # Account for yellow phases
            main_green = max(self.min_green_time, min(self.max_green_time, main_ratio * total_green_time))
            side_green = max(self.min_green_time, min(self.max_green_time, side_ratio * total_green_time))
            
            return {'main_green': int(main_green), 'side_green': int(side_green)}
        
        return {'main_green': self.min_green_time, 'side_green': self.min_green_time}
    
    def should_switch_phase(self, tl_id, traffic_data):
        """Decide if we should switch the traffic light phase"""
        current_time = traci.simulation.getTime()
        state = self.intersection_state[tl_id]
        current_phase = traci.trafficlight.getPhase(tl_id)
        
        # Time since current phase started
        phase_duration = current_time - state['phase_start_time']
        
        # Don't switch too frequently (minimum phase time)
        if phase_duration < self.min_green_time:
            return False
        
        # Force switch if maximum time reached
        if phase_duration >= self.max_green_time:
            return True
        
        # Smart switching logic
        if current_phase == self.main_road_phase:
            # Currently main road has green
            # Switch if side road has significantly more waiting cars
            if traffic_data['side_road_waiting'] > traffic_data['main_road_waiting'] * 2:
                return True
        else:
            # Currently side road has green
            # Switch if main road has more waiting cars
            if traffic_data['main_road_waiting'] > traffic_data['side_road_waiting']:
                return True
        
        return False
    
    def control_intersection(self, tl_id):
        """Control a single T-intersection"""
        traffic_data = self.get_traffic_data(tl_id)
        current_time = traci.simulation.getTime()
        
        # Update phase start time if this is the beginning
        if self.intersection_state[tl_id]['phase_start_time'] == 0:
            self.intersection_state[tl_id]['phase_start_time'] = current_time
        
        # Check if we should switch phase
        if self.should_switch_phase(tl_id, traffic_data):
            current_phase = traci.trafficlight.getPhase(tl_id)
            
            # Switch to the other phase
            if current_phase == self.main_road_phase:
                new_phase = self.side_road_phase
            else:
                new_phase = self.main_road_phase
            
            # Apply the phase change
            traci.trafficlight.setPhase(tl_id, new_phase)
            
            # Update state
            self.intersection_state[tl_id]['current_phase'] = new_phase
            self.intersection_state[tl_id]['phase_start_time'] = current_time
            self.intersection_state[tl_id]['last_switch_time'] = current_time
            
            print(f"🚦 {tl_id}: Switched to phase {new_phase} | Main waiting: {traffic_data['main_road_waiting']}, Side waiting: {traffic_data['side_road_waiting']}")
    
    def collect_metrics(self):
        """Collect performance metrics"""
        total_waiting_time = 0
        total_vehicles = 0
        
        try:
            # Get all vehicles in the simulation
            vehicle_ids = traci.vehicle.getIDList()
            total_vehicles = len(vehicle_ids)
            
            # Calculate total waiting time
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
            return {
                'total_vehicles': 0,
                'total_waiting_time': 0,
                'avg_waiting_time': 0,
                'simulation_time': traci.simulation.getTime()
            }
    
    def run_simulation(self, sumo_config_file, simulation_duration=3600):
        """Run the main simulation loop"""
        if not self.connect_to_sumo(sumo_config_file):
            return
        
        print(f"🚀 Starting simulation for {simulation_duration} seconds...")
        print(f"📊 Controlling intersections: {self.traffic_lights}")
        
        # Metrics collection
        metrics_history = []
        last_metrics_time = 0
        
        try:
            while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < simulation_duration:
                # Control each intersection
                for tl_id in self.traffic_lights:
                    self.control_intersection(tl_id)
                
                # Collect metrics every 60 seconds
                current_time = traci.simulation.getTime()
                if current_time - last_metrics_time >= 60:
                    metrics = self.collect_metrics()
                    metrics_history.append(metrics)
                    last_metrics_time = current_time
                    
                    print(f"⏱️  Time: {current_time:.0f}s | Vehicles: {metrics['total_vehicles']} | Avg Wait: {metrics['avg_waiting_time']:.2f}s")
                
                # Advance simulation by one step
                traci.simulationStep()
            
            # Final metrics
            print("\n📈 Simulation Complete!")
            if metrics_history:
                final_metrics = metrics_history[-1]
                print(f"🎯 Final Results:")
                print(f"   Total Vehicles: {final_metrics['total_vehicles']}")
                print(f"   Average Waiting Time: {final_metrics['avg_waiting_time']:.2f} seconds")
                print(f"   Total Simulation Time: {final_metrics['simulation_time']:.0f} seconds")
            
        except KeyboardInterrupt:
            print("\n⏹️  Simulation stopped by user")
        except Exception as e:
            print(f"❌ Simulation error: {e}")
        finally:
            traci.close()
            print("✅ SUMO connection closed")

def main():
    """Main function to run the traffic controller"""
    # Initialize controller
    controller = SimpleTrafficController()
    
    # Replace with your SUMO configuration file path
    sumo_config = "E:\Programming\Projects\SIH 2025\Traffic Simulation\TLS\Traci\Traci 2 GitHub\Smart-Traffic-Managment-System\Traci2.sumocfg"  # Update this path!
    
    # Run simulation (3600 seconds = 1 hour)
    controller.run_simulation(sumo_config, simulation_duration=3600)

if __name__ == "__main__":
    main()

