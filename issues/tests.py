from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from .models import CivicIssue
from .services.ai_service import fallback_rule_analysis, analyze_issue
from .services.priority_service import calculate_priority
from .services.clustering_service import haversine_distance_km, find_nearby_reports, detect_issue_clusters


class CivicFixCoreServicesTest(TestCase):
    def test_ai_fallback_pothole(self):
        """Test AI fallback correctly identifies high safety risk for severe pothole."""
        res = fallback_rule_analysis(
            category='pothole',
            title='Massive deep pothole near college gate',
            description='Two-wheelers and bikes are almost falling over this deep crater.',
            extra_context={'road_condition': 'Severe road damage', 'severity': 'High'}
        )
        self.assertEqual(res['severity'], 'High')
        self.assertEqual(res['recommended_department'], 'Road Maintenance')
        self.assertIn('accident risk', res['safety_risk'].lower())
        self.assertFalse(res['ai_available'])

    def test_ai_fallback_water_outage(self):
        """Test AI fallback for severe water supply outage."""
        res = fallback_rule_analysis(
            category='water',
            title='No water supply for three days',
            description='Whole neighborhood has zero drinking water supply.',
            extra_context={'water_problem_type': 'No water supply', 'water_duration': 'More than 3 days', 'affected_households': 'Many households'}
        )
        self.assertEqual(res['priority'], 'Critical')
        self.assertEqual(res['recommended_department'], 'Water Supply Department')

    def test_ai_fallback_waste(self):
        """Test AI fallback for waste accumulation."""
        res = fallback_rule_analysis(
            category='waste',
            title='Garbage overflowing near park for one week',
            description='Stench and massive trash pile near walking area.',
            extra_context={'waste_type': 'Overflowing bin', 'waste_accumulation': 'Severe', 'waste_duration': 'More than a week'}
        )
        self.assertEqual(res['priority'], 'High')
        self.assertEqual(res['recommended_department'], 'Waste Management')

    def test_priority_engine_rules(self):
        """Test explainable priority rules."""
        # Pothole severe
        prio, reason = calculate_priority('pothole', {'road_condition': 'Severe road damage', 'severity': 'High'}, nearby_count=4)
        self.assertEqual(prio, 'Critical')

        # Water outage
        prio_w, _ = calculate_priority('water', {'water_problem_type': 'No water supply', 'water_duration': '1–3 days', 'affected_households': 'Many households'})
        self.assertEqual(prio_w, 'Critical')

        # Minor waste
        prio_waste, _ = calculate_priority('waste', {'waste_type': 'Household waste', 'waste_accumulation': 'Small', 'waste_duration': 'Today'})
        self.assertEqual(prio_waste, 'Low')

    def test_haversine_and_clustering(self):
        """Test geographic distance and cluster detection."""
        # Create 4 nearby potholes on College Road
        coords = [
            (12.9720, 77.5940),
            (12.9722, 77.5942),
            (12.9724, 77.5944),
            (12.9726, 77.5946),
        ]
        for idx, (lat, lng) in enumerate(coords):
            CivicIssue.objects.create(
                tracking_code=f"CF-TEST{idx}",
                issue_category='pothole',
                title=f"Test Pothole {idx}",
                description="Testing cluster detection",
                latitude=lat,
                longitude=lng,
                location_name="College Road Test",
                priority="High",
                status="Submitted"
            )

        nearby = find_nearby_reports(12.9721, 77.5941, category='pothole', radius_km=0.5)
        self.assertEqual(len(nearby), 4)

        clusters = detect_issue_clusters(radius_km=0.8, min_reports=3)
        self.assertGreaterEqual(len(clusters), 1)
        self.assertEqual(clusters[0]['category'], 'pothole')
        self.assertEqual(clusters[0]['count'], 4)


class CivicFixViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('testadmin', 'test@civic.local', 'password123')
        self.issue = CivicIssue.objects.create(
            tracking_code='CF-SAMPLE1',
            issue_category='pothole',
            title='Sample Pothole Road Damage',
            description='Test pothole on Main Street',
            latitude=12.9716,
            longitude=77.5946,
            road_condition='Large pothole',
            severity='High',
            priority='High',
            status='Submitted',
        )

    def test_home_page(self):
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Report. Understand.')

    def test_report_select_page(self):
        res = self.client.get(reverse('report_issue'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'What problem are you facing?')

    def test_dynamic_report_pages(self):
        for cat in ['pothole', 'water', 'waste']:
            res = self.client.get(reverse('report_issue') + f'?category={cat}')
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'Pin Location on Map')

    def test_admin_dashboard(self):
        res = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'CIVIC ACTION CENTER')

    def test_issue_detail_view(self):
        res = self.client.get(reverse('issue_detail', args=[self.issue.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, self.issue.tracking_code)

    def test_track_detail_view(self):
        res = self.client.get(reverse('track_detail', args=[self.issue.tracking_code]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Resolution Progress Tracker')

    def test_api_map_issues(self):
        res = self.client.get(reverse('api_map_issues'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('issues', data)
        self.assertIn('clusters', data)

    def test_resolution_proof_action(self):
        """Test admin action updating status to Resolved with note."""
        self.client.force_login(self.admin)
        post_data = {
            'status': 'Resolved',
            'assigned_department': 'Road Maintenance',
            'admin_action': 'Repaired by South Division',
            'resolution_note': 'Asphalt resurfaced and compacted.',
        }
        res = self.client.post(reverse('issue_detail', args=[self.issue.id]), data=post_data)
        self.assertEqual(res.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, 'Resolved')
        self.assertIsNotNone(self.issue.resolved_at)
        self.assertEqual(self.issue.resolution_note, 'Asphalt resurfaced and compacted.')

    def test_exif_gps_extraction_and_api(self):
        """Test EXIF GPS extraction from camera image and API endpoint."""
        from PIL import Image
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        from issues.services.exif_service import extract_image_gps

        # Create image with GPS metadata
        img = Image.new('RGB', (100, 100), color='green')
        exif = img.getexif()
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd[1] = 'N'
        gps_ifd[2] = (12.0, 58.0, 17.76)
        gps_ifd[3] = 'E'
        gps_ifd[4] = (77.0, 35.0, 40.56)

        buf = io.BytesIO()
        img.save(buf, format='JPEG', exif=exif)
        buf.seek(0)

        # 1. Test Service function
        lat, lng = extract_image_gps(buf)
        self.assertIsNotNone(lat)
        self.assertIsNotNone(lng)
        self.assertAlmostEqual(lat, 12.9716, places=2)
        self.assertAlmostEqual(lng, 77.5946, places=2)

        # 2. Test API Endpoint
        buf.seek(0)
        upload_file = SimpleUploadedFile("gps_photo.jpg", buf.getvalue(), content_type="image/jpeg")
        res = self.client.post(reverse('api_extract_photo_gps'), data={'image': upload_file})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['has_gps'])
        self.assertAlmostEqual(data['latitude'], 12.9716, places=2)
        self.assertAlmostEqual(data['longitude'], 77.5946, places=2)

    def test_resident_and_admin_points_gamification(self):
        """Test points awarded to resident on submission and to admin on resolution."""
        from issues.models import UserProfile, get_user_profile

        # 1. Resident reports issue
        resident = User.objects.create_user(username='test_resident', password='password123')
        self.client.force_login(resident)

        report_data = {
            'title': 'Broken water pipe overflowing on road',
            'description': 'Water leaking continuously for two days.',
            'water_problem_type': 'Water leakage',
            'water_duration': '1–3 days',
            'affected_households': 'Many households',
            'location_name': 'Block B Street',
            'latitude': 12.9715,
            'longitude': 77.5940,
        }
        res = self.client.post(reverse('report_issue') + '?category=water', data=report_data)
        self.assertEqual(res.status_code, 302)

        # Check resident points
        res_profile = get_user_profile(resident)
        self.assertGreater(res_profile.points, 0)
        self.assertEqual(res_profile.reports_count, 1)
        created_issue = CivicIssue.objects.filter(user=resident).first()
        self.assertIsNotNone(created_issue)

        # 2. Admin resolves issue
        self.client.force_login(self.admin)
        admin_profile_before = get_user_profile(self.admin).points
        action_data = {
            'status': 'Resolved',
            'assigned_department': 'Water Supply Department',
            'admin_action': 'Replaced broken valve',
            'resolution_note': 'Leak sealed and tested with full water pressure.',
        }
        res = self.client.post(reverse('issue_detail', args=[created_issue.id]), data=action_data)
        self.assertEqual(res.status_code, 302)

        # Check admin points awarded
        admin_profile_after = get_user_profile(self.admin).points
        self.assertGreater(admin_profile_after, admin_profile_before)

        # Check resident received resolution bonus
        res_profile.refresh_from_db()
        self.assertGreaterEqual(res_profile.points, 150)



