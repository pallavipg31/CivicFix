from django.contrib import admin
from .models import CivicIssue


@admin.register(CivicIssue)
class CivicIssueAdmin(admin.ModelAdmin):
    list_display = (
        'tracking_code',
        'title',
        'issue_category',
        'priority',
        'status',
        'assigned_department',
        'created_at',
    )
    list_filter = ('issue_category', 'priority', 'status', 'assigned_department', 'created_at')
    search_fields = ('tracking_code', 'title', 'description', 'location_name', 'reporter_name')
    readonly_fields = ('tracking_code', 'created_at', 'updated_at')
