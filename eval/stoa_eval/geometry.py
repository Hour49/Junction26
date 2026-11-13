"""Box overlap, shared by the Part 1 scorers."""

Box = tuple[float, float, float, float]


def iou(a: Box, b: Box) -> float:
    """IoU of two [x0, y0, x1, y1] boxes; identical boxes give 1 even when flat."""
    if a == b:
        return 1.0
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(width, 0.0) * max(height, 0.0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0
