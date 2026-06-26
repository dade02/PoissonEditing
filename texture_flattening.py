"""
TEXTURE FLATTENING SOLVER (Sezione 4.1)
=======================================

Implementazione dell'Appiattimento delle Texture (Texture Flattening) descritto nella
Sezione 4.1 del paper "Poisson Image Editing" (Pérez, Gangnet, Blake - SIGGRAPH 2003).

Questo algoritmo rimuove o leviga i dettagli di texture e il rumore all'interno
di una regione selezionata (Ω), mantenendo intatti solo i contorni principali.
Per fare ciò:
1. Rileva i contorni dell'immagine tramite un edge detector (Canny).
2. Costruisce una mappa binaria M (1 sui contorni, 0 altrove).
3. Costruisce un campo di guida v filtrato: v_pq = M_pq * (f*_q - f*_p).
4. Risolve l'equazione di Poisson con condizioni di Dirichlet.
"""

import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from argparse import ArgumentParser
from utils import lab_to_rgb
from solver import PoissonInterpolationSolver


try:
    from skimage.feature import canny
    from skimage.color import rgb2gray
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False


class TextureFlatteningSolver(PoissonInterpolationSolver):
    """
    Solutore per il Texture Flattening (Sezione 4.1).
    Eredita da PoissonInterpolationSolver per riutilizzare la griglia di calcolo,
    la maschera e la matrice A del sistema lineare.
    """
    def __init__(self, target_path, mask_path, solver='spsolve', color_space='RGB',
                 sigma=1.0, low_threshold=None, high_threshold=None, edge_mode='or',
                 edge_image_path=None, luminance_only=False,
                 mask_source=None, mask_target=None):
        """
        Inizializza il solutore caricando l'immagine target e la maschera.
        
        Args:
            target_path:    percorso immagine target da modificare (boundary values e contenuto)
            mask_path:      percorso maschera (dominio Ω)
            solver:         tipo di solutore lineare da usare (spsolve, multigrid, etc.)
            color_space:    spazio colore ('RGB' o 'Lab')
            sigma:          sigma per il filtro Gaussiano di Canny
            low_threshold:  soglia bassa per Canny
            high_threshold: soglia alta per Canny
            edge_mode:      'or', 'and' o 'pixel' per definire quando un arco <p,q> tocca un edge
            edge_image_path: percorso opzionale a un'immagine di edge pre-calcolata (se fornito, ignora Canny)
            luminance_only: Se True, applica flattening solo al canale L (luminance)
            mask_source:    percorso maschera sorgente opzionale
            mask_target:    percorso maschera target opzionale
        """
        if not HAS_SKIMAGE:
            raise ImportError(
                "scikit-image non è installato o non è disponibile in questo ambiente. "
                "Assicurati di usare l'ambiente virtuale corretto."
            )
        
        self.luminance_only = luminance_only
        # Se luminance_only, forza Lab ma lo useremo solo per L
        if luminance_only:
            color_space = 'Lab'
        # In texture flattening, non c'è una sorgente esterna. 
        # Passiamo target_path sia per la sorgente che per il target.
        super().__init__(
            source_path=target_path,
            target_path=target_path,
            mask_path=mask_path,
            solver=solver,
            color_space=color_space,
            mask_source=mask_source,
            mask_target=mask_target
        )
        self.sigma = sigma
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.edge_mode = edge_mode
        self.edge_image_path = edge_image_path
        
        if luminance_only:
            # Salva i canali a,b originali
            self.original_a = self.target[..., 1].copy()
            self.original_b = self.target[..., 2].copy()

        # Calcola o carica la mappa binaria degli edge M
        if edge_image_path is not None:
            print(f"Caricamento edge map da file: {edge_image_path}")
            self.edge_mask = self._load_edge_image(edge_image_path)
        else:
            print("Calcolo edge map (Canny)...")
            self.edge_mask = self._compute_edge_mask()
        
    def _get_grayscale_for_canny(self):
        """Estrae la luminanza dell'immagine in base allo spazio colore scelto."""
        if self.color_space == 'LAB':
            # Il canale L in CIE-Lab rappresenta la luminanza
            return self.target[..., 0]
        else:
            # Converte RGB in scala di grigi
            return rgb2gray(self.target)
            
    def _load_edge_image(self, path):
        """Carica una mappa di edge pre-calcolata da un file immagine."""
        edge_img = np.array(Image.open(path))
        if edge_img.ndim == 3:
            edge_img = edge_img[..., 0]  # Prende il primo canale se RGB/RGBA
        H, W = self.target.shape[:2]
        if edge_img.shape != (H, W):
            # Ridimensiona se necessario
            edge_img = np.array(Image.open(path).resize((W, H), Image.NEAREST))
            if edge_img.ndim == 3:
                edge_img = edge_img[..., 0]
        return edge_img > 0

    def _compute_edge_mask(self):
        """Rileva i contorni dell'immagine usando l'algoritmo Canny."""
        gray = self._get_grayscale_for_canny()
        edges = canny(
            gray,
            sigma=self.sigma,
            low_threshold=self.low_threshold,
            high_threshold=self.high_threshold
        )
        return edges.astype(bool)
        
    def _solve_channel(self, target_ch, ch_name):
        """
        Risolve l'equazione di Poisson per il texture flattening su un singolo canale.
        """
        H, W = target_ch.shape
        M = self.edge_mask
        
        # Valori dei vicini (left, right, up, down) con padding per i bordi
        val_left = np.zeros_like(target_ch)
        val_left[:, 1:] = target_ch[:, :-1]
        val_left[:, 0] = target_ch[:, 0]
        
        val_right = np.zeros_like(target_ch)
        val_right[:, :-1] = target_ch[:, 1:]
        val_right[:, -1] = target_ch[:, -1]
        
        val_up = np.zeros_like(target_ch)
        val_up[1:, :] = target_ch[:-1, :]
        val_up[0, :] = target_ch[0, :]
        
        val_down = np.zeros_like(target_ch)
        val_down[:-1, :] = target_ch[1:, :]
        val_down[-1, :] = target_ch[-1, :]
        
        # M_left, M_right, M_up, M_down (maschere edge per i vicini)
        M_left = np.zeros_like(M, dtype=bool)
        M_left[:, 1:] = M[:, :-1]
        
        M_right = np.zeros_like(M, dtype=bool)
        M_right[:, :-1] = M[:, 1:]
        
        M_up = np.zeros_like(M, dtype=bool)
        M_up[1:, :] = M[:-1, :]
        
        M_down = np.zeros_like(M, dtype=bool)
        M_down[:-1, :] = M[1:, :]
        
        # Definisce M_pq (se c'è un edge tra p e q)
        if self.edge_mode == 'or':
            edge_left = M | M_left
            edge_right = M | M_right
            edge_up = M | M_up
            edge_down = M | M_down
        elif self.edge_mode == 'and':
            edge_left = M & M_left
            edge_right = M & M_right
            edge_up = M & M_up
            edge_down = M & M_down
        else: # 'pixel'
            edge_left = M
            edge_right = M
            edge_up = M
            edge_down = M
            
        # Coordinate di validità (truncated neighborhood per i pixel sul bordo dell'immagine)
        Y, X = np.ogrid[:H, :W]
        valid_left = X > 0
        valid_right = X < W - 1
        valid_up = Y > 0
        valid_down = Y < H - 1
        
        # Calcola divergenza del campo di guida filtrato: v_pq = M_pq * (f*_q - f*_p)
        # e sommiamo su q in N_p: div_v = sum_{q in N_p} M_pq * (f*_q - f*_p)
        div_v = (
            valid_left.astype(float) * edge_left.astype(float) * (val_left - target_ch) +
            valid_right.astype(float) * edge_right.astype(float) * (val_right - target_ch) +
            valid_up.astype(float) * edge_up.astype(float) * (val_up - target_ch) +
            valid_down.astype(float) * edge_down.astype(float) * (val_down - target_ch)
        )
        
        # Filtra solo per la regione interna (inner_mask)
        div_v = div_v * self.inner_mask
        
        # Costruisci il vettore b
        b = self._construct_b_vector(div_v, target_ch)
        
        # Risolve il sistema lineare Ax = b
        if self.solver_type == 'multigrid':
            import pyamg
            ml = pyamg.ruge_stuben_solver(self.A)
            x = ml.solve(b, tol=1e-10)
        else:
            x = self.solver_func(self.A, b)
            if isinstance(x, tuple):
                x = x[0]
                
        # Ricostruisci il canale su tutta l'immagine
        result_ch = target_ch.flatten()
        result_ch = result_ch.copy()
        result_ch[self.mask_pos] = x
        result_ch = result_ch.reshape((self.img_h, self.img_w))
        result_ch = np.clip(result_ch, 0, 1)
        
        print(f"  ✓ Canale {ch_name} appiattito")
        return result_ch
        
    def solve(self):
        if self.luminance_only:
            # Risolve SOLO il canale L
            result_L = self._solve_channel(self.target[..., 0], 'Luminance')
            
            # Ricostruisce Lab
            result_lab = self.target.copy()
            result_lab[..., 0] = result_L
            result_lab[..., 1] = self.original_a
            result_lab[..., 2] = self.original_b
            
            result = lab_to_rgb(result_lab)
            print("✓ Texture Flattening su LUMINANCE completato!")
            return result
        else:
            """
            Esegue il texture flattening su tutti i canali colore dell'immagine.
            """
            print(f"\nEsecuzione Texture Flattening per {self.n_channels} canali "
                f"({self.color_space}, sigma={self.sigma}, edge_mode={self.edge_mode}, solver={self.solver_type})...")
                
            channels_out = []
            for c, name in enumerate(self.channel_names):
                ch_result = self._solve_channel(
                    self.target[..., c],
                    name
                )
                channels_out.append(ch_result)
                
            result = np.stack(channels_out, axis=-1)
            
            # Converte LAB in RGB se necessario
            if self.color_space == 'LAB':
                
                result = lab_to_rgb(result)
                
            print("✓ Texture Flattening completato!")
            return result


def main():
    """Interfaccia a riga di comando autonoma per il Texture Flattening."""
    parser = ArgumentParser(description='Texture Flattening (Sezione 4.1)')
    parser.add_argument('target', help='Percorso immagine target da appiattire')
    parser.add_argument('mask', help='Percorso maschera (dominio Ω)')
    parser.add_argument('--solver', default='spsolve',
                        choices=['spsolve', 'gmres', 'lgmres', 'multigrid'],
                        help='Solver da usare')
    parser.add_argument('--colorspace', default='RGB',
                        choices=['RGB', 'Lab'],
                        help='Spazio colore: RGB (default) o CIE-Lab')
    parser.add_argument('--sigma', type=float, default=1.5,
                        help='Sigma per Canny edge detector (default: 1.5)')
    parser.add_argument('--low-threshold', type=float, default=None,
                        help='Soglia bassa Canny (default: None, automatica)')
    parser.add_argument('--high-threshold', type=float, default=None,
                        help='Soglia alta Canny (default: None, automatica)')
    parser.add_argument('--edge-mode', default='or',
                        choices=['or', 'and', 'pixel'],
                        help='Come considerare gli edge tra pixel vicini (default: or)')
    parser.add_argument('--edge-image', default=None,
                        help='Percorso a un\'immagine di edge pre-calcolata (se fornito, ignora Canny)')
    parser.add_argument('--luminance_only', action='store_true',
                    help='Applica flattening solo sulla luminance (canale L)')
    parser.add_argument('--output', default='flattening_result.png',
                        help='File output (immagine composita)')
                        
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("TEXTURE FLATTENING (SEZIONE 4.1)")
    print("="*70)
    
    solver = TextureFlatteningSolver(
        args.target, args.mask,
        solver=args.solver,
        color_space=args.colorspace,
        sigma=args.sigma,
        low_threshold=args.low_threshold,
        high_threshold=args.high_threshold,
        edge_mode=args.edge_mode,
        edge_image_path=args.edge_image
    )
    
    result = solver.solve()
    
    # Prepara immagini per la visualizzazione
    tgt_vis = solver.target if solver.color_space == 'RGB' else lab_to_rgb(solver.target)
    
    # Salva risultati individuali
    base_name, ext = os.path.splitext(args.output)
    Image.fromarray((np.clip(tgt_vis, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_target{ext}")
    Image.fromarray((solver.mask * 255).astype(np.uint8)).save(f"{base_name}_mask{ext}")
    Image.fromarray((solver.edge_mask * 255).astype(np.uint8)).save(f"{base_name}_edges{ext}")
    Image.fromarray((np.clip(result, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_flattened{ext}")
    
    # Visualizza e salva l'immagine composita a 4 pannelli
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    
    axes[0].imshow(np.clip(tgt_vis, 0, 1))
    axes[0].set_title('Original Target')
    axes[0].axis('off')
    
    axes[1].imshow(solver.mask, cmap='gray')
    axes[1].set_title('Mask (Dominio Ω)')
    axes[1].axis('off')
    
    axes[2].imshow(solver.edge_mask, cmap='gray')
    axes[2].set_title(f'Edges (Canny, sigma={args.sigma})')
    axes[2].axis('off')
    
    axes[3].imshow(np.clip(result, 0, 1))
    axes[3].set_title(f'Flattened Result\n({solver.color_space}, edge_mode={args.edge_mode})')
    axes[3].axis('off')
    
    plt.tight_layout()
    plt.savefig(args.output, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n✓ Immagine composita salvata: {args.output}")
    print(f"✓ Immagini singole salvate: {base_name}_{{target,mask,edges,flattened}}{ext}")


if __name__ == '__main__':
    main()