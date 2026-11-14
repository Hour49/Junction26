"""A synthetic swiss_dwellings sheet whose walls are grey fills (1:100, 1 m = 28.35 pt):
Bagno 1.01 (3 x 3 m) | a 0.12 m wall with a 1 m door | Stanza 1.02 (3.89 x 3 m), 0.2 m outer
walls, and Balcone 1.03 past the façade."""

from pdf_sheets import BLACK, SheetPdf, rect
from test_vector_pdf import DOOR_GREY, swiss_room

WALL = (191, 191, 191)
M = 72 / 25.4 * 1000 / 100  # points per metre at 1:100


def wall(sheet: SheetPdf, x0: float, y0: float, x1: float, y1: float) -> None:
    sheet.path(rect(x0, y0, x1, y1), stroke=BLACK, width=0.99, fill=WALL)


def walled_flat(scale: bool = True) -> bytes:
    sheet = SheetPdf(600, 400)
    left, top, mid, right, bottom = 100, 100, 100 + 3 * M, 100 + 3.12 * M, 100 + 3 * M
    end = right + 3.888 * M
    swiss_room(sheet, (left, top, mid, bottom), "Bagno", "1.01", "9.00 m²")
    swiss_room(sheet, (right, top, end, bottom), "Stanza", "1.02", "11.66 m²")
    swiss_room(sheet, (left, bottom + 0.2 * M, end, bottom + 2 * M), "Balcone", "1.03", fill=228)
    t = 0.2 * M
    wall(sheet, left - t, top - t, end + t, top)  # façade, top
    wall(sheet, left - t, bottom, end + t, bottom + t)  # façade to the balcony
    wall(sheet, left - t, top, left, bottom)
    wall(sheet, end, top, end + t, bottom)
    door = (top + 1 * M, top + 2 * M)
    wall(sheet, mid, top, right, door[0])  # the inside wall, with a 1 m door gap
    wall(sheet, mid, door[1], right, bottom)
    sheet.path(rect(mid - 2, door[0], right + 2, door[1]), stroke=DOOR_GREY, width=0.37)
    if scale:
        sheet.text("Massstab 1:100 (A3)", 450, 380)
    return sheet.pdf()
