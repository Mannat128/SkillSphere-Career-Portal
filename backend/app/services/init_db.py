import logging
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.skill import Skill
from app.models.assessment import TechnicalAssessment, AssessmentQuestion
from app.models.recruiter_assessment import QuestionBankQuestion

logger = logging.getLogger(__name__)

INITIAL_SKILLS = [
    ("Python", "Programming"),
    ("Java", "Programming"),
    ("JavaScript", "Programming"),
    ("TypeScript", "Programming"),
    ("C++", "Programming"),
    ("C#", "Programming"),
    ("Go", "Programming"),
    ("Ruby", "Programming"),
    ("React", "Frontend"),
    ("Vue.js", "Frontend"),
    ("Angular", "Frontend"),
    ("HTML", "Frontend"),
    ("CSS", "Frontend"),
    ("Tailwind CSS", "Frontend"),
    ("Next.js", "Frontend"),
    ("FastAPI", "Backend"),
    ("Flask", "Backend"),
    ("Django", "Backend"),
    ("Node.js", "Backend"),
    ("Express.js", "Backend"),
    ("Spring Boot", "Backend"),
    ("SQL", "Database"),
    ("MySQL", "Database"),
    ("PostgreSQL", "Database"),
    ("MongoDB", "Database"),
    ("Redis", "Database"),
    ("AWS", "Cloud & DevOps"),
    ("Azure", "Cloud & DevOps"),
    ("Google Cloud", "Cloud & DevOps"),
    ("Docker", "Cloud & DevOps"),
    ("Kubernetes", "Cloud & DevOps"),
    ("CI/CD", "Cloud & DevOps"),
    ("Git", "Cloud & DevOps"),
    ("Machine Learning", "AI & Data"),
    ("Data Analytics", "AI & Data"),
    ("Deep Learning", "AI & Data"),
    ("Pandas", "AI & Data"),
    ("NumPy", "AI & Data"),
]

INITIAL_QUESTION_BANK = [
    # Python
    {
        "category": "Python",
        "difficulty": "Easy",
        "question_text": "Which of the following data types in Python is immutable?",
        "option_a": "List",
        "option_b": "Tuple",
        "option_c": "Dictionary",
        "option_d": "Set",
        "correct_answer": "B",
        "marks": 1.0,
        "explanation": "Tuples are immutable sequences in Python; their contents cannot be altered after creation."
    },
    {
        "category": "Python",
        "difficulty": "Medium",
        "question_text": "What is the primary function of the `__init__` method in Python classes?",
        "option_a": "To destroy an object and free memory",
        "option_b": "To initialize the newly created object instance attributes",
        "option_c": "To convert the object to a string representation",
        "option_d": "To make class attributes private",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "`__init__` is the constructor method invoked automatically when an object is instantiated."
    },
    {
        "category": "Python",
        "difficulty": "Hard",
        "question_text": "In Python generator functions, what happens when execution reaches a `yield` statement?",
        "option_a": "The function terminates and returns the final value",
        "option_b": "The function produces a value and suspends its execution state for resumption",
        "option_c": "An exception is raised to stop the loop",
        "option_d": "The variable is added to the global namespace",
        "correct_answer": "B",
        "marks": 3.0,
        "explanation": "`yield` returns the value to the caller and freezes local state until the generator's `__next__()` is called."
    },
    # React
    {
        "category": "React",
        "difficulty": "Easy",
        "question_text": "Which React hook is used to manage local component state in functional components?",
        "option_a": "useEffect",
        "option_b": "useState",
        "option_c": "useContext",
        "option_d": "useReducer",
        "correct_answer": "B",
        "marks": 1.0,
        "explanation": "`useState` declares a state variable and a setter function."
    },
    {
        "category": "React",
        "difficulty": "Medium",
        "question_text": "What is the purpose of passing an empty dependency array `[]` to `useEffect`?",
        "option_a": "It prevents the effect from ever running",
        "option_b": "It runs the effect once after the component mounts",
        "option_c": "It runs the effect on every single state change",
        "option_d": "It causes an infinite rendering loop",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "Passing `[]` tells React the effect depends on no state or props, so it runs only once upon mounting."
    },
    {
        "category": "React",
        "difficulty": "Hard",
        "question_text": "How does `useMemo` differ from `useCallback` in React?",
        "option_a": "`useMemo` caches a calculated value; `useCallback` caches a function definition",
        "option_b": "`useMemo` is for class components; `useCallback` is for functional components",
        "option_c": "`useCallback` runs synchronously; `useMemo` runs asynchronously",
        "option_d": "There is no difference; they are exact aliases",
        "correct_answer": "A",
        "marks": 3.0,
        "explanation": "`useMemo` memoizes the result of an expensive calculation; `useCallback` memoizes the function instance itself."
    },
    # SQL & MySQL
    {
        "category": "SQL",
        "difficulty": "Easy",
        "question_text": "Which SQL clause is used to eliminate duplicate rows from a result set?",
        "option_a": "UNIQUE",
        "option_b": "DISTINCT",
        "option_c": "FILTER",
        "option_d": "DIFFERENT",
        "correct_answer": "B",
        "marks": 1.0,
        "explanation": "`SELECT DISTINCT` filters out identical rows from query output."
    },
    {
        "category": "SQL",
        "difficulty": "Medium",
        "question_text": "What is the crucial difference between the `WHERE` and `HAVING` clauses?",
        "option_a": "`WHERE` filters groups; `HAVING` filters individual rows",
        "option_b": "`WHERE` filters rows before aggregation; `HAVING` filters aggregated groups after GROUP BY",
        "option_c": "`HAVING` can only be used with primary keys",
        "option_d": "`WHERE` cannot use comparison operators",
        "correct_answer": "B",
        "explanation": "`WHERE` filters base rows; `HAVING` operates on grouped/aggregated results."
    },
    {
        "category": "SQL",
        "difficulty": "Hard",
        "question_text": "Which ACID property guarantees that database changes remain permanent even during system crashes?",
        "option_a": "Atomicity",
        "option_b": "Consistency",
        "option_c": "Isolation",
        "option_d": "Durability",
        "correct_answer": "D",
        "marks": 3.0,
        "explanation": "Durability guarantees that once a transaction commits, its effects survive power loss or crashes."
    },
    # JavaScript
    {
        "category": "JavaScript",
        "difficulty": "Easy",
        "question_text": "What is the return value of `typeof null` in standard JavaScript?",
        "option_a": "'null'",
        "option_b": "'undefined'",
        "option_c": "'object'",
        "option_d": "'boolean'",
        "correct_answer": "C",
        "marks": 1.0,
        "explanation": "`typeof null` returns 'object' due to a historical legacy bug preserved for backward compatibility."
    },
    {
        "category": "JavaScript",
        "difficulty": "Medium",
        "question_text": "In the JavaScript Event Loop, which queue is given immediate priority after call stack clears?",
        "option_a": "Macrotasks (e.g., setTimeout)",
        "option_b": "Microtasks (e.g., Promise callbacks, queueMicrotask)",
        "option_c": "Render animation frames only",
        "option_d": "I/O network callbacks",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "Microtasks are always processed completely before the event loop advances to the next macrotask."
    },
    {
        "category": "JavaScript",
        "difficulty": "Hard",
        "question_text": "What is a closure in JavaScript?",
        "option_a": "A syntax rule requiring brackets around function declarations",
        "option_b": "The combination of a function bundled together with references to its surrounding lexical environment",
        "option_c": "A method to delete variables from memory immediately",
        "option_d": "An event listener that only triggers once",
        "correct_answer": "B",
        "marks": 3.0,
        "explanation": "A closure gives an inner function access to an outer function's scope even after the outer function has returned."
    },
    # FastAPI
    {
        "category": "FastAPI",
        "difficulty": "Easy",
        "question_text": "Which library powers data parsing and validation in FastAPI?",
        "option_a": "Marshmallow",
        "option_b": "Pydantic",
        "option_c": "Cerberus",
        "option_d": "Attrs",
        "correct_answer": "B",
        "marks": 1.0,
        "explanation": "FastAPI is built natively on Pydantic for request and response validation."
    },
    {
        "category": "FastAPI",
        "difficulty": "Medium",
        "question_text": "How do you declare a dependency in a FastAPI route handler function?",
        "option_a": "param = Inject(get_dependency)",
        "option_b": "param = Depends(get_dependency)",
        "option_c": "@fastapi.depends(get_dependency)",
        "option_d": "param: Require(get_dependency)",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "FastAPI utilizes `Depends()` in default parameter arguments to inject dependencies."
    },
    {
        "category": "FastAPI",
        "difficulty": "Hard",
        "question_text": "What HTTP status code does FastAPI automatically return when request body validation fails?",
        "option_a": "400 Bad Request",
        "option_b": "422 Unprocessable Entity",
        "option_c": "500 Internal Server Error",
        "option_d": "404 Not Found",
        "correct_answer": "B",
        "marks": 3.0,
        "explanation": "FastAPI returns 422 Unprocessable Entity with error location and messages when validation fails."
    },
    # Java
    {
        "category": "Java",
        "difficulty": "Easy",
        "question_text": "Which keyword is used in Java to prevent a method from being overridden by subclasses?",
        "option_a": "static",
        "option_b": "final",
        "option_c": "abstract",
        "option_d": "const",
        "correct_answer": "B",
        "marks": 1.0,
        "explanation": "The `final` keyword prevents method overriding and class inheritance."
    },
    {
        "category": "Java",
        "difficulty": "Medium",
        "question_text": "What is the underlying data structure of Java's `ArrayList`?",
        "option_a": "Doubly linked list",
        "option_b": "Resizable dynamic array",
        "option_c": "Binary search tree",
        "option_d": "Hash table",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "`ArrayList` uses a dynamically resizing array to store elements."
    },
    {
        "category": "Java",
        "difficulty": "Hard",
        "question_text": "What guarantee does the `volatile` keyword provide in multi-threaded Java?",
        "option_a": "Mutual exclusion locking like synchronized",
        "option_b": "Visibility of variable modifications across threads by reading directly from main memory",
        "option_c": "Prevents garbage collection of the variable",
        "option_d": "Compiles the variable to native assembly code",
        "correct_answer": "B",
        "marks": 3.0,
        "explanation": "`volatile` establishes a happens-before relationship, guaranteeing thread memory visibility."
    },
    # Data Structures & Algorithms
    {
        "category": "Data Structures and Algorithms",
        "difficulty": "Easy",
        "question_text": "What is the time complexity of searching an element in a balanced Binary Search Tree (BST)?",
        "option_a": "O(1)",
        "option_b": "O(log N)",
        "option_c": "O(N)",
        "option_d": "O(N log N)",
        "correct_answer": "B",
        "marks": 1.0,
        "explanation": "In a balanced BST, half of remaining elements are eliminated at each step, yielding O(log N)."
    },
    {
        "category": "Data Structures and Algorithms",
        "difficulty": "Medium",
        "question_text": "Which sorting algorithm exhibits the best worst-case time complexity of O(N log N)?",
        "option_a": "Quick Sort",
        "option_b": "Merge Sort",
        "option_c": "Bubble Sort",
        "option_d": "Insertion Sort",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "Merge Sort consistently guarantees O(N log N) in best, average, and worst cases."
    },
    {
        "category": "Data Structures and Algorithms",
        "difficulty": "Hard",
        "question_text": "Which graph algorithm is optimal for finding the shortest path in a weighted graph with non-negative edges?",
        "option_a": "Depth-First Search (DFS)",
        "option_b": "Dijkstra's Algorithm",
        "option_c": "Floyd-Warshall",
        "option_d": "Kruskal's Algorithm",
        "correct_answer": "B",
        "marks": 3.0,
        "explanation": "Dijkstra's algorithm finds shortest paths from a source to all vertices with non-negative edge weights."
    },
    # Computer Networks
    {
        "category": "Computer Networks",
        "difficulty": "Easy",
        "question_text": "Which transport layer protocol provides connection-oriented, reliable byte-stream transmission?",
        "option_a": "UDP",
        "option_b": "TCP",
        "option_c": "IP",
        "option_d": "ICMP",
        "correct_answer": "B",
        "marks": 1.0,
        "explanation": "TCP establishes a 3-way handshake and handles sequence numbering, acknowledgments, and retransmission."
    },
    {
        "category": "Computer Networks",
        "difficulty": "Medium",
        "question_text": "What is the default port number used by HTTPS connections?",
        "option_a": "80",
        "option_b": "443",
        "option_c": "8080",
        "option_d": "22",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "Standard HTTPS traffic runs over TCP port 443."
    },
    # Aptitude
    {
        "category": "Aptitude",
        "difficulty": "Easy",
        "question_text": "If a train travels 120 km in 2 hours, what is its average speed in meters per second (m/s)?",
        "option_a": "16.67 m/s",
        "option_b": "20.50 m/s",
        "option_c": "25.00 m/s",
        "option_d": "30.00 m/s",
        "correct_answer": "A",
        "marks": 1.0,
        "explanation": "Speed = 120 km / 2 h = 60 km/h. Convert to m/s: 60 * (5/18) = 16.67 m/s."
    },
    {
        "category": "Aptitude",
        "difficulty": "Medium",
        "question_text": "A can finish a task in 10 days, and B in 15 days. How long will it take them working together?",
        "option_a": "5 days",
        "option_b": "6 days",
        "option_c": "7.5 days",
        "option_d": "8 days",
        "correct_answer": "B",
        "marks": 2.0,
        "explanation": "Combined rate = 1/10 + 1/15 = 5/30 = 1/6 task per day. Total time = 6 days."
    }
]

def init_db(db: Session) -> None:
    """
    Initialize database:
    1. Seed Admin user from environment.
    2. Seed technical skills.
    3. Seed Admin-approved shared Question Bank questions.
    """
    admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if not admin:
        logger.info(f"Provisioning initial Platform Admin: {settings.ADMIN_EMAIL}")
        admin = User(
            email=settings.ADMIN_EMAIL,
            full_name=settings.ADMIN_NAME,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    # Seed Skills
    existing_skills = {s.name for s in db.query(Skill.name).all()}
    for name, category in INITIAL_SKILLS:
        if name not in existing_skills:
            skill = Skill(name=name, category=category)
            db.add(skill)
    db.commit()

    # Seed Shared Question Bank
    if db.query(QuestionBankQuestion).count() == 0:
        logger.info("Seeding Admin-approved Shared Question Bank...")
        for q in INITIAL_QUESTION_BANK:
            question = QuestionBankQuestion(
                recruiter_id=None, # Shared across all recruiters
                created_by_id=admin.id if admin else None,
                is_shared=True,
                question_text=q["question_text"],
                category=q["category"],
                difficulty=q["difficulty"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                correct_answer=q["correct_answer"],
                marks=q.get("marks", 1.0),
                explanation=q.get("explanation")
            )
            db.add(question)
        db.commit()
        logger.info(f"Seeded {len(INITIAL_QUESTION_BANK)} shared Question Bank questions.")
