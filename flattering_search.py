import os
import itertools
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

# Importiamo il solutore direttamente dal tuo file
from texture_flattening import TextureFlatteningSolver

def run_grid_search():
    # ---- CONFIGURAZIONE PERCORSI ----
    source_path = "data/texture_flattering/test1/source.jpg"
    mask_path = "data/texture_flattering/test1/mask.png"
    output_base_dir = "results/grid_search"
    
    # ---- DEFINIZIONE DELLA GRIGLIA DI PARAMETRI ----
    sigmas = [1.0, 1.5, 2.0]
    low_thresholds = [0.02, 0.05, 0.10]
    high_thresholds = [0.12, 0.18, 0.25]
    edge_modes = ['and'] 
    
    # Creiamo la cartella base se non esiste
    os.makedirs(output_base_dir, exist_ok=True)
    
    # Genera tutte le combinazioni possibili
    combinations = list(itertools.product(sigmas, low_thresholds, high_thresholds, edge_modes))
    total_runs = len(combinations)
    print(f"Inizio Grid Search: {total_runs} combinazioni da testare.\n")
    
    for idx, (sigma, low, high, mode) in enumerate(combinations, 1):
        # Canny richiede coerentemente che high_threshold > low_threshold
        if low >= high:
            continue
            
        print(f"[{idx}/{total_runs}] Elaborazione: sigma={sigma}, low={low}, high={high}, mode={mode}")
        
        try:
            # Corretto il parametro da solver_type a solver
            solver = TextureFlatteningSolver(
                target_path=source_path,
                mask_path=mask_path,
                solver='spsolve',  # Nome parametro corretto
                color_space='RGB',
                sigma=sigma,
                low_threshold=low,
                high_threshold=high,
                edge_mode=mode
            )
            
            # Calcoliamo il risultato
            result = solver.solve()
            
            # Generiamo i nomi dei file con i parametri correnti
            prefix = f"sig{sigma}_low{low}_high{high}_{mode}"
            
            # 1. Salva l'immagine finale "appiattita"
            out_img_path = os.path.join(output_base_dir, f"{prefix}_flattened.png")
            Image.fromarray((np.clip(result, 0, 1) * 255).astype(np.uint8)).save(out_img_path)
            
            # 2. Salva la mappa dei contorni (edges)
            out_edge_path = os.path.join(output_base_dir, f"{prefix}_edges.png")
            Image.fromarray((solver.edge_mask * 255).astype(np.uint8)).save(out_edge_path)
            
            # 3. Salva la composizione a 4 pannelli (come fa la funzione main originale)
            fig, axes = plt.subplots(1, 4, figsize=(20, 5))
            axes[0].imshow(np.clip(solver.target, 0, 1))
            axes[0].set_title('Original Target')
            axes[0].axis('off')
            
            axes[1].imshow(solver.mask, cmap='gray')
            axes[1].set_title('Mask (Dominio Ω)')
            axes[1].axis('off')
            
            axes[2].imshow(solver.edge_mask, cmap='gray')
            axes[2].set_title(f'Edges (Canny, sigma={sigma})')
            axes[2].axis('off')
            
            axes[3].imshow(np.clip(result, 0, 1))
            axes[3].set_title(f'Flattened Result\n(edge_mode={mode})')
            axes[3].axis('off')
            
            plt.tight_layout()
            composite_path = os.path.join(output_base_dir, f"{prefix}_composite.png")
            plt.savefig(composite_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
        except Exception as e:
            print(f"  Errore nella combinazione sigma={sigma}, low={low}, high={high}: {e}")

    print(f"\n✓ Grid Search completata! Trovi tutti i risultati in: '{output_base_dir}'")

if __name__ == "__main__":
    run_grid_search()