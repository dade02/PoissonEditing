import numpy as np
from PIL import Image

src = np.array(Image.open('data/test9/source.jpg')).astype(np.float64)
mask = np.array(Image.open('data/test9/mask.png')) > 0
if mask.ndim == 3: mask = mask[..., 0]

for beta in [0.2, 0.5, 0.8]:
    res = np.array(Image.open(f'results/test9/beta_{beta}.png')).astype(np.float64)
    diff = np.abs(src - res)
    print(f"Beta {beta}: Max diff={diff.max():.1f}, Mean diff in mask={diff[mask].mean():.1f}")
