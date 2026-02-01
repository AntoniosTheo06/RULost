from passiogo_fix import passiogo as pg
import time
from haversine import haversine


first_day_of_sem = 20 # January 20, 2026 for Spring 2026

last_stoptime: dict[str, StopTime] = {} # (stop, time, reached destination)
distance_since_log: dict[str, float] = {} # distance from last stop to recording time
total_stop_distance: dict[str, float] = {} # distance from one stop to the next
last_position: dict[str, tuple[float, float]] = {} # (latitude, longitude)
first_log_time: dict[str, int] = {} # time that bus was logged

class StopNode:
    def __init__(self, stop: pg.Stop, next: StopNode = None):
        self.stop = stop
        self.next = next
        self.average_stop_time = 0.0
        self.num_data_points = 0.0

class StopTime:
    def __init__(self, stop_node: StopNode, time: int, reached_stop: bool = False):
        self.stop_node = stop_node
        self.time = time
        self.reached_stop = reached_stop

def ordered_stops(route: pg.Route) -> StopNode:
    """
    Given a route, returns an ordered circular linked list of all the stops along that route
    
    :param route: The route to get stops from
    :type route: passiogo.Route
    """

    # Get stops and sort by position in route
    stops = route.getStops()
    route_id = route.myid
    stops = sorted(stops, key=lambda stop : stop.routesAndPositions[str(route_id)][0])

    # Append duplicate stops to end of list
    additional_stops = []
    for stop in stops:
        if len(stop.routesAndPositions[str(route_id)]) > 1 and stop.routesAndPositions[str(route_id)][0] != 0:
            additional_stops.append(stop)

    additional_stops = sorted(additional_stops, key=lambda stop : stop.routesAndPositions[str(route_id)][1])
    stops += additional_stops

    # Add stops to linked list
    first_node = StopNode(stops[0])
    previous = first_node
    for stop in stops[1:]:
        current = StopNode(stop)
        previous.next = current
        previous = previous.next

    previous.next = first_node
    
    return first_node

def is_at_stop(bus: pg.Vehicle, stop: pg.Stop) -> bool:
    distance_threshold_km = 0.040 # 40 meter radius
    return (haversine((float(bus.latitude), float(bus.longitude)), (stop.latitude, stop.longitude)) < distance_threshold_km)

def time_string():
    localtime = time.localtime()
    return f"{localtime.tm_year}-{localtime.tm_mon}-{localtime.tm_mday} {localtime.tm_hour}:{localtime.tm_min}:{localtime.tm_sec}"

def update_stops(system: pg.TransportationSystem, routes_to_stops: dict[str, StopNode]):
    log_time = int(time.time())
    target_time = log_time + 14 * 60 # run for the next 14 minutes

    with open("rulost_data.csv", "a") as data, open("rulost_stops.txt", "a") as stops, open("log.txt", "a") as log:
        while int(time.time()) < target_time:
            vehicles = system.getVehicles()
            for vehicle in vehicles:
                # add vehicle to dictionaries if not already present
                if vehicle.id not in last_stoptime.keys():
                    last_stoptime[vehicle.id] = None
                    distance_since_log[vehicle.id] = None
                    total_stop_distance[vehicle.id] = None
                    last_position[vehicle.id] = None
                    first_log_time[vehicle.id] = None
                    print(f"Added vehicle {vehicle.id} to system")
                    log.write(f"{time_string()} Added vehicle {vehicle.id} to system")
                
                # Vehicle exists but is not established in system
                # check all stops in route to see first stop that bus reaches
                if last_stoptime[vehicle.id] == None:
                    ptr = routes_to_stops[vehicle.routeId]
                    while True:
                        if is_at_stop(vehicle, ptr.stop):
                            last_stoptime[vehicle.id] = StopTime(ptr, int(time.time()), True)
                            distance_since_log[vehicle.id] = 0.0
                            total_stop_distance[vehicle.id] = 0.0
                            last_position[vehicle.id] = (float(vehicle.latitude), float(vehicle.longitude))
                            first_log_time[vehicle.id] = 0
                            print(f"Established vehicle {vehicle.id} in system at stop {last_stoptime[vehicle.id].stop_node.stop.name}")
                            log.write(f"{time_string()} Established vehicle {vehicle.id} in system at stop {last_stoptime[vehicle.id].stop_node.stop.name}")
                            break
                        ptr = ptr.next
                        if ptr == routes_to_stops[vehicle.routeId]:
                            break
                
                # Vehicle is already established in system
                else:
                    # check if vehicle has reached next stop
                    if is_at_stop(vehicle, last_stoptime[vehicle.id].stop_node.next.stop):
                        # Write to file
                        if not last_stoptime[vehicle.id].reached_stop:
                            route_id = vehicle.routeId
                            stop_id = last_stoptime[vehicle.id].stop_node.next.stop.id
                            semester = 3 # fall, winter, spring, summer
                            day_of_sem = time.localtime().tm_yday - first_day_of_sem
                            day_of_week = time.localtime().tm_wday
                            departure_time = time_of_day(last_stoptime[vehicle.id].time)
                            seconds_since_departure = first_log_time[vehicle.id] - last_stoptime[vehicle.id].time
                            distance_left = distance_since_log[vehicle.id]
                            result_time = int(time.time()) - first_log_time[vehicle.id]

                            print(f"{route_id},{stop_id},{semester},{day_of_sem},{day_of_week},{departure_time},{seconds_since_departure},{distance_left},{result_time}")
                            print(f"Vehicle {vehicle.id} went to {last_stoptime[vehicle.id].stop_node.next.stop.name}")
                            log.write(f"{time_string()} Vehicle {vehicle.id} went to {last_stoptime[vehicle.id].stop_node.next.stop.name}")
                            if distance_left <= 10000: # failsafe against buses missing stops and looping back
                                # Route id, stop id, semester, day of semester, day of week, departure time, seconds since departure, distance left, result time
                                data.write(f"{route_id},{stop_id},{semester},{day_of_sem},{day_of_week},{departure_time},{seconds_since_departure},{distance_left},{result_time}\n")
                                stops.write(f"{last_stoptime[vehicle.id].stop_node.next.stop.name} in route {vehicle.routeId} had distance {total_stop_distance}")
                        else:
                            print(f"Vehicle {vehicle.id} has gone to {last_stoptime[vehicle.id].stop_node.next.stop.name}")
                            print(f"{time_string()} Vehicle {vehicle.id} has gone to {last_stoptime[vehicle.id].stop_node.next.stop.name}")

                        # 

                        # Reset bus counters
                        last_stoptime[vehicle.id] = StopTime(last_stoptime[vehicle.id].stop_node.next, int(time.time()), True)
                        distance_since_log[vehicle.id] = 0.0
                        total_stop_distance[vehicle.id] = 0.0
                    else:
                        # Update distances
                        if not last_stoptime[vehicle.id].reached_stop: # Distance since log only counts after next loop starts
                            distance_since_log[vehicle.id] += haversine(last_position[vehicle.id], (float(vehicle.latitude), float(vehicle.longitude))) * 1000
                        
                        total_stop_distance[vehicle.id] += haversine(last_position[vehicle.id], (float(vehicle.latitude), float(vehicle.longitude))) * 1000
                    
                    print(f"Vehicle {vehicle.id} has traveled {distance_since_log[vehicle.id]}, {total_stop_distance[vehicle.id]}")
                    last_position[vehicle.id] = (float(vehicle.latitude), float(vehicle.longitude))
            

def time_of_day(time: int) -> int:
    return (time - 5 * 3600) % (3600 * 24) # seconds since midnight

def main():
    # System setup
    system = pg.getSystemFromID(1268)
    routes = system.getRoutes()
    vehicles = system.getVehicles()
    stops = system.getStops()
    for vehicle in vehicles:
        print(vehicle.__dict__)
    print()
    for stop in stops:
        print(stop.__dict__)
    print()
    for route in routes:
        print(route.__dict__)
    print()
    # for stop in routes[5].getStops():
    #     print(stop.__dict__)

    # Stores ordered stops of each route
    routes_to_stops = {}
    for route in routes:
        routes_to_stops[route.myid] = ordered_stops(route)

    while True:
        print("Running main loop")
        vehicles = system.getVehicles()
        # Assign all buses to "not reached stop" and remove ones that go out of service
        for vehicle_id in last_stoptime.keys():
            if last_stoptime[vehicle_id] == None:
                continue

            print(vehicle_id)
            print(last_stoptime[vehicle_id])
            is_in_list = False
            for vehicle in vehicles:
                if int(vehicle.id) == vehicle_id:
                    is_in_list = True
                    break
            
            if not is_in_list:
                last_stoptime.pop(vehicle_id, None)
                distance_since_log.pop(vehicle_id, None)
                total_stop_distance.pop(vehicle_id, None)
                last_position.pop(vehicle_id, None)
                print(f"Deleted vehicle {vehicle_id}")
            else:
                print(last_stoptime[vehicle_id].__dict__)
                if last_stoptime[vehicle_id].reached_stop:
                    last_stoptime[vehicle_id].reached_stop = False
                    first_log_time[vehicle_id] = int(time.time())
                    print(f"Logging vehicle {vehicle_id} at {first_log_time[vehicle_id]}")
        
        # Updates bus info and writes to file
        update_stops(system, routes_to_stops)

    

if __name__ == "__main__":
    main()
