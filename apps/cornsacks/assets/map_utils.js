// Organize our namespace
window.dash_leaflet = window.dash_leaflet || {};
window.dash_leaflet.cornsacks = {
    // 1. Styyyyyylin
    pointToLayerIncident: function(feature, latlng, context) {
        const colors = (context.hideout && context.hideout.colors) || {};
        const defaultColor = (context.hideout && context.hideout.defaultColor) || "#808080";
        const incidentType = feature.properties.incident_type;
        const markerColor = colors[incidentType] || defaultColor;

        return L.circleMarker(latlng, {
            radius: 5,
            color: markerColor,
            fillColor: markerColor,
            fill: true,
            fillOpacity: 0.55,
            opacity: 0.55,
            weight: 1
        });
    },

    pointToLayerDeptHq: function(feature, latlng, context) {
        const svgString = (context.hideout && context.hideout.hqSvg) || '';

        return L.marker(latlng, {
            icon: L.divIcon({
                className: 'hq-marker',
                html: svgString,
                iconSize: [24, 24],
                iconAnchor: [12, 12],
                opacity: 0.80
            })
        });
    },

    pointToLayerStation: function(feature, latlng, context) {
        const svgString = (context.hideout && context.hideout.stationSvg) || '';
        const size = (context.hideout && context.hideout.stationSize) || [10, 15];

        return L.marker(latlng, {
            icon: L.divIcon({
                className: 'station-marker',
                html: svgString,
                iconSize: size,
                iconAnchor: [size[0] / 2, size[1] / 2],
                opacity: 0.80
            })
        });
    },

    styleDeptJurisdiction: function(feature) {
        return {
            fillColor: '#465187',
            fillOpacity: 0.12,
            color: '#1e165c',
            opacity: 0.465187,
            weight: 1
        };
    },


    // 2. Interaction
    renderPopupDeptHq: function(feature, layer) {
        if (feature.properties) {
            const props = feature.properties;
            const addressParts = [
                props.address_line_1,
                props.address_line_2,
                `${props.city || ''}, ${props.state || ''} ${props.zip_code || ''}`.trim()
            ].filter(part => part && part !== 'null' && part !== ',');

            const popupContent = `
                <div style="font-family: sans-serif; line-height: 1.4; min-width: 200px;">
                    <b style="color: #333; font-size: 1.1em;">Department HQ: ${props.name || 'Department HQ'}</b><hr style="margin: 8px 0; border: 0; border-top: 1px solid #eee;">
                    <span style="color: #555;">${addressParts.join('<br>')}</span>
                </div>
            `;
            layer.bindPopup(popupContent);
        }
    },

    renderPopupStation: function(feature, layer) {
        if (feature.properties) {
            const props = feature.properties;
            const addressParts = [
                props.address_line_1,
                props.address_line_2,
                `${props.city || ''}, ${props.state || ''} ${props.zip_code || ''}`.trim()
            ].filter(part => part && part !== 'null' && part !== ',');

            const popupContent = `
                <div style="font-family: sans-serif; line-height: 1.4; min-width: 220px;">
                    <b style="color: #333; font-size: 1.1em;">Fire Station: ${props.station_name || 'Fire Station'}</b><hr style="margin: 8px 0; border: 0; border-top: 1px solid #eee;">
                    <span style="color: #555;">${addressParts.join('<br>')}</span>
                </div>
            `;
            layer.bindPopup(popupContent);
        }
    },
    renderPopupIncident: function(feature, layer) {
        if (feature.properties && feature.properties.neris_id_incident) {
            const props = feature.properties;

            // Generate the URL safe incident ID and extract department ID for the URL
            const incidentId = props.neris_id_incident;
            const deptId = incidentId.split('|')[0];
            const urlSafeIncidentId = incidentId.replace(/\|/g, '%7C');
            const url = `https://neris.fsri.org/departments/${deptId}/incidents/${urlSafeIncidentId}`;

            const popupContent = `
                <div style="font-family: sans-serif; line-height: 1.4; min-width: 200px;">
                    <b style="color: #333; font-size: 1.1em;">Incident: ${incidentId}</b><hr style="margin: 8px 0; border: 0; border-top: 1px solid #eee;">
                    <span style="color: #555;"><b>Department</b>: ${props.department_name || 'No Department Provided'}</span><br>
                    <span style="color: #555;"><b>Call Created</b>: ${props.call_create || 'No Call Created Provided'}</span><br>
                    <span style="color: #555;"><b>Location</b>: ${props.civic_location || 'No Location Provided'}</span><br>
                    <span style="color: #555;"><b>Incident Type</b>: ${props.incident_type || 'No Incident Type Provided'}</span>
                    <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #eee;">
                        <a href="${url}" target="_blank" style="color: rgb(60, 86, 231); text-decoration: none; font-weight: bold;">
                            See the incident page in NERIS →
                        </a>
                    </div>
                </div>
            `;
            layer.bindPopup(popupContent);
        }
    }
};
