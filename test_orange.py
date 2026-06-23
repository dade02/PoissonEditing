import numpy as np
from utils import read_image
from local_illumination_change import LocalIlluminationChangeSolver
import cv2

source = read_image("data/local_illumination_changes/test8/source.jpg")
mask = read_image("data/local_illumination_changes/test8/mask.jpg", gray=True)

# Try beta = 0.2
solver1 = LocalIlluminationChangeSolver(source, mask, mode='luminance')
solver1.beta = 0.2
solver1.alpha_factor = 0.2
res1 = solver1.solve()
cv2.imwrite("results/local_illumination_changes/test8/res_beta0.2.jpg", (res1[...,::-1]*255).astype(np.uint8))

# Try beta = 0.5
solver2 = LocalIlluminationChangeSolver(source, mask, mode='luminance')
solver2.beta = 0.5
solver2.alpha_factor = 0.2
res2 = solver2.solve()
cv2.imwrite("results/local_illumination_changes/test8/res_beta0.5.jpg", (res2[...,::-1]*255).astype(np.uint8))

print("Max val beta 0.2:", np.max(res1))
print("Max val beta 0.5:", np.max(res2))
