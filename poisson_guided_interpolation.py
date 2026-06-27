import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from argparse import ArgumentParser

from utils import lab_to_rgb, build_gray_rgb
from solver import PoissonInterpolationSolver
from texture_flattening import TextureFlatteningSolver
from local_illumination_change import LocalIlluminationChangeSolver
from local_color_change import LocalColorChangeSolver
from poisson_seamless_tiling import PoissonSeamlessTiling, tile_image


def main():
    """
    Risolve Poisson equation su immagini reali a colori in una delle tre modalità:
    - seamless_cloning
    - mixed_gradient
    - texture_flattening

    Uso per Cloning / Mixed:
        python poisson_guided_interpolation.py <source> <target> <mask> --mode [seamless_cloning|mixed_gradient] [opzioni]

    Uso per Flattening:
        python poisson_guided_interpolation.py <target> <mask> --mode texture_flattening [opzioni]
    """
    parser = ArgumentParser(description='Poisson Guided Interpolation (Color) - Seamless Editing Suite')
    parser.add_argument('source', help='Percorso immagine sorgente (cloning) o immagine da modificare (flattening, tiling)')
    parser.add_argument('target', nargs='?', default=None, help='Percorso immagine target (cloning) o maschera (flattening)')
    parser.add_argument('mask',   nargs='?', default=None, help='Percorso maschera (cloning) - opzionale per flattening')
    
    parser.add_argument('--mode', default='seamless_cloning',
                        choices=[
                            'seamless_cloning', 'cloning',
                            'mixed_gradient', 'mixed',
                            'texture_flattening', 'texture_flattering', 'flatten',
                            'local_illumination_change', 'illumination_change', 'illum',
                            'local_color_change', 'color_change', 'color',
                            'seamless_tiling', 'tiling'
                        ],
                        help='Modalità: seamless_cloning (default), mixed_gradient, texture_flattening, local_illumination_change, local_color_change, o seamless_tiling')
    parser.add_argument('--grayscale', action='store_true',
                        help='Esegue la local illumination change in scala di grigi (solo per local_illumination_change)')
    parser.add_argument('--solver', default='spsolve',
                        choices=['spsolve', 'gmres', 'lgmres', 'multigrid'],
                        help='Solver da usare')
    parser.add_argument('--colorspace', default='RGB',
                        choices=['RGB', 'Lab'],
                        help='Spazio colore: RGB (default) o CIE-Lab')
    parser.add_argument('--sigma', type=float, default=1.0,
                        help='Sigma per Canny edge detector o smoothing Fattal (default: 1.0)')
    parser.add_argument('--low-threshold', type=float, default=None,
                        help='Soglia bassa Canny (usato solo in modalità texture_flattening)')
    parser.add_argument('--high-threshold', type=float, default=None,
                        help='Soglia alta Canny (usato solo in modalità texture_flattening)')
    parser.add_argument('--edge-mode', default='or',
                        choices=['or', 'and', 'pixel'],
                        help='Come considerare gli edge tra pixel vicini (usato solo in modalità texture_flattening)')
    parser.add_argument('--edge-image', default=None,
                        help='Percorso a un\'immagine di edge pre-calcolata (usato solo in modalità texture_flattening)')
    parser.add_argument('--illum-mode', default='luminance',
                        choices=['luminance'],
                        help='Modalità per local_illumination_change (default: luminance)')
    parser.add_argument('--alpha-factor', type=float, default=0.1,
                        help='Fattore di moltiplicazione per alpha in Fattal et al. (default: 0.2)')
    parser.add_argument('--beta', type=float, default=0.2,
                        help='Esponente beta della trasformazione di Fattal (default: 0.5 per effetti più marcati)')
    parser.add_argument('--rgb-factors', type=float, nargs=3, default=(1.5, 0.5, 0.5),
                    help='Fattori di moltiplicazione per R, G, B (solo per multiply_rgb mode, default: 1.5 0.5 0.5)')
    parser.add_argument('--color-mode', default='gray_background',
                    choices=['gray_background', 'multiply_rgb', 'color_change'],
                    help='Modalità di modifica colore (solo per local_color_change)')
    parser.add_argument('--change-hue', type=float, default=60.0,
                    help='Valore in gradi da aggiungere al canale hue (solo per color_change mode, default: 60)')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Fattore di scala immagine (solo per seamless_tiling)')
    parser.add_argument('--luminance_only', action='store_true',
                        help='lavora su luminanza nel flattening')
    parser.add_argument('--mask-source', default=None,
                        help='Percorso maschera sorgente (opzionale per allineamento)')
    parser.add_argument('--mask-target', default=None,
                        help='Percorso maschera target (opzionale per allineamento)')
    parser.add_argument('--monochrome-transfer', action='store_true',
                        help='Applica monochrome transfer: rende la source in scala di grigi (solo per seamless_cloning/mixed_gradient)')
    parser.add_argument('--output', default='poisson_result.png',
                        help='File output (immagine composita)')

    args = parser.parse_args()

    # Mappatura dei sinonimi per la modalità
    mode = args.mode
    if mode in ['cloning', 'seamless_cloning']:
        exec_mode = 'seamless_cloning'
    elif mode in ['mixed', 'mixed_gradient']:
        exec_mode = 'mixed_gradient'
    elif mode in ['local_illumination_change', 'illumination_change', 'illum']:
        exec_mode = 'local_illumination_change'
    elif mode in ['local_color_change', 'color_change', 'color']:
        exec_mode = 'local_color_change'
    elif mode in ['seamless_tiling', 'tiling']:
        exec_mode = 'seamless_tiling'
    else:  # flatten, texture_flattening, texture_flattering
        exec_mode = 'texture_flattening'

    # Validazione argomenti per modalità
    if exec_mode in ['seamless_cloning', 'mixed_gradient']:
        if args.mask_source is not None and args.mask_target is not None:
            if args.mask is None:
                args.mask = args.mask_target
        if args.mask is None or args.target is None:
            parser.error(f"La modalità '{args.mode}' richiede 3 argomenti posizionali: <source> <target> <mask_image>.")
        source_path = args.source
        target_path = args.target
        mask_path = args.mask
    elif exec_mode == 'texture_flattening':
        if args.mask_source is not None and args.mask_target is not None:
            if args.mask is None:
                args.mask = args.mask_target
        if args.mask is None and args.target is None:
            parser.error(f"La modalità '{args.mode}' richiede almeno 2 argomenti: <target> <mask_image>.")
        if args.mask is None:
            # Sviluppo comodo a 2 argomenti: target mask
            target_path = args.source
            mask_path = args.target
        else:
            # Caso 3 argomenti (es. per script automatici, ignorando la prima immagine come source)
            target_path = args.target
            mask_path = args.mask
    elif exec_mode in ['local_illumination_change', 'local_color_change']:
        if args.mask_source is not None and args.mask_target is not None:
            if args.mask is None:
                args.mask = args.mask_target
        if args.mask is None and args.target is None:
            parser.error(f"La modalità '{args.mode}' richiede almeno 2 argomenti: <source> <mask_image>.")
        if args.mask is None:
            source_path = args.source
            mask_path = args.target
        else:
            source_path = args.source
            mask_path = args.mask
    elif exec_mode == 'seamless_tiling':
        source_path = args.source

    # Assicura che la directory di output esista
    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print("\n" + "="*70)
    if exec_mode == 'seamless_cloning':
        print("POISSON GUIDED INTERPOLATION - SEAMLESS CLONING")
    elif exec_mode == 'mixed_gradient':
        print("POISSON GUIDED INTERPOLATION - MIXED GRADIENT CLONING")
    elif exec_mode == 'texture_flattening':
        print("POISSON IMAGE EDITING - TEXTURE FLATTENING")
    elif exec_mode == 'local_illumination_change':
        print("POISSON IMAGE EDITING - LOCAL ILLUMINATION CHANGE")
    elif exec_mode == 'local_color_change':
        print("POISSON IMAGE EDITING - LOCAL COLOR CHANGE")
    elif exec_mode == 'seamless_tiling':
        print("POISSON IMAGE EDITING - SEAMLESS TILING")
    print("="*70)

    # Inizializza ed esegue in base alla modalità selezionata
    if exec_mode == 'seamless_cloning':
        solver = PoissonInterpolationSolver(
            source_path, target_path, mask_path,
            solver=args.solver,
            color_space=args.colorspace,
            mixed=False,
            mask_source=args.mask_source,
            mask_target=args.mask_target
        )
        
        # Applica monochrome transfer se richiesto
        if args.monochrome_transfer:
            solver.source = build_gray_rgb(solver.source)
        
        result = solver.solve(mixed=False)

        src_vis = solver.source if solver.color_space == 'RGB' else lab_to_rgb(solver.source)
        tgt_vis = solver.target if solver.color_space == 'RGB' else lab_to_rgb(solver.target)

        # Salva le immagini singole
        base_name, ext = os.path.splitext(args.output)
        Image.fromarray((np.clip(src_vis, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_source{ext}")
        Image.fromarray((np.clip(tgt_vis, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_target{ext}")
        Image.fromarray((solver.mask * 255).astype(np.uint8)).save(f"{base_name}_mask{ext}")
        Image.fromarray((np.clip(result, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_cloning{ext}")

        # Visualizza e salva l'immagine composita con 4 pannelli
        fig, axes = plt.subplots(1, 4, figsize=(20, 5))

        axes[0].imshow(np.clip(src_vis, 0, 1))
        axes[0].set_title('Source\n(Guidance Field)')
        axes[0].axis('off')

        axes[1].imshow(np.clip(tgt_vis, 0, 1))
        axes[1].set_title('Target\n(Boundary Values)')
        axes[1].axis('off')

        axes[2].imshow(solver.mask, cmap='gray')
        axes[2].set_title('Mask\n(Dominio Ω)')
        axes[2].axis('off')

        axes[3].imshow(np.clip(result, 0, 1))
        axes[3].set_title(f'Seamless Cloning\n({solver.color_space})')
        axes[3].axis('off')

        plt.tight_layout()
        plt.savefig(args.output, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"\n✓ Immagine composita salvata: {args.output}")
        print(f"✓ Immagini singole: {base_name}_{{source,target,mask,cloning}}{ext}")

    elif exec_mode == 'mixed_gradient':
        solver = PoissonInterpolationSolver(
            source_path, target_path, mask_path,
            solver=args.solver,
            color_space=args.colorspace,
            mixed=True,
            mask_source=args.mask_source,
            mask_target=args.mask_target
        )
        
        # Applica monochrome transfer se richiesto
        if args.monochrome_transfer:
            solver.source = build_gray_rgb(solver.source)
        
        result = solver.solve(mixed=True)

        src_vis = solver.source if solver.color_space == 'RGB' else lab_to_rgb(solver.source)
        tgt_vis = solver.target if solver.color_space == 'RGB' else lab_to_rgb(solver.target)

        # Salva le immagini singole
        base_name, ext = os.path.splitext(args.output)
        Image.fromarray((np.clip(src_vis, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_source{ext}")
        Image.fromarray((np.clip(tgt_vis, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_target{ext}")
        Image.fromarray((solver.mask * 255).astype(np.uint8)).save(f"{base_name}_mask{ext}")
        Image.fromarray((np.clip(result, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_mixed{ext}")

        # Visualizza e salva l'immagine composita con 4 pannelli
        fig, axes = plt.subplots(1, 4, figsize=(20, 5))

        axes[0].imshow(np.clip(src_vis, 0, 1))
        axes[0].set_title('Source\n(Guidance Field)')
        axes[0].axis('off')

        axes[1].imshow(np.clip(tgt_vis, 0, 1))
        axes[1].set_title('Target\n(Boundary Values)')
        axes[1].axis('off')

        axes[2].imshow(solver.mask, cmap='gray')
        axes[2].set_title('Mask\n(Dominio Ω)')
        axes[2].axis('off')

        axes[3].imshow(np.clip(result, 0, 1))
        axes[3].set_title(f'Seamless Cloning\n(Mixed Gradient)')
        axes[3].axis('off')

        plt.tight_layout()
        plt.savefig(args.output, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"\n✓ Immagine composita salvata: {args.output}")
        print(f"✓ Immagini singole: {base_name}_{{source,target,mask,mixed}}{ext}")

    elif exec_mode == 'texture_flattening':
    
        solver = TextureFlatteningSolver(
            target_path, mask_path,
            solver=args.solver,
            color_space=args.colorspace,
            sigma=args.sigma,
            low_threshold=args.low_threshold,
            high_threshold=args.high_threshold,
            edge_mode=args.edge_mode,
            edge_image_path=args.edge_image,
            luminance_only=args.luminance_only,
            mask_source=args.mask_source,
            mask_target=args.mask_target
        )
        result = solver.solve()

        tgt_vis = solver.target if solver.color_space == 'RGB' else lab_to_rgb(solver.target)

        # Salva le immagini singole
        base_name, ext = os.path.splitext(args.output)
        Image.fromarray((np.clip(tgt_vis, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_target{ext}")
        Image.fromarray((solver.mask * 255).astype(np.uint8)).save(f"{base_name}_mask{ext}")
        Image.fromarray((solver.edge_mask * 255).astype(np.uint8)).save(f"{base_name}_edges{ext}")
        Image.fromarray((np.clip(result, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_flattened{ext}")

        # Visualizza e salva l'immagine composita con 4 pannelli
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
        print(f"✓ Immagini singole: {base_name}_{{target,mask,edges,flattened}}{ext}")

    elif exec_mode == 'local_illumination_change':
        solver = LocalIlluminationChangeSolver(
            source_path, mask_path,
            solver=args.solver,
            grayscale=args.grayscale,
            mode=args.illum_mode,
            sigma=args.sigma,
            beta=args.beta,
            alpha_factor= args.alpha_factor,
            mask_source=args.mask_source,
            mask_target=args.mask_target
        )
        result = solver.solve()

        src_vis = solver.original_rgb if not solver.grayscale else rgb2gray(solver.original_rgb)

        base_name, ext = os.path.splitext(args.output)
        Image.fromarray((np.clip(src_vis, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_input{ext}")
        Image.fromarray((solver.mask * 255).astype(np.uint8)).save(f"{base_name}_mask{ext}")
        Image.fromarray((np.clip(result, 0, 1) * 255).astype(np.uint8)).save(f"{base_name}_illumination{ext}")

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        if solver.grayscale:
            axes[0].imshow(src_vis, cmap='gray')
            axes[2].imshow(result, cmap='gray')
        else:
            axes[0].imshow(np.clip(src_vis, 0, 1))
            axes[2].imshow(np.clip(result, 0, 1))
        axes[0].set_title('Originale')
        axes[0].axis('off')

        axes[1].imshow(solver.mask, cmap='gray')
        axes[1].set_title('Mask (Dominio Ω)')
        axes[1].axis('off')

        axes[2].set_title('Local Illumination Change')
        axes[2].axis('off')

        plt.tight_layout()
        plt.savefig(args.output, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"\n✓ Immagine composita salvata: {args.output}")
        print(f"✓ Immagini singole: {base_name}_{{input,mask,illumination}}{ext}")

    elif exec_mode == 'local_color_change':
        solver = LocalColorChangeSolver(
            source_path, mask_path,
            solver=args.solver,
            mode=args.color_mode,
            rgb_factors=args.rgb_factors,
            change_hue=args.change_hue,
            mask_source=args.mask_source,
            mask_target=args.mask_target
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

    elif exec_mode == 'seamless_tiling':
        tiler = PoissonSeamlessTiling(source_path, solver=args.solver, scale=args.scale)
        tileable = tiler.generate_tileable_image()

        base_name, ext = os.path.splitext(args.output)
        if ext == '':
            ext = '.png'

        Image.fromarray(tileable).save(args.output)

        source_img = (tiler.img * 255).astype(np.uint8)
        source_tile = tile_image(source_img, x_repeat=3, y_repeat=2)
        result_tile = tile_image(tileable, x_repeat=3, y_repeat=2)

        output_dir = os.path.dirname(args.output)
        if output_dir == '':
            output_dir = '.'
        base_name = os.path.splitext(os.path.basename(args.output))[0]
        source_tile_path = os.path.join(output_dir, f'{base_name}_original_2x3{ext}')
        result_tile_path = os.path.join(output_dir, f'{base_name}_seamless_2x3{ext}')

        Image.fromarray(source_tile).save(source_tile_path)
        Image.fromarray(result_tile).save(result_tile_path)
        print(f"\n✓ Immagine base salvata: {args.output}")
        print(f"✓ Immagini 2x3: {source_tile_path}, {result_tile_path}")


if __name__ == '__main__':
    main()
