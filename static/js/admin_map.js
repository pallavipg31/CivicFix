/**
 * CivicFix - Civic Action Center Leaflet Admin Map
 */

document.addEventListener('DOMContentLoaded', function () {
  const mapElem = document.getElementById('admin-map');
  if (!mapElem) return;

  const map = L.map('admin-map').setView([12.9716, 77.5946], 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  const markerLayerGroup = L.layerGroup().addTo(map);
  const clusterLayerGroup = L.layerGroup().addTo(map);

  let rawIssuesData = [];
  let rawClustersData = [];
  let currentFilter = 'all';

  function fetchAndRenderMap() {
    fetch('/api/map-issues/')
      .then(res => res.json())
      .then(data => {
        rawIssuesData = data.issues || [];
        rawClustersData = data.clusters || [];
        applyFilter(currentFilter);

        // Fit bounds if markers exist
        if (rawIssuesData.length > 0) {
          const group = L.featureGroup(rawIssuesData.map(i => L.marker([i.latitude, i.longitude])));
          map.fitBounds(group.getBounds().pad(0.15));
        }
      })
      .catch(err => console.error('Map loading error:', err));
  }

  function applyFilter(filterKey) {
    currentFilter = filterKey;
    markerLayerGroup.clearLayers();
    clusterLayerGroup.clearLayers();

    // 1. Filter Issues
    const filteredIssues = rawIssuesData.filter(issue => {
      if (filterKey === 'all') return true;
      if (filterKey === 'pothole') return issue.category === 'pothole';
      if (filterKey === 'water') return issue.category === 'water';
      if (filterKey === 'waste') return issue.category === 'waste';
      if (filterKey === 'critical') return issue.priority === 'Critical';
      if (filterKey === 'high') return issue.priority === 'High' || issue.priority === 'Critical';
      if (filterKey === 'unresolved') return issue.status !== 'Resolved' && issue.status !== 'Rejected';
      if (filterKey === 'clusters') return false; // Show only cluster overlays
      return true;
    });

    filteredIssues.forEach(issue => {
      const pinColor = issue.color || '#0d9488';
      const icon = L.divIcon({
        className: 'custom-admin-pin',
        html: `
          <div style="
            background: ${pinColor};
            width: 32px;
            height: 32px;
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            border: 2.5px solid white;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
          ">
            <span style="transform: rotate(45deg); font-size: 14px;">${issue.emoji}</span>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -28]
      });

      const marker = L.marker([issue.latitude, issue.longitude], { icon: icon });

      const popupHtml = `
        <div style="min-width: 220px; font-family: 'Plus Jakarta Sans', sans-serif;">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="badge bg-dark">${issue.tracking_code}</span>
            <span class="badge bg-${getPriorityBadgeColor(issue.priority)}">${issue.priority}</span>
          </div>
          <h6 class="fw-bold mb-1" style="font-size: 0.95rem; color: #0f172a;">${issue.title}</h6>
          <p class="text-muted small mb-2"><i class="bi bi-geo-alt"></i> ${issue.location_name}</p>
          <div class="d-flex justify-content-between align-items-center pt-2 border-top">
            <span class="badge bg-secondary">${issue.status}</span>
            <a href="${issue.detail_url}" class="btn btn-sm btn-primary text-white" style="font-size: 0.75rem; border-radius: 6px;">
              Action <i class="bi bi-arrow-right-short"></i>
            </a>
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml);
      markerLayerGroup.addLayer(marker);
    });

    // 2. Render Clusters (if filter is 'all', 'clusters', or category matches)
    if (filterKey === 'all' || filterKey === 'clusters' || ['pothole', 'water', 'waste', 'critical'].includes(filterKey)) {
      rawClustersData.forEach(cluster => {
        if (filterKey === 'pothole' && cluster.category !== 'pothole') return;
        if (filterKey === 'water' && cluster.category !== 'water') return;
        if (filterKey === 'waste' && cluster.category !== 'waste') return;

        const circleColor = cluster.priority === 'Critical' ? '#ef4444' : '#ea580c';

        const circle = L.circle([cluster.latitude, cluster.longitude], {
          color: circleColor,
          fillColor: circleColor,
          fillOpacity: 0.18,
          weight: 2,
          dashArray: '6, 6',
          radius: 650
        });

        const clusterPopup = `
          <div style="min-width: 230px;">
            <span class="badge bg-danger mb-1"><i class="bi bi-diagram-3-fill me-1"></i> ${cluster.title}</span>
            <h6 class="fw-bold mb-1">${cluster.count} Active Reports Detected</h6>
            <p class="text-muted small mb-2"><i class="bi bi-geo-alt-fill"></i> ${cluster.location_label}</p>
            <div class="p-2 bg-light rounded small mb-2 border">
              <strong>Action:</strong> ${cluster.recommended_action}
            </div>
          </div>
        `;
        circle.bindPopup(clusterPopup);
        clusterLayerGroup.addLayer(circle);
      });
    }
  }

  // Filter Buttons Hookup
  const filterButtons = document.querySelectorAll('[data-map-filter]');
  filterButtons.forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      filterButtons.forEach(b => b.classList.remove('active', 'btn-primary'));
      filterButtons.forEach(b => b.classList.add('btn-outline-secondary'));

      this.classList.remove('btn-outline-secondary');
      this.classList.add('active', 'btn-primary');

      const filter = this.getAttribute('data-map-filter');
      applyFilter(filter);
    });
  });

  function getPriorityBadgeColor(p) {
    const map = { 'Critical': 'danger', 'High': 'warning text-dark', 'Medium': 'primary', 'Low': 'info text-dark' };
    return map[p] || 'secondary';
  }

  fetchAndRenderMap();
});
