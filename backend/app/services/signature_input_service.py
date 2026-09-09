"""Validate and normalize a signature mark independently of authenticated identity."""

import base64
from io import BytesIO
import warnings
from PIL import Image, UnidentifiedImageError


def normalize_signature_image(value):
    if not isinstance(value, str) or not value.startswith("data:image/png;base64,") or len(value) > 700000:
        raise ValueError("Signature images must be PNG and smaller than 500 KB.")
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        if len(raw) > 500000:
            raise ValueError("Signature image exceeds 500 KB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as picture:
                if picture.format != "PNG" or picture.width > 2048 or picture.height > 1024 or min(picture.size) < 2:
                    raise ValueError("Signature image dimensions must be between 2×2 and 2048×1024.")
                picture.load()
                normalized = picture.convert("RGBA")
                # Reject fully transparent and blank monochrome canvases.
                visible = Image.new("RGBA", normalized.size, "white")
                visible.alpha_composite(normalized)
                if all(low == high for low, high in visible.convert("RGB").getextrema()):
                    raise ValueError("The signature image is blank.")
                result = BytesIO()
                normalized.save(result, format="PNG")
                return base64.b64encode(result.getvalue()).decode("ascii")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("The signature image could not be read.") from exc
