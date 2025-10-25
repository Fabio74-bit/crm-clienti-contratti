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


def export_excel_contratti(df_ct, sel_id, rag_soc):
    """Esporta i contratti di un cliente in formato Excel"""
    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Contratti {rag_soc}"
    ws.merge_cells("A1:M1")

    title = ws["A1"]
    title.value = f"Contratti Cliente: {rag_soc}"
    title.font = Font(size=14, bold=True, color="2563EB")
    title.alignment = Alignment(horizontal="center")

    headers = ["NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto",
               "NOL_FIN", "NOL_INT", "TotRata", "CopieBN", "EccBN", "CopieCol", "EccCol", "Stato"]
    ws.append(headers)

    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2563EB")
    center = Alignment(horizontal="center", wrap_text=True)
    thin = Border(left=Side(style="thin"), right=Side(style="thin"),
                  top=Side(style="thin"), bottom=Side(style="thin"))

    for i, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=i)
        c.font = head_font
        c.fill = head_fill
        c.alignment = center
        c.border = thin

    for _, row in disp.iterrows():
        ws.append([str(row.get(h, "")) for h in headers])
        stato = str(row.get("Stato", "")).lower()
        r_idx = ws.max_row
        for j in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=j)
            cell.alignment = center
            cell.border = thin
            if stato == "chiuso":
                cell.fill = PatternFill("solid", fgColor="FFCDD2")

    for i in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 25

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def export_pdf_contratti(df_ct, sel_id, rag_soc):
    """Esporta i contratti di un cliente in formato PDF"""
    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)

    headers = ["NumeroContratto", "DataInizio", "DataFine", "Durata", "TotRata", "Stato"]
    widths = [30, 25, 25, 15, 25, 20]

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, safe_text(f"Contratti Cliente: {rag_soc}"), ln=1, align="C")
    pdf.set_font("Arial", "B", 10)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, safe_text(h), 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("Arial", "", 9)
    for _, r in disp.iterrows():
        stato = str(r.get("Stato", "")).lower()
        for i, h in enumerate(headers):
            if stato == "chiuso":
                pdf.set_fill_color(255, 235, 238)
                pdf.cell(widths[i], 7, safe_text(r.get(h, "")), 1, 0, "C", fill=True)
            else:
                pdf.cell(widths[i], 7, safe_text(r.get(h, "")), 1, 0, "C")
        pdf.ln()

    return pdf.output(dest="S").encode("latin-1", errors="replace")
