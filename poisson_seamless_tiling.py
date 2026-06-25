import os
import numpy as np
from PIL import Image
from argparse import ArgumentParser
from solver import PoissonInterpolationSolver


class PoissonSeamlessTiling(PoissonInterpolationSolver):
    """
    Implements seamless tiling using Poisson editing by reusing PoissonInterpolationSolver.
    
    When the domain Ω is rectangular, its content can be made tileable by 
    enforcing periodic boundary conditions with the Poisson solver.
    The boundary conditions are derived from the boundary values of the 
    original image, such that opposite sides correspond to identical 
    Dirichlet conditions.
    
    Reference: Pérez et al., "Poisson Image Editing", SIGGRAPH 2003
    """
    
    def __init__(self, image_path, solver='spsolve', scale=1.0):
        """
        Initialize the seamless tiling solver.
        
        Args:
            image_path: Path to the input image
            solver: Linear solver to use ('spsolve' or iterative solver name)
            scale: Image scaling factor
        """
        img = Image.open(image_path)
        if scale != 1.0:
            w, h = img.size
            img = img.resize((int(w * scale), int(h * scale)), Image.BICUBIC)

        self.img = np.array(img).astype(np.float64) / 255.0
        if len(self.img.shape) == 3:
            self.img = self.img[..., :3]

        self.img_h, self.img_w = self.img.shape[:2]
        self.is_color = len(self.img.shape) == 3

        # Create a mask of all ones
        mask = np.ones((self.img_h, self.img_w), dtype=np.float64)

        # Construct target boundary image with periodic values
        target = np.zeros_like(self.img)
        if self.is_color:
            for c in range(3):
                target[..., c] = self._compute_periodic_target_channel(self.img[..., c])
        else:
            target = self._compute_periodic_target_channel(self.img)

        # Call parent constructor to setup matrix A and properties
        super().__init__(
            source_path=self.img,
            target_path=target,
            mask_path=mask,
            solver=solver,
            color_space='RGB',
            mixed=False
        )

    def _compute_periodic_target_channel(self, img_channel):
        target_ch = np.zeros_like(img_channel)

        # Corner average
        corner_avg = 0.25 * (
            img_channel[0, 0] +
            img_channel[0, -1] +
            img_channel[-1, 0] +
            img_channel[-1, -1]
        )

        # Set corners
        target_ch[0, 0] = corner_avg
        target_ch[0, -1] = corner_avg
        target_ch[-1, 0] = corner_avg
        target_ch[-1, -1] = corner_avg

        # Set top/bottom borders (excluding corners)
        target_ch[0, 1:-1] = 0.5 * (img_channel[0, 1:-1] + img_channel[-1, 1:-1])
        target_ch[-1, 1:-1] = target_ch[0, 1:-1]

        # Set left/right borders (excluding corners)
        target_ch[1:-1, 0] = 0.5 * (img_channel[1:-1, 0] + img_channel[1:-1, -1])
        target_ch[1:-1, -1] = target_ch[1:-1, 0]

        return target_ch

    def generate_tileable_image(self):
        """
        Generates the tileable image using the Poisson solver.
        """
        tileable = self.solve(mixed=False)
        tileable = (tileable * 255).astype(np.uint8)
        return tileable


def tile_image(image, x_repeat=3, y_repeat=2):
    if image.ndim == 3:
        return np.tile(image, (y_repeat, x_repeat, 1))
    return np.tile(image, (y_repeat, x_repeat))


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--input', type=str, required=True, help='Input image path.')
    parser.add_argument('--output', type=str, default=None, help='Output image path.')
    parser.add_argument('--scale', type=float, default=1.0, help='Image scaling factor.')
    parser.add_argument('--solver', type=str, default='spsolve', help='Linear system solver.')

    args = parser.parse_args()

    tiler = PoissonSeamlessTiling(args.input, args.solver, args.scale)
    tileable = tiler.generate_tileable_image()

    if args.output is None:
         base_name = os.path.splitext(os.path.basename(args.input))[0]
         args.output = f'{base_name}_seamless_tiling.png'

    Image.fromarray(tileable).save(args.output)
    print(f'Seamless tiling saved to: {args.output}')

    source_img = (tiler.img * 255).astype(np.uint8)
    source_tile = tile_image(source_img, x_repeat=3, y_repeat=2)
    result_tile = tile_image(tileable, x_repeat=3, y_repeat=2)

    output_dir = os.path.dirname(args.output)
    if output_dir == '':
        output_dir = '.'
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    source_tile_path = os.path.join(output_dir, f'{base_name}_original_2x3.png')
    result_tile_path = os.path.join(output_dir, f'{base_name}_seamless_2x3.png')

    Image.fromarray(source_tile).save(source_tile_path)
    Image.fromarray(result_tile).save(result_tile_path)
    print(f'Original source 2x3 tile saved to: {source_tile_path}')
    print(f'Seamless result 2x3 tile saved to: {result_tile_path}')
