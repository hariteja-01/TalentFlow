"""Constants used across the pipeline.

Centralizing magic values here keeps them maintainable and testable.
"""

# ---------------------------------------------------------------------------
# Source reliability weights
# Higher weight = more trusted source. Used in merge conflict resolution
# and confidence scoring.
# ---------------------------------------------------------------------------
SOURCE_WEIGHTS: dict[str, float] = {
    "json": 0.9,   # Structured API/ATS data — usually authoritative
    "csv": 0.7,    # Manual HR exports — often stale or inconsistent
    "resume": 0.6, # Self-reported, regex-parsed — highest error risk
    "github": 0.4, # GitHub profiles are external and unverified
    "linkedin": 0.4, # LinkedIn profile URLs are external
}

# ---------------------------------------------------------------------------
# Default phone region for parsing numbers without a country code
# ---------------------------------------------------------------------------
DEFAULT_PHONE_REGION = "US"

# ---------------------------------------------------------------------------
# Skill alias map: raw name (lowercase) → canonical name
# Keeps skill lists consistent across sources that use different terminology
# ---------------------------------------------------------------------------
SKILL_ALIASES: dict[str, str] = {
    # Languages
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "r": "R",
    "scala": "Scala",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "php": "PHP",
    "matlab": "MATLAB",
    "sql": "SQL",
    "nosql": "NoSQL",
    "html": "HTML",
    "css": "CSS",
    "bash": "Bash",
    "shell": "Shell Scripting",

    # AI / ML
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision",
    "computer vision": "Computer Vision",
    "data science": "Data Science",
    "data engineering": "Data Engineering",
    "data analysis": "Data Analysis",

    # Frameworks
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "svelte": "Svelte",
    "next": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "express": "Express.js",
    "expressjs": "Express.js",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "rails": "Ruby on Rails",
    "ruby on rails": "Ruby on Rails",
    "laravel": "Laravel",

    # Infrastructure / DevOps
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "azure": "Microsoft Azure",
    "git": "Git",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "linux": "Linux",
    "terraform": "Terraform",
    "ansible": "Ansible",

    # Databases
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "mysql": "MySQL",

    # Data tools
    "kafka": "Apache Kafka",
    "spark": "Apache Spark",
    "hadoop": "Hadoop",
    "tableau": "Tableau",
    "power bi": "Power BI",

    # APIs
    "rest": "REST APIs",
    "restful": "REST APIs",
    "rest apis": "REST APIs",
    "graphql": "GraphQL",

    # Methodologies
    "agile": "Agile",
    "scrum": "Scrum",
    
    # Fundamentals
    "data structures": "Data Structures",
    "algorithms": "Algorithms",
    "oop": "Object-Oriented Programming",
    "object-oriented programming": "Object-Oriented Programming",
}

# ---------------------------------------------------------------------------
# Common US state abbreviations → full names (for location normalization)
# ---------------------------------------------------------------------------
US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
