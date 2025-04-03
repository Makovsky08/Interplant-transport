"""
Resource-Constrained Multi-Project Scheduling Problem (RCMPSP) Simulation Module
for optimizing inter-facility shuttle schedules.

This module implements a genetic algorithm approach to solve the RCMPSP
for optimizing shuttle schedules based on route statistics.
"""

import random
import json
import math
import time
from datetime import datetime, timedelta
from itertools import groupby
import copy
from deap import base, creator, tools, algorithms

class ScheduleOptimizer:
    """
    Shuttle Schedule Optimizer using genetic algorithms to solve RCMPSP.
    """
    
    def __init__(self, shuttles, plants, travel_times, start_time="06:00"):
        """
        Initialize the schedule optimizer.
        
        Args:
            shuttles (list): List of shuttle dictionaries with their properties
            plants (list): List of plant dictionaries with their properties
            travel_times (dict): Dictionary of travel times between plants
            start_time (str): Start time for the schedule in "HH:MM" format
        """
        self.shuttles = shuttles
        self.plants = plants
        self.travel_times = travel_times
        self.start_time = datetime.strptime(start_time, "%H:%M")
        
        # Create a lookup for plants by identifier
        self.plants_by_id = {plant['identifier']: plant for plant in plants}
        
        # Store route statistics for each shuttle
        self.shuttle_stats = {}
        
        # Store the best schedule found by GA
        self.best_schedule = None
        
        # GA parameters
        self.population_size = 300
        self.generations = 90
        self.crossover_prob = 0.7
        self.mutation_prob = 0.2
        self.tournament_size = 3

    def load_shuttle_stats(self, shuttle_id, route_statistics, scenario='median'):
        """
        Load route statistics for a shuttle.
        
        Args:
            shuttle_id (int): ID of the shuttle
            route_statistics (dict): Statistics including route details
            scenario (str): Scenario to use ('median', 'peak_median', 'p90', 'peak_p90')
        """
        if shuttle_id not in self.shuttle_stats:
            self.shuttle_stats[shuttle_id] = {}
        
        # Store the relevant route details based on scenario
        route_details_key = f"{scenario}_route_details"
        once_per_shift_details = route_statistics.get(f'{scenario}_once_per_shift_details', 
                                                     route_statistics.get('once_per_shift_details', []))
        
        self.shuttle_stats[shuttle_id][scenario] = {
            'frequency_time': route_statistics.get(f"{scenario}_frequency_time", 0),
            'frequencies': route_statistics.get(f"{scenario}_frequencies", 0),
            'max_capacity': route_statistics.get(f"{scenario}_max_capacity", 0),
            'route_details': route_statistics.get(route_details_key, []),
            'once_per_shift_details': once_per_shift_details,
            'active_time': route_statistics.get(f"{scenario}_active_time", 0)
        }

    def get_shuttle_by_id(self, shuttle_id):
        """Get shuttle object by ID."""
        for shuttle in self.shuttles:
            if shuttle['id'] == shuttle_id:
                return shuttle
        return None

    def create_initial_schedule(self, shuttle_id, scenario='median'):
        """
        Create an initial schedule for a shuttle WITHOUT breaks.
        Breaks will be added later by the genetic algorithm.
        
        Args:
            shuttle_id (int): ID of the shuttle
            scenario (str): Scenario to use
            
        Returns:
            dict: Schedule details including start times for each operation
        """
        shuttle = self.get_shuttle_by_id(shuttle_id)
        if not shuttle:
            return None
        
        shuttle_stats = self.shuttle_stats.get(shuttle_id, {}).get(scenario, {})
        if not shuttle_stats:
            return None
        
        route_details = shuttle_stats.get('route_details', [])
        once_per_shift_details = shuttle_stats.get('once_per_shift_details', [])
        frequencies = shuttle_stats.get('frequencies', 0)
        
        # Start operations from the start time
        current_time = self.start_time
        shift_length_minutes = shuttle['shift_length'] * 60
        break_time = shuttle['break_time']
        break_each_minutes = shuttle['break_each']
        shift_change_dest = shuttle['shift_change_dest']
        
        # Determine if this is a preprah shuttle
        is_preprah = shuttle['shuttle_type'] == 'preprah'
        preprah_destination = shuttle.get('preprah_destination')
        
        # Create schedule operations list
        operations = []
        
        # Parse the once-per-shift operations
        # Note: once_per_shift_details contain operations that need to be done once per shift
        # First operation: Travel from shift_change_dest to the starting plant (if needed)
        start_plant = None
        end_plant = None
        
        # Get the first plant in the route (start plant)
        if route_details:
            first_op = route_details[0]
            if first_op['type'] == 'travel':
                start_plant = first_op['from']
            else:
                start_plant = first_op['plant']
        
        # Get the last plant in the route (end plant)
        if route_details:
            last_op = route_details[-1]
            if last_op['type'] == 'travel':
                end_plant = last_op['to']
            else:
                end_plant = last_op['plant']
        
        # If we have a specific travel in once_per_shift_details from shift_change_dest to start_plant, use it
        has_initial_travel = False
        has_final_travel = False
        has_shift_change = False
        
        for op in once_per_shift_details:
            op_type = op.get('type', '')
            
            # Skip operations with zero time
            if op.get('time', 0) <= 0:
                continue
            
            if op_type == 'travel' and op.get('from') == shift_change_dest and op.get('to') == start_plant:
                # This is the initial travel from shift_change_dest to start_plant
                operations.append({
                    'type': 'travel',
                    'start_time': current_time,
                    'end_time': current_time + timedelta(minutes=op.get('time', 0)),
                    'duration': op.get('time', 0),
                    'plant': None,
                    'from_plant': op.get('from'),
                    'to_plant': op.get('to'),
                    'frequency_num': 0,  # 0 indicates once-per-shift
                    'operation_num': len(operations)
                })
                current_time += timedelta(minutes=op.get('time', 0))
                has_initial_travel = True
            
            elif op_type == 'travel' and op.get('from') == end_plant and op.get('to') == shift_change_dest:
                # This is the final travel from end_plant to shift_change_dest
                # We'll add this later at the end of the schedule
                has_final_travel = True
            
            elif op_type == 'shift_change' and op.get('plant') == shift_change_dest:
                # This is the final shift change operation
                # We'll add this later at the end of the schedule
                has_shift_change = True
                
        # If no explicit initial travel was found and we need to travel from shift_change_dest to start_plant
        if not has_initial_travel and start_plant is not None and start_plant != shift_change_dest:
            travel_time = self._get_travel_time(shift_change_dest, start_plant)
            operations.append({
                'type': 'travel',
                'start_time': current_time,
                'end_time': current_time + timedelta(minutes=travel_time),
                'duration': travel_time,
                'plant': None,
                'from_plant': shift_change_dest,
                'to_plant': start_plant,
                'frequency_num': 0,  # 0 indicates once-per-shift
                'operation_num': len(operations)
            })
            current_time += timedelta(minutes=travel_time)
        
        # Track preprah ramp info
        preprah_ramp_info = None
        if is_preprah and preprah_destination:
            # For preprah shuttles, one ramp is constantly used at preprah destination
            preprah_ramp_info = {
                'plant': preprah_destination,
                'start_time': self.start_time,
                'end_time': self.start_time + timedelta(minutes=shift_length_minutes)
            }
        
        # Schedule route frequencies
        for freq_num in range(1, frequencies + 1):
            # Add route operations for this frequency
            # Track whether we've added a preprah operation in this cycle
            current_preprah_operation = None
            preprah_operations_to_skip = set()  # Track load/unload operations in preprah destination
            preprah_start_time = None  # Start time of the current preprah operation
            
            # First pass: identify preprah operation and operations to skip
            if is_preprah and preprah_destination:
                for i, op in enumerate(route_details):
                    op_type = op.get('type', '')
                    op_plant = op.get('plant')
                    is_preprah_op = op.get('is_preprah_operation', False)
                    
                    # If this is a preprah operation, remember it
                    if op_type == 'preprah' and op_plant == preprah_destination:
                        preprah_start_time = current_time
                        current_preprah_operation = {
                            'index': i,
                            'time': op.get('time', 0)
                        }
                    
                    # If this is a load/unload at preprah destination, mark to skip
                    elif op_type in ['load', 'unload'] and is_preprah_op and op_plant == preprah_destination:
                        preprah_operations_to_skip.add(i)
            
            # Now process all operations
            for i, op in enumerate(route_details):
                op_type = op.get('type', '')
                op_time = op.get('time', 0)
                
                # Skip operations with zero time
                if op_time <= 0:
                    continue
                
                # Skip load/unload operations at preprah destination
                if i in preprah_operations_to_skip:
                    continue
                
                # Check if this is the preprah operation we identified
                is_current_preprah = current_preprah_operation and i == current_preprah_operation['index']
                
                # For preprah operations, we need to handle them specially
                if is_current_preprah:
                    operation = {
                        'type': 'preprah',
                        'start_time': current_time,
                        'end_time': current_time + timedelta(minutes=op_time),
                        'duration': op_time,
                        'plant': op.get('plant'),
                        'from_plant': None,
                        'to_plant': None,
                        'frequency_num': freq_num,
                        'operation_num': len(operations),
                        'is_preprah_operation': True,
                        'uses_two_ramps': True  # Flag that this operation uses 2 ramps
                    }
                    
                    operations.append(operation)
                    current_time += timedelta(minutes=op_time)
                    
                # For travel operations
                elif op_type == 'travel':
                    operation = {
                        'type': op_type,
                        'start_time': current_time,
                        'end_time': current_time + timedelta(minutes=op_time),
                        'duration': op_time,
                        'plant': None,
                        'from_plant': op.get('from'),
                        'to_plant': op.get('to'),
                        'frequency_num': freq_num,
                        'operation_num': len(operations),
                        'is_preprah_operation': False,
                        'load_change': op.get('load_change', 0),
                        'capacity_percent': op.get('capacity_percent', 0),
                        'moves': op.get('moves', 0),
                        'source_dest_key': op.get('source_dest_key', None)
                    }
                    
                    operations.append(operation)
                    current_time += timedelta(minutes=op_time)
                    
                # For other operations (load, unload, etc. but not at preprah destination)
                elif op_type != 'preprah':
                    # Only add if this is not a preprah-related operation we're skipping
                    is_preprah_op = op.get('is_preprah_operation', False)
                    
                    # Skip preprah operations that aren't the main preprah op
                    if is_preprah_op and not is_current_preprah:
                        continue
                    
                    operation = {
                        'type': op_type,
                        'start_time': current_time,
                        'end_time': current_time + timedelta(minutes=op_time),
                        'duration': op_time,
                        'plant': op.get('plant'),
                        'from_plant': None,
                        'to_plant': None,
                        'frequency_num': freq_num,
                        'operation_num': len(operations),
                        'is_preprah_operation': is_preprah_op,
                        'load_change': op.get('load_change', 0),
                        'capacity_percent': op.get('capacity_percent', 0),
                        'moves': op.get('moves', 0),
                        'source_dest_key': op.get('source_dest_key', None)
                    }
                    
                    operations.append(operation)
                    current_time += timedelta(minutes=op_time)
            
            # Check if we've exceeded shift length
            if (current_time - self.start_time).total_seconds() / 60 > shift_length_minutes:
                # We've gone beyond the shift length, so stop adding frequencies
                break
        
        # Add final travel operation to return to shift change destination if needed
        # First determine the last location
        last_plant = None
        if operations:
            last_op = operations[-1]
            if last_op['type'] == 'travel':
                last_plant = last_op['to_plant']
            else:
                last_plant = last_op['plant']
        
        # If we have a specific travel in once_per_shift_details for the return trip, use it
        for op in once_per_shift_details:
            op_type = op.get('type', '')
            
            # Skip operations with zero time
            if op.get('time', 0) <= 0:
                continue
            
            if op_type == 'travel' and op.get('from') == last_plant and op.get('to') == shift_change_dest:
                # This is the final travel from last_plant to shift_change_dest
                operations.append({
                    'type': 'travel',
                    'start_time': current_time,
                    'end_time': current_time + timedelta(minutes=op.get('time', 0)),
                    'duration': op.get('time', 0),
                    'plant': None,
                    'from_plant': op.get('from'),
                    'to_plant': op.get('to'),
                    'frequency_num': frequencies + 1,
                    'operation_num': len(operations)
                })
                current_time += timedelta(minutes=op.get('time', 0))
                has_final_travel = True
        
        # If no explicit final travel was found and we need to travel from last_plant to shift_change_dest
        if not has_final_travel and last_plant is not None and last_plant != shift_change_dest:
            travel_time = self._get_travel_time(last_plant, shift_change_dest)
            operations.append({
                'type': 'travel',
                'start_time': current_time,
                'end_time': current_time + timedelta(minutes=travel_time),
                'duration': travel_time,
                'plant': None,
                'from_plant': last_plant,
                'to_plant': shift_change_dest,
                'frequency_num': frequencies + 1,
                'operation_num': len(operations)
            })
            current_time += timedelta(minutes=travel_time)
        
        # Add final shift change
        shift_change_time = shuttle['time_for_shift_change']
        # Look for a specific shift_change operation in once_per_shift_details
        for op in once_per_shift_details:
            if op.get('type') == 'shift_change' and op.get('plant') == shift_change_dest:
                shift_change_time = op.get('time', shift_change_time)
                break
        
        operations.append({
            'type': 'shift_change',
            'start_time': current_time,
            'end_time': current_time + timedelta(minutes=shift_change_time),
            'duration': shift_change_time,
            'plant': shift_change_dest,
            'from_plant': None,
            'to_plant': None,
            'frequency_num': frequencies + 1,
            'operation_num': len(operations)
        })
        
        return {
            'shuttle_id': shuttle_id,
            'operations': operations,
            'scenario': scenario,
            'frequencies_completed': frequencies,
            'total_time': (operations[-1]['end_time'] - self.start_time).total_seconds() / 60,
            'preprah_ramp_info': preprah_ramp_info
        }

    def _get_travel_time(self, source_plant, dest_plant):
        """Get travel time between two plants, with fallback default."""
        if source_plant is None or dest_plant is None:
            return 15  # Default if plants are not specified
            
        if self.travel_times and source_plant in self.travel_times and dest_plant in self.travel_times[source_plant]:
            return self.travel_times[source_plant][dest_plant]
        return 15  # Default travel time if not specified

    def optimize_schedules(self, scenario='median'):
        """
        Run the genetic algorithm to optimize schedules for all shuttles.
        
        Args:
            scenario (str): Scenario to use for optimization
            
        Returns:
            dict: Optimized schedule for all shuttles
        """
        # Create initial schedules for all shuttles
        initial_schedules = {}
        for shuttle_id in self.shuttle_stats.keys():
            schedule = self.create_initial_schedule(shuttle_id, scenario)
            if schedule:
                initial_schedules[shuttle_id] = schedule
        
        if not initial_schedules:
            return None
            
        # Set up the genetic algorithm
        self._setup_ga(initial_schedules)
        
        # Run the genetic algorithm
        optimized_schedules = self._run_ga(initial_schedules)
        
        return optimized_schedules
    
    def _apply_breaks(self, break_placements, schedules):
        """
        Apply breaks to schedules according to break_placements.
        
        The genetic algorithm determines where to place breaks to minimize resource conflicts.
        Break placement is encoded in the individual's genome.
        
        Args:
            break_placements (list): List of break placement strategies for each shuttle
            schedules (dict): Original schedules without breaks
            
        Returns:
            dict: Modified schedules with breaks inserted
        """
        modified_schedules = copy.deepcopy(schedules)
        
        try:
            for i, (shuttle_id, schedule) in enumerate(modified_schedules.items()):
                # Get the break placements for this shuttle
                if i >= len(break_placements):
                    print(f"Warning: Not enough break placements ({len(break_placements)}) for all schedules ({len(modified_schedules)})")
                    continue
                
                shuttle = self.get_shuttle_by_id(shuttle_id)
                if not shuttle:
                    continue
                    
                shuttle_breaks = break_placements[i]
                operations = schedule['operations']
                
                # Verify the lengths match
                if len(operations) != len(shuttle_breaks):
                    # Adjust lengths if needed
                    if len(operations) > len(shuttle_breaks):
                        # Extend shuttle_breaks with zeros
                        shuttle_breaks.extend([0] * (len(operations) - len(shuttle_breaks)))
                    else:
                        # Truncate shuttle_breaks
                        shuttle_breaks = shuttle_breaks[:len(operations)]
                
                # Keep track of the time offset as we add breaks
                time_offset = timedelta(minutes=0)
                new_operations = []
                
                # Track break requirements
                required_short_breaks = math.floor(shuttle['shift_length'] / 4)  # One 10-min break every 4 hours
                required_lunch_break = 1  # One 20-min lunch break per shift
                
                # Track break usage
                used_short_breaks = 0
                used_lunch_break = 0
                total_break_minutes = 0
                
                # Determine total break time based on shift length
                required_break_time = shuttle['break_time']  # 30 min for 8h, 60 min for 12h
                
                # Process each operation and add breaks where indicated
                for j, (op, break_type) in enumerate(zip(operations, shuttle_breaks)):
                    # Create a copy of the operation with adjusted times
                    adjusted_op = copy.deepcopy(op)
                    adjusted_op['start_time'] += time_offset
                    adjusted_op['end_time'] += time_offset
                    
                    # Add the adjusted operation to the new list
                    new_operations.append(adjusted_op)
                    
                    # If there's a break after this operation, add it
                    if break_type > 0:
                        # Determine break length in minutes
                        break_minutes = 0
                        if break_type == 1 and used_short_breaks < required_short_breaks:  # 10-min break (short)
                            break_minutes = 10
                            used_short_breaks += 1
                        elif break_type == 2 and used_lunch_break < required_lunch_break:  # 20-min break (lunch)
                            break_minutes = 30
                            used_lunch_break += 1
                        elif break_type == 3:
                            break_minutes = 6
                        elif break_type == 4: 
                            break_minutes = 3
                        elif break_type == 5: 
                            break_minutes = 2
                        elif break_type == 6:  
                            break_minutes = 10
                        elif break_type == 7:  
                            break_minutes = 15
                        elif break_type == 8:  
                            break_minutes = 20
                        
                        # Check if adding this break would exceed total allowed break time
                        if total_break_minutes + break_minutes > required_break_time + 15:  # Allow 15 min extra for flexibility
                            break_minutes = 0  # Skip this break
                            
                        if break_minutes > 0:
                            total_break_minutes += break_minutes
                            
                            # Get location for the break - happens at the current location
                            break_plant = None
                            if adjusted_op['type'] == 'travel':
                                break_plant = adjusted_op['to_plant']
                            else:
                                break_plant = adjusted_op['plant']
                            
                            # Create a new break operation
                            break_op = {
                                'type': 'break',
                                'start_time': adjusted_op['end_time'],
                                'end_time': adjusted_op['end_time'] + timedelta(minutes=break_minutes),
                                'duration': break_minutes,
                                'plant': break_plant,
                                'from_plant': None,
                                'to_plant': None,
                                'frequency_num': adjusted_op.get('frequency_num', 0),
                                'operation_num': len(operations) + j,  # Assign unique operation number
                                'is_break': True
                            }
                            
                            # Add the break operation to the new list
                            new_operations.append(break_op)
                            
                            # Update time offset for subsequent operations
                            time_offset += timedelta(minutes=break_minutes)
                
                # Make sure minimum break requirements are met
                if total_break_minutes < required_break_time:
                    # If we're missing breaks, add them at the end if possible
                    last_op = new_operations[-1]
                    remaining_break_time = required_break_time - total_break_minutes
                    
                    # Get location for the break - happens at the last location
                    break_plant = None
                    if last_op['type'] == 'travel':
                        break_plant = last_op['to_plant']
                    else:
                        break_plant = last_op['plant']
                    
                    if remaining_break_time > 0:
                        # Add the remaining break time
                        break_op = {
                            'type': 'break',
                            'start_time': last_op['end_time'],
                            'end_time': last_op['end_time'] + timedelta(minutes=remaining_break_time),
                            'duration': remaining_break_time,
                            'plant': break_plant,
                            'from_plant': None,
                            'to_plant': None,
                            'frequency_num': last_op.get('frequency_num', 0),
                            'operation_num': len(new_operations),
                            'is_break': True
                        }
                        
                        # Add the break operation to the new list
                        new_operations.append(break_op)
                        
                        # Update time offset for final operations
                        time_offset += timedelta(minutes=remaining_break_time)
                
                # Replace the original operations with the new ones
                schedule['operations'] = new_operations
                
                # Renumber operations
                for i, op in enumerate(new_operations):
                    op['operation_num'] = i
        
        except Exception as e:
            print(f"Error applying breaks: {e}")
            import traceback
            traceback.print_exc()
            return schedules  # Return original schedules on error
            
        return modified_schedules

    def _setup_ga(self, initial_schedules):
        """Set up the genetic algorithm components with enhanced mutation and break placement strategies."""
        # Clear any existing creator attributes to avoid conflicts with multiple runs
        if hasattr(creator, "FitnessMin"):
            del creator.FitnessMin
        if hasattr(creator, "Individual"):
            del creator.Individual
            
        # Define fitness class with weights (minimize negative fitness)
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
        
        # Define individual class
        creator.create("Individual", list, fitness=creator.FitnessMin)
        
        # Set up toolbox
        self.toolbox = base.Toolbox()
        
        # Store resource usage patterns for collision-aware mutations
        self.resource_usage_patterns = self._analyze_resource_usage(initial_schedules)
        self.high_contention_periods = self._identify_high_contention_periods(self.resource_usage_patterns)
        
        def create_individual():
            """
            Create a genetic algorithm individual that represents break placements.
            Each individual contains an array of break placements for each shuttle.
            
            Break types:
            0 = no break
            1 = 10-min short break (required every 4 hours)  
            2 = 20-min lunch break (required once per shift)
            3 = 5-min micro break (flexible for collision avoidance)
            4 = 2-min micro break (flexible for collision avoidance)
            5 = 1-min micro break (flexible for collision avoidance)
            6 = 15-min medium break (new)
            7 = 25-min long break (new)
            8 = 30-min extended break (new)
            """
            individual = []
            
            for shuttle_id, schedule in initial_schedules.items():
                shuttle = self.get_shuttle_by_id(shuttle_id)
                shift_length = shuttle['shift_length']
                
                # Determine the number of operations in the schedule
                operations = schedule['operations']
                num_operations = len(operations)
                
                # Create an array of break flags for each operation
                break_placements = [0] * num_operations
                
                # Calculate required breaks
                required_short_breaks = math.floor(shift_length / 4)  # One 10-min break every 4 hours
                required_lunch_break = 1  # One 20-min lunch break per shift
                
                # Build a map of all operations at each plant
                plant_operations = {}  # Dictionary of plant_id -> list of operation indices
                
                # Group operations by plant
                for i, op in enumerate(operations):
                    # Skip travel operations when grouping
                    if op['type'] == 'travel':
                        continue
                        
                    plant_id = op.get('plant')
                    if plant_id:
                        if plant_id not in plant_operations:
                            plant_operations[plant_id] = []
                        plant_operations[plant_id].append(i)
                
                # Find valid break positions (after completing operations at a plant)
                valid_break_positions = []
                for i, op in enumerate(operations):
                    if op['type'] == 'travel' and i > 0:
                        # Get previous operation
                        prev_op = operations[i-1]
                        if prev_op['type'] != 'travel':
                            prev_plant = prev_op.get('plant')
                            
                            # Check if we completed all operations at this plant
                            if prev_plant in plant_operations:
                                ops_at_plant = plant_operations[prev_plant]
                                if ops_at_plant and max(ops_at_plant) == i-1:
                                    # This travel follows the last operation at the plant
                                    valid_break_positions.append(i-1)  # Break after last plant operation
                
                # Also add last operations at each plant as valid break positions
                for plant_id, ops in plant_operations.items():
                    if ops:
                        valid_break_positions.append(max(ops))
                
                # Remove duplicates and sort
                valid_break_positions = sorted(list(set(valid_break_positions)))
                
                # Calculate ideal times for breaks (in minutes since shift start)
                ideal_break_times = []
                for i in range(required_short_breaks):
                    ideal_time = (i + 1) * 240  # 240 minutes = 4 hours
                    ideal_break_times.append(ideal_time)
                
                ideal_lunch_time = shift_length * 30  # Ideally in the middle of the shift
                
                # Place lunch break near the middle of the shift
                lunch_placed = False
                best_lunch_pos = None
                best_lunch_diff = float('inf')
                
                # Find the operation closest to middle of shift
                for pos in valid_break_positions:
                    op = operations[pos]
                    op_time = op.get('start_time')
                    
                    if op_time:
                        # Calculate minutes since shift start
                        op_minutes = 0
                        if isinstance(op_time, datetime):
                            op_minutes = (op_time - self.start_time).total_seconds() / 60
                        else:
                            # Try to parse string time
                            try:
                                if 'T' in op_time:
                                    time_part = op_time.split('T')[1]
                                else:
                                    time_part = op_time
                                    
                                if ':' in time_part:
                                    parts = time_part.split(':')
                                    start_hour = int(parts[0])
                                    start_minute = int(parts[1])
                                    op_minutes = (start_hour - self.start_time.hour) * 60 + (start_minute - self.start_time.minute)
                            except:
                                op_minutes = 0
                        
                        # Find position closest to lunch time
                        lunch_diff = abs(op_minutes - ideal_lunch_time)
                        if lunch_diff < best_lunch_diff:
                            best_lunch_diff = lunch_diff
                            best_lunch_pos = pos
                
                # Add lunch break at best position
                if best_lunch_pos is not None:
                    break_placements[best_lunch_pos] = 2  # 20-min lunch break
                    lunch_placed = True
                
                # Place short breaks at operations closest to ideal times
                short_breaks_placed = 0
                for ideal_time in ideal_break_times:
                    best_pos = None
                    best_diff = float('inf')
                    
                    # Find operation closest to this ideal time
                    for pos in valid_break_positions:
                        # Skip if already has a break
                        if break_placements[pos] > 0:
                            continue
                            
                        op = operations[pos]
                        op_time = op.get('start_time')
                        
                        if op_time:
                            # Calculate minutes since shift start
                            op_minutes = 0
                            if isinstance(op_time, datetime):
                                op_minutes = (op_time - self.start_time).total_seconds() / 60
                            else:
                                # Try to parse string time
                                try:
                                    if 'T' in op_time:
                                        time_part = op_time.split('T')[1]
                                    else:
                                        time_part = op_time
                                        
                                    if ':' in time_part:
                                        parts = time_part.split(':')
                                        start_hour = int(parts[0])
                                        start_minute = int(parts[1])
                                        op_minutes = (start_hour - self.start_time.hour) * 60 + (start_minute - self.start_time.minute)
                                except:
                                    op_minutes = 0
                            
                            # Find position closest to ideal time
                            time_diff = abs(op_minutes - ideal_time)
                            if time_diff < best_diff:
                                best_diff = time_diff
                                best_pos = pos
                    
                    # Add short break at best position
                    if best_pos is not None:
                        break_placements[best_pos] = 1  # 10-min short break
                        short_breaks_placed += 1
                
                # Ensure at least one break in the first 60 minutes (first hour)
                early_break_added = False
                for i in valid_break_positions:
                    if i >= len(operations):
                        continue
                        
                    op = operations[i]
                    op_time = op.get('start_time')
                    
                    # Calculate minutes since shift start
                    op_minutes = 0
                    if op_time:
                        if isinstance(op_time, datetime):
                            op_minutes = (op_time - self.start_time).total_seconds() / 60
                        else:
                            # Try to parse string time
                            try:
                                if 'T' in op_time:
                                    time_part = op_time.split('T')[1]
                                else:
                                    time_part = op_time
                                    
                                if ':' in time_part:
                                    parts = time_part.split(':')
                                    start_hour = int(parts[0])
                                    start_minute = int(parts[1])
                                    op_minutes = (start_hour - self.start_time.hour) * 60 + (start_minute - self.start_time.minute)
                            except:
                                op_minutes = 0
                    
                    if op_minutes <= 60 and break_placements[i] == 0:
                        # 90% chance to add early break if it's a valid position
                        if random.random() < 0.9:
                            break_placements[i] = random.choices([1, 3, 6], weights=[3, 2, 1])[0]
                            early_break_added = True
                            break
                
                # If no early break was added but we have valid positions, force one
                if not early_break_added and valid_break_positions:
                    # Find earliest valid position
                    earliest_pos = None
                    earliest_time = float('inf')
                    
                    for pos in valid_break_positions:
                        if pos >= len(operations):
                            continue
                            
                        op = operations[pos]
                        op_time = op.get('start_time')
                        
                        # Calculate minutes since shift start
                        op_minutes = float('inf')
                        if op_time:
                            if isinstance(op_time, datetime):
                                op_minutes = (op_time - self.start_time).total_seconds() / 60
                            else:
                                # Try to parse string time
                                try:
                                    if 'T' in op_time:
                                        time_part = op_time.split('T')[1]
                                    else:
                                        time_part = op_time
                                        
                                    if ':' in time_part:
                                        parts = time_part.split(':')
                                        start_hour = int(parts[0])
                                        start_minute = int(parts[1])
                                        op_minutes = (start_hour - self.start_time.hour) * 60 + (start_minute - self.start_time.minute)
                                except:
                                    op_minutes = float('inf')
                        
                        if op_minutes < earliest_time:
                            earliest_time = op_minutes
                            earliest_pos = pos
                    
                    # Force break at earliest valid position
                    if earliest_pos is not None and break_placements[earliest_pos] == 0:
                        break_placements[earliest_pos] = 1  # 10-min short break
                
                # Add micro breaks around high contention periods - MUCH more aggressively
                self._add_targeted_breaks(break_placements, operations, shuttle_id)
                
                # Add break clusters - MUCH more aggressively
                self._add_break_clusters(break_placements, operations, shuttle_id)
                
                individual.append(break_placements)
            
            return individual
        
        # Register the generator for individuals
        self.toolbox.register("attr_float", create_individual)
        
        # Register the individual creation operator
        self.toolbox.register("individual", tools.initIterate, creator.Individual, self.toolbox.attr_float)
        
        # Register the population creation operator
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        
        # Register the evaluation function
        def evaluate_schedule(individual):
            # Apply breaks to schedules
            modified_schedules = self._apply_breaks(individual, initial_schedules)
            
            # Evaluate the modified schedules
            fitness = self._evaluate_schedules(modified_schedules)
            
            return (fitness,)
        
        self.toolbox.register("evaluate", evaluate_schedule)
        
        # Register custom crossover for break placements
        def cxBreakPlacements(ind1, ind2):
            # For each shuttle's break placements, perform two-point crossover
            for i in range(min(len(ind1), len(ind2))):
                if len(ind1[i]) > 2 and len(ind2[i]) > 2:  # Need at least 3 elements for two-point crossover
                    # Select two random points
                    size = min(len(ind1[i]), len(ind2[i]))
                    cxpoint1 = random.randint(0, size - 2)
                    cxpoint2 = random.randint(cxpoint1 + 1, size - 1)
                    
                    # Swap elements between the points
                    ind1[i][cxpoint1:cxpoint2], ind2[i][cxpoint1:cxpoint2] = \
                        ind2[i][cxpoint1:cxpoint2], ind1[i][cxpoint1:cxpoint2]
            
            return ind1, ind2
            
        # Register crossover, mutation, and selection operators
        self.toolbox.register("mate", cxBreakPlacements)
        
        # Register custom mutation for break placements
        def mutBreakPlacements(individual, indpb):
            for i in range(len(individual)):
                shuttle_id = list(initial_schedules.keys())[i] if i < len(initial_schedules) else None
                
                if shuttle_id:
                    shuttle = self.get_shuttle_by_id(shuttle_id)
                    if not shuttle:
                        continue
                        
                    # Calculate ideal break times for this shuttle's shift
                    shift_length = shuttle['shift_length'] * 60  # in minutes
                    required_short_breaks = math.floor(shift_length / 240)  # One 10-min break every 240 minutes
                    
                    ideal_break_times = []
                    for b in range(required_short_breaks):
                        ideal_time = (b + 1) * 240  # in minutes from shift start
                        ideal_break_times.append(ideal_time)
                    
                    ideal_lunch_time = shift_length / 2  # middle of shift
                
                for j in range(len(individual[i])):
                    # Get operation details
                    op_time = None
                    plant_id = None
                    op_minutes = 0
                    
                    if shuttle_id and i < len(individual) and j < len(individual[i]):
                        op_index = j
                        if op_index < len(initial_schedules[shuttle_id]['operations']):
                            op = initial_schedules[shuttle_id]['operations'][op_index]
                            op_time = op.get('start_time')
                            plant_id = op.get('plant')
                            op_type = op.get('type')
                            
                            # Calculate minutes since shift start
                            if op_time:
                                if isinstance(op_time, datetime):
                                    op_minutes = (op_time - self.start_time).total_seconds() / 60
                                else:
                                    # Try to parse string time
                                    try:
                                        if 'T' in op_time:
                                            time_part = op_time.split('T')[1]
                                        else:
                                            time_part = op_time
                                            
                                        if ':' in time_part:
                                            parts = time_part.split(':')
                                            start_hour = int(parts[0])
                                            start_minute = int(parts[1])
                                            op_minutes = (start_hour - self.start_time.hour) * 60 + (start_minute - self.start_time.minute)
                                    except:
                                        op_minutes = 0
                            
                            # Check if this operation is the last one at this plant before moving
                            is_last_at_plant = False
                            if op_type != 'travel' and plant_id:
                                # Find all operations at this plant
                                ops_at_plant = [
                                    idx for idx, o in enumerate(initial_schedules[shuttle_id]['operations']) 
                                    if o.get('plant') == plant_id and o.get('type') != 'travel'
                                ]
                                if ops_at_plant and max(ops_at_plant) == op_index:
                                    is_last_at_plant = True
                            
                            # Only add breaks after completing all operations at a plant
                            if not is_last_at_plant and op_type != 'travel':
                                # Skip mutation for operations that are not the last at their plant
                                continue
                            
                            # If operation is close to ideal break time and it's a valid break position
                            is_near_ideal_short = any(abs(op_minutes - ideal) <= 30 for ideal in ideal_break_times)
                            is_near_ideal_lunch = abs(op_minutes - ideal_lunch_time) <= 30
                            
                            # Prioritize required breaks at ideal times
                            if is_last_at_plant and (is_near_ideal_short or is_near_ideal_lunch):
                                # Very high probability to add a break at this position
                                if random.random() < 0.95:  # 95% chance
                                    if is_near_ideal_lunch:
                                        individual[i][j] = 2  # Add 20-min lunch break
                                    else:
                                        individual[i][j] = 1  # Add 10-min short break
                                    continue  # Skip regular mutation for this position
                            
                            # Regular mutation logic for other positions
                            # Higher mutation rate for operations in high contention periods or involved in violations
                            in_high_contention = self._is_in_high_contention_period(op_time, plant_id)
                            violation_involved = self._is_operation_in_violation(shuttle_id, op_index, initial_schedules)
                            
                            # Much higher base mutation rate (50% instead of 15%)
                            local_indpb = indpb * 3.0  # Triple the base rate
                            
                            if in_high_contention:
                                local_indpb *= 3.0  # Triple mutation probability for high contention periods
                            if violation_involved:
                                local_indpb *= 5.0  # 5x mutation probability for operations in violations
                            
                            # Special case for early breaks (first hour)
                            if op_minutes <= 60:
                                local_indpb *= 2.0  # Double probability for early breaks
                            
                            # Cap probability at 0.95 (extremely high)
                            local_indpb = min(0.95, local_indpb)
                            
                            if random.random() < local_indpb:
                                # Check if plant has high ramp usage
                                high_ramp_usage = self._has_high_ramp_usage(plant_id)
                                
                                if high_ramp_usage and individual[i][j] == 0:
                                    # For high ramp usage plants, don't add new breaks, but maybe modify existing ones
                                    pass
                                elif violation_involved:
                                    # For operations involved in violations, prefer longer breaks
                                    individual[i][j] = random.choices([0, 3, 6, 7, 8], weights=[1, 3, 5, 3, 1])[0]
                                elif in_high_contention:
                                    # For high contention periods, prefer medium to long breaks
                                    individual[i][j] = random.choices([0, 3, 6, 7, 8], weights=[1, 3, 5, 3, 1])[0]
                                elif op_minutes <= 60:
                                    # For early operations, prioritize short-medium breaks
                                    individual[i][j] = random.choices([1, 3, 6], weights=[5, 3, 2])[0]
                                else:
                                    # Regular mutation - prefer a mix of break types
                                    individual[i][j] = random.choices(
                                        [0, 1, 2, 3, 4, 5, 6, 7, 8], 
                                        weights=[1, 2, 2, 2, 2, 2, 2, 1, 1]
                                    )[0]
            
            return individual,
        
        # Register specialized mutation for end-of-shift optimization
        def mutEndOfShiftOptimization(individual):
            for i in range(len(individual)):
                shuttle_id = list(initial_schedules.keys())[i] if i < len(initial_schedules) else None
                
                if shuttle_id:
                    # Get the shuttle's operations
                    ops = initial_schedules[shuttle_id]['operations']
                    num_ops = len(ops)
                    
                    # Focus on the last third of operations to optimize end-of-shift timing
                    start_idx = max(0, num_ops - num_ops // 3)
                    
                    # Add breaks to extend shift toward target end time (17:45)
                    current_end_time = None
                    target_end_time = None
                    
                    # Get the current end time
                    if ops:
                        last_op = ops[-1]
                        current_end_time = last_op['end_time']
                        
                        # Calculate target end time (17:45)
                        target_hour = 17
                        target_minute = 45
                        
                        # Convert current_end_time to hours and minutes
                        if isinstance(current_end_time, datetime):
                            current_hour = current_end_time.hour
                            current_minute = current_end_time.minute
                        else:
                            try:
                                # Try parsing as string
                                if 'T' in current_end_time:
                                    time_part = current_end_time.split('T')[1]
                                else:
                                    time_part = current_end_time
                                    
                                if ':' in time_part:
                                    current_hour = int(time_part.split(':')[0])
                                    current_minute = int(time_part.split(':')[1])
                                else:
                                    current_hour = 0
                                    current_minute = 0
                            except:
                                current_hour = 0
                                current_minute = 0
                        
                        # Check if we need to extend the shift - MUCH more aggressive
                        if current_hour < target_hour or (current_hour == target_hour and current_minute < target_minute):
                            # Need to add more breaks to extend toward 17:45
                            for j in range(start_idx, num_ops):
                                # 70% chance to add or enhance a break (up from 60%)
                                if random.random() < 0.7 and j < len(individual[i]):
                                    # If no break, add one; if already a break, possibly extend it
                                    if individual[i][j] == 0:
                                        # Add a break, preferring longer breaks to reach target time
                                        individual[i][j] = random.choices(
                                            [1, 3, 6, 7, 8], 
                                            weights=[1, 2, 3, 3, 2]
                                        )[0]
                                    elif individual[i][j] in [3, 4, 5]:
                                        # Upgrade micro break to a longer one
                                        individual[i][j] = random.choices(
                                            [individual[i][j], 6, 7], 
                                            weights=[1, 2, 1]
                                        )[0]
            
            return individual,
        
        # Register the collision-aware mutation operator
        def mutCollisionAware(individual):
            # Get all violations from the current best schedule
            if self.best_schedule:
                violations = self._identify_resource_violations(self.best_schedule, 'ramp')
                violations.extend(self._identify_resource_violations(self.best_schedule, 'worker'))
                
                # Process each violation
                for violation in violations:
                    shuttle_id = violation.get('shuttle_id')
                    operation_num = violation.get('operation_num')
                    
                    if shuttle_id is not None and operation_num is not None:
                        # Find the corresponding individual
                        shuttle_idx = None
                        for i, sid in enumerate(initial_schedules.keys()):
                            if sid == shuttle_id:
                                shuttle_idx = i
                                break
                        
                        if shuttle_idx is not None and shuttle_idx < len(individual):
                            # Find operations before the violation to add breaks
                            ops = initial_schedules[shuttle_id]['operations']
                            
                            # Look for operations 1-5 positions before the violation (increased from 1-3)
                            for offset in range(1, 6):
                                op_idx = operation_num - offset
                                if op_idx >= 0 and op_idx < len(individual[shuttle_idx]):
                                    # Check if the plant at this operation has low ramp usage
                                    if op_idx < len(ops):
                                        plant_id = None
                                        if ops[op_idx]['type'] == 'travel':
                                            plant_id = ops[op_idx].get('from_plant')
                                        else:
                                            plant_id = ops[op_idx].get('plant')
                                        
                                        # Only add break if plant doesn't have high ramp usage
                                        if not self._has_high_ramp_usage(plant_id):
                                            # 80% chance to add a break (up from 50%)
                                            if random.random() < 0.8:
                                                # Prefer longer micro breaks for better collision avoidance
                                                individual[shuttle_idx][op_idx] = random.choices(
                                                    [3, 4, 5], weights=[3, 1, 1])[0]
            
            return individual,
        
        # Register break cluster mutation
        def mutBreakClusters(individual):
            for i in range(len(individual)):
                if random.random() < 0.5:  # 50% chance to apply cluster mutation to a shuttle (up from 30%)
                    # Choose a random position to start the cluster
                    if len(individual[i]) > 5:  # Need enough operations for a cluster
                        cluster_start = random.randint(0, len(individual[i]) - 5)
                        cluster_length = random.randint(2, 4)  # 2-4 operations in a cluster
                        
                        # Check if this is a valid place for a cluster (avoid plants with high ramp usage)
                        valid_location = True
                        shuttle_id = list(initial_schedules.keys())[i] if i < len(initial_schedules) else None
                        
                        if shuttle_id:
                            ops = initial_schedules[shuttle_id]['operations']
                            for j in range(cluster_start, min(cluster_start + cluster_length, len(ops))):
                                op = ops[j]
                                plant_id = op.get('plant')
                                if self._has_high_ramp_usage(plant_id):
                                    valid_location = False
                                    break
                        
                        if valid_location:
                            # Apply a break pattern to the cluster
                            for j in range(cluster_start, min(cluster_start + cluster_length, len(individual[i]))):
                                # Alternate between break types - higher probability of long breaks
                                if random.random() < 0.4:  # 40% chance for required breaks (up from 30%)
                                    individual[i][j] = random.choices([1, 2], weights=[2, 1])[0]  # Required breaks
                                else:
                                    individual[i][j] = random.choices([3, 4, 5], weights=[3, 1, 1])[0]  # Micro breaks
            
            return individual,
        
        # Using a compound mutation
        def mutCompound(individual, indpb):
            # Apply basic mutation
            individual = mutBreakPlacements(individual, indpb)[0]
            
            # Each specialized mutation has a chance to be applied
            if random.random() < 0.6:  # 60% chance (up from 40%)
                individual = mutEndOfShiftOptimization(individual)[0]
            
            if random.random() < 0.7:  # 70% chance (up from 50%)
                individual = mutCollisionAware(individual)[0]
            
            if random.random() < 0.5:  # 50% chance (up from 30%)
                individual = mutBreakClusters(individual)[0]
            
            return individual,
        
        self.toolbox.register("mutate", mutCompound, indpb=0.3)  # Doubled base mutation probability from 0.15
        self.toolbox.register("select", tools.selTournament, tournsize=self.tournament_size)

    def _analyze_resource_usage(self, schedules):
        """
        Analyze resource usage patterns across all plants to identify high contention periods.
        
        Args:
            schedules (dict): Dictionary of schedules
            
        Returns:
            dict: Resource usage patterns by plant and time
        """
        try:
            # Track resource usage by plant and time period
            resource_usage = {}
            
            # Process each schedule
            for shuttle_id, schedule in schedules.items():
                for op in schedule.get('operations', []):
                    # Skip operations without proper time information
                    if 'start_time' not in op or 'end_time' not in op:
                        continue
                        
                    # Get the operation time and plant
                    start_time = op['start_time']
                    end_time = op['end_time']
                    
                    # Check if this operation uses plant resources (load, unload, preprah)
                    if op['type'] in ['load', 'unload', 'preprah']:
                        plant_id = op.get('plant')
                        if plant_id is not None:
                            # Initialize plant if not in resource_usage
                            if plant_id not in resource_usage:
                                resource_usage[plant_id] = {
                                    'ramp_usage': {},
                                    'worker_usage': {}
                                }
                            
                            # Convert time to hour-minute format
                            start_hour_minute = None
                            
                            if isinstance(start_time, datetime):
                                start_hour = start_time.hour
                                start_minute = start_time.minute
                                start_hour_minute = f"{start_hour:02d}:{start_minute:02d}"
                            else:
                                # Try to parse string time
                                try:
                                    if isinstance(start_time, str):
                                        if 'T' in start_time:
                                            start_time = start_time.split('T')[1]
                                            
                                        if ':' in start_time:
                                            start_hour_minute = start_time.split('.')[0]
                                except:
                                    # Skip if time parsing fails
                                    continue
                            
                            if start_hour_minute:
                                # Increment resource usage for this time window
                                if start_hour_minute not in resource_usage[plant_id]['ramp_usage']:
                                    resource_usage[plant_id]['ramp_usage'][start_hour_minute] = 0
                                resource_usage[plant_id]['ramp_usage'][start_hour_minute] += 1
                                
                                if start_hour_minute not in resource_usage[plant_id]['worker_usage']:
                                    resource_usage[plant_id]['worker_usage'][start_hour_minute] = 0
                                resource_usage[plant_id]['worker_usage'][start_hour_minute] += 1
            
            return resource_usage
        except Exception as e:
            print(f"Error analyzing resource usage: {e}")
            import traceback
            traceback.print_exc()
            # Return empty dict on error
            return {}

    def _identify_high_contention_periods(self, resource_usage, threshold_percentile=0.75):
        """
        Identify time periods with high resource contention.
        
        Args:
            resource_usage (dict): Resource usage patterns by plant and time
            threshold_percentile (float): Percentile threshold to consider high contention
            
        Returns:
            dict: High contention periods by plant
        """
        try:
            high_contention_periods = {}
            
            for plant_id, usage in resource_usage.items():
                # Get ramp usage values
                ramp_usage_values = list(usage['ramp_usage'].values())
                if not ramp_usage_values:
                    continue
                    
                # Calculate threshold
                sorted_values = sorted(ramp_usage_values)
                threshold_index = int(len(sorted_values) * threshold_percentile)
                if threshold_index >= len(sorted_values):
                    threshold_index = len(sorted_values) - 1
                    
                threshold = sorted_values[threshold_index]
                
                # Identify high contention periods
                high_contention_periods[plant_id] = {
                    'times': [],
                    'threshold': threshold
                }
                
                for time_str, count in usage['ramp_usage'].items():
                    if count >= threshold:
                        high_contention_periods[plant_id]['times'].append(time_str)
            
            return high_contention_periods
        except Exception as e:
            print(f"Error identifying high contention periods: {e}")
            # Return empty dict on error
            return {}

    def _is_in_high_contention_period(self, time_str, plant_id):
        """
        Check if a given time is in a high contention period for a plant.
        
        Args:
            time_str: Time to check
            plant_id: Plant ID
            
        Returns:
            bool: True if in high contention period
        """
        try:
            if not hasattr(self, 'high_contention_periods') or not self.high_contention_periods or plant_id not in self.high_contention_periods:
                return False
            
            # Convert time to hour-minute format
            hour_minute = None
            
            if isinstance(time_str, datetime):
                hour_minute = f"{time_str.hour:02d}:{time_str.minute:02d}"
            else:
                # Try to parse string time
                try:
                    if isinstance(time_str, str):
                        if 'T' in time_str:
                            time_str = time_str.split('T')[1]
                            
                        if ':' in time_str:
                            hour_minute = time_str.split('.')[0]
                except:
                    return False
            
            if not hour_minute:
                return False
            
            # Check if in high contention periods
            return hour_minute in self.high_contention_periods[plant_id]['times']
        except Exception as e:
            # On any error, assume not in contention period
            return False

    def _has_high_ramp_usage(self, plant_id):
        """
        Check if a plant has generally high ramp usage.
        
        Args:
            plant_id: Plant ID
            
        Returns:
            bool: True if plant has high ramp usage
        """
        try:
            if not plant_id or not hasattr(self, 'resource_usage_patterns') or not self.resource_usage_patterns or plant_id not in self.resource_usage_patterns:
                return False
            
            # Get average ramp usage
            ramp_usage = self.resource_usage_patterns[plant_id]['ramp_usage']
            if not ramp_usage:
                return False
            
            avg_usage = sum(ramp_usage.values()) / len(ramp_usage)
            
            # Check if plant is in top 25% of ramp usage
            if plant_id in self.plants_by_id:
                plant = self.plants_by_id[plant_id]
                ramp_capacity = plant.get('ramp_capacity', 5)
                
                # If average usage is more than 70% of capacity, consider it high
                return avg_usage > (ramp_capacity * 0.7)
            
            return False
        except Exception as e:
            # On any error, assume not high usage
            return False

    def _is_operation_in_violation(self, shuttle_id, op_idx, schedules):
        """
        Check if an operation is involved in a resource violation.
        
        Args:
            shuttle_id: Shuttle ID
            op_idx: Operation index
            schedules: Current schedules
            
        Returns:
            bool: True if operation is in violation
        """
        try:
            # If we don't have a best schedule yet, return False
            if not hasattr(self, 'best_schedule') or not self.best_schedule:
                return False
            
            # Get violations from the best schedule
            violations = self._identify_resource_violations(self.best_schedule, 'ramp')
            violations.extend(self._identify_resource_violations(self.best_schedule, 'worker'))
            
            # Check if this operation is in the violations
            for violation in violations:
                if violation.get('shuttle_id') == shuttle_id and violation.get('operation_num') == op_idx:
                    return True
            
            return False
        except Exception as e:
            # On any error, assume not in violation
            return False

    def _add_targeted_breaks(self, break_placements, operations, shuttle_id):
        """
        Add targeted breaks around high contention periods.
        Now MUCH more aggressive with break placement, but only after completing all operations at a plant.
        """
        try:
            # Build a map of all operations at each plant
            plant_operations = {}  # Dictionary of plant_id -> list of operation indices
            
            # Group operations by plant
            for i, op in enumerate(operations):
                # Skip travel operations when grouping
                if op['type'] == 'travel':
                    continue
                    
                plant_id = op.get('plant')
                if plant_id:
                    if plant_id not in plant_operations:
                        plant_operations[plant_id] = []
                    plant_operations[plant_id].append(i)
            
            # Find travel operations that occur right after completing all operations at a plant
            travel_after_plant = []
            
            for i, op in enumerate(operations):
                if op['type'] == 'travel' and i > 0:
                    # Get previous operation
                    prev_op = operations[i-1]
                    if prev_op['type'] != 'travel':
                        prev_plant = prev_op.get('plant')
                        
                        # Check if we completed all operations at this plant
                        if prev_plant in plant_operations:
                            ops_at_plant = plant_operations[prev_plant]
                            if ops_at_plant and max(ops_at_plant) == i-1:
                                # This travel follows the last operation at the plant
                                travel_after_plant.append(i)
            
            # Add breaks before these travel operations - VERY aggressively
            for travel_idx in travel_after_plant:
                if travel_idx < len(break_placements):
                    # Get previous plant
                    prev_op = operations[travel_idx-1]
                    plant_id = prev_op.get('plant')
                    
                    # Very high chance (90%) to add a break after completing operations at a plant
                    if random.random() < 0.9:
                        # Prefer longer breaks for better contention reduction and worker rotation
                        break_placements[travel_idx] = random.choices(
                            [1, 2, 3, 6, 7, 8], 
                            weights=[2, 2, 3, 3, 2, 1]
                        )[0]  # Include new longer break options
            
            # High chance to add breaks before EVERY travel operation (not just after plant completion)
            for i, op in enumerate(operations):
                if op['type'] == 'travel' and i < len(break_placements):
                    # 50% chance for any travel operation to have a break
                    if random.random() < 0.5 and break_placements[i] == 0:
                        # Only add a break if this travel happens after a complete set of operations
                        # at the current plant (i.e., no more operations at this plant)
                        is_after_complete_set = False
                        if i > 0:
                            prev_op = operations[i-1]
                            if prev_op['type'] != 'travel':
                                prev_plant = prev_op.get('plant')
                                if prev_plant in plant_operations:
                                    ops_at_plant = plant_operations[prev_plant]
                                    if ops_at_plant and max(ops_at_plant) == i-1:
                                        is_after_complete_set = True
                        
                        if is_after_complete_set:
                            break_placements[i] = random.choices(
                                [3, 4, 5, 6], 
                                weights=[5, 3, 2, 2]
                            )[0]
        except Exception as e:
            print(f"Error adding targeted breaks: {e}")
            import traceback
            traceback.print_exc()
            pass

    def _add_break_clusters(self, break_placements, operations, shuttle_id):
        """
        Add clusters of breaks at strategic points.
        Now MUCH more aggressive with break clustering, but only after completing operations at a plant.
        
        Args:
            break_placements: Array of break placements
            operations: Shuttle operations
            shuttle_id: Shuttle ID
        """
        try:
            # Higher chance to add clusters (40% instead of 20%)
            if random.random() > 0.4:
                return
            
            # Build a map of all operations at each plant
            plant_operations = {}  # Dictionary of plant_id -> list of operation indices
            
            # Group operations by plant
            for i, op in enumerate(operations):
                # Skip travel operations when grouping
                if op['type'] == 'travel':
                    continue
                    
                plant_id = op.get('plant')
                if plant_id:
                    if plant_id not in plant_operations:
                        plant_operations[plant_id] = []
                    plant_operations[plant_id].append(i)
            
            # Find travel operations that occur right after completing all operations at a plant
            travel_after_plant = []
            
            for i, op in enumerate(operations):
                if op['type'] == 'travel' and i > 0:
                    # Get previous operation
                    prev_op = operations[i-1]
                    if prev_op['type'] != 'travel':
                        prev_plant = prev_op.get('plant')
                        
                        # Check if we completed all operations at this plant
                        if prev_plant in plant_operations:
                            ops_at_plant = plant_operations[prev_plant]
                            if ops_at_plant and max(ops_at_plant) == i-1:
                                # This travel follows the last operation at the plant
                                travel_after_plant.append(i)
            
            # Add break clusters before travel operations after completing a plant
            for travel_idx in travel_after_plant:
                if travel_idx < len(break_placements):
                    # Get previous plant
                    prev_op = operations[travel_idx-1]
                    plant_id = prev_op.get('plant')
                    
                    # Skip plants with high ramp usage
                    if self._has_high_ramp_usage(plant_id):
                        continue
                    
                    # 80% chance to add a break cluster (up from 70%)
                    if random.random() < 0.8:
                        # Add first break before travel - include longer breaks
                        if break_placements[travel_idx] == 0:
                            break_placements[travel_idx] = random.choices(
                                [3, 6, 7, 8], 
                                weights=[3, 3, 2, 1]
                            )[0]
                        
                        # Try to add more breaks in a cluster
                        cluster_size = random.randint(2, 3) # 2-3 breaks in a cluster
                        
                        # Both before and after the travel
                        for offset in range(1, cluster_size):
                            # Add break after travel - ONLY if it's the last operation at the next plant
                            if (travel_idx + offset < len(operations) and 
                                travel_idx + offset < len(break_placements)):
                                
                                # Check if this position is after completing operations at a plant
                                is_after_plant_completion = False
                                for plant_idx in travel_after_plant:
                                    if plant_idx == travel_idx + offset:
                                        is_after_plant_completion = True
                                        break
                                
                                if is_after_plant_completion and break_placements[travel_idx + offset] == 0:
                                    break_placements[travel_idx + offset] = random.choices(
                                        [3, 6, 7], 
                                        weights=[3, 2, 1]
                                    )[0]
                            
                            # Add break before travel - but check that it's still after plant completion
                            prev_idx = travel_idx - offset
                            if prev_idx >= 0 and break_placements[prev_idx] == 0:
                                # Only add if this is also after plant completion
                                is_valid_position = False
                                for plant_idx in travel_after_plant:
                                    if plant_idx == prev_idx:
                                        is_valid_position = True
                                        break
                                
                                if is_valid_position:
                                    break_placements[prev_idx] = random.choices(
                                        [3, 6, 7], 
                                        weights=[3, 2, 1]
                                    )[0]
            
            # Add additional break clusters at random positions - but ONLY at valid break points
            if len(operations) > 10:  # Only for longer routes
                num_random_clusters = random.randint(1, 3)  # 1-3 random clusters
                
                for _ in range(num_random_clusters):
                    if len(break_placements) > 5:  # Need at least 5 operations
                        # Only consider valid break positions (after plant completion)
                        valid_positions = travel_after_plant
                        
                        if valid_positions:  # Only proceed if we have valid positions
                            # Choose a random valid position to start the cluster
                            cluster_start = random.choice(valid_positions)
                            
                            if cluster_start < len(break_placements) and break_placements[cluster_start] == 0:
                                # Add a break at this position
                                break_placements[cluster_start] = random.choices(
                                    [3, 6, 7, 8], 
                                    weights=[2, 3, 2, 1]
                                )[0]
                                
                                # Try to expand cluster to nearby valid positions
                                for pos in valid_positions:
                                    # If position is close to our cluster_start and doesn't have a break
                                    if abs(pos - cluster_start) <= 3 and pos != cluster_start:
                                        if pos < len(break_placements) and break_placements[pos] == 0:
                                            # 60% chance to add another break in the cluster
                                            if random.random() < 0.6:
                                                break_placements[pos] = random.choices(
                                                    [3, 6, 7], 
                                                    weights=[3, 2, 1]
                                                )[0]
        except Exception as e:
            print(f"Error adding break clusters: {e}")
            import traceback
            traceback.print_exc()
            pass


    def _evaluate_schedules(self, schedules):
        """
        Evaluate how good a set of schedules is.
        Lower score is better.
        
        Returns:
            float: Fitness score (lower is better)
        """
        score = 0.0
        
        try:
            # Check for ramp capacity violations at plants
            ramp_usage = self._calculate_ramp_usage(schedules)
            ramp_violations = self._count_resource_violations(ramp_usage, 'ramp')
            score += float(ramp_violations) * 1000.0  # Heavy penalty for ramp violations
            
            # Check for worker capacity violations at plants - ignore preprah operations
            worker_usage = self._calculate_worker_usage(schedules)
            worker_violations = self._count_resource_violations(worker_usage, 'worker')
            score += float(worker_violations) * 600.0  # Heavy penalty for worker violations
            
            # Penalize undesired idle time between operations
            idle_time_penalty = self._calculate_idle_time_penalty(schedules)
            score += float(idle_time_penalty) * 0.5
            
            # Penalize scheduling outside of shift hours
            overtime_penalty = self._calculate_overtime_penalty(schedules)
            score += float(overtime_penalty) * 200.0
            
            # Penalize early/late operations relative to optimal timing
            timing_penalty = self._calculate_timing_penalty(schedules)
            score += float(timing_penalty)
            
            # Penalize insufficient breaks or too many breaks
            break_penalty = self._calculate_break_penalty(schedules)
            score += float(break_penalty) * 50.0
            
            # Add penalty for ending shift too early (before 17:45)
            end_of_shift_penalty = self._calculate_end_of_shift_penalty(schedules)
            score += float(end_of_shift_penalty) * 100.0
            
            # Add penalty for not spreading breaks evenly
            break_distribution_penalty = self._calculate_break_distribution_penalty(schedules)
            score += float(break_distribution_penalty) * 30.0
            
        except Exception as e:
            # If any calculation fails, return a very high score
            print(f"Error in evaluation function: {e}")
            import traceback
            traceback.print_exc()
            return 1e6  # Very high penalty for errors
        
        return score
    
    def _calculate_end_of_shift_penalty(self, schedules):
        """Calculate penalty for ending shifts before the target end time (17:45)."""
        penalty = 0.0
        
        target_hour = 17
        target_minute = 45
        target_time_minutes = target_hour * 60 + target_minute
        
        for shuttle_id, schedule in schedules.items():
            # Skip if empty schedule
            if not schedule['operations']:
                continue
            
            # Get the last operation's end time
            last_op = schedule['operations'][-1]
            end_time = last_op['end_time']
            
            # Convert end time to minutes since midnight
            end_time_minutes = 0
            
            if isinstance(end_time, datetime):
                end_time_minutes = end_time.hour * 60 + end_time.minute
            else:
                # Try to parse string time
                try:
                    if 'T' in end_time:
                        time_part = end_time.split('T')[1]
                    else:
                        time_part = end_time
                        
                    if ':' in time_part:
                        parts = time_part.split(':')
                        end_time_minutes = int(parts[0]) * 60 + int(parts[1])
                except:
                    # Skip if time parsing fails
                    continue
            
            # Calculate penalty if ending too early
            # Give a grace period of 15 minutes (no penalty if within 15 minutes of target)
            if end_time_minutes < target_time_minutes - 15:
                time_diff = target_time_minutes - end_time_minutes
                # Square the difference to penalize larger gaps more severely
                penalty += (time_diff ** 2) * 0.01
        
        return penalty

    def _calculate_break_distribution_penalty(self, schedules):
        """
        Calculate penalty for breaks that are not well distributed throughout the shift.
        Encourages more evenly spaced breaks.
        """
        penalty = 0.0
        
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            if not shuttle:
                continue
            
            # Skip if empty schedule
            if not schedule['operations']:
                continue
            
            # Get all breaks
            breaks = []
            for i, op in enumerate(schedule['operations']):
                if op['type'] == 'break':
                    # Store break info with position and time
                    start_time_minutes = 0
                    
                    if isinstance(op['start_time'], datetime):
                        start_time_minutes = op['start_time'].hour * 60 + op['start_time'].minute
                    else:
                        # Try to parse string time
                        try:
                            if 'T' in op['start_time']:
                                time_part = op['start_time'].split('T')[1]
                            else:
                                time_part = op['start_time']
                                
                            if ':' in time_part:
                                parts = time_part.split(':')
                                start_time_minutes = int(parts[0]) * 60 + int(parts[1])
                        except:
                            # Skip if time parsing fails
                            continue
                    
                    breaks.append({
                        'position': i,
                        'time_minutes': start_time_minutes,
                        'duration': op['duration']
                    })
            
            # Skip if no breaks
            if not breaks:
                continue
            
            # Sort breaks by time
            breaks.sort(key=lambda x: x['time_minutes'])
            
            # Get shift duration in minutes
            shift_minutes = shuttle['shift_length'] * 60
            
            # Calculate ideal break intervals
            num_breaks = len(breaks)
            ideal_interval = shift_minutes / (num_breaks + 1)  # +1 to account for start and end
            
            # Calculate penalty for deviation from ideal spacing
            for i in range(len(breaks)):
                if i == 0:
                    # First break: compare with shift start (6:00 AM = 360 minutes)
                    actual_interval = breaks[i]['time_minutes'] - 360  # 6 hours * 60 minutes
                else:
                    # Other breaks: compare with previous break
                    actual_interval = breaks[i]['time_minutes'] - breaks[i-1]['time_minutes']
                
                # Calculate deviation from ideal
                deviation = abs(actual_interval - ideal_interval)
                
                # Add squared deviation to penalty
                penalty += (deviation ** 2) * 0.001
            
            # Check last break to shift end interval
            if breaks:
                last_break_time = breaks[-1]['time_minutes']
                shift_end_time = 360 + shift_minutes  # 6:00 AM + shift duration
                actual_interval = shift_end_time - last_break_time
                deviation = abs(actual_interval - ideal_interval)
                penalty += (deviation ** 2) * 0.001
        
        return penalty

    def _calculate_ramp_usage(self, schedules):
        """
        Calculate ramp usage over time at each plant.
        
        This method properly handles preprah shuttles by:
        1. Identifying preprah destinations where 1 ramp is always reserved
        2. During preprah operations, counting only 1 additional ramp (for 2 total)
        
        Args:
            schedules (dict): Dictionary of schedules
            
        Returns:
            dict: Dictionary mapping plant IDs to ramp usage
        """
        usage = {}
        
        # First identify preprah shuttles and their destinations
        preprah_destinations = {}  # plant_id -> set of shuttle_ids that use it as preprah destination
        
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            if shuttle and shuttle['shuttle_type'] == 'preprah':
                preprah_destination = shuttle.get('preprah_destination')
                if preprah_destination:
                    if preprah_destination not in preprah_destinations:
                        preprah_destinations[preprah_destination] = set()
                    preprah_destinations[preprah_destination].add(shuttle_id)
        
        # Process all operations and add to usage
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            is_preprah = shuttle and shuttle['shuttle_type'] == 'preprah'
            preprah_destination = shuttle.get('preprah_destination') if is_preprah else None
            
            # Process all operations for this shuttle
            for op in schedule['operations']:
                if op['type'] in ['load', 'unload', 'preprah']:
                    plant_id = op['plant']
                    if plant_id is None:
                        continue
                        
                    start_time = op['start_time']
                    end_time = op['end_time']
                    
                    # Initialize plant in usage dict if not present
                    if plant_id not in usage:
                        usage[plant_id] = []
                    
                    # Skip load/unload operations at preprah destinations
                    is_preprah_op = op.get('is_preprah_operation', False)
                    if is_preprah and is_preprah_op and op['type'] in ['load', 'unload'] and plant_id == preprah_destination:
                        continue
                    
                    # Determine ramp usage
                    ramp_usage = 1  # Standard operations use 1 ramp
                    
                    usage[plant_id].append({
                        'start_time': start_time,
                        'end_time': end_time,
                        'ramps': ramp_usage,
                        'shuttle_id': shuttle_id,
                        'operation': op['type'],
                        'is_preprah_operation': op['type'] == 'preprah',
                        'preprah_destination': plant_id == preprah_destination if is_preprah else False
                    })
        
        # Add permanent ramp reservation for preprah destinations
        for plant_id, shuttle_ids in preprah_destinations.items():
            if plant_id not in usage:
                usage[plant_id] = []
            
            # For each preprah shuttle, add a permanent reservation
            for shuttle_id in shuttle_ids:
                shuttle = self.get_shuttle_by_id(shuttle_id)
                if shuttle:
                    shift_start = self.start_time
                    shift_end = self.start_time + timedelta(hours=shuttle['shift_length'])
                    
                    usage[plant_id].append({
                        'start_time': shift_start,
                        'end_time': shift_end,
                        'ramps': 1,  # Reserve 1 ramp permanently
                        'shuttle_id': shuttle_id,
                        'operation': 'preprah_reserved',
                        'is_permanent': True  # Flag to identify permanent reservation
                    })
        
        return usage
    
    def _calculate_worker_usage(self, schedules):
        """
        Calculate worker usage over time at each plant.
        
        For preprah operations, we don't count individual load/unload operations
        at the preprah destination since they're handled by the preprah operation itself.
        
        Args:
            schedules (dict): Dictionary of schedules
            
        Returns:
            dict: Dictionary mapping plant IDs to worker usage
        """
        usage = {}
        
        # Identify preprah shuttles and their destinations
        preprah_destinations = {}  # shuttle_id -> preprah_destination
        
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            if shuttle and shuttle['shuttle_type'] == 'preprah':
                preprah_destination = shuttle.get('preprah_destination')
                if preprah_destination:
                    preprah_destinations[shuttle_id] = preprah_destination
        
        # Track worker usage for each plant over time
        for shuttle_id, schedule in schedules.items():
            # Check if this is a preprah shuttle
            is_preprah_shuttle = shuttle_id in preprah_destinations
            preprah_destination = preprah_destinations.get(shuttle_id)
            
            for op in schedule['operations']:
                if op['type'] in ['load', 'unload']:
                    plant_id = op['plant']
                    if plant_id is None:
                        continue
                        
                    start_time = op['start_time']
                    end_time = op['end_time']
                    
                    # Skip load/unload operations at preprah destinations for preprah shuttles
                    is_preprah_op = op.get('is_preprah_operation', False)
                    if is_preprah_shuttle and is_preprah_op and plant_id == preprah_destination:
                        continue
                    
                    # Initialize plant in usage dict if not present
                    if plant_id not in usage:
                        usage[plant_id] = []
                    
                    # All load/unload operations require workers, even at preprah locations
                    usage[plant_id].append({
                        'start_time': start_time,
                        'end_time': end_time,
                        'workers': 1,
                        'shuttle_id': shuttle_id,
                        'operation': op['type']
                    })
                
                # # For preprah operations, add worker usage for the duration of preprah
                # elif op['type'] == 'preprah':
                #     plant_id = op['plant']
                #     if plant_id is None:
                #         continue
                    
                #     start_time = op['start_time']
                #     end_time = op['end_time']
                    
                #     # Initialize plant in usage dict if not present
                #     if plant_id not in usage:
                #         usage[plant_id] = []
                    
                #     # Preprah operation requires one worker
                #     usage[plant_id].append({
                #         'start_time': start_time,
                #         'end_time': end_time,
                #         'workers': 1,  # Preprah requires one worker
                #         'shuttle_id': shuttle_id,
                #         'operation': 'preprah'
                #     })
        
        return usage

    def _count_resource_violations(self, usage_data, resource_type):
        """
        Count resource capacity violations.
        
        Args:
            usage_data (dict): Resource usage data
            resource_type (str): 'ramp' or 'worker'
            
        Returns:
            int: Number of violations
        """
        violations = 0
        
        # Check each plant's resource usage
        for plant_id, usages in usage_data.items():
            if plant_id not in self.plants_by_id:
                continue
                
            plant = self.plants_by_id[plant_id]
            capacity = plant['ramp_capacity'] if resource_type == 'ramp' else plant['worker_capacity']
            
            # Sort operations by start time
            sorted_usages = sorted(usages, key=lambda x: x['start_time'])
            
            # Find all time points where resource usage might change
            time_points = []
            for usage in sorted_usages:
                time_points.append(usage['start_time'])
                time_points.append(usage['end_time'])
            time_points = sorted(set(time_points))
            
            # Check resource usage at each time point
            for i in range(len(time_points) - 1):
                current_time = time_points[i]
                next_time = time_points[i+1]
                
                # Skip if the interval is 0
                if current_time == next_time:
                    continue
                
                # Find all operations active during this time interval
                active_operations = []
                for usage in sorted_usages:
                    if usage['start_time'] <= current_time and usage['end_time'] > current_time:
                        active_operations.append(usage)
                
                # Calculate total resource usage for this interval
                resource_key = 'ramps' if resource_type == 'ramp' else 'workers'
                
                # For ramp usage, we need to handle preprah specially
                if resource_type == 'ramp':
                    # Count regular operations
                    regular_usage = sum(op.get(resource_key, 0) for op in active_operations 
                                    if op.get('operation') not in ['preprah_reserved'])
                    
                    # Count permanent reservations (only once per plant)
                    permanent_reservations = {}  # plant_id -> count
                    for op in active_operations:
                        if op.get('is_permanent'):
                            permanent_reservations[plant_id] = 1
                    
                    permanent_usage = sum(permanent_reservations.values())
                    
                    total_usage = regular_usage + permanent_usage
                else:
                    # For workers, just count normally
                    total_usage = sum(op.get(resource_key, 0) for op in active_operations)
                
                # Check if capacity is exceeded
                if total_usage > capacity:
                    # Calculate violation severity (weighted by duration and amount)
                    interval_minutes = (next_time - current_time).total_seconds() / 60
                    violation_amount = total_usage - capacity
                    violation_score = violation_amount * interval_minutes
                    violations += violation_score
            
        return violations


    def _calculate_idle_time_penalty(self, schedules):
        """Calculate penalty for idle time between operations."""
        total_idle_time = 0
        
        for shuttle_id, schedule in schedules.items():
            ops = sorted(schedule['operations'], key=lambda x: x['start_time'])
            
            # Calculate idle time between consecutive operations
            for i in range(1, len(ops)):
                prev_op = ops[i-1]
                curr_op = ops[i]
                
                # Find idle time between operations
                idle_time = (curr_op['start_time'] - prev_op['end_time']).total_seconds() / 60
                
                # Don't penalize for break time or deliberate waiting for resources
                if idle_time > 5 and prev_op['type'] != 'break' and curr_op['type'] != 'break':
                    total_idle_time += idle_time
        
        return total_idle_time

    def _calculate_overtime_penalty(self, schedules):
        """Calculate penalty for operations scheduled outside of shift hours."""
        total_overtime = 0
        
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            shift_end = self.start_time + timedelta(hours=shuttle['shift_length'])
            
            for op in schedule['operations']:
                # Check if operation ends after shift end
                if op['end_time'] > shift_end:
                    overtime_minutes = (op['end_time'] - shift_end).total_seconds() / 60
                    total_overtime += overtime_minutes
        
        return total_overtime

    def _calculate_timing_penalty(self, schedules):
        """Calculate penalty for operations not occurring at optimal times."""
        total_penalty = 0
        
        # This is a simplistic implementation - in a real system, you might
        # want to compare against historical data or preferred time slots
        
        return total_penalty
    
    def _calculate_break_penalty(self, schedules):
        """
        Calculate penalty for break constraint violations with MUCH stronger penalties.
        
        Ensures:
        1. Total break time meets requirements (30 min for 8h shift, 60 min for 12h shift)
        2. Breaks are properly distributed (one 10-min break every 4 hours, one 20-min lunch)
        3. Lunch break is properly placed around the middle of the shift
        4. Breaks don't exceed the required total by too much
        """
        total_penalty = 0
        
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            if not shuttle:
                continue
                
            # Get required break time
            required_break_time = shuttle['break_time']  # 30 min for 8h, 60 min for 12h
            shift_length = shuttle['shift_length']
            
            # Calculate required break distribution
            required_short_breaks = math.floor(shift_length / 4)  # One 10-min break every 4 hours
            required_lunch_break = 1  # One 20-min lunch break per shift
            
            # Track actual breaks
            total_break_time = 0
            short_breaks = []  # Store 10-min breaks with their times
            lunch_breaks = []  # Store 20-min breaks with their times
            micro_breaks = []  # Store other breaks with their times
            
            # Count breaks by type and record their times
            for op in schedule['operations']:
                if op['type'] == 'break':
                    duration = op['duration']
                    total_break_time += duration
                    
                    # Convert start time to minutes since shift start
                    start_time_minutes = 0
                    
                    if isinstance(op['start_time'], datetime):
                        start_time_minutes = (op['start_time'] - self.start_time).total_seconds() / 60
                    else:
                        # Try to parse string time
                        try:
                            if 'T' in op['start_time']:
                                time_part = op['start_time'].split('T')[1]
                            else:
                                time_part = op['start_time']
                                
                            if ':' in time_part:
                                parts = time_part.split(':')
                                start_hour = int(parts[0])
                                start_minute = int(parts[1])
                                start_time_minutes = (start_hour - self.start_time.hour) * 60 + (start_minute - self.start_time.minute)
                        except:
                            # If time parsing fails, skip this break
                            continue
                    
                    # Categorize by duration
                    if duration == 10:
                        short_breaks.append(start_time_minutes)
                    elif duration == 20:
                        lunch_breaks.append(start_time_minutes)
                    else:
                        micro_breaks.append(start_time_minutes)
            
            # EXTREMELY SEVERE penalty for missing required breaks
            if len(short_breaks) < required_short_breaks:
                # 1000 points per missing short break (up from 50)
                total_penalty += 750 * (required_short_breaks - len(short_breaks))
            
            if len(lunch_breaks) < required_lunch_break:
                # 2000 points per missing lunch break (up from 100)
                total_penalty += 1500 * (required_lunch_break - len(lunch_breaks))
            
            # Check if breaks are properly distributed (every 4 hours)
            ideal_break_times = []
            for i in range(required_short_breaks):
                # Ideal time for each short break (in minutes from shift start)
                ideal_time = (i + 1) * 240  # 240 minutes = 4 hours
                ideal_break_times.append(ideal_time)
            
            # Check actual break placement against ideal
            if short_breaks:
                for ideal_time in ideal_break_times:
                    # Find the closest short break to this ideal time
                    closest_break = min(short_breaks, key=lambda x: abs(x - ideal_time))
                    time_diff = abs(closest_break - ideal_time)
                    
                    # Severely penalize breaks that are more than 60 minutes away from ideal
                    if time_diff > 60:
                        # 20 points per minute of deviation beyond 60 minutes
                        total_penalty += 20 * (time_diff - 60)
            
            # Check lunch break placement
            ideal_lunch_time = shift_length * 30  # Ideally in the middle of the shift
            if lunch_breaks:
                lunch_time = lunch_breaks[0]  # Use the first lunch break
                lunch_diff = abs(lunch_time - ideal_lunch_time)
                
                # Severely penalize lunch breaks more than 60 minutes away from middle
                if lunch_diff > 60:
                    # 30 points per minute of deviation beyond 60 minutes for lunch
                    total_penalty += 30 * (lunch_diff - 60)
            
            # Penalize insufficient total break time
            if total_break_time < required_break_time:
                # 50 points per minute of missing break time (up from 10)
                total_penalty += 50 * (required_break_time - total_break_time)
            
            # Penalize excess break time (but less severely)
            # Allow 15 minutes of flexibility
            excess_time = total_break_time - (required_break_time + 15)
            if excess_time > 0:
                # 10 points per excess minute (up from 5)
                total_penalty += 10 * excess_time
            
            # REWARD for breaks at specific plants (e.g., ID 4)
            for op in schedule['operations']:
                if op['type'] == 'break':
                    plant_id = op.get('plant')
                    if plant_id == 4:  # If plant ID is 4, give a reward
                        # 50 point reward for each break at plant ID 4
                        total_penalty -= 50
            
            # REWARD for correct break placement
            for break_time in short_breaks:
                # Find the closest ideal break time
                closest_ideal = min(ideal_break_times, key=lambda x: abs(x - break_time))
                time_diff = abs(break_time - closest_ideal)
                
                # If break is within 30 minutes of ideal, give reward
                if time_diff <= 30:
                    # 100 point reward for well-placed breaks
                    total_penalty -= 100
            
            # Reward for correct lunch placement
            if lunch_breaks:
                lunch_time = lunch_breaks[0]
                lunch_diff = abs(lunch_time - ideal_lunch_time)
                
                # If lunch is within 30 minutes of middle, give big reward
                if lunch_diff <= 30:
                    # 200 point reward for well-placed lunch
                    total_penalty -= 200
        
        return total_penalty

    def _run_ga(self, initial_schedules):
        """Run the genetic algorithm to optimize schedules with improved diversity."""
        try:
            # Create initial population
            pop_size = self.population_size
            
            pop = self.toolbox.population(n=pop_size)
            
            # Verify individual structure
            if not pop or len(pop) == 0:
                print("Warning: Empty population created")
                return initial_schedules
                
            hof = tools.HallOfFame(20)  # Track top 10 individuals
            
            # Statistics setup
            stats = tools.Statistics(lambda ind: ind.fitness.values if hasattr(ind, 'fitness') else (float('inf'),))
            stats.register("avg", lambda x: sum(fit[0] for fit in x) / len(x) if x else 0)
            stats.register("min", lambda x: min(fit[0] for fit in x) if x else float('inf'))
            stats.register("max", lambda x: max(fit[0] for fit in x) if x else float('-inf'))
            
            # Evaluate the initial population
            print("Evaluating initial population...")
            invalid_ind = [ind for ind in pop if not ind.fitness.valid]
            fitnesses = []
            
            for i, ind in enumerate(invalid_ind):
                try:
                    fit = self.toolbox.evaluate(ind)
                    fitnesses.append(fit)
                except Exception as e:
                    print(f"Error evaluating individual {i}: {e}")
                    fitnesses.append((float(1e6),))  # Very high penalty for errors
            
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit
            
            # Update hall of fame with initial population
            hof.update(pop)
            
            # Log initial statistics
            record = stats.compile(pop)
            print(f"Initial population: min={record['min']}, avg={record['avg']}")
            
            # Run the genetic algorithm
            print(f"Starting genetic algorithm with {self.generations} generations...")
            
            # Increase generations for better convergence
            num_generations = self.generations
            
            # Create multiple sub-populations (islands)
            num_islands = 3
            island_size = len(pop) // num_islands
            islands = [pop[i*island_size:(i+1)*island_size] for i in range(num_islands)]
            
            # Island-specific parameters
            island_params = [
                {'cxpb': 0.7, 'mutpb': 0.2},  # First island: standard parameters
                {'cxpb': 0.5, 'mutpb': 0.4},  # Second island: higher mutation
                {'cxpb': 0.9, 'mutpb': 0.1}   # Third island: higher crossover
            ]
            
            # Main evolution loop
            for gen in range(1, num_generations + 1):
                # Evolve each island separately
                for i, island in enumerate(islands):
                    # Select parameters for this island
                    params = island_params[i]
                    cxpb = params['cxpb']
                    mutpb = params['mutpb']
                    
                    # Select the next generation individuals
                    offspring = self.toolbox.select(island, len(island))
                    
                    # Clone the selected individuals
                    offspring = list(map(self.toolbox.clone, offspring))
                    
                    # Apply crossover
                    for i in range(1, len(offspring), 2):
                        if i < len(offspring) - 1 and random.random() < cxpb:
                            self.toolbox.mate(offspring[i - 1], offspring[i])
                            del offspring[i - 1].fitness.values, offspring[i].fitness.values
                    
                    # Apply mutation
                    for i in range(len(offspring)):
                        if random.random() < mutpb:
                            self.toolbox.mutate(offspring[i])
                            del offspring[i].fitness.values
                    
                    # Evaluate the new individuals
                    invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
                    fitnesses = []
                    
                    for i, ind in enumerate(invalid_ind):
                        try:
                            fit = self.toolbox.evaluate(ind)
                            fitnesses.append(fit)
                        except Exception as e:
                            print(f"Error evaluating individual in generation {gen}: {e}")
                            fitnesses.append((float(1e6),))  # Very high penalty for errors
                    
                    for ind, fit in zip(invalid_ind, fitnesses):
                        ind.fitness.values = fit
                    
                    # Update the island population
                    island[:] = offspring
                
                # Migration between islands every 5 generations
                if gen % 5 == 0:
                    for i in range(num_islands):
                        next_island = (i + 1) % num_islands
                        
                        # Select best individuals from this island
                        migrants = tools.selBest(islands[i], 5)
                        
                        # Select worst individuals from next island to replace
                        islands[next_island].sort(key=lambda ind: ind.fitness.values[0], reverse=True)
                        
                        # Replace worst with migrants
                        for j in range(min(5, len(migrants))):
                            islands[next_island][j] = self.toolbox.clone(migrants[j])
                
                # Combine islands to update hall of fame and statistics
                combined_pop = []
                for island in islands:
                    combined_pop.extend(island)
                
                # Update hall of fame
                hof.update(combined_pop)

                if gen % 10 == 0 and len(hof) > 0:
                    # Insert the best individual from hall of fame into each island
                    for i in range(num_islands):
                        if len(islands[i]) > 0:
                            # Replace a random individual with the best
                            random_idx = random.randint(0, len(islands[i]) - 1)
                            islands[i][random_idx] = self.toolbox.clone(hof[0])
                            
                # Log statistics periodically
                if gen % 10 == 0 or gen == num_generations:
                    record = stats.compile(combined_pop)
                    print(f"Generation {gen}: min={record['min']}, avg={record['avg']}")
                
                # Population refresh every 25 generations to avoid premature convergence
                if gen % 25 == 0 and gen < num_generations - 25:
                    for i in range(num_islands):
                        # Keep the best 25% of individuals
                        best_quarter = tools.selBest(islands[i], len(islands[i]) // 4)
                        
                        # Generate new individuals for the rest 75%
                        new_individuals = self.toolbox.population(n=len(islands[i]) - len(best_quarter))
                        
                        # Evaluate new individuals
                        fitnesses = []
                        for ind in new_individuals:
                            try:
                                fit = self.toolbox.evaluate(ind)
                                fitnesses.append(fit)
                            except Exception as e:
                                fitnesses.append((float(1e6),))
                        
                        for ind, fit in zip(new_individuals, fitnesses):
                            ind.fitness.values = fit
                        
                        # Combine best with new individuals
                        islands[i] = best_quarter + new_individuals
            
            print("Genetic algorithm completed")
            
            # Combine islands for final selection
            final_pop = []
            for island in islands:
                final_pop.extend(island)
            
            # Apply the best solution
            if len(hof) > 0:
                print(f"Best fitness: {hof[0].fitness.values[0]}")
                optimized_schedules = self._apply_breaks(hof[0], initial_schedules)
                
                # Store the best schedule
                self.best_schedule = optimized_schedules
                
                return optimized_schedules
            else:
                print("No valid solutions found")
                return initial_schedules
                
        except Exception as e:
            print(f"Error in genetic algorithm: {e}")
            import traceback
            traceback.print_exc()
            return initial_schedules

    def visualize_schedule(self, schedules=None):
        """
        Generate visualization data for the schedule.
        
        Args:
            schedules (dict): Optimized schedules to visualize, or use self.best_schedule if None
            
        Returns:
            dict: Data for visualization
        """
        if schedules is None:
            schedules = self.best_schedule
            
        if not schedules:
            return None
            
        # Prepare data for Gantt chart
        gantt_data = []
        
        # Track violations for highlighting
        violations = {
            'ramp': self._identify_resource_violations(schedules, 'ramp'),
            'worker': self._identify_resource_violations(schedules, 'worker')
        }
        
        # Identify preprah shuttles and their destinations
        preprah_shuttles = {}
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            if shuttle and shuttle['shuttle_type'] == 'preprah':
                preprah_shuttles[shuttle_id] = shuttle.get('preprah_destination')
        
        # Convert schedules to visualization format
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            is_preprah = shuttle_id in preprah_shuttles
            preprah_destination = preprah_shuttles.get(shuttle_id)
            
            # If this is a preprah shuttle, add the constant ramp reservation as a background event
            if is_preprah and preprah_destination:
                # Get plant name
                plant_name = "Unknown"
                for plant in self.plants:
                    if plant['identifier'] == preprah_destination:
                        plant_name = plant['name']
                        break
                
                # Add preprah ramp reservation event
                gantt_data.append({
                    'shuttle_id': shuttle_id,
                    'shuttle_name': shuttle.get('name', f"Shuttle {shuttle_id}"),
                    'operation_type': 'preprah_reserved',
                    'start_time': self.start_time.strftime("%H:%M"),
                    'end_time': (self.start_time + timedelta(hours=shuttle['shift_length'])).strftime("%H:%M"),
                    'duration': shuttle['shift_length'] * 60,
                    'has_violation': False,
                    'violation_type': None,
                    'frequency_num': 0,
                    'plant_name': plant_name,
                    'plant_id': preprah_destination,
                    'is_background': True  # Special flag for styling
                })
            
            # Add regular operations - filter out load/unload at preprah destination
            for op in schedule['operations']:
                # Skip load/unload operations at preprah destination
                is_preprah_op = op.get('is_preprah_operation', False)
                plant_id = op.get('plant')
                
                if is_preprah and is_preprah_op and op['type'] in ['load', 'unload'] and plant_id == preprah_destination:
                    continue
                    
                # Check if this operation is involved in a violation
                has_violation = False
                violation_type = None
                
                # Check ramp violations
                for violation in violations['ramp']:
                    if (shuttle_id == violation['shuttle_id'] and 
                        op['operation_num'] == violation['operation_num']):
                        has_violation = True
                        violation_type = 'ramp'
                        break
                
                # Check worker violations
                if not has_violation:
                    for violation in violations['worker']:
                        if (shuttle_id == violation['shuttle_id'] and 
                            op['operation_num'] == violation['operation_num']):
                            has_violation = True
                            violation_type = 'worker'
                            break
                
                # Create event data
                event = {
                    'shuttle_id': shuttle_id,
                    'shuttle_name': shuttle.get('name', f"Shuttle {shuttle_id}"),
                    'operation_type': op['type'],
                    'start_time': op['start_time'].strftime("%H:%M"),
                    'end_time': op['end_time'].strftime("%H:%M"),
                    'duration': op['duration'],
                    'has_violation': has_violation,
                    'violation_type': violation_type,
                    'frequency_num': op.get('frequency_num', 0),
                    'is_preprah_operation': op.get('is_preprah_operation', False)
                }
                
                # Add plant information if applicable
                if op['plant'] is not None:
                    plant_id = op['plant']
                    if plant_id in self.plants_by_id:
                        event['plant_name'] = self.plants_by_id[plant_id].get('name', f"Plant {plant_id}")
                        event['plant_id'] = plant_id
                
                # Add travel information if applicable
                if op['type'] == 'travel':
                    from_plant_id = op['from_plant']
                    to_plant_id = op['to_plant']
                    
                    if from_plant_id in self.plants_by_id:
                        event['from_plant_name'] = self.plants_by_id[from_plant_id].get('name', f"Plant {from_plant_id}")
                        event['from_plant_id'] = from_plant_id
                        
                    if to_plant_id in self.plants_by_id:
                        event['to_plant_name'] = self.plants_by_id[to_plant_id].get('name', f"Plant {to_plant_id}")
                        event['to_plant_id'] = to_plant_id
                
                # Special handling for preprah operations
                if op['type'] == 'preprah':
                    # Mark preprah operations as using two ramps
                    event['uses_two_ramps'] = True
                
                gantt_data.append(event)
        
        return {
            'gantt_data': gantt_data,
            'violations': {
                'ramp': len(violations['ramp']),
                'worker': len(violations['worker']),
                'details': violations
            }
        }
        
    def _identify_resource_violations(self, schedules, resource_type):
        """
        Identify specific resource capacity violations.
        
        Args:
            schedules (dict): Schedules to check
            resource_type (str): 'ramp' or 'worker'
            
        Returns:
            list: Violations with details
        """
        violations = []
        
        # Calculate resource usage
        if resource_type == 'ramp':
            usage_data = self._calculate_ramp_usage(schedules)
        else:
            usage_data = self._calculate_worker_usage(schedules)
        
        # Track which operations already have violations to avoid duplicates
        operation_violations = set()
        
        # Identify preprah destinations
        preprah_destinations = {}  # plant_id -> set of shuttle_ids
        for shuttle_id, schedule in schedules.items():
            shuttle = self.get_shuttle_by_id(shuttle_id)
            if shuttle and shuttle['shuttle_type'] == 'preprah':
                preprah_destination = shuttle.get('preprah_destination')
                if preprah_destination:
                    if preprah_destination not in preprah_destinations:
                        preprah_destinations[preprah_destination] = set()
                    preprah_destinations[preprah_destination].add(shuttle_id)
        
        # Check each plant's resource usage
        for plant_id, usages in usage_data.items():
            if plant_id not in self.plants_by_id:
                continue
                
            plant = self.plants_by_id[plant_id]
            capacity = plant['ramp_capacity'] if resource_type == 'ramp' else plant['worker_capacity']
            
            # Sort operations by start time
            sorted_usages = sorted(usages, key=lambda x: x['start_time'])
            
            # Find all time points where resource usage might change
            time_points = []
            for usage in sorted_usages:
                time_points.append(usage['start_time'])
                time_points.append(usage['end_time'])
            time_points = sorted(set(time_points))
            
            # Check resource usage at each time point
            for i in range(len(time_points) - 1):
                current_time = time_points[i]
                next_time = time_points[i+1]
                
                # Skip intervals with zero length
                if current_time == next_time:
                    continue
                
                # Find all operations active during this time interval
                active_operations = []
                permanent_reservations = set()  # Set of shuttle_ids with permanent reservations
                
                for usage in sorted_usages:
                    # Skip preprah_reserved for worker violations (they don't use workers)
                    if resource_type == 'worker' and usage.get('operation') == 'preprah_reserved':
                        continue
                        
                    if usage['start_time'] <= current_time and usage['end_time'] > current_time:
                        if usage.get('operation') == 'preprah_reserved':
                            # Track permanent reservations separately
                            permanent_reservations.add(usage.get('shuttle_id'))
                        else:
                            active_operations.append(usage)
                
                # Calculate total resource usage for this interval
                total_usage = 0
                
                # For ramp usage, count regular operations + 1 permanent reservation per preprah destination
                if resource_type == 'ramp':
                    regular_usage = len(active_operations)
                    permanent_usage = len(permanent_reservations)
                    total_usage = regular_usage + permanent_usage
                else:
                    # For workers, just count non-preprah-reserved operations
                    total_usage = len(active_operations)
                
                # Check if capacity is exceeded
                if total_usage > capacity:
                    # For each active operation, create a violation
                    for op in active_operations:
                        shuttle_id = op.get('shuttle_id')
                        operation = op.get('operation')
                        
                        # Skip preprah_reserved operations (they're not real operations)
                        if operation == 'preprah_reserved':
                            continue
                        
                        # Find the corresponding schedule operation
                        schedule = schedules.get(shuttle_id)
                        if not schedule:
                            continue
                            
                        # Find operation in schedule with matching time and type
                        for schedule_op in schedule['operations']:
                            if (schedule_op['start_time'] == op['start_time'] and 
                                schedule_op['type'] == operation):
                                
                                # Create a unique key for this operation
                                op_key = (shuttle_id, schedule_op.get('operation_num'), resource_type)
                                
                                # Only add if we haven't already added a violation for this operation
                                if op_key not in operation_violations:
                                    operation_violations.add(op_key)
                                    
                                    violations.append({
                                        'plant_id': plant_id,
                                        'plant_name': plant.get('name', f"Plant {plant_id}"),
                                        'shuttle_id': shuttle_id,
                                        'operation': operation,
                                        'operation_num': schedule_op.get('operation_num'),
                                        'start_time': current_time.strftime("%H:%M") if hasattr(current_time, 'strftime') else current_time,
                                        'end_time': next_time.strftime("%H:%M") if hasattr(next_time, 'strftime') else next_time,
                                        'capacity': capacity,
                                        'total_usage': total_usage,
                                        'time_point': current_time,
                                        'resource_type': resource_type  # Add resource type to help with display
                                    })
                                break
        
        # Sort violations by time
        violations.sort(key=lambda x: (x.get('plant_id'), str(x.get('time_point')), x.get('shuttle_id'), x.get('operation_num')))
        
        return violations


class InterFacilityRCMPSP:
    """
    Interface class for RCMPSP simulation to be used in Flask application.
    """
    
    def __init__(self):
        """Initialize the RCMPSP interface."""
        self.optimizer = None
        self.facilities = {}
        self.resources = {}
        self.shuttles = {}
        self.travel_times = {}
        self.shift_models = {}
        self.transportation_projects = {}
        self.schedule = {}
        self.scenario = "median"
        
    def define_facilities_and_resources(self, facilities_data, resources_data):
        """
        Define facilities and their resources.
        
        Args:
            facilities_data (dict): Dictionary mapping facility ID to its properties
            resources_data (dict): Dictionary of resources (ramps, workers) for each facility
        """
        self.facilities = facilities_data
        self.resources = resources_data
        
    def define_travel_times(self, travel_times_data):
        """
        Define travel times between facilities.
        
        Args:
            travel_times_data (dict): Dictionary mapping (source, dest) tuples to travel times
        """
        self.travel_times = travel_times_data
        
    def define_shuttles(self, shuttles_data):
        """
        Define shuttles with their properties.
        
        Args:
            shuttles_data (dict): Dictionary mapping shuttle ID to its properties
        """
        self.shuttles = shuttles_data
        
    def define_shift_models(self, shift_models_data):
        """
        Define shift models.
        
        Args:
            shift_models_data (dict): Dictionary mapping shift model name to its properties
        """
        self.shift_models = shift_models_data
        
    def define_transportation_projects(self, projects_data):
        """
        Define transportation projects.
        
        Args:
            projects_data (dict): Dictionary mapping project ID to its properties
        """
        self.transportation_projects = projects_data
        
    def load_from_database(self, shuttles, plants, travel_times, route_statistics):
        """
        Load data from application database objects.
        
        Args:
            shuttles (list): List of shuttle objects from database
            plants (list): List of plant objects from database
            travel_times (dict): Travel times matrix
            route_statistics (dict): Route statistics keyed by shuttle_id
            scenario (str): Scenario to use for optimization
        """
        # Create the optimizer with the loaded data
        self.optimizer = ScheduleOptimizer(shuttles, plants, travel_times)
        
        # Load statistics for each shuttle
        for shuttle_id, stats in route_statistics.items():
            self.optimizer.load_shuttle_stats(shuttle_id, stats, self.scenario)
            
    def generate_activities(self):
        """
        Generate activities for the scheduling problem.
        This method creates initial schedules for each shuttle.
        """
        if not self.optimizer:
            raise ValueError("Data must be loaded first using load_from_database")
            
        # Create initial schedules for all shuttles
        for shuttle_id in self.optimizer.shuttle_stats.keys():
            self.optimizer.create_initial_schedule(shuttle_id)
            
    def solve_model(self, time_horizon=480, time_limit=60):
        """
        Solve the RCMPSP model using genetic algorithm.
        
        Args:
            time_horizon (int): Time horizon in minutes
            time_limit (int): Time limit for solving in seconds
            
        Returns:
            bool: True if a feasible solution was found, False otherwise
        """
        if not self.optimizer:
            raise ValueError("Data must be loaded first using load_from_database")
            
        # Track start time for time limit
        start_time = time.time()
        
        # Set maximum generations based on time limit
        #self.optimizer.generations = min(100, max(20, int(time_limit / 0.5)))
        
        # Run the genetic algorithm
        optimized_schedules = self.optimizer.optimize_schedules(self.scenario)
        
        if optimized_schedules:
            self.schedule = optimized_schedules
            return True
            
        return False
        
    def get_visualization_data(self):
        """
        Get data for visualization of the schedule.
        
        Returns:
            dict: Data for visualization
        """
        if not self.optimizer or not self.optimizer.best_schedule:
            return None
            
        return self.optimizer.visualize_schedule()
        
    def get_schedule_summary(self):
        """
        Get a summary of the schedule.
        
        Returns:
            dict: Summary statistics
        """
        if not self.optimizer or not self.optimizer.best_schedule:
            return None
            
        # Calculate overall statistics
        total_violations = 0
        total_frequencies = 0
        total_idle_time = 0
        
        vis_data = self.optimizer.visualize_schedule()
        if vis_data:
            total_violations = vis_data['violations']['ramp'] + vis_data['violations']['worker']
        
        # Calculate frequencies completed for each shuttle
        for shuttle_id, schedule in self.optimizer.best_schedule.items():
            total_frequencies += schedule.get('frequencies_completed', 0)
            
            # Calculate idle time
            ops = sorted(schedule['operations'], key=lambda x: x['start_time'])
            for i in range(1, len(ops)):
                prev_op = ops[i-1]
                curr_op = ops[i]
                idle_time = (curr_op['start_time'] - prev_op['end_time']).total_seconds() / 60
                if idle_time > 5:
                    total_idle_time += idle_time
        
        return {
            'total_violations': total_violations,
            'total_frequencies': total_frequencies,
            'total_idle_time': total_idle_time,
            'shuttles_scheduled': len(self.optimizer.best_schedule),
            'solution_quality': 'Good' if total_violations < 20  else 'Fair' if total_violations < 50 else 'Poor'
        }
    
    def get_best_schedule(self):
        if not self.optimizer or not self.optimizer.best_schedule:
            return None
        
        return self.optimizer.best_schedule