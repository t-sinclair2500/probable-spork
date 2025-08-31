#!/usr/bin/env python3
"""
Texture Effects Demonstration

This script demonstrates the mid-century modern print texture effects
by applying them to sample images and generating before/after comparisons.
"""

import os
import sys
from pathlib import Path

# Add bin directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bin'))

def create_sample_image(width: int = 400, height: int = 300, output_path: str = "sample_image.png"):
    """Create a sample image for texture demonstration."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple geometric design
        img = Image.new('RGB', (width, height), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        
        # Draw some geometric shapes
        colors = [
            (52, 152, 219),   # Blue
            (46, 204, 113),   # Green  
            (155, 89, 182),   # Purple
            (241, 196, 15),   # Yellow
            (230, 126, 34),   # Orange
        ]
        
        # Draw rectangles
        for i, color in enumerate(colors):
            x = 50 + i * 60
            y = 50 + (i % 2) * 100
            draw.rectangle([x, y, x + 50, y + 50], fill=color, outline=(100, 100, 100), width=2)
        
        # Draw circles
        for i in range(3):
            x = 100 + i * 80
            y = 200
            draw.ellipse([x, y, x + 40, y + 40], fill=colors[i], outline=(100, 100, 100), width=2)
        
        # Add text
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except (OSError, IOError):
            font = ImageFont.load_default()
        
        draw.text((20, 20), "Sample Design", fill=(50, 50, 50), font=font)
        draw.text((20, height - 40), "Mid-Century Style", fill=(50, 50, 50), font=font)
        
        # Save image
        img.save(output_path, "PNG")
        print(f"✓ Created sample image: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"✗ Failed to create sample image: {e}")
        return None


def demonstrate_texture_effects():
    """Demonstrate texture effects on sample images."""
    
    try:
        from bin.cutout.texture_engine import create_texture_engine
        
        # Create sample image
        sample_path = create_sample_image()
        if not sample_path:
            return False
        
        # Load sample image
        from PIL import Image
        sample_img = Image.open(sample_path)
        print(f"✓ Loaded sample image: {sample_img.size}")
        
        # Texture configurations to demonstrate
        texture_configs = {
            "subtle_grain": {
                "enabled": True,
                "grain": {"density": 0.1, "intensity": 0.05},
                "halftone": {"enabled": False},
                "edges": {"edge_strength": 0.1}
            },
            "moderate_texture": {
                "enabled": True,
                "grain": {"density": 0.15, "intensity": 0.08},
                "halftone": {"enabled": True, "intensity": 0.08},
                "edges": {"edge_strength": 0.2, "feather_radius": 1.0}
            },
            "strong_vintage": {
                "enabled": True,
                "grain": {"density": 0.2, "intensity": 0.12},
                "halftone": {"enabled": True, "intensity": 0.15, "dot_size": 1.5},
                "edges": {"edge_strength": 0.4, "posterization_levels": 6}
            }
        }
        
        # Brand palette
        brand_palette = [
            "#1C4FA1", "#D62828", "#F6BE00", "#F28C28", 
            "#4E9F3D", "#008080", "#8B5E3C", "#1A1A1A", 
            "#FFFFFF", "#F8F1E5", "#FF6F91"
        ]
        
        # Create output directory
        output_dir = Path("texture_demo_output")
        output_dir.mkdir(exist_ok=True)
        
        # Save original for comparison
        original_path = output_dir / "00_original.png"
        sample_img.save(original_path, "PNG")
        print(f"✓ Saved original: {original_path}")
        
        # Apply each texture configuration
        for config_name, config in texture_configs.items():
            print(f"\n🎨 Applying {config_name} texture...")
            
            # Create texture engine
            engine = create_texture_engine(config, brand_palette)
            
            # Apply texture overlay
            textured_img = engine.apply_texture_overlay(sample_img)
            
            # Save textured version
            output_path = output_dir / f"{config_name}.png"
            textured_img.save(output_path, "PNG")
            print(f"✓ Saved {config_name}: {output_path}")
        
        # Create comparison grid
        create_comparison_grid(output_dir)
        
        print(f"\n🎉 Texture demonstration complete!")
        print(f"📁 Output saved to: {output_dir}")
        print(f"🔍 Check the generated images to see the texture effects")
        
        return True
        
    except Exception as e:
        print(f"✗ Texture demonstration failed: {e}")
        return False


def create_comparison_grid(output_dir: Path):
    """Create a comparison grid showing all texture variations."""
    try:
        from PIL import Image
        
        # Find all PNG files
        png_files = sorted(output_dir.glob("*.png"))
        if len(png_files) < 2:
            print("⚠ Not enough images for comparison grid")
            return
        
        # Load images
        images = []
        for png_file in png_files:
            img = Image.open(png_file)
            # Resize to consistent size
            img = img.resize((300, 225), Image.Resampling.LANCZOS)
            images.append(img)
        
        # Calculate grid dimensions
        cols = min(3, len(images))
        rows = (len(images) + cols - 1) // cols
        
        # Create grid
        grid_width = cols * 300
        grid_height = rows * 225
        grid_img = Image.new('RGB', (grid_width, grid_height), (255, 255, 255))
        
        # Place images in grid
        for i, img in enumerate(images):
            row = i // cols
            col = i % cols
            x = col * 300
            y = row * 225
            grid_img.paste(img, (x, y))
        
        # Save grid
        grid_path = output_dir / "texture_comparison_grid.png"
        grid_img.save(grid_path, "PNG")
        print(f"✓ Created comparison grid: {grid_path}")
        
    except Exception as e:
        print(f"✗ Failed to create comparison grid: {e}")


def main():
    """Run texture effects demonstration."""
    print("🎨 Mid-Century Modern Texture Effects Demonstration")
    print("=" * 60)
    
    success = demonstrate_texture_effects()
    
    if success:
        print("\n✅ Demonstration completed successfully!")
        print("📖 Check the generated images to see the texture effects in action.")
        return 0
    else:
        print("\n❌ Demonstration failed. Check the error messages above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
