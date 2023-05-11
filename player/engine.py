from ai.pathFinder import AStarPathfinding
from model.hex import Hex
from model.game import Game
from model.vehicle import Vehicle, VehicleType
from model.common import PlayerId
from model.action import ShootAction, MoveAction

from typing import List


VEHICLE_TURN_ORDER = [
    VehicleType.SPG,
    VehicleType.LIGHT_TANK,
    VehicleType.HEAVY_TANK,
    VehicleType.MEDIUM_TANK,
    VehicleType.AT_SPG
]


class Engine():

    def __init__(self, game: Game, player_id: PlayerId):
        self.game = game
        self.player_id = player_id
        self.actions = []
        self.path_finder = AStarPathfinding(game.map.size)

    def __shoot(self, vehicle: Vehicle, enemy: Vehicle):
        target = None
        if vehicle.type == VehicleType.AT_SPG:
            # Fix for problem of AT_SPG because he can only shoot on neighbour hexs
            # We should just find closest neighbour
            minDist = None
            for neighbour in vehicle.position.neighbors():
                dist = neighbour.distance(enemy.position)
                if minDist is None or minDist > dist:
                    minDist = dist
                    target = neighbour
        else:
            target = enemy.position
        self.actions.append(
            ShootAction(self.player_id, vehicle.id, target)
        )

    def __move(self, vehicle: Vehicle, target: Hex):
        self.actions.append(
            MoveAction(self.player_id, vehicle.id, target)
        )

    def __shoot_with_vehicle(self, vehicle: Vehicle) -> bool:
        target = None

        for enemy in self.game.get_enemy_vehicles_for(self.player_id):
            can_attack = self.game.check_neutrality(vehicle, enemy)
            in_range = vehicle.in_shooting_range(
                enemy.position, 
                self.game.map.get_obstacles_for(self.player_id)
            )

            if not can_attack or not in_range:
                continue

            if target is None or target.hp > enemy.hp:
                target = enemy

        if target is not None:
            self.__shoot(vehicle, target)
            return True

        return False

    def __decide_target(self, vehicle: Vehicle, exclude: List[Hex]) -> Hex:
        target = Hex(0, 0, 0)
        base_nodes = self.game.map.get_base_nodes(exclude)

        # We should find closest base target that is reachable
        if base_nodes is not None:
            minDist = base_nodes[0].distance(vehicle.position)
            target = base_nodes[0]

            for node in base_nodes:
                dist = node.distance(vehicle.position)
                if dist < minDist:
                    target = node
                    minDist = dist

        if vehicle.position not in base_nodes and vehicle.hp <= 1:
            # Then we should make target closest repair only if it is closer than base

            # So now let's find closest repair
            if vehicle.type == VehicleType.MEDIUM_TANK:
                repairs = self.game.map.get_light_repairs()
            elif vehicle.type == VehicleType.HEAVY_TANK or vehicle.type == VehicleType.AT_SPG:
                repairs = self.game.map.get_heavy_repairs()
            else:
                return target

            if repairs is None:
                return target
            
            temp = repairs[0]
            minDist = vehicle.position.distance(temp)
            for node in repairs:
                dist = node.distance(vehicle.position)
                if dist < minDist:
                    temp = node
                    minDist = dist
            
            # Now we should see if repair is closer than closest base node
            if temp.distance(vehicle.position) <= target.distance(vehicle.position):
                return temp
        
        if vehicle.position in base_nodes:
            # If you are already in base go to the closest next base node
            minDist = None

            for node in base_nodes:
                if node == vehicle.position:
                    continue
                dist = node.distance(vehicle.position)
                if minDist is None or dist < minDist:
                    target = node
                    minDist = dist

        return target

    def __move_vehicle(self, vehicle: Vehicle):
        obstacles = self.game.get_obstacles_for(self.player_id)
        target = Hex(0, 0, 0)

        # We should get all other vehicles except this one
        other_vehicles = []
        for node, veh in self.game.map.vehicles.items():
            if veh.id == vehicle.id:
                continue
            other_vehicles.append(node)

        exclude = []
        for obst in obstacles:
            exclude.append(obst)
        for veh in other_vehicles:
            exclude.append(veh)
        
        target = self.__decide_target(vehicle, exclude)

        path = self.path_finder.path(
            vehicle.position,
            target,
            exclude,
            vehicle.speed
        )

        if len(path) > 1:
            #move = vehicle.pick_move(path)
            move = path[1]
            while not move.on_line(vehicle.position, obstacles):
                exclude.append(move)
                target = self.__decide_target(vehicle, exclude)

                path = self.path_finder.path(
                    vehicle.position,
                    target,
                    exclude,
                    vehicle.speed
                )
                if len(path) > 1:
                    move = path[1]

            self.game.map.vehicles[move] = vehicle
            self.game.map.vehicles.pop(vehicle.position)
            
            self.__move(vehicle, move)

    def __vehicle_action(self, vehicle):
        shooted = self.__shoot_with_vehicle(vehicle)

        if shooted == False:
            self.__move_vehicle(vehicle)

    def make_turn(self):
        vehicles = self.game.get_vehicles_for(self.player_id)

        for vehicle_type in VEHICLE_TURN_ORDER:
            for vehicle in vehicles[vehicle_type]:
                self.__vehicle_action(vehicle)

        result = self.actions
        self.actions = []

        return result
