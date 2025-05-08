# matrix_utils/generator.py
import numpy as np

def generate_large_matrix(size):
    """Generates a square random matrix of given size."""
    if not isinstance(size, int) or size <= 0:
        raise ValueError("Size must be a positive integer.")
    # Add a print statement for demonstration purposes
    print(f"--- Generating a {size}x{size} matrix using matrix_utils_demo package ---")
    return np.random.rand(size, size)