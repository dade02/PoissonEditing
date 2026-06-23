"""
DISCRETE POISSON SOLVER (Sezione 2)
====================================

Solutore dell'equazione di Poisson discreta per seamless cloning
su immagini a colori, come descritto nel paper:

    Pérez, Gangnet, Blake - "Poisson Image Editing" (SIGGRAPH 2003)

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
- ∂Ω = {p ∈ S \\ Ω : N_p ∩ Ω ≠ ∅}  (boundary: pixel fuori Ω adiacenti a Ω)

DISCRETIZZAZIONE DELLA VARIATIONAL PROBLEM (Eq. 3):
    min_f ∑_{<p,q> ∩ Ω ≠ ∅} (f_p - f_q - v_pq)²
    
    con f_p = f*_p per tutti p ∈ ∂Ω

Per ogni pixel interno p:
- Se q è neighbor interno: contribuisce (f_p - f_q - v_pq)²
- Se q è boundary: contribuisce (f_p - f*_q - v_pq)² (f*_q è noto)

EQUAZIONE LINEARE RISULTANTE (Euler-Lagrange discreto):
    |N_p| · f_p - ∑_{q ∈ N_p ∩ Ω} f_q = ∑_{q ∈ N_p} v_pq + ∑_{q ∈ ∂Ω} f*_q
    
    Questa è la forma discreta dell'equazione di Poisson.

PER IMMAGINI A COLORI (dal paper):
    L'equazione viene risolta indipendentemente per ogni canale colore
    dello spazio scelto (RGB o CIE-Lab). La matrice A è la stessa per
    tutti i canali; solo il vettore b cambia per canale.
"""

import numpy as np
from scipy import sparse
import scipy.sparse.linalg

try:
    import pyamg
    HAS_PYAMG = True
except ImportError:
    HAS_PYAMG = False

from utils import (
    read_image, rgb_to_lab, lab_to_rgb,
    compute_laplacian, compute_mixed_laplacian,
    process_mask, get_pixel_ids, get_masked_values,
)


class PoissonInterpolationSolver:
    """
    Solutore dell'equazione di Poisson discreta (Section 2) per immagini a colori.

    Risolve tre equazioni di Poisson indipendenti (una per canale):
        ∆f_c = div(v_c)  over Ω,  c ∈ {R,G,B}  (o L,a,b in CIE-Lab)
        f_c|∂Ω = f*_c|∂Ω

    La matrice A del sistema lineare è condivisa tra i tre canali;
    solo il termine noto b cambia per ogni canale.
    """

    def __init__(self, source_path, target_path, mask_path,
                 solver='spsolve', color_space='RGB', mixed=False):
        """
        Inizializza il solutore caricando immagini da file.

        Args:
            source_path:  percorso immagine sorgente (guidance)
            target_path:  percorso immagine target (boundary values)
            mask_path:    percorso maschera (dominio Ω)
            solver:       'spsolve' (scipy LU) o 'multigrid' (pyamg)
            color_space:  'RGB' (default) o 'Lab' (CIE-Lab)
            mixed:       True to use mixed gradient (v_mixed) instead of simple Laplacian.
        """
        self.use_mixed = mixed
        self.color_space = color_space.upper()   

        # Carica immagini RGB [0,1] oppure usa direttamente array NumPy
        print(f"Caricamento immagini...")
        if isinstance(source_path, np.ndarray):
            source_rgb = source_path
        else:
            source_rgb = read_image(source_path)

        if isinstance(target_path, np.ndarray):
            target_rgb = target_path
        else:
            target_rgb = read_image(target_path)

        if isinstance(mask_path, np.ndarray):
            mask_gray = mask_path
        else:
            mask_gray = read_image(mask_path, gray=True)

        print(f"  Source:  {getattr(source_path, 'shape', source_rgb.shape)} {source_rgb.shape}")
        print(f"  Target:  {getattr(target_path, 'shape', target_rgb.shape)} {target_rgb.shape}")
        print(f"  Mask:    {getattr(mask_path, 'shape', mask_gray.shape)}   {mask_gray.shape}")
        print(f"  Spazio colore: {self.color_space}")

        # Converti nello spazio colore scelto
        if self.color_space == 'LAB':
            self.source = rgb_to_lab(source_rgb)   # (H, W, 3)
            self.target = rgb_to_lab(target_rgb)   # (H, W, 3)
        else:  # RGB
            self.source = source_rgb               # (H, W, 3)
            self.target = target_rgb               # (H, W, 3)

        # Threshold e process mask (sempre in grigio)
        self.mask = (mask_gray > 0.5).astype(np.float64)
        self.inner_mask, self.boundary_mask = process_mask(self.mask)

        self.img_h, self.img_w = self.mask.shape
        self.n_channels = self.source.shape[2]
        self.channel_names = (['L', 'a', 'b'] if self.color_space == 'LAB'
                               else ['R', 'G', 'B'])

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

        # Pixel mappings
        self.pixel_ids   = get_pixel_ids((self.img_h, self.img_w))
        self.inner_ids   = get_masked_values(self.pixel_ids, self.inner_mask).flatten()
        self.boundary_ids= get_masked_values(self.pixel_ids, self.boundary_mask).flatten()
        self.mask_ids    = get_masked_values(self.pixel_ids, self.mask).flatten()

        self.inner_pos    = np.searchsorted(self.mask_ids, self.inner_ids)
        self.boundary_pos = np.searchsorted(self.mask_ids, self.boundary_ids)
        self.mask_pos     = np.searchsorted(self.pixel_ids.flatten(), self.mask_ids)

        print(f"Dominio Ω: {len(self.inner_ids)} pixel (interior) "
              f"+ {len(self.boundary_ids)} pixel (boundary)")

        # Costruisci matrice A (condivisa tra tutti i canali)
        self.A = self._construct_A_matrix()

    def _construct_A_matrix(self):
        """
        Costruisce matrice A della stencil Laplaciana discreta.

        Implementa esattamente l'Eq. (7) del paper:
            |N_p| f_p - Σ_{q ∈ N_p ∩ Ω} f_q = ...

        |N_p| è il numero di vicini 4-connessi di p che sono in S
        (può essere < 4 per pixel al bordo dell'immagine — "truncated
        neighborhood" come descritto nel paper).

        La stessa matrice A viene riutilizzata per tutti i canali colore:
        solo il vettore b cambia per canale.
        """
        # Indici lineari dei 4 vicini di ogni pixel interno
        # (offset: sinistra, destra, sopra, sotto)
        neighbor_offsets = [-1, +1, -self.img_w, +self.img_w]
        # Maschere di validità: il vicino deve essere in S (dentro l'immagine)
        inner_rows = self.inner_ids // self.img_w
        inner_cols = self.inner_ids % self.img_w

        neighbor_valid = [
            inner_cols > 0,                          # sinistra: non colonna 0
            inner_cols < self.img_w - 1,             # destra:   non colonna W-1
            inner_rows > 0,                          # sopra:    non riga 0
            inner_rows < self.img_h - 1,             # sotto:    non riga H-1
        ]

        # |N_p|: numero di vicini validi in S per ogni pixel interno
        # (Eq. 7: truncated neighborhood al bordo dell'immagine)
        Np = np.zeros(len(self.inner_ids), dtype=np.int32)
        for valid in neighbor_valid:
            Np += valid.astype(np.int32)

        # Costruisci formato COO
        row_list, col_list, data_list = [], [], []

        for offset, valid in zip(neighbor_offsets, neighbor_valid):
            neighbor_ids = self.inner_ids[valid] + offset
            # Posizione del vicino nell'array mask_ids
            neighbor_pos = np.searchsorted(self.mask_ids, neighbor_ids)
            # Verifica che il vicino sia davvero in mask_ids (potrebbe essere fuori maschera)
            in_mask = (neighbor_pos < len(self.mask_ids)) & \
                      (self.mask_ids[np.clip(neighbor_pos, 0, len(self.mask_ids)-1)] == neighbor_ids)

            valid_idx = np.where(valid)[0]           # indici in inner_ids
            row_list.append(self.inner_pos[valid_idx[in_mask]])
            col_list.append(neighbor_pos[in_mask])
            data_list.append(np.ones(in_mask.sum(), dtype=np.float64))  # off-diag: +1

        # Diagonale: -|N_p|  (convenzione operatore Laplaciano A*f = ∆f)
        # L'equazione è: -|N_p|*f_p + Σ f_q = ∆source_p  →  ∆f = ∆source ✓
        row_list.append(self.inner_pos)
        col_list.append(self.inner_pos)
        data_list.append(-Np.astype(np.float64))  # diag: -|N_p|

        # Righe boundary: equazione identità f_p = f*_p
        row_list.append(self.boundary_pos)
        col_list.append(self.boundary_pos)
        data_list.append(np.ones(len(self.boundary_pos), dtype=np.float64))

        A = sparse.csr_matrix(
            (np.concatenate(data_list),
             (np.concatenate(row_list), np.concatenate(col_list))),
            shape=(len(self.mask_ids), len(self.mask_ids))
        )

        truncated = (Np < 4).sum()
        print(f"Matrice A: {A.shape}, nnz={A.nnz}  "
              f"(condivisa tra {self.n_channels} canali, "
              f"{truncated} pixel con |N_p|<4)")
        return A

    def _construct_b_vector(self, guidance_laplacian, target_boundary):
        """
        Costruisce vettore b per un singolo canale colore.

        Args:
            guidance_laplacian: Laplaciano del canale guidance (H, W)
            target_boundary:    valori target sul boundary (H, W)

        Returns:
            b: vettore dei termini noti
        """
        b = np.zeros(len(self.mask_ids))
        inner_laplacian  = get_masked_values(guidance_laplacian, self.inner_mask).flatten()
        boundary_values  = get_masked_values(target_boundary,    self.boundary_mask).flatten()

        b[self.inner_pos]    = inner_laplacian
        b[self.boundary_pos] = boundary_values
        return b

    def _solve_channel(self, source_ch, target_ch, ch_name, mixed=False):
        """
        Risolve l'equazione di Poisson per un singolo canale colore.

        Args:
            source_ch: canale sorgente (H, W) — guidance
            target_ch: canale target  (H, W) — boundary
            ch_name:   nome del canale (per log)
            mixed:     se True usa mixed gradient, altrimenti Laplaciano semplice

        Returns:
            result_ch: canale risolto (H, W), clippato in [0, 1]
        """
        if mixed:
            guidance_laplacian = compute_mixed_laplacian(source_ch, target_ch, self.inner_mask)
        else:
            guidance_laplacian = compute_laplacian(source_ch) * self.inner_mask
        b = self._construct_b_vector(guidance_laplacian, target_ch)

        if self.solver_type == 'multigrid':
            ml = pyamg.ruge_stuben_solver(self.A)
            x = ml.solve(b, tol=1e-10)
        else:
            x = self.solver_func(self.A, b)
            if isinstance(x, tuple):
                x = x[0]

        result_ch = target_ch.flatten()          # fuori dalla maschera → target
        result_ch = result_ch.copy()
        result_ch[self.mask_pos] = x
        result_ch = result_ch.reshape((self.img_h, self.img_w))
        result_ch = np.clip(result_ch, 0, 1)

        print(f"  ✓ Canale {ch_name} risolto")
        return result_ch

    def solve(self, mixed=None):
        """
        Risolve tre equazioni di Poisson indipendenti (una per canale colore).

        Come descritto nel paper (Pérez et al., SIGGRAPH 2003):
          "Three Poisson equations of the form (4) are solved independently
           in the three color channels of the chosen color space."

        Args:
            mixed: se specificato, forza la modalità mixed gradient.
                   Se None, usa self.use_mixed.

        Returns:
            result_rgb: immagine risultante in RGB [0, 1], shape (H, W, 3)
        """
        use_mixed = mixed if mixed is not None else self.use_mixed
        mode_str = "mixed gradient" if use_mixed else "import (normal)"
        print(f"\nRisoluzione Poisson per {self.n_channels} canali "
              f"({self.color_space}, {mode_str}, solver={self.solver_type})...")

        channels_out = []
        for c, name in enumerate(self.channel_names):
            ch_result = self._solve_channel(
                self.source[..., c],
                self.target[..., c],
                name,
                mixed=use_mixed
            )
            channels_out.append(ch_result)

        result = np.stack(channels_out, axis=-1)   # (H, W, 3) nello spazio scelto

        # Riporta in RGB se necessario
        if self.color_space == 'LAB':
            result = lab_to_rgb(result)

        print(f"✓ Soluzione colore completata ({mode_str})")
        return result

    def solve_both(self):
        """
        Esegue sia seamless cloning (normal) che mixed gradient in un'unica chiamata.
        La matrice A è condivisa, quindi si risparmia la costruzione.

        Returns:
            (result_normal, result_mixed): tuple di immagini RGB [0, 1]
        """
        result_normal = self.solve(mixed=False)
        result_mixed  = self.solve(mixed=True)
        return result_normal, result_mixed
