# utils/legal_taxonomy.py

LEGAL_CASE_TYPES = [
    "Family Law",
    "Criminal Law",
    "Labour Law",
    "Property Law",
    "Inheritance Law",
    "Cybercrime",
    "Harassment",
    "Civil Law / Procedure",
    "Contract Law",
    "Consumer Rights",
    "Constitutional Law",
    "General / Other",
]

URGENCY_LEVELS = [
    "Low",
    "Medium",
    "High",
    "Critical",
]

NGO_CATEGORIES = [
    "Family Law",
    "Criminal Law",
    "Labour Law",
    "Property Law",
    "Inheritance Law",
    "Cybercrime",
    "Harassment",
    "Civil Law / Procedure",
    "Contract Law",
    "Consumer Rights",
    "Constitutional Law",
    "General / Other",
]

LAWYER_EXPERTISE_AREAS = NGO_CATEGORIES.copy()

EXPERTISE_SUBAREAS = {
    "Family Law": [
        "Domestic Violence",
        "Child Custody",
        "Divorce",
        "Maintenance",
        "Forced Marriage",
        "Dowry Abuse",
    ],

    "Criminal Law": [
        "Assault",
        "Murder",
        "Theft",
        "Fraud",
        "Bail",
        "FIR Issues",
    ],

    "Labour Law": [
        "Wrongful Termination",
        "Salary Disputes",
        "Workplace Harassment",
        "Child Labour",
    ],

    "Cybercrime": [
        "Online Harassment",
        "Blackmail",
        "Identity Theft",
        "Financial Fraud",
    ],

    "Property Law": [
        "Tenant Disputes",
        "Illegal Eviction",
        "Land Ownership",
    ],
}