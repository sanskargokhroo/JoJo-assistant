"""
🎨 JoJo AGI: UI-TARS Action Visualizer & Grounding Blackboard
Adapted from ByteDance UI-TARS-desktop (visualizer blackboard):
- Visual overlay on captured screenshots
- Bounding box rendering with translucent fill & crisp border
- Target crosshairs and ripple circles for clicks
- Directed vector arrows for drag / swipe actions
- Label pills / badges with drop shadow showing action name and screen coordinates
"""

import os
import math
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

# Action Palette (Tailored, modern UI-TARS colors)
ACTION_COLORS = {
    "click": (0, 220, 130, 220),         # Vibrant Emerald / Cyan
    "left_double": (0, 180, 255, 220),   # Vibrant Sky Blue
    "right_single": (255, 170, 0, 220),  # Amber / Orange
    "middle_click": (200, 100, 255, 220),# Purple
    "drag": (255, 60, 120, 220),         # Neon Pink / Magenta
    "swipe": (255, 60, 120, 220),
    "type": (80, 120, 255, 220),         # Royal Blue
    "hotkey": (170, 80, 255, 220),       # Violet
    "scroll": (255, 215, 0, 220),        # Gold / Yellow
    "wait": (150, 150, 150, 180),        # Gray
    "default": (0, 200, 255, 220)
}

FILL_ALPHA = 45  # Translucent bounding box fill


def get_default_font(size: int = 14):
    """Attempts to load a clean TTF font; falls back to default."""
    candidates = [
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf",
        "C:\\Windows\\Fonts\\consola.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def render_action_overlay(
    image: Image.Image,
    actions: List[Dict[str, Any]],
    output_path: Optional[str] = None
) -> Image.Image:
    """
    Renders visual markers, bounding boxes, crosshairs, and badges on top of an image.
    
    Args:
        image: Original PIL screenshot.
        actions: List of parsed action dictionaries from UI-TARS.
        output_path: Optional path to save the annotated image.
    Returns:
        Annotated PIL Image.
    """
    canvas = image.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = get_default_font(13)
    font_bold = get_default_font(15)

    img_w, img_h = canvas.size

    for idx, act in enumerate(actions, start=1):
        action_type = act.get("action_type", "default").lower()
        inputs = act.get("action_inputs", {})
        color = ACTION_COLORS.get(action_type, ACTION_COLORS["default"])
        rgb = color[:3]

        start_coords = inputs.get("start_coords")
        end_coords = inputs.get("end_coords")
        raw_box = inputs.get("start_box")

        # 1. Draw Bounding Box if box was specified
        box_rect = None
        if raw_box and isinstance(raw_box, (list, tuple)) and len(raw_box) == 4:
            x1, y1, x2, y2 = [int(v) for v in raw_box]
            # Ensure proper min/max
            left = max(0, min(x1, x2))
            top = max(0, min(y1, y2))
            right = min(img_w, max(x1, x2))
            bottom = min(img_h, max(y1, y2))
            box_rect = (left, top, right, bottom)

            # Translucent fill
            fill_color = rgb + (FILL_ALPHA,)
            draw.rectangle([left, top, right, bottom], fill=fill_color, outline=rgb + (255,), width=2)

        # 2. Draw Target Point Markers (Clicks, Touches)
        if start_coords and len(start_coords) >= 2:
            cx, cy = int(start_coords[0]), int(start_coords[1])

            # Click ripple rings
            for r in [6, 14, 22]:
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rgb + (max(60, 255 - r * 8),), width=2)
            
            # Solid central dot
            draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=rgb + (255,))

            # Crosshairs
            ch_len = 12
            draw.line([cx - ch_len, cy, cx + ch_len, cy], fill=rgb + (255,), width=1)
            draw.line([cx, cy - ch_len, cx, cy + ch_len], fill=rgb + (255,), width=1)

            # 3. If Drag / Swipe, draw Vector Arrow to end_coords
            if end_coords and len(end_coords) >= 2:
                ex, ey = int(end_coords[0]), int(end_coords[1])
                # Main line
                draw.line([cx, cy, ex, ey], fill=rgb + (255,), width=3)

                # End target circle
                draw.ellipse([ex - 6, ey - 6, ex + 6, ey + 6], fill=rgb + (255,), outline=(255, 255, 255, 255), width=2)

                # Arrowhead
                angle = math.atan2(ey - cy, ex - cx)
                arr_len = 14
                p1_x = ex - arr_len * math.cos(angle - math.pi / 6)
                p1_y = ey - arr_len * math.sin(angle - math.pi / 6)
                p2_x = ex - arr_len * math.cos(angle + math.pi / 6)
                p2_y = ey - arr_len * math.sin(angle + math.pi / 6)
                draw.polygon([(ex, ey), (p1_x, p1_y), (p2_x, p2_y)], fill=rgb + (255,))

            # 4. Action Label Pill / Badge
            badge_text = f"#{idx} {action_type.upper()} ({cx}, {cy})"
            if action_type == "type":
                content_preview = inputs.get("content", "")[:18]
                badge_text += f' "{content_preview}"'
            elif action_type == "hotkey":
                badge_text += f" [{inputs.get('key', '')}]"

            # Badge bounds
            bbox = font.getbbox(badge_text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            pad_x, pad_y = 6, 4

            badge_x = min(img_w - text_w - 20, max(10, cx + 18))
            badge_y = min(img_h - text_h - 20, max(10, cy - 25))

            pill_rect = [badge_x - pad_x, badge_y - pad_y, badge_x + text_w + pad_x, badge_y + text_h + pad_y]

            # Drop shadow
            draw.rounded_rectangle(
                [pill_rect[0] + 2, pill_rect[1] + 2, pill_rect[2] + 2, pill_rect[3] + 2],
                radius=4,
                fill=(0, 0, 0, 160)
            )
            # Pill background
            draw.rounded_rectangle(
                pill_rect,
                radius=4,
                fill=(20, 24, 33, 230),
                outline=rgb + (255,),
                width=1
            )
            # Pill text
            draw.text((badge_x, badge_y), badge_text, fill=(255, 255, 255, 255), font=font)

    # Composite overlay on original screenshot
    annotated = Image.alpha_composite(canvas, overlay).convert("RGB")

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        annotated.save(output_path, "PNG")

    return annotated
