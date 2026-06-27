# Poisson Image Editing

## Project Summary

This repository implements the Poisson Image Editing framework in Python, following the `PoissonImageEditing.pdf` reference paper. The project focuses on gradient-domain image editing methods for seamless blending, local color modification, illumination adjustment, texture flattening, and seamless tiling.

## Features

- Local color modification with Poisson-based blending
- Local illumination adjustment and color transfer
- Texture flattening for visual smoothing
- Seamless cloning and mixed-gradient cloning
- Guided interpolation and gradient-based editing
- Seamless tiling for texture synthesis

## Project Structure

- `local_color_change.py` — local color modification with Poisson blending
- `local_illumination_change.py` — local illumination and color transfer
- `texture_flattening.py` — texture flattening using gradient manipulation
- `poisson_seamless_tiling.py` — seamless periodic tiling
- `poisson_guided_interpolation.py` — guided interpolation with gradient constraints
- `solver.py` — core Poisson equation solver
- `utils.py` — image loading, preprocessing, and helper functions
- `run_test.sh` — batch runner for available test cases

## Data and Results

- `data/` — input datasets organized by technique and test case
- `results/` — output images generated during testing
- `extracted_images/` — extracted example images from the paper

## Documentation and Reference

- `PoissonImageEditing.pdf` — reference paper that this implementation follows, including problem formulation, algorithm design, and evaluation examples.

## Dependencies

This project uses the following Python libraries:

- `numpy>=1.21.0`
- `scipy>=1.7.0`
- `Pillow>=8.3.0`
- `scikit-image>=0.18.0`
- `matplotlib>=3.4.0`

Install dependencies from `requirements.txt`.

## Setup

1. Create and activate the Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the batch test script with no parameters to execute all available test cases:

```bash
./run_test.sh
```

Target specific techniques by passing a keyword:

- `all` — run all available tests (default)
- `color` — local color change tests
- `illumination` — local illumination change tests
- `cloning` — seamless cloning and mixed-gradient cloning tests
- `mixed` — alias for the cloning family, also runs the seamless cloning / mixed-gradient tests
- `tiling` — seamless tiling tests
- `flattening` — texture flattening tests

Example commands:

```bash
./run_test.sh all
./run_test.sh color
./run_test.sh illumination
./run_test.sh cloning
./run_test.sh mixed
./run_test.sh tiling
./run_test.sh flattening
```

Individual modules can also be executed directly to reproduce specific results.

## Notes

- The implementation uses standard scientific Python libraries.
- OpenCV is intentionally excluded from the core image editing computations to comply with assignment guidelines.
- The repository is structured for reproducibility and result comparison.

## Limitations

- Performance depends on image size and solver efficiency.
- Some test cases may require manual tuning of masks and parameters.
- The current implementation targets algorithm correctness and visual results over real-time performance.

## References

- `PoissonImageEditing.pdf` — paper and project description
- Assignment guidelines in `consegna_esame.txt`

## Author

- Student: Davide De Soricellis
