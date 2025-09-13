import math

def linearScale1(value, min_v1, max_v1, start_v2, end_v2):
    return start_v2 + (value - min_v1) * (end_v2 - start_v2) / (max_v1 - min_v1)

def cubic(t):
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2

def quart(t):
    if t < 0.5:
        return 8 * t * t * t * t
    return 1 - pow(-2 * t + 2, 4) / 2

def sine(t):
        return -(math.cos(math.pi * t) - 1) / 2