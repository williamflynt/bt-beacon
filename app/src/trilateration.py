import math
import numpy

from scipy.optimize import minimize


class TrilaterationSolver(object):
    def __init__(self, method="L-BFGS-B",
                 tolerance=1e-5, iterations=1e+2):
        self.initial_guess = numpy.asarray((0, 0))
        self.method = method
        self.tolerance = tolerance
        self.iterations = iterations

    @staticmethod
    def distance_calc(x1, y1, x2, y2):
        """
        Pythagorean Theorem in action
        :param x1: float or int X Coord for Point 1
        :param y1: float or int Y Coord for Point 1
        :param x2: float or int X Coord for Point 2
        :param y2: float or int Y Coord for Point 2
        :return: float Distance in same units as provided coordinates
        """
        x1 = float(x1)
        x2 = float(x2)
        y1 = float(y1)
        y2 = float(y2)
        distance = math.sqrt(((x1 - x2) ** 2) + ((y1 - y2) ** 2))
        return distance

    def mse(self, test_point, locations, distances):
        """
        Mean Square Error
        :param test_point: tuple A tuple of coordinates like (x_coord, y_coord)
        :param locations: [ (x_coord1, y_coord1), ... ]
        :param distances: [ distance1, distance2, ... ]
        :return: float Mean square error in same units as coordinates
        """
        data = zip(locations, distances)
        mse = 0.0
        location_count = 0
        for location, distance in data:
            distance_calculated = self.distance_calc(test_point[0],
                                                     test_point[1],
                                                     location[0],
                                                     location[1])
            calced_error = distance_calculated - distance
            # primitive attempt at weighting "near" results
            # ex: distance is 6.5m
            # error_mod is 1.5
            # calced_error is multiplied by (1 - .015)
            # calced_error = 0.985 * calced_error
            error_mod = max(0, distance-1.5)
            calced_error *= (1-(error_mod/100.0))

            mse += math.pow(calced_error, 2.0)
            location_count += 1
        return mse / location_count

    def best_point(self, locations, distances):
        """
        Find the point with the minimal error given a set of known points
         and distances from those points.
        :param locations: list Known node locations [ (x_coord1, y_coord1), ... ]
        :param distances: list Our RSSI-based distance guesses [ distance1, distance2, ... ]
        :return: tuple The coordinates of the minimal-error solution
        """
        # Find a reasonable initial guess using the closest distance guess
        data = zip(locations, distances)
        min_distance = float('inf')
        closest_location = None
        for loc, dist in data:
            # A new closest point!
            if dist < min_distance:
                min_distance = dist
            closest_location = loc
        self.initial_guess = closest_location

        result = minimize(
            self.mse,  # The error function
            self.initial_guess,  # The initial guess
            args=(locations, distances),  # Additional parameters for mse
            method=self.method,  # The optimisation algorithm
            options={
                'ftol': self.tolerance,  # Tolerance
                'maxiter': self.iterations  # Maximum iterations
            })

        return {"coords": tuple(result.x),
                "avg_err": math.sqrt(result.fun)}
