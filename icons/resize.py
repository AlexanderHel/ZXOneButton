from PIL import Image
import os

def resize_icon(input_file, sizes):
    img = Image.open(input_file)
    base, ext = os.path.splitext(input_file)
    
    for size in sizes:
        img_resized = img.resize((size, size), Image.LANCZOS)
        output_file = f'{base}_{size}x{size}{ext}'
        img_resized.save(output_file)
        print(f'Resized image saved as: {output_file}')

# Specify the input filename and desired sizes
input_file = 'icon.ico'
desired_sizes = [16, 32, 48, 256]

# Call the function to resize the icon
resize_icon(input_file, desired_sizes)