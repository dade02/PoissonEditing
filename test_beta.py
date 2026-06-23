import numpy as np
from PIL import Image
import os
import sys

sys.path.append('.')
from local_illumination_change import LocalIlluminationChangeSolver

source = 'data/test9/source.jpg'
mask = 'data/test9/mask.png'

for beta in [0.2, 0.5, 0.8]:
    solver = LocalIlluminationChangeSolver(source, mask, mode='rgb', beta=beta)
    res = solver.solve()
    Image.fromarray((np.clip(res, 0, 1) * 255).astype(np.uint8)).save(f'results/test9/beta_{beta}.png')
