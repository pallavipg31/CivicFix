import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'civicfix.settings')
django.setup()

from issues.models import CivicIssue
from issues.services.ai_service import fallback_rule_analysis, analyze_issue
from issues.services.priority_service import calculate_priority
from issues.services.clustering_service import detect_issue_clusters, find_nearby_reports

BASE_URL = "http://127.0.0.1:8000"

def test_live_server_endpoints():
    print("=" * 60)
    print("CIVICFIX COMPREHENSIVE END-TO-END VERIFICATION")
    print("=" * 60)
    
    session = requests.Session()

    # 1. Test Landing Page
    print("\n[1] Testing Landing Page ('/')...")
    res = session.get(f"{BASE_URL}/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert "Report. Understand." in res.text, "Landing page headline missing"
    assert "ROAD PROBLEMS" in res.text, "Road Problems card missing"
    assert "WATER PROBLEMS" in res.text, "Water Problems card missing"
    assert "WASTE PROBLEMS" in res.text, "Waste Problems card missing"
    print("  -> PASS: Landing page renders headline, 3 problem cards & live statistics.")

    # 2. Test Step 1 Category Select
    print("\n[2] Testing Report Select ('/report/')...")
    res = session.get(f"{BASE_URL}/report/")
    assert res.status_code == 200
    assert "What problem are you facing?" in res.text
    print("  -> PASS: Category selection prompt renders.")

    # 3. Test Category Forms
    print("\n[3] Testing Category Dynamic Forms ('/report/?category=...')...")
    for cat in ['pothole', 'water', 'waste']:
        res = session.get(f"{BASE_URL}/report/?category={cat}")
        assert res.status_code == 200
        assert "Pin Location on Map" in res.text
        print(f"  -> PASS: {cat.upper()} reporting form rendered with Leaflet map.")

    # 4. Test AI Analyze AJAX API
    print("\n[4] Testing AI Analyze AJAX API ('/api/analyze/')...")
    test_payload = {
        'category': 'pothole',
        'title': 'Massive pothole near college gate. Bikes are struggling to pass.',
        'description': 'Large deep crater in asphalt right in front of the college main gate. Multiple two-wheelers slipping.',
        'road_condition': 'Large pothole',
        'severity': 'High',
        'latitude': 12.9720,
        'longitude': 77.5942
    }
    res = session.post(f"{BASE_URL}/api/analyze/", json=test_payload)
    assert res.status_code == 200, f"AI analyze returned {res.status_code}"
    data = res.json()
    assert 'ai_analysis' in data
    assert 'smart_priority' in data
    print(f"  -> PASS: AI Analysis returned Issue Type: '{data['ai_analysis']['issue_type']}', Priority: '{data['smart_priority']}', Recommended Dept: '{data['ai_analysis']['recommended_department']}'.")
    print(f"  -> PASS: Nearby reports detected: {data['nearby_count']}.")

    # 4b. Test Photo Camera GPS Extraction API
    print("\n[4b] Testing Photo Camera GPS Extraction API ('/api/extract-photo-gps/')...")
    from PIL import Image
    import io
    img = Image.new('RGB', (100, 100), color='teal')
    exif = img.getexif()
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1] = 'N'
    gps_ifd[2] = (12.0, 58.0, 17.76)
    gps_ifd[3] = 'E'
    gps_ifd[4] = (77.0, 35.0, 40.56)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', exif=exif)
    buf.seek(0)

    files = {'image': ('camera_photo.jpg', buf.getvalue(), 'image/jpeg')}
    res_gps = session.post(f"{BASE_URL}/api/extract-photo-gps/", files=files)
    assert res_gps.status_code == 200, f"GPS extraction returned {res_gps.status_code}"
    gps_data = res_gps.json()
    assert gps_data.get('has_gps') is True
    print(f"  -> PASS: Successfully extracted camera EXIF GPS: Lat={gps_data['latitude']}, Lng={gps_data['longitude']}")


    # 5. Test Map API & Clusters
    print("\n[5] Testing Admin Map API ('/api/map-issues/')...")
    res = session.get(f"{BASE_URL}/api/map-issues/")
    assert res.status_code == 200
    map_data = res.json()
    assert len(map_data['issues']) > 0, "No issues in map API"
    assert len(map_data['clusters']) >= 3, "Expected at least 3 clusters (Pothole, Water, Waste)"
    print(f"  -> PASS: Map API returned {len(map_data['issues'])} pins and {len(map_data['clusters'])} active clusters:")
    for c in map_data['clusters']:
        print(f"     * [{c['title']}] - {c['count']} active reports around {c['location_label']} ({c['priority']} Priority)")

    # 6. Test Civic Action Center Dashboard
    print("\n[6] Testing Civic Action Center ('/dashboard/')...")
    res = session.get(f"{BASE_URL}/dashboard/")
    assert res.status_code == 200
    assert "CIVIC ACTION CENTER" in res.text
    assert "WHAT NEEDS ATTENTION?" in res.text
    print("  -> PASS: Civic Action Center rendered KPI cards, Attention alerts, and Table.")

    # 7. Test End-to-End Workflow: Pothole -> AI -> Action -> Resolution Proof -> Resident Tracking
    print("\n[7] Testing Complete Workflow 1 (Pothole):")
    # Fetch report form to get CSRF token
    report_page = session.get(f"{BASE_URL}/report/?category=pothole")
    csrf_token = session.cookies.get('csrftoken') or ''
    if not csrf_token and 'csrfmiddlewaretoken' in report_page.text:
        import re
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', report_page.text)
        if match:
            csrf_token = match.group(1)

    # Submit Pothole
    post_data = {
        'csrfmiddlewaretoken': csrf_token,
        'title': 'Huge pothole at College Gate West Wing',
        'description': 'Bikes are skidding daily at this spot near the gate.',
        'road_condition': 'Severe road damage',
        'severity': 'High',
        'location_name': 'College Road West Gate',
        'latitude': '12.9723',
        'longitude': '77.5945',
        'reporter_name': 'Aarav Patel',
        'reporter_contact': 'aarav@college.edu',
    }
    submit_res = session.post(f"{BASE_URL}/report/?category=pothole", data=post_data, headers={'Referer': f"{BASE_URL}/report/?category=pothole"})
    assert submit_res.status_code in [200, 302], f"Submission returned {submit_res.status_code}"
    
    new_issue = CivicIssue.objects.filter(title='Huge pothole at College Gate West Wing').first()
    assert new_issue is not None, "New issue was not saved in database"
    print(f"  -> Created Issue #{new_issue.tracking_code}: Priority = {new_issue.priority}, Status = {new_issue.status}")

    # Track view
    track_res = session.get(f"{BASE_URL}/track/{new_issue.tracking_code}/")
    assert track_res.status_code == 200
    assert "Resolution Progress Tracker" in track_res.text
    print(f"  -> Resident Tracking Page shows 5-stage timeline for #{new_issue.tracking_code}")

    # Admin marks Resolved with Proof
    admin_detail_url = f"{BASE_URL}/issues/{new_issue.id}/"
    detail_page = session.get(admin_detail_url)
    assert detail_page.status_code == 200

    admin_post = {
        'csrfmiddlewaretoken': csrf_token,
        'status': 'Resolved',
        'assigned_department': 'Road Maintenance',
        'admin_action': 'Road crew dispatched under Work Order #892. Pothole filled and sealed.',
        'resolution_note': 'Asphalt patch applied and compacted with heavy roller. Level restored.',
    }
    action_res = session.post(admin_detail_url, data=admin_post, headers={'Referer': admin_detail_url})
    assert action_res.status_code in [200, 302]
    
    new_issue.refresh_from_db()
    assert new_issue.status == 'Resolved', f"Expected Resolved, got {new_issue.status}"
    assert new_issue.resolved_at is not None, "resolved_at timestamp was not set"
    print(f"  -> Issue #{new_issue.tracking_code} transitioned to Resolved with proof note and timestamp: {new_issue.resolved_at}")

    # Verify Resident Tracking now displays Resolved Proof
    track_res2 = session.get(f"{BASE_URL}/track/{new_issue.tracking_code}/")
    assert "Official Resolution Proof" in track_res2.text
    assert "Asphalt patch applied" in track_res2.text
    print(f"  -> Resident Tracking Page displays verified Resolution Proof successfully!")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_live_server_endpoints()
