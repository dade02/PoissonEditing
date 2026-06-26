"""
LOCAL ILLUMINATION CHANGE
=========================

Implementation of Local Illumination Changes as described in Section 4 of:

    Pérez, Gangnet, Blake – "Poisson Image Editing" (SIGGRAPH 2003)

The idea, adapted from Fattal et al. (2002), operates in the log domain.
The gradient field of each color channel is rescaled non-linearly to
compress large illumination variations while boosting fine details.

Key formula (Eq. 16 of the paper):

    v = α^β · |∇f*|^{-β} · ∇f*

where:
  - f*  is the log of the image (applied per channel)
  - α   = alpha_factor × average(|∇f*|) computed over the domain Ω
  - β   controls the compression (paper default: 0.2)

As per the paper's general framework: "three Poisson equations of the
form (4) are solved independently in the three color channels."

Each channel is processed independently in the log domain:
    Δf_c = div(v_c)   on Ω,    f_c|∂Ω = f*_c|∂Ω

This allows different channels to be affected differently by the
non-linear gradient transformation (e.g., the blue channel at a
specular highlight has much larger gradients than red/green, so it
gets compressed more aggressively).
"""

import numpy as np

from solver import PoissonInterpolationSolver
from utils import read_image


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def rgb2gray(img: np.ndarray) -> np.ndarray:
    """Convert an RGB image (H,W,3) to grayscale (H,W)
    using ITU-R BT.601 luminance coefficients."""
    if img.ndim == 2:
        return img
    return np.dot(img[..., :3], [0.2989, 0.5870, 0.1140])


# ---------------------------------------------------------------------------
# Guidance field computation (Eq. 16) and its divergence
# ---------------------------------------------------------------------------

def compute_guidance_divergence(log_ch: np.ndarray,
                                mask: np.ndarray,
                                beta: float = 0.2,
                                alpha_factor: float = 0.2) -> np.ndarray:
    """Compute div(v) where v is defined by Eq. 16 of the paper.

    Steps:
    1. Compute forward-difference gradients of the log-channel.
    2. Compute gradient magnitude.
    3. Estimate α = alpha_factor × mean(|∇f*|) over Ω  (Eq. 16).
    4. Apply non-linear rescaling:  v = α^β · |∇f*|^{-β} · ∇f*
    5. Compute divergence of v via backward differences (consistent
       with the discrete Laplacian stencil used by the solver).

    Parameters
    ----------
    log_ch       : (H, W)  log of the image channel
    mask         : (H, W)  binary mask (1 = inside Ω)
    beta         : float   exponent β  (Eq. 16, paper default: 0.2)
    alpha_factor : float   multiplicative factor for α (paper default: 0.2)

    Returns
    -------
    div_v : (H, W)  divergence of the guidance field
    """
    eps = 1e-10

    # --- 1. Forward-difference gradients ---
    # gx = ∂f*/∂x  (horizontal),  gy = ∂f*/∂y  (vertical)
    gx = np.zeros_like(log_ch)
    gy = np.zeros_like(log_ch)
    gx[:, :-1] = log_ch[:, 1:] - log_ch[:, :-1]
    gy[:-1, :] = log_ch[1:, :] - log_ch[:-1, :]

    # --- 2. Gradient magnitude ---
    mag = np.sqrt(gx**2 + gy**2)

    # --- 3. Estimate α  (Eq. 16) ---
    # α = alpha_factor × average gradient magnitude inside Ω
    valid = (mask > 0) & (mag > eps)
    if np.any(valid):
        alpha = alpha_factor * np.mean(mag[valid])
    else:
        alpha = 1.0  # fallback, no rescaling

    # --- 4. Non-linear rescaling  (Eq. 16) ---
    #   v = α^β · |∇f*|^{-β} · ∇f*
    #
    # Equivalent to:  scale = (α / |∇f*|)^β,  v = scale · ∇f*
    #
    # Gradients larger than α are compressed (scale < 1).
    # Gradients smaller than α are boosted (scale > 1).
    # We cap the scale to avoid extreme amplification of noise.
    scale = (alpha / (mag + eps)) ** beta
    max_scale = 1.0 / (alpha**beta + eps)  # reasonable ceiling
    scale = np.minimum(scale, max_scale)

    vx = scale * gx
    vy = scale * gy

    # --- 5. Divergence via backward differences ---
    # div(v) = ∂vx/∂x + ∂vy/∂y
    # Using backward differences to be consistent with the forward-difference
    # gradients and the 5-point Laplacian stencil of the solver.
    div_v = np.zeros_like(log_ch)

    # ∂vx/∂x  (backward difference)
    div_v[:, 0]   = vx[:, 0]
    div_v[:, 1:]  = vx[:, 1:] - vx[:, :-1]

    # ∂vy/∂y  (backward difference)
    div_v[0, :]  += vy[0, :]
    div_v[1:, :] += vy[1:, :] - vy[:-1, :]

    return div_v


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class LocalIlluminationChangeSolver(PoissonInterpolationSolver):
    """Solver for Local Illumination Change (Section 4 of the paper).

    Extends PoissonInterpolationSolver: reuses the sparse matrix A and
    the linear solver, but overrides the right-hand side vector b with
    the divergence of the non-linearly rescaled guidance field.

    As per the paper, three independent Poisson equations are solved,
    one per color channel, each in the log domain.
    """

    def __init__(self, source_path, mask_path,
                 solver='spsolve', grayscale=False,
                 mode='luminance', sigma=0.0, beta=0.2,
                 alpha_factor=0.2, mask_source=None, mask_target=None):
        """
        Parameters
        ----------
        source_path  : str   path to the source image
        mask_path    : str   path to the binary mask (domain Ω)
        solver       : str   solver type ('spsolve', 'gmres', …)
        grayscale    : bool  if True, output is grayscale
        mode         : str   'per_channel' (default, Eq. 16 per RGB channel)
                             or 'luminance' (single luminance + ratio)
        sigma        : float (unused, kept for CLI compatibility)
        beta         : float exponent β (Eq. 16, paper default: 0.2)
        alpha_factor : float multiplicative factor for α (Eq. 16)
        """
        # Load images
        self.original_rgb = read_image(source_path)
        mask_raw = read_image(mask_path, gray=True)
        self.mask = (mask_raw > 0.5).astype(np.float64)

        self.grayscale = grayscale
        self.mode = mode
        self.sigma = sigma
        self.beta = beta
        self.alpha_factor = alpha_factor

        # The base solver expects source == target (same image):
        # the actual guidance comes from the non-linear field v,
        # not from the Laplacian of the source.
        if grayscale:
            lum = rgb2gray(self.original_rgb)
            guidance = np.stack([lum, lum, lum], axis=-1)
        else:
            guidance = self.original_rgb.copy()

        super().__init__(guidance, guidance, self.mask,
                         solver=solver, color_space='RGB',
                         mask_source=mask_source, mask_target=mask_target)

    # ------------------------------------------------------------------

    def _solve_log_channel(self, channel: np.ndarray) -> np.ndarray:
        """Solve Δf = div(v) in the log domain for a single channel.

        Parameters
        ----------
        channel : (H, W)  image channel [0, 1]

        Returns
        -------
        result : (H, W)  reconstructed channel [0, 1]
        """
        # Transform to log domain
        log_ch = np.log(channel + 1e-10)

        # Compute div(v) from Eq. 16
        div_v = compute_guidance_divergence(
            log_ch, self.inner_mask,
            beta=self.beta,
            alpha_factor=self.alpha_factor,
        )

        # Build b vector: interior → div(v), boundary → original log values
        b = self._construct_b_vector(div_v * self.inner_mask, log_ch)

        # Solve the linear system A x = b
        if self.solver_type == 'multigrid':
            import pyamg
            ml = pyamg.ruge_stuben_solver(self.A)
            x = ml.solve(b, tol=1e-10)
        else:
            x = self.solver_func(self.A, b)
            if isinstance(x, tuple):
                x = x[0]

        # Reconstruct image in log domain
        log_result = log_ch.flatten().copy()
        log_result[self.mask_pos] = x
        log_result = log_result.reshape(self.img_h, self.img_w)

        # Back to linear domain
        return np.clip(np.exp(log_result), 0, 1)

    # ------------------------------------------------------------------

    def solve(self, mixed=False) -> np.ndarray:
        """Perform the local illumination change.

        Applies Eq. 16 independently to each color channel in the log
        domain, as prescribed by the paper's general framework.

        Returns
        -------
        result : (H, W, 3)  resulting RGB image [0, 1]
        """
        print(f"\nLocal Illumination Change "
              f"(per-channel log, solver={self.solver_type}, "
              f"β={self.beta}, α_factor={self.alpha_factor})...")

        if self.grayscale:
            lum = rgb2gray(self.original_rgb)
            solved = self._solve_log_channel(lum)
            result = np.stack([solved, solved, solved], axis=-1)
        else:
            # Solve each RGB channel independently in the log domain
            channels = []
            for c, name in enumerate(['R', 'G', 'B']):
                ch = self.original_rgb[..., c]
                solved_ch = self._solve_log_channel(ch)
                channels.append(solved_ch)
                print(f"  ✓ Channel {name} solved")
            result = np.stack(channels, axis=-1)

        print("✓ Local Illumination Change completed!")
        return result