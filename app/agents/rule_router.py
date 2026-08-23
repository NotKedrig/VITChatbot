import re

def rule_route(utterance: str) -> str:
    """
    A standalone, genuinely competent regex/keyword-based baseline router.
    Used for Experiment 2 to compare against the LLM Supervisor.
    """
    text = utterance.lower()

    # Define regex patterns carefully so this acts as a strong baseline, not a strawman.
    
    # Notifications/Reminders
    if re.search(r'\b(remind|reminder|alert|alarm|notify|deadline)\b', text):
        return "notification"
        
    # Progress/Performance
    if re.search(r'\b(progress|failed|passed|struggling|stuck|finished|completed|score|result|marks|performance)\b', text):
        return "progress"
        
    # Study Planning
    if re.search(r'\b(plan|timetable|schedule|curriculum|what to study|syllabus|routine|organize|roadmap)\b', text):
        return "planner"
        
    # Company Research (default fallback, but let's give it strong keywords too)
    if re.search(r'\b(company|salary|ctc|eligibility|cgpa|rounds|interview|hiring|recruitment|process|stipend|role|novatech|aether|meridian)\b', text):
        return "company_research"

    # Default fallback
    return "company_research"
