import json
import logging
import re
from django.conf import settings

logger = logging.getLogger(__name__)

# Fallback department mapping
CATEGORY_DEPARTMENTS = {
    'pothole': 'Road Maintenance',
    'water': 'Water Supply Department',
    'waste': 'Waste Management',
}


def analyze_issue(category, title, description, extra_context=None):
    """
    Analyzes a civic issue using Groq API (Llama 3) with fallback to rule-based analysis.
    
    Parameters:
        category (str): 'pothole', 'water', or 'waste'
        title (str): Resident's title
        description (str): Resident's problem description
        extra_context (dict, optional): Category-specific form values (road_condition, water_duration, etc.)
        
    Returns:
        dict: Structured AI analysis dictionary with fallback support.
    """
    extra_context = extra_context or {}
    api_key = getattr(settings, 'GROQ_API_KEY', '').strip()

    # If API key is not configured, immediately use intelligent rule-based fallback
    if not api_key:
        logger.info("GROQ_API_KEY not configured. Using rule-based fallback analyzer.")
        return fallback_rule_analysis(category, title, description, extra_context, reason="API key not provided")

    try:
        from groq import Groq
        client = Groq(api_key=api_key, timeout=10.0)

        prompt_system = (
            "You are CivicFix AI, an intelligent civic task converter. "
            "Your job is to analyze resident complaints regarding civic infrastructure (Potholes/Roads, Water Supply, Waste Management) "
            "and convert them into a structured, actionable municipal task for civic administrators.\n"
            "You MUST respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "issue_type": "<Short issue classification, e.g. Deep Pothole / Main Pipeline Leakage / Overflowing Garbage>",\n'
            '  "severity": "<Low | Medium | High | Critical>",\n'
            '  "priority": "<Low | Medium | High | Critical>",\n'
            '  "safety_risk": "<Concise risk assessment, e.g. High accident risk for two-wheelers>",\n'
            '  "impact": "<Affected population / traffic impact assessment>",\n'
            '  "summary": "<1-2 sentence executive summary of the civic problem>",\n'
            '  "recommended_department": "<Road Maintenance | Water Supply Department | Waste Management>",\n'
            '  "recommended_action": "<Clear actionable steps for municipal field crew>"\n'
            "}"
        )

        user_content = (
            f"Civic Category: {category}\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Additional Context Data: {json.dumps(extra_context, ensure_ascii=False)}"
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=600,
        )

        raw_content = response.choices[0].message.content
        data = json.loads(raw_content)

        return {
            "issue_type": data.get("issue_type") or default_issue_type(category),
            "severity": normalize_level(data.get("severity"), "Medium"),
            "priority": normalize_level(data.get("priority"), "Medium"),
            "safety_risk": data.get("safety_risk", "General civic safety concern"),
            "impact": data.get("impact", "Local residents affected"),
            "summary": data.get("summary", title),
            "recommended_department": data.get("recommended_department") or CATEGORY_DEPARTMENTS.get(category, "General Civic Services"),
            "recommended_action": data.get("recommended_action", "Dispatch inspection crew to site."),
            "ai_available": True,
        }

    except Exception as exc:
        logger.warning(f"Groq API call failed or encountered error: {exc}. Using fallback analyzer.")
        return fallback_rule_analysis(category, title, description, extra_context, reason=str(exc))


def fallback_rule_analysis(category, title, description, extra_context=None, reason=""):
    """
    Deterministic rule-based NLP extraction when Groq API is offline, rate-limited, or unconfigured.
    """
    extra_context = extra_context or {}
    text = f"{title} {description}".lower()
    
    # 1. Pothole / Road Damage
    if category == 'pothole' or any(k in text for k in ['pothole', 'road', 'asphalt', 'crater', 'crack', 'pavement']):
        road_cond = extra_context.get('road_condition', '').lower()
        severity_in = extra_context.get('severity', 'Medium')
        
        is_severe = any(w in text for w in ['huge', 'massive', 'deep', 'dangerous', 'bike fall', 'accident', 'severe', 'large']) or ('severe' in road_cond or 'large' in road_cond or 'multiple' in road_cond)
        
        if is_severe or severity_in == 'High':
            severity = 'High'
            priority = 'High'
            safety_risk = 'Severe accident risk for two-wheelers and pedestrians; vehicle tire/suspension damage'
            impact = 'Commuters and heavy vehicular flow on this route are impeded'
            summary = f"Severe road damage/pothole requiring rapid asphalt patching: {title}"
            action = "Dispatch Road Maintenance asphalt patching team with road roller and safety warning cones."
        else:
            severity = severity_in if severity_in in ['Low', 'Medium', 'High'] else 'Medium'
            priority = 'Medium'
            safety_risk = 'Moderate traffic slowing and localized hazard'
            impact = 'Local road users and neighborhood traffic'
            summary = f"Road defect identified on transit route: {title}"
            action = "Schedule site inspection and add to upcoming road resurfacing batch."

        return {
            "issue_type": "Pothole / Road Surface Damage",
            "severity": severity,
            "priority": priority,
            "safety_risk": safety_risk,
            "impact": impact,
            "summary": summary,
            "recommended_department": "Road Maintenance",
            "recommended_action": action,
            "ai_available": False,
        }

    # 2. Water Supply Problems
    elif category == 'water' or any(k in text for k in ['water', 'pipe', 'leak', 'pipeline', 'pressure', 'tap', 'contamination']):
        prob_type = extra_context.get('water_problem_type', '').lower()
        duration = extra_context.get('water_duration', '').lower()
        affected = extra_context.get('affected_households', '').lower()
        
        is_outage = 'no water' in text or 'no water' in prob_type or 'burst' in text or 'broken' in text
        is_prolonged = 'day' in duration or 'week' in duration
        is_large_area = 'many' in affected or 'community' in affected or 'neighborhood' in text
        
        if is_outage or is_prolonged or is_large_area:
            severity = 'Critical' if (is_outage and is_prolonged) else 'High'
            priority = 'Critical' if (is_outage and is_large_area) else 'High'
            safety_risk = 'Public health concern, sanitation disruption, and potential water contamination'
            impact = 'Multiple households experiencing domestic water crisis'
            summary = f"Urgent water supply disruption reported: {title}"
            action = "Deploy Water Supply emergency pipeline technician team to locate line fault and restore mains pressure."
        else:
            severity = 'Medium'
            priority = 'Medium'
            safety_risk = 'Minor domestic disruption and non-potable waste'
            impact = 'Localized household water connection'
            summary = f"Water utility irregularity reported: {title}"
            action = "Send plumbing inspector to check local valve chamber and pipeline pressure."

        return {
            "issue_type": "Water Supply Outage / Pipeline Defect",
            "severity": severity,
            "priority": priority,
            "safety_risk": safety_risk,
            "impact": impact,
            "summary": summary,
            "recommended_department": "Water Supply Department",
            "recommended_action": action,
            "ai_available": False,
        }

    # 3. Waste Management
    else:
        waste_type = extra_context.get('waste_type', '').lower()
        accumulation = extra_context.get('waste_accumulation', '').lower()
        duration = extra_context.get('waste_duration', '').lower()
        
        is_severe = 'severe' in accumulation or 'large' in accumulation or 'overflowing' in waste_type or any(w in text for w in ['stink', 'smell', 'overflow', 'dump', 'huge pile', 'rats', 'hazard'])
        is_old = 'week' in duration or '3–7' in duration
        
        if is_severe or is_old:
            severity = 'High'
            priority = 'High'
            safety_risk = 'Vector-borne disease risk, stray animal attraction, and noxious odor'
            impact = 'Pedestrians and nearby residents in surrounding vicinity'
            summary = f"Significant garbage accumulation requiring sanitation truck: {title}"
            action = "Dispatch Waste Management compactor truck and sanitation team for immediate clearance and disinfectant spray."
        else:
            severity = 'Medium'
            priority = 'Medium'
            safety_risk = 'Aesthetic degradation and minor public hygiene concern'
            impact = 'Local residential sector'
            summary = f"Waste collection request logged: {title}"
            action = "Add site to the next scheduled daily municipal garbage collection route."

        return {
            "issue_type": "Solid Waste Accumulation / Overflowing Bin",
            "severity": severity,
            "priority": priority,
            "safety_risk": safety_risk,
            "impact": impact,
            "summary": summary,
            "recommended_department": "Waste Management",
            "recommended_action": action,
            "ai_available": False,
        }


def default_issue_type(category):
    defaults = {
        'pothole': 'Road Damage / Pothole',
        'water': 'Water Supply Disruption',
        'waste': 'Waste Accumulation',
    }
    return defaults.get(category, 'Civic Infrastructure Issue')


def normalize_level(val, fallback="Medium"):
    if not val:
        return fallback
    clean = str(val).strip().capitalize()
    if clean in ['Low', 'Medium', 'High', 'Critical']:
        return clean
    return fallback
