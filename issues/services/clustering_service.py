import math
from ..models import CivicIssue


def haversine_distance_km(lat1, lon1, lat2, lon2):
    """
    Computes great-circle distance between two points on the Earth using Haversine formula in kilometers.
    """
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')

    r = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def find_nearby_reports(lat, lng, category=None, radius_km=0.8, exclude_id=None, unresolved_only=True):
    """
    Finds existing issues within `radius_km` of given (lat, lng).
    
    Returns:
        list of dicts containing issue object and distance in meters.
    """
    if lat is None or lng is None:
        return []

    # Rough bounding box filter first (1 deg lat ~ 111km)
    lat_delta = radius_km / 110.0
    lng_delta = radius_km / (110.0 * math.cos(math.radians(lat)) if math.cos(math.radians(lat)) != 0 else 110.0)

    qs = CivicIssue.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=lat - lat_delta,
        latitude__lte=lat + lat_delta,
        longitude__gte=lng - lng_delta,
        longitude__lte=lng + lng_delta,
    )

    if category:
        qs = qs.filter(issue_category=category)

    if unresolved_only:
        qs = qs.exclude(status__in=[CivicIssue.STATUS_RESOLVED, CivicIssue.STATUS_REJECTED])

    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    results = []
    for issue in qs:
        dist_km = haversine_distance_km(lat, lng, issue.latitude, issue.longitude)
        if dist_km <= radius_km:
            results.append({
                'issue': issue,
                'distance_km': round(dist_km, 2),
                'distance_m': int(dist_km * 1000),
            })

    results.sort(key=lambda x: x['distance_km'])
    return results


def detect_issue_clusters(radius_km=0.8, min_reports=3):
    """
    Detects geographic clusters of active/unresolved civic issues per category.
    Used for Civic Action Center intelligent alerts.
    
    Returns:
        list of cluster dicts:
        [
            {
                'id': 'cluster-pothole-1',
                'category': 'pothole',
                'category_display': 'Pothole',
                'title': 'POTHOLE CLUSTER',
                'count': 7,
                'center_lat': 12.9716,
                'center_lng': 77.5946,
                'location_label': 'College Road Area',
                'priority': 'Critical' | 'High',
                'urgency_color': 'danger' | 'warning',
                'summary': '7 reports around College Road with severe vehicle safety hazard',
                'recommended_action': 'Immediate road inspection and batch resurfacing',
                'issues': [issue1, issue2, ...]
            },
            ...
        ]
    """
    active_issues = list(CivicIssue.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    ).exclude(
        status__in=[CivicIssue.STATUS_RESOLVED, CivicIssue.STATUS_REJECTED]
    ).order_by('-created_at'))

    clusters = []
    visited_ids = set()

    for category in [CivicIssue.CATEGORY_POTHOLE, CivicIssue.CATEGORY_WATER, CivicIssue.CATEGORY_WASTE]:
        cat_issues = [i for i in active_issues if i.issue_category == category and i.id not in visited_ids]

        for issue in cat_issues:
            if issue.id in visited_ids:
                continue

            # Find all neighbors within radius_km
            group = [issue]
            for other in cat_issues:
                if other.id != issue.id and other.id not in visited_ids:
                    dist = haversine_distance_km(issue.latitude, issue.longitude, other.latitude, other.longitude)
                    if dist <= radius_km:
                        group.append(other)

            if len(group) >= min_reports:
                for item in group:
                    visited_ids.add(item.id)

                center_lat = sum(i.latitude for i in group) / len(group)
                center_lng = sum(i.longitude for i in group) / len(group)

                # Determine highest priority in group
                priorities = [i.priority for i in group]
                if 'Critical' in priorities:
                    cluster_priority = 'Critical'
                    urgency_color = 'danger'
                elif 'High' in priorities or len(group) >= 5:
                    cluster_priority = 'High'
                    urgency_color = 'warning'
                else:
                    cluster_priority = 'Medium'
                    urgency_color = 'primary'

                # Determine location label
                locations = [i.location_name for i in group if i.location_name]
                location_label = locations[0] if locations else "Dense Municipal Zone"

                cat_name = dict(CivicIssue.CATEGORY_CHOICES).get(category, category).upper()
                
                # Category-specific action advice
                if category == CivicIssue.CATEGORY_POTHOLE:
                    title = "POTHOLE CLUSTER"
                    rec = "Immediate road inspection, traffic warning signage, and batch asphalt repair."
                elif category == CivicIssue.CATEGORY_WATER:
                    title = "WATER SUPPLY CLUSTER"
                    rec = "Urgent mainline valve inspection and emergency water tanker dispatch."
                else:
                    title = "WASTE ACCUMULATION CLUSTER"
                    rec = "Immediate garbage compactor truck dispatch and sanitation clearing."

                clusters.append({
                    'id': f"cluster-{category}-{len(clusters) + 1}",
                    'category': category,
                    'category_display': dict(CivicIssue.CATEGORY_CHOICES).get(category, category),
                    'title': title,
                    'count': len(group),
                    'center_lat': round(center_lat, 6),
                    'center_lng': round(center_lng, 6),
                    'location_label': location_label,
                    'priority': cluster_priority,
                    'urgency_color': urgency_color,
                    'recommended_action': rec,
                    'issues': group,
                })

    # Sort clusters by priority and count
    priority_weights = {'Critical': 3, 'High': 2, 'Medium': 1, 'Low': 0}
    clusters.sort(key=lambda c: (priority_weights.get(c['priority'], 0), c['count']), reverse=True)

    return clusters
