# =====================================
# utils/pdf_builder.py — utilità per creazione PDF professionali
# =====================================
from fpdf import FPDF
from datetime import datetime
from utils.formatting import safe_text

# Colori aziendali
SHT_BLUE = (37, 99, 235)
SHT_LIGHT_BLUE = (230, 240, 255)
SHT_GRAY = (120, 120, 120)
SHT_RED_LIGHT = (255, 235, 238)


class SHTPDF(FPDF):
    """Classe PDF personalizzata per CRM-SHT con layout e stile coerente."""

    def __init__(self, orientation="L", unit="mm", format="A4", title="Documento CRM SHT"):
        super().__init__(orientation, unit, format)
        self.title = title
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(10, 18, 10)
        self.alias_nb_pages()

    # =============================
    # HEADER
    # =============================
    def header(self):
        self.set_fill_color(*SHT_BLUE)
        self.rect(0, 0, 297, 18, "F")
        try:
            self.image("https://www.shtsrl.com/template/images/logo.png", 10, 2, 30)
        except Exception:
            pass
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, safe_text(self.title), ln=1, align="C")
        self.ln(6)

    # =============================
    # FOOTER
    # =============================
    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", "I", 8)
        self.set_text_color(*SHT_GRAY)
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 10, f"Pagina {self.page_no()} di {{nb}} — Generato il {now}", 0, 0, "C")

    # =============================
    # UTILITÀ PER TABELLE
    # =============================
    def table_header(self, headers, widths, fill_color=SHT_BLUE):
        """Crea la riga d’intestazione di una tabella con stile SHT"""
        self.set_font("Arial", "B", 9)
        self.set_fill_color(*fill_color)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(widths[i], 8, safe_text(h), 1, 0, "C", fill=True)
        self.ln()
        self.set_font("Arial", "", 9)
        self.set_text_color(0, 0, 0)

    def table_row(self, row_data, widths, wrap_index=None, stato=None):
        """Aggiunge una riga alla tabella con testo a capo automatico e colorazione di stato"""
        y_start = self.get_y()
        max_height = 6

        # Calcola altezza dinamica se testo lungo
        if wrap_index is not None and len(row_data[wrap_index]) > 60:
            lines = (len(row_data[wrap_index]) // 60) + 1
            max_height = 6 * lines

        for i, val in enumerate(row_data):
            x = self.get_x()
            y = self.get_y()

            if stato == "chiuso":
                self.set_fill_color(*SHT_RED_LIGHT)
            else:
                self.set_fill_color(255, 255, 255)

            align = "L" if (wrap_index is not None and i == wrap_index) else "C"
            self.multi_cell(widths[i], 6, safe_text(val), border=1, align=align, fill=True)
            self.set_xy(x + widths[i], y)

        self.set_y(y_start + max_height)
