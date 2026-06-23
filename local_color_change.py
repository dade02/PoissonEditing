import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.colors import rgb_to_hsv, hsv_to_rgb
from argparse import ArgumentParser

from solver import PoissonInterpolationSolver
from utils import read_image


def rgb2gray(img):
    """Converte RGB in scala di grigi usando la luminanza standard."""
    if img.ndim == 2:
        return img
    return np.dot(img[..., :3], [0.2989, 0.5870, 0.1140])


def build_gray_rgb(img_rgb):
    """Costruisce un'immagine RGB grigia a partire da un'immagine RGB."""
    gray = rgb2gray(img_rgb)
    return np.stack([gray, gray, gray], axis=-1)


def apply_hue_shift(img_rgb, hue_delta_degrees):
    """Sposta la tonalità di un'immagine RGB mantenendo saturazione e luminosità."""
    hsv = rgb_to_hsv(img_rgb)
    hue_delta = (hue_delta_degrees % 360.0) / 360.0
    hsv[..., 0] = (hsv[..., 0] + hue_delta) % 1.0
    return np.clip(hsv_to_rgb(hsv), 0, 1)


def apply_rgb_multiply(img_rgb, factors):
    """Moltiplica i canali RGB per fattori specifici.
    
    Args:
        img_rgb: immagine RGB [0, 1]
        factors: tuple/list di 3 fattori (r, g, b) oppure singolo fattore per tutti i canali
    
    Returns:
        immagine RGB modificata, clippata in [0, 1]
    """
    result = img_rgb.copy()
    if isinstance(factors, (int, float)):
        # Singolo fattore per tutti i canali
        result *= factors
    else:
        # Fattori specifici per canale
        for c, factor in enumerate(factors):
            result[..., c] *= factor
    return np.clip(result, 0, 1)


def apply_brightness_contrast(img_rgb, brightness=0.0, contrast=1.0):
    """Applica brightness e contrast a un'immagine RGB.
    
    Args:
        img_rgb: immagine RGB [0, 1]
        brightness: valore da aggiungere (-1 to 1)
        contrast: fattore di moltiplicazione (0.5 to 2.0)
    
    Returns:
        immagine RGB modificata, clippata in [0, 1]
    """
    result = img_rgb.copy()
    # Applica contrast attorno al punto medio (0.5)
    result = (result - 0.5) * contrast + 0.5
    # Applica brightness
    result += brightness
    return np.clip(result, 0, 1)


class LocalColorChangeSolver(PoissonInterpolationSolver):
    """Solutore per Local Color Change usando Poisson image editing."""

    def __init__(self, source_path, mask_path,
                 solver='spsolve', mode='color_change', change_hue=60.0,
                 rgb_factors=None, brightness=0.0, contrast=1.0):
        self.original_rgb = read_image(source_path)
        self.mask = read_image(mask_path, gray=True)
        self.mask = (self.mask > 0.5).astype(np.float64)

        self.mode = mode
        self.change_hue = change_hue
        self.rgb_factors = rgb_factors
        self.brightness = brightness
        self.contrast = contrast

        if self.mode == 'gray_background':
            guidance_rgb = self.original_rgb
            target_rgb = build_gray_rgb(self.original_rgb)
        elif self.mode == 'color_change':
            guidance_rgb = apply_hue_shift(self.original_rgb, self.change_hue)
            target_rgb = self.original_rgb
        elif self.mode == 'multiply_rgb':
            if rgb_factors is None:
                raise ValueError("multiply_rgb mode richiede rgb_factors")
            guidance_rgb = apply_rgb_multiply(self.original_rgb, rgb_factors)
            target_rgb = self.original_rgb
        elif self.mode == 'brightness_contrast':
            guidance_rgb = apply_brightness_contrast(self.original_rgb, brightness, contrast)
            target_rgb = self.original_rgb
        else:
            raise ValueError("Modalità non valida. Usa 'color_change', 'gray_background', "
                           "'multiply_rgb' o 'brightness_contrast'.")

        super().__init__(guidance_rgb, target_rgb, self.mask,
                         solver=solver, color_space='RGB')

    def solve(self):
        print(f"\nEsecuzione Local Color Change (mode={self.mode}, solver={self.solver_type})...")
        result = super().solve(mixed=False)
        result = np.clip(result, 0, 1)
        print("✓ Local Color Change completato!")
        return result


def main():
    parser = ArgumentParser(description='Local Color Change')
    parser.add_argument('source', help='Percorso immagine sorgente da modificare')
    parser.add_argument('mask', help='Percorso maschera (dominio Ω)')
    parser.add_argument('--solver', default='spsolve',
                        choices=['spsolve', 'gmres', 'lgmres', 'bicg', 'bicgstab', 'cgs', 'minres', 'multigrid'],
                        help='Solver da usare')
    parser.add_argument('--mode', default='color_change',
                        choices=['color_change', 'gray_background', 'multiply_rgb', 'brightness_contrast'],
                        help='Modalità di modifica colore')
    parser.add_argument('--change-hue', type=float, default=60.0,
                        help='Valore in gradi da aggiungere al canale hue in modalità color_change')
    parser.add_argument('--rgb-factors', type=float, nargs=3, default=None,
                        help='Fattori di moltiplicazione per R, G, B in modalità multiply_rgb (es: 1.5 0.5 0.5)')
    parser.add_argument('--brightness', type=float, default=0.0,
                        help='Valore brightness (-1 a 1) in modalità brightness_contrast')
    parser.add_argument('--contrast', type=float, default=1.0,
                        help='Fattore contrast (0.5 a 2.0) in modalità brightness_contrast')
    parser.add_argument('--output', default='local_color_change.png',
                        help='File output (immagine risultante)')

    args = parser.parse_args()

    solver = LocalColorChangeSolver(
        args.source,
        args.mask,
        solver=args.solver,
        mode=args.mode,
        change_hue=args.change_hue,
        rgb_factors=args.rgb_factors,
        brightness=args.brightness,
        contrast=args.contrast,
    )
    result = solver.solve()

    base_name, ext = os.path.splitext(args.output)
    if ext == '':
        ext = '.png'

    Image.fromarray((np.clip(solver.original_rgb, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_input{ext}")
    Image.fromarray((solver.mask * 255).astype(np.uint8)).save(f"{base_name}_mask{ext}")
    Image.fromarray((np.clip(result, 0, 1) * 255).astype(np.uint8)).save(args.output)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(np.clip(solver.original_rgb, 0, 1))
    axes[0].set_title('Originale')
    axes[0].axis('off')

    axes[1].imshow(solver.mask, cmap='gray')
    axes[1].set_title('Mask (Ω)')
    axes[1].axis('off')

    axes[2].imshow(np.clip(result, 0, 1))
    axes[2].set_title('Local Color Change')
    axes[2].axis('off')

    plt.tight_layout()
    plt.savefig(f"{base_name}_composite{ext}", dpi=150, bbox_inches='tight')
    plt.close(fig)

    print(f"\n✓ Immagine risultante salvata: {args.output}")
    print(f"✓ Immagini ausiliarie salvate: {base_name}_input{ext}, {base_name}_mask{ext}, {base_name}_composite{ext}")


if __name__ == '__main__':
    main()
