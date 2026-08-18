/**
 * CivicFix - Resident Reporting & AI Review Flow + Photo EXIF GPS Extraction
 */

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('report-form');
  const imageInput = document.getElementById('id_image');
  const previewBox = document.getElementById('image-preview-container');
  const previewImg = document.getElementById('preview-image');
  const uploadPlaceholder = document.getElementById('upload-placeholder');
  const btnAnalyze = document.getElementById('btn-analyze-report');
  const nearbyAlert = document.getElementById('nearby-reports-alert');
  const nearbyCountSpan = document.getElementById('nearby-count-span');
  const nearbyList = document.getElementById('nearby-reports-list');
  const photoGpsAlert = document.getElementById('photo-gps-alert');

  // 1. IMAGE PREVIEW & AUTOMATIC PHOTO GPS EXTRACTION
  if (imageInput) {
    imageInput.addEventListener('change', function (e) {
      const file = e.target.files[0];
      if (file) {
        // Validate file size (10MB)
        if (file.size > 10 * 1024 * 1024) {
          alert('File is too large! Please choose an image smaller than 10MB.');
          imageInput.value = '';
          return;
        }

        // Show image preview
        const reader = new FileReader();
        reader.onload = function (event) {
          if (previewImg) {
            previewImg.src = event.target.result;
            previewImg.classList.remove('d-none');
          }
          if (uploadPlaceholder) uploadPlaceholder.classList.add('d-none');
        };
        reader.readAsDataURL(file);

        // Extract EXIF GPS and AI Location Analysis from Photo
        if (photoGpsAlert) {
          photoGpsAlert.className = 'alert alert-info py-2 px-3 small d-flex align-items-center gap-2 mt-2';
          photoGpsAlert.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Analyzing photo camera GPS & location metadata with Groq AI...';
          photoGpsAlert.classList.remove('d-none');
        }

        const category = document.getElementById('report-category')?.value || 'pothole';
        const formData = new FormData();
        formData.append('image', file);
        formData.append('category', category);

        fetch('/api/extract-photo-gps/', {
          method: 'POST',
          body: formData,
        })
        .then(res => res.json())
        .then(data => {
          if (data.has_gps && data.latitude && data.longitude) {
            // Found GPS in photo EXIF!
            const lat = data.latitude;
            const lng = data.longitude;
            const locName = data.location_name || `Photo GPS Site (${lat.toFixed(4)}, ${lng.toFixed(4)})`;

            if (photoGpsAlert) {
              photoGpsAlert.className = 'alert alert-success py-2 px-3 small mt-2';
              photoGpsAlert.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <div>
                    <i class="bi bi-camera-fill text-success me-1"></i>
                    <strong>Camera GPS Detected:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}
                  </div>
                  <span class="badge bg-success">Map Auto-Centered</span>
                </div>
                <div class="text-dark small"><i class="bi bi-geo-alt-fill text-danger me-1"></i> <strong>Location:</strong> ${locName}</div>
                ${data.insight ? `<div class="text-muted small mt-1"><i class="bi bi-stars text-warning me-1"></i> <strong>AI Insight:</strong> ${data.insight}</div>` : ''}
              `;
            }

            // Center map and update marker
            if (window.updateMapLocation) {
              window.updateMapLocation(lat, lng, 'Photo Camera GPS');
            }

            // Auto-fill location landmark input
            const locNameInput = document.getElementById('id_location_name');
            if (locNameInput) {
              locNameInput.value = locName;
            }
          } else {
            // No embedded hardware GPS
            const locName = data.location_name || '';
            const locNameInput = document.getElementById('id_location_name');
            if (locName && locNameInput && !locNameInput.value.trim()) {
              locNameInput.value = locName;
            }

            if (photoGpsAlert) {
              photoGpsAlert.className = 'alert alert-light border py-2 px-3 small mt-2 text-muted';
              photoGpsAlert.innerHTML = `
                <div class="d-flex align-items-center gap-2">
                  <i class="bi bi-info-circle text-primary"></i>
                  <span>Photo analyzed by AI. No direct GPS tags embedded — you can tap the map or click <strong>"Use My Current Location"</strong>.</span>
                </div>
                ${data.insight ? `<div class="text-dark small mt-1 ps-4"><i class="bi bi-stars text-warning me-1"></i> <strong>AI Insight:</strong> ${data.insight}</div>` : ''}
              `;
            }
          }
        })
        .catch(err => {
          console.debug('Photo GPS check error:', err);
          if (photoGpsAlert) photoGpsAlert.classList.add('d-none');
        });
      }
    });
  }


  // 2. NEARBY REPORT CHECKER
  window.checkNearbyReports = function (lat, lng) {
    const category = document.getElementById('report-category')?.value || 'pothole';
    if (!lat || !lng) return;

    fetch(`/api/analyze/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        category: category,
        title: document.getElementById('id_title')?.value || 'Check',
        description: document.getElementById('id_description')?.value || 'Check',
        latitude: lat,
        longitude: lng
      })
    })
    .then(res => res.json())
    .then(data => {
      if (data.nearby_count > 0 && nearbyAlert) {
        nearbyAlert.classList.remove('d-none');
        if (nearbyCountSpan) nearbyCountSpan.textContent = data.nearby_count;
        if (nearbyList) {
          nearbyList.innerHTML = data.nearby_reports.map(r => `
            <div class="small border-bottom py-1 d-flex justify-content-between align-items-center">
              <span><strong>#${r.tracking_code}</strong>: ${r.title}</span>
              <span class="badge bg-secondary">${r.distance_m}m away</span>
            </div>
          `).join('');
        }
      } else if (nearbyAlert) {
        nearbyAlert.classList.add('d-none');
      }
    })
    .catch(err => console.debug('Nearby check note:', err));
  };

  // 3. AI ANALYSIS REVIEW MODAL
  if (btnAnalyze) {
    btnAnalyze.addEventListener('click', function (e) {
      e.preventDefault();

      const titleInput = document.getElementById('id_title');
      const descInput = document.getElementById('id_description');
      const category = document.getElementById('report-category')?.value || 'pothole';

      // If user hasn't typed yet, provide helpful smart defaults so analysis always succeeds
      if (titleInput && !titleInput.value.trim()) {
        const catNames = { 'pothole': 'Road Surface Damage / Pothole', 'water': 'Water Supply Disruption', 'waste': 'Waste Accumulation Issue' };
        const roadCond = document.getElementById('id_road_condition')?.value;
        const waterType = document.getElementById('id_water_problem_type')?.value;
        const wasteType = document.getElementById('id_waste_type')?.value;
        titleInput.value = roadCond || waterType || wasteType || catNames[category] || 'Civic Issue';
      }

      if (descInput && !descInput.value.trim()) {
        const locName = document.getElementById('id_location_name')?.value || 'the marked site';
        descInput.value = `Observed ${category} problem near ${locName}. Requires immediate municipal assessment and repair.`;
      }

      const originalBtnText = btnAnalyze.innerHTML;
      btnAnalyze.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>AI Analyzing Problem with Groq...';
      btnAnalyze.disabled = true;

      const payload = {
        category: category,
        title: titleInput ? titleInput.value.trim() : `Reported ${category}`,
        description: descInput ? descInput.value.trim() : `Observed ${category} issue at site.`,
        latitude: document.getElementById('id_latitude')?.value || null,
        longitude: document.getElementById('id_longitude')?.value || null,
        location_name: document.getElementById('id_location_name')?.value || null,
        road_condition: document.getElementById('id_road_condition')?.value || null,
        severity: document.getElementById('id_severity')?.value || null,
        water_problem_type: document.getElementById('id_water_problem_type')?.value || null,
        water_duration: document.getElementById('id_water_duration')?.value || null,
        affected_households: document.getElementById('id_affected_households')?.value || null,
        waste_type: document.getElementById('id_waste_type')?.value || null,
        waste_accumulation: document.getElementById('id_waste_accumulation')?.value || null,
        waste_duration: document.getElementById('id_waste_duration')?.value || null,
      };

      fetch('/api/analyze/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(payload)
      })
      .then(res => {
        if (!res.ok) throw new Error('Analysis request failed with status ' + res.status);
        return res.json();
      })
      .then(data => {
        btnAnalyze.innerHTML = originalBtnText;
        btnAnalyze.disabled = false;

        const ai = data.ai_analysis || {};
        const priority = data.smart_priority || ai.priority || 'Medium';

        // Populate AI Review Modal fields
        const setTxt = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt || ''; };
        setTxt('ai-res-issue-type', ai.issue_type || 'Civic Problem Evaluation');
        setTxt('ai-res-severity', ai.severity || 'Medium');
        setTxt('ai-res-priority', priority);
        
        const prioBadge = document.getElementById('ai-res-priority-badge');
        if (prioBadge) {
          prioBadge.className = `badge bg-${getPriorityColor(priority)} px-3 py-2 fs-6`;
        }

        setTxt('ai-res-safety-risk', ai.safety_risk || 'Standard municipal safety consideration');
        setTxt('ai-res-impact', ai.impact || 'Local commuters and nearby residents');
        setTxt('ai-res-department', ai.recommended_department || 'Municipal Corporation');
        setTxt('ai-res-action', ai.recommended_action || 'Site inspection and field remediation');
        setTxt('ai-res-summary', ai.summary || 'CivicFix AI evaluated the reported parameters for municipal routing.');
        setTxt('ai-res-reasoning', data.priority_explanation || 'Calculated dynamically based on severity, duration, and density.');

        // AI badge availability status
        const aiStatusBadge = document.getElementById('ai-status-badge');
        if (aiStatusBadge) {
          aiStatusBadge.innerHTML = ai.ai_available 
            ? '<i class="bi bi-cpu-fill me-1"></i> Groq Llama 3.3 70B' 
            : '<i class="bi bi-shield-check me-1"></i> Smart Rule Engine';
        }

        // Show Modal safely
        const modalEl = document.getElementById('aiReviewModal');
        if (modalEl) {
          if (window.bootstrap && bootstrap.Modal) {
            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
            modalInstance.show();
          } else {
            // Fallback
            modalEl.classList.add('show');
            modalEl.style.display = 'block';
          }
        }
      })
      .catch(err => {
        console.error('AI Analysis error:', err);
        btnAnalyze.innerHTML = originalBtnText;
        btnAnalyze.disabled = false;
        alert('AI analysis encountered a temporary network delay. You can submit directly or try clicking again in a few moments.');
      });
    });
  }


  // 4. CONFIRM & SUBMIT FROM MODAL
  const btnConfirmSubmit = document.getElementById('btn-confirm-submit');
  if (btnConfirmSubmit && form) {
    btnConfirmSubmit.addEventListener('click', function () {
      btnConfirmSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving Report...';
      btnConfirmSubmit.disabled = true;
      form.submit();
    });
  }

  function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  }

  function getPriorityColor(priority) {
    const map = { 'Critical': 'danger', 'High': 'warning', 'Medium': 'primary', 'Low': 'info' };
    return map[priority] || 'secondary';
  }
});
