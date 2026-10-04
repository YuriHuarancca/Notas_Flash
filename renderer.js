// Universal Bridge supporting pywebview (Python WebView2) and Electron
(function initBridge() {
  if (!window.widgetAPI) {
    const getApi = () => (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
    const waitForApi = () => {
      const immediate = getApi();
      if (immediate) return Promise.resolve(immediate);
      return new Promise((resolve) => {
        const handler = () => {
          window.removeEventListener('pywebviewready', handler);
          resolve(getApi());
        };
        window.addEventListener('pywebviewready', handler);
        setTimeout(() => resolve(getApi()), 1200);
      });
    };

    window.widgetAPI = {
      windowReady: async () => {
        const api = await waitForApi();
        if (api && api.window_ready) {
          try { return await api.window_ready(); } catch (e) { console.error(e); }
        }
        return false;
      },
      getInitialData: async () => {
        const api = await waitForApi();
        if (api && api.get_initial_data) {
          try { return await api.get_initial_data(); } catch (e) { console.error(e); }
        }
        try {
          const raw = localStorage.getItem('win11-widget-data');
          if (raw) return JSON.parse(raw);
        } catch (e) {}
        return null;
      },
      togglePin: async (state) => {
        const api = getApi();
        if (api && api.toggle_pin) {
          try { return await api.toggle_pin(state); } catch (e) { console.error(e); }
        }
        return Boolean(state);
      },
      minimizeWindow: () => {
        const api = getApi();
        if (api && api.minimize) api.minimize();
      },
      closeWindow: () => {
        const api = getApi();
        if (api && api.close) api.close();
        else window.close();
      },
      saveData: async (data) => {
        const api = getApi();
        if (api && api.save_data) {
          try { return await api.save_data(data); } catch (e) { console.error(e); }
        }
        try {
          const cur = JSON.parse(localStorage.getItem('win11-widget-data') || '{}');
          localStorage.setItem('win11-widget-data', JSON.stringify({ ...cur, ...data }));
        } catch (e) {}
        return true;
      },
      exportFile: async (data) => {
        const api = getApi();
        if (api && api.export_file) {
          try { return await api.export_file(data); } catch (e) { console.error(e); }
        }
        return { success: false, error: 'No API' };
      },
      importFile: async () => {
        const api = getApi();
        if (api && api.import_file) {
          try { return await api.import_file(); } catch (e) { console.error(e); }
        }
        return { success: false, error: 'No API' };
      },
      manualResizeStep: (delta) => {
        const api = getApi();
        if (api && api.resize_step) {
          try { api.resize_step(delta); } catch (e) { console.error(e); }
        }
      },
      moveWindowStep: (delta) => {
        const api = getApi();
        if (api && api.move_step) {
          try { return api.move_step(delta); } catch (e) { console.error(e); }
        }
      },
      getWindowRect: async () => {
        const api = getApi();
        if (api && api.get_window_rect) {
          try { return await api.get_window_rect(); } catch (e) { console.error(e); }
        }
        return null;
      },
      setWindowPosition: (pos) => {
        const api = getApi();
        if (api && api.set_window_position) {
          try { return api.set_window_position(pos); } catch (e) { console.error(e); }
        }
      },
      setWindowGeometry: (geom) => {
        const api = getApi();
        if (api && api.set_window_geometry) {
          try { return api.set_window_geometry(geom); } catch (e) { console.error(e); }
        }
      },
      saveWindowPosition: () => {
        const api = getApi();
        if (api && api.save_window_position) {
          try { api.save_window_position(); } catch (e) { console.error(e); }
        }
      },
      toggleCompactMode: async (isCompact) => {
        const api = getApi();
        if (api && api.toggle_compact_mode) {
          try { return await api.toggle_compact_mode(isCompact); } catch (e) { console.error(e); }
        }
        return { isCompact };
      },
      onPinChanged: (cb) => {
        window.addEventListener('pin-changed', (e) => cb(e.detail));
      }
    };
  }
})();

async function initApp() {
  // DOM Elements
  const widgetContainer = document.getElementById('widgetContainer');
  const widgetHeader = document.getElementById('widgetHeader');
  const widgetTitle = document.getElementById('widgetTitle');
  const floatingToast = document.getElementById('floatingToast');
  const modalUnsaved = document.getElementById('modalUnsaved');
  const btnModalSave = document.getElementById('btnModalSave');
  const btnModalDiscard = document.getElementById('btnModalDiscard');
  const btnModalCancel = document.getElementById('btnModalCancel');

  // Animación de entrada de alto impacto (Caída Elástica Rápida 300ms)
  window.triggerEntranceAnimation = function triggerEntranceAnimation() {
    if (!widgetContainer) return;
    widgetContainer.classList.remove('anim-cinematic-enter');
    void widgetContainer.offsetWidth;
    widgetContainer.classList.add('anim-cinematic-enter');
  };

  // Header controls
  const btnPin = document.getElementById('btnPin');
  const pinBadge = document.getElementById('pinBadge');
  const btnCompact = document.getElementById('btnCompact');
  const btnMinimize = document.getElementById('btnMinimize');
  const btnClose = document.getElementById('btnClose');

  // Toolbar controls
  const btnBulletList = document.getElementById('btnBulletList');
  const btnNumberedList = document.getElementById('btnNumberedList');
  const btnChecklist = document.getElementById('btnChecklist');
  const btnBold = document.getElementById('btnBold');
  const btnItalic = document.getElementById('btnItalic');
  const btnUnderline = document.getElementById('btnUnderline');
  const btnStrike = document.getElementById('btnStrike');
  const btnHeading = document.getElementById('btnHeading');
  const btnFontSizeDown = document.getElementById('btnFontSizeDown');
  const btnFontSizeUp = document.getElementById('btnFontSizeUp');
  const btnImport = document.getElementById('btnImport');
  const btnExport = document.getElementById('btnExport');
  const btnPalette = document.getElementById('btnPalette');
  const btnClear = document.getElementById('btnClear');
  const themePopup = document.getElementById('themePopup');

  // Editor and Footer
  const noteEditor = document.getElementById('noteEditor');
  const statWords = document.getElementById('statWords');
  const selectOpacity = document.getElementById('selectOpacity');
  const resizeGrip = document.getElementById('resizeGrip');

  // State
  let isPinned = false;
  let isCompact = false;
  let preCompactHeight = 500;
  let currentTheme = 'theme-dark-mica';
  let currentFontSize = 15.0;
  let hasUnexportedChanges = false;
  // Backward compatibility: sanitize legacy todo items to modern task-list
  function sanitizeChecklists(html) {
    if (!html) return html || '';
    if (html.includes('todo-item')) {
      const temp = document.createElement('div');
      temp.innerHTML = html;
      const oldItems = temp.querySelectorAll('.todo-item');
      if (oldItems.length > 0) {
        const taskList = document.createElement('ul');
        taskList.className = 'task-list';
        oldItems.forEach(item => {
          const checkbox = item.querySelector('.todo-checkbox');
          const textSpan = item.querySelector('.todo-text');
          const isChecked = (checkbox && checkbox.checked) || item.classList.contains('checked');
          const text = textSpan ? textSpan.innerText : item.innerText;
          const li = document.createElement('li');
          li.setAttribute('data-checked', isChecked ? 'true' : 'false');
          li.innerText = text.trim() || 'Tarea';
          taskList.appendChild(li);
        });
        oldItems[0].parentNode.insertBefore(taskList, oldItems[0]);
        oldItems.forEach(i => i.remove());
        return temp.innerHTML;
      }
    }
    return html;
  }

  // Minimalist ultra-short timestamp for header title (e.g. 04/10 · 12:25)
  function getMinimalTimestamp(d = new Date()) {
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month} · ${hours}:${minutes}`;
  }

  // Render síncrono instantáneo desde caché local (0 ms de espera)
  const isFirstLaunchDone = localStorage.getItem('win11-widget-first-launch') === 'true';
  try {
    const cached = JSON.parse(localStorage.getItem('win11-widget-data') || '{}');
    if (!isFirstLaunchDone && cached.content) {
      noteEditor.innerHTML = sanitizeChecklists(cached.content);
    } else {
      noteEditor.innerHTML = '';
    }
    if (cached.title && !isFirstLaunchDone) {
      widgetTitle.innerText = cached.title;
    } else {
      widgetTitle.innerText = getMinimalTimestamp();
    }
    if (cached.theme) setTheme(cached.theme);
    if (cached.fontSize) {
      currentFontSize = parseFloat(cached.fontSize) || 15.0;
      noteEditor.style.fontSize = `${currentFontSize}px`;
    }
  } catch (e) {}

  // Initialize data from main process
  async function loadInitialData() {
    try {
      const data = await window.widgetAPI.getInitialData();
      if (data) {
        if (data.filePath) {
          // Archivo abierto directamente por anticlick / abrir con
          if (data.content !== undefined) {
            noteEditor.innerHTML = sanitizeChecklists(data.content);
          }
          if (data.title) {
            widgetTitle.innerText = data.title;
          }
          widgetTitle.title = `Archivo: ${data.filePath}`;
          hasUnexportedChanges = false;
        } else if (!data.first_launch_done) {
          // Primera apertura: mostrar texto de ejemplo
          if (data.content) {
            noteEditor.innerHTML = sanitizeChecklists(data.content);
          }
          widgetTitle.innerText = data.title || getMinimalTimestamp();
          widgetTitle.title = 'Arrastrar para mover widget';
        } else {
          // En lo sucesivo la app se abre en limpio
          noteEditor.innerHTML = '';
          localStorage.setItem('win11-widget-first-launch', 'true');
          const initTime = getMinimalTimestamp();
          widgetTitle.innerText = initTime;
          widgetTitle.title = 'Arrastrar para mover widget';
        }
        if (data.theme) {
          setTheme(data.theme);
        }
        if (data.opacity) {
          selectOpacity.value = data.opacity;
          applyOpacity(data.opacity);
        }
        if (data.fontSize) {
          currentFontSize = parseFloat(data.fontSize) || 15.0;
          noteEditor.style.fontSize = `${currentFontSize}px`;
        }
        updatePinUI(Boolean(data.alwaysOnTop));
      }
    } catch (err) {
      console.warn('Could not load initial data:', err);
    }
    updateStats();
    updateToolbarStates();
  }

  await loadInitialData();
  window.addEventListener('pywebviewready', loadInitialData);

  // Asegurar que el navegador completó el cálculo y pintado del DOM
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

  // Indicar a Python que desenmascare la ventana (cero tiempo muerto, sin cuadro en blanco)
  if (window.widgetAPI && window.widgetAPI.windowReady) {
    try {
      await window.widgetAPI.windowReady();
    } catch (e) {
      console.warn('Error calling windowReady:', e);
    }
  }

  // Desencadenar la animación de caída elástica en el instante exacto en que la ventana se hace visible
  window.triggerEntranceAnimation();

  // Listen to pin changes from tray menu
  window.widgetAPI.onPinChanged((pinned) => {
    updatePinUI(pinned);
  });

  // ------------------------------------------------------------------------
  // Pin Toggle (Always on Top)
  // ------------------------------------------------------------------------
  function updatePinUI(pinned) {
    isPinned = pinned;
    if (isPinned) {
      btnPin.classList.add('pinned');
      pinBadge.innerText = 'Fijado';
      btnPin.title = 'Widget anclado sobre todas las ventanas (Haz clic para desanclar y dejarlo en el escritorio)';
    } else {
      btnPin.classList.remove('pinned');
      pinBadge.innerText = 'Libre';
      btnPin.title = 'Widget en escritorio (Haz clic para fijarlo siempre al frente)';
    }
  }

  btnPin.addEventListener('click', async () => {
    try {
      const newState = await window.widgetAPI.togglePin(!isPinned);
      updatePinUI(newState);
      showNotification(newState ? '📌 Anclado al frente' : '🪟 Libre en el escritorio');
    } catch (e) {
      console.error(e);
    }
  });

  // ------------------------------------------------------------------------
  // Window Minimize / Close with Cinematic Animation & Unsaved Changes Prompt
  // ------------------------------------------------------------------------
  btnMinimize.addEventListener('click', () => {
    window.widgetAPI.minimizeWindow();
  });

  // Animación de salida cinemática continua (Float & Settle Exit)
  function animateAndClose() {
    if (!widgetContainer) {
      window.widgetAPI.closeWindow();
      return;
    }
    if (widgetContainer.classList.contains('anim-cinematic-exit')) return;
    widgetContainer.classList.remove('anim-cinematic-enter');
    widgetContainer.classList.add('anim-cinematic-exit');
    setTimeout(() => {
      window.widgetAPI.closeWindow();
    }, 290);
  }

  function handleCloseRequest() {
    const hasContent = noteEditor.innerText.trim().length > 0;
    if (hasUnexportedChanges && hasContent) {
      if (modalUnsaved) {
        modalUnsaved.style.display = 'flex';
      } else {
        animateAndClose();
      }
    } else {
      animateAndClose();
    }
  }

  btnClose.addEventListener('click', handleCloseRequest);

  if (btnModalSave) {
    btnModalSave.addEventListener('click', async () => {
      modalUnsaved.style.display = 'none';
      const res = await performExport();
      if (res && res.success && !res.canceled) {
        animateAndClose();
      }
    });
  }

  if (btnModalDiscard) {
    btnModalDiscard.addEventListener('click', () => {
      modalUnsaved.style.display = 'none';
      animateAndClose();
    });
  }

  if (btnModalCancel) {
    btnModalCancel.addEventListener('click', () => {
      modalUnsaved.style.display = 'none';
    });
  }

  // ------------------------------------------------------------------------
  // Compact Mode Toggle (Solo cabecera)
  // ------------------------------------------------------------------------
  btnCompact.addEventListener('click', async () => {
    isCompact = !isCompact;
    if (isCompact) {
      widgetContainer.classList.add('is-compact');
      btnCompact.title = 'Restaurar editor';
      btnCompact.style.color = 'var(--accent-color)';
      await window.widgetAPI.toggleCompactMode(true);
    } else {
      widgetContainer.classList.remove('is-compact');
      btnCompact.title = 'Modo compacto';
      btnCompact.style.color = '';
      await window.widgetAPI.toggleCompactMode(false);
    }
  });



  // ------------------------------------------------------------------------
  // Formatting & List Commands
  // ------------------------------------------------------------------------
  function execFormat(command, value = null) {
    noteEditor.focus();
    document.execCommand(command, false, value);
    updateToolbarStates();
    triggerAutosave();
    updateStats();
  }

  // Lists & Checklists
  function toggleChecklist() {
    noteEditor.focus();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;

    const node = sel.anchorNode;
    const parentLi = node ? (node.nodeType === 1 ? node.closest('li') : node.parentElement?.closest('li')) : null;
    const parentUl = parentLi ? parentLi.closest('ul') : null;

    if (parentUl && parentUl.classList.contains('task-list')) {
      // Toggle off task-list back to normal text
      parentUl.classList.remove('task-list');
      parentUl.querySelectorAll('li').forEach(li => li.removeAttribute('data-checked'));
      document.execCommand('insertUnorderedList', false, null);
    } else if (parentUl) {
      // Convert existing bullet list into task-list
      parentUl.className = 'task-list';
      parentUl.querySelectorAll('li').forEach(li => {
        if (!li.hasAttribute('data-checked')) {
          li.setAttribute('data-checked', 'false');
        }
      });
    } else {
      // Not in list: create unordered list first, then tag it as task-list
      document.execCommand('insertUnorderedList', false, null);
      const newSel = window.getSelection();
      const currNode = newSel?.anchorNode;
      const newLi = currNode ? (currNode.nodeType === 1 ? currNode.closest('li') : currNode.parentElement?.closest('li')) : null;
      const newUl = newLi ? newLi.closest('ul') : null;
      if (newUl) {
        newUl.className = 'task-list';
        newUl.querySelectorAll('li').forEach(li => {
          if (!li.hasAttribute('data-checked')) {
            li.setAttribute('data-checked', 'false');
          }
        });
      }
    }
    triggerAutosave();
    updateStats();
  }

  btnBulletList.addEventListener('click', () => {
    const sel = window.getSelection();
    const li = sel?.anchorNode ? (sel.anchorNode.nodeType === 1 ? sel.anchorNode.closest('li') : sel.anchorNode.parentElement?.closest('li')) : null;
    const ul = li ? li.closest('ul') : null;
    if (ul && ul.classList.contains('task-list')) {
      ul.classList.remove('task-list');
      ul.querySelectorAll('li').forEach(item => item.removeAttribute('data-checked'));
      triggerAutosave();
      return;
    }
    execFormat('insertUnorderedList');
  });

  btnNumberedList.addEventListener('click', () => {
    const sel = window.getSelection();
    const li = sel?.anchorNode ? (sel.anchorNode.nodeType === 1 ? sel.anchorNode.closest('li') : sel.anchorNode.parentElement?.closest('li')) : null;
    const ul = li ? li.closest('ul') : null;
    if (ul && ul.classList.contains('task-list')) {
      ul.classList.remove('task-list');
      ul.querySelectorAll('li').forEach(item => item.removeAttribute('data-checked'));
    }
    execFormat('insertOrderedList');
  });

  btnChecklist.addEventListener('click', toggleChecklist);

  // Delegate clicks on checklist items
  noteEditor.addEventListener('click', (e) => {
    const li = e.target.closest('ul.task-list > li');
    if (li) {
      const rect = li.getBoundingClientRect();
      // Checkbox is drawn with ::before between -24px and -4px relative to li left edge
      if (e.clientX >= rect.left - 28 && e.clientX <= rect.left + 8 && e.clientY >= rect.top && e.clientY <= rect.bottom) {
        e.preventDefault();
        e.stopPropagation();
        const current = li.getAttribute('data-checked') === 'true';
        li.setAttribute('data-checked', current ? 'false' : 'true');
        triggerAutosave();
        return;
      }
    }

    // Legacy fallback for old todo-checkbox
    if (e.target.classList.contains('todo-checkbox')) {
      const parent = e.target.closest('.todo-item');
      if (parent) {
        if (e.target.checked) {
          parent.classList.add('checked');
          e.target.setAttribute('checked', 'checked');
        } else {
          parent.classList.remove('checked');
          e.target.removeAttribute('checked');
        }
        triggerAutosave();
      }
    }
  });

  // Hover feedback: change cursor to pointer when hovering directly over the checkbox
  noteEditor.addEventListener('mousemove', (e) => {
    const li = e.target.closest('ul.task-list > li');
    if (li) {
      const rect = li.getBoundingClientRect();
      if (e.clientX >= rect.left - 28 && e.clientX <= rect.left + 8 && e.clientY >= rect.top && e.clientY <= rect.bottom) {
        noteEditor.style.cursor = 'pointer';
        return;
      }
    }
    noteEditor.style.cursor = 'text';
  });

  // ------------------------------------------------------------------------
  // Heading & Normal Text Alternation Logic
  // ------------------------------------------------------------------------
  function getHeadingParent(node) {
    if (!node || node === noteEditor) return null;
    const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    if (!el || !noteEditor.contains(el)) return null;
    return el.closest('h1, h2, h3, h4, h5, h6');
  }

  function isCurrentSelectionHeading() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return false;
    return Boolean(getHeadingParent(sel.anchorNode));
  }

  // Alternar entre Título (h2) y Texto Normal (p) en un solo botón
  function toggleHeading() {
    noteEditor.focus();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;

    const currentHeading = getHeadingParent(sel.anchorNode);

    if (currentHeading) {
      // Estaba en Título -> Alternar a Texto Normal
      document.execCommand('formatBlock', false, '<p>');

      // Respaldo de compatibilidad por si formatBlock no desenvuelve el bloque en Chromium
      const stillHeading = getHeadingParent(window.getSelection()?.anchorNode);
      if (stillHeading && noteEditor.contains(stillHeading)) {
        const p = document.createElement('p');
        p.innerHTML = stillHeading.innerHTML || '<br>';
        stillHeading.parentNode.replaceChild(p, stillHeading);
        const range = document.createRange();
        range.selectNodeContents(p);
        range.collapse(false);
        sel.removeAllRanges();
        sel.addRange(range);
      }
    } else {
      // Estaba en Texto Normal -> Alternar a Título
      document.execCommand('formatBlock', false, '<h2>');

      // Respaldo de compatibilidad si el editor estaba vacío o el nodo no se agrupó
      const newSel = window.getSelection();
      const afterHeading = getHeadingParent(newSel?.anchorNode);
      if (!afterHeading) {
        let node = sel.anchorNode;
        if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
        if (node && node !== noteEditor && noteEditor.contains(node)) {
          const h2 = document.createElement('h2');
          h2.innerHTML = node.innerHTML || '<br>';
          node.parentNode.replaceChild(h2, node);
          const range = document.createRange();
          range.selectNodeContents(h2);
          range.collapse(false);
          sel.removeAllRanges();
          sel.addRange(range);
        } else if (!noteEditor.innerText.trim()) {
          noteEditor.innerHTML = '<h2><br></h2>';
          const h2 = noteEditor.querySelector('h2');
          const range = document.createRange();
          range.selectNodeContents(h2);
          range.collapse(false);
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
    }

    updateToolbarStates();
    triggerAutosave();
    updateStats();
  }

  // Sincronizar el estado visual de los botones (Activo / Inactivo) con el texto seleccionado
  function updateToolbarStates() {
    const sel = window.getSelection();
    const hasFocus = sel && sel.rangeCount > 0 && noteEditor.contains(sel.anchorNode);

    if (!hasFocus) {
      btnHeading.classList.remove('active');
      btnBold.classList.remove('active');
      btnItalic.classList.remove('active');
      btnUnderline.classList.remove('active');
      btnStrike.classList.remove('active');
      btnBulletList.classList.remove('active');
      btnNumberedList.classList.remove('active');
      btnChecklist.classList.remove('active');
      return;
    }

    // Estado del botón Título / Normal
    const inHeading = isCurrentSelectionHeading();
    btnHeading.classList.toggle('active', inHeading);
    btnHeading.title = inHeading 
      ? 'Título activo (Clic para alternar a Texto Normal)' 
      : 'Texto Normal activo (Clic para alternar a Título)';

    // Estados de estilos de texto inline
    try {
      btnBold.classList.toggle('active', document.queryCommandState('bold'));
      btnItalic.classList.toggle('active', document.queryCommandState('italic'));
      btnUnderline.classList.toggle('active', document.queryCommandState('underline'));
      btnStrike.classList.toggle('active', document.queryCommandState('strikeThrough'));

      // Listas
      const node = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
      const inTaskList = Boolean(node && node.closest('ul.task-list'));
      const inUl = document.queryCommandState('insertUnorderedList');
      const inOl = document.queryCommandState('insertOrderedList');

      btnChecklist.classList.toggle('active', inTaskList);
      btnBulletList.classList.toggle('active', inUl && !inTaskList);
      btnNumberedList.classList.toggle('active', inOl);
    } catch (e) {
      // Ignorado si queryCommandState no está disponible en el contexto
    }
  }

  // Listeners para actualizar los botones de la barra al mover el cursor o cambiar selección
  document.addEventListener('selectionchange', () => {
    const sel = window.getSelection();
    if (sel && sel.anchorNode && noteEditor.contains(sel.anchorNode)) {
      updateToolbarStates();
    }
  });

  noteEditor.addEventListener('keyup', updateToolbarStates);
  noteEditor.addEventListener('mouseup', updateToolbarStates);
  noteEditor.addEventListener('focus', updateToolbarStates);

  // Text Styling
  btnBold.addEventListener('click', () => execFormat('bold'));
  btnItalic.addEventListener('click', () => execFormat('italic'));
  btnUnderline.addEventListener('click', () => execFormat('underline'));
  btnStrike.addEventListener('click', () => execFormat('strikeThrough'));

  // Heading / Normal Text Toggle (Alternancia en un solo botón)
  btnHeading.addEventListener('click', toggleHeading);

  // Font Size
  btnFontSizeUp.addEventListener('click', () => {
    if (currentFontSize < 26) {
      currentFontSize += 1.5;
      noteEditor.style.fontSize = `${currentFontSize}px`;
      triggerAutosave();
    }
  });

  btnFontSizeDown.addEventListener('click', () => {
    if (currentFontSize > 11) {
      currentFontSize -= 1.5;
      noteEditor.style.fontSize = `${currentFontSize}px`;
      triggerAutosave();
    }
  });

  // Export and Save Notes
  async function performExport() {
    try {
      const customTitle = widgetTitle ? widgetTitle.innerText.trim() : '';
      const res = await window.widgetAPI.exportFile({
        title: customTitle,
        content: noteEditor.innerHTML,
        theme: currentTheme,
        fontSize: currentFontSize
      });

      if (res && res.success && !res.canceled) {
        hasUnexportedChanges = false;
        if (res.title && widgetTitle) {
          widgetTitle.innerText = res.title;
        }
        if (res.filePath && widgetTitle) {
          widgetTitle.title = `Guardado: ${res.filePath}`;
        }
        showNotification(`💾 Guardado: ${res.fileName}`);
      }
      return res;
    } catch (err) {
      console.error('Error exporting:', err);
      return null;
    }
  }

  async function performImport() {
    try {
      const res = await window.widgetAPI.importFile();
      if (res && res.success && res.data) {
        if (res.data.content !== undefined) {
          noteEditor.innerHTML = sanitizeChecklists(res.data.content);
        }
        if (res.data.title) {
          widgetTitle.innerText = res.data.title;
        }
        if (res.data.theme) {
          setTheme(res.data.theme);
        }
        if (res.data.fontSize) {
          currentFontSize = parseFloat(res.data.fontSize) || 15.0;
          noteEditor.style.fontSize = `${currentFontSize}px`;
        }
        hasUnexportedChanges = false;
        updateStats();
        triggerAutosave();
        showNotification('📂 Nota abierta con formato');
      }
    } catch (err) {
      console.error('Error importing:', err);
    }
  }

  btnExport.addEventListener('click', performExport);
  btnImport.addEventListener('click', performImport);

  // Clear Content
  btnClear.addEventListener('click', () => {
    if (confirm('¿Deseas vaciar el contenido de la nota?')) {
      noteEditor.innerHTML = '';
      triggerAutosave();
      updateStats();
      noteEditor.focus();
    }
  });

  // ------------------------------------------------------------------------
  // Keyboard Shortcuts in Editor
  // ------------------------------------------------------------------------
  noteEditor.addEventListener('keydown', (e) => {
    // Enter inside task list ensures new item starts unchecked
    if (e.key === 'Enter') {
      const sel = window.getSelection();
      const li = sel?.anchorNode ? (sel.anchorNode.nodeType === 1 ? sel.anchorNode.closest('li') : sel.anchorNode.parentElement?.closest('li')) : null;
      if (li && li.closest('ul.task-list')) {
        setTimeout(() => {
          const newSel = window.getSelection();
          const newLi = newSel?.anchorNode ? (newSel.anchorNode.nodeType === 1 ? newSel.anchorNode.closest('li') : newSel.anchorNode.parentElement?.closest('li')) : null;
          if (newLi && newLi !== li && newLi.closest('ul.task-list')) {
            newLi.setAttribute('data-checked', 'false');
          }
          triggerAutosave();
        }, 10);
      }

      // Al presionar Enter dentro de un título, convertir la nueva línea en párrafo normal
      const node = sel?.anchorNode ? (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement) : null;
      const heading = node ? node.closest('h1, h2, h3, h4, h5, h6') : null;
      if (heading && noteEditor.contains(heading)) {
        setTimeout(() => {
          const newSel = window.getSelection();
          const newNode = newSel?.anchorNode ? (newSel.anchorNode.nodeType === 1 ? newSel.anchorNode : newSel.anchorNode.parentElement) : null;
          const newHeading = newNode ? newNode.closest('h1, h2, h3, h4, h5, h6') : null;
          if (newHeading && newHeading !== heading && (!newHeading.textContent || newHeading.textContent.trim() === '')) {
            document.execCommand('formatBlock', false, '<p>');
            updateToolbarStates();
            triggerAutosave();
          }
        }, 10);
      }
    }

    // Ctrl+H: Alternar entre Título y Texto Normal
    if (e.ctrlKey && !e.shiftKey && (e.key === 'h' || e.key === 'H')) {
      e.preventDefault();
      toggleHeading();
      return;
    }

    // Ctrl+S: Export / Save note
    if (e.ctrlKey && !e.shiftKey && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      performExport();
      return;
    }

    // Ctrl+O: Open / Import note
    if (e.ctrlKey && !e.shiftKey && (e.key === 'o' || e.key === 'O')) {
      e.preventDefault();
      performImport();
      return;
    }

    // Tab / Shift+Tab indenting for lists
    if (e.key === 'Tab') {
      e.preventDefault();
      if (e.shiftKey) {
        document.execCommand('outdent', false, null);
      } else {
        document.execCommand('indent', false, null);
      }
      triggerAutosave();
      return;
    }

    // Ctrl+Shift+8: Bullet list
    if (e.ctrlKey && e.shiftKey && (e.key === '8' || e.key === '*')) {
      e.preventDefault();
      execFormat('insertUnorderedList');
      return;
    }

    // Ctrl+Shift+7: Numbered list
    if (e.ctrlKey && e.shiftKey && (e.key === '7' || e.key === '&')) {
      e.preventDefault();
      execFormat('insertOrderedList');
      return;
    }

    // Ctrl+Shift+9: Checklist
    if (e.ctrlKey && e.shiftKey && (e.key === '9' || e.key === '(')) {
      e.preventDefault();
      btnChecklist.click();
      return;
    }
  });

  // ------------------------------------------------------------------------
  // Themes and Palette
  // ------------------------------------------------------------------------
  function setTheme(themeClass) {
    document.body.className = '';
    document.body.classList.add(themeClass);
    currentTheme = themeClass;
  }

  btnPalette.addEventListener('click', (e) => {
    e.stopPropagation();
    const isVisible = themePopup.style.display === 'block';
    themePopup.style.display = isVisible ? 'none' : 'block';
  });

  document.querySelectorAll('.theme-swatch').forEach((swatch) => {
    swatch.addEventListener('click', () => {
      const theme = swatch.getAttribute('data-theme');
      setTheme(theme);
      themePopup.style.display = 'none';
      triggerAutosave();
    });
  });

  // Close popup if clicked outside
  document.addEventListener('click', (e) => {
    if (!themePopup.contains(e.target) && e.target !== btnPalette) {
      themePopup.style.display = 'none';
    }
  });

  // ------------------------------------------------------------------------
  // Opacity Control
  // ------------------------------------------------------------------------
  function applyOpacity(val) {
    const num = parseFloat(val) || 0.95;
    widgetContainer.style.opacity = num;
  }

  selectOpacity.addEventListener('change', (e) => {
    applyOpacity(e.target.value);
    triggerAutosave();
  });

  // ------------------------------------------------------------------------
  // ------------------------------------------------------------------------
  // ------------------------------------------------------------------------
  // Interactive Border & Corner Resizing (All 8 Edges & Corners - Cursor Locked)
  // ------------------------------------------------------------------------
  let isResizing = false;
  let resizeDirection = 'bottom-right';
  let resizeStartMouseX = 0;
  let resizeStartMouseY = 0;
  let resizeStartRect = null;
  let activeResizeHandle = null;
  let targetResizeGeom = null;
  let isResizeInFlight = false;

  async function syncResizeGeom() {
    if (!isResizing || !targetResizeGeom) return;
    if (isResizeInFlight) return;

    isResizeInFlight = true;
    const geomToSend = { ...targetResizeGeom };

    try {
      await window.widgetAPI.setWindowGeometry(geomToSend);
    } catch (err) {
      console.error(err);
    } finally {
      isResizeInFlight = false;
      if (isResizing && targetResizeGeom && (
        targetResizeGeom.width !== geomToSend.width ||
        targetResizeGeom.height !== geomToSend.height ||
        targetResizeGeom.x !== geomToSend.x ||
        targetResizeGeom.y !== geomToSend.y
      )) {
        requestAnimationFrame(syncResizeGeom);
      }
    }
  }

  async function handleResizeStart(e, direction, handleEl) {
    if (e.button !== 0) return;
    isResizing = true;
    resizeDirection = direction || 'bottom-right';
    resizeStartMouseX = e.screenX;
    resizeStartMouseY = e.screenY;
    activeResizeHandle = handleEl;
    if (handleEl && handleEl.setPointerCapture && e.pointerId !== undefined) {
      try { handleEl.setPointerCapture(e.pointerId); } catch (err) {}
    }

    const rect = await window.widgetAPI.getWindowRect();
    if (rect) {
      resizeStartRect = rect;
    } else {
      resizeStartRect = {
        x: window.screenX || 0,
        y: window.screenY || 0,
        width: window.outerWidth || 380,
        height: window.outerHeight || 280
      };
    }
    targetResizeGeom = { ...resizeStartRect };

    e.preventDefault();
    e.stopPropagation();
  }

  function handleResizeMove(e) {
    if (!isResizing || !resizeStartRect) return;
    const deltaX = e.screenX - resizeStartMouseX;
    const deltaY = e.screenY - resizeStartMouseY;

    const minW = 260;
    const minH = isCompact ? 44 : 140;

    let newX = resizeStartRect.x;
    let newY = resizeStartRect.y;
    let newW = resizeStartRect.width;
    let newH = resizeStartRect.height;

    if (resizeDirection.includes('right')) {
      newW = Math.max(minW, resizeStartRect.width + deltaX);
    } else if (resizeDirection.includes('left')) {
      const candidateW = resizeStartRect.width - deltaX;
      if (candidateW >= minW) {
        newW = candidateW;
        newX = (resizeStartRect.x + resizeStartRect.width) - newW;
      } else {
        newW = minW;
        newX = (resizeStartRect.x + resizeStartRect.width) - minW;
      }
    }

    if (resizeDirection.includes('bottom')) {
      newH = Math.max(minH, resizeStartRect.height + deltaY);
    } else if (resizeDirection.includes('top')) {
      const candidateH = resizeStartRect.height - deltaY;
      if (candidateH >= minH) {
        newH = candidateH;
        newY = (resizeStartRect.y + resizeStartRect.height) - newH;
      } else {
        newH = minH;
        newY = (resizeStartRect.y + resizeStartRect.height) - minH;
      }
    }

    targetResizeGeom = { x: newX, y: newY, width: newW, height: newH };
    syncResizeGeom();
  }

  function handleResizeEnd(e) {
    if (isResizing) {
      isResizing = false;
      if (activeResizeHandle && activeResizeHandle.releasePointerCapture && e && e.pointerId !== undefined) {
        try { activeResizeHandle.releasePointerCapture(e.pointerId); } catch (err) {}
      }
      activeResizeHandle = null;
      document.body.style.cursor = '';
      if (targetResizeGeom) {
        window.widgetAPI.setWindowGeometry(targetResizeGeom);
      }
      window.widgetAPI.saveWindowPosition();
    }
  }

  const resizeHandles = document.querySelectorAll('.resize-handle');
  resizeHandles.forEach((handle) => {
    handle.addEventListener('pointerdown', (e) => {
      handleResizeStart(e, handle.dataset.direction, handle);
    });
    handle.addEventListener('pointermove', handleResizeMove);
    handle.addEventListener('pointerup', handleResizeEnd);
    handle.addEventListener('pointercancel', handleResizeEnd);
  });

  if (resizeGrip) {
    resizeGrip.addEventListener('pointerdown', (e) => {
      handleResizeStart(e, 'bottom-right', resizeGrip);
    });
    resizeGrip.addEventListener('pointermove', handleResizeMove);
    resizeGrip.addEventListener('pointerup', handleResizeEnd);
    resizeGrip.addEventListener('pointercancel', handleResizeEnd);
  }

  window.addEventListener('pointermove', handleResizeMove);
  window.addEventListener('pointerup', handleResizeEnd);

  // ------------------------------------------------------------------------
  // Interactive Window Repositioning (Header Drag - Absolute Cursor Lock)
  // ------------------------------------------------------------------------
  let isMovingWindow = false;
  let moveStartMouseX = 0;
  let moveStartMouseY = 0;
  let moveStartWinX = 0;
  let moveStartWinY = 0;
  let targetWinX = 0;
  let targetWinY = 0;
  let isMoveInFlight = false;

  async function syncMovePosition() {
    if (!isMovingWindow) return;
    if (isMoveInFlight) return;

    isMoveInFlight = true;
    const sendX = targetWinX;
    const sendY = targetWinY;

    try {
      await window.widgetAPI.setWindowPosition({ x: sendX, y: sendY });
    } catch (err) {
      console.error(err);
    } finally {
      isMoveInFlight = false;
      if (isMovingWindow && (targetWinX !== sendX || targetWinY !== sendY)) {
        requestAnimationFrame(syncMovePosition);
      }
    }
  }

  widgetHeader.addEventListener('pointerdown', async (e) => {
    // Solo clic primario izquierdo
    if (e.button !== 0) return;

    // Ignorar clics sobre botones, inputs, iconos interactivos o título en edición
    if (e.target.closest('button, input, select, textarea, .win-btn, .color-swatch, .save-status, #widgetTitle[contenteditable="true"]')) {
      return;
    }

    if (widgetHeader.setPointerCapture && e.pointerId !== undefined) {
      try { widgetHeader.setPointerCapture(e.pointerId); } catch (err) {}
    }

    moveStartMouseX = e.screenX;
    moveStartMouseY = e.screenY;

    const rect = await window.widgetAPI.getWindowRect();
    if (rect) {
      moveStartWinX = rect.x;
      moveStartWinY = rect.y;
    } else {
      moveStartWinX = window.screenX || 0;
      moveStartWinY = window.screenY || 0;
    }

    targetWinX = moveStartWinX;
    targetWinY = moveStartWinY;
    isMovingWindow = true;
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  window.addEventListener('pointermove', (e) => {
    if (!isMovingWindow) return;
    const deltaX = e.screenX - moveStartMouseX;
    const deltaY = e.screenY - moveStartMouseY;

    targetWinX = moveStartWinX + deltaX;
    targetWinY = moveStartWinY + deltaY;

    syncMovePosition();
  });

  const stopMovingWindow = (e) => {
    if (isMovingWindow) {
      isMovingWindow = false;
      if (widgetHeader.releasePointerCapture && e && e.pointerId !== undefined) {
        try { widgetHeader.releasePointerCapture(e.pointerId); } catch (err) {}
      }
      document.body.style.userSelect = '';
      window.widgetAPI.setWindowPosition({ x: targetWinX, y: targetWinY });
      window.widgetAPI.saveWindowPosition();
    }
  };

  window.addEventListener('pointerup', stopMovingWindow);
  window.addEventListener('pointercancel', stopMovingWindow);

  // ------------------------------------------------------------------------
  // Autosave, Image Paste, and Word Counter
  // ------------------------------------------------------------------------
  noteEditor.addEventListener('input', () => {
    hasUnexportedChanges = true;
    updateStats();
    triggerAutosave();
  });

  widgetTitle.addEventListener('input', () => {
    hasUnexportedChanges = true;
  });

  function insertAdaptiveImage(dataUrl) {
    const imgHtml = `<p><img src="${dataUrl}" alt="Captura de pantalla" style="max-width: 100%; height: auto; border-radius: 8px; display: block; margin: 10px auto;" /></p><p><br></p>`;
    document.execCommand('insertHTML', false, imgHtml);
    hasUnexportedChanges = true;
    triggerAutosave();
    updateStats();
    showNotification('🖼️ Captura pegada y adaptada al editor');
  }

  // Soporte directo para pegar capturas de pantalla, imágenes y GIFs animados (Ctrl+V)
  noteEditor.addEventListener('paste', (e) => {
    const clipboardData = e.clipboardData || window.clipboardData;
    const items = clipboardData?.items;
    if (items) {
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          const file = items[i].getAsFile();
          if (file) {
            e.preventDefault();
            const reader = new FileReader();
            reader.onload = (event) => {
              insertAdaptiveImage(event.target.result);
            };
            reader.readAsDataURL(file);
            return;
          }
        }
      }
    }
  });

  // Soporte para arrastrar y soltar imágenes directamente al editor
  noteEditor.addEventListener('dragover', (e) => {
    if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    }
  });

  noteEditor.addEventListener('drop', (e) => {
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      for (let i = 0; i < files.length; i++) {
        if (files[i].type.startsWith('image/')) {
          e.preventDefault();
          const reader = new FileReader();
          reader.onload = (event) => {
            insertAdaptiveImage(event.target.result);
          };
          reader.readAsDataURL(files[i]);
          return;
        }
      }
    }
  });

  function updateStats() {
    const text = noteEditor.innerText.trim();
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    if (statWords) {
      statWords.innerText = `${words} ${words === 1 ? 'palabra' : 'palabras'}`;
    }
  }

  function triggerAutosave() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(async () => {
      try {
        const timestampTitle = getMinimalTimestamp();
        widgetTitle.innerText = timestampTitle;
        widgetTitle.title = `Último guardado: ${timestampTitle}`;

        await window.widgetAPI.saveData({
          content: noteEditor.innerHTML,
          title: timestampTitle,
          theme: currentTheme,
          opacity: selectOpacity.value,
          fontSize: currentFontSize
        });
      } catch (err) {
        console.error('Error saving data:', err);
      }
    }, 350);
  }

  // Floating Toast Notification
  let toastTimer = null;
  function showNotification(msg) {
    if (!floatingToast) return;
    floatingToast.innerText = msg;
    floatingToast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      floatingToast.classList.remove('show');
    }, 2200);
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
