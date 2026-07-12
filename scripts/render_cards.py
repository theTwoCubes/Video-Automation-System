import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.slide_renderer.renderer import SlideRenderer

def main():
    print("Generating intro and outro cards...")
    renderer = SlideRenderer()
    
    out_dir = Path("output/cards")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Render Intro Card
    intro_data = {"id": "intro_card", "layout": "intro"}
    print(" Rendering intro_card.png...")
    renderer.render_slides([intro_data], str(out_dir), prefix="")
    
    # 2. Render Outro Card
    outro_data = {"id": "outro_card", "layout": "outro"}
    print(" Rendering outro_card.png...")
    renderer.render_slides([outro_data], str(out_dir), prefix="")
    
    print(f"\nDone! Cards saved to {out_dir.absolute()}")

if __name__ == "__main__":
    main()
