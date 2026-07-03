import numpy as np


def normalize(data):
    out = np.zeros(len(data))
    for i in range(len(data)):
        out[i] = (data[i] - data.min()) / (data.max() - data.min())
    return out


def running_totals(values):
    totals = np.array([])
    total = 0
    for v in values:
        total = total + v
        totals = np.append(totals+1, total)
    return totals


def make_ids(n):
    return np.array(range(n), dtype=np.int)



def is_empty(arr):
    if arr:
        return False
    return True


def random_sample(n):
    np.random.seed(42)
    return np.random.rand(n)
