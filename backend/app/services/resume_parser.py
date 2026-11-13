import re
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.models.skill import Skill

class ResumeParser:
    COMMON_DEGREES = [
        "Bachelor of Science", "B.Sc", "B.S.", "B.Tech", "Bachelor of Technology",
        "Master of Science", "M.Sc", "M.S.", "M.Tech", "Master of Technology",
        "Bachelor of Engineering", "B.E.", "Master of Engineering", "M.E.",
        "Bachelor of Computer Applications", "BCA", "MCA", "Master of Computer Applications",
        "Bachelor of Arts", "B.A.", "Master of Business Administration", "MBA", "Ph.D", "Doctorate"
    ]

    COMMON_TITLES = [
        "Software Engineer", "Full Stack Developer", "Backend Developer", "Frontend Developer",
        "Web Developer", "Data Scientist", "Data Analyst", "DevOps Engineer",
        "System Architect", "Machine Learning Engineer", "Cloud Engineer", "Technical Lead",
        "Intern", "Software Development Engineer", "Product Manager", "QA Engineer"
    ]

    @classmethod
    def parse(cls, raw_text: str, db: Optional[Session] = None) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Parse raw extracted resume text into structured fields and confidence scores.
        """
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        extracted: Dict[str, Any] = {
            "full_name": None,
            "email": None,
            "phone": None,
            "location": None,
            "skills": [],
            "educations": [],
            "experiences": [],
            "projects": [],
            "certifications": [],
            "summary": None,
        }
        confidence: Dict[str, float] = {
            "full_name": 0.0,
            "email": 0.0,
            "phone": 0.0,
            "location": 0.0,
            "skills": 0.0,
            "educations": 0.0,
            "experiences": 0.0,
        }

        if not raw_text or len(raw_text.strip()) == 0:
            return extracted, confidence

        # 1. Extract Email
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        email_matches = re.findall(email_pattern, raw_text)
        if email_matches:
            extracted["email"] = email_matches[0].lower()
            confidence["email"] = 0.95

        # 2. Extract Phone Number
        phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?\d{10,13}"
        phone_matches = re.findall(phone_pattern, raw_text)
        if phone_matches:
            # Filter matches that have at least 10 digits
            clean_phones = [p for p in phone_matches if sum(c.isdigit() for c in p) >= 10]
            if clean_phones:
                extracted["phone"] = clean_phones[0].strip()
                confidence["phone"] = 0.90

        # 3. Extract Full Name
        # Look at the first 3 non-empty lines for candidate name (excluding lines containing email/phone/urls)
        for line in lines[:5]:
            if "@" in line or "http" in line or re.search(r"\d{3}", line):
                continue
            words = line.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
                extracted["full_name"] = line
                confidence["full_name"] = 0.85
                break

        # 4. Extract Technical Skills
        # Fetch known skill dictionary from database if session provided
        skill_dict = set()
        if db:
            db_skills = db.query(Skill.name).all()
            skill_dict = {s[0] for s in db_skills}

        # Fallback known skill pool if DB is empty or not passed
        fallback_skills = {
            "Python", "Java", "JavaScript", "TypeScript", "React", "Next.js", "Vue.js",
            "Angular", "FastAPI", "Flask", "Django", "Node.js", "Express.js",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes",
            "AWS", "Azure", "Git", "HTML", "CSS", "Machine Learning", "Data Analytics",
            "C++", "C#", "Go", "Spring Boot", "REST API", "GraphQL"
        }
        all_candidate_skills = skill_dict.union(fallback_skills)

        detected_skills = []
        for skill in all_candidate_skills:
            # Word boundary regex search (case insensitive)
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, raw_text, re.IGNORECASE):
                detected_skills.append(skill)

        extracted["skills"] = sorted(list(set(detected_skills)))
        confidence["skills"] = 0.88 if extracted["skills"] else 0.0

        # 5. Extract Education
        educations = []
        for degree in cls.COMMON_DEGREES:
            pattern = r"\b" + re.escape(degree) + r"\b"
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                # Look for surrounding line to get institution and year
                pos = match.start()
                snippet = raw_text[max(0, pos - 100): min(len(raw_text), pos + 150)]
                year_match = re.search(r"\b(20\d{2}|19\d{2})\b", snippet)
                year = year_match.group(1) if year_match else None

                # Find possible college/university name
                institution = "University / College"
                inst_match = re.search(r"([A-Z][a-zA-Z\s]+(?:University|College|Institute|Academy))", snippet)
                if inst_match:
                    institution = inst_match.group(1).strip()

                educations.append({
                    "degree": degree,
                    "institution": institution,
                    "graduation_year": year
                })

        extracted["educations"] = educations[:3] # keep top distinct
        confidence["educations"] = 0.80 if educations else 0.0

        # 6. Extract Experience
        experiences = []
        for title in cls.COMMON_TITLES:
            pattern = r"\b" + re.escape(title) + r"\b"
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                pos = match.start()
                snippet = raw_text[max(0, pos - 50): min(len(raw_text), pos + 200)]
                # Look for company indicators
                company = "Organization"
                comp_match = re.search(r"at\s+([A-Z][A-Za-z0-9\s&]+?)(?:,|\.|\n|from|since)", snippet)
                if comp_match:
                    company = comp_match.group(1).strip()

                experiences.append({
                    "position": title,
                    "company": company,
                    "description": snippet.splitlines()[0] if snippet else None
                })

        extracted["experiences"] = experiences[:4]
        confidence["experiences"] = 0.75 if experiences else 0.0

        # 7. Summary / Bio
        for i, line in enumerate(lines[:10]):
            if any(k in line.lower() for k in ["summary", "profile", "about me", "objective"]):
                if i + 1 < len(lines):
                    extracted["summary"] = lines[i + 1]
                    break

        return extracted, confidence
