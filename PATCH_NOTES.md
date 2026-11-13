# SkillSphere update notes

This update is based on the latest SkillSphere source package supplied on 12 November 2026.

## Frontend updates included

- Candidate profile is wired to the backend's profile, completion, avatar, visibility, career preference, alert preference, education, experience, skills, projects and certification routes.
- Candidate dashboard uses live profile completion, applications, saved jobs, assigned assessments and published jobs. Empty states remain empty.
- Candidate applications page reads the backend application status/date fields and uses the actual withdraw endpoint.
- Explore Jobs now sends the backend-supported `keyword` search parameter (instead of the unsupported `query` parameter); pagination response handling uses `items`.
- Resume Management now reads the backend's actual `original_filename`, `file_name`, `upload_date` and `ocr_status` fields. It loads extracted OCR data from the per-resume endpoint, displays actual extracted skills, sends the required `{ apply_to_profile: true }` body when syncing, and downloads through the authenticated API client.
- Resume Builder now reads `experiences` and `educations` as returned by the API, uses the backend's `position` and `graduation_year` fields, and removes fabricated example name, phone, job title, institution and date values.
- Recruiter dashboard, jobs, company profile, applicant pipeline, candidate comparison, question bank, assessment results and interview scheduling are connected to their corresponding backend routes.
- Admin dashboard supports overview, user management, recruiter verification, job moderation, reports and audit logs.
- Dashboard shell styling uses the approved Midnight `#08090B`, Ivory `#FAF8F3` and Neon Lime `#CDF22B` palette.

## Packaging and safety

- `.env` files and secrets are excluded. Keep your existing local `.env` files unchanged.
- `node_modules`, Python virtual environments, caches, generated `dist` output and uploaded user documents are excluded.
- No database migrations or database records are changed by this frontend update.
- Backend source is included unchanged from the supplied project.

## Verification completed in this environment

- Babel JSX/JavaScript parser scan: 34 files parsed, 0 syntax errors.
- Python compile scan: 0 syntax errors.
- Static review confirmed the frontend request/response corrections listed above against the backend route and Pydantic schema definitions.
- A full Vite production build could not be run in this Linux environment because the available `node_modules` contains Windows-native Rollup/esbuild binaries. Run `npm run build` on the Windows development machine after applying the package.
- End-to-end verification against the local MySQL database and configured `.env` is still required. Do not treat API functionality as fully E2E-tested until that is run.
