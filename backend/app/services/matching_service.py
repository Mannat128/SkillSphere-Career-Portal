from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session
from app.models.job import Job
from app.models.resume import Resume, ResumeAnalysis

class MatchingService:
    @staticmethod
    def calculate_match(
        candidate_skills: List[str],
        job_required_skills: List[str],
        job_description: str = ""
    ) -> Dict[str, Any]:
        """
        Calculates transparent match score and skill gaps between a candidate and a job.
        """
        cand_set: Set[str] = {s.strip().lower() for s in candidate_skills if s}
        req_set: Set[str] = {s.strip().lower() for s in job_required_skills if s}

        # If job has explicit required skills
        if req_set:
            matched_set = cand_set.intersection(req_set)
            missing_set = req_set.difference(cand_set)

            # Preserve original casing
            matched_skills = [s for s in job_required_skills if s.strip().lower() in matched_set]
            missing_skills = [s for s in job_required_skills if s.strip().lower() in missing_set]

            # Transparent formula: 85% weight on required skills + 15% on additional tech relevance
            base_score = (len(matched_set) / float(len(req_set))) * 85.0
            bonus = min(15.0, (len(cand_set) - len(matched_set)) * 2.5) if len(cand_set) > len(matched_set) else 0.0
            match_score = round(min(100.0, base_score + bonus), 1)

            explanation = (
                f"Candidate matches {len(matched_set)} of {len(req_set)} explicitly required job skills "
                f"({round((len(matched_set)/len(req_set))*100, 1)}% core requirement match). "
                f"Added {round(bonus, 1)}% bonus for {len(cand_set) - len(matched_set)} complementary technical skills."
            )
        else:
            # Fallback when job has no tagged skills: look for candidate skills mentioned in description
            matched = []
            for skill in candidate_skills:
                if skill.lower() in job_description.lower():
                    matched.append(skill)
            matched_skills = matched
            missing_skills = []
            match_score = min(90.0, max(40.0, len(matched) * 15.0)) if matched else 50.0
            explanation = (
                f"Job description contains references to {len(matched_skills)} of candidate's technical skills."
            )

        # Recommendations based on missing skills
        if missing_skills:
            recommendations = (
                f"To strengthen candidacy for this position, focus on mastering the missing core requirements: "
                f"{', '.join(missing_skills)}. Consider taking technical assessments or completing hands-on projects with these technologies."
            )
        else:
            recommendations = (
                "Excellent match! Candidate profile satisfies all required technologies for this role."
            )

        return {
            "match_score": match_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "explanation": explanation,
            "recommendations": recommendations,
        }

    @classmethod
    def analyze_resume_for_job(cls, db: Session, resume_id: int, job_id: int) -> Dict[str, Any]:
        """Performs analysis, stores/updates record in database, and returns analysis object."""
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()

        if not resume or not job:
            raise ValueError("Resume or Job record not found")

        # Gather candidate skills: from candidate profile and OCR result
        candidate_skills = []
        if resume.candidate and resume.candidate.skills:
            candidate_skills.extend([cs.skill.name for cs in resume.candidate.skills if cs.skill])

        if resume.ocr_result and resume.ocr_result.extracted_data:
            ocr_skills = resume.ocr_result.extracted_data.get("skills", [])
            candidate_skills.extend(ocr_skills)

        # Deduplicate
        candidate_skills = sorted(list(set(candidate_skills)))

        # Gather job skills
        job_skills = [js.skill.name for js in job.required_skills if js.skill]

        result = cls.calculate_match(candidate_skills, job_skills, job.description)

        # Check existing analysis
        analysis = db.query(ResumeAnalysis).filter(
            ResumeAnalysis.resume_id == resume_id,
            ResumeAnalysis.job_id == job_id
        ).first()

        if not analysis:
            analysis = ResumeAnalysis(
                resume_id=resume_id,
                job_id=job_id,
                match_score=result["match_score"],
                matched_skills=result["matched_skills"],
                missing_skills=result["missing_skills"],
                recommendations=result["recommendations"],
                explanation=result["explanation"],
            )
            db.add(analysis)
        else:
            analysis.match_score = result["match_score"]
            analysis.matched_skills = result["matched_skills"]
            analysis.missing_skills = result["missing_skills"]
            analysis.recommendations = result["recommendations"]
            analysis.explanation = result["explanation"]

        db.commit()
        db.refresh(analysis)

        return {
            "id": analysis.id,
            "resume_id": resume_id,
            "job_id": job_id,
            "job_title": job.title,
            "company_name": job.company.name if job.company else "SkillSphere Partner",
            "match_score": analysis.match_score,
            "matched_skills": analysis.matched_skills,
            "missing_skills": analysis.missing_skills,
            "recommendations": analysis.recommendations,
            "explanation": analysis.explanation,
        }
