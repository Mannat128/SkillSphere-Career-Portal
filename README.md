# SkillSphere – Career & Job Portal

SkillSphere is a full-stack career and recruitment platform designed to connect Candidates, Recruiters, and Platform Administrators through a unified hiring ecosystem.

The platform provides job discovery, candidate profile management, resume processing, recruiter-controlled assessments, applicant tracking, and administrative management.

---

## Table of Contents

- Overview
- Design System
- Key Features
- Platform Modules
- Recruiter Assessment System
- Technology Stack
- Project Structure
- Installation & Setup
- Running the Application
- API Documentation
- Testing
- Security & Privacy
- Future Enhancements

---

## Overview

SkillSphere provides three major user roles:

- **Candidates:** Create profiles, upload resumes, explore jobs, apply for positions, and complete assigned assessments.
- **Recruiters:** Manage company profiles, publish jobs, evaluate applicants, create technical assessments, and schedule interviews.
- **Platform Administrators:** Manage users, verify recruiters, moderate jobs, and monitor platform activity.

The application follows a modular architecture with a React frontend, FastAPI backend, and MySQL database.

---

## Design System

SkillSphere uses a consistent visual design system.

| Token | Name | HEX |
|---|---|---|
| Primary | Powder Blue | `#8DB9F0` |
| Primary Light | Soft Sky Blue | `#EBF3FC` |
| Primary Dark | Deep Slate Blue | `#2B5890` |
| Background | Lavender White | `#E9E8F8` |
| Accent | Warm Sunset Peach | `#F5B69E` |
| Text Primary | Dark Slate Navy | `#1E293B` |
| Card Surface | Pure White | `#FFFFFF` |

---

## Key Features

### Candidate Features

- Candidate registration and authentication.
- Profile creation and management.
- Profile completion tracking.
- Profile picture upload.
- Resume upload and management.
- Resume text extraction using PyMuPDF.
- OCR fallback for scanned documents.
- Extracted resume information and skill analysis.
- Job exploration and keyword search.
- Job application management.
- Saved jobs.
- Application status tracking.
- Resume builder.
- Assigned technical assessments.
- Assessment results and scorecards.
- Mock interview practice.
- Skill gap analysis.

### Recruiter Features

- Recruiter registration and authentication.
- Company profile management.
- Recruiter verification workflow.
- Job creation, editing, and publishing.
- Applicant pipeline management.
- Candidate comparison.
- Recruiter-owned question bank.
- Bulk question upload through CSV and Excel.
- First-round assessment configuration.
- Assessment assignment for shortlisted candidates.
- Assessment results and candidate evaluation.
- Interview scheduling.

### Administrator Features

- Platform overview dashboard.
- User management.
- Recruiter verification.
- Job moderation.
- Reports and analytics.
- Audit log monitoring.
- Shared question bank management.

---

## Recruiter-Controlled First-Round Assessment System

SkillSphere includes a recruiter-controlled MCQ assessment workflow for initial candidate screening.

### 1. Question Bank

Recruiters can create technical MCQs using three methods:

**Manual Question Creation**
- Question text.
- Four options (A, B, C, D).
- Correct answer.
- Category or technology.
- Difficulty level.
- Marks.
- Optional explanation.

**Bulk Upload**
- CSV and Excel file support.
- Downloadable CSV template.
- Pre-import validation.
- Duplicate detection.
- Row-level error reporting.
- Import confirmation.

**Question Bank Selection**
- Search questions by keyword.
- Filter by category and difficulty.
- Select questions from authorized sources.
- Preview question details.
- Manage personal questions.

### 2. Job Assessment Configuration

Recruiters can configure assessments while creating or editing jobs.

Configuration options include:

- Enable or disable assessment.
- Assessment title and instructions.
- Total number of questions.
- Duration in minutes.
- Total marks.
- Passing marks.
- Qualification criteria (`>` or `>=`).
- Optional negative marking.
- Difficulty distribution.
- Random or specific question selection.
- Assessment preview.

### 3. Automated Assessment Assignment

When a candidate is moved to `SHORTLISTED`, the configured assessment can be assigned automatically.

The system supports:
- Automatic assessment assignment.
- Duplicate assignment prevention.
- Randomized question order.
- Randomized answer option order.
- Server-side correct-answer protection.

### 4. Candidate Assessment Experience

Candidates receive a focused assessment interface with:

- Question navigation palette.
- Countdown timer based on backend expiry time.
- Automatic answer synchronization.
- Mark-for-review functionality.
- Answered, unanswered, and review indicators.
- Submission confirmation.
- Automatic submission after expiry.
- Single-attempt enforcement.

### 5. Assessment Evaluation

After submission, the system evaluates the assessment and generates a scorecard containing:

- Marks obtained.
- Total marks.
- Percentage.
- Correct answers.
- Incorrect answers.
- Unanswered questions.
- Qualification result.

Recruiters can review assessment results and question-level performance.

---

## Technology Stack

### Backend

- Python 3.14+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- Pydantic V2
- PyMySQL
- PyMuPDF
- EasyOCR / OCR processing

### Frontend

- React 18
- Vite
- React Router DOM
- Axios
- Lucide React
- Recharts
- CSS

### Database

- MySQL
- Database: `skillsphere_portal`

### Supporting Libraries

- Pillow
- OpenPyXL
- ReportLab
- Python-dotenv

---

## Project Structure

```text
SkillSphere-Project/
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   │
│   ├── alembic/
│   │   └── versions/
│   │
│   ├── tests/
│   ├── .env.example
│   ├── alembic.ini
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── pages/
│   │   │   ├── admin/
│   │   │   ├── auth/
│   │   │   ├── candidate/
│   │   │   └── recruiter/
│   │   ├── services/
│   │   ├── styles/
│   │   └── App.jsx
│   │
│   ├── .env.example
│   └── package.json
│
├── .gitignore
├── README.md
├── package.json
└── package-lock.json
```

---

## Installation & Setup

### Prerequisites

Install the following software:

- Python 3.14 or compatible version.
- Node.js and npm.
- MySQL Server.
- Git.

### 1. Clone the Repository

```bash
git clone YOUR_REPOSITORY_URL
cd SkillSphere-Career-Portal
```

### 2. Backend Setup

Open a terminal in the project root:

```powershell
cd backend
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
python -m pip install -r requirements.txt
```

### 3. Backend Environment Configuration

Create a local `.env` file inside the `backend` directory using `backend/.env.example` as the template.

Configure your local MySQL connection and application settings.

Example configuration:

```env
APP_ENV=development
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=skillsphere_portal
DATABASE_USER=YOUR_MYSQL_USERNAME
DATABASE_PASSWORD=YOUR_MYSQL_PASSWORD

SECRET_KEY=YOUR_SECURE_SECRET_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

Use your own secure credentials. Never commit the actual `.env` file.

### 4. Database Setup

Ensure MySQL Server is running.

Create the database:

```sql
CREATE DATABASE skillsphere_portal;
```

Configure the database credentials in `backend/.env`.

Apply migrations if supported by the project setup:

```powershell
alembic upgrade head
```

### 5. Start Backend Server

From the `backend` directory:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend URL:

`http://127.0.0.1:8000`

### 6. Frontend Setup

Open a separate terminal:

```powershell
cd frontend
npm install
```

Create a local frontend `.env` file only if required by the frontend configuration. Refer to `frontend/.env.example`.

Start the frontend:

```powershell
npm run dev
```

Frontend URL:

`http://localhost:5173`

---

## API Documentation

FastAPI provides interactive API documentation.

| Documentation | URL |
|---|---|
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |
| Backend Health | `http://127.0.0.1:8000/health` |

Use Swagger UI or Postman to test the backend APIs.

---

## Testing

### Backend Tests

From the backend directory:

```powershell
python -m pytest
```

### Frontend Production Build

From the frontend directory:

```powershell
npm run build
```

Testing should be performed in the local development environment with the required dependencies and database configured.

---

## Security & Privacy

SkillSphere follows basic security and privacy practices:

- Environment variables are stored locally.
- Secret keys and passwords must not be committed.
- `.env` files are excluded through `.gitignore`.
- Uploaded documents and private user files are excluded from version control.
- Authentication and role-based access control protect platform resources.
- Candidate assessment answers are evaluated on the backend.
- Correct assessment answers must not be exposed through candidate-facing APIs.

Never publish:
- Database credentials.
- JWT secret keys.
- Admin passwords.
- AI provider API keys.
- SMTP credentials.
- Candidate resumes or personal documents.
- Private user information.

---

## Future Enhancements

Potential future improvements include:

- Advanced AI-based candidate-job matching.
- Enhanced resume analysis.
- Advanced recruitment analytics.
- Additional assessment question types.
- Improved interview evaluation workflows.
- Deployment and production monitoring.

---

## Project Status

SkillSphere is under active development. Features and integrations may evolve as development and testing continue.

---

**SkillSphere – Connecting Talent with Opportunity.**
```

---

### Ab tum ye karo

1. Root `README.md` open karo.
2. Existing complete content delete karo.
3. Upar wala complete README paste karo.
4. `Ctrl + S` press karke save karo.

<text color="success" weight="medium" size="sm">README ready for the next security review.</text>