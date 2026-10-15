"""PDF reports with ReportLab (pure Python: works on any hosting, no system libraries)."""
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.report_types import InventoryReport, MovementsReport

PAGE = landscape(A4)
MARGIN = 12 * mm
DARK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#D1D5DB")
ZEBRA = colors.HexColor("#F9FAFB")
TOTAL_BG = colors.HexColor("#F3F4F6")
STATUS_BG = {"Agotado": colors.HexColor("#FDE2E1"), "Stock bajo": colors.HexColor("#FEF3C7")}
STATUS_TEXT = {"Agotado": "#B91C1C", "Stock bajo": "#92400E", "Disponible": "#15803D"}
ENTRY_TEXT, EXIT_TEXT = "#1D4ED8", "#C2410C"

_base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("title", parent=_base["Title"], fontName="Helvetica-Bold", fontSize=16,
                            leading=20, alignment=0, spaceAfter=2, textColor=DARK),
    "subtitle": ParagraphStyle("subtitle", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=10,
                               textColor=colors.HexColor("#374151")),
    "meta": ParagraphStyle("meta", parent=_base["Normal"], fontSize=8, leading=10, textColor=MUTED),
    "h2": ParagraphStyle("h2", parent=_base["Heading2"], fontName="Helvetica-Bold", fontSize=11,
                         spaceBefore=8, spaceAfter=4, textColor=DARK),
    "cell": ParagraphStyle("cell", parent=_base["Normal"], fontSize=7.5, leading=9),
    "cell_right": ParagraphStyle("cell_right", parent=_base["Normal"], fontSize=7.5, leading=9, alignment=TA_RIGHT),
    "empty": ParagraphStyle("empty", parent=_base["Normal"], fontSize=10, textColor=MUTED, spaceBefore=12),
    "kpi_label": ParagraphStyle("kpi_label", parent=_base["Normal"], fontSize=7.5, textColor=MUTED),
    "kpi_value": ParagraphStyle("kpi_value", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16),
}


# --- Formatting helpers ----------------------------------------------------------------------------

def _money(value: Decimal) -> str:
    return f"S/ {value:,.2f}"


def _qty(value: Decimal) -> str:
    text = f"{value:,.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _p(text: str, style: str = "cell", color: str | None = None, bold: bool = False) -> Paragraph:
    """Paragraph cell: wraps long text. User data is escaped (a product named 'A&B <x>' is safe)."""
    content = escape(str(text))
    if bold:
        content = f"<b>{content}</b>"
    if color:
        content = f'<font color="{color}">{content}</font>'
    return Paragraph(content, STYLES[style])


class _NumberedCanvas(canvas.Canvas):
    """Draws 'Página X de Y' on every page (the total is only known after the last page)."""

    def __init__(self, *args, footer_text: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []
        self._footer_text = footer_text

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        width, _ = PAGE
        self.setStrokeColor(LINE)
        self.line(MARGIN, 9 * mm, width - MARGIN, 9 * mm)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(MUTED)
        self.drawString(MARGIN, 5.5 * mm, self._footer_text)
        self.drawRightString(width - MARGIN, 5.5 * mm, f"Página {self._pageNumber} de {total}")


def _build(story: list, footer_text: str, title: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=14 * mm, title=title, author=footer_text)
    doc.build(story, canvasmaker=lambda *a, **kw: _NumberedCanvas(*a, footer_text=footer_text, **kw))
    buffer.seek(0)
    return buffer


def _header(title: str, business: str, generated_at, filters: list[str]) -> list:
    return [
        Paragraph(escape(title), STYLES["title"]),
        Paragraph(escape(business), STYLES["subtitle"]),
        Paragraph(escape(f"Generado el {generated_at:%d/%m/%Y %H:%M} · {' · '.join(filters)}"), STYLES["meta"]),
        Spacer(1, 6),
    ]


def _kpis(items: list[tuple[str, str]]) -> Table:
    """A row of small indicator boxes above the table."""
    # A table cell may hold a list of flowables: label on top, big value below.
    cells = [[_p(label, "kpi_label"), Paragraph(escape(value), STYLES["kpi_value"])] for label, value in items]
    table = Table([cells], colWidths=[62 * mm] * len(items), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _data_table(rows: list[list], widths: list[float], right_cols: list[int], extra_styles=None, total_row=False) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    styles = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for col in right_cols:
        styles.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    last_data = len(rows) - (2 if total_row else 1)
    for r in range(2, last_data + 1, 2):
        styles.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
    if total_row:
        styles += [("BACKGROUND", (0, -1), (-1, -1), TOTAL_BG), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                   ("LINEABOVE", (0, -1), (-1, -1), 0.75, DARK)]
    table.setStyle(TableStyle(styles + (extra_styles or [])))
    return table


# --- Inventory -----------------------------------------------------------------------------------

def inventory_pdf(report: InventoryReport) -> BytesIO:
    story = _header("Reporte de inventario actual", report.business_name, report.generated_at, report.filters)
    story.append(_kpis([
        ("Productos", str(len(report.rows))),
        ("En alerta (agotados)", f"{report.low_stock_count} ({report.out_of_stock_count})"),
        ("Valor total a costo", _money(report.total_value)),
    ]))
    story.append(Spacer(1, 8))

    if not report.rows:
        story.append(Paragraph("No hay productos para los filtros elegidos.", STYLES["empty"]))
        return _build(story, report.business_name, "Reporte de inventario")

    header = ["SKU", "Producto", "Categoría", "Unidad", "Stock", "Mínimo", "P. compra", "P. venta", "Valor", "Estado"]
    rows, extra = [header], []
    for i, item in enumerate(report.rows, start=1):
        rows.append([
            item.sku, _p(item.name), _p(item.category), item.unit, _qty(item.stock), _qty(item.min_stock),
            _money(item.purchase_price), _money(item.sale_price), _money(item.stock_value),
            _p(item.status, color=STATUS_TEXT[item.status], bold=item.status != "Disponible"),
        ])
        if item.status in STATUS_BG:  # tint rows that need attention
            extra.append(("BACKGROUND", (0, i), (-1, i), STATUS_BG[item.status]))
    rows.append(["", "Total", "", "", "", "", "", "", _money(report.total_value), ""])

    widths = [24, 70, 34, 15, 18, 18, 24, 24, 26, 20]  # sums 273 mm (landscape A4 minus margins)
    story.append(_data_table(rows, [w * mm for w in widths], right_cols=[4, 5, 6, 7, 8], extra_styles=extra, total_row=True))
    return _build(story, report.business_name, "Reporte de inventario")


# --- Movements -----------------------------------------------------------------------------------

def movements_pdf(report: MovementsReport) -> BytesIO:
    story = _header("Reporte de movimientos de inventario", report.business_name, report.generated_at, report.filters)
    story.append(_kpis([
        ("Entradas", f"{report.entry_count} · {_money(report.total_in_value)}"),
        ("Salidas", f"{report.exit_count} · {_money(report.total_out_value)}"),
        ("Movimientos", str(len(report.rows))),
    ]))

    if not report.rows:
        story.append(Paragraph("No hay movimientos en el periodo elegido.", STYLES["empty"]))
        return _build(story, report.business_name, "Reporte de movimientos")

    summary = [["Tipo", "Motivo", "N.º", "Valor a costo"]]
    for type_label, reason, count, value in report.by_reason():
        if count:
            summary.append([type_label, reason, str(count), _money(value)])
    story.append(KeepTogether([
        Paragraph("Resumen por motivo", STYLES["h2"]),
        _data_table(summary, [22 * mm, 48 * mm, 14 * mm, 30 * mm], right_cols=[2, 3]),
    ]))

    story.append(Paragraph("Detalle", STYLES["h2"]))
    rows = [["Fecha", "SKU", "Producto", "Tipo", "Motivo", "Cantidad", "Costo unit.", "Costo total", "Saldo", "Usuario", "Observaciones"]]
    for m in report.rows:
        rows.append([
            f"{m.moment:%d/%m/%Y %H:%M}", m.sku, _p(m.product),
            _p(m.type_label, color=ENTRY_TEXT if m.is_entry else EXIT_TEXT, bold=True),
            _p(m.reason), f"{'+' if m.is_entry else '-'}{_qty(m.quantity)} {m.unit}",
            _money(m.unit_cost), _money(m.total_cost), _qty(m.stock_after), m.user, _p(m.notes),
        ])
    widths = [25, 20, 48, 18, 27, 22, 20, 22, 15, 18, 38]  # sums 273 mm (landscape A4 minus margins)
    story.append(_data_table(rows, [w * mm for w in widths], right_cols=[5, 6, 7, 8]))
    return _build(story, report.business_name, "Reporte de movimientos")
