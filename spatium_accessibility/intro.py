"""Pure timing functions for the decorative introduction, not analysis progress."""
from math import isfinite
DURATION=4.8

def phase(seconds,start,end):
    if end<=start: raise ValueError('Animation interval must be positive.')
    fraction=max(0.0,min(1.0,(seconds-start)/(end-start)))
    return fraction*fraction*(3-2*fraction)

def progress(seconds):
    if not isfinite(seconds): return 0.0
    return max(0.0,min(1.0,seconds/DURATION))
