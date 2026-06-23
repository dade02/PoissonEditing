import numpy as np

def test():
    img = np.array([[1., 2., 3.], [4., 5., 6.], [7., 8., 9.]])
    scale = np.ones_like(img)
    
    # Forward diff
    gx = np.roll(img, -1, axis=1) - img
    # Right column rolls to left, we should set boundary to 0 or handle it
    gx[:, -1] = 0
    
    vx = scale * gx
    
    # Backward diff for div
    divx = vx - np.roll(vx, 1, axis=1)
    # Left column rolls from right, so set to 0? No, vx at -1 is 0.
    divx[:, 0] = vx[:, 0]  # since vx(-1) is 0
    
    print("img:\n", img)
    print("gx:\n", gx)
    print("vx:\n", vx)
    print("divx:\n", divx)

test()
