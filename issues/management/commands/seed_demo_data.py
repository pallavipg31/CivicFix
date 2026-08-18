import os
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import io

from issues.models import CivicIssue


def generate_sample_image(text, bg_color=(200, 220, 240), text_color=(30, 40, 50), is_after=False):
    """Creates a lightweight synthetic image for demo issues and resolution proof."""
    img = Image.new('RGB', (600, 400), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Decorative header bar
    header_color = (22, 163, 74) if is_after else (234, 88, 12)
    draw.rectangle([0, 0, 600, 40], fill=header_color)
    badge_label = "CIVICFIX RESOLUTION PROOF (AFTER)" if is_after else "CIVICFIX INCIDENT REPORT (BEFORE)"
    draw.text((15, 12), badge_label, fill=(255, 255, 255))

    # Center label
    draw.rectangle([40, 80, 560, 340], outline=(150, 150, 150), width=2)
    draw.text((60, 160), text, fill=text_color)
    draw.text((60, 200), f"Status: {'VERIFIED REPAIRED' if is_after else 'INCIDENT REPORTED'}", fill=header_color)
    draw.text((60, 240), f"Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M')}", fill=(100, 100, 100))

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = 'Seeds realistic synthetic demo civic issues and creates an admin user for hackathon testing.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding CivicFix demo data..."))

        # 1. Create or get Admin user
        admin_user, created = User.objects.get_or_create(username='admin')
        if created:
            admin_user.set_password('admin123')
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.email = 'admin@civicfix.local'
            admin_user.first_name = 'Civic'
            admin_user.last_name = 'Administrator'
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created admin user: admin / admin123"))
        # Seed UserProfiles & Points
        from issues.models import UserProfile, get_user_profile
        admin_profile = get_user_profile(admin_user)
        admin_profile.points = 450
        admin_profile.resolved_count = 3
        admin_profile.role = 'admin'
        admin_profile.save()

        # Demo Citizens
        for uname, pts, reps, fname in [
            ('priya_sharma', 320, 5, 'Priya Sharma'),
            ('rahul_verma', 210, 3, 'Rahul Verma'),
            ('ananya_patel', 150, 2, 'Ananya Patel'),
        ]:
            u, _ = UserProfile.objects.get_or_create(
                user=User.objects.get_or_create(username=uname, defaults={'first_name': fname})[0],
                defaults={'points': pts, 'reports_count': reps, 'role': 'resident'}
            )
            u.points = pts
            u.reports_count = reps
            u.save()

        # Ensure media directories exist
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'issues'), exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'resolutions'), exist_ok=True)


        # Clear previous issues
        CivicIssue.objects.all().delete()

        # ==========================================
        # 1. POTHOLE CLUSTER: 7 reports near College Road + 2 isolated
        # ==========================================
        college_road_coords = [
            (12.9720, 77.5942, "College Gate Main Road - In front of Library"),
            (12.9724, 77.5946, "College Road - Near Bus Stop #4"),
            (12.9728, 77.5950, "College Road - Opposite Science Block"),
            (12.9731, 77.5954, "College Road - Crossing at Student Cafe"),
            (12.9735, 77.5958, "College Road - Near Hostels Entrance"),
            (12.9738, 77.5961, "College Road - East Junction"),
            (12.9741, 77.5965, "College Road - Sports Complex Turn"),
        ]

        pothole_titles = [
            "Massive pothole near college gate, two-wheelers slipping constantly",
            "Deep asphalt crater causing traffic bottleneck at bus stop",
            "Multiple severe potholes across entire westbound lane",
            "Broken road surface with exposed gravel near cafe crossing",
            "Large pothole filling with muddy water during rain",
            "Sunken asphalt trench causing bicycle accidents",
            "Severe surface cracking and multiple potholes on curve",
        ]

        for i, (lat, lng, loc) in enumerate(college_road_coords):
            is_resolved = (i == 0)  # Make 1st one resolved with proof
            status = CivicIssue.STATUS_RESOLVED if is_resolved else (CivicIssue.STATUS_IN_PROGRESS if i % 2 == 0 else CivicIssue.STATUS_SUBMITTED)
            
            issue = CivicIssue(
                tracking_code=f"CF-RD{100 + i}",
                user=admin_user,
                reporter_name=f"Resident {chr(65 + i)}",
                reporter_contact=f"resident_{i}@civic.org",
                issue_category=CivicIssue.CATEGORY_POTHOLE,
                title=pothole_titles[i],
                description=f"Dangerous pothole on {loc}. Bikes are almost falling when they pass. Urgent asphalt patching needed.",
                latitude=lat,
                longitude=lng,
                location_name=loc,
                road_condition='Large pothole' if i % 2 == 0 else 'Multiple potholes',
                severity='High',
                issue_type='Deep Pothole / Road Hazard',
                priority='High',
                safety_risk='High accident hazard for two-wheelers and braking vehicles',
                impact='Heavy college commuter traffic disrupted',
                ai_summary=f"Severe road crater defect on {loc} requiring asphalt patching.",
                recommended_department='Road Maintenance',
                recommended_action='Deploy asphalt patching truck with roller and safety cones.',
                ai_available=True,
                status=status,
                assigned_department='Road Maintenance',
                admin_action='Work order #RD-884 dispatched to South Division Road Crew.',
                created_at=timezone.now() - timedelta(days=random.randint(1, 4), hours=random.randint(2, 10))
            )
            
            # Attach sample before image
            issue.image.save(f"demo_pothole_{i}.jpg", generate_sample_image(f"Pothole: {loc}", bg_color=(254, 215, 170)), save=False)

            if is_resolved:
                issue.resolution_note = "Asphalt hot-mix laid, leveled, compacted with 10-ton road roller. Road surface fully restored."
                issue.resolved_at = timezone.now() - timedelta(hours=3)
                issue.resolution_image.save(f"demo_pothole_res_{i}.jpg", generate_sample_image(f"Repaired: {loc}", bg_color=(187, 247, 208), is_after=True), save=False)

            issue.save()

        # 2 Isolated Potholes
        isolated_potholes = [
            (12.9550, 77.5800, "Ring Road Flyover exit - Isolated pothole", "Moderate damage", "Medium"),
            (12.9890, 77.6150, "East Avenue lane 3 - Small asphalt crack", "Small damage", "Low"),
        ]
        for idx, (lat, lng, loc, cond, sev) in enumerate(isolated_potholes, start=8):
            issue = CivicIssue.objects.create(
                tracking_code=f"CF-RD{100 + idx}",
                issue_category=CivicIssue.CATEGORY_POTHOLE,
                title=f"Road imperfection on {loc}",
                description=f"Isolated road surface issue at {loc}. Traffic slow but passable.",
                latitude=lat,
                longitude=lng,
                location_name=loc,
                road_condition=cond,
                severity=sev,
                issue_type='Pothole',
                priority=sev,
                safety_risk='Minor traffic disruption',
                impact='Neighborhood commuters',
                ai_summary=f"Isolated road maintenance item at {loc}.",
                recommended_department='Road Maintenance',
                recommended_action='Inspect in next maintenance cycle.',
                ai_available=True,
                status=CivicIssue.STATUS_UNDER_REVIEW,
                created_at=timezone.now() - timedelta(days=2)
            )

        self.stdout.write(self.style.SUCCESS("Created 7 Clustered Potholes on College Road + 2 Isolated Potholes."))

        # ==========================================
        # 2. WATER SUPPLY CLUSTER: 12 reports in Sector 4 + 1 isolated
        # ==========================================
        water_base_lat = 12.9855
        water_base_lng = 77.6060

        for w in range(12):
            w_lat = water_base_lat + random.uniform(-0.003, 0.003)
            w_lng = water_base_lng + random.uniform(-0.003, 0.003)
            loc = f"North Sector 4 - Block {chr(65 + (w % 6))}, Lane {(w % 4) + 1}"
            
            is_resolved = (w == 0)
            status = CivicIssue.STATUS_RESOLVED if is_resolved else (CivicIssue.STATUS_IN_PROGRESS if w < 3 else CivicIssue.STATUS_SUBMITTED)

            issue = CivicIssue(
                tracking_code=f"CF-WT{200 + w}",
                user=admin_user,
                reporter_name=f"Resident Water-{w+1}",
                issue_category=CivicIssue.CATEGORY_WATER,
                title=f"No water supply for 3 days in {loc}",
                description=f"Zero tap water supply for past 3 days. Over 200 families suffering. Borewell and pipeline dry.",
                latitude=w_lat,
                longitude=w_lng,
                location_name=loc,
                water_problem_type='No water supply',
                water_duration='More than 3 days' if w % 2 == 0 else '1–3 days',
                affected_households='Large community',
                issue_type='Main Pipeline Water Outage',
                priority='Critical',
                safety_risk='Severe drinking water shortage and sanitation breakdown across community',
                impact='Multiple residential apartment blocks and houses without potable water',
                ai_summary=f"Widespread municipal water pipeline outage reported in {loc}.",
                recommended_department='Water Supply Department',
                recommended_action='Dispatch emergency pipeline maintenance squad and arrange emergency drinking water tankers.',
                ai_available=True,
                status=status,
                assigned_department='Water Supply Department',
                admin_action='Emergency mainline valve repair initiated; 4 water tankers routed to Sector 4.',
                created_at=timezone.now() - timedelta(days=random.randint(1, 3), hours=random.randint(1, 12))
            )
            issue.image.save(f"demo_water_{w}.jpg", generate_sample_image(f"Water Issue: {loc}", bg_color=(186, 230, 253)), save=False)

            if is_resolved:
                issue.resolution_note = "Main 400mm distribution pipe repaired, valve pressure restored to 3.5 bar. Water flowing smoothly."
                issue.resolved_at = timezone.now() - timedelta(hours=5)
                issue.resolution_image.save(f"demo_water_res_{w}.jpg", generate_sample_image(f"Pipeline Repaired: {loc}", bg_color=(187, 247, 208), is_after=True), save=False)

            issue.save()

        # 1 Isolated Water Leakage
        CivicIssue.objects.create(
            tracking_code="CF-WT299",
            issue_category=CivicIssue.CATEGORY_WATER,
            title="Slow roadside water leakage near Metro Pillar 102",
            description="Clear water slowly bubbling from sidewalk joint. Low pressure leak.",
            latitude=12.9600,
            longitude=77.6200,
            location_name="Metro Pillar 102, South Blvd",
            water_problem_type='Water leakage',
            water_duration='6–12 hours',
            affected_households='Few nearby households',
            issue_type='Roadside Pipeline Leakage',
            priority='Medium',
            safety_risk='Water wastage and slippery walkway',
            impact='Minor localized foot traffic',
            ai_summary="Minor pipeline joint seepage at Metro Pillar 102.",
            recommended_department='Water Supply Department',
            recommended_action='Inspect sidewalk valve and seal joint.',
            ai_available=True,
            status=CivicIssue.STATUS_ASSIGNED,
            assigned_department='Water Supply Department',
            created_at=timezone.now() - timedelta(days=1)
        )

        self.stdout.write(self.style.SUCCESS("Created 12 Clustered Water Outage Reports in Sector 4 + 1 Isolated Leakage."))

        # ==========================================
        # 3. WASTE CLUSTER: 8 reports around Central Park + 2 isolated
        # ==========================================
        waste_base_lat = 12.9635
        waste_base_lng = 77.5865

        waste_types = ['Overflowing bin', 'Mixed waste', 'Plastic waste', 'Household waste']

        for k in range(8):
            k_lat = waste_base_lat + random.uniform(-0.0025, 0.0025)
            k_lng = waste_base_lng + random.uniform(-0.0025, 0.0025)
            loc = f"Central Park Perimeter - Gate {(k % 4) + 1}, Walking Promenade"

            is_resolved = (k == 0)
            status = CivicIssue.STATUS_RESOLVED if is_resolved else (CivicIssue.STATUS_IN_PROGRESS if k % 2 == 1 else CivicIssue.STATUS_SUBMITTED)

            issue = CivicIssue(
                tracking_code=f"CF-WS{300 + k}",
                user=admin_user,
                reporter_name=f"Park Visitor {k+1}",
                issue_category=CivicIssue.CATEGORY_WASTE,
                title=f"Garbage severely overflowing for a week near {loc}",
                description=f"Massive accumulation of uncollected garbage near park perimeter. Strong foul odor, stray dogs, and plastic spreading on pathway.",
                latitude=k_lat,
                longitude=k_lng,
                location_name=loc,
                waste_type=waste_types[k % len(waste_types)],
                waste_accumulation='Severe' if k % 2 == 0 else 'Large',
                waste_duration='More than a week' if k % 2 == 0 else '3–7 days',
                issue_type='Solid Waste Accumulation / Public Hygiene Hazard',
                priority='High',
                safety_risk='Vector-borne diseases, attraction of stray animals, and respiratory nuisance from foul odor',
                impact='Daily morning walkers, children in park, and neighborhood residents',
                ai_summary=f"Severe solid waste dump accumulated over a week near {loc}.",
                recommended_department='Waste Management',
                recommended_action='Dispatch municipal compactor truck and sanitation workers for clearance and disinfectant washdown.',
                ai_available=True,
                status=status,
                assigned_department='Waste Management',
                admin_action='Compactor Truck #WM-14 dispatched to Central Park perimeter.',
                created_at=timezone.now() - timedelta(days=random.randint(1, 5))
            )
            issue.image.save(f"demo_waste_{k}.jpg", generate_sample_image(f"Waste Dump: {loc}", bg_color=(254, 202, 202)), save=False)

            if is_resolved:
                issue.resolution_note = "Garbage cleared via compactor truck. Bins emptied, area bleached and disinfected."
                issue.resolved_at = timezone.now() - timedelta(hours=8)
                issue.resolution_image.save(f"demo_waste_res_{k}.jpg", generate_sample_image(f"Cleaned Park: {loc}", bg_color=(187, 247, 208), is_after=True), save=False)

            issue.save()

        # 2 Isolated Waste reports
        isolated_waste = [
            (12.9800, 77.5700, "West Market corner bin - Full bin", "Overflowing bin", "Moderate", "Medium"),
            (12.9500, 77.6100, "Commercial Street Lane 2 - Construction debris", "Construction waste", "Small", "Low"),
        ]
        for widx, (wlat, wlng, wloc, wtype, wacc, wprio) in enumerate(isolated_waste, start=8):
            CivicIssue.objects.create(
                tracking_code=f"CF-WS{300 + widx}",
                issue_category=CivicIssue.CATEGORY_WASTE,
                title=f"Waste cleanup needed at {wloc}",
                description=f"Isolated waste accumulation: {wtype} at {wloc}.",
                latitude=wlat,
                longitude=wlng,
                location_name=wloc,
                waste_type=wtype,
                waste_accumulation=wacc,
                waste_duration='1–2 days',
                issue_type='Waste Cleanup',
                priority=wprio,
                safety_risk='Minor public littering',
                impact='Local street',
                ai_summary=f"Routine waste pickup logged for {wloc}.",
                recommended_department='Waste Management',
                recommended_action='Add to scheduled municipal route.',
                ai_available=True,
                status=CivicIssue.STATUS_SUBMITTED,
                created_at=timezone.now() - timedelta(days=1)
            )

        self.stdout.write(self.style.SUCCESS("Created 8 Clustered Waste Reports around Central Park + 2 Isolated Reports."))
        self.stdout.write(self.style.SUCCESS("Demo database seed complete! Total active & resolved records created."))
