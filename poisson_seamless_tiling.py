import os
import numpy as np
from PIL import Image
from argparse import ArgumentParser
import scipy.sparse.linalg
from scipy.sparse import linalg as sp_linalg

import utils


class PoissonSeamlessTiling:
    """
    Implements seamless tiling using Poisson editing.
    
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

        self.mask = np.ones((self.img_h, self.img_w), dtype=np.float64)
        self.inner_mask, self.boundary_mask = utils.process_mask(self.mask)

        self.pixel_ids = utils.get_pixel_ids(self.mask)
        self.inner_ids = utils.get_masked_values(self.pixel_ids, self.inner_mask).flatten()
        self.boundary_ids = utils.get_masked_values(self.pixel_ids, self.boundary_mask).flatten()
        self.mask_ids = utils.get_masked_values(self.pixel_ids, self.mask).flatten()

        self.inner_pos = np.searchsorted(self.mask_ids, self.inner_ids)
        self.boundary_pos = np.searchsorted(self.mask_ids, self.boundary_ids)
        self.mask_pos = np.searchsorted(self.pixel_ids.flatten(), self.mask_ids)

        self.solver_name = solver
        self.solver = getattr(scipy.sparse.linalg, solver)

        self.A = self._construct_A_matrix()

        if solver == 'spsolve':
            self.A_factored = sp_linalg.splu(self.A.tocsc())
            self.use_factored = True
        else:
            self.use_factored = False

    def _construct_A_matrix(self):
        A = scipy.sparse.lil_matrix((len(self.mask_ids), len(self.mask_ids)))

        for i, pixel_id in enumerate(self.inner_ids):
            row, col = divmod(pixel_id, self.img_w)
            center_pos = self.inner_pos[i]
            A[center_pos, center_pos] = -4

            neighbors = [
                (row - 1, col, pixel_id - self.img_w),
                (row + 1, col, pixel_id + self.img_w),
                (row, col - 1, pixel_id - 1),
                (row, col + 1, pixel_id + 1),
            ]

            for n_row, n_col, n_pixel_id in neighbors:
                if 0 <= n_row < self.img_h and 0 <= n_col < self.img_w:
                    n_pos = np.searchsorted(self.mask_ids, n_pixel_id)
                    if n_pos < len(self.mask_ids) and self.mask_ids[n_pos] == n_pixel_id:
                        A[center_pos, n_pos] = 1

        A[self.boundary_pos, self.boundary_pos] = 1
        return A.tocsr()

    def _get_periodic_boundary_values(self, channel_idx):
        if self.is_color:
            img_channel = self.img[..., channel_idx]
        else:
            img_channel = self.img

        boundary_values = np.zeros(len(self.boundary_ids))

        for idx, pixel_id in enumerate(self.boundary_ids):
            row, col = divmod(pixel_id, self.img_w)

            if row == 0:
                avg_value = 0.5 * (img_channel[0, col] + img_channel[-1, col])
                boundary_values[idx] = avg_value
            elif row == self.img_h - 1:
                avg_value = 0.5 * (img_channel[-1, col] + img_channel[0, col])
                boundary_values[idx] = avg_value
            elif col == 0:
                avg_value = 0.5 * (img_channel[row, 0] + img_channel[row, -1])
                boundary_values[idx] = avg_value
            elif col == self.img_w - 1:
                avg_value = 0.5 * (img_channel[row, -1] + img_channel[row, 0])
                boundary_values[idx] = avg_value
            else:
                boundary_values[idx] = img_channel.flat[pixel_id]

        return boundary_values

    def construct_b(self, gradients, boundary_values):
        b = np.zeros(len(self.mask_ids))
        b[self.inner_pos] = utils.get_masked_values(gradients, self.inner_mask).flatten()
        b[self.boundary_pos] = boundary_values
        return b

    def solve_system(self, b):
        if self.use_factored:
            x = self.A_factored.solve(b)
        else:
            x = self.solver(self.A, b)
            if isinstance(x, tuple):
                x = x[0]
        return x

    def compute_gradients(self, channel_data):
        return utils.compute_laplacian(channel_data)

    def apply_seamless_tiling(self, channel_data, channel_idx):
        gradients = self.compute_gradients(channel_data)
        boundary_values = self._get_periodic_boundary_values(channel_idx)
        b = self.construct_b(gradients, boundary_values)
        x = self.solve_system(b)

        tiled = np.zeros_like(channel_data).flatten()
        tiled[self.mask_pos] = x
        tiled = tiled.reshape(channel_data.shape)
        return np.clip(tiled, 0, 1)

    def generate_tileable_image(self):
        if self.is_color:
            result = []
            for c in range(3):
                channel_result = self.apply_seamless_tiling(self.img[..., c], c)
                result.append(channel_result)
            tileable = np.dstack(result)
        else:
            tileable = self.apply_seamless_tiling(self.img, 0)

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
