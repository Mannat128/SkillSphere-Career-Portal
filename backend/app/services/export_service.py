import io
from sqlalchemy.orm import Session
import openpyxl
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.resume import Resume

class ExportService:
    @staticmethod
    def generate_excel_report(db: Session) -> io.BytesIO:
        wb = openpyxl.Workbook()

        # Sheet 1: Summary
        ws_summary = wb.active
        ws_summary.title = "Platform Summary"
        ws_summary.append(["SkillSphere Platform Executive Report"])
        ws_summary.append([])
        ws_summary.append(["Metric", "Count"])
        ws_summary.append(["Total Users", db.query(User).count()])
        ws_summary.append(["Total Jobs Posted", db.query(Job).count()])
        ws_summary.append(["Total Applications", db.query(Application).count()])
        ws_summary.append(["Total Resumes Uploaded", db.query(Resume).count()])

        # Sheet 2: Users
        ws_users = wb.create_sheet(title="Users")
        ws_users.append(["ID", "Full Name", "Email", "Role", "Active", "Verified", "Created At"])
        users = db.query(User).all()
        for u in users:
            ws_users.append([u.id, u.full_name, u.email, u.role.value, u.is_active, u.is_verified, str(u.created_at)])

        # Sheet 3: Jobs
        ws_jobs = wb.create_sheet(title="Jobs")
        ws_jobs.append(["ID", "Title", "Company", "Location", "Status", "Total Applications"])
        jobs = db.query(Job).all()
        for j in jobs:
            ws_jobs.append([
                j.id,
                j.title,
                j.company.name if j.company else "",
                j.location,
                j.status.value,
                len(j.applications)
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def generate_pdf_report(db: Session) -> io.BytesIO:
        output = io.BytesIO()
        p = canvas.Canvas(output, pagesize=letter)
        p.setTitle("SkillSphere Platform Analytics Report")

        # Header
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, 750, "SkillSphere – Career & Job Portal")
        p.setFont("Helvetica", 12)
        p.drawString(50, 730, "Platform Summary & Analytics Executive Report")
        p.line(50, 720, 560, 720)

        # Statistics
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, 690, "Key Metrics")

        p.setFont("Helvetica", 11)
        metrics = [
            f"Total Registered Users: {db.query(User).count()}",
            f"Total Active Jobs: {db.query(Job).filter(Job.status == 'PUBLISHED').count()}",
            f"Total Applications Submitted: {db.query(Application).count()}",
            f"Total Resumes Processed: {db.query(Resume).count()}",
        ]

        y = 665
        for m in metrics:
            p.drawString(70, y, f"• {m}")
            y -= 25

        y -= 20
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Recent Job Postings")
        y -= 25

        p.setFont("Helvetica", 10)
        jobs = db.query(Job).order_by(Job.created_at.desc()).limit(10).all()
        if jobs:
            for j in jobs:
                comp_name = j.company.name if j.company else "SkillSphere Partner"
                p.drawString(70, y, f"- {j.title} at {comp_name} ({j.location}) – Status: {j.status.value}")
                y -= 20
        else:
            p.drawString(70, y, "No job postings recorded in database yet.")

        p.showPage()
        p.save()
        output.seek(0)
        return output
