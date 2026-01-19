from passiogo_fix import passiogo as pg
import time
from haversine import haversine


first_day_of_sem = 20 # January 20, 2026 for Spring 2026

last_stoptime: dict[int, StopTime] = {} # (stop, time)
distance_traveled: dict[int, float] = {} # distance from last stop to recording time
total_stop_distance: dict[int, float] = {} # distance from one stop to the next
last_position: dict[int, tuple[float, float]] = {} # (latitude, longitude)

class StopNode:
    def __init__(self, stop: pg.Stop, next: StopNode = None):
        self.stop = stop
        self.next = next

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
    distance_threshold_km = 0.01
    return (haversine((float(bus.latitude), float(bus.longitude)), (stop.latitude, stop.longitude)) < distance_threshold_km)

def update_stops(system: pg.TransportationSystem, routes_to_stops: dict[pg.Route, StopNode]):
    log_time = int(time.time())
    target_time = log_time + 60 # run for the next 20 minutes

    with open("rulost_data.csv", "a") as f:
        while int(time.time()) < target_time:
            vehicles = system.getVehicles()
            for vehicle in vehicles:
                # add vehicle to dictionaries if not already present
                if vehicle.id not in last_stoptime.keys():
                    last_stoptime[vehicle.id] = None
                    distance_traveled[vehicle.id] = None
                    total_stop_distance[vehicle.id] = None
                    last_position[vehicle.id] = None
                    print(f"Added vehicle {vehicle.id} to system")
                
                # Vehicle exists but is not established in system
                # check all stops in route to see first stop that bus reaches
                if last_stoptime[vehicle.id] == None:
                    ptr = routes_to_stops[vehicle.routeId]
                    while True:
                        if is_at_stop(vehicle, ptr.stop):
                            last_stoptime[vehicle.id] = StopTime(ptr, int(time.time()), True)
                            distance_traveled[vehicle.id] = 0.0
                            total_stop_distance[vehicle.id] = 0.0
                            last_position[vehicle.id] = (float(vehicle.latitude), float(vehicle.longitude))
                            print(f"Established vehicle {vehicle.id} in system at stop {last_stoptime[vehicle.id].stop_node.stop.name}")
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
                            seconds_since_departure = log_time - last_stoptime[vehicle.id].time
                            distance_left = total_stop_distance[vehicle.id] - distance_traveled[vehicle.id]
                            result_time = int(time.time()) - log_time

                            print(f"{route_id},{stop_id},{semester},{day_of_sem},{day_of_week},{departure_time},{seconds_since_departure},{distance_left},{result_time}")
                            print(f"Stop name is {last_stoptime[vehicle.id].stop_node.next.stop.name}")
                            f.write(f"{route_id},{stop_id},{semester},{day_of_sem},{day_of_week},{departure_time},{seconds_since_departure},{distance_left},{result_time}")
                        else:
                            print(f"Vehicle has gone to {last_stoptime[vehicle.id].stop_node.next.stop.name}")

                        # Reset bus counters
                        last_stoptime[vehicle.id] = StopTime(last_stoptime[vehicle.id].stop_node.next, int(time.time()), True)
                        distance_traveled[vehicle.id] = 0.0
                        total_stop_distance[vehicle.id] = 0.0
                    else:
                        # Update distances
                        if last_stoptime[vehicle.id].reached_stop: # Distance traveled only counts until next loop
                            distance_traveled[vehicle.id] += haversine(last_position[vehicle.id], (float(vehicle.latitude), float(vehicle.longitude))) * 1000
                        
                        total_stop_distance[vehicle.id] += haversine(last_position[vehicle.id], (float(vehicle.latitude), float(vehicle.longitude))) * 1000
                    
                    print(f"Vehicle {vehicle.id} has traveled {distance_traveled[vehicle.id]}, {total_stop_distance[vehicle.id]}")
                    last_position[vehicle.id] = (float(vehicle.latitude), float(vehicle.longitude))
            
            time.sleep(1.5) # timeout to keep machine from exploding

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
            is_in_list = False
            for vehicle in vehicles:
                if vehicle.id == vehicle_id:
                    is_in_list = True
                    break
            
            if not is_in_list:
                last_stoptime.pop(vehicle.id, None)
                distance_traveled.pop(vehicle.id, None)
                total_stop_distance.pop(vehicle_id, None)
                last_position.pop(vehicle.id, None)
            else:
                last_stoptime[vehicle.id].reached_stop = False
        
        # Run update_stops and write_file
        update_stops(system, routes_to_stops)

    

if __name__ == "__main__":
    main()