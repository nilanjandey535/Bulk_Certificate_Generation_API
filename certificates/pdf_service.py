
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas


def generate_certificate_pdf(recipient):
    """
    Generate a landscape PDF certificate and save it
    inside the project's private storage directory.
    """

    course_name = recipient.metadata.get(
        "course_name", "Course Completion"
    )

    completion_date = recipient.metadata.get(
        "completion_date",
        timezone.localdate().strftime("%d %B %Y"),
    )

    organization_name = recipient.metadata.get(
        "organization_name", "Demo Learning Institute"
    )

    # Generate the PDF in memory.
    buffer = BytesIO()
    page_width, page_height = landscape(A4)

    pdf = canvas.Canvas(
        buffer,
        pagesize=(page_width, page_height),
    )

    # Background.
    pdf.setFillColor(colors.HexColor("#FFFDF8"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    # Decorative gold borders.
    gold = colors.HexColor("#B39450")

    pdf.setStrokeColor(gold)
    pdf.setLineWidth(4)
    pdf.rect(
        25, 25,
        page_width - 50,
        page_height - 50,
        fill=0,
        stroke=1,
    )

    pdf.setLineWidth(1)
    pdf.rect(
        34, 34,
        page_width - 68,
        page_height - 68,
        fill=0,
        stroke=1,
    )

    center_x = page_width / 2

    # Organization name.
    pdf.setFillColor(colors.HexColor("#8B7137"))
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawCentredString(
        center_x,
        page_height - 105,
        organization_name[:100],
    )

    # Main heading.
    pdf.setFillColor(colors.HexColor("#252525"))
    pdf.setFont("Times-Bold", 34)
    pdf.drawCentredString(
        center_x,
        page_height - 160,
        "CERTIFICATE",
    )

    pdf.setFont("Helvetica", 14)
    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.drawCentredString(
        center_x,
        page_height - 188,
        "OF ACHIEVEMENT",
    )

    pdf.setFont("Times-Roman", 14)
    pdf.drawCentredString(
        center_x,
        page_height - 230,
        "This certificate is proudly presented to",
    )

    # Recipient name.
    pdf.setFillColor(colors.HexColor("#9B7830"))
    pdf.setFont("Times-Bold", 29)
    pdf.drawCentredString(
        center_x,
        page_height - 275,
        recipient.recipient_name[:80],
    )

    # Course information.
    pdf.setFillColor(colors.HexColor("#333333"))
    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(
        center_x,
        page_height - 315,
        "for successfully completing",
    )

    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawCentredString(
        center_x,
        page_height - 345,
        course_name[:100],
    )

    # Completion date.
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawCentredString(
        center_x,
        page_height - 375,
        f"Completion Date: {completion_date[:50]}",
    )

    # Certificate ID.
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(
        center_x,
        95,
        f"Certificate ID: {recipient.id}",
    )

    # Signature line.
    pdf.setStrokeColor(colors.HexColor("#888888"))
    pdf.line(center_x - 100, 70, center_x + 100, 70)

    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(
        center_x,
        55,
        "Authorized Signature",
    )

    pdf.showPage()
    pdf.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Save under private storage.
    relative_key = (
        f"certificates/{recipient.job_id}/{recipient.id}.pdf"
    )

    storage_root = Path(
        settings.CERTIFICATE_STORAGE_ROOT
    ).resolve()

    destination = (storage_root / relative_key).resolve()

    # Prevent paths from escaping the storage directory.
    if not destination.is_relative_to(storage_root):
        raise ValueError("Invalid certificate storage path.")

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_bytes(pdf_bytes)

    return relative_key
