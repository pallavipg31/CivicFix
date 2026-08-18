import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


def generate_tracking_code():
    return f"CF-{uuid.uuid4().hex[:6].upper()}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    points = models.IntegerField(default=0)
    reports_count = models.IntegerField(default=0)
    resolved_count = models.IntegerField(default=0)
    role = models.CharField(max_length=30, default='resident')  # 'resident', 'officer', 'admin'
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.points} pts - {self.badge_title})"

    def add_points(self, amount, reason=""):
        self.points += amount
        self.save(update_fields=['points', 'updated_at'])
        return self.points

    @property
    def badge_title(self):
        if self.user.is_staff or self.role in ['admin', 'officer']:
            if self.points >= 500:
                return "Senior Civic Commander 🥇"
            elif self.points >= 250:
                return "Lead Field Resolver 🥈"
            elif self.points >= 100:
                return "Municipal Officer 🥉"
            return "Civic Officer 🛡️"
        else:
            if self.points >= 500:
                return "Civic Champion 👑"
            elif self.points >= 250:
                return "Community Hero 🥇"
            elif self.points >= 100:
                return "Civic Scout 🥈"
            return "Active Citizen 🥉"


def get_user_profile(user):
    """Safely retrieves or creates a UserProfile for any user."""
    if not user or not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'admin' if user.is_staff else 'resident'}
    )
    return profile


class CivicIssue(models.Model):
    # Core Categories (strictly 3 civic categories)
    CATEGORY_POTHOLE = 'pothole'
    CATEGORY_WATER = 'water'
    CATEGORY_WASTE = 'waste'

    CATEGORY_CHOICES = [
        (CATEGORY_POTHOLE, 'Potholes / Road Damage'),
        (CATEGORY_WATER, 'Water Supply Problems'),
        (CATEGORY_WASTE, 'Waste Management'),
    ]

    # Priority Levels
    PRIORITY_LOW = 'Low'
    PRIORITY_MEDIUM = 'Medium'
    PRIORITY_HIGH = 'High'
    PRIORITY_CRITICAL = 'Critical'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_CRITICAL, 'Critical'),
    ]

    # Severity Levels
    SEVERITY_LOW = 'Low'
    SEVERITY_MEDIUM = 'Medium'
    SEVERITY_HIGH = 'High'
    SEVERITY_CRITICAL = 'Critical'

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, 'Low'),
        (SEVERITY_MEDIUM, 'Medium'),
        (SEVERITY_HIGH, 'High'),
        (SEVERITY_CRITICAL, 'Critical'),
    ]

    # Status Workflow
    STATUS_SUBMITTED = 'Submitted'
    STATUS_UNDER_REVIEW = 'Under Review'
    STATUS_ASSIGNED = 'Assigned'
    STATUS_IN_PROGRESS = 'In Progress'
    STATUS_RESOLVED = 'Resolved'
    STATUS_REJECTED = 'Rejected'

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    # Departments
    DEPT_ROAD = 'Road Maintenance'
    DEPT_WATER = 'Water Supply Department'
    DEPT_WASTE = 'Waste Management'

    DEPARTMENT_CHOICES = [
        (DEPT_ROAD, 'Road Maintenance'),
        (DEPT_WATER, 'Water Supply Department'),
        (DEPT_WASTE, 'Waste Management'),
    ]

    # Road Condition Choices (Pothole specific)
    ROAD_CONDITION_CHOICES = [
        ('Small damage', 'Small damage'),
        ('Moderate damage', 'Moderate damage'),
        ('Large pothole', 'Large pothole'),
        ('Multiple potholes', 'Multiple potholes'),
        ('Severe road damage', 'Severe road damage'),
    ]

    # Water Problem Type Choices (Water specific)
    WATER_PROBLEM_CHOICES = [
        ('No water supply', 'No water supply'),
        ('Low water pressure', 'Low water pressure'),
        ('Water leakage', 'Water leakage'),
        ('Irregular supply', 'Irregular supply'),
        ('Pipeline damage', 'Pipeline damage'),
        ('Other', 'Other'),
    ]

    # Water Duration Choices
    WATER_DURATION_CHOICES = [
        ('Less than 6 hours', 'Less than 6 hours'),
        ('6–12 hours', '6–12 hours'),
        ('12–24 hours', '12–24 hours'),
        ('1–3 days', '1–3 days'),
        ('More than 3 days', 'More than 3 days'),
    ]

    # Affected Area Choices
    AFFECTED_AREA_CHOICES = [
        ('My household', 'My household'),
        ('Few nearby households', 'Few nearby households'),
        ('Many households', 'Many households'),
        ('Large community', 'Large community'),
    ]

    # Waste Type Choices (Waste specific)
    WASTE_TYPE_CHOICES = [
        ('Household waste', 'Household waste'),
        ('Plastic waste', 'Plastic waste'),
        ('Construction waste', 'Construction waste'),
        ('Overflowing bin', 'Overflowing bin'),
        ('Mixed waste', 'Mixed waste'),
        ('Other', 'Other'),
    ]

    # Waste Accumulation Choices
    WASTE_ACCUMULATION_CHOICES = [
        ('Small', 'Small'),
        ('Moderate', 'Moderate'),
        ('Large', 'Large'),
        ('Severe', 'Severe'),
    ]

    # Waste Duration Choices
    WASTE_DURATION_CHOICES = [
        ('Today', 'Today'),
        ('1–2 days', '1–2 days'),
        ('3–7 days', '3–7 days'),
        ('More than a week', 'More than a week'),
    ]

    # Tracking & Identity
    tracking_code = models.CharField(max_length=20, unique=True, default=generate_tracking_code)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_issues')
    reporter_name = models.CharField(max_length=120, blank=True, default='Concerned Resident')
    reporter_contact = models.CharField(max_length=60, blank=True)

    # Core Fields
    issue_category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='issues/%Y/%m/', null=True, blank=True)

    # Geolocation
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_name = models.CharField(max_length=255, blank=True, help_text="e.g. Near College Main Gate, Sector 4")

    # Category Specific Fields
    # 1. Pothole / Road
    road_condition = models.CharField(max_length=60, choices=ROAD_CONDITION_CHOICES, null=True, blank=True)
    severity = models.CharField(max_length=30, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)

    # 2. Water
    water_problem_type = models.CharField(max_length=60, choices=WATER_PROBLEM_CHOICES, null=True, blank=True)
    water_duration = models.CharField(max_length=60, choices=WATER_DURATION_CHOICES, null=True, blank=True)
    affected_households = models.CharField(max_length=60, choices=AFFECTED_AREA_CHOICES, null=True, blank=True)

    # 3. Waste
    waste_type = models.CharField(max_length=60, choices=WASTE_TYPE_CHOICES, null=True, blank=True)
    waste_accumulation = models.CharField(max_length=60, choices=WASTE_ACCUMULATION_CHOICES, null=True, blank=True)
    waste_duration = models.CharField(max_length=60, choices=WASTE_DURATION_CHOICES, null=True, blank=True)

    # AI Understanding Fields
    issue_type = models.CharField(max_length=120, blank=True, default='General Civic Issue')
    priority = models.CharField(max_length=30, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    safety_risk = models.CharField(max_length=255, blank=True)
    impact = models.CharField(max_length=255, blank=True)
    ai_summary = models.TextField(blank=True)
    recommended_department = models.CharField(max_length=120, blank=True)
    recommended_action = models.TextField(blank=True)
    ai_available = models.BooleanField(default=True)

    # Admin Management & Action
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    assigned_department = models.CharField(max_length=120, choices=DEPARTMENT_CHOICES, blank=True)
    admin_action = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_issues')

    # Gamification
    points_awarded = models.BooleanField(default=False)

    # Resolution Proof
    resolution_image = models.ImageField(upload_to='resolutions/%Y/%m/', null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['issue_category']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['created_at']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        return f"[{self.tracking_code}] {self.title} ({self.get_issue_category_display()})"

    @property
    def icon_emoji(self):
        icons = {
            self.CATEGORY_POTHOLE: '🕳️',
            self.CATEGORY_WATER: '💧',
            self.CATEGORY_WASTE: '🗑️',
        }
        return icons.get(self.issue_category, '📌')

    @property
    def category_color(self):
        colors = {
            self.CATEGORY_POTHOLE: '#ea580c',  # Orange / Amber
            self.CATEGORY_WATER: '#0284c7',    # Sky Blue
            self.CATEGORY_WASTE: '#16a34a',    # Emerald Green
        }
        return colors.get(self.issue_category, '#4f46e5')

    @property
    def priority_badge_class(self):
        badges = {
            self.PRIORITY_LOW: 'bg-info text-dark',
            self.PRIORITY_MEDIUM: 'bg-primary text-white',
            self.PRIORITY_HIGH: 'bg-warning text-dark',
            self.PRIORITY_CRITICAL: 'bg-danger text-white',
        }
        return badges.get(self.priority, 'bg-secondary text-white')

    @property
    def status_badge_class(self):
        badges = {
            self.STATUS_SUBMITTED: 'badge-submitted',
            self.STATUS_UNDER_REVIEW: 'badge-review',
            self.STATUS_ASSIGNED: 'badge-assigned',
            self.STATUS_IN_PROGRESS: 'badge-in-progress',
            self.STATUS_RESOLVED: 'badge-resolved',
            self.STATUS_REJECTED: 'badge-rejected',
        }
        return badges.get(self.status, 'bg-secondary')

    @property
    def is_resolved(self):
        return self.status == self.STATUS_RESOLVED

    def get_timeline_stages(self):
        """Returns ordered timeline stages with active/completed status for resident tracker."""
        stages = [
            ('Submitted', 'Report submitted by resident'),
            ('Under Review', 'Verified & evaluated by civic staff'),
            ('Assigned', f'Assigned to {self.assigned_department or "Department"}'),
            ('In Progress', 'Field team executing repair / cleaning'),
            ('Resolved', 'Resolution verified with photographic proof'),
        ]
        
        status_order = {
            self.STATUS_SUBMITTED: 1,
            self.STATUS_UNDER_REVIEW: 2,
            self.STATUS_ASSIGNED: 3,
            self.STATUS_IN_PROGRESS: 4,
            self.STATUS_RESOLVED: 5,
            self.STATUS_REJECTED: -1,
        }

        current_idx = status_order.get(self.status, 1)
        timeline = []

        for idx, (name, desc) in enumerate(stages, start=1):
            is_completed = (current_idx >= idx) and (self.status != self.STATUS_REJECTED)
            is_current = (current_idx == idx) and (self.status != self.STATUS_REJECTED)
            timeline.append({
                'name': name,
                'description': desc,
                'is_completed': is_completed,
                'is_current': is_current,
                'index': idx,
            })
        return timeline
