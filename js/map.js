const key = 'Vr8csikavibrZIA07nBS';
const osmStandard = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {});
const openTopo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {});
const stadiaSmooth = L.tileLayer(`https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png`,);
const stadiaOutdoors = L.maplibreGL({style: 'https://tiles.stadiamaps.com/styles/outdoors.json',});
const TerrainStyle = L.maplibreGL({style: 'styles/Terrain.json',});
const satelliteStyle = L.tileLayer(`https://api.maptiler.com/tiles/satellite-v2/{z}/{x}/{y}.png?key=${key}`,{ //style URL
                                    tileSize: 512,
                                    zoomOffset: -1,
                                    minZoom: 1,
                                    maxZoom: 20,
                                    attribution: "\u003ca href=\"https://www.maptiler.com/copyright/\" target=\"_blank\"\u003e\u0026copy; MapTiler\u003c/a\u003e \u003ca href=\"https://www.openstreetmap.org/copyright\" target=\"_blank\"\u003e\u0026copy; OpenStreetMap contributors\u003c/a\u003e",
                                    crossOrigin: true
                                  });

const map = L.map('map', {zoomControl: true,
                          maxZoom: 20,
                          preferCanvas: true
                         }).setView([47.2, 9.6], 9);

const baseLayers = {'Terrain' : TerrainStyle,
                    'Satellit' : satelliteStyle,
                    'OpenStreetMap': osmStandard,
                    'Topographisch': openTopo,
                    'Stadia – Outdoor': stadiaOutdoors,
                    'Stadia – Hell / reduziert': stadiaSmooth
                   };
// Below this zoom level, clicked points are snapped to the nearest routable
// road/path -- at this zoom or closer, the exact clicked pixel is used.
// Below the stricter zoom, only named (i.e. typically more major) roads are
// considered, so a big overview click doesn't snap onto every minor track.
const ROAD_SNAP_MAX_ZOOM = 18;
const ROAD_SNAP_STRICT_ZOOM = 7;

let actualStyle = null;

const layerControl = L.control.layers(baseLayers, null, {collapsed: true,
                                                         position: 'bottomleft'
                                                        }).addTo(map);
layerControl.getContainer().style.zIndex = '2001';  

  // Reliably suppress the browser's native right-click menu on the map,
  // independent of Leaflet's own internal listener-presence check.
  map.getContainer().addEventListener('contextmenu', (e) => e.preventDefault());  
                        
  const calculatedRouteStyle = { color: '#22a6ff', weight: 5, opacity: 0.8, lineJoin: 'round' };
  L.control.scale({position: 'bottomright',   // 'topleft', 'topright', 'bottomleft', 'bottomright'
                   metric: true,               // km/m anzeigen
                   imperial: false,            // mi/ft NICHT anzeigen (falls nur metrisch gewünscht)
                   maxWidth: 100,               // maximale Breite der Scale-Bar in Pixel
                   updateWhenIdle: false        // Aktualisierung während des Zoomens/Pannens
                  }).addTo(map);

  map.createPane('waypointPane');
  map.getPane('waypointPane').style.zIndex = 650; // Standard-Marker-Pane liegt bei 600

  // ---------- LEflet cluster ----------
  function createClusterLayer(poi, options = {}) {   
    const clusterGroup = L.markerClusterGroup({      
      maxClusterRadius: 60,
      disableClusteringAtZoom: 15,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,

      iconCreateFunction: (cluster) => {
        const count = cluster.getChildCount();
        const size = count >= 50 ? 'large' : count >= 10 ? 'medium' : 'small';
        const sizePx = size === 'large' ? 52 : size === 'medium' ? 42 : 34;

        return L.divIcon({
          html: `
            <div class="poi-cluster poi-cluster-${size}">
              <span class="poi-cluster-icon">${poi.labelicon.options.html}</span>
              <span class="poi-cluster-count">${count}</span>
            </div>`,
          className: `poi-cluster-wrapper extern-poi-marker ${poi.mapicon.options.className}`, // NEU: Farb-Klasse jetzt am AEUSSEREN Wrapper
          iconSize: L.point(sizePx, sizePx),
        });
      },
      ...options,
    });

    // Rechtsklick auf eine Cluster-Bubble soll KEIN Kontextmenue
    clusterGroup.on('clustercontextmenu', (e) => {
      L.DomEvent.preventDefault(e.originalEvent);
      L.DomEvent.stopPropagation(e);
    });

    return clusterGroup;
  }

  TerrainStyle.addTo(map);

  map.on('baselayerchange', function (e) {
      actualStyle = Object.keys(baseLayers).find(
          name => baseLayers[name] === e.layer
      );
      saveAppStateDebounced();
  });

  async function snapToRoadIfZoomedOut(latlng){
    const zoom = map.getZoom();
    if (zoom >= ROAD_SNAP_MAX_ZOOM) return latlng;
    const profile = document.getElementById('planning-route-profile').value;
    const preferNamed = zoom < ROAD_SNAP_STRICT_ZOOM;
    const count = preferNamed ? 8 : 1;
    const url = `https://router.project-osrm.org/nearest/v1/${profile}/${latlng.lng},${latlng.lat}?number=${count}`;
    try {
      const resp = await fetch(url);
      const data = await resp.json();
      if (data.code === 'Ok' && data.waypoints && data.waypoints.length){
        let chosen = data.waypoints[0];
        if (preferNamed){
          const named = data.waypoints.find(w => w.name && w.name.trim().length > 0);
          if (named) chosen = named;
        }
        return L.latLng(chosen.location[1], chosen.location[0]);
      }
    } catch (e){ /* network error -- fall back to the exact clicked point */ }
    return latlng;
  }


