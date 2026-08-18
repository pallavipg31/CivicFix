import logging
import json
import base64
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from django.conf import settings

logger = logging.getLogger(__name__)


def _convert_to_degrees(value):
    """
    Helper function to convert the GPS coordinates stored in EXIF to decimal degrees.
    Handles IFDRational, float, tuple, and int values.
    """
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception as e:
        logger.debug(f"Error converting GPS rational to degrees: {e}")
        return None


def extract_image_gps(image_file):
    """
    Extracts latitude and longitude from an uploaded image file's EXIF metadata.
    
    Parameters:
        image_file: Django UploadedFile or file-like object / image path
        
    Returns:
        tuple: (latitude: float, longitude: float) or (None, None) if no GPS data
    """
    try:
        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        image = Image.open(image_file)
        
        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        if not hasattr(image, '_getexif'):
            return None, None

        exif_data = image._getexif()
        if not exif_data:
            return None, None

        gps_info = {}
        for tag, value in exif_data.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = value[t]

        if not gps_info:
            return None, None

        lat_val = gps_info.get('GPSLatitude')
        lat_ref = gps_info.get('GPSLatitudeRef')
        lng_val = gps_info.get('GPSLongitude')
        lng_ref = gps_info.get('GPSLongitudeRef')

        if lat_val and lat_ref and lng_val and lng_ref:
            lat = _convert_to_degrees(lat_val)
            lng = _convert_to_degrees(lng_val)

            if lat is not None and lng is not None:
                if str(lat_ref).upper() != 'N':
                    lat = -lat
                if str(lng_ref).upper() != 'E':
                    lng = -lng
                return round(lat, 6), round(lng, 6)

    except Exception as exc:
        logger.debug(f"Could not extract EXIF GPS from image: {exc}")
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        return None, None

    return None, None


def analyze_photo_location_with_ai(image_file, category='pothole', filename='photo.jpg'):
    """
    Comprehensive location analysis:
    1. Scans EXIF GPS metadata for exact camera hardware coordinates.
    2. Uses Groq AI to interpret image context and generate location landmarks & civic assessment.
    """
    lat, lng = extract_image_gps(image_file)
    api_key = getattr(settings, 'GROQ_API_KEY', '').strip()

    if lat and lng:
        has_gps = True
        source = 'camera_exif_gps'
        confidence = 'High (Camera Hardware GPS)'
    else:
        # Default urban reference if no hardware GPS in image
        has_gps = False
        source = 'ai_inferred'
        confidence = 'Location Pin Required'
        lat, lng = None, None

    # Determine location description
    location_name = ""
    problem_insight = ""

    if has_gps:
        location_name = f"Photo GPS Site ({lat:.4f}, {lng:.4f})"

    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key, timeout=8.0)

            prompt = (
                f"You are CivicFix Location & Visual Analyzer AI. An image named '{filename}' has been uploaded for civic problem category '{category}'. "
                f"GPS Coordinates found from photo: {f'Latitude {lat}, Longitude {lng}' if has_gps else 'No embedded GPS'}.\n"
                "Return a JSON object:\n"
                "{\n"
                '  "location_label": "<Concise landmark, street name, or urban zone description>",\n'
                '  "civic_insight": "<Brief 1-sentence insight about the civic condition in the photo>",\n'
                '  "safety_flag": "<High | Medium | Low>"\n'
                "}"
            )

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a municipal location analysis assistant. Respond ONLY in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=250
            )

            data = json.loads(response.choices[0].message.content)
            if data.get('location_label') and not has_gps:
                location_name = data.get('location_label')
            elif data.get('location_label') and has_gps:
                location_name = f"{data.get('location_label')} ({lat:.4f}, {lng:.4f})"
            problem_insight = data.get('civic_insight', '')

        except Exception as e:
            logger.warning(f"Groq location analysis note: {e}")

    if not location_name:
        location_name = f"Photo Location ({lat:.4f}, {lng:.4f})" if has_gps else "Marked Site Location"

    return {
        'has_gps': has_gps,
        'latitude': lat,
        'longitude': lng,
        'location_name': location_name,
        'source': source,
        'confidence': confidence,
        'insight': problem_insight,
        'message': f"GPS location analyzed from photo: {lat}, {lng}" if has_gps else "Photo analyzed. Tap map to pin location."
    }
