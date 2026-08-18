"""
CivicFix Smart Priority Engine

Calculates transparent, explainable civic priority without black-box ML.
Evaluates severity, scope of impact, public risk, and geographical report density.
"""


def calculate_priority(category, data, nearby_count=0):
    """
    Computes priority ('Low', 'Medium', 'High', 'Critical') and returns the priority and explanation.
    
    Parameters:
        category (str): 'pothole', 'water', or 'waste'
        data (dict or object): contains relevant attributes (road_condition, water_duration, etc.)
        nearby_count (int): count of similar issues reported in the vicinity
        
    Returns:
        tuple: (priority_level: str, explanation: str)
    """
    if isinstance(data, dict):
        get_val = lambda k, default='': data.get(k, default)
    else:
        get_val = lambda k, default='': getattr(data, k, default) or ''

    # 1. Pothole / Road Problems
    if category == 'pothole':
        condition = get_val('road_condition', '')
        severity = get_val('severity', 'Medium')
        
        is_severe_condition = condition in ['Severe road damage', 'Multiple potholes', 'Large pothole']
        has_cluster_pressure = nearby_count >= 3

        if condition == 'Severe road damage' and (has_cluster_pressure or severity == 'High'):
            return (
                'Critical',
                f"Severe road hazard with {nearby_count} nearby incident reports creating high accident potential."
            )
        elif is_severe_condition or severity == 'High' or has_cluster_pressure:
            return (
                'High',
                f"Significant road damage ({condition}) identified with safety risk to commuters ({nearby_count} nearby reports)."
            )
        elif condition == 'Moderate damage' or severity == 'Medium':
            return (
                'Medium',
                "Moderate asphalt degradation causing vehicle slowdown; standard maintenance queue."
            )
        else:
            return (
                'Low',
                "Minor surface imperfection with low risk to vehicular and pedestrian traffic."
            )

    # 2. Water Supply Problems
    elif category == 'water':
        prob_type = get_val('water_problem_type', '')
        duration = get_val('water_duration', '')
        affected = get_val('affected_households', '')

        is_outage = prob_type in ['No water supply', 'Pipeline damage']
        is_long_duration = duration in ['1–3 days', 'More than 3 days']
        is_widespread = affected in ['Many households', 'Large community']

        if is_outage and (is_long_duration or is_widespread):
            return (
                'Critical',
                f"Critical essential utility crisis: '{prob_type}' persisting for '{duration}' impacting '{affected}'."
            )
        elif is_outage or is_widespread or is_long_duration or nearby_count >= 3:
            return (
                'High',
                f"High-impact water disruption ({prob_type}) affecting residential zone for {duration}."
            )
        elif prob_type in ['Low water pressure', 'Irregular supply']:
            return (
                'Medium',
                f"Ongoing water utility irregularity ({prob_type}) reported over {duration}."
            )
        else:
            return (
                'Low',
                "Isolated domestic plumbing or low-impact water supply inquiry."
            )

    # 3. Waste Management
    else:
        waste_type = get_val('waste_type', '')
        accumulation = get_val('waste_accumulation', '')
        duration = get_val('waste_duration', '')

        is_severe_acc = accumulation in ['Severe', 'Large']
        is_long_duration = duration in ['3–7 days', 'More than a week']
        has_cluster = nearby_count >= 3

        if is_severe_acc and (is_long_duration or has_cluster):
            return (
                'High',
                f"Severe solid waste accumulation left uncollected for {duration} ({nearby_count} related vicinity reports) posing hygiene hazard."
            )
        elif is_severe_acc or is_long_duration or waste_type in ['Overflowing bin', 'Construction waste']:
            return (
                'Medium',
                f"Uncollected waste ({waste_type}, {accumulation} volume) accumulating for {duration}."
            )
        else:
            return (
                'Low',
                "Routine residential waste cleanup request."
            )
