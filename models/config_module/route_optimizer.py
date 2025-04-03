"""
Route Optimizer for inter-facility transportation shuttles.
This module contains the logic for optimizing routes, calculating statistics,
and building simulation models.
"""

import numpy as np
import math
from datetime import datetime
from models.config_module.shuttle import Shuttle
from models.data_module.celky import Celky
from models.config_module.shuttle_statistics import ShuttleStatistics


class RouteOptimizer:
    @staticmethod
    def group_celky_by_source_dest(celky_data, time_interval=15):
        """
        Group celky by source-destination pair and preserve hourly patterns.
        
        Args:
            celky_data (list): List of celky dictionaries
            time_interval (int): Interval in minutes for dividing hours
            
        Returns:
            dict: Dictionary with (source, dest) keys and grouped data
        """
        grouped = {}
        # Convert hourly values to intervals
        interval_ratio = int(60 / time_interval)  # Number of intervals per hour
    
        for celky in celky_data:
            source = celky["source_plant"]
            dest = celky["dest_plant"]
            key = (source, dest)
        
            # Initialize if not exists
            if key not in grouped:
                grouped[key] = {
                    "celky": [],
                    "celky_ids": [],
                    "source": source,
                    "dest": dest,
                    "moves": 0,
                    "median_moves_by_hour": [0 for _ in range(24)],
                    "percentile90_moves_by_hour": [0 for _ in range(24)],
                    "median_moves_by_interval": [0 for _ in range(24*interval_ratio)],
                    "percentile90_moves_by_interval": [0 for _ in range(24*interval_ratio)]
                }
        
            # Add celky to group
            grouped[key]["celky"].append(celky)
            grouped[key]["celky_ids"].append(celky["id"])
        
            # Process hourly stats while preserving hourly patterns
            hourly_stats = celky.get("hourly_stats", [])

            for stat in hourly_stats:
                grouped[key]["median_moves_by_hour"][stat.get("hour")] += stat.get("median_moves")
                grouped[key]["percentile90_moves_by_hour"][stat.get("hour")] += stat.get("percentile_90")
        
            # Calculate average hourly moves for backward compatibility
            total_median_moves = sum(grouped[key]["median_moves_by_hour"])
            if total_median_moves > 0:
                grouped[key]["moves"] = total_median_moves / 24  # Average over 24 hours
        
        for key, value in grouped.items():

            # Distribute median moves across intervals
            for hour in range(24):
                hourly_median = value["median_moves_by_hour"][hour]
                interval_median = hourly_median / interval_ratio
                
                # Distribute this value evenly across all intervals in the hour
                for interval_offset in range(interval_ratio):
                    interval_index = hour * interval_ratio + interval_offset
                    value["median_moves_by_interval"][interval_index] += interval_median

            # Distribute percentile90 moves across intervals
            for hour in range(24):
                hourly_percentile = value["percentile90_moves_by_hour"][hour]
                interval_percentile = hourly_percentile / interval_ratio
                
                # Distribute this value evenly across all intervals in the hour
                for interval_offset in range(interval_ratio):
                    interval_index = hour * interval_ratio + interval_offset
                    value["percentile90_moves_by_interval"][interval_index] += interval_percentile
            
        return grouped
    
    @staticmethod
    def create_scenario_grouped_celky(grouped_celky, scenario="median", start_interval=None, intervals_per_freq=None, time_interval=15):
        """
        Create a new grouped_celky dictionary for a specific scenario.
        
        Args:
            grouped_celky (dict): Original grouped celky dictionary
            scenario (str): "median" or "p90" to choose which values to use
            start_interval (int, optional): Starting interval for peak period
            intervals_per_freq (int, optional): Number of intervals in the frequency
            time_interval (int): Interval in minutes for dividing hours
            
        Returns:
            dict: New grouped_celky dictionary for the scenario
        """
        scenario_grouped = {}
        interval_ratio = int(60 / time_interval)
        total_intervals = 24 * interval_ratio
        
        for source_dest_key, group_data in grouped_celky.items():
            # Copy the basic structure
            scenario_grouped[source_dest_key] = {
                "celky": group_data["celky"].copy(),
                "celky_ids": group_data["celky_ids"].copy(),
                "source": group_data["source"],
                "dest": group_data["dest"],
                "moves": 0
            }
            
            if scenario == "median":
                if start_interval is not None and intervals_per_freq is not None:
                    # For peak period median
                    scenario_moves = 0
                    median_moves = group_data["median_moves_by_interval"]
                    
                    # Calculate sum for the specified time window
                    for i in range(intervals_per_freq):
                        interval_idx = (start_interval + i) % total_intervals
                        scenario_moves += median_moves[interval_idx]
                    
                    # Scale moves to match the frequency length
                    scenario_grouped[source_dest_key]["moves"] = scenario_moves
                else:
                    # For average median
                    scenario_grouped[source_dest_key]["moves"] = sum(group_data["median_moves_by_hour"]) / 24
            else:  # p90
                if start_interval is not None and intervals_per_freq is not None:
                    # For peak period p90
                    scenario_moves = 0
                    p90_moves = group_data["percentile90_moves_by_interval"]
                    
                    # Calculate sum for the specified time window
                    for i in range(intervals_per_freq):
                        interval_idx = (start_interval + i) % total_intervals
                        scenario_moves += p90_moves[interval_idx]
                    
                    # Scale moves to match the frequency length
                    scenario_grouped[source_dest_key]["moves"] = scenario_moves
                else:
                    # For average p90
                    scenario_grouped[source_dest_key]["moves"] = sum(group_data["percentile90_moves_by_hour"]) / 24
                
        return scenario_grouped
    
    @staticmethod
    def build_optimal_route_simulation(grouped_celky, shift_change_dest, travel_times, shuttle_capacity):
        """
        Build an optimal route using a simulation-based approach that ensures all cargo is loaded and unloaded.
        Tracks celky IDs with the shuttle inventory.
        
        Args:
            grouped_celky (dict): Dictionary with grouped celky data
            shift_change_dest (int): Destination for shift change
            travel_times (dict): Dictionary with travel times
            shuttle_capacity (int): Maximum shuttle capacity
            
        Returns:
            tuple: (route, operations) - List of plants in route order and operations at each stop
        """
        # Extract all plants
        all_plants = set()
        for (source, dest) in grouped_celky.keys():
            all_plants.add(source)
            all_plants.add(dest)
        
        # Find plant with most outgoing moves
        outgoing_counts = {}
        for (source, _), group_data in grouped_celky.items():
            if source not in outgoing_counts:
                outgoing_counts[source] = 0
            outgoing_counts[source] += group_data["moves"]
        
        start_plant = max(outgoing_counts.items(), key=lambda x: x[1])[0] if outgoing_counts else min(all_plants)
        
        # Initialize route and state
        route = [start_plant]
        operations = [{"plant": start_plant, "load": {}, "unload": {}}]
        current_plant = start_plant
        
        # Track remaining moves and celky IDs for each celky group
        remaining_moves = {}
        remaining_celky_ids = {}
        
        for group_key, group_data in grouped_celky.items():
            remaining_moves[group_key] = group_data["moves"]
            remaining_celky_ids[group_key] = group_data["celky_ids"].copy()  # Make a copy to avoid modifying original
        
        # Track what's on the shuttle
        shuttle_inventory = {}  # (source, dest) -> {"moves": count, "celky_ids": [ids]}
        
        # Continue until all moves are fulfilled AND shuttle is empty
        while (any(moves > 0 for moves in remaining_moves.values()) or 
            any(inventory.get("moves", 0) > 0 for inventory in shuttle_inventory.values())):
            
            # Step 1: Decide what operations to perform at current plant
            
            # Unload anything that has this plant as destination
            for (source, dest), inventory in list(shuttle_inventory.items()):
                if dest == current_plant and inventory.get("moves", 0) > 0:
                    # Create string key for JSON serialization
                    str_key = f"{source},{dest}"
                    
                    if str_key not in operations[-1]["unload"]:
                        operations[-1]["unload"][str_key] = {"moves": 0, "celky_ids": []}
                    
                    operations[-1]["unload"][str_key]["moves"] += inventory["moves"]
                    operations[-1]["unload"][str_key]["celky_ids"].extend(inventory["celky_ids"])
                    
                    # Update remaining moves (already handled)
                    remaining_moves[(source, dest)] = max(0, remaining_moves.get((source, dest), 0) - inventory["moves"])
                    
                    # Clear shuttle inventory for this route
                    shuttle_inventory[(source, dest)] = {"moves": 0, "celky_ids": []}
            
            # Load anything that has this plant as source (if no shuttle issues)
            current_destinations = set(dest for (source, dest) in shuttle_inventory if shuttle_inventory[(source, dest)].get("moves", 0) > 0)
            
            # Can load if shuttle is empty or all current cargo is going to the same destination
            can_load = len(current_destinations) <= 1
            
            if can_load:
                for (source, dest), moves in list(remaining_moves.items()):
                    if source == current_plant and moves > 0:
                        # Check if this would create shuttle issues
                        if not current_destinations or dest in current_destinations:
                            # Determine how much to load
                            current_load = sum(inv.get("moves", 0) for inv in shuttle_inventory.values())
                            available_capacity = shuttle_capacity - current_load
                            load_amount = moves

                            # Strict capacity enforcement while handling large loads
                            projected_load = current_load + load_amount
                            if projected_load > shuttle_capacity:
                                # If there's no load yet (empty shuttle), we should load at least up to capacity
                                # even if the single load exceeds capacity (will require multiple trips)
                                if current_load < 2:  # Shuttle is almost empty
                                    # Load up to capacity for first trip
                                    load_amount = moves
                                else:
                                    # get how much over
                                    how_much_over = load_amount - (shuttle_capacity - current_load)
                                    if how_much_over >= 1:
                                        break  # if how much over is more than 1 we cannot load
                            
                            if load_amount > 0.001:
                                # Create string key for JSON serialization
                                str_key = f"{source},{dest}"
                                
                                if str_key not in operations[-1]["load"]:
                                    operations[-1]["load"][str_key] = {"moves": 0, "celky_ids": []}
                                
                                # With floating point load_amount, we need to handle celky_ids differently
                                # For example, if we have a fractional move (0.25 moves), we still assign
                                # a celky_id to represent it, instead of slicing
                                celky_ids_to_load = []
                                if remaining_celky_ids[(source, dest)]:
                                    # Just take the first ID from remaining_celky_ids
                                    celky_ids_to_load = remaining_celky_ids[(source, dest)]
                                
                                operations[-1]["load"][str_key]["moves"] += load_amount
                                operations[-1]["load"][str_key]["celky_ids"].extend(celky_ids_to_load)
                                
                                # Initialize shuttle inventory if needed
                                if (source, dest) not in shuttle_inventory:
                                    shuttle_inventory[(source, dest)] = {"moves": 0, "celky_ids": []}
                                
                                # Update shuttle inventory
                                shuttle_inventory[(source, dest)]["moves"] += load_amount
                                shuttle_inventory[(source, dest)]["celky_ids"].extend(celky_ids_to_load)
                                
                                # Update remaining moves
                                remaining_moves[(source, dest)] -= load_amount
                                
                                # Only remove celky_ids if we have any and actually used them
                                if remaining_celky_ids[(source, dest)] and celky_ids_to_load:
                                    # Remove the first ID that we used
                                    remaining_celky_ids[(source, dest)].pop(0)
                                    
                                # Check if we've reached shuttle capacity and need to unload
                                current_total_load = sum(inv.get("moves", 0) for inv in shuttle_inventory.values())
                                if current_total_load >= shuttle_capacity:  # 95% capacity threshold
                                    # Mark that we need to prioritize unloading
                                    break
            
            # Step 2: Determine next plant to visit
            next_plant = None

            # Track destinations we're currently going to
            current_destinations = set(dest for (source, dest), inventory in shuttle_inventory.items() 
                                    if inventory.get("moves", 0) > 0)

            # First, find the closest destination where we need to unload cargo (the original direct path)
            direct_dest = None
            direct_travel_time = float('inf')

            if any(inventory.get("moves", 0) > 0 for inventory in shuttle_inventory.values()):
                for (_, dest), inventory in shuttle_inventory.items():
                    if inventory.get("moves", 0) > 0:
                        travel_time = RouteOptimizer.get_travel_time(travel_times, current_plant, dest)
                        if travel_time < direct_travel_time:
                            direct_travel_time = travel_time
                            direct_dest = dest

            # If we have current destinations and space on the shuttle, evaluate detour efficiency
            if current_destinations and direct_dest is not None:
                # Calculate remaining capacity on the shuttle
                current_load = sum(inv.get("moves", 0) for inv in shuttle_inventory.values())
                available_capacity = shuttle_capacity - current_load
                
                best_detour_efficiency = 0
                best_detour_source = None
                
                # For each potential source-destination pair with remaining moves
                for (source, dest), moves in remaining_moves.items():
                    # Only consider sources that aren't the current plant and have cargo going to our current destinations
                    if moves > 0 and dest in current_destinations and source != current_plant:
                        # Calculate the detour cost: time to go from current to this source and then to the destination
                        time_to_source = RouteOptimizer.get_travel_time(travel_times, current_plant, source)
                        time_from_source_to_dest = RouteOptimizer.get_travel_time(travel_times, source, direct_dest)
                        
                        # Total time for the detour
                        detour_time = time_to_source + time_from_source_to_dest
                        
                        # Direct time to destination and back to this source (the alternative)
                        direct_time = direct_travel_time + RouteOptimizer.get_travel_time(travel_times, direct_dest, source)
                        
                        # Amount we can pick up at this source (limited by available capacity)
                        loadable_moves = min(moves, available_capacity)
                        
                        # If the detour saves time and we can pick up cargo
                        if detour_time < direct_time and loadable_moves > 0:
                            # Calculate efficiency: time saved per move loaded
                            time_saved = direct_time - detour_time
                            efficiency = time_saved * loadable_moves
                            
                            if efficiency > best_detour_efficiency:
                                best_detour_efficiency = efficiency
                                best_detour_source = source
                
                # If we found an efficient detour, take it
                if best_detour_source is not None:
                    next_plant = best_detour_source
                else:
                    # Otherwise go straight to the destination
                    next_plant = direct_dest
            elif direct_dest is not None:
                # If no efficient detours or no space, go straight to destination
                next_plant = direct_dest

            # If still no next plant found (no cargo to deliver), find a source with remaining moves
            if next_plant is None:
                sources_with_remaining = []
                for (source, _), moves in remaining_moves.items():
                    if moves > 0:
                        travel_time = RouteOptimizer.get_travel_time(travel_times, current_plant, source)
                        sources_with_remaining.append((source, travel_time, moves))
                
                if sources_with_remaining:
                    # Instead of just closest, consider both distance and amount of cargo
                    # Sort by a weighted score that prioritizes closer locations with more cargo
                    sources_with_remaining.sort(key=lambda x: (x[1] / (x[2] * 0.5 + 1)))
                    next_plant = sources_with_remaining[0][0]

            # If still no next plant found but we have cargo, visit the destinations for unloading
            if next_plant is None and any(inventory.get("moves", 0) > 0 for inventory in shuttle_inventory.values()):
                destinations_needed = set(dest for (_, dest), inventory in shuttle_inventory.items() if inventory.get("moves", 0) > 0)
                if destinations_needed:
                    # Pick closest destination
                    best_dest = None
                    best_time = float('inf')
                    for dest in destinations_needed:
                        travel_time = RouteOptimizer.get_travel_time(travel_times, current_plant, dest)
                        if travel_time < best_time:
                            best_time = travel_time
                            best_dest = dest
                    
                    if best_dest is not None:
                        next_plant = best_dest

            # If absolutely nothing found, just return to start
            if next_plant is None:
                # If all moves are fulfilled and shuttle is empty, we're done
                if (not any(moves > 0 for moves in remaining_moves.values()) and 
                    not any(inventory.get("moves", 0) > 0 for inventory in shuttle_inventory.values())):
                    break
                
                next_plant = start_plant
            
            # Check for infinite loop where we keep revisiting plants without making progress
            if len(route) > len(all_plants) * 3:  # Arbitrary threshold
                total_remaining = sum(remaining_moves.values()) + sum(inventory.get("moves", 0) for inventory in shuttle_inventory.values())
                if total_remaining <= 0.001:  # Using small epsilon for float comparison
                    # Everything is done, we can stop
                    break
                
                # If there's cargo that can't be unloaded for some reason, force visit destinations
                if any(inventory.get("moves", 0) > 0 for inventory in shuttle_inventory.values()):
                    for (_, dest), inventory in shuttle_inventory.items():
                        if inventory.get("moves", 0) > 0 and dest not in route[-3:]:  # Not in recent history
                            next_plant = dest
                            break
            
            # Add next plant to route
            route.append(next_plant)
            operations.append({"plant": next_plant, "load": {}, "unload": {}})
            current_plant = next_plant
        
        # Ensure we return to the starting plant if needed
        if route[-1] != start_plant:
            route.append(start_plant)
            operations.append({"plant": start_plant, "load": {}, "unload": {}})
        
        # Verify all cargo is properly loaded and unloaded
        total_remaining_moves = sum(remaining_moves.values())
        total_inventory_moves = sum(inventory.get("moves", 0) for inventory in shuttle_inventory.values())
        total_cargo_remaining = total_remaining_moves + total_inventory_moves
        
        if total_cargo_remaining > 0.001:  # Using small epsilon for float comparison
            print(f"Warning: Route did not handle all cargo. Remaining: {total_cargo_remaining}")
        
        # Clean up operations - remove empty operations
        for op in operations:
            if not op["load"] and not op["unload"]:
                op["empty"] = True
        
        return route, operations
        
    @staticmethod
    def get_travel_time(travel_times, source_plant, dest_plant):
        """
        Get the travel time between two plants.
        
        Args:
            travel_times (dict): Dictionary mapping (source, dest) to travel time
            source_plant (int): Source plant ID
            dest_plant (int): Destination plant ID
            
        Returns:
            int: Travel time in minutes or default value if not found
        """
        source = source_plant
        dest = dest_plant

        # Check if travel time exists in the matrix
        if (source in travel_times and 
            dest in travel_times[source]):
            return travel_times[source][dest]

        return 15  # Default travel time if not found
    
    @staticmethod
    def calculate_route_statistics(shuttle_id, celky_ids, active_schedule_id, plants, travel_times):
        """
        Calculate statistics for a shuttle route with the given celky assignments,
        taking into account time intervals and frequency length.
        """
        from models.config_module.shuttle import Shuttle
        from models.data_module.celky import Celky
        
        # Get shuttle data
        shuttle = Shuttle.get_by_id(shuttle_id)
        if not shuttle:
            return {"error": "Shuttle not found"}
        
        shift_length_minutes = shuttle["shift_length"] * 60
        shift_change_dest = shuttle["shift_change_dest"]
        break_time = shuttle["break_time"]
        time_for_shift_change = shuttle["time_for_shift_change"]
        shuttle_capacity = shuttle["capacity"]
        shuttle_type = shuttle["shuttle_type"]
        preprah_length = shuttle["preprah_length"]
        preprah_destination = shuttle["preprah_destination"]
        
        # Get celky data
        celky_data = []
        for celky_id in celky_ids:
            celky = Celky.get_celky_by_id(celky_id)
            if celky:
                celky_data.append(celky)
        
        if not celky_data:
            return {
                "total_time": 0,
                "active_time": 0,
                "break_time": break_time,
                "shift_change_time": time_for_shift_change,
                "frequencies": 0,
                "one_freq_time": 0,
                "avg_load": 0,
                "max_capacity": 0,
                "avg_capacity_percent": 0,
                "start_plant": shift_change_dest,
                "end_plant": shift_change_dest,
                "route_details": [],
                "once_per_shift_details": []
            }
        
        # Time interval for calculations (15 minutes)
        time_interval = 15
        
        # Group celky by source-destination with interval data
        grouped_celky = RouteOptimizer.group_celky_by_source_dest(celky_data, time_interval)
        
        # Helper function to calculate operation time
        def calculate_operation_time(moves):
            return moves * 0.76  # Time per move in minutes
        
        # Helper function to simulate route and create route details
        def simulate_route_and_create_details(scenario_grouped_celky, scenario_name):
            # Build the route and operations for this scenario
            route, operations = RouteOptimizer.build_optimal_route_simulation(
                scenario_grouped_celky, 
                shift_change_dest, 
                travel_times, 
                shuttle_capacity
            )
            
            # Build the detailed route with loading/unloading operations
            route_details = []
            current_capacity = 0
            one_freq_time = 0
            avg_capacity_usage = []

            # Check if this is a preprah shuttle
            is_preprah = shuttle_type  == "preprah"
            preprah_time = shuttle.get("preprah_length", 0) if is_preprah else 0
            preprah_destination = shuttle.get("preprah_destination", None) if is_preprah else None
            # Process each stop in the route
            current_preprah_operations = []  # Track operations at current preprah location
            current_preprah_time = 0  # Track accumulated time at current preprah location
            in_preprah_location = False  # Flag if we're currently at a preprah location
                        
            # Process each stop in the route
            for i in range(len(route)):
                current_plant = route[i]
                next_plant = route[i + 1] if i < len(route) - 1 else None
                
                # Get the operations data for the current plant
                current_operations = operations[i]

                # Check if we're at a preprah location
                at_preprah_location = is_preprah and current_plant == preprah_destination


                # If we just arrived at preprah location, reset tracking
                if at_preprah_location and not in_preprah_location:
                    current_preprah_operations = []
                    current_preprah_time = 0
                    in_preprah_location = True
                                
                
                # 1. Handle unloading operations
                unload_operations = current_operations.get("unload", {})
                if unload_operations:
                    for str_key, op_data in unload_operations.items():
                        unload_moves = op_data.get("moves", 0)
                        unloaded_celky_ids = op_data.get("celky_ids", [])
                        
                        if unload_moves > 0:
                            has_operations = True
                            # Convert string key back to tuple for lookup
                            source, dest = map(int, str_key.split(",")) if "," in str_key else (0, 0)
                            source_dest_key = (source, dest)
                            
                            # Collect celky objects
                            unloaded_celky = []
                            for celky in celky_data:
                                if celky["id"] in unloaded_celky_ids:
                                    unloaded_celky.append(celky)
                            
                            # Calculate unloading time based on the actual moves
                            unload_time = calculate_operation_time(unload_moves)
                            
                            op_detail = {
                                "type": "unload",
                                "plant": current_plant,
                                "time": unload_time,
                                "moves": unload_moves,
                                "source_dest_key": source_dest_key,
                                "celky": unloaded_celky,
                                "celky_ids": unloaded_celky_ids,
                                "load_change": -unload_moves,
                                "capacity_used": current_capacity,
                                "capacity_percent": round(current_capacity / shuttle_capacity * 100, 1),
                                "is_preprah_operation": at_preprah_location  # Add this flag
                            }

                            # If at preprah location, track this operation
                            if at_preprah_location:
                                current_preprah_operations.append(op_detail)
                                current_preprah_time += unload_time
                            
                            # Add to route details
                            route_details.append(op_detail)
                            
                            current_capacity = max(0, current_capacity - unload_moves)
                            one_freq_time += unload_time
                            avg_capacity_usage.append(current_capacity / shuttle_capacity * 100)
                
                # 2. Handle loading operations
                load_operations = current_operations.get("load", {})
                if load_operations:
                    for str_key, op_data in load_operations.items():
                        load_moves = op_data.get("moves", 0)
                        loaded_celky_ids = op_data.get("celky_ids", [])
                        
                        if load_moves > 0:
                            has_operations = True
                            # Convert string key back to tuple for lookup
                            source, dest = map(int, str_key.split(",")) if "," in str_key else (0, 0)
                            source_dest_key = (source, dest)
                            
                            # Collect celky objects
                            loaded_celky = []
                            for celky in celky_data:
                                if celky["id"] in loaded_celky_ids:
                                    loaded_celky.append(celky)
                            
                            # Calculate loading time based on the actual moves
                            load_time = calculate_operation_time(load_moves)
                            
                            op_detail = {
                                "type": "load",
                                "plant": current_plant,
                                "time": load_time,
                                "moves": load_moves,
                                "source_dest_key": source_dest_key,
                                "celky": loaded_celky,
                                "celky_ids": loaded_celky_ids,
                                "load_change": load_moves,
                                "capacity_used": current_capacity,
                                "capacity_percent": round(current_capacity / shuttle_capacity * 100, 1),
                                "is_preprah_operation": at_preprah_location  # Add this flag
                            }

                            # If at preprah location, track this operation
                            if at_preprah_location:
                                current_preprah_operations.append(op_detail)
                                current_preprah_time += load_time
                            
                            # Add to route details
                            route_details.append(op_detail)
                            
                            current_capacity += load_moves
                            one_freq_time += load_time
                            avg_capacity_usage.append(current_capacity / shuttle_capacity * 100)
                
                # Check if we're about to leave the preprah location
                leaving_preprah = in_preprah_location and (next_plant is None or next_plant != preprah_destination)
                # If we're leaving preprah and have operations, add the preprah operation
                if leaving_preprah and current_preprah_operations and next_plant is not None:
                    # Add preprah operation at the end, before we leave
                    preprah_op = {
                        "type": "preprah",
                        "plant": current_plant,
                        "time": preprah_time,
                        "celky": [],
                        "load_change": 0,
                        "capacity_used": current_capacity,
                        "capacity_percent": round(current_capacity / shuttle_capacity * 100, 1)
                    }
                    
                    # Add to route details
                    route_details.append(preprah_op)
                
                    # Adjust the total time by replacing individual operations time with preprah time
                    time_difference = preprah_time - current_preprah_time
                    one_freq_time += time_difference
                    
                    # Reset preprah tracking
                    in_preprah_location = False

                if leaving_preprah and current_preprah_operations and next_plant is None:
                    # Add preprah operation at the end, before we leave
                    # Adjust the total time by replacing individual operations time with preprah time
                    time_difference = current_preprah_time
                    one_freq_time -= time_difference
                    
                    # Reset preprah tracking
                    in_preprah_location = False
                    
                # 3. Travel to next plant (only if this isn't the last stop)
                if next_plant is not None:
                    travel_time = RouteOptimizer.get_travel_time(travel_times, current_plant, next_plant)
                    
                    route_details.append({
                        "type": "travel",
                        "from": current_plant,
                        "to": next_plant,
                        "time": travel_time,
                        "celky": [],
                        "load_change": 0,
                        "capacity_used": current_capacity,
                        "capacity_percent": round(current_capacity / shuttle_capacity * 100, 1)
                    })

                    # If we're traveling from preprah location to somewhere else, we're definitely leaving
                    if in_preprah_location and next_plant != preprah_destination:
                        in_preprah_location = False
                                
                    one_freq_time += travel_time
                                
            # Get the max capacity used during the route
            max_capacity = max([detail.get("capacity_used", 0) for detail in route_details]) if route_details else 0
            
            return {
                "route": route,
                "operations": operations,
                "route_details": route_details,
                "one_freq_time": one_freq_time,
                "max_capacity": max_capacity
            }
        
        # Create scenario data for average median and average p90
        avg_median_grouped = RouteOptimizer.create_scenario_grouped_celky(grouped_celky, "median")
        avg_p90_grouped = RouteOptimizer.create_scenario_grouped_celky(grouped_celky, "p90")
        
        # Simulate routes for average scenarios
        avg_median_simulation = simulate_route_and_create_details(avg_median_grouped, "avg_median")
        avg_p90_simulation = simulate_route_and_create_details(avg_p90_grouped, "avg_p90")
        
        # Calculate initial frequency length for each scenario
        median_frequency_time = avg_median_simulation["one_freq_time"]
        p90_frequency_time = avg_p90_simulation["one_freq_time"]
        
        median_frequency_length = math.ceil(median_frequency_time / time_interval) * time_interval
        p90_frequency_length = math.ceil(p90_frequency_time / time_interval) * time_interval
        
        median_intervals_per_freq = int(median_frequency_length / time_interval)
        p90_intervals_per_freq = int(p90_frequency_length / time_interval)
        
        # Find the peak period for median scenario
        median_max_capacity = 0
        median_max_interval_start = 0
        
        # Find the peak period for both median and 90th percentile scenarios
        for start_interval in range(24 * int(60 / time_interval)):
            # Calculate what the capacity would be if we start at this interval
            test_median_grouped = RouteOptimizer.create_scenario_grouped_celky(
                grouped_celky, "median", start_interval, median_intervals_per_freq, time_interval)
            
            # Simulate to get the max capacity
            test_simulation = simulate_route_and_create_details(test_median_grouped, "test_median")
            test_max_capacity = test_simulation["max_capacity"]
            
            # Update if this is higher than current max
            if test_max_capacity > median_max_capacity:
                median_max_capacity = test_max_capacity
                median_max_interval_start = start_interval
        
        # Similar process for P90
        p90_max_capacity = 0
        p90_max_interval_start = 0
        
        for start_interval in range(24 * int(60 / time_interval)):
            # Calculate what the capacity would be if we start at this interval
            test_p90_grouped = RouteOptimizer.create_scenario_grouped_celky(
                grouped_celky, "p90", start_interval, p90_intervals_per_freq, time_interval)
            
            # Simulate to get the max capacity
            test_simulation = simulate_route_and_create_details(test_p90_grouped, "test_p90")
            test_max_capacity = test_simulation["max_capacity"]
            
            # Update if this is higher than current max
            if test_max_capacity > p90_max_capacity:
                p90_max_capacity = test_max_capacity
                p90_max_interval_start = start_interval
        
        # Now create and simulate the peak scenarios
        peak_median_grouped = RouteOptimizer.create_scenario_grouped_celky(
            grouped_celky, "median", median_max_interval_start, median_intervals_per_freq, time_interval)
        
        peak_p90_grouped = RouteOptimizer.create_scenario_grouped_celky(
            grouped_celky, "p90", p90_max_interval_start, p90_intervals_per_freq, time_interval)
        
        # Simulate peak routes
        peak_median_simulation = simulate_route_and_create_details(peak_median_grouped, "peak_median")
        peak_p90_simulation = simulate_route_and_create_details(peak_p90_grouped, "peak_p90")
        

        def once_per_shift_info(route, shift_change_dest, travel_times, time_for_shift_change, shift_length_minutes, break_time):
            # Create once_per_shift route details
            once_per_shift_details = []
            
            # Add shift change operation
            once_per_shift_details.append({
                "type": "shift_change",
                "plant": shift_change_dest,
                "time": time_for_shift_change,
                "load_change": 0,
                "capacity_used": 0,
                "capacity_percent": 0
            })
            
            initial_travel_time = 0
            final_travel_time = 0
            
            # Check if shift_change_dest is in the route
            if shift_change_dest != route[0]:
                initial_travel_time = RouteOptimizer.get_travel_time(travel_times, shift_change_dest, route[0])
                once_per_shift_details.append({
                    "type": "travel",
                    "from": shift_change_dest,
                    "to": route[0],
                    "time": initial_travel_time,
                    "celky": [],
                    "load_change": 0,
                    "capacity_used": 0,
                    "capacity_percent": 0
                })
            else:
                initial_travel_time = 0
                once_per_shift_details.append({
                    "type": "travel",
                    "from": shift_change_dest,
                    "to": shift_change_dest,
                    "time": initial_travel_time,
                    "celky": [],
                    "load_change": 0,
                    "capacity_used": 0,
                    "capacity_percent": 0
                })

            if shift_change_dest != route[-1]:
                final_travel_time = RouteOptimizer.get_travel_time(travel_times, route[-1], shift_change_dest)
                once_per_shift_details.append({
                    "type": "travel",
                    "from": route[-1],
                    "to": shift_change_dest,
                    "time": final_travel_time,
                    "celky": [],
                    "load_change": 0,
                    "capacity_used": 0,
                    "capacity_percent": 0
                })
            else:
                initial_travel_time = 0
                once_per_shift_details.append({
                    "type": "travel",
                    "from": shift_change_dest,
                    "to": shift_change_dest,
                    "time": initial_travel_time,
                    "celky": [],
                    "load_change": 0,
                    "capacity_used": 0,
                    "capacity_percent": 0
                })

            # Total once-per-shift time
            once_per_shift_time = initial_travel_time + final_travel_time + time_for_shift_change
            
            # Calculate frequencies for each scenario
            available_time = shift_length_minutes - once_per_shift_time - break_time

            return {
                "route": route,
                "available_time": available_time,
                "once_per_shift_details": once_per_shift_details,
                "once_per_shift_time": once_per_shift_time
            }
        
        # Calculate once-per-shift information for each scenario
        median_once_per_shift_info = once_per_shift_info(avg_median_simulation["route"], shift_change_dest, travel_times, time_for_shift_change, shift_length_minutes, break_time)
        peak_median_once_per_shift_info = once_per_shift_info(peak_median_simulation["route"], shift_change_dest, travel_times, time_for_shift_change, shift_length_minutes, break_time)
        p90_once_per_shift_info = once_per_shift_info(avg_p90_simulation["route"], shift_change_dest, travel_times, time_for_shift_change, shift_length_minutes, break_time)
        peak_p90_once_per_shift_info = once_per_shift_info(peak_p90_simulation["route"], shift_change_dest, travel_times, time_for_shift_change, shift_length_minutes, break_time)
            
        
        avg_median_frequencies = int(median_once_per_shift_info["available_time"] / median_frequency_time) if median_frequency_time > 0 else 0
        avg_p90_frequencies = int(p90_once_per_shift_info["available_time"] / p90_frequency_time) if p90_frequency_time > 0 else 0
        
        # Calculate frequencies for peak periods
        peak_median_frequency_time = peak_median_simulation["one_freq_time"]
        peak_median_frequency_length = math.ceil(peak_median_frequency_time / time_interval) * time_interval
        peak_median_frequencies = int(peak_median_once_per_shift_info["available_time"] / peak_median_frequency_time) if peak_median_frequency_time > 0 else 0
        
        peak_p90_frequency_time = peak_p90_simulation["one_freq_time"]
        peak_p90_frequency_length = math.ceil(peak_p90_frequency_time / time_interval) * time_interval
        peak_p90_frequencies = int(peak_p90_once_per_shift_info["available_time"] / peak_p90_frequency_time) if peak_p90_frequency_time > 0 else 0

        # Calculate active time for each scenario
        avg_median_active_time = (avg_median_frequencies * median_frequency_time) + median_once_per_shift_info["once_per_shift_time"]
        avg_p90_active_time = (avg_p90_frequencies * p90_frequency_time) + p90_once_per_shift_info["once_per_shift_time"]
        peak_median_active_time = (peak_median_frequencies * peak_median_frequency_time) + peak_median_once_per_shift_info["once_per_shift_time"]
        peak_p90_active_time = (peak_p90_frequencies * peak_p90_frequency_time) + peak_p90_once_per_shift_info["once_per_shift_time"]

        # Check if shift change destination is in the route
        shift_change_in_route = shift_change_dest in avg_median_simulation["route"]
        
        # Return the final statistics with all four scenarios and their once-per-shift details
        return {
            "total_time": shift_length_minutes,
            "active_time": avg_median_active_time,  # Use average median as the default
            "break_time": break_time,
            "shift_change_time": time_for_shift_change,

            # Add shuttle type information
            "shuttle_type": shuttle["shuttle_type"],
            "preprah_length": preprah_length if "preprah_length" in shuttle else 0,
            "preprah_destination": preprah_destination if "preprah_destination" in shuttle else None,
            
            # Average median scenario
            "frequencies": avg_median_frequencies,  # For backward compatibility
            "median_frequencies": avg_median_frequencies,
            "one_freq_time": median_frequency_time,  # For backward compatibility

            "median_frequency_time": median_frequency_time,
            "median_frequency_length": median_frequency_length,
            "median_route_details": avg_median_simulation["route_details"],
            "median_max_capacity": avg_median_simulation["max_capacity"],
            "median_active_time": avg_median_active_time,
            "median_max_interval": median_max_interval_start * time_interval,
            "median_once_per_shift_details": median_once_per_shift_info["once_per_shift_details"],
            
            # Peak median scenario
            "peak_median_frequencies": peak_median_frequencies,
            "peak_median_frequency_time": peak_median_frequency_time,
            "peak_median_frequency_length": peak_median_frequency_length,
            "peak_median_route_details": peak_median_simulation["route_details"],
            "peak_median_max_capacity": median_max_capacity,
            "peak_median_active_time": peak_median_active_time,
            "peak_median_once_per_shift_details": peak_median_once_per_shift_info["once_per_shift_details"],
            
            # Average P90 scenario
            "p90_frequencies": avg_p90_frequencies,
            "p90_frequency_time": p90_frequency_time,
            "p90_frequency_length": p90_frequency_length,
            "p90_route_details": avg_p90_simulation["route_details"],
            "p90_max_capacity": avg_p90_simulation["max_capacity"],
            "p90_active_time": avg_p90_active_time,
            "p90_max_interval": p90_max_interval_start * time_interval,
            "p90_once_per_shift_details": p90_once_per_shift_info["once_per_shift_details"],
            
            # Peak P90 scenario
            "peak_p90_frequencies": peak_p90_frequencies,
            "peak_p90_frequency_time": peak_p90_frequency_time,
            "peak_p90_frequency_length": peak_p90_frequency_length,
            "peak_p90_route_details": peak_p90_simulation["route_details"],
            "peak_p90_max_capacity": p90_max_capacity,
            "peak_p90_active_time": peak_p90_active_time,
            "peak_p90_once_per_shift_details": peak_p90_once_per_shift_info["once_per_shift_details"],
            
            # General information for backward compatibility
            "once_per_shift_time": median_once_per_shift_info["once_per_shift_time"],
            "once_per_shift_details": median_once_per_shift_info["once_per_shift_details"],
            "start_plant": shift_change_dest if shift_change_in_route else avg_median_simulation["route"][0],
            "first_plant": avg_median_simulation["route"][0],
            "end_plant": shift_change_dest if shift_change_in_route else avg_median_simulation["route"][-1],
            "route": avg_median_simulation["route"]
        }
    
    @staticmethod
    def get_assignment_statistics(shuttle_id, schedule_id):
        """
        Get statistics for a specific shuttle's assignments.
        
        Args:
            shuttle_id (int): ID of the shuttle
            schedule_id (int): ID of the schedule
            
        Returns:
            dict: Statistics for the shuttle's assignments or None if not found
        """
        return ShuttleStatistics.get_by_shuttle_and_schedule(shuttle_id, schedule_id)
