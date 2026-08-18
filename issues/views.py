import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q

from .models import CivicIssue, UserProfile, get_user_profile
from .forms import PotholeReportForm, WaterReportForm, WasteReportForm, AdminActionForm
from .services.ai_service import analyze_issue
from .services.priority_service import calculate_priority
from .services.clustering_service import find_nearby_reports, detect_issue_clusters
from .services.exif_service import extract_image_gps, analyze_photo_location_with_ai


def is_staff_or_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser or user.groups.filter(name='CivicAdmin').exists())


# ==========================================
# 1. LANDING PAGE
# ==========================================

def home(request):
    """
    Public Landing Page for CivicFix.
    """
    # System Statistics from database
    total_count = CivicIssue.objects.count()
    resolved_count = CivicIssue.objects.filter(status=CivicIssue.STATUS_RESOLVED).count()
    pothole_count = CivicIssue.objects.filter(issue_category=CivicIssue.CATEGORY_POTHOLE).count()
    water_count = CivicIssue.objects.filter(issue_category=CivicIssue.CATEGORY_WATER).count()
    waste_count = CivicIssue.objects.filter(issue_category=CivicIssue.CATEGORY_WASTE).count()

    # Recent resolved proof showcase
    resolved_showcase = CivicIssue.objects.filter(
        status=CivicIssue.STATUS_RESOLVED,
        resolution_image__isnull=False
    ).exclude(resolution_image='').order_by('-resolved_at')[:3]

    context = {
        'total_count': total_count,
        'resolved_count': resolved_count,
        'pothole_count': pothole_count,
        'water_count': water_count,
        'waste_count': waste_count,
        'resolved_showcase': resolved_showcase,
    }
    return render(request, 'issues/home.html', context)


# ==========================================
# 2. RESIDENT REPORTING FLOW
# ==========================================

def report_issue(request):
    """
    Step 1 & Step 2 Resident Reporting.
    Dynamic form selection based on category.
    """
    selected_category = request.GET.get('category', '').lower()
    
    if selected_category not in [CivicIssue.CATEGORY_POTHOLE, CivicIssue.CATEGORY_WATER, CivicIssue.CATEGORY_WASTE]:
        # Render category selection screen if not chosen yet
        return render(request, 'issues/report_select.html')

    form_class = {
        CivicIssue.CATEGORY_POTHOLE: PotholeReportForm,
        CivicIssue.CATEGORY_WATER: WaterReportForm,
        CivicIssue.CATEGORY_WASTE: WasteReportForm,
    }[selected_category]

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.issue_category = selected_category
            
            if request.user.is_authenticated:
                issue.user = request.user
                if not issue.reporter_name:
                    issue.reporter_name = request.user.get_full_name() or request.user.username

            # Automatic EXIF GPS Extraction from Photo
            if issue.image and (not issue.latitude or not issue.longitude):
                photo_lat, photo_lng = extract_image_gps(issue.image)
                if photo_lat and photo_lng:
                    issue.latitude = photo_lat
                    issue.longitude = photo_lng
                    if not issue.location_name:
                        issue.location_name = f"Photo GPS ({photo_lat}, {photo_lng})"

            # Extract category extra context
            extra_ctx = {}
            if selected_category == CivicIssue.CATEGORY_POTHOLE:
                extra_ctx = {
                    'road_condition': issue.road_condition,
                    'severity': issue.severity,
                }
            elif selected_category == CivicIssue.CATEGORY_WATER:
                extra_ctx = {
                    'water_problem_type': issue.water_problem_type,
                    'water_duration': issue.water_duration,
                    'affected_households': issue.affected_households,
                }
            elif selected_category == CivicIssue.CATEGORY_WASTE:
                extra_ctx = {
                    'waste_type': issue.waste_type,
                    'waste_accumulation': issue.waste_accumulation,
                    'waste_duration': issue.waste_duration,
                }

            # AI Analysis & Fallback
            ai_data = analyze_issue(
                category=selected_category,
                title=issue.title,
                description=issue.description,
                extra_context=extra_ctx
            )

            # Check nearby reports
            nearby = []
            if issue.latitude and issue.longitude:
                nearby = find_nearby_reports(
                    lat=issue.latitude,
                    lng=issue.longitude,
                    category=selected_category,
                    radius_km=0.8
                )


            # Smart Priority calculation
            smart_priority, priority_reason = calculate_priority(
                category=selected_category,
                data=issue,
                nearby_count=len(nearby)
            )

            # Store AI & Smart Priority data on instance
            issue.issue_type = ai_data.get('issue_type') or 'Civic Problem'
            issue.severity = ai_data.get('severity') or issue.severity or 'Medium'
            issue.priority = smart_priority or ai_data.get('priority') or 'Medium'
            issue.safety_risk = ai_data.get('safety_risk', '')
            issue.impact = ai_data.get('impact', '')
            issue.ai_summary = ai_data.get('summary', '')
            issue.recommended_department = ai_data.get('recommended_department', '')
            issue.recommended_action = ai_data.get('recommended_action', '')
            issue.ai_available = ai_data.get('ai_available', True)
            issue.status = CivicIssue.STATUS_SUBMITTED

            issue.save()

            # Award citizen karma points
            karma_msg = ""
            if request.user.is_authenticated:
                profile = get_user_profile(request.user)
                if profile:
                    points_earned = 50
                    if issue.image:
                        points_earned += 15
                    if issue.latitude and issue.longitude:
                        points_earned += 10
                    profile.add_points(points_earned, f"Reported issue #{issue.tracking_code}")
                    profile.reports_count += 1
                    profile.save(update_fields=['reports_count'])
                    karma_msg = f" 🌟 +{points_earned} Citizen Karma Points earned! Total: {profile.points} pts ({profile.badge_title})."

            # Save tracking code in session for resident easy access
            session_codes = request.session.get('my_tracking_codes', [])
            if issue.tracking_code not in session_codes:
                session_codes.append(issue.tracking_code)
                request.session['my_tracking_codes'] = session_codes

            messages.success(
                request,
                f"Report #{issue.tracking_code} submitted successfully! Our AI prioritized it as '{issue.priority}'.{karma_msg}"
            )
            return redirect('track_detail', tracking_code=issue.tracking_code)

    else:
        form = form_class()

    context = {
        'form': form,
        'category': selected_category,
        'category_display': dict(CivicIssue.CATEGORY_CHOICES).get(selected_category),
    }
    return render(request, 'issues/report.html', context)


# ==========================================
# 3. AI ANALYZE PREVIEW API
# ==========================================

@csrf_exempt
@require_POST
def api_analyze_preview(request):
    """
    AJAX endpoint called when resident clicks 'Analyze Report'
    Runs AI analysis, nearby check, and smart priority calculation without saving yet.
    """

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    category = data.get('category', 'pothole')
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    lat = data.get('latitude')
    lng = data.get('longitude')

    if not title:
        title = f"Reported {category.capitalize()} Issue"
    if not description:
        description = f"{category.capitalize()} incident requiring municipal evaluation and action."


    try:
        lat = float(lat) if lat else None
        lng = float(lng) if lng else None
    except (ValueError, TypeError):
        lat, lng = None, None

    extra_ctx = {
        'road_condition': data.get('road_condition'),
        'severity': data.get('severity'),
        'water_problem_type': data.get('water_problem_type'),
        'water_duration': data.get('water_duration'),
        'affected_households': data.get('affected_households'),
        'waste_type': data.get('waste_type'),
        'waste_accumulation': data.get('waste_accumulation'),
        'waste_duration': data.get('waste_duration'),
    }

    # Run AI
    ai_result = analyze_issue(category, title, description, extra_ctx)

    # Check Nearby
    nearby_items = []
    if lat and lng:
        nearby = find_nearby_reports(lat, lng, category=category, radius_km=0.8)
        nearby_items = [{
            'tracking_code': item['issue'].tracking_code,
            'title': item['issue'].title,
            'distance_m': item['distance_m'],
            'status': item['issue'].status,
            'priority': item['issue'].priority,
        } for item in nearby[:5]]

    # Priority
    priority, explanation = calculate_priority(category, extra_ctx, nearby_count=len(nearby_items))

    return JsonResponse({
        'ai_analysis': ai_result,
        'smart_priority': priority,
        'priority_explanation': explanation,
        'nearby_count': len(nearby_items),
        'nearby_reports': nearby_items,
    })


@csrf_exempt
@require_POST
def api_extract_photo_gps(request):
    """
    AJAX endpoint called when user uploads a photo.
    Extracts embedded EXIF GPS tags (latitude, longitude) and runs Groq AI Location Analysis.
    """
    if 'image' not in request.FILES:
        return JsonResponse({'has_gps': False, 'error': 'No image file uploaded.'}, status=400)

    image_file = request.FILES['image']
    category = request.POST.get('category', 'pothole')
    filename = getattr(image_file, 'name', 'photo.jpg')

    analysis = analyze_photo_location_with_ai(image_file, category=category, filename=filename)
    return JsonResponse(analysis)



# ==========================================
# 4. RESIDENT TRACKING & MY REPORTS
# ==========================================

def my_reports(request):
    """
    Shows reports submitted by resident (authenticated or via session tracking).
    """
    user_issues = CivicIssue.objects.none()
    if request.user.is_authenticated:
        user_issues = CivicIssue.objects.filter(user=request.user)

    session_codes = request.session.get('my_tracking_codes', [])
    session_issues = CivicIssue.objects.filter(tracking_code__in=session_codes)

    # Combined distinct query
    issues = (user_issues | session_issues).distinct().order_by('-created_at')
    user_profile = get_user_profile(request.user) if request.user.is_authenticated else None

    context = {
        'issues': issues,
        'has_reports': issues.exists(),
        'user_profile': user_profile,
    }
    return render(request, 'issues/my_reports.html', context)


def track_detail(request, tracking_code):
    """
    Detailed public/resident tracking page for a specific issue.
    Shows 5-stage timeline and Before/After resolution proof if resolved.
    """
    issue = get_object_or_404(CivicIssue, tracking_code=tracking_code.upper().strip())
    timeline_stages = issue.get_timeline_stages()
    nearby = []
    if issue.latitude and issue.longitude:
        nearby = find_nearby_reports(issue.latitude, issue.longitude, category=issue.issue_category, exclude_id=issue.id)

    context = {
        'issue': issue,
        'timeline_stages': timeline_stages,
        'nearby_count': len(nearby),
        'nearby_reports': nearby[:3],
    }
    return render(request, 'issues/track_detail.html', context)


# ==========================================
# 5. CIVIC ACTION CENTER (ADMIN DASHBOARD)
# ==========================================

def admin_dashboard(request):
    """
    Custom Administrator Dashboard - Civic Action Center.
    Answers: 'What needs attention?' with critical cards, cluster intelligence, map, leaderboard & table.
    """
    # Key Metrics
    total_reports = CivicIssue.objects.count()
    pothole_count = CivicIssue.objects.filter(issue_category=CivicIssue.CATEGORY_POTHOLE).count()
    water_count = CivicIssue.objects.filter(issue_category=CivicIssue.CATEGORY_WATER).count()
    waste_count = CivicIssue.objects.filter(issue_category=CivicIssue.CATEGORY_WASTE).count()

    high_priority_count = CivicIssue.objects.filter(priority=CivicIssue.PRIORITY_HIGH).exclude(status__in=[CivicIssue.STATUS_RESOLVED, CivicIssue.STATUS_REJECTED]).count()
    critical_count = CivicIssue.objects.filter(priority=CivicIssue.PRIORITY_CRITICAL).exclude(status__in=[CivicIssue.STATUS_RESOLVED, CivicIssue.STATUS_REJECTED]).count()
    in_progress_count = CivicIssue.objects.filter(status=CivicIssue.STATUS_IN_PROGRESS).count()
    resolved_count = CivicIssue.objects.filter(status=CivicIssue.STATUS_RESOLVED).count()

    # Detect Issue Clusters for Administrative Intelligence
    detected_clusters = detect_issue_clusters(radius_km=0.8, min_reports=3)

    # Critical Unresolved Issues needing immediate attention
    attention_issues = CivicIssue.objects.filter(
        priority__in=[CivicIssue.PRIORITY_CRITICAL, CivicIssue.PRIORITY_HIGH]
    ).exclude(
        status__in=[CivicIssue.STATUS_RESOLVED, CivicIssue.STATUS_REJECTED]
    ).order_by('-priority', '-created_at')[:8]

    # Civic Impact Leaderboards (Top Admins & Top Citizens)
    top_officers = UserProfile.objects.filter(Q(user__is_staff=True) | Q(role__in=['admin', 'officer'])).order_by('-points')[:5]
    top_citizens = UserProfile.objects.filter(user__is_staff=False).order_by('-points')[:5]

    # Filtered issue list
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    search_query = request.GET.get('q', '').strip()

    issues_qs = CivicIssue.objects.all()

    if category_filter:
        issues_qs = issues_qs.filter(issue_category=category_filter)
    if status_filter:
        issues_qs = issues_qs.filter(status=status_filter)
    if priority_filter:
        issues_qs = issues_qs.filter(priority=priority_filter)
    if search_query:
        issues_qs = issues_qs.filter(
            Q(title__icontains=search_query) |
            Q(tracking_code__icontains=search_query) |
            Q(location_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    context = {
        'total_reports': total_reports,
        'pothole_count': pothole_count,
        'water_count': water_count,
        'waste_count': waste_count,
        'high_priority_count': high_priority_count,
        'critical_count': critical_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'detected_clusters': detected_clusters,
        'attention_issues': attention_issues,
        'top_officers': top_officers,
        'top_citizens': top_citizens,
        'issues': issues_qs[:50],
        'category_filter': category_filter,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_query': search_query,
    }
    return render(request, 'issues/dashboard.html', context)



# ==========================================
# 6. ISSUE DETAIL & ADMIN ACTION
# ==========================================

def issue_detail(request, pk):
    """
    Detailed Issue view with AI breakdown, location map, nearby reports, and Admin Action Form.
    """
    issue = get_object_or_404(CivicIssue, pk=pk)
    
    if request.method == 'POST':
        # Admin Action Submission
        form = AdminActionForm(request.POST, request.FILES, instance=issue)
        if form.is_valid():
            updated_issue = form.save(commit=False)
            admin_points_msg = ""

            # If changing to Resolved, set timestamp & award gamification points
            if updated_issue.status == CivicIssue.STATUS_RESOLVED:
                if not updated_issue.resolved_at:
                    updated_issue.resolved_at = timezone.now()

                # Record resolving officer & award admin points
                if request.user.is_authenticated:
                    updated_issue.resolved_by = request.user
                    admin_profile = get_user_profile(request.user)
                    if admin_profile:
                        prio_points = {
                            CivicIssue.PRIORITY_CRITICAL: 250,
                            CivicIssue.PRIORITY_HIGH: 150,
                            CivicIssue.PRIORITY_MEDIUM: 100,
                            CivicIssue.PRIORITY_LOW: 50,
                        }.get(updated_issue.priority, 100)

                        admin_profile.add_points(prio_points, f"Resolved {updated_issue.priority} priority issue #{updated_issue.tracking_code}")
                        admin_profile.resolved_count += 1
                        admin_profile.save(update_fields=['resolved_count'])
                        admin_points_msg = f" 🏆 +{prio_points} Officer Impact Points awarded to {request.user.username} ({admin_profile.badge_title})!"

                # Award resolution bonus to original resident
                if updated_issue.user and not updated_issue.points_awarded:
                    res_profile = get_user_profile(updated_issue.user)
                    if res_profile:
                        res_profile.add_points(100, f"Issue #{updated_issue.tracking_code} verified & resolved")
                    updated_issue.points_awarded = True

            elif updated_issue.status != CivicIssue.STATUS_RESOLVED:
                updated_issue.resolved_at = None

            updated_issue.save()
            messages.success(request, f"Issue #{issue.tracking_code} updated successfully. Status: {updated_issue.status}.{admin_points_msg}")
            return redirect('issue_detail', pk=issue.pk)

        else:
            messages.error(request, "Please correct the errors in the action form.")
    else:
        form = AdminActionForm(instance=issue)

    # Nearby reports
    nearby = []
    if issue.latitude and issue.longitude:
        nearby = find_nearby_reports(issue.latitude, issue.longitude, category=issue.issue_category, exclude_id=issue.id)

    context = {
        'issue': issue,
        'form': form,
        'nearby_reports': nearby,
        'nearby_count': len(nearby),
    }
    return render(request, 'issues/detail.html', context)


# ==========================================
# 7. MAP DATA API (FOR LEAFLET MAPS)
# ==========================================

@require_GET
def api_map_issues(request):
    """
    Returns JSON list of issues for Leaflet map display.
    """
    category = request.GET.get('category')
    priority = request.GET.get('priority')
    status_param = request.GET.get('status')
    unresolved_only = request.GET.get('unresolved_only', 'false').lower() == 'true'

    qs = CivicIssue.objects.filter(latitude__isnull=False, longitude__isnull=False)

    if category:
        qs = qs.filter(issue_category=category)
    if priority:
        qs = qs.filter(priority=priority)
    if status_param:
        qs = qs.filter(status=status_param)
    if unresolved_only:
        qs = qs.exclude(status__in=[CivicIssue.STATUS_RESOLVED, CivicIssue.STATUS_REJECTED])

    features = []
    for issue in qs:
        features.append({
            'id': issue.id,
            'tracking_code': issue.tracking_code,
            'title': issue.title,
            'category': issue.issue_category,
            'category_display': issue.get_issue_category_display(),
            'emoji': issue.icon_emoji,
            'color': issue.category_color,
            'priority': issue.priority,
            'status': issue.status,
            'latitude': issue.latitude,
            'longitude': issue.longitude,
            'location_name': issue.location_name or 'Marked Location',
            'created_at': issue.created_at.strftime('%b %d, %Y'),
            'image_url': issue.image.url if issue.image else None,
            'detail_url': f"/issues/{issue.id}/",
            'track_url': f"/track/{issue.tracking_code}/",
        })

    # Also include detected clusters
    clusters = detect_issue_clusters(radius_km=0.8, min_reports=3)
    cluster_list = [{
        'id': c['id'],
        'title': c['title'],
        'category': c['category'],
        'count': c['count'],
        'latitude': c['center_lat'],
        'longitude': c['center_lng'],
        'priority': c['priority'],
        'location_label': c['location_label'],
        'recommended_action': c['recommended_action'],
    } for c in clusters]

    return JsonResponse({
        'issues': features,
        'clusters': cluster_list,
    })


# ==========================================
# 8. AUTHENTICATION (LOGIN, REGISTER, LOGOUT)
# ==========================================

def user_login(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard' if request.user.is_staff else 'my_reports')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('admin_dashboard' if user.is_staff else 'my_reports')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'issues/login.html', {'form': form})


def user_register(request):
    if request.user.is_authenticated:
        return redirect('my_reports')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully! You can now report and track civic issues.")
            return redirect('my_reports')
        else:
            messages.error(request, "Registration error. Please check the details.")
    else:
        form = UserCreationForm()

    return render(request, 'issues/register.html', {'form': form})


def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')
