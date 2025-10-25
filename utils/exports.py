# =====================================
# utils/exports.py — funzioni di esportazione (Excel + PDF)
# =====================================
from io import BytesIO
import pandas as pd
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

from utils.formatting import fmt_date, safe_text


def export_pdf_contratti(df_ct, sel_id, rag_soc):
    """Esporta i contratti di un cliente in formato PDF A4 orizzontale con stile professionale."""
    from fpdf import FPDF
    from utils.formatting import safe_text, fmt_date

    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)

    # ✅ intestazione colonne (manteniamo 6 per leggibilità)
    headers = ["NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto", "TotRata", "Stato"]
    widths = [30, 25, 25, 20, 95, 25, 25]  # perfettamente centrato in A4 landscape

    class PDF(FPDF):
        def header(self):
            """Header con logo e barra blu"""
            self.set_fill_color(37, 99, 235)  # blu SHT
            self.rect(0, 0, 297, 18, "F")
            self.image("https://www.shtsrl.com/template/images/logo.png", 10, 2, 30)
            self.set_text_color(255, 255, 255)
            self.set_font("Arial", "B", 14)
            self.cell(0, 8, "GESTIONALE CLIENTI SHT — CONTRATTI", ln=1, align="C")
            self.ln(6)

        def footer(self):
            """Piè di pagina elegante"""
            self.set_y(-12)
            self.set_font("Arial", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, f"Pagina {self.page_no()}", 0, 0, "C")

    pdf = PDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Titolo cliente
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 10, safe_text(f"Contratti Cliente: {rag_soc}"), ln=1, align="C")

    # Intestazione tabella
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, safe_text(h), 1, 0, "C", fill=True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 9)

    # Contenuto righe
    for _, r in disp.iterrows():
        stato = str(r.get("Stato", "")).lower()
        cell_values = [safe_text(str(r.get(h, ""))) for h in headers]

        # 🔹 altezza dinamica riga (in base alla descrizione)
        descr = cell_values[headers.index("DescrizioneProdotto")] if "DescrizioneProdotto" in headers else ""
        lines = (len(descr) // 70) + 1
        max_height = 6 * lines

        y_before = pdf.get_y()
        x_before = pdf.get_x()

        for i, h in enumerate(headers):
            text = cell_values[i]
            if stato == "chiuso":
                pdf.set_fill_color(255, 235, 238)  # rosa chiaro
            else:
                pdf.set_fill_color(255, 255, 255)

            # 🔸 MultiCell per testo a capo
            x = pdf.get_x()
            y = pdf.get_y()
            align = "C" if h != "DescrizioneProdotto" else "L"
            pdf.multi_cell(widths[i], 6, text, border=1, align=align, fill=True)
            pdf.set_xy(x + widths[i], y)

        pdf.set_y(y_before + max_height)

    # Restituisce il PDF come bytes per download
    return pdf.output(dest="S").encode("latin-1", errors="replace")



def export_pdf_contratti(df_ct, sel_id, rag_soc):
    """Esporta i contratti di un cliente in formato PDF A4 orizzontale con stile professionale."""
    from fpdf import FPDF
    from utils.formatting import safe_text, fmt_date

    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)

    # ✅ intestazione colonne (manteniamo 6 per leggibilità)
    headers = ["NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto", "TotRata", "Stato"]
    widths = [30, 25, 25, 20, 95, 25, 25]  # perfettamente centrato in A4 landscape

    class PDF(FPDF):
        def header(self):
            """Header con logo e barra blu"""
            self.set_fill_color(37, 99, 235)  # blu SHT
            self.rect(0, 0, 297, 18, "F")
            self.image("https://www.shtsrl.com/template/images/logo.png", 10, 2, 30)
            self.set_text_color(255, 255, 255)
            self.set_font("Arial", "B", 14)
            self.cell(0, 8, "GESTIONALE CLIENTI SHT — CONTRATTI", ln=1, align="C")
            self.ln(6)

        def footer(self):
            """Piè di pagina elegante"""
            self.set_y(-12)
            self.set_font("Arial", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, f"Pagina {self.page_no()}", 0, 0, "C")

    pdf = PDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Titolo cliente
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 10, safe_text(f"Contratti Cliente: {rag_soc}"), ln=1, align="C")

    # Intestazione tabella
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, safe_text(h), 1, 0, "C", fill=True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 9)

    # Contenuto righe
    for _, r in disp.iterrows():
        stato = str(r.get("Stato", "")).lower()
        cell_values = [safe_text(str(r.get(h, ""))) for h in headers]

        # 🔹 altezza dinamica riga (in base alla descrizione)
        descr = cell_values[headers.index("DescrizioneProdotto")] if "DescrizioneProdotto" in headers else ""
        lines = (len(descr) // 70) + 1
        max_height = 6 * lines

        y_before = pdf.get_y()
        x_before = pdf.get_x()

        for i, h in enumerate(headers):
            text = cell_values[i]
            if stato == "chiuso":
                pdf.set_fill_color(255, 235, 238)  # rosa chiaro
            else:
                pdf.set_fill_color(255, 255, 255)

            # 🔸 MultiCell per testo a capo
            x = pdf.get_x()
            y = pdf.get_y()
            align = "C" if h != "DescrizioneProdotto" else "L"
            pdf.multi_cell(widths[i], 6, text, border=1, align=align, fill=True)
            pdf.set_xy(x + widths[i], y)

        pdf.set_y(y_before + max_height)

    # Restituisce il PDF come bytes per download
    return pdf.output(dest="S").encode("latin-1", errors="replace")
