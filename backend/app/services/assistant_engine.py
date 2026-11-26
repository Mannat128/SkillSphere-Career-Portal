"""Local multilingual SkillSphere Assistant; no model or translation service calls."""

from __future__ import annotations

from datetime import datetime
import hashlib
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatusEnum
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job import Job, JobStatusEnum
from app.models.recruiter import Recruiter
from app.models.recruiter_assessment import AssessmentAssignment
from app.models.sphera import AssistantKnowledgeSuggestion, AssistantUnansweredQuestion
from app.models.user import User, UserRole
from app.services.assistant_company_catalog import catalog_options, format_catalog_reply, lookup_catalog
from app.services.assistant_knowledge import (
    answer_website_help,
    detect_language,
    match_intent,
    normalize_text,
    route_for_path,
    TOPICS,
)


LANGUAGES = {"auto", "en", "hi", "hinglish", "hi_latn", "pa", "pa_latn"}
CONFIDENCE_THRESHOLD = 0.70
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b(password|passwd|passcode|otp|one[- ]time(?: password)? code|"
    r"api[_ -]?key|secret(?: key)?|access[_ -]?token|refresh[_ -]?token|"
    r"auth(?:entication)? token)\b\s*(?:is\s*)?[:=]\s*[\"']?([^\s,;]+)"
)
_FINANCIAL_SECRET_PATTERN = re.compile(
    r"(?i)\b(credit card(?: number)?|card number|bank account(?: number)?|"
    r"account number|routing number)\b\s*(?:is\s*)?[:=]\s*[\"']?([^\s,;]+)"
)
_PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d(). -]{6,}\d(?!\w)")
_CARD_NUMBER_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_TOKEN_PATTERN = re.compile(
    r"(?i)\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{16,}|"
    r"AKIA[A-Z0-9]{16})\b"
)
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)


def role_name(user: Optional[User]) -> str:
    if user is None:
        return "visitor"
    return {
        UserRole.CANDIDATE: "candidate",
        UserRole.RECRUITER: "recruiter",
        UserRole.ADMIN: "admin",
    }.get(user.role, "visitor")


def redact_sensitive_data(text: str) -> str:
    """Redact common secrets before persistence; this is heuristic, not exhaustive."""
    result = str(text or "")
    result = _PRIVATE_KEY_PATTERN.sub("[REDACTED_PRIVATE_KEY]", result)
    result = _BEARER_PATTERN.sub("Bearer [REDACTED]", result)
    result = _CREDENTIAL_PATTERN.sub(lambda match: f"{match.group(1)}: [REDACTED]", result)
    result = _FINANCIAL_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}: [REDACTED]", result)
    result = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", result)
    result = _TOKEN_PATTERN.sub("[REDACTED_API_KEY]", result)
    result = _CARD_NUMBER_PATTERN.sub("[REDACTED_CARD_NUMBER]", result)

    def redact_phone(match):
        candidate = match.group(0)
        digits = re.sub(r"\D", "", candidate)
        has_phone_format = candidate.startswith("+") or any(char in candidate for char in " ()-.")
        if 8 <= len(digits) <= 15 and (len(digits) >= 10 or has_phone_format):
            return "[REDACTED_PHONE]"
        return candidate

    return _PHONE_PATTERN.sub(redact_phone, result)


def _privacy_redact(text: str) -> str:
    return normalize_text(redact_sensitive_data(text))[:500]


def record_unanswered(db: Session, text: str, language: str, match: dict) -> None:
    """Store only a redacted normalized question and aggregate identical queries."""
    if db is None:
        return
    query = _privacy_redact(text)
    if not query:
        return
    digest = hashlib.sha256(f"{language}:{query}".encode("utf-8")).hexdigest()
    row = db.query(AssistantUnansweredQuestion).filter_by(
        query_hash=digest, language=language
    ).first()
    now = datetime.utcnow()
    if row:
        row.frequency += 1
        row.last_seen_at = now
        row.match_score = max(row.match_score, float(match.get("confidence", 0)))
    else:
        db.add(AssistantUnansweredQuestion(
            query_hash=digest,
            normalized_query=query,
            language=language,
            best_intent=match.get("intent"),
            match_score=float(match.get("confidence", 0)),
            frequency=1,
            created_at=now,
            last_seen_at=now,
        ))


def _language_response(code: str, key: str) -> str:
    strings = {
        "en": {
            "greeting": "Hello! I’m the SkillSphere Assistant. I can guide you through the platform and verified SkillSphere jobs.",
            "goodbye": "Goodbye. I’m here if you need help with SkillSphere later.",
            "thanks": "You’re welcome!",
            "unknown": "I don’t have verified information for that yet. You can rephrase it or choose a topic below.",
            "clarify": "I found more than one likely topic. Are you asking about your profile, resume, applications, or assessments?",
            "about": "SkillSphere is a career and job portal. Visitors can browse published jobs and create an account; candidates manage profiles and applications; recruiters manage their own jobs and applicant workflow.",
            "services": "SkillSphere includes candidate profiles, resume upload and builder tools, published job search, applications, assessments, interview practice, recruiter job and applicant tools, and support. Availability depends on your account role.",
            "contact": "For account-specific help, sign in and use the Support Center. I don’t have a verified public phone number or office address to share.",
            "register": "Choose Create Account and follow the registration form. Select the account type that matches your role.",
            "login": "Use Sign In with your registered email and password. Never share your password or one-time codes in chat.",
            "pricing": "I don’t have verified SkillSphere pricing information available.",
            "hours": "I don’t have verified support operating hours available. Use the Support Center to submit a request.",
            "privacy": "Your signed-in chat history is private to your account. Don’t send passwords, OTPs, payment data, or unnecessary sensitive information in chat.",
            "language": "Choose a reply language from the language menu. Auto detects English, Hindi, Hinglish, Punjabi, and Roman Punjabi from your message.",
        },
        "hi": {
            "greeting": "नमस्ते! मैं SkillSphere Assistant हूँ। मैं प्लेटफ़ॉर्म और सत्यापित SkillSphere नौकरियों के बारे में मार्गदर्शन कर सकता हूँ।",
            "goodbye": "अलविदा। SkillSphere के लिए मदद चाहिए तो फिर पूछें।",
            "thanks": "आपका स्वागत है!",
            "unknown": "इसका सत्यापित उत्तर अभी मेरे पास नहीं है। आप प्रश्न दूसरे तरीके से पूछ सकते हैं या नीचे कोई विषय चुन सकते हैं।",
            "clarify": "एक से अधिक विषय मिल रहे हैं। क्या आप profile, resume, applications या assessments के बारे में पूछ रहे हैं?",
            "about": "SkillSphere एक career और job portal है। उम्मीदवार अपनी profile और applications संभालते हैं; recruiters अपनी jobs और applicants संभालते हैं।",
            "services": "SkillSphere में candidate profile, resume upload और builder, job search, applications, assessments, interview practice, recruiter tools और support शामिल हैं। सुविधाएँ account role पर निर्भर हैं।",
            "contact": "अपने खाते की सहायता के लिए sign in करके Support Center खोलें। मेरे पास सत्यापित public phone number या office address नहीं है।",
            "register": "Create Account चुनें और registration form भरें। अपने role के अनुसार account type चुनें।",
            "login": "अपने registered email और password से Sign In करें। Chat में password या OTP न भेजें।",
            "pricing": "SkillSphere की सत्यापित pricing जानकारी मेरे पास उपलब्ध नहीं है।",
            "hours": "Support के verified working hours मेरे पास नहीं हैं। अनुरोध भेजने के लिए Support Center खोलें।",
            "privacy": "Sign-in chat history केवल आपके खाते के लिए है। Chat में password, OTP या अनावश्यक निजी जानकारी न भेजें।",
            "language": "Language menu से जवाब की भाषा चुनें। Auto English, Hindi, Hinglish, Punjabi और Roman Punjabi पहचानता है।",
        },
        "hinglish": {
            "greeting": "Namaste! Main SkillSphere Assistant hoon. Main platform aur verified SkillSphere jobs mein guide kar sakta hoon.",
            "goodbye": "Alvida! SkillSphere help chahiye ho to phir pooch sakte hain.",
            "thanks": "Aapka welcome!",
            "unknown": "Iska verified answer mere paas abhi nahi hai. Aap rephrase karein ya neeche topic choose karein.",
            "clarify": "Kai topics match ho rahe hain. Aap profile, resume, applications ya assessments ke baare mein pooch rahe hain?",
            "about": "SkillSphere ek career aur job portal hai. Candidates apni profile aur applications manage karte hain; recruiters apni jobs aur applicants manage karte hain.",
            "services": "SkillSphere mein profile, resume upload/builder, job search, applications, assessments, interview practice, recruiter tools aur support hain. Features aapke role par depend karte hain.",
            "contact": "Account help ke liye sign in karke Support Center use karein. Verified public phone number ya office address mere paas nahi hai.",
            "register": "Create Account select karke form fill karein aur apne role ka account type choose karein.",
            "login": "Registered email aur password se Sign In karein. Chat mein password ya OTP share na karein.",
            "pricing": "SkillSphere ki verified pricing mere paas available nahi hai.",
            "hours": "Support ke verified timings mere paas nahi hain. Request bhejne ke liye Support Center use karein.",
            "privacy": "Sign-in chat history aapke account tak private hai. Password, OTP ya unnecessary private info share na karein.",
            "language": "Language menu se reply language choose karein. Auto English, Hindi, Hinglish, Punjabi aur Roman Punjabi detect karta hai.",
        },
        "pa": {
            "greeting": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ SkillSphere Assistant ਹਾਂ। ਮੈਂ platform ਅਤੇ SkillSphere ਦੀਆਂ verified jobs ਬਾਰੇ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ।",
            "goodbye": "ਫਿਰ ਮਿਲਾਂਗੇ। SkillSphere ਲਈ ਮਦਦ ਚਾਹੀਦੀ ਹੋਵੇ ਤਾਂ ਪੁੱਛੋ।",
            "thanks": "ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ!",
            "unknown": "ਇਸ ਬਾਰੇ verified ਜਾਣਕਾਰੀ ਮੇਰੇ ਕੋਲ ਨਹੀਂ ਹੈ। ਸਵਾਲ ਹੋਰ ਤਰੀਕੇ ਨਾਲ ਪੁੱਛੋ ਜਾਂ ਹੇਠਾਂ topic ਚੁਣੋ।",
            "clarify": "ਕਈ topics ਮਿਲ ਰਹੇ ਹਨ। ਕੀ ਤੁਸੀਂ profile, resume, applications ਜਾਂ assessments ਬਾਰੇ ਪੁੱਛ ਰਹੇ ਹੋ?",
            "about": "SkillSphere career ਅਤੇ job portal ਹੈ। Candidates ਆਪਣੀ profile ਅਤੇ applications ਸੰਭਾਲਦੇ ਹਨ; recruiters ਆਪਣੀਆਂ jobs ਅਤੇ applicants ਸੰਭਾਲਦੇ ਹਨ।",
            "services": "SkillSphere ਵਿੱਚ profile, resume upload/builder, job search, applications, assessments, interview practice, recruiter tools ਅਤੇ support ਹਨ। Features role ਅਨੁਸਾਰ ਹੁੰਦੇ ਹਨ।",
            "contact": "Account help ਲਈ sign in ਕਰਕੇ Support Center ਖੋਲ੍ਹੋ। ਮੇਰੇ ਕੋਲ verified public phone ਜਾਂ office address ਨਹੀਂ ਹੈ।",
            "register": "Create Account ਚੁਣੋ, form ਭਰੋ ਅਤੇ ਆਪਣੇ role ਅਨੁਸਾਰ account type ਚੁਣੋ।",
            "login": "Registered email ਅਤੇ password ਨਾਲ Sign In ਕਰੋ। Chat ਵਿੱਚ password ਜਾਂ OTP ਨਾ ਭੇਜੋ।",
            "pricing": "SkillSphere pricing ਦੀ verified ਜਾਣਕਾਰੀ ਮੇਰੇ ਕੋਲ ਨਹੀਂ ਹੈ।",
            "hours": "Support ਦੇ verified hours ਮੇਰੇ ਕੋਲ ਨਹੀਂ ਹਨ। Request ਲਈ Support Center ਵਰਤੋ।",
            "privacy": "Sign-in chat history ਤੁਹਾਡੇ account ਤੱਕ private ਹੈ। Password, OTP ਜਾਂ ਬੇਲੋੜੀ private ਜਾਣਕਾਰੀ ਨਾ ਭੇਜੋ।",
            "language": "Language menu ਵਿੱਚ reply language ਚੁਣੋ। Auto English, Hindi, Hinglish, Punjabi ਅਤੇ Roman Punjabi ਪਛਾਣਦਾ ਹੈ।",
        },
        "pa_latn": {
            "greeting": "Sat sri akaal! Main SkillSphere Assistant haan. Main platform ate verified SkillSphere jobs bare madad kar sakda haan.",
            "goodbye": "Phir milange. SkillSphere help chahidi hove taan puchho.",
            "thanks": "Tuhada swagat hai!",
            "unknown": "Is bare verified jaankari mere kol nahi hai. Sawaal hor tareeke naal puchho ya topic chuno.",
            "clarify": "Kai topics mil rahe han. Tusi profile, resume, applications ja assessments bare puch rahe ho?",
            "about": "SkillSphere career ate job portal hai. Candidates apni profile/applications sambhalde han; recruiters apnia jobs ate applicants sambhalde han.",
            "services": "SkillSphere vich profile, resume upload/builder, job search, applications, assessments, interview practice, recruiter tools ate support han.",
            "contact": "Account help layi sign in karke Support Center kholo. Verified public phone ja office address mere kol nahi.",
            "register": "Create Account chuno, form bharo ate apne role da account type chuno.",
            "login": "Registered email ate password naal Sign In karo. Chat vich password ja OTP na bhejo.",
            "pricing": "SkillSphere pricing bare verified jaankari mere kol nahi.",
            "hours": "Support de verified hours mere kol nahi. Request layi Support Center varto.",
            "privacy": "Sign-in chat history tuhade account tak private hai. Password, OTP ja private info na bhejo.",
            "language": "Language menu ton reply language chuno. Auto English, Hindi, Hinglish, Punjabi ate Roman Punjabi detect karda hai.",
        },
    }
    language_aliases = {"hi_latn": "hinglish"}
    lang = language_aliases.get(code, code)
    return strings.get(lang, strings["en"])[key]


_CANDIDATE_RESPONSE_TEXT = {
    "en": {
        "no_applications": "You have no applications recorded yet. Browse published jobs to apply.",
        "applications_header": "Your recent applications:", "application_status": "status",
        "no_assessments": "No assessment has been assigned to your account. Assessments appear after a recruiter shortlists your application.",
        "results_header": "Your assessment results:", "assignments_header": "Your assigned assessments:",
        "marks": "marks", "qualified": "qualified", "not_qualified": "not qualified",
        "review_status": "review status", "profile_missing": "Your candidate profile is not set up yet. Open My Profile to complete it.",
        "profile_completion": "Your profile completion is {value}%. Open My Profile to review your details.",
        "no_interviews": "No interview is currently recorded for your account.",
        "interviews_header": "Your interviews:", "interview_status": "status",
    },
    "hi": {
        "no_applications": "आपके खाते में अभी कोई आवेदन दर्ज नहीं है। आवेदन करने के लिए प्रकाशित jobs देखें।",
        "applications_header": "आपके हाल के आवेदन:", "application_status": "स्थिति",
        "no_assessments": "आपके खाते में कोई assessment assign नहीं हुआ है। Recruiter द्वारा आवेदन shortlist करने के बाद assessment दिखाई देगा।",
        "results_header": "आपके assessment परिणाम:", "assignments_header": "आपको दिए गए assessments:",
        "marks": "अंक", "qualified": "योग्य", "not_qualified": "योग्य नहीं",
        "review_status": "review स्थिति", "profile_missing": "आपकी candidate profile अभी सेट नहीं है। इसे पूरा करने के लिए My Profile खोलें।",
        "profile_completion": "आपकी profile {value}% पूरी है। विवरण देखने के लिए My Profile खोलें।",
        "no_interviews": "आपके खाते में अभी कोई interview दर्ज नहीं है।",
        "interviews_header": "आपके interviews:", "interview_status": "स्थिति",
    },
    "hinglish": {
        "no_applications": "Aapke account mein abhi koi application record nahi hai. Apply karne ke liye published jobs dekhein.",
        "applications_header": "Aapki recent applications:", "application_status": "status",
        "no_assessments": "Aapke account ko abhi assessment assign nahi hua. Recruiter aapki application shortlist karega tab assessment dikhega.",
        "results_header": "Aapke assessment results:", "assignments_header": "Aapko assigned assessments:",
        "marks": "marks", "qualified": "qualified", "not_qualified": "qualified nahi",
        "review_status": "review status", "profile_missing": "Aapki candidate profile abhi set up nahi hai. Ise complete karne ke liye My Profile kholein.",
        "profile_completion": "Aapki profile {value}% complete hai. Details dekhne ke liye My Profile kholein.",
        "no_interviews": "Aapke account mein abhi koi interview record nahi hai.",
        "interviews_header": "Aapke interviews:", "interview_status": "status",
    },
    "pa": {
        "no_applications": "ਤੁਹਾਡੇ ਖਾਤੇ ਵਿੱਚ ਹਾਲੇ ਕੋਈ ਅਰਜ਼ੀ ਦਰਜ ਨਹੀਂ ਹੈ। ਅਰਜ਼ੀ ਦੇਣ ਲਈ ਪ੍ਰਕਾਸ਼ਿਤ jobs ਵੇਖੋ।",
        "applications_header": "ਤੁਹਾਡੀਆਂ ਹਾਲੀਆ ਅਰਜ਼ੀਆਂ:", "application_status": "ਸਥਿਤੀ",
        "no_assessments": "ਤੁਹਾਡੇ ਖਾਤੇ ਲਈ ਹਾਲੇ assessment ਨਹੀਂ ਦਿੱਤਾ ਗਿਆ। Recruiter ਵੱਲੋਂ ਅਰਜ਼ੀ shortlist ਕਰਨ ਤੋਂ ਬਾਅਦ assessment ਦਿਖੇਗਾ।",
        "results_header": "ਤੁਹਾਡੇ assessment ਨਤੀਜੇ:", "assignments_header": "ਤੁਹਾਨੂੰ ਦਿੱਤੇ assessments:",
        "marks": "ਅੰਕ", "qualified": "ਯੋਗ", "not_qualified": "ਯੋਗ ਨਹੀਂ",
        "review_status": "review ਸਥਿਤੀ", "profile_missing": "ਤੁਹਾਡੀ candidate profile ਹਾਲੇ ਸੈੱਟ ਨਹੀਂ ਹੈ। ਇਸਨੂੰ ਪੂਰਾ ਕਰਨ ਲਈ My Profile ਖੋਲ੍ਹੋ।",
        "profile_completion": "ਤੁਹਾਡੀ profile {value}% ਪੂਰੀ ਹੈ। ਵੇਰਵੇ ਵੇਖਣ ਲਈ My Profile ਖੋਲ੍ਹੋ।",
        "no_interviews": "ਤੁਹਾਡੇ ਖਾਤੇ ਵਿੱਚ ਹਾਲੇ ਕੋਈ interview ਦਰਜ ਨਹੀਂ ਹੈ।",
        "interviews_header": "ਤੁਹਾਡੇ interviews:", "interview_status": "ਸਥਿਤੀ",
    },
    "pa_latn": {
        "no_applications": "Tuhade account vich hale koi application record nahi hai. Apply karan layi published jobs vekho.",
        "applications_header": "Tuhadian recent applications:", "application_status": "status",
        "no_assessments": "Tuhade account nu hale assessment assign nahi hoya. Recruiter application shortlist karega taan assessment dikhuga.",
        "results_header": "Tuhade assessment results:", "assignments_header": "Tuhanu assigned assessments:",
        "marks": "marks", "qualified": "yog", "not_qualified": "yog nahi",
        "review_status": "review status", "profile_missing": "Tuhadi candidate profile hale set nahi hai. Complete karan layi My Profile kholo.",
        "profile_completion": "Tuhadi profile {value}% complete hai. Details vekhan layi My Profile kholo.",
        "no_interviews": "Tuhade account vich hale koi interview record nahi hai.",
        "interviews_header": "Tuhade interviews:", "interview_status": "status",
    },
}


def _candidate_words(language: str) -> dict:
    language = {"hi_latn": "hinglish"}.get(language, language)
    return _CANDIDATE_RESPONSE_TEXT.get(language, _CANDIDATE_RESPONSE_TEXT["en"])


def _classify(message: str, match: dict) -> Optional[str]:
    text = normalize_text(message)
    words = set(text.split())
    ticket_request_phrases = (
        "raise a ticket", "raise ticket", "create a ticket", "create ticket",
        "submit a ticket", "submit ticket", "open a ticket", "open ticket",
        "file a ticket", "file ticket", "support ticket", "contact support",
        "contact the support", "contact customer support", "talk to support",
        "speak to support", "reach support", "help desk",
    )
    if any(normalize_text(phrase) in text for phrase in ticket_request_phrases):
        return "support"
    if words & {"hi", "hello", "hey", "namaste", "नमस्ते", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "sat", "salam"}:
        return "greeting"
    if words & {"bye", "goodbye", "alvida", "ਅਲਵਿਦਾ"}:
        return "goodbye"
    if words & {"thanks", "thank", "shukriya", "ਧੰਨਵਾਦ", "धन्यवाद"}:
        return "thanks"
    groups = {
        "about": {"about skillsphere", "what is skillsphere", "about the company", "company overview", "तुम कौन", "skillSphere kya hai"},
        "services": {"services", "features", "platform features", "what can you do", "क्या सुविधाएं"},
        "contact": {"contact", "phone number", "office address", "contact information", "संपर्क"},
        "register": {"register", "registration", "sign up", "create account", "खाता बनाएं"},
        "login": {"login", "log in", "sign in", "साइन इन"},
        "pricing": {"price", "pricing", "subscription", "fees", "cost"},
        "hours": {"working hours", "support hours", "opening hours", "timing"},
        "privacy": {"privacy", "private chat", "chat history privacy", "my data"},
        "language": {"change language", "select language", "language options", "भाषा बदलें"},
    }
    for intent, phrases in groups.items():
        if any(normalize_text(phrase) in text for phrase in phrases):
            return intent
    if match.get("intent"):
        return match["intent"]
    return None


def _candidate_data(db: Session, user: User, intent: str, language: str):
    words = _candidate_words(language)
    candidate = db.query(Candidate).filter_by(user_id=user.id).first()
    if not candidate:
        if intent == "applications":
            return words["no_applications"]
        if intent in {"assessments", "assessment_results"}:
            return words["no_assessments"]
        if intent == "profile_status":
            return words["profile_missing"]
        if intent == "interview_status":
            return words["no_interviews"]
        return None
    if intent == "applications":
        rows = db.query(Application).filter_by(candidate_id=candidate.id).order_by(Application.updated_at.desc()).limit(8).all()
        if not rows:
            return words["no_applications"]
        return words["applications_header"] + "\n" + "\n".join(
            f"• {row.job.title} — {row.job.company.name}: {words['application_status']} {row.current_status.value}"
            for row in rows if row.job and row.job.company
        )
    if intent in {"assessments", "assessment_results"}:
        rows = db.query(AssessmentAssignment).filter_by(candidate_id=candidate.id).order_by(AssessmentAssignment.assigned_at.desc()).limit(8).all()
        if not rows:
            return words["no_assessments"]
        lines = []
        for row in rows:
            title = row.job_assessment.title if row.job_assessment else "Assessment"
            result = row.result
            if intent == "assessment_results" and result:
                lines.append(
                    f"• {title} — {result.obtained_marks:g}/{result.total_marks:g} {words['marks']}, "
                    f"{words['qualified'] if result.is_qualified else words['not_qualified']}, "
                    f"{words['review_status']}: {result.review_status}."
                )
            else:
                lines.append(f"• {title} — {row.status}")
        header = words["results_header"] if intent == "assessment_results" else words["assignments_header"]
        return header + "\n" + "\n".join(lines)
    if intent == "profile_status":
        return words["profile_completion"].format(value=candidate.profile_percentage)
    if intent == "interview_status":
        rows = db.query(Interview).filter_by(candidate_id=candidate.id).order_by(Interview.interview_date.desc()).limit(5).all()
        if not rows:
            return words["no_interviews"]
        return words["interviews_header"] + "\n" + "\n".join(
            f"• {row.job.title if row.job else 'Interview'} — {words['interview_status']}: {row.status.value}, {row.interview_date:%Y-%m-%d %H:%M}"
            for row in rows
        )
    return None


def _recruiter_data(db: Session, user: User, intent: str):
    recruiter = db.query(Recruiter).filter_by(user_id=user.id).first()
    if not recruiter:
        return None
    jobs = db.query(Job).filter_by(recruiter_id=recruiter.id).order_by(Job.updated_at.desc()).limit(30).all()
    if intent == "recruiter_jobs":
        if not jobs:
            return "Your account has no job postings yet. Open My Jobs to create one."
        return "Your job postings:\n" + "\n".join(f"• {job.title} — {job.status.value}" for job in jobs[:10])
    if intent == "applicant_pipeline":
        rows = db.query(Application).join(Job, Application.job_id == Job.id).filter(Job.recruiter_id == recruiter.id).order_by(Application.updated_at.desc()).limit(20).all()
        if not rows:
            return "There are no applications for your job postings yet."
        return "Recent applications to your jobs:\n" + "\n".join(
            f"• {row.candidate.user.full_name} — {row.job.title}: {row.current_status.value}"
            for row in rows if row.candidate and row.candidate.user and row.job
        )
    return None


def _role_actions(role: str, intent: str, language: str):
    candidates = {
        "profile": "/candidate/profile", "resume_upload": "/candidate/resumes",
        "resume_builder": "/candidate/resume-builder", "jobs": "/candidate/jobs",
        "applications": "/candidate/applications", "assessments": "/candidate/assessments",
        "skill_gap": "/candidate/matching", "interview_practice": "/candidate/interview-practice",
        "support": "/candidate/support", "interview_status": "/candidate/support",
        "profile_status": "/candidate/profile", "assessment_results": "/candidate/assessments",
    }
    recruiters = {
        "recruiter_jobs": "/recruiter/jobs", "recruiter_dashboard": "/recruiter/dashboard",
        "question_bank": "/recruiter/question-bank", "applicant_pipeline": "/recruiter/pipeline",
        "recruiter_interviews": "/recruiter/interviews", "support": "/recruiter/support",
    }
    public = {"about": "/home", "register": "/register", "login": "/login", "jobs": "/home", "support": "/login"}
    path = (candidates if role == "candidate" else recruiters if role == "recruiter" else public).get(intent)
    if not path:
        return []
    labels = {
        "/candidate/profile": "My Profile", "/candidate/resumes": "Resume Upload & OCR",
        "/candidate/resume-builder": "Resume Builder", "/candidate/jobs": "Find Jobs",
        "/candidate/applications": "My Applications", "/candidate/assessments": "Assessment Rules",
        "/candidate/matching": "Skill Gap Analysis", "/candidate/interview-practice": "Interview Practice",
        "/candidate/support": "Contact Support", "/recruiter/jobs": "My Jobs",
        "/recruiter/dashboard": "Recruiter Dashboard", "/recruiter/question-bank": "Question Bank",
        "/recruiter/pipeline": "Manage Applicants", "/recruiter/interviews": "Interview Scheduler",
        "/recruiter/support": "Contact Support", "/home": "About SkillSphere",
        "/register": "Create Account", "/login": "Sign In",
    }
    return [{"label": labels[path], "path": path}]


def _company_answer(db: Session, message: str):
    if db is None:
        return None
    lowered = normalize_text(message)
    options = catalog_options(db)
    for company in sorted(options["companies"], key=lambda item: len(item["name"]), reverse=True):
        if normalize_text(company["name"]) in lowered:
            return lookup_catalog(db, company_id=company["id"])
    company_listing_terms = ("registered companies", "list companies", "which companies", "ਕਿਹੜੀਆਂ ਕੰਪਨੀਆਂ")
    indic_company_listing = ("कंप" in lowered or "ਕੰਪਨ" in lowered) and any(
        marker in lowered for marker in ("कौन", "कौन सी", "ਕਿਹੜੀ", "ਕਿਹੜੀਆਂ")
    )
    if indic_company_listing or any(normalize_text(term) in lowered for term in company_listing_terms):
        result = lookup_catalog(db, show_jobs=False)
        names = [item["name"] for item in options["companies"]]
        if names:
            result["message"] = "Registered SkillSphere companies: " + ", ".join(names[:20])
        return result
    job_terms = ("job", "jobs", "vacancy", "vacancies", "openings", "hiring", "नौकरी", "ਨੌਕਰੀ")
    if any(normalize_text(term) in lowered for term in job_terms):
        return lookup_catalog(db, show_jobs=True)
    return None


def answer_assistant(
    db: Session,
    message: str,
    role: str,
    context_path: str = "",
    history=None,
    selected_language: str = "auto",
    user: Optional[User] = None,
):
    match = match_intent(message)
    intent = _classify(message, match)
    detected = detect_language(message)
    language = detected if selected_language == "auto" else selected_language
    if language not in LANGUAGES:
        language = "en"

    normalized_request = normalize_text(message)
    if role == "candidate":
        if "application status" in normalized_request or "my applications" in normalized_request:
            intent = "applications"
        elif "assessment result" in normalized_request:
            intent = "assessment_results"
        elif "my assessment" in normalized_request:
            intent = "assessments"
        elif "profile completion" in normalized_request:
            intent = "profile_status"
        elif "my interview" in normalized_request or "interview schedule" in normalized_request:
            intent = "interview_status"
    elif role == "recruiter" and any(word in normalized_request.split() for word in ("applicant", "applicants", "candidate", "candidates")):
        intent = "applicant_pipeline"

    normalized_message = normalize_text(message)
    approved_entries = db.query(AssistantKnowledgeSuggestion).filter_by(status="APPROVED", language=language).limit(300).all() if db is not None else []
    for entry in approved_entries:
        if normalize_text(entry.question) == normalized_message:
            actions = []
            route_role = "public" if role == "visitor" else role
            if entry.route and route_for_path(entry.route, route_role):
                actions = [{"label": "Open verified page", "path": entry.route}]
            return {"reply": entry.response, "intent": entry.intent_id, "confidence": 1.0, "language": language, "actions": actions, "suggestions": _suggestions(role, language), "ticket_suggestion": False}

    # Company/job facts are always sourced from published SkillSphere records.
    company_message = message
    normalized = normalize_text(message)
    if any(marker in normalized for marker in ("their jobs", "their openings", "what about their", "jobs there", "aur jobs", "hor jobs")):
        previous_user = next((
            item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
            for item in reversed(history or [])
            if (item.get("role") if isinstance(item, dict) else getattr(item, "role", None)) == "user"
        ), "")
        if previous_user:
            company_message = previous_user
    company_result = _company_answer(db, company_message) if role in {"visitor", "candidate", "recruiter"} else None
    if company_result is not None:
        reply = format_catalog_reply(company_result, language)
        actions = _role_actions(role, "jobs", language) if role in {"visitor", "candidate"} else []
        return {"reply": reply, "intent": "company_information", "confidence": 0.98, "language": language, "actions": actions, "suggestions": _suggestions(role, language), "ticket_suggestion": False}

    if intent in {"applications", "assessments", "assessment_results", "profile_status", "interview_status", "recruiter_jobs", "applicant_pipeline"}:
        if user is None:
            intent = "login"
            reply = _language_response(language, "login")
        elif role == "candidate":
            reply = _candidate_data(db, user, intent, language)
        elif role == "recruiter":
            reply = _recruiter_data(db, user, intent)
        else:
            reply = "Account-specific information is available only to the owning candidate or recruiter."
        if not reply:
            reply = _language_response(language, "unknown")
        return {"reply": reply, "intent": intent, "confidence": max(0.9, match.get("confidence", 0)), "language": language, "actions": _role_actions(role, intent, language), "suggestions": [], "ticket_suggestion": False}

    key = intent
    if key is None and history:
        last = next((item for item in reversed(history) if (item.get("role") if isinstance(item, dict) else getattr(item, "role", None)) == "user"), None)
        if last:
            last_text = last.get("text", "") if isinstance(last, dict) else last.text
            previous_match = match_intent(last_text)
            if any(term in normalize_text(message).split() for term in ("it", "that", "this", "there", "फिर", "ਫਿਰ")):
                key = _classify(last_text, previous_match)
    if key is None and context_path:
        context_intent = next((name for name, topic in TOPICS.items() if topic.get("route") == context_path and role in topic["roles"]), None)
        if len(normalize_text(message).split()) < 4:
            key = context_intent
    if key in {"greeting", "goodbye", "thanks", "about", "services", "contact", "register", "login", "pricing", "hours", "privacy", "language"}:
        reply = _language_response(language, key)
        return {"reply": reply, "intent": key, "confidence": max(0.88, match.get("confidence", 0)), "language": language, "actions": _role_actions(role, key, language), "suggestions": _suggestions(role, language), "ticket_suggestion": False}

    if key:
        result = answer_website_help(message, role, context_path=context_path, history=history, language_override=language)
        reply = result["reply"]
        confidence = max(float(match.get("confidence", 0)), 0.78)
        intent = key
        actions = result["actions"]
        suggestions = _suggestions(role, language)
    else:
        confidence = float(match.get("confidence", 0))
        reply = _language_response(language, "clarify" if match.get("ambiguous") else "unknown")
        intent = match.get("intent")
        actions = []
        suggestions = _suggestions(role, language)
        record_unanswered(db, message, language, match)
    ticket_suggestion = result.get("ticket_suggestion", intent == "support") if key else intent == "support"
    return {"reply": reply, "intent": intent, "confidence": confidence, "language": language, "actions": actions, "suggestions": suggestions, "ticket_suggestion": ticket_suggestion}


def _suggestions(role: str, language: str):
    language = {"hi_latn": "hinglish"}.get(language, language)
    suggestions = {
        "en": {
            "candidate": ["Find jobs", "My applications", "Resume Builder", "Assessment rules"],
            "recruiter": ["My jobs", "Manage applicants", "Question Bank", "Interview Scheduler"],
            "visitor": ["About SkillSphere", "Browse jobs", "Create account", "Contact support"],
            "admin": ["Review assistant feedback", "Review unanswered questions", "Manage support tickets", "Admin dashboard"],
        },
        "hi": {
            "candidate": ["नौकरियाँ खोजें", "मेरे आवेदन", "Resume Builder", "Assessment नियम"],
            "recruiter": ["मेरी jobs", "Applicants कैसे देखें?", "Question Bank", "Interview Scheduler"],
            "visitor": ["SkillSphere के बारे में", "नौकरियाँ देखें", "खाता बनाएँ", "सहायता संपर्क"],
            "admin": ["Assistant feedback देखें", "अनुत्तरित प्रश्न देखें", "Support tickets प्रबंधित करें", "Admin dashboard"],
        },
        "hinglish": {
            "candidate": ["Jobs dekhein", "Meri applications", "Resume Builder", "Assessment rules"],
            "recruiter": ["Meri jobs", "Applicants kaise dekhein?", "Question Bank", "Interview Scheduler"],
            "visitor": ["SkillSphere ke baare mein", "Jobs dekhein", "Account banayein", "Support se contact karein"],
            "admin": ["Assistant feedback review karein", "Unanswered questions dekhein", "Support tickets manage karein", "Admin dashboard"],
        },
        "pa": {
            "candidate": ["ਨੌਕਰੀਆਂ ਲੱਭੋ", "ਮੇਰੀਆਂ ਅਰਜ਼ੀਆਂ", "Resume Builder", "Assessment ਨਿਯਮ"],
            "recruiter": ["ਮੇਰੀਆਂ jobs", "Applicants ਕਿਵੇਂ ਵੇਖੀਏ?", "Question Bank", "Interview Scheduler"],
            "visitor": ["SkillSphere ਬਾਰੇ", "ਨੌਕਰੀਆਂ ਵੇਖੋ", "ਖਾਤਾ ਬਣਾਓ", "ਮਦਦ ਨਾਲ ਸੰਪਰਕ"],
            "admin": ["Assistant feedback ਵੇਖੋ", "ਬਿਨਾਂ ਜਵਾਬ ਵਾਲੇ ਸਵਾਲ ਵੇਖੋ", "Support tickets ਸੰਭਾਲੋ", "Admin dashboard"],
        },
        "pa_latn": {
            "candidate": ["Jobs labho", "Merian applications", "Resume Builder", "Assessment rules"],
            "recruiter": ["Merian jobs", "Applicants kiven vekhan?", "Question Bank", "Interview Scheduler"],
            "visitor": ["SkillSphere bare", "Jobs vekho", "Account banao", "Support naal sampark"],
            "admin": ["Assistant feedback vekho", "Unanswered questions vekho", "Support tickets sambhalo", "Admin dashboard"],
        },
    }
    return suggestions.get(language, suggestions["en"]).get(role, suggestions.get(language, suggestions["en"])["visitor"])
