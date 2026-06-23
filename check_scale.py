import numpy as np
from PIL import Image

img = np.array(Image.open('data/test9/source.jpg'))[..., :3].astype(np.float64) / 255.0
mask = np.array(Image.open('data/test9/mask.png')).astype(np.float64) / 255.0
if mask.ndim == 3: mask = mask[..., 0]
mask = mask > 0.5

# Test directly on RGB
beta = 0.2
for c in range(3):
    channel = img[..., c]
    gy, gx = np.gradient(channel)
    mag = np.sqrt(gx**2 + gy**2)
    alpha = 0.2 * np.mean(mag[mask])
    scale = np.power(alpha, beta) * np.power(mag + 1e-8, -beta)
    print(f"Ch {c}: alpha = {alpha:.4f}, scale min = {scale.min():.4f}, max = {scale.max():.4f}")
