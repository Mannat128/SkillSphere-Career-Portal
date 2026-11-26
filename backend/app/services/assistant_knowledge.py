"""Local, code-reviewed Sphera knowledge and lightweight multilingual retrieval.

Website Help intentionally uses no network model or translation service. Its answers
are limited to the routes and workflows documented here; uncertain requests get a
clarification or an honest limitation instead of an invented feature.
"""

from difflib import SequenceMatcher
import re
import unicodedata


PUBLIC_ROUTES = {
    "public": {"/home": "Home", "/login": "Sign in", "/register": "Create an account"},
    "candidate": {
        "/candidate/dashboard": "Candidate dashboard", "/candidate/profile": "Candidate profile",
        "/candidate/resumes": "Resume upload and OCR", "/candidate/resume-builder": "Resume Builder",
        "/candidate/jobs": "Explore jobs", "/candidate/saved-jobs": "Saved jobs",
        "/candidate/applications": "My applications", "/candidate/assessments": "First round assessments",
        "/candidate/technical-assessments": "Technical quizzes", "/candidate/matching": "Skill gap analysis",
        "/candidate/interview-practice": "Interview practice", "/candidate/support": "Support Center",
    },
    "recruiter": {
        "/recruiter/dashboard": "Recruiter dashboard", "/recruiter/company": "Company profile",
        "/recruiter/jobs": "Manage job postings", "/recruiter/pipeline": "Applicant pipeline",
        "/recruiter/question-bank": "Recruiter-only Question Bank", "/recruiter/comparison": "Candidate comparison",
        "/recruiter/assessments/results": "Assessment results", "/recruiter/interviews": "Interview scheduling",
        "/recruiter/ai-assistant": "Recruiter AI Assistant", "/recruiter/support": "Support Center",
    },
    "admin": {
        "/admin/dashboard": "Admin dashboard", "/admin/users": "User management",
        "/admin/recruiters": "Recruiter verification", "/admin/jobs": "Job moderation",
        "/admin/pending-approvals": "Pending approvals",
        "/admin/audit-logs": "Audit logs", "/admin/support": "Support Center",
    },
}


# Aliases are deliberately kept local and reviewable. Longer, more specific phrases
# score above generic terms such as "resume" or "assessment".
TOPICS = {
    "profile": {
        "route": "/candidate/profile", "roles": {"candidate"},
        "aliases": ["profile", "my profile", "edit profile", "update profile", "profile details", "प्रोफ़ाइल", "प्रोफाइल", "मेरा प्रोफ़ाइल", "प्रोफाइल अपडेट", "profile update", "mera profile", "meri profile", "profile kaise update", "profile upd", "முக perfil", "আমার প্রোফাইল", "mi perfil", "mon profil"],
        "guidance": "Open My Profile to view or update your candidate profile details.",
        "guidance_hi": "अपनी प्रोफ़ाइल देखने या अपडेट करने के लिए My Profile खोलें।",
    },
    "resume_upload": {
        "route": "/candidate/resumes", "roles": {"candidate"},
        "aliases": ["resume upload", "upload resume", "my resume", "resume parsing", "resume ocr", "no resume found", "resume not found", "cv upload", "résumé", "resume", "रिज़्यूमे", "रिज्यूमे", "सीवी", "बायोडाटा", "मेरा रिज्यूमे", "रिज्यूमे अपलोड", "mera resume", "resume upload nahi", "resume ni hora", "resmue", "curriculo", "currículo", "জীবনবৃত্তান্ত", "ரெஸ்யூம்", "రెజ్యూమ్", "रेझ्युमे", "ਰੇਜ਼ਿਊਮੇ", "ریزیومے", "السيرة الذاتية"],
        "guidance": "Open My Resume to upload a resume and check its processing status. Skill Gap Analysis needs a processed resume.",
        "guidance_hi": "रेज़्यूमे अपलोड करने और उसकी प्रोसेसिंग स्थिति देखने के लिए My Resume खोलें। Skill Gap Analysis के लिए प्रोसेस हुआ रेज़्यूमे चाहिए।",
    },
    "resume_builder": {
        "route": "/candidate/resume-builder", "roles": {"candidate"},
        "aliases": ["resume builder", "build resume", "build a resume", "create resume pdf", "download resume pdf", "resume pdf", "resume template", "resume builder pdf", "रिज्यूमे बिल्डर", "रेज्यूमे पीडीएफ", "resume builder kaise", "curriculo pdf"],
        "guidance": "Open Resume Builder, choose a template, preview it, then use Download PDF. The builder offers six templates.",
        "guidance_hi": "Resume Builder खोलें, टेम्पलेट चुनें, प्रीव्यू देखें और Download PDF चुनें। इसमें छह टेम्पलेट हैं।",
    },
    "jobs": {
        "route": "/candidate/jobs", "roles": {"candidate"},
        "aliases": ["explore jobs", "search jobs", "find jobs", "browse jobs", "apply for job", "apply to job", "job application", "नौकरी", "जॉब खोज", "नौकरी कैसे ढूंढ", "job kaise dhunde", "naukri", "काम खोज", "empleos", "buscar trabajo", "offres emploi", "வேலைகள்", "চাকরি"],
        "guidance": "Open Explore Jobs to browse available postings. Open a job to review its details and application option.",
        "guidance_hi": "उपलब्ध नौकरियां देखने के लिए Explore Jobs खोलें। विवरण और आवेदन विकल्प देखने के लिए कोई नौकरी खोलें।",
    },
    "applications": {
        "route": "/candidate/applications", "roles": {"candidate"},
        "aliases": ["my applications", "application status", "track application", "check application", "आवेदन स्थिति", "मेरे आवेदन", "application status kya", "mis postulaciones", "mes candidatures", "என் விண்ணப்பங்கள்", "আমার আবেদন"],
        "guidance": "Open My Applications to review the status of your submitted applications.",
        "guidance_hi": "जमा किए गए आवेदनों की स्थिति देखने के लिए My Applications खोलें।",
    },
    "assessments": {
        "route": "/candidate/assessments", "roles": {"candidate"},
        "aliases": ["first round assessment", "assigned assessment", "assessment consent", "camera microphone assessment", "assessment recording", "assessment", "test", "exam", "मूल्यांकन", "असेसमेंट", "परीक्षा", "camera permission", "mera test", "avaliação", "évaluation", "மதிப்பீடு", "পরীক্ষা"],
        "guidance": "Open Assessments to see assigned first-round assessments. Read the consent notice and complete the displayed device checks before starting.",
        "guidance_hi": "दिए गए first-round assessments देखने के लिए Assessments खोलें। शुरू करने से पहले सहमति सूचना पढ़ें और दिखाए गए device checks पूरे करें।",
    },
    "skill_gap": {
        "route": "/candidate/matching", "roles": {"candidate"},
        "aliases": ["skill gap", "skill gap analysis", "resume job match", "match resume to job", "compare jobs", "job fit", "कौशल अंतर", "स्किल गैप", "resume match", "mera match score", "brecha de habilidades", "écart de compétences", "திறன் இடைவெளி", "দক্ষতার ঘাটতি"],
        "guidance": "Open Skill Gap Analysis, select a processed resume and a job, then run a single analysis or compare across open jobs.",
        "guidance_hi": "Skill Gap Analysis खोलें, प्रोसेस हुआ रेज़्यूमे और नौकरी चुनें, फिर एक analysis चलाएं या open jobs से तुलना करें।",
    },
    "interview_practice": {
        "route": "/candidate/interview-practice", "roles": {"candidate"},
        "aliases": ["interview practice", "practice interview", "mock interview", "interview questions practice", "इंटरव्यू अभ्यास", "interview ki practice", "práctica de entrevista", "entretien pratique", "நேர்காணல் பயிற்சி", "সাক্ষাৎকার অনুশীলন"],
        "guidance": "Open Interview Practice to start a practice session and review the prompts shown there.",
        "guidance_hi": "अभ्यास सत्र शुरू करने और वहां दिए गए prompts देखने के लिए Interview Practice खोलें।",
    },
    "technical_quizzes": {
        "route": "/candidate/technical-assessments", "roles": {"candidate"},
        "aliases": ["technical quiz", "technical assessment", "coding quiz", "quiz", "तकनीकी क्विज़", "technical test", "prueba técnica", "quiz técnico", "தொழில்நுட்ப வினாடி வினா", "প্রযুক্তি কুইজ"],
        "guidance": "Open Technical Quizzes to view and complete quizzes available to your candidate account.",
        "guidance_hi": "अपने candidate खाते के उपलब्ध quizzes देखने और पूरा करने के लिए Technical Quizzes खोलें।",
    },
    "recruiter_jobs": {
        "route": "/recruiter/jobs", "roles": {"recruiter"},
        "aliases": ["create job", "post a job", "job posting", "manage jobs", "assessment configuration", "configure assessment", "vacancy", "job ad", "नौकरी पोस्ट", "recruiter job", "publicar empleo", "offre d'emploi"],
        "guidance": "Open Manage Jobs to create or edit your job postings and their available assessment settings.",
        "guidance_hi": "अपने job postings बनाने या बदलने और उपलब्ध assessment settings देखने के लिए Manage Jobs खोलें।",
    },
    "question_bank": {
        "route": "/recruiter/question-bank", "roles": {"recruiter"},
        "aliases": ["question bank", "assessment questions", "recruiter question bank", "प्रश्न बैंक", "question bank kaha", "banco de preguntas", "banque de questions", "கேள்வி வங்கி", "প্রশ্ন ব্যাংক"],
        "guidance": "The Question Bank is recruiter-only. Recruiters can open it from the recruiter navigation.",
        "guidance_hi": "Question Bank केवल recruiters के लिए है। Recruiters इसे अपने navigation से खोल सकते हैं।",
    },
    "applicant_pipeline": {
        "route": "/recruiter/pipeline", "roles": {"recruiter"},
        "aliases": ["applicant pipeline", "review applicants", "shortlist candidate", "candidate applications recruiter", "pipeline", "उम्मीदवार आवेदन", "recruiter applicants", "candidatos", "candidatures", "விண்ணப்பதாரர்கள்", "আবেদনকারী"],
        "guidance": "Open Applicants to review candidates who applied to your jobs and manage their pipeline status.",
        "guidance_hi": "अपनी नौकरियों पर आवेदन करने वाले candidates देखने और उनकी pipeline स्थिति संभालने के लिए Applicants खोलें।",
    },
    "recruiter_interviews": {
        "route": "/recruiter/interviews", "roles": {"recruiter"},
        "aliases": ["schedule interview", "interview scheduling", "recruiter interviews", "interview calendar", "साक्षात्कार शेड्यूल", "programar entrevista", "planifier entretien", "நேர்காணல் அட்டவணை", "সাক্ষাৎকার সময়সূচী"],
        "guidance": "Open Interview Scheduling to review and manage interview appointments.",
        "guidance_hi": "इंटरव्यू appointments देखने और संभालने के लिए Interview Scheduling खोलें।",
    },
    "admin_approvals": {
        "route": "/admin/pending-approvals", "roles": {"admin"},
        "aliases": ["pending approvals", "approve job", "job approval", "moderate jobs", "प्रतीक्षित अनुमोदन", "admin approval", "aprobar empleo", "approbation emploi", "நிலுவை ஒப்புதல்கள்", "অনুমোদন"],
        "guidance": "Open Pending Approvals to review items awaiting admin moderation.",
        "guidance_hi": "Admin moderation की प्रतीक्षा कर रहे items देखने के लिए Pending Approvals खोलें।",
    },
    "admin_audit": {
        "route": "/admin/audit-logs", "roles": {"admin"},
        "aliases": ["audit logs", "admin audit", "activity logs", "ऑडिट लॉग", "registro de auditoría", "journaux d'audit", "தணிக்கை பதிவுகள்", "অডিট লগ"],
        "guidance": "Open Audit Logs to review recorded administrative and security activity available to your admin account.",
        "guidance_hi": "अपने admin खाते में उपलब्ध administrative और security activity देखने के लिए Audit Logs खोलें।",
    },
    "support": {
        "route": None, "roles": {"candidate", "recruiter", "admin", "public_guest"},
        "aliases": ["support", "help desk", "raise ticket", "contact support", "technical issue", "सहायता", "टिकट बनाना", "ayuda", "assistance", "உதவி", "সহায়তা"],
        "guidance": "Open Support Center for help. Signed-in users can use its ticket controls.",
        "guidance_hi": "सहायता के लिए Support Center खोलें। Sign-in users वहां ticket controls का उपयोग कर सकते हैं।",
    },
}


# Short response strings are curated locally. Product page names remain in English
# because that is how they appear in the existing UI; the response sentence follows
# the detected language/script.
MESSAGES = {
    "en": {"found": "The verified SkillSphere page for this task is **{page}** (`{path}`). {guidance}", "unknown": "I don't have verified instructions for that yet. Which SkillSphere page or task do you mean?", "clarify": "I found more than one possible topic. Which SkillSphere page or task should I explain?", "restricted": "That SkillSphere page is not available for your account role.", "login": "Please sign in to open candidate or recruiter pages.", "open": "Open"},
    "hi": {"found": "इस काम का सत्यापित SkillSphere पेज **{page}** (`{path}`) है। {guidance}", "unknown": "इस बारे में मेरे पास अभी सत्यापित निर्देश नहीं हैं। आप SkillSphere के किस पेज या काम के बारे में पूछ रहे हैं?", "clarify": "एक से अधिक विषय संभव हैं। आप किस SkillSphere पेज या काम के बारे में पूछ रहे हैं?", "restricted": "यह SkillSphere पेज आपके खाते की भूमिका के लिए उपलब्ध नहीं है।", "login": "Candidate या recruiter पेज खोलने के लिए पहले sign in करें।", "open": "खोलें"},
    "hinglish": {"found": "Is task ka verified SkillSphere page **{page}** (`{path}`) hai. {guidance}", "unknown": "Is baare mein mere paas abhi verified steps nahi hain. Aap kis SkillSphere page ya task ke baare mein pooch rahe hain?", "clarify": "Ek se zyada topics match ho rahe hain. Aap kis SkillSphere page ya task ke baare mein pooch rahe hain?", "restricted": "Yeh SkillSphere page aapke account role ke liye available nahi hai.", "login": "Candidate ya recruiter pages kholne ke liye pehle sign in karein.", "open": "Open"},
    "hi_latn": {"found": "Is kaam ka verified SkillSphere page **{page}** (`{path}`) hai. {guidance}", "unknown": "Is baare mein mere paas abhi verified jaankari nahi hai. Aap kis SkillSphere page ya kaam ke baare mein pooch rahe hain?", "clarify": "Kai topics ho sakte hain. Aap kis SkillSphere page ya kaam ke baare mein pooch rahe hain?", "restricted": "Yeh page aapke account role ke liye available nahi hai.", "login": "Candidate ya recruiter pages ke liye pehle sign in karein.", "open": "Kholein"},
    "pa": {"found": "ਇਸ ਕੰਮ ਲਈ SkillSphere ਦਾ ਪੱਕਾ ਪੰਨਾ **{page}** (`{path}`) ਹੈ। {guidance}", "unknown": "ਇਸ ਬਾਰੇ ਮੇਰੇ ਕੋਲ ਪੱਕੀ ਜਾਣਕਾਰੀ ਨਹੀਂ ਹੈ। ਤੁਸੀਂ ਕਿਹੜੇ SkillSphere ਪੰਨੇ ਜਾਂ ਕੰਮ ਬਾਰੇ ਪੁੱਛ ਰਹੇ ਹੋ?", "clarify": "ਇੱਕ ਤੋਂ ਵੱਧ ਵਿਸ਼ੇ ਮਿਲਦੇ ਹਨ। ਤੁਸੀਂ ਕਿਹੜੇ SkillSphere ਪੰਨੇ ਬਾਰੇ ਪੁੱਛ ਰਹੇ ਹੋ?", "restricted": "ਇਹ SkillSphere ਪੰਨਾ ਤੁਹਾਡੇ ਖਾਤੇ ਦੀ ਭੂਮਿਕਾ ਲਈ ਉਪਲਬਧ ਨਹੀਂ ਹੈ।", "login": "Candidate ਜਾਂ recruiter ਪੰਨੇ ਲਈ ਪਹਿਲਾਂ sign in ਕਰੋ।", "open": "ਖੋਲ੍ਹੋ"},
    "pa_latn": {"found": "Is kam layi SkillSphere da verified page **{page}** (`{path}`) hai. {guidance}", "unknown": "Is bare mere kol verified jaankari nahi hai. Tusi kehde SkillSphere page ja kam bare puch rahe ho?", "clarify": "Kai topics ho sakde han. Tusi kehde SkillSphere page bare puch rahe ho?", "restricted": "Eh page tuhade account role layi available nahi hai.", "login": "Candidate ja recruiter pages layi pehlan sign in karo.", "open": "Kholo"},
    "ur": {"found": "اس کام کے لیے SkillSphere کا تصدیق شدہ صفحہ **{page}** (`{path}`) ہے۔ {guidance}", "unknown": "اس بارے میں میرے پاس ابھی تصدیق شدہ ہدایات نہیں ہیں۔ آپ کس SkillSphere صفحے یا کام کے بارے میں پوچھ رہے ہیں؟", "clarify": "ایک سے زیادہ موضوعات ممکن ہیں۔ آپ کس SkillSphere صفحے کی وضاحت چاہتے ہیں؟", "restricted": "یہ SkillSphere صفحہ آپ کے اکاؤنٹ کے کردار کے لیے دستیاب نہیں ہے۔", "login": "Candidate یا recruiter صفحات کھولنے کے لیے پہلے sign in کریں۔", "open": "کھولیں"},
    "bn": {"found": "এই কাজের জন্য যাচাইকৃত SkillSphere পৃষ্ঠা হলো **{page}** (`{path}`)। {guidance}", "unknown": "এ বিষয়ে আমার কাছে এখনো যাচাইকৃত নির্দেশনা নেই। আপনি কোন SkillSphere পৃষ্ঠা বা কাজের কথা বলছেন?", "clarify": "একাধিক বিষয় মিলে যাচ্ছে। কোন SkillSphere পৃষ্ঠা বা কাজটি ব্যাখ্যা করব?", "restricted": "এই SkillSphere পৃষ্ঠাটি আপনার অ্যাকাউন্টের ভূমিকার জন্য উপলভ্য নয়।", "login": "Candidate বা recruiter পৃষ্ঠা খুলতে আগে sign in করুন।", "open": "খুলুন"},
    "ta": {"found": "இந்தப் பணிக்கான சரிபார்க்கப்பட்ட SkillSphere பக்கம் **{page}** (`{path}`). {guidance}", "unknown": "இதற்கான சரிபார்க்கப்பட்ட வழிமுறை என்னிடம் இல்லை. எந்த SkillSphere பக்கம் அல்லது பணியைப் பற்றி கேட்கிறீர்கள்?", "clarify": "ஒன்றுக்கு மேற்பட்ட தலைப்புகள் பொருந்துகின்றன. எந்த SkillSphere பக்கத்தை விளக்க வேண்டும்?", "restricted": "இந்த SkillSphere பக்கம் உங்கள் கணக்கு வகைக்கு கிடைக்காது.", "login": "Candidate அல்லது recruiter பக்கங்களைத் திறக்க முதலில் sign in செய்யவும்.", "open": "திறக்கவும்"},
    "te": {"found": "ఈ పనికి ధృవీకరించిన SkillSphere పేజీ **{page}** (`{path}`). {guidance}", "unknown": "దీనికి ధృవీకరించిన సూచనలు నా వద్ద లేవు. ఏ SkillSphere పేజీ లేదా పని గురించి అడుగుతున్నారు?", "clarify": "ఒకటి కంటే ఎక్కువ అంశాలు సరిపోతున్నాయి. ఏ SkillSphere పేజీని వివరించాలి?", "restricted": "ఈ SkillSphere పేజీ మీ ఖాతా పాత్రకు అందుబాటులో లేదు.", "login": "Candidate లేదా recruiter పేజీలను తెరవడానికి ముందుగా sign in చేయండి.", "open": "తెరవండి"},
    "mr": {"found": "या कामासाठीचे पडताळलेले SkillSphere पृष्ठ **{page}** (`{path}`) आहे. {guidance}", "unknown": "याबद्दल माझ्याकडे पडताळलेल्या सूचना नाहीत. तुम्ही कोणत्या SkillSphere पृष्ठाबद्दल किंवा कामाबद्दल विचारत आहात?", "clarify": "एकापेक्षा जास्त विषय जुळत आहेत. कोणते SkillSphere पृष्ठ समजावून सांगू?", "restricted": "हे SkillSphere पृष्ठ तुमच्या खाते-भूमिकेसाठी उपलब्ध नाही.", "login": "Candidate किंवा recruiter पृष्ठ उघडण्यासाठी आधी sign in करा.", "open": "उघडा"},
    "gu": {"found": "આ કાર્ય માટેનું ચકાસેલું SkillSphere પેજ **{page}** (`{path}`) છે. {guidance}", "unknown": "આ માટે મારી પાસે ચકાસેલી સૂચનાઓ નથી. તમે કયા SkillSphere પેજ અથવા કાર્ય વિશે પૂછો છો?", "clarify": "એકથી વધુ વિષયો મળ્યા છે. કયું SkillSphere પેજ સમજાવું?", "restricted": "આ SkillSphere પેજ તમારા ખાતાની ભૂમિકા માટે ઉપલબ્ધ નથી.", "login": "Candidate અથવા recruiter પેજ ખોલવા પહેલાં sign in કરો.", "open": "ખોલો"},
    "ml": {"found": "ഈ ജോലിക്കുള്ള പരിശോധിച്ച SkillSphere പേജ് **{page}** (`{path}`) ആണ്. {guidance}", "unknown": "ഇതിനുള്ള സ്ഥിരീകരിച്ച നിർദ്ദേശങ്ങൾ ഇപ്പോൾ എനിക്ക് ലഭ്യമല്ല. ഏത് SkillSphere പേജിനെക്കുറിച്ചാണ് ചോദിക്കുന്നത്?", "clarify": "ഒന്നിലധികം വിഷയങ്ങൾ പൊരുത്തപ്പെടുന്നു. ഏത് SkillSphere പേജ് വിശദീകരിക്കണം?", "restricted": "ഈ SkillSphere പേജ് നിങ്ങളുടെ അക്കൗണ്ട് റോളിന് ലഭ്യമല്ല.", "login": "Candidate അല്ലെങ്കിൽ recruiter പേജുകൾ തുറക്കാൻ ആദ്യം sign in ചെയ്യുക.", "open": "തുറക്കുക"},
    "kn": {"found": "ಈ ಕೆಲಸಕ್ಕೆ ಪರಿಶೀಲಿಸಿದ SkillSphere ಪುಟ **{page}** (`{path}`). {guidance}", "unknown": "ಇದಕ್ಕೆ ಪರಿಶೀಲಿಸಿದ ಸೂಚನೆಗಳು ನನ್ನ ಬಳಿ ಇಲ್ಲ. ಯಾವ SkillSphere ಪುಟ ಅಥವಾ ಕೆಲಸದ ಬಗ್ಗೆ ಕೇಳುತ್ತಿದ್ದೀರಿ?", "clarify": "ಒಂದಕ್ಕಿಂತ ಹೆಚ್ಚು ವಿಷಯಗಳು ಹೊಂದಿಕೆಯಾಗಿವೆ. ಯಾವ SkillSphere ಪುಟವನ್ನು ವಿವರಿಸಲಿ?", "restricted": "ಈ SkillSphere ಪುಟ ನಿಮ್ಮ ಖಾತೆಯ ಪಾತ್ರಕ್ಕೆ ಲಭ್ಯವಿಲ್ಲ.", "login": "Candidate ಅಥವಾ recruiter ಪುಟಗಳನ್ನು ತೆರೆಯಲು ಮೊದಲು sign in ಮಾಡಿ.", "open": "ತೆರೆಯಿರಿ"},
    "es": {"found": "La página verificada de SkillSphere para esta tarea es **{page}** (`{path}`). {guidance}", "unknown": "Aún no tengo instrucciones verificadas para eso. ¿Qué página o tarea de SkillSphere quieres consultar?", "clarify": "Hay varios temas posibles. ¿Qué página o tarea de SkillSphere quieres que explique?", "restricted": "Esa página de SkillSphere no está disponible para el rol de tu cuenta.", "login": "Inicia sesión para abrir páginas de candidatos o reclutadores.", "open": "Abrir"},
    "fr": {"found": "La page SkillSphere vérifiée pour cette tâche est **{page}** (`{path}`). {guidance}", "unknown": "Je n'ai pas encore d'instructions vérifiées à ce sujet. Quelle page ou tâche SkillSphere voulez-vous consulter ?", "clarify": "Plusieurs sujets correspondent. Quelle page ou tâche SkillSphere dois-je expliquer ?", "restricted": "Cette page SkillSphere n'est pas disponible pour le rôle de votre compte.", "login": "Connectez-vous pour ouvrir les pages candidat ou recruteur.", "open": "Ouvrir"},
    "pt": {"found": "A página verificada do SkillSphere para esta tarefa é **{page}** (`{path}`). {guidance}", "unknown": "Ainda não tenho instruções verificadas sobre isso. Qual página ou tarefa do SkillSphere você quer consultar?", "clarify": "Há mais de um assunto possível. Qual página ou tarefa do SkillSphere devo explicar?", "restricted": "Essa página do SkillSphere não está disponível para o perfil da sua conta.", "login": "Entre para abrir páginas de candidato ou recrutador.", "open": "Abrir"},
    "de": {"found": "Die verifizierte SkillSphere-Seite für diese Aufgabe ist **{page}** (`{path}`). {guidance}", "unknown": "Dazu habe ich noch keine verifizierten Anweisungen. Welche SkillSphere-Seite oder Aufgabe meinst du?", "clarify": "Mehrere Themen passen. Welche SkillSphere-Seite oder Aufgabe soll ich erklären?", "restricted": "Diese SkillSphere-Seite ist für die Rolle deines Kontos nicht verfügbar.", "login": "Melde dich an, um Kandidaten- oder Recruiter-Seiten zu öffnen.", "open": "Öffnen"},
    "ar": {"found": "صفحة SkillSphere الموثقة لهذه المهمة هي **{page}** (`{path}`). {guidance}", "unknown": "لا أملك تعليمات موثقة لهذا بعد. ما صفحة أو مهمة SkillSphere التي تقصدها؟", "clarify": "هناك أكثر من موضوع محتمل. ما صفحة SkillSphere التي تريد شرحها؟", "restricted": "صفحة SkillSphere هذه غير متاحة لدور حسابك.", "login": "سجّل الدخول لفتح صفحات المرشح أو مسؤول التوظيف.", "open": "افتح"},
}

VISITOR_SUPPORT_LOGIN = {
    "en": "Visitors need to sign in before they can submit a support ticket.",
    "hi": "Support ticket भेजने के लिए visitors को पहले sign in करना होगा।",
    "hinglish": "Support ticket submit karne ke liye visitors ko pehle sign in karna hoga.",
    "hi_latn": "Support ticket bhejne ke liye visitors ko pehle sign in karna hoga.",
    "pa": "Support ticket ਭੇਜਣ ਲਈ visitor ਨੂੰ ਪਹਿਲਾਂ sign in ਕਰਨਾ ਪਵੇਗਾ।",
    "pa_latn": "Support ticket bhejan layi visitor nu pehlan sign in karna pavega.",
}


NAVIGATION_PROMPTS = {
    "en": "You can open **{page}** using the button below.",
    "hi": "नीचे दिए गए बटन से **{page}** खोलें।",
    "hinglish": "Neeche diye gaye button se **{page}** khol sakte hain.",
    "hi_latn": "Neeche diye gaye button se **{page}** khol sakte hain.",
    "pa": "ਹੇਠਾਂ ਦਿੱਤੇ ਬਟਨ ਨਾਲ **{page}** ਖੋਲ੍ਹੋ।",
    "pa_latn": "Hethaan ditte button naal **{page}** kholo.",
}


LANGUAGE_MARKERS = {
    "hi_latn": {"mera", "meri", "mujhe", "kaise", "kya", "kahan", "chahiye", "nahi", "nhi", "karo", "kro", "kaise", "batao", "btao", "krdo"},
    "pa_latn": {"kive", "kiven", "kidda", "kithon", "kehda", "kehri", "tuhada", "sada", "vich", "layi", "nu", "chahida"},
    "es": {"como", "quiero", "donde", "necesito", "trabajo", "perfil", "curriculo", "solicitud"},
    "fr": {"comment", "voudrais", "profil", "emploi", "candidature", "comment", "mon", "ma"},
    "pt": {"como", "quero", "curriculo", "emprego", "candidatura", "meu", "minha"},
    "de": {"wie", "bitte", "profil", "bewerbung", "lebenslauf", "stelle", "mein", "meine"},
}


def normalize_text(text: str) -> str:
    """Normalize Unicode, case, punctuation and spacing without transliterating scripts."""
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = "".join(char for char in value if unicodedata.category(char) != "Cf")
    value = "".join(char if char.isalnum() or unicodedata.category(char).startswith("M") else " " for char in value)
    return " ".join(value.split())


def detect_language(text: str) -> str:
    """Detect supported scripts and common Romanized language markers locally."""
    value = str(text or "")
    if any(marker in value for marker in ("माझा", "माझे", "माझी", "आहे", "मला")):
        return "mr"
    scripts = {
        "pa": (0x0A00, 0x0A7F), "gu": (0x0A80, 0x0AFF),
        "hi": (0x0900, 0x097F), "bn": (0x0980, 0x09FF),
        "ta": (0x0B80, 0x0BFF), "te": (0x0C00, 0x0C7F),
        "kn": (0x0C80, 0x0CFF), "ml": (0x0D00, 0x0D7F),
    }
    counts = {language: 0 for language in scripts}
    arabic_count = 0
    for char in value:
        point = ord(char)
        for language, (start, end) in scripts.items():
            if start <= point <= end:
                counts[language] += 1
                break
        if 0x0600 <= point <= 0x06FF or 0x0750 <= point <= 0x077F:
            arabic_count += 1
    language, count = max(counts.items(), key=lambda item: item[1])
    if count:
        if language == "hi":
            words = set(normalize_text(value).split())
            if words & {"आहे", "माझा", "माझे", "माझी", "कसा", "कसे", "करा", "करू", "मला"}:
                return "mr"
        return language
    if arabic_count:
        words = set(normalize_text(value).split())
        return "ur" if words & {"ہے", "میرا", "کیسے", "کیا", "آپ", "نہیں"} or "؟" in value else "ar"

    words = set(normalize_text(value).split())
    pa_score = len(words & LANGUAGE_MARKERS["pa_latn"])
    hi_score = len(words & LANGUAGE_MARKERS["hi_latn"])
    if pa_score:
        return "pa_latn"
    if hi_score:
        english_words = {"my", "how", "please", "update", "upload", "help", "resume", "profile", "job", "assessment"}
        return "hinglish" if words & english_words else "hi_latn"
    # Resolve shared words (for example "como" and "profil") with more
    # distinctive vocabulary before broad French/Spanish markers.
    for language in ("pt", "es", "fr", "de"):
        matches = words & LANGUAGE_MARKERS[language]
        if len(matches) >= 2 or (matches and language == "de" and bool(matches & {"wie", "bitte", "bewerbung", "lebenslauf", "stelle"})):
            return language
    return "en"


def routes_for(role: str):
    role_key = str(role or "public").lower()
    if role_key in {"visitor", "public_guest"}:
        role_key = "public"
    allowed = dict(PUBLIC_ROUTES["public"])
    allowed.update(PUBLIC_ROUTES.get(role_key, {}))
    return allowed


def route_for_path(path: str, role: str):
    return routes_for(role).get(path)


def _alias_score(text: str, alias: str) -> float:
    normalized_alias = normalize_text(alias)
    if not normalized_alias:
        return 0.0
    if normalized_alias in text:
        # Prefer a specific phrase over a broad keyword contained in it.
        return min(0.99, 0.76 + 0.045 * len(normalized_alias.split()) + 0.002 * min(len(normalized_alias), 30))
    alias_words = normalized_alias.split()
    if len(normalized_alias) < 5 or not text:
        return 0.0
    words = text.split()[:48]
    target_size = len(alias_words)
    best = 0.0
    for size in range(max(1, target_size - 1), min(len(words), target_size + 1) + 1):
        for start in range(0, len(words) - size + 1):
            candidate = " ".join(words[start:start + size])
            best = max(best, SequenceMatcher(None, normalized_alias, candidate).ratio())
    if best < 0.76:
        return 0.0
    # Fuzzy matches are useful for typos, but must remain below a direct phrase
    # match so a similar neighboring topic cannot make a clear request ambiguous.
    return min(0.84, 0.64 + best * 0.20 + 0.01 * min(len(alias_words), 4))


def match_intent(message: str):
    normalized = normalize_text(message)
    scored = []
    for intent, topic in TOPICS.items():
        score = max((_alias_score(normalized, alias) for alias in topic["aliases"]), default=0.0)
        if score:
            scored.append((score, intent))
    scored.sort(reverse=True)
    if not scored or scored[0][0] < 0.70:
        return {"intent": None, "confidence": scored[0][0] if scored else 0.0, "ambiguous": False}
    exact_lengths = {
        intent: max((len(normalize_text(alias)) for alias in topic["aliases"] if normalize_text(alias) in normalized), default=0)
        for intent, topic in TOPICS.items()
    }
    exact_lengths = {intent: length for intent, length in exact_lengths.items() if length}
    top_exact_length = max(exact_lengths.values(), default=0)
    has_topic_joiner = bool(set(normalized.split()) & {"and", "or", "और", "तथा", "ਤੇ", "اور", "বা", "மற்றும்", "మరియు"})
    ambiguous_exact = len(exact_lengths) > 1 and (
        has_topic_joiner or sum(length == top_exact_length for length in exact_lengths.values()) > 1
    )
    ambiguous = ambiguous_exact or (len(scored) > 1 and scored[0][0] - scored[1][0] < 0.04 and scored[0][0] < 0.96)
    return {"intent": None if ambiguous else scored[0][1], "confidence": scored[0][0], "ambiguous": ambiguous}


FOLLOW_UP_MARKERS = {
    "this", "that", "it", "there", "then", "what next", "and then", "how about", "what about",
    "aur", "uske baad", "phir", "fir", "iska", "iske", "oh", "ਫਿਰ", "ਇਸ ਤੋਂ ਬਾਅਦ", "اور", "اس کے بعد",
    "তারপর", "এরপর", "அடுத்து", "తర్వాత", "नंतर", "પછી", "ശേഷം", "ನಂತರ",
}


def _history_intent(history):
    for item in reversed(history or []):
        role = item.get("role") if isinstance(item, dict) else getattr(item, "role", None)
        text = item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
        if role != "user":
            continue
        matched = match_intent(text)
        if matched["intent"]:
            return matched["intent"]
    return None


def _is_follow_up(message: str) -> bool:
    normalized = normalize_text(message)
    words = normalized.split()
    if len(words) > 7:
        return False
    for marker in FOLLOW_UP_MARKERS:
        normalized_marker = normalize_text(marker)
        if " " in normalized_marker:
            if normalized_marker in normalized:
                return True
        elif normalized_marker in words:
            return True
    return False


def _context_intent(context_path: str, role: str):
    if not route_for_path(context_path or "", role):
        return None
    for intent, topic in TOPICS.items():
        if topic.get("route") == context_path and role.lower() in topic["roles"]:
            return intent
    return None


def answer_website_help(message: str, role: str, context_path: str = "", history=None, language_override=None):
    """Return a verified, role-authorized local Website Help response."""
    language = language_override if language_override in MESSAGES else detect_language(message)
    strings = MESSAGES.get(language, MESSAGES["en"])
    match = match_intent(message)
    intent = match["intent"]
    follow_up = _is_follow_up(message)
    if follow_up and not intent:
        intent = _history_intent(history) or _context_intent(context_path, role)
    if not intent and _context_intent(context_path, role) and (follow_up or len(normalize_text(message).split()) <= 3):
        intent = _context_intent(context_path, role)

    if match["ambiguous"] and not intent:
        return {"reply": strings["clarify"], "ticket_suggestion": False, "actions": [], "language": language}
    if not intent:
        return {"reply": strings["unknown"], "ticket_suggestion": False, "actions": [], "language": language}

    topic = TOPICS[intent]
    role_key = str(role or "public_guest").lower()
    if role_key == "visitor":
        role_key = "public_guest"
    if role_key not in topic["roles"]:
        if role_key == "public_guest" and "candidate" in topic["roles"]:
            return {
                "reply": strings["login"], "ticket_suggestion": False,
                "actions": [{"label": f"{strings['open']}: {PUBLIC_ROUTES['public']['/login']}", "path": "/login"}],
                "language": language,
            }
        return {"reply": strings["restricted"], "ticket_suggestion": False, "actions": [], "language": language}

    route = topic.get("route")
    if intent == "support":
        if role_key == "public_guest":
            login_path = "/login"
            label = route_for_path(login_path, "public")
            return {
                "reply": VISITOR_SUPPORT_LOGIN.get(language, strings["login"]),
                "ticket_suggestion": False,
                "actions": [{"label": f"{strings['open']}: {label}", "path": login_path}],
                "language": language,
            }
        route = {
            "candidate": "/candidate/support", "recruiter": "/recruiter/support", "admin": "/admin/support",
        }.get(role_key)
    label = route_for_path(route, role_key) if route else None
    if not label:
        return {"reply": strings["unknown"], "ticket_suggestion": False, "actions": [], "language": language}

    if intent == "resume_upload" and language == "en":
        reply = "To upload your resume, simply click the button below."
    elif language in NAVIGATION_PROMPTS:
        reply = NAVIGATION_PROMPTS[language].format(page=label)
    else:
        guidance = topic.get("guidance") or ""
        reply = strings["found"].format(page=label, path=route, guidance=guidance).strip()
    action_label = (
        "Open Resume Upload & OCR"
        if intent == "resume_upload"
        else f"{strings['open']}: {label}"
    )
    return {
        "reply": reply,
        "ticket_suggestion": intent == "support",
        "actions": [{"label": action_label, "path": route}],
        "language": language,
    }
