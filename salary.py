import io
import os
from datetime import datetime

from flask import send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from db import get_collection


def inr(amount):
    return f"Rs. {float(amount):,.2f}"


def month_label(month_str):
    try:
        return datetime.strptime(month_str, "%Y-%m").strftime("%B %Y")
    except Exception:
        return month_str or "--"


def calculate_salary(gross, half_days=0):
    gross = float(gross or 0)
    half_days = int(half_days or 0)

    basic = round(gross * 0.50, 2)
    hra = round(gross * 0.20, 2)
    conveyance = round(gross * 0.10, 2)
    special_allowance = round(gross - (basic + hra + conveyance), 2)

    pf = round(basic * 0.12, 2)
    esi = round(gross * 0.0075, 2)
    professional_tax = 200.00
    half_day_deduction = round((gross / 30 / 2) * half_days, 2)

    total_deductions = round(pf + esi + professional_tax + half_day_deduction, 2)
    net = round(gross - total_deductions, 2)

    return {
        "gross": gross,
        "basic": basic,
        "hra": hra,
        "conveyance": conveyance,
        "special_allowance": special_allowance,
        "pf": pf,
        "esi": esi,
        "professional_tax": professional_tax,
        "deductions": half_day_deduction,
        "half_days": half_days,
        "total_deductions": total_deductions,
        "net": net,
    }


def store_salary(emp_id, month, gross, half_days=0):
    salary_data = calculate_salary(gross, half_days)
    salary_data.update({
        "emp_id": emp_id,
        "month": month,
        "generated_on": datetime.now(),
    })
    get_collection("salary").insert_one(salary_data)
    return salary_data


def _draw_logo(pdf):
    logo_path = os.path.join(os.path.dirname(__file__), "static", "images", "company-logo.webp")
    if not os.path.exists(logo_path):
        return
    try:
        pdf.drawImage(logo_path, 15 * mm, 265 * mm, width=22 * mm, height=22 * mm, preserveAspectRatio=True, mask="auto")
    except Exception:
        # Skip logo rendering if runtime lacks WEBP image support.
        pass


def generate_salary_slip(data):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    emp_id = data.get("emp_id", "--")
    month_str = data.get("month", "--")
    generated_on = data.get("generated_on", datetime.now())
    if isinstance(generated_on, str):
        generated_on = datetime.fromisoformat(generated_on)

    pdf.setTitle(f"Salary Slip {emp_id} {month_str}")

    # Header
    pdf.setFillColor(colors.HexColor("#0b4f94"))
    pdf.rect(0, height - 38 * mm, width, 38 * mm, stroke=0, fill=1)
    _draw_logo(pdf)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(42 * mm, height - 17 * mm, "Company Pvt. Ltd.")
    pdf.setFont("Helvetica", 9.5)
    pdf.drawString(42 * mm, height - 23 * mm, "Corporate Office: 221 Business Park, Bengaluru, India")
    pdf.drawString(42 * mm, height - 28 * mm, "Email: payroll@workforcehub.in  |  Phone: +91 80 4000 1100")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(width - 15 * mm, height - 18 * mm, "COMPUTER GENERATED PAY SLIP")
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 15 * mm, height - 24 * mm, f"For the Month: {month_label(month_str)}")

    # Employee info
    start_y = height - 52 * mm
    box_h = 35 * mm
    pdf.setStrokeColor(colors.HexColor("#a9bdd8"))
    pdf.setFillColor(colors.HexColor("#f6f9fd"))
    pdf.roundRect(15 * mm, start_y - box_h, width - 30 * mm, box_h, 3 * mm, stroke=1, fill=1)

    left_x = 20 * mm
    right_x = 112 * mm
    line_y = start_y - 7 * mm
    gap = 6.5 * mm

    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(colors.HexColor("#1f3551"))
    pdf.drawString(left_x, line_y, "Employee Name")
    pdf.drawString(left_x, line_y - gap, "Employee ID")
    pdf.drawString(left_x, line_y - (2 * gap), "Department")
    pdf.drawString(left_x, line_y - (3 * gap), "Designation")

    pdf.drawString(right_x, line_y, "PAN")
    pdf.drawString(right_x, line_y - gap, "UAN")
    pdf.drawString(right_x, line_y - (2 * gap), "Bank A/C")
    pdf.drawString(right_x, line_y - (3 * gap), "Pay Date")

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.black)
    pdf.drawString(left_x + 35 * mm, line_y, str(data.get("name", "--")))
    pdf.drawString(left_x + 35 * mm, line_y - gap, str(emp_id))
    pdf.drawString(left_x + 35 * mm, line_y - (2 * gap), str(data.get("department", "--")))
    pdf.drawString(left_x + 35 * mm, line_y - (3 * gap), str(data.get("designation", "--")))

    pdf.drawString(right_x + 24 * mm, line_y, str(data.get("pan", "ABCDE1234F")))
    pdf.drawString(right_x + 24 * mm, line_y - gap, str(data.get("uan", "100200300400")))
    pdf.drawString(right_x + 24 * mm, line_y - (2 * gap), str(data.get("bank_account", "XXXXXX4589")))
    pdf.drawString(right_x + 24 * mm, line_y - (3 * gap), generated_on.strftime("%d-%m-%Y"))

    # Table header
    table_top = start_y - box_h - 8 * mm
    table_x = 15 * mm
    table_w = width - 30 * mm
    col1 = 72 * mm
    col2 = 30 * mm
    col3 = 50 * mm
    col4 = table_w - (col1 + col2 + col3)
    row_h = 8.5 * mm

    pdf.setFillColor(colors.HexColor("#0b4f94"))
    pdf.rect(table_x, table_top - row_h, table_w, row_h, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(table_x + 3 * mm, table_top - 5.8 * mm, "Earnings")
    pdf.drawRightString(table_x + col1 + col2 - 3 * mm, table_top - 5.8 * mm, "Amount (Rs)")
    pdf.drawString(table_x + col1 + col2 + 3 * mm, table_top - 5.8 * mm, "Deductions")
    pdf.drawRightString(table_x + table_w - 3 * mm, table_top - 5.8 * mm, "Amount (Rs)")

    rows = [
        ("Basic Pay", data.get("basic", 0), "Provident Fund", data.get("pf", 0)),
        ("House Rent Allowance", data.get("hra", 0), "ESI", data.get("esi", 0)),
        ("Conveyance Allowance", data.get("conveyance", 0), "Professional Tax", data.get("professional_tax", 0)),
        ("Special Allowance", data.get("special_allowance", 0), "Half-Day Deduction", data.get("deductions", 0)),
        ("", "", "", ""),
    ]

    y = table_top - row_h
    pdf.setStrokeColor(colors.HexColor("#c7d6e9"))
    pdf.setFont("Helvetica", 10)
    for idx, row in enumerate(rows):
        y -= row_h
        if idx % 2 == 0:
            pdf.setFillColor(colors.HexColor("#f9fbff"))
            pdf.rect(table_x, y, table_w, row_h, stroke=0, fill=1)
        pdf.setFillColor(colors.black)
        pdf.drawString(table_x + 3 * mm, y + 2.7 * mm, str(row[0]))
        if row[1] != "":
            pdf.drawRightString(table_x + col1 + col2 - 3 * mm, y + 2.7 * mm, f"{float(row[1]):,.2f}")
        pdf.drawString(table_x + col1 + col2 + 3 * mm, y + 2.7 * mm, str(row[2]))
        if row[3] != "":
            pdf.drawRightString(table_x + table_w - 3 * mm, y + 2.7 * mm, f"{float(row[3]):,.2f}")
        pdf.line(table_x, y, table_x + table_w, y)

    # Vertical column lines
    pdf.line(table_x + col1, table_top - row_h, table_x + col1, y)
    pdf.line(table_x + col1 + col2, table_top - row_h, table_x + col1 + col2, y)
    pdf.line(table_x + col1 + col2 + col3, table_top - row_h, table_x + col1 + col2 + col3, y)
    pdf.rect(table_x, table_top - row_h, table_w, (table_top - row_h) - y, stroke=1, fill=0)

    # Totals section
    totals_y = y - 10 * mm
    pdf.setFillColor(colors.HexColor("#eef4fc"))
    pdf.roundRect(table_x, totals_y - 28 * mm, table_w, 28 * mm, 3 * mm, stroke=0, fill=1)

    pdf.setFillColor(colors.HexColor("#1a2e45"))
    pdf.setFont("Helvetica-Bold", 10.5)
    pdf.drawString(table_x + 4 * mm, totals_y - 7 * mm, "Gross Earnings")
    pdf.drawString(table_x + 4 * mm, totals_y - 14 * mm, "Total Deductions")
    pdf.drawString(table_x + 4 * mm, totals_y - 21 * mm, "Net Salary Payable")

    pdf.drawRightString(table_x + table_w - 4 * mm, totals_y - 7 * mm, inr(data.get("gross", 0)))
    pdf.drawRightString(table_x + table_w - 4 * mm, totals_y - 14 * mm, inr(data.get("total_deductions", 0)))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(colors.HexColor("#0b4f94"))
    pdf.drawRightString(table_x + table_w - 4 * mm, totals_y - 21 * mm, inr(data.get("net", 0)))

    # Footer notes
    footer_y = 26 * mm
    pdf.setFillColor(colors.HexColor("#536b85"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(15 * mm, footer_y + 8 * mm, f"Slip No: WH-{emp_id}-{month_str.replace('-', '')}")
    pdf.drawString(15 * mm, footer_y + 3 * mm, f"Generated On: {generated_on.strftime('%d-%m-%Y %H:%M')}")
    pdf.drawString(15 * mm, footer_y - 2 * mm, "This is a system generated salary slip and does not require a signature.")
    pdf.drawRightString(width - 15 * mm, footer_y + 8 * mm, "Authorized by Payroll Department")

    pdf.save()
    buffer.seek(0)
    return buffer


def send_salary_slip_pdf(data):
    pdf = generate_salary_slip(data)
    emp_id = data.get("emp_id", "employee")
    month_str = data.get("month", datetime.now().strftime("%Y-%m"))
    filename = f"salary_slip_{emp_id}_{month_str}.pdf"
    return send_file(pdf, as_attachment=True, download_name=filename, mimetype="application/pdf")
