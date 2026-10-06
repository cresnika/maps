  const settingsModalBackdrop = document.getElementById('settings-modal-backdrop');
  const settingsDefaultPoiColorInput = document.getElementById('settings-default-poi-color');
  const DEFAULT_POI_COLOR_FALLBACK = '#3b82f6';
  let cachedDefaultPoiColor = DEFAULT_POI_COLOR_FALLBACK;

  settingsModalBackdrop.addEventListener('click', (e) => {
            e.stopPropagation();
        //   if (e.target === settingsModalBackdrop) settingsModalBackdrop.classList.remove('active');
        });
  
  function getDefaultPoiColor(){
    return cachedDefaultPoiColor;
  }
  async function defaultPoiColorChanged() {
    cachedDefaultPoiColor = settingsDefaultPoiColorInput.value;
    // saveAppStateDebounced(); 
  }
  settingsDefaultPoiColorInput.addEventListener('change', () => { defaultPoiColorChanged(); })

  document.getElementById('btn-theme').addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    setTheme(current === 'dark' ? 'light' : 'dark');
  });  