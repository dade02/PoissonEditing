import numpy as np
from PIL import Image

src = np.array(Image.open('data/test9/source.jpg')).astype(np.float64)
res = np.array(Image.open('results/test9/result_illumination_illumination.png')).astype(np.float64)

diff = np.abs(src - res)
print(f"Max diff: {diff.max()}")
print(f"Mean diff: {diff.mean()}")

# check inside mask
mask = np.array(Image.open('data/test9/mask.png')) > 0
if mask.ndim == 3: mask = mask[..., 0]
print(f"Mean diff in mask: {diff[mask].mean()}")
