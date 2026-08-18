/**
 * CivicFix - Resident Map Location Picker (Leaflet + OpenStreetMap + Photo EXIF GPS)
 */

document.addEventListener('DOMContentLoaded', function () {
  const mapContainer = document.getElementById('map-picker');
  if (!mapContainer) return;

  const latInput = document.getElementById('id_latitude') || document.querySelector('[name="latitude"]');
  const lngInput = document.getElementById('id_longitude') || document.querySelector('[name="longitude"]');
  const locNameInput = document.getElementById('id_location_name') || document.querySelector('[name="location_name"]');
  const locateBtn = document.getElementById('btn-locate-me');
  const coordsDisplay = document.getElementById('selected-coords-text');

  // Default coordinate (Urban Center)
  let defaultLat = 12.9716;
  let defaultLng = 77.5946;
  let zoomLevel = 13;

  // If inputs already have coordinates
  if (latInput && lngInput && latInput.value && lngInput.value) {
    defaultLat = parseFloat(latInput.value);
    defaultLng = parseFloat(lngInput.value);
    zoomLevel = 15;
  }

  const map = L.map('map-picker').setView([defaultLat, defaultLng], zoomLevel);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  // Custom marker icon
  const civicIcon = L.divIcon({
    className: 'custom-map-pin',
    html: '<div style="background:#0d9488;width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 0 10px rgba(0,0,0,0.4);"></div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  });

  let marker = null;

  function updateMarker(lat, lng, pan = true) {
    if (marker) {
      marker.setLatLng([lat, lng]);
    } else {
      marker = L.marker([lat, lng], { draggable: true, icon: civicIcon }).addTo(map);
      marker.on('dragend', function (e) {
        const pos = e.target.getLatLng();
        setCoordinates(pos.lat, pos.lng, 'Map Pin Drag');
      });
    }

    if (pan) {
      map.setView([lat, lng], Math.max(map.getZoom(), 16), { animate: true });
    }
  }

  function setCoordinates(lat, lng, sourceLabel = 'Map Pin') {
    const fixedLat = parseFloat(lat).toFixed(6);
    const fixedLng = parseFloat(lng).toFixed(6);

    if (latInput) latInput.value = fixedLat;
    if (lngInput) lngInput.value = fixedLng;

    if (coordsDisplay) {
      coordsDisplay.innerHTML = `<span class="badge bg-success"><i class="bi bi-geo-alt-fill me-1"></i> ${sourceLabel}: ${fixedLat}, ${fixedLng}</span>`;
    }

    // Trigger nearby check if function exists
    if (window.checkNearbyReports) {
      window.checkNearbyReports(fixedLat, fixedLng);
    }
  }

  // Expose global updater so Photo EXIF GPS can call it
  window.updateMapLocation = function (lat, lng, sourceLabel = 'Photo GPS') {
    updateMarker(lat, lng, true);
    setCoordinates(lat, lng, sourceLabel);
  };

  // Initial marker if lat/lng present
  if (latInput && lngInput && latInput.value && lngInput.value) {
    updateMarker(parseFloat(latInput.value), parseFloat(lngInput.value), false);
    setCoordinates(latInput.value, lngInput.value, 'Saved Coordinates');
  }

  // Click on map to drop / move pin
  map.on('click', function (e) {
    updateMarker(e.latlng.lat, e.latlng.lng, false);
    setCoordinates(e.latlng.lat, e.latlng.lng, 'Manual Pin');
  });

  // "Use My Current Location" button (Browser Geolocation API)
  if (locateBtn) {
    locateBtn.addEventListener('click', function (e) {
      e.preventDefault();
      locateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Locating GPS...';
      locateBtn.disabled = true;

      if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser. Please click directly on the map to pin your location.');
        resetLocateBtn();
        return;
      }

      navigator.geolocation.getCurrentPosition(
        function (pos) {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          updateMarker(lat, lng, true);
          setCoordinates(lat, lng, 'Browser GPS');
          resetLocateBtn(true);
        },
        function (err) {
          console.warn('Geolocation failed or permission denied:', err);
          alert('Could not retrieve GPS location. You can simply tap anywhere on the map to mark the exact spot.');
          resetLocateBtn(false);
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
      );
    });
  }

  function resetLocateBtn(success = false) {
    if (!locateBtn) return;
    locateBtn.disabled = false;
    if (success) {
      locateBtn.innerHTML = '<i class="bi bi-check-circle-fill me-1 text-success"></i> GPS Located';
      setTimeout(() => {
        locateBtn.innerHTML = '<i class="bi bi-crosshair me-1"></i> Use My Current Location';
      }, 3000);
    } else {
      locateBtn.innerHTML = '<i class="bi bi-crosshair me-1"></i> Use My Current Location';
    }
  }
});
