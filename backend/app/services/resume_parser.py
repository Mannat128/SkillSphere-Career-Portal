import re
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlsplit
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

    @staticmethod
    def _urls(text: str) -> List[str]:
        found = re.findall(r"(?:https?://|www\.)[^\s<>()]+|(?<![@\w])(?:linkedin|github)\.com/[^\s<>()]+", text, re.I)
        normalized = []
        for value in found:
            value = value.rstrip(".,;:)")
            if value.lower().startswith("www.") or "://" not in value:
                value = "https://" + value
            parsed = urlsplit(value)
            if parsed.scheme in {"http", "https"} and parsed.hostname:
                normalized.append(value)
        return list(dict.fromkeys(normalized))

    @classmethod
    def _extract_projects(cls, lines: List[str], all_urls: List[str]) -> List[Dict[str, Any]]:
        start = next((i for i, line in enumerate(lines) if re.fullmatch(r"(?:selected |personal )?projects?\s*:??", line, re.I)), None)
        if start is None:
            return []
        stop = re.compile(r"^(?:education|experience|work experience|employment|skills|technical skills|certifications?|achievements|publications|summary|profile)\s*:?$", re.I)
        section = []
        for line in lines[start + 1:]:
            if stop.fullmatch(line):
                break
            section.append(line)
        if not section:
            return []

        blocks: List[List[str]] = []
        for line in section:
            if re.match(r"^(?:[-*•▪]|\d+[.)])\s+", line):
                blocks.append([re.sub(r"^(?:[-*•▪]|\d+[.)])\s+", "", line)])
            elif blocks:
                blocks[-1].append(line)
            else:
                blocks.append([line])

        projects = []
        for block in blocks[:20]:
            joined = " ".join(block).strip()
            if not joined:
                continue
            title_line = block[0]
            split_title = re.split(r"\s+[|–—-]\s+", title_line, maxsplit=1)
            title = split_title[0].strip()
            if not title or len(title) > 200:
                continue
            urls = [url for url in all_urls if url in joined]
            description_parts = block[1:]
            if len(split_title) > 1:
                description_parts.insert(0, split_title[1])
            projects.append({
                "title": title,
                "description": " ".join(description_parts).strip() or None,
                "technologies": None,
                "start_date": None,
                "end_date": None,
                "project_url": next((url for url in urls if "github.com" not in url.lower()), None),
                "github_url": next((url for url in urls if "github.com" in url.lower()), None),
                "image_url": None,
            })
        return projects

    @staticmethod
    def is_probable_person_name(value: Any) -> bool:
        """Reject section labels and contact lines before exposing a parsed name."""
        if not isinstance(value, str):
            return False
        candidate = value.strip()
        labelled = re.match(r"(?i)^(?:full\s+name|name)\s*[:\-]\s*(.+)$", candidate)
        if labelled:
            candidate = labelled.group(1).strip()
        if not candidate or re.search(r"[@\d:/\\]|https?", candidate, re.I):
            return False
        normalized = " ".join(re.findall(r"[a-z]+", candidate.casefold()))
        excluded_headings = {
            "professional summary", "summary", "profile", "profile summary",
            "career summary", "career objective", "objective", "experience",
            "work experience", "employment history", "education", "skills",
            "technical skills", "core skills", "projects", "certifications",
            "contact", "contact information", "resume", "curriculum vitae",
        }
        if normalized in excluded_headings:
            return False
        words = candidate.split()
        return (
            2 <= len(words) <= 4
            and all(word[0].isalpha() and word[0].isupper() for word in words)
            and all(any(character.isalpha() for character in word) for word in words)
        )

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
            "headline": None,
            "linkedin_url": None,
            "github_url": None,
            "portfolio_url": None,
            "additional_url": None,
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
            "projects": 0.0,
            "certifications": 0.0,
            "linkedin_url": 0.0,
            "github_url": 0.0,
            "portfolio_url": 0.0,
            "additional_url": 0.0,
            "headline": 0.0,
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

        urls = cls._urls(raw_text)
        for url in urls:
            host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
            if host.endswith("linkedin.com") and not extracted["linkedin_url"]:
                extracted["linkedin_url"] = url
                confidence["linkedin_url"] = 0.95
            elif host.endswith("github.com") and not extracted["github_url"]:
                extracted["github_url"] = url
                confidence["github_url"] = 0.95
            elif not extracted["portfolio_url"]:
                extracted["portfolio_url"] = url
                confidence["portfolio_url"] = 0.8
            elif not extracted["additional_url"]:
                extracted["additional_url"] = url
                confidence["additional_url"] = 0.6

        location_match = re.search(r"(?im)^(?:location|based in|address)\s*[:|\-]\s*(.{2,100})$", raw_text)
        if location_match:
            extracted["location"] = location_match.group(1).strip()
            confidence["location"] = 0.8

        # 3. Extract Full Name. Ignore section headings (including all-caps
        # headings) and accept explicitly labelled names after removing the label.
        for line in lines[:8]:
            labelled = re.match(r"(?i)^(?:full\s+name|name)\s*[:\-]\s*(.+)$", line)
            candidate = labelled.group(1).strip() if labelled else line
            if "@" in candidate or "http" in candidate.lower() or re.search(r"\d{3}", candidate):
                continue
            if cls.is_probable_person_name(candidate):
                extracted["full_name"] = candidate
                confidence["full_name"] = 0.85
                break

        if extracted["full_name"]:
            name_index = next((i for i, line in enumerate(lines[:5]) if line == extracted["full_name"]), None)
            if name_index is not None:
                for line in lines[name_index + 1:name_index + 4]:
                    if "@" in line or "http" in line.lower() or re.search(r"\d{7}", line):
                        continue
                    if len(line) <= 120 and not re.match(r"^(?:summary|profile|experience|education|skills|projects)\b", line, re.I):
                        extracted["headline"] = line
                        confidence["headline"] = 0.55
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
                institution = None
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
                company = None
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

        extracted["projects"] = cls._extract_projects(lines, urls)
        confidence["projects"] = 0.7 if extracted["projects"] else 0.0

        certification_lines = []
        in_certifications = False
        for line in lines:
            if re.fullmatch(r"(?:certifications?|licenses?)\s*:?", line, re.I):
                in_certifications = True
                continue
            if in_certifications and re.fullmatch(r"(?:education|experience|projects?|skills|achievements|publications|summary)\s*:?", line, re.I):
                break
            if in_certifications and line:
                certification_lines.append(line.lstrip("-•* "))
        extracted["certifications"] = list(dict.fromkeys(certification_lines[:20]))
        confidence["certifications"] = 0.7 if certification_lines else 0.0

        # 7. Summary / Bio
        for i, line in enumerate(lines[:10]):
            if any(k in line.lower() for k in ["summary", "profile", "about me", "objective"]):
                if i + 1 < len(lines):
                    extracted["summary"] = lines[i + 1]
                    break

        return extracted, confidence
