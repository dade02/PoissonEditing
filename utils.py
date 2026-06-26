"""
Utility functions per Poisson Image Editing.

Funzioni di I/O immagini, conversione colore, calcolo gradienti/Laplaciani,
e processamento maschere.

Riferimento: Pérez, Gangnet, Blake - "Poisson Image Editing" (SIGGRAPH 2003)
"""

import numpy as np
from PIL import Image


# ============================================================================
# IMAGE I/O
# ============================================================================

def read_image(file_path, gray=False):
    """Legge immagine da file e normalizza [0, 1]."""
    img = Image.open(file_path).convert('RGB')
    if gray:
        img = img.convert('L')
    img = np.array(img)
    return img.astype(np.float64) / 255.0


# ============================================================================
# COLOR SPACE CONVERSION
# ============================================================================

def rgb_to_lab(img):
    """Converte immagine RGB [0,1] in CIE-Lab usando PIL/skimage."""
    from skimage.color import rgb2lab
    # rgb2lab si aspetta float32 in [0,1] oppure uint8
    lab = rgb2lab(img.astype(np.float32))
    # Normalizza: L in [0,100], a/b in [-128,127] → [0,1]
    lab[..., 0] /= 100.0
    lab[..., 1] = (lab[..., 1] + 128.0) / 255.0
    lab[..., 2] = (lab[..., 2] + 128.0) / 255.0
    return lab

def lab_to_rgb(lab):
    """Converte CIE-Lab normalizzato [0,1] in RGB [0,1]."""
    from skimage.color import lab2rgb
    lab_orig = lab.copy().astype(np.float32)
    lab_orig[..., 0] *= 100.0
    lab_orig[..., 1] = lab_orig[..., 1] * 255.0 - 128.0
    lab_orig[..., 2] = lab_orig[..., 2] * 255.0 - 128.0
    rgb = lab2rgb(lab_orig)
    return np.clip(rgb, 0, 1)


# ============================================================================
# GRADIENT & LAPLACIAN COMPUTATION
# ============================================================================

def compute_laplacian(img):
    """Calcola il Laplaciano discreto puro con vicinato troncato ai bordi dell'immagine.
    Implementa esattamente la divergenza del gradiente sul reticolo discreto.
    """
    if img.ndim == 3:
        h, w, c = img.shape
        laplacian = np.zeros_like(img)
        for i in range(c):
            laplacian[..., i] = compute_laplacian(img[..., i])
        return laplacian

    h, w = img.shape
    neighbor_sum = np.zeros((h, w), dtype=img.dtype)
    Np = np.zeros((h, w), dtype=img.dtype)

    # Vicino sinistro (sposta img a destra)
    neighbor_sum[:, 1:] += img[:, :-1]
    Np[:, 1:] += 1

    # Vicino destro (sposta img a sinistra)
    neighbor_sum[:, :-1] += img[:, 1:]
    Np[:, :-1] += 1

    # Vicino superiore (sposta img in basso)
    neighbor_sum[1:, :] += img[:-1, :]
    Np[1:, :] += 1

    # Vicino inferiore (sposta img in alto)
    neighbor_sum[:-1, :] += img[1:, :]
    Np[:-1, :] += 1

    # ∆g_p = Σ_{q ∈ N_p} g_q - |N_p| * g_p
    return neighbor_sum - Np * img


def compute_mixed_laplacian(source, target, mask):
    """Calcola il Laplaciano del campo di gradiente misto (mixed gradient).

    Per ogni pixel interno, sceglie il gradiente (dx, dy) da source o target
    in base a quale ha magnitudine maggiore, quindi ne calcola la divergenza.
    Il risultato è un array con lo stesso shape di source.
    """
    # Gradienti di source e target (vertical, horizontal)
    gy_src, gx_src = np.gradient(source)
    gy_tgt, gx_tgt = np.gradient(target)
    # Magnitudini
    mag_src = np.sqrt(gx_src**2 + gy_src**2)
    mag_tgt = np.sqrt(gx_tgt**2 + gy_tgt**2)
    # Selezione per pixel
    use_src = mag_src > mag_tgt
    mixed_gx = np.where(use_src, gx_src, gx_tgt)
    mixed_gy = np.where(use_src, gy_src, gy_tgt)
    # Divergenza: d/dx(mixed_gx) + d/dy(mixed_gy)
    div_x = np.gradient(mixed_gx, axis=1)
    div_y = np.gradient(mixed_gy, axis=0)
    mixed_laplacian = div_x + div_y
    # Applicare maschera: zero fuori interior
    mixed_laplacian = mixed_laplacian * mask
    return mixed_laplacian


# ============================================================================
# MASK PROCESSING
# ============================================================================

def process_mask(mask):
    """Divide maschera in inner (interior) e boundary."""
    from scipy.ndimage import binary_erosion
    # Convert mask to boolean for erosion
    mask_bool = mask.astype(bool)
    # Inner region: eroded mask (pixels whose 4-neighborhood is fully inside mask)
    inner = binary_erosion(mask_bool).astype(mask.dtype)
    # Boundary: mask pixels that are not in inner
    boundary = mask - inner
    return inner, boundary

def get_pixel_ids(img_shape):
    """Mappa pixel 2D a indici lineari."""
    if isinstance(img_shape, np.ndarray):
        img_shape = img_shape.shape
    return np.arange(img_shape[0] * img_shape[1]).reshape(img_shape)

def get_masked_values(values, mask):
    """Estrae valori dove mask == 1."""
    return values[mask > 0]

def shift_image(img, dy, dx):
    """Sposta l'immagine img di dy righe e dx colonne, riempiendo con zero."""
    if img.ndim == 3:
        h, w, c = img.shape
        shifted = np.zeros_like(img)
    else:
        h, w = img.shape
        shifted = np.zeros_like(img)
        
    # Target bounds (where to paste in the new shifted image)
    ty1 = max(0, dy)
    ty2 = min(h, h + dy)
    tx1 = max(0, dx)
    tx2 = min(w, w + dx)
    
    # Source bounds (where to copy from the original image)
    sy1 = max(0, -dy)
    sy2 = min(h, h - dy)
    sx1 = max(0, -dx)
    sx2 = min(w, w - dx)
    
    if ty2 > ty1 and tx2 > tx1 and sy2 > sy1 and sx2 > sx1:
        if img.ndim == 3:
            shifted[ty1:ty2, tx1:tx2, :] = img[sy1:sy2, sx1:sx2, :]
        else:
            shifted[ty1:ty2, tx1:tx2] = img[sy1:sy2, sx1:sx2]
            
    return shifted
