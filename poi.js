//#region POI
  const poiLayer = L.layerGroup().addTo(map);
  const poiSearchPreviewLayer = L.layerGroup().addTo(map);
  const pois = [];
  let poiCounter = 0;
  let pendingPoiLatLng = null;
  let poiSearchPreviewMarker = null;
  const collapsedPoiGroups = new Set();
  const poiListEl = document.getElementById('poi-list');
  const poiModalBackdrop = document.getElementById('poi-modal-backdrop');
  const poiNameInput = document.getElementById('poi-name-input');
  const poiGroupInput = document.getElementById('poi-group-input');
  const poiGroupOptions = document.getElementById('poi-group-options');

  function showPoiSearchResult(latlng, label){
    poiSearchPreviewLayer.clearLayers();
    poiSearchPreviewMarker = L.marker(latlng, {
      icon: L.divIcon({
        className: 'poi-search-preview-icon',
        html: '<div class="poi-search-preview-marker">&#9733;</div>',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      }),
      interactive: true
    }).addTo(poiSearchPreviewLayer);
    poiSearchPreviewMarker.bindTooltip((label || 'Suchergebnis') + '<br>Rechtsklick: Als POI speichern', { direction: 'top', offset: [0, -14] });
    poiSearchPreviewMarker.on('contextmenu', e => {
      L.DomEvent.stop(e);
      showCustomContextMenu(e.originalEvent.clientX, e.originalEvent.clientY, [
        { label: 'Als POI speichern', action: () => openPoiModal(latlng) }
      ]);
    });
    map.setView(latlng, Math.max(map.getZoom(), 13));
  }

  function poiIcon(color){
    return L.divIcon({
      className: 'poi-marker-icon',
      html: `<div class="poi-marker" style="color:${color};">&#9733;</div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
  }

  function hexToRgb(hex){
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    const num = parseInt(hex, 16);
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  }
  function colorsAreSimilar(a, b, threshold){
    const ca = hexToRgb(a), cb = hexToRgb(b);
    const dist = Math.sqrt((ca.r - cb.r) ** 2 + (ca.g - cb.g) ** 2 + (ca.b - cb.b) ** 2);
    return dist <= (threshold || 30);
  }

  function buildPoiPopupContent(poi){
    const container = document.createElement('div');
    container.className = 'poi-popup';

    const title = document.createElement('strong');
    title.textContent = poi.name;
    container.appendChild(title);

    const groupEl = document.createElement('div');
    groupEl.className = 'poi-popup-group';
    groupEl.textContent = poi.poi_group;
    container.appendChild(groupEl);

    const btnRow = document.createElement('div');
    btnRow.className = 'poi-popup-actions';
    [['Start', 'start'], ['Via', 'via'], ['Ziel', 'end']].forEach(([lbl, role]) => {
      const b = document.createElement('button');
      b.className = 'poi-popup-btn';
      b.textContent = lbl;
      b.addEventListener('click', () => {
        insertWaypointAtRole(L.latLng(poi.lat, poi.lng), role, poi.name);
        poi.marker.closePopup();
      });
      btnRow.appendChild(b);
    });
    container.appendChild(btnRow);

    const searchRow = document.createElement('div');
    searchRow.className = 'poi-popup-actions';
    const searchBtn = document.createElement('button');
    searchBtn.className = 'poi-popup-btn poi-popup-btn-wide';
    searchBtn.innerHTML = '🔍 In Google suchen';
    searchBtn.addEventListener('click', () => {
      window.open('https://www.google.com/search?q=' + encodeURIComponent(poi.name), '_blank', 'noopener');
    });
    searchRow.appendChild(searchBtn);
    container.appendChild(searchRow);

    return container;
  }

  function addPoiInternal(name, poi_group, lat, lng, visible, color, dbid = -1, isShared){
    const id = dbid || -1;
    const poiColor = color || getDefaultPoiColor();
    const marker = L.marker([lat, lng], { icon: poiIcon(poiColor), draggable: true });
    const poi = { id, name, poi_group, lat, lng, marker, visible: visible !== false, color: poiColor, isShared: isShared };
    marker.bindTooltip(() => {
      const content = document.createElement('div');
      const nameEl = document.createElement('div');
      nameEl.className = 'poi-hover-name';
      nameEl.textContent = poi.name;
      content.appendChild(nameEl);
      const groupEl = document.createElement('div');
      groupEl.className = 'poi-hover-group';
      groupEl.textContent = poi.poi_group;
      content.appendChild(groupEl);
      return content;
    }, { direction: 'top', offset: [0, -10], className: 'poi-hover-tooltip' });
    marker.bindPopup(() => buildPoiPopupContent(poi));
    marker.on('contextmenu', (e) => {
      L.DomEvent.stop(e);
      const items = [
        { label: 'Als Startpunkt setzen', action: () => insertWaypointAtRole(L.latLng(poi.lat, poi.lng), 'start', poi.name) },
        { label: 'Als Via-Punkt hinzufügen', action: () => insertWaypointAtRole(L.latLng(poi.lat, poi.lng), 'via', poi.name) },
        { label: 'Als Zielpunkt setzen', action: () => insertWaypointAtRole(L.latLng(poi.lat, poi.lng), 'end', poi.name) }
      ];
      showCustomContextMenu(e.originalEvent.clientX, e.originalEvent.clientY, items);
    });
    marker.on('dragend', () => {
      const pos = marker.getLatLng();
      poi.lat = pos.lat;
      poi.lng = pos.lng;
      savePoiToStorage(poi.lat, poi.lng, poi.name, poi.poi_group, poi.color, poi.id);
    });
    if (poi.visible) marker.addTo(poiLayer);
    pois.push(poi);
    return poi;
  }

  async function submitPOIList() {
    document.getElementById('btn-user-savePOI').disabled = true;
    const data = {pois: pois.map(p => ({
                  name: p.name,
                  poi_group: p.poi_group,
                  lat: p.lat,
                  lng: p.lng,
                  color: p.color
                  }))
              };
    try {
      const response = await apiFetch('addPOIList', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      
      const result = await response.json();
      showToast('POIs gespeichert: ' + `Neu: ${result.inserted}, aktualisiert: ${result.updated}`, 5000);

      document.getElementById('btn-user-savePOI').disabled = false;
    } catch (error) {
      showToast('Fehler beim hinzufügen der POIs: ' + error, 7000);
      console.warn('Fehler beim hinzufügen der POIs',error);
      document.getElementById('btn-user-savePOI').disabled = false;
    }
  }
  
  async function loadPoisFromStorage(){
    try {
      const response = await apiFetch('getPOIList', {
        method: 'GET'
      });
      const resp = await response.json()
      const data = resp.pois;
      clearPOIs();
      (data || []).forEach(p => addPoiInternal(p.name, p.poi_group, p.lat, p.lng, false, p.color, p.id));
    }
    catch (error) {
      showToast('Fehler beim laden der POIs: ' + error, 7000);
      console.warn('Fehler beim laden der POIs: ', error);
    }
  }

  async function savePoiToStorage(lat, lng, name, poi_group, color, id, isShared) {
    try {
      const poi = {lat, lng, name, poi_group, color, id, isShared};
      const response = await apiFetch('addPOI', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(poi),
        // body: poi,
      });
      const resp = await response.json();
      return resp.id;
    }
    catch (error) {
      showToast('Fehler beim speichern vom POI' + error, 2000);
      return -1;
    }
  }

  async function addPoi(latlng, name, poi_group){
    const poi = {lat:latlng.lat, lng:latlng.lng, name:name, poi_group:poi_group, color:getDefaultPoiColor(), id:-1, isShared: false};
    const id = await savePoiToStorage(poi.lat, poi.lng, poi.name, poi.poi_group, poi.color, poi.id);
    if (id != -1) {
      addPoiInternal(name, poi_group, latlng.lat, latlng.lng, true, getDefaultPoiColor(), id, poi.isShared);
      renderPoiList();
    }
  }

  async function delPoiFromStorage(id) {
    try {
      await apiFetch('delPOI', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json'},
        body: JSON.stringify({id: id})
      });
    }
    catch (error) {
      showToast('Fehler beim löschen vom POI' + error, 2000);
      return -1;
    }
  };

  function deletePoi(id){
    const idx = pois.findIndex(p => p.id === Number(id));
    if (idx === -1) return;
    delPoiFromStorage(id);
    poiLayer.removeLayer(pois[idx].marker);
    pois.splice(idx, 1);
    renderPoiList();
  }

  function setPoiVisible(poi, visible){
    poi.visible = visible;
    if (visible){ if (!poiLayer.hasLayer(poi.marker)) poi.marker.addTo(poiLayer); }
    else { if (poiLayer.hasLayer(poi.marker)) poiLayer.removeLayer(poi.marker); }
    saveAppStateDebounced();
  }

  function buildPoiGroupTree(){
    const root = { children: new Map(), items: [] };
    pois.forEach(p => {
      const parts = String(p.poi_group?.trim() || 'POI')
                             .split('/')
                             .map(s => s.trim())
                             .filter(Boolean);
      if (parts.length === 0) {
        parts.push('POI');
      }
      let node = root;
      let pathSoFar = '';
      parts.forEach(part => {
        pathSoFar = pathSoFar ? pathSoFar + '/' + part : part;
        if (!node.children.has(part)) node.children.set(part, { children: new Map(), items: [], path: pathSoFar, label: part });
        node = node.children.get(part);
      });
      node.items.push(p);
    });
    return root;
  }

  function collectAllPoisInNode(node){
    let all = [...node.items];
    node.children.forEach(child => { all = all.concat(collectAllPoisInNode(child)); });
    return all;
  }

  function movePoiToGroup(poiId, newGroupPath){
    const poi = pois.find(p => p.id === Number(poiId));
    if (!poi || poi.poi_group === newGroupPath) return;
    poi.poi_group = newGroupPath;
    savePoiToStorage(poi.lat, poi.lng, poi.name, poi.poi_group, poi.color, poi.id);
    renderPoiList();
  }

  function startInlineRename(displayEl, currentValue, onCommit){
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'inline-rename-input';
    input.value = currentValue;
    displayEl.replaceWith(input);
    input.focus();
    input.select();

    let committed = false;
    function commit(){
      if (committed) return;
      committed = true;
      const newValue = input.value.trim();
      if (newValue && newValue !== currentValue) onCommit(newValue);
      else renderPoiList();
    }
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') input.blur();
      if (ev.key === 'Escape'){ committed = true; renderPoiList(); }
    });
  }

  async function delPOIHelper(poi) {
    const ok = await confirmDialog(`Möchten Sie den POI "${poi.name}" wirklich löschen?`);
    if (!ok) return;
    deletePoi(poi.id); 
  }

  function getGroupState(groupName) {
    const groupPois = pois.filter(p => p.poi_group.startsWith(groupName));

    const visibleCount = groupPois.filter(
        p => p.visible
    ).length;

    if (visibleCount === 0) return 'hidden';
    if (visibleCount === groupPois.length) return 'visible';
    return 'partial';
  }

  function buildPoiRow(poi){
    const row = document.createElement('div');
    row.className = 'file-row';
    row.draggable = true;

    row.addEventListener('dragstart', (e) => {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/x-poi-id', poi.id);
      row.classList.add('dragging');
    });
    row.addEventListener('dragend', () => row.classList.remove('dragging'));
    row.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const items = [
        { label: 'Als Startpunkt setzen', action: () => insertWaypointAtRole(L.latLng(poi.lat, poi.lng), 'start', poi.name) },
        { label: 'Als Via-Punkt hinzufügen', action: () => insertWaypointAtRole(L.latLng(poi.lat, poi.lng), 'via', poi.name) },
        { label: 'Als Zielpunkt setzen', action: () => insertWaypointAtRole(L.latLng(poi.lat, poi.lng), 'end', poi.name) }
      ];
      showCustomContextMenu(e.clientX, e.clientY, items);
    });

    const handle = document.createElement('span');
    handle.className = 'waypoint-drag-handle';
    handle.innerHTML = '&#8942;&#8942;';
    handle.title = 'Ziehen, um die Gruppe zu ändern';
    row.appendChild(handle);

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = poi.visible;
    cb.addEventListener('change', () => { 
      setPoiVisible(poi, cb.checked);
      renderPoiList();
    });
    row.appendChild(cb);

    const swWrap = document.createElement('label');
    swWrap.className = 'swatch-wrap';
    swWrap.title = 'Farbe ändern';
    const sw = document.createElement('span');
    sw.className = 'swatch';
    sw.style.background = poi.color;
    swWrap.appendChild(sw);
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.className = 'swatch-input';
    colorInput.value = poi.color;
    colorInput.addEventListener('input', () => {
      poi.color = colorInput.value;
      sw.style.background = poi.color;
      poi.marker.setIcon(poiIcon(poi.color));
    });
    colorInput.addEventListener('change', () => { 
      savePoiToStorage(poi.lat, poi.lng, poi.name, poi.poi_group, poi.color, poi.id); 
    });    
    colorInput.addEventListener('click', (ev) => ev.stopPropagation());
    swWrap.appendChild(colorInput);
    row.appendChild(swWrap);

    const info = document.createElement('div');
    info.className = 'file-info';
    const nm = document.createElement('div');
    nm.className = 'file-name';
    nm.textContent = poi.name;
    if (authState.admin) nm.textContent = nm.textContent + `   (id:${+poi.id})`;
    nm.title = 'Klick: zur Karte springen · Doppelklick: umbenennen';
    nm.style.cursor = 'pointer';
    nm.addEventListener('click', () => {
      cb.checked = true;
      setPoiVisible(poi, cb.checked);
      map.setView([poi.lat, poi.lng], Math.max(map.getZoom(), 13));
      // poi.marker.openPopup();
    });
    nm.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      startInlineRename(nm, poi.name, (newName) => {
        if (newName.includes('/')) {
            const parts = newName.split('/').map(p => p.trim()).filter(Boolean);
            poi.name = parts.pop();           // letzter Teil = Name
            poi.poi_group = parts.join('/');      // alles davor = Gruppe
        } else {
            poi.name = newName.trim();
        }

        
        poi.name = newName;

        savePoiToStorage(poi.lat, poi.lng, poi.name, poi.poi_group, poi.color, poi.id);
        renderPoiList();
      });
    });
    info.appendChild(nm);
    row.appendChild(info);

    const delBtn = document.createElement('button');
    delBtn.className = 'row-icon-btn';
    const icon = document.createElement('span');
    icon.innerHTML = trashSVG;
    delBtn.appendChild(icon);
    delBtn.title = 'POI löschen';
    delBtn.addEventListener('click', (ev) => { 
      ev.stopPropagation(); 
      delPOIHelper(poi);
    });
    row.appendChild(delBtn);

    return row;
  }

  let poiGroupsInitialized = false;
    
  async function delPOIGroupHelper(child, descendants) {
    const ok = await confirmDialog(`Möchten Sie die Gruppe "${child.label}"" mit ${descendants.length} POIs wirklich löschen?`);
    if (!ok) return;
    
    descendants.forEach(p => { deletePoi(p.id); });
  }
  
  function renderPoiGroupNode(node, container){
    node.children.forEach(child => {
      const descendants = collectAllPoisInNode(child);
      // const entries = collectViewerEntries(child);
        
      if (!poiGroupsInitialized) {
        if (child.items.length > 0) 
        {
          collapsedPoiGroups.add(child.path);
        } 
        else 
        {
          collapsedPoiGroups.delete(child.path);
        }
      }
      const collapsed = collapsedPoiGroups.has(child.path);

      const groupEl = document.createElement('div');
      groupEl.className = 'group';

      const header = document.createElement('div');
      header.className = 'group-header' + (collapsed ? ' collapsed' : '');

      const twist = document.createElement('span');
      twist.className = 'twist';
      twist.textContent = '▾';
      header.appendChild(twist);

      // geht nicht 
      // const allVisible = descendants.every(p => p.visible);
      // const noneVisible = descendants.every(p => !p.visible);

      // von routen, da gehts
      const allVisible = descendants.length > 0 && descendants.every(entry => entry.visible);
      const noneVisible = descendants.every(entry => !entry.visible);

      const groupCb = document.createElement('input');
      groupCb.type = 'checkbox';
      groupCb.checked = allVisible;
      groupCb.indeterminate = !allVisible && !noneVisible;


      // am schluss nach dem rendern machen, wenn alle childs vorhanden sind
      // const state = getGroupState(child.label);
      // groupCb.checked = state === 'visible';
      // groupCb.indeterminate = state === 'partial';

      groupCb.addEventListener('click', ev => ev.stopPropagation());
      groupCb.addEventListener('change', () => {
        descendants.forEach(p => setPoiVisible(p, groupCb.checked));
        renderPoiList();
        saveAppStateDebounced();
      });
      header.appendChild(groupCb);

      const nameEl = document.createElement('span');
      nameEl.className = 'group-name';
      nameEl.textContent = child.label;
      nameEl.title = 'Doppelklick: Gruppe umbenennen';
      header.appendChild(nameEl);

      const countEl = document.createElement('span');
      countEl.className = 'group-count';
      countEl.textContent = descendants.length;
      header.appendChild(countEl);

      const groupDelBtn = document.createElement('button');
      groupDelBtn.className = 'row-icon-btn group-del-btn';
      const icon = document.createElement('span');
      icon.innerHTML = trashSVG;
      groupDelBtn.appendChild(icon);
      groupDelBtn.title = 'Ganze Gruppe löschen';
      groupDelBtn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        delPOIGroupHelper(child, descendants);
      });
      header.appendChild(groupDelBtn);

      header.addEventListener('click', (e) => {
        if (e.target === nameEl) return; // let dblclick-to-rename own this element
        if (collapsedPoiGroups.has(child.path)) collapsedPoiGroups.delete(child.path);
        else collapsedPoiGroups.add(child.path);
        renderPoiList();
      });

      nameEl.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        startInlineRename(nameEl, child.label, (newLabel) => {
          const parentPath = child.path.includes('/') ? child.path.slice(0, child.path.lastIndexOf('/')) : '';
          const newPath = parentPath ? parentPath + '/' + newLabel : newLabel;
          pois.forEach(poi => {
            if (poi.poi_group === child.path) {
              poi.poi_group = newPath;
              savePoiToStorage(poi.lat, poi.lng, poi.name, poi.poi_group, poi.color, poi.id);
            }
            else if (poi.poi_group.startsWith(child.path + '/')) { 
              poi.poi_group = newPath + poi.poi_group.slice(child.path.length);
              savePoiToStorage(poi.lat, poi.lng, poi.name, poi.poi_group, poi.color, poi.id);
            }
          });
          renderPoiList();
        });
      });

      header.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        header.classList.add('drop-target');
      });
      header.addEventListener('dragleave', () => header.classList.remove('drop-target'));
      header.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        header.classList.remove('drop-target');
        const poiId = e.dataTransfer.getData('text/x-poi-id');
        if (!poiId) return;
        movePoiToGroup(poiId, child.path);
      });

      groupEl.appendChild(header);

      // Fallback: dropping anywhere else in this group's box (not on a more
      // specific nested header, which stops propagation) also files under it.
      groupEl.addEventListener('dragover', (e) => {
        e.preventDefault();
        groupEl.classList.add('drop-target-box');
      });
      groupEl.addEventListener('dragleave', (e) => {
        if (!groupEl.contains(e.relatedTarget)) groupEl.classList.remove('drop-target-box');
      });
      groupEl.addEventListener('drop', (e) => {
        e.preventDefault();
        groupEl.classList.remove('drop-target-box');
        const poiId = e.dataTransfer.getData('text/x-poi-id');
        if (!poiId) return;
        movePoiToGroup(poiId, child.path);
      });

      const childWrap = document.createElement('div');
      childWrap.className = 'file-list' + (collapsed ? ' collapsed' : '');

      child.items.forEach(poi => childWrap.appendChild(buildPoiRow(poi)));
      renderPoiGroupNode(child, childWrap);

      groupEl.appendChild(childWrap);
      container.appendChild(groupEl);
    });
  }

  function renderPoiList(){
    const scrollPos = poiListEl.scrollTop;
    poiListEl.innerHTML = '';

    if (pois.length === 0){
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.innerHTML = '<div>Noch keine POIs gespeichert.<br>Rechtsklick auf die Karte →<br>"Als POI speichern".</div>';
      poiListEl.appendChild(empty);
      return;
    }

    const root = buildPoiGroupTree();
    renderPoiGroupNode(root, poiListEl);
    poiGroupsInitialized = true;

    poiListEl.scrollTop = scrollPos;
  }

  function clearPOIs() {
    pois.length = 0;
    renderPoiList();
  }
  const poiSearchInput = document.getElementById('poi-search');
  const btnSearchPoi = document.getElementById('btn-search-poi');
  const poiSearchResultsEl = document.getElementById('poi-search-results');

  async function runPoiSearch(){
    const q = poiSearchInput.value.trim();
    if (!q) return;
    poiSearchResultsEl.innerHTML = '<div class="search-result-item">Suche läuft …</div>';
    const results = await searchPlace(q);
    poiSearchResultsEl.innerHTML = '';
    if (!results.length){
      poiSearchResultsEl.innerHTML = '<div class="search-result-item">Nichts gefunden.</div>';
      return;
    }
    results.forEach(r => {
      const item = document.createElement('div');
      item.className = 'search-result-item';
      item.textContent = r.display_name;
      item.addEventListener('click', () => {
        const latlng = L.latLng(parseFloat(r.lat), parseFloat(r.lon));
        showPoiSearchResult(latlng, shortLabel(r.display_name));
        poiSearchResultsEl.innerHTML = '';
        poiSearchInput.value = '';
      });
      poiSearchResultsEl.appendChild(item);
    });
  }

  btnSearchPoi.addEventListener('click', runPoiSearch);
  poiSearchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') runPoiSearch(); });
  let poiSearchDebounceTimer = null;
  poiSearchInput.addEventListener('input', () => {
    if (poiSearchDebounceTimer) clearTimeout(poiSearchDebounceTimer);
    if (poiSearchInput.value.trim().length < 3){
      poiSearchResultsEl.innerHTML = '';
      return;
    }
    poiSearchDebounceTimer = setTimeout(runPoiSearch, 500);
  });

  function openPoiModal(latlng){
    pendingPoiLatLng = latlng;
    poiNameInput.value = '';
    poiGroupInput.value = '';
    poiGroupOptions.innerHTML = '';
    [...new Set(pois.map(p => p.poi_group))].forEach(g => {
      const opt = document.createElement('option');
      opt.value = g;
      poiGroupOptions.appendChild(opt);
    });
    poiModalBackdrop.classList.add('active');
    poiNameInput.focus();
  }

  function closePoiModal(){
    poiModalBackdrop.classList.remove('active');
    pendingPoiLatLng = null;
  }

  document.getElementById('poi-modal-cancel').addEventListener('click', closePoiModal);
  poiModalBackdrop.addEventListener('click', (e) => { if (e.target === poiModalBackdrop) closePoiModal(); });
  document.getElementById('poi-modal-save').addEventListener('click', () => {
    const name = poiNameInput.value.trim() || 'Unbenannt';
    const group = poiGroupInput.value.trim() || 'POI';
    if (pendingPoiLatLng) addPoi(pendingPoiLatLng, name, group);
    closePoiModal();
  });
  poiNameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') poiGroupInput.focus(); });
  poiGroupInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') document.getElementById('poi-modal-save').click(); });
  //#endregion
