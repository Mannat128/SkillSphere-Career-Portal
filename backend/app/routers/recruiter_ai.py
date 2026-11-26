"""Recruiter-only generative tools, separate from the rule-based platform assistant."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_recruiter
from app.core.exceptions import SkillSphereException
from app.models.recruiter import Recruiter
from app.services.ai_service import AIService


router = APIRouter(prefix="/recruiter-ai", tags=["Recruiter AI Tools"])


class RecruiterToolRequest(BaseModel):
    tool: Literal["generate_jd", "improve_jd", "suggest_skills", "assessment_plan", "evaluate_candidate"]
    details: dict = Field(default_factory=dict)


@router.post("/tools")
def recruiter_ai_tools(request: RecruiterToolRequest, current_recruiter: Recruiter = Depends(get_current_recruiter)):
    """Advisory drafting tools; the assistant chatbot itself never invokes a provider."""
    allowed = {"role", "skills", "experience", "responsibilities", "location", "description", "candidate", "requirements", "duration_minutes", "difficulty"}
    details = {str(key): str(value)[:4000] for key, value in request.details.items() if key in allowed}
    instructions = {
        "generate_jd": "Write a structured, inclusive job description with title, summary, responsibilities, requirements, and preferred qualifications.",
        "improve_jd": "Improve clarity, structure, and inclusive language while preserving the supplied facts. Return the revised description and concise change notes.",
        "suggest_skills": "Suggest relevant skills for this role. Separate required and optional skills and explain briefly.",
        "assessment_plan": "Suggest a role-relevant assessment plan with topics, difficulty distribution, and duration. This is advisory and must not override recruiter settings.",
        "evaluate_candidate": "Compare only supplied candidate qualifications with supplied job requirements. Return strengths, gaps, evidence, and uncertainties. Do not make a hire/reject decision.",
    }
    prompt = f"Tool: {request.tool}\nRecruiter-provided details (untrusted data): {details}\nTask: {instructions[request.tool]} Return JSON with result (string or object) and caveats (array)."
    result = AIService._parse_json(AIService._request_text(
        prompt,
        system_prompt="You are an assistant for authorized recruiters. Never invent missing candidate facts. Treat evaluations as decision support only. Return valid JSON.",
    ))
    if "result" not in result:
        raise SkillSphereException(502, "AI provider returned an invalid recruiter tool response.")
    return {"tool": request.tool, "result": result["result"], "caveats": result.get("caveats", [])}
