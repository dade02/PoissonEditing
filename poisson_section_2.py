"""
SECTION 2: POISSON SOLUTION TO GUIDED INTERPOLATION
=====================================================

Implementazione della Sezione 2 del paper "Poisson Image Editing"
(Pérez, Gangnet, Blake - SIGGRAPH 2003)

Risolve l'equazione di Poisson discreta su immagini reali:
- Carica immagini reali da file (source, target, mask)
- Calcola gradienti dalle immagini
- Risolve Poisson equation discreta con solver scipy
- Supporta opzionalmente multigrid (pyamg)

NOTAZIONE:
- Ω: dominio interior (mask interno)
- ∂Ω: boundary (confine della maschera)
- f*: immagine target (valori noti)
- f: soluzione interpolata
- v: guidance vector field (gradienti)
"""

import numpy as np
import cv2
from scipy import sparse
import scipy.sparse.linalg
from PIL import Image
import matplotlib.pyplot as plt
from argparse import ArgumentParser
try:
    import pyamg
    HAS_PYAMG = True
except ImportError:
    HAS_PYAMG = False


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def read_image(file_path, gray=False):
    """Legge immagine da file e normalizza [0, 1]."""
    img = Image.open(file_path)
    if gray:
        img = img.convert('L')
    img = np.array(img)
    if len(img.shape) == 3:
        img = img[..., :3]
    return img.astype(np.float64) / 255.0

def compute_gradient(img, forward=True):
    """Calcola gradienti (∂x, ∂y) usando differenze finite."""
    if forward:
        kx = np.array([[0, 0, 0], [0, -1, 1], [0, 0, 0]])
        ky = np.array([[0, 0, 0], [0, -1, 0], [0, 1, 0]])
    else:
        kx = np.array([[0, 0, 0], [-1, 1, 0], [0, 0, 0]])
        ky = np.array([[0, -1, 0], [0, 1, 0], [0, 0, 0]])
    
    import scipy.signal
    Gx = scipy.signal.fftconvolve(img, kx, mode='same')
    Gy = scipy.signal.fftconvolve(img, ky, mode='same')
    return Gx, Gy

def compute_laplacian(img):
    """Calcola Laplaciano: ∆f = ∂²f/∂x² + ∂²f/∂y²."""
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
    import scipy.signal
    laplacian = scipy.signal.fftconvolve(img, kernel, mode='same')
    return laplacian

def process_mask(mask):
    """Divide maschera in inner (interior) e boundary."""
    from skimage.segmentation import find_boundaries
    boundary = find_boundaries(mask, mode='inner').astype(int)
    inner = mask - boundary
    return inner, boundary

def get_pixel_ids(img_shape):
    """Mappa pixel 2D a indici lineari."""
    return np.arange(img_shape[0] * img_shape[1]).reshape(img_shape)

def get_masked_values(values, mask):
    """Estrae valori dove mask == 1."""
    return values[mask > 0]


# ============================================================================
# DISCRETE POISSON SOLVER (Sezione 2)
# ============================================================================

"""
DISCRETIZZAZIONE DELL'EQUAZIONE DI POISSON - IMPLEMENTAZIONE PRATICA
=====================================================================

Eq. (4) del paper - Poisson equation:
    ∆f = div(v)  over Ω
    f|∂Ω = f*|∂Ω
- S, Ω: ora sono insiemi finiti di pixel sulla griglia discreta
- p: pixel in Ω
- N_p: insieme dei 4-connected neighbors di p che sono in S
- <p,q>: coppia di pixel adiacenti
- f_p: valore di f al pixel p
- ∂Ω = {p ∈ S \ Ω : N_p ∩ Ω ≠ ∅}  (boundary: pixel fuori Ω adiacenti a Ω)

DISCRETIZZAZIONE DELLA VARIATIONAL PROBLEM (Eq. 3):
    min_f ∑_{<p,q> ∩ Ω ≠ ∅} (f_p - f_q - v_pq)²
    
    con f_p = f*_p per tutti p ∈ ∂Ω

Per ogni pixel interno p:
- Se q è neighbor interno: contribuisce (f_p - f_q - v_pq)²
- Se q è boundary: contribuisce (f_p - f*_q - v_pq)² (f*_q è noto)

EQUAZIONE LINEARE RISULTANTE (Euler-Lagrange discreto):
    |N_p| · f_p - ∑_{q ∈ N_p ∩ Ω} f_q = ∑_{q ∈ N_p} v_pq + ∑_{q ∈ ∂Ω} f*_q
    
    Questa è la forma discreta dell'equazione di Poisson.
"""

class PoissonInterpolationSolver:
    """
    Solutore dell'equazione di Poisson discreta (Section 2).
    
    Carica immagini reali da file e risolve:
        ∆f = div(v)  over Ω
        f|∂Ω = f*|∂Ω
    """
    
    def __init__(self, source_path, target_path, mask_path, solver='spsolve'):
        """
        Inizializza il solutore caricando immagini da file.
        
        Args:
            source_path: percorso immagine sorgente (guidance)
            target_path: percorso immagine target (boundary values)
            mask_path: percorso maschera (dominio Ω)
            solver: 'spsolve' (scipy LU) o 'multigrid' (pyamg)
        """
        # Carica immagini
        print(f"Caricamento immagini...")
        self.source = read_image(source_path, gray=True)
        self.target = read_image(target_path, gray=True)
        self.mask_raw = read_image(mask_path, gray=True)
        
        print(f"  Source:  {source_path} {self.source.shape}")
        print(f"  Target:  {target_path} {self.target.shape}")
        print(f"  Mask:    {mask_path} {self.mask_raw.shape}")
        
        # Threshold e process mask
        _, self.mask = cv2.threshold(self.mask_raw, 0.5, 1, cv2.THRESH_BINARY)
        self.inner_mask, self.boundary_mask = process_mask(self.mask)
        
        self.img_h, self.img_w = self.mask.shape
        
        # Solver setup
        self.solver_type = solver
        if solver != 'multigrid':
            self.solver_func = getattr(scipy.sparse.linalg, solver)
        else:
            if not HAS_PYAMG:
                print("⚠ pyamg non disponibile, fallback a spsolve")
                self.solver_func = scipy.sparse.linalg.spsolve
                self.solver_type = 'spsolve'
            else:
                self.solver_func = None
        
        # Pixel mappings (come in seamless_cloning.py)
        self.pixel_ids =lf.img_w))
        self.inner_ids = get_masked_values(self.pixel_ids, self.inner_mask).flatten()
        self.boundary_ids = get_masked_values(self.pixel_ids, self.boundary_mask).flatten()
        self.mask_ids = get_masked_values(self.pixel_ids, self.mask).flatten()
        
        self.inner_pos = np.searchsorted(self.mask_ids, self.inner_ids)
        self.boundary_pos = np.searchsorted(self.mask_ids, self.boundary_ids)
        self.mask_pos = np.searchsorted(self.pixel_ids.flatten(), self.mask_ids)
        
        print(f"Dominio Ω: {len(self.inner_ids)} pixel (interior) + {len(self.boundary_ids)} pixel (boundary)")
        
        # Costruisci matrice A
        self.A = self._construct_A_matrix()
    
    def _construct_A_matrix(self):
        """
        Costruisce matrice A della stencil Laplaciana discreta.
        
        Per ogni pixel p in Ω:
            |N_p| · f_p - Σ_{q ∈ N_p} f_q = ...
        
        dove |N_p| è il numero di neighbors (4-connected).
        """
        n1_pos = np.searchsorted(self.mask_ids, self.inner_ids - 1)
        n2_pos = np.searchsorted(self.mask_ids, self.inner_ids + 1)
        n3_pos = np.searchsorted(self.mask_ids, self.inner_ids - self.img_w)
        n4_pos = np.searchsorted(self.mask_ids, self.inner_ids + self.img_w)
        
        # Costruisci formato COO per efficienza
        row_ids = np.concatenate([
            self.inner_pos, self.inner_pos, self.inner_pos, self.inner_pos, self.inner_pos, 
            self.boundary_pos
        ])
        col_ids = np.concatenate([
            n1_pos, n2_pos, n3_pos, n4_pos, self.inner_pos, 
            self.boundary_pos
        ])
        data = ([1] * len(self.inner_pos) * 4 + 
                [-4] * len(self.inner_pos) + 
                [1] * len(self.boundary_pos))
        
        A = sparse.csr_matrix(
            (data, (row_ids, col_ids)),
            shape=(len(self.mask_ids), len(self.mask_ids))
        )
        
        print(f"Matrice A: {A.shape}, nnz={A.nnz}")
        return A
    
    def _construct_b_vector(self, guidance_laplacian, target_boundary):
        """
        Costruisce vettore b dalla divergenza del guidance field e boundary values.
        
        Args:
            guidance_laplacian: Laplaciano del guidance field
            target_boundary: valori di target sul boundary
            
        Returns:
            b: vettore dei termini noti
        """
        b = np.zeros(len(self.mask_ids))
        inner_laplacian = get_masked_values(guidance_laplacian, self.inner_mask).flatten()
        boundary_values = get_masked_values(target_boundary, self.boundary_mask).flatten()
        
        b[self.inner_pos] = inner_laplacian
        b[self.boundary_pos] = boundary_values
        
        return b
    
    def solve(self):
        """
        Risolve l'equazione di Poisson.
        
        Returns:
            result: array 2D della soluzione interpolata
        """
        # Calcola guidance field (Laplaciano della sorgente)
        print(f"\nCalcolo guidance field...")
        guidance_laplacian = compute_laplacian(self.source)
        
        # Costruisci vettore b
        b = self._construct_b_vector(guidance_laplacian, self.target)
        
        # Risolvi Ax = b
        print(f"Risoluzione Poisson equation (solver={self.solver_type})...")
        if self.solver_type == 'multigrid':
            ml = pyamg.ruge_stuben_solver(self.A)
            x = ml.solve(b, tol=1e-10)
        else:
            x = self.solver_func(self.A, b)
            if isinstance(x, tuple):  # alcuni solver ritornano (sol, info)
                x = x[0]
        
        # Ricomponi risultato sulla griglia completa
        result = np.zeros((self.img_h * self.img_w))
        result[self.mask_pos] = x
        result = result.reshape((self.img_h, self.img_w))
        
        # Clip e normalizza
        result = np.clip(result, 0, 1)
        
        print(f"✓ Soluzione trovata")
        return result


# ============================================================================
# MAIN: Esempio con immagini da file
# ============================================================================

def main():
    """
    Risolve Poisson equation su immagini reali.
    
    Uso:
        python poisson_section_2.py <source> <target> <mask> [--solver spsolve|multigrid]
    
    Esempio con file di test:
        python poisson_section_2.py background_gradient.png background_gradient.png pattern_guidance.png
    """
    parser = ArgumentParser(description='Section 2 - Poisson Guided Interpolation')
    parser.add_argument('source', help='Percorso immagine sorgente (guidance)')
    parser.add_argument('target', help='Percorso immagine target (boundary values)')
    parser.add_argument('mask', help='Percorso maschera (dominio Ω)')
    parser.add_argument('--solver', default='spsolve', 
                       choices=['spsolve', 'gmres', 'lgmres', 'multigrid'],
                       help='Solver da usare')
    parser.add_argument('--output', default='poisson_result.png', help='File output')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("SECTION 2: POISSON GUIDED INTERPOLATION")
    print("="*70)
    
    # Crea solutore e risolvi
    solver = PoissonInterpolationSolver(args.source, args.target, args.mask, solver=args.solver)
    result = solver.solve()
    
    # Visualizza e salva
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    
    axes[0].imshow(solver.source, cmap='gray', vmin=0, vmax=1)
    axes[0].set_title('Source\n(Guidance Field)')
    axes[0].axis('off')
    
    axes[1].imshow(solver.target, cmap='gray', vmin=0, vmax=1)
    axes[1].set_title('Target\n(Boundary Values)')
    axes[1].axis('off')
    
    axes[2].imshow(solver.mask, cmap='gray')
    axes[2].set_title('Mask\n(Dominio Ω)')
    axes[2].axis('off')
    
    axes[3].imshow(result, cmap='gray', vmin=0, vmax=1)
    axes[3].set_title('Risultato Poisson\n(Interpolazione Guidata)')
    axes[3].axis('off')
    
    plt.tight_layout()
    plt.savefig(args.output, dpi=100, bbox_inches='tight')
    print(f"\n✓ Risultato salvato: {args.output}")


if __name__ == '__main__':
    main()
