// Carburanti Economici Italia — Lovelace Card v5.1

const ITALIAN_FLAG_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3 2" width="24" height="16" style="border-radius:2px;vertical-align:middle;margin:0 4px">
  <rect width="1" height="2" fill="#009246"/>
  <rect x="1" width="1" height="2" fill="#fff"/>
  <rect x="2" width="1" height="2" fill="#CE2B37"/>
</svg>`;

const FUEL_COLORS = { benzina: "#FF6B00", diesel: "#0066CC", gpl: "#00AA55" };
const FUEL_LABELS = { benzina: "Benzina", diesel: "Diesel", gpl: "GPL" };
const ORDINALS = ["1°","2°","3°","4°","5°"];

function slugFromPriceEntity(entityId) {
  // Match known fuel types explicitly to avoid greedy capture issues
  const m = entityId.match(/^sensor\.distributore_(\d+)deg_(benzina|diesel|gpl)_(.+)_prezzo$/);
  if (!m) return null;
  return { rank: parseInt(m[1]), fuel: m[2], zone: m[3] };
}

function friendlyZoneName(hass, zoneSlug) {
  const state = hass.states[`zone.${zoneSlug}`];
  if (state) return state.attributes.friendly_name || zoneSlug;
  for (const [eid, s] of Object.entries(hass.states)) {
    if (eid.startsWith("device_tracker.") && eid.includes(zoneSlug))
      return s.attributes.friendly_name || zoneSlug;
  }
  return zoneSlug.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function formatDate(iso) {
  if (!iso || iso === "unavailable" || iso === "unknown") return "—";
  try { return new Date(iso).toLocaleDateString("it-IT", {day:"2-digit",month:"2-digit",year:"numeric"}); }
  catch { return "—"; }
}

class CarburantiEconomiciCard extends HTMLElement {

  static getConfigElement() {
    return document.createElement("carburanti-economici-card-editor");
  }
  static getStubConfig() { return { entities: [] }; }

  setConfig(config) {
    if (!Array.isArray(config.entities)) throw new Error("entities must be an array");
    this.config = config;
    this._rendered = false; // force full re-render on config change
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) {
      this._render();
    } else {
      // Only update list and map hass — avoid recreating ha-map (would reset zoom)
      this._updateList();
      const haMap = this.querySelector("ha-map");
      if (haMap) haMap.hass = this._buildPatchedHass(hass);
    }
  }

  _buildStations(hass) {
    const h = hass || this._hass;
    if (!h) return [];
    const stations = [];
    for (const entityId of (this.config.entities || [])) {
      const meta = slugFromPriceEntity(entityId);
      if (!meta) continue;
      const priceState = h.states[entityId];
      if (!priceState) continue;
      const base = entityId.replace(/_prezzo$/, "");
      const get = s => h.states[`${base}_${s}`];
      const addrState = get("indirizzo");
      stations.push({
        rank: meta.rank,
        fuel: meta.fuel,
        zone: meta.zone,
        price: priceState.state,
        address: addrState?.state || "—",
        brand: get("marchio")?.state || "—",
        updated: get("aggiornamento")?.state,
        lat: addrState?.attributes?.latitude,
        lng: addrState?.attributes?.longitude,
      });
    }
    return stations.sort((a, b) => a.rank - b.rank);
  }

  _buildPatchedHass(hass) {
    const stations = this._buildStations(hass);
    const extra = {};
    stations.filter(s => s.lat && s.lng).forEach(s => {
      extra[`device_tracker.ce_station_${s.rank}`] = {
        entity_id: `device_tracker.ce_station_${s.rank}`,
        state: "home",
        attributes: {
          latitude: s.lat,
          longitude: s.lng,
          friendly_name: String(s.rank),
          icon: `mdi:numeric-${s.rank}-circle`,
        },
      };
    });
    return { ...hass, states: { ...hass.states, ...extra } };
  }

  _stationRowsHTML(stations, accent) {
    if (!stations.length) return `<div class="ce-empty">Nessun dato disponibile</div>`;
    return stations.map(s => `
      <div class="ce-station">
        <div class="ce-rank" style="background:${FUEL_COLORS[s.fuel]||accent}">${s.rank}</div>
        <div class="ce-info">
          <div class="ce-primary">
            <span class="ce-brand">${s.brand}</span>
            <span class="ce-price" style="color:${FUEL_COLORS[s.fuel]||accent}">${s.price} €/L</span>
          </div>
          <div class="ce-address">${s.address}</div>
        </div>
      </div>`).join("");
  }

  _updateList() {
    const listEl = this.querySelector(".ce-list");
    if (!listEl || !this._hass) return;
    const stations = this._buildStations();
    const fuel = stations[0]?.fuel || "benzina";
    const accent = FUEL_COLORS[fuel] || "#FF6B00";
    listEl.innerHTML = this._stationRowsHTML(stations, accent);
  }

  _render() {
    if (!this._hass || !this.config) return;
    this._rendered = true;

    const stations = this._buildStations();
    const fuel = stations[0]?.fuel || "benzina";
    const accent = FUEL_COLORS[fuel] || "#FF6B00";
    const fuelLabel = FUEL_LABELS[fuel] || fuel;
    const zoneName = stations[0] ? friendlyZoneName(this._hass, stations[0].zone) : "—";
    const hasCoords = stations.some(s => s.lat && s.lng);
    const lastUpdate = stations[0]?.updated ? `Aggiornato: ${formatDate(stations[0].updated)}` : "";
    const zoneSlug = stations[0]?.zone || "";

    this.innerHTML = `
      <ha-card>
        <style>
          ha-card { overflow: hidden; font-family: var(--primary-font-family, sans-serif); }
          .ce-header { display:flex; align-items:center; gap:6px; padding:12px 14px 8px; border-bottom:2px solid ${accent}; font-size:15px; font-weight:700; color:var(--primary-text-color); }
          .ce-header-fuel { margin-left:auto; font-size:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:${accent}; }
          .ce-body { display:grid; grid-template-columns:1fr 1fr; }
          .ce-list { display:flex; flex-direction:column; padding:8px; gap:5px; border-right:2px solid ${accent}; overflow-y:auto; max-height:320px; }
          .ce-station { display:flex; align-items:center; gap:8px; background:var(--secondary-background-color); border-radius:8px; padding:6px 8px; flex-shrink:0; }
          .ce-rank { min-width:22px; height:22px; border-radius:50%; color:#fff; font-weight:700; font-size:11px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
          .ce-info { flex:1; min-width:0; }
          .ce-primary { display:flex; align-items:baseline; justify-content:space-between; gap:6px; }
          .ce-brand { font-size:12px; font-weight:600; color:var(--primary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .ce-price { font-size:14px; font-weight:700; white-space:nowrap; flex-shrink:0; }
          .ce-address { font-size:10px; color:var(--secondary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; }
          .ce-empty { padding:20px; text-align:center; color:var(--secondary-text-color); font-size:13px; }
          .ce-map-col { overflow:hidden; }
          ha-map { height:320px; width:100%; display:block; }
          .ce-no-map { height:320px; display:flex; align-items:center; justify-content:center; color:var(--secondary-text-color); font-size:12px; background:var(--secondary-background-color); }
          .ce-footer { padding:6px 14px; font-size:10px; color:var(--secondary-text-color); border-top:1px solid var(--divider-color); display:flex; align-items:center; gap:4px; }
        </style>
        <div class="ce-header">
          ${ITALIAN_FLAG_SVG}
          Carburanti Economici — ${zoneName}
          <span class="ce-header-fuel">${fuelLabel}</span>
        </div>
        <div class="ce-body">
          <div class="ce-list">${this._stationRowsHTML(stations, accent)}</div>
          <div class="ce-map-col" id="ce-map-col"></div>
        </div>
        ${lastUpdate ? `<div class="ce-footer"><ha-icon icon="mdi:update" style="--mdi-icon-size:14px"></ha-icon>${lastUpdate}</div>` : ""}
      </ha-card>`;

    const col = this.querySelector("#ce-map-col");
    if (!col) return;

    if (!hasCoords) {
      col.innerHTML = `<div class="ce-no-map">📍 Coordinate non disponibili</div>`;
      return;
    }

    // Build patched hass with fake device_trackers for station pins
    const patchedHass = this._buildPatchedHass(this._hass);

    // Build entity list for ha-map
    const entities = [];

    // Add zone if exists
    if (patchedHass.states[`zone.${zoneSlug}`]) {
      entities.push({ entity_id: `zone.${zoneSlug}` });
    }

    // Add real device_tracker for source entity if it's a tracker
    const sourceSlug = zoneSlug;
    const trackerKey = Object.keys(patchedHass.states).find(
      k => k.startsWith("device_tracker.") &&
           !k.startsWith("device_tracker.ce_station_") &&
           k.includes(sourceSlug)
    );
    if (trackerKey) {
      entities.push({ entity_id: trackerKey });
    }

    // Add station fake trackers
    stations.filter(s => s.lat && s.lng).forEach(s => {
      entities.push({ entity_id: `device_tracker.ce_station_${s.rank}` });
    });

    const haMap = document.createElement("ha-map");
    haMap.hass = patchedHass;
    haMap.entities = entities;
    haMap.zoom = 13;
    col.appendChild(haMap);
  }
}

// ── Editor ────────────────────────────────────────────────────────────────────

class CarburantiEconomiciCardEditor extends HTMLElement {

  connectedCallback() { if (!this.innerHTML) this._render(); }

  setConfig(config) {
    this._config = JSON.parse(JSON.stringify({entities:[], ...config}));
    this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }

  _priceEntities() {
    if (!this._hass?.states) return [];
    return Object.keys(this._hass.states)
      .filter(e => /^sensor\.distributore_\d+deg_\w+_.+_prezzo$/.test(e))
      .sort();
  }

  _render() {
    if (!this._config) return;
    const entities = this._config.entities || [];
    const available = this._priceEntities();

    const rows = entities.map((eid, idx) => `
      <div class="er">
        <select data-idx="${idx}" class="es">
          <option value="">— seleziona sensore prezzo —</option>
          ${available.map(e => `<option value="${e}" ${e===eid?"selected":""}>${e}</option>`).join("")}
        </select>
        <button class="eb" data-idx="${idx}" type="button">✕</button>
      </div>`).join("");

    this.innerHTML = `
      <style>
        .ew{padding:12px;display:flex;flex-direction:column;gap:10px}
        .el{font-size:13px;font-weight:600;color:var(--primary-text-color)}
        .eh{font-size:11px;color:var(--secondary-text-color);margin-top:-6px}
        .er{display:flex;gap:8px;align-items:center}
        .es{flex:1;padding:6px 8px;border-radius:6px;font-size:12px;background:var(--secondary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color)}
        .eb{background:none;border:none;cursor:pointer;color:var(--error-color,#f44336);font-size:14px;padding:4px 6px}
        .ea{align-self:flex-start;padding:6px 14px;border-radius:6px;background:var(--primary-color);color:#fff;border:none;cursor:pointer;font-size:13px}
        .en{font-size:12px;color:var(--secondary-text-color);font-style:italic}
      </style>
      <div class="ew">
        <div class="el">Sensori prezzo da mostrare</div>
        <div class="eh">Seleziona i sensori <b>_prezzo</b> — nome, indirizzo e marchio vengono caricati automaticamente.</div>
        <div id="el">${rows || '<div class="en">Nessun distributore aggiunto</div>'}</div>
        <button class="ea" id="ea" type="button">+ Aggiungi distributore</button>
      </div>`;

    this.querySelector("#ea").addEventListener("click", () => {
      this._config = {...this._config, entities:[...(this._config.entities||[]), ""]};
      this._render(); this._fire();
    });
    this.querySelectorAll(".es").forEach(sel => {
      sel.addEventListener("change", e => {
        const idx = parseInt(e.target.dataset.idx);
        const ne = [...(this._config.entities||[])];
        ne[idx] = e.target.value;
        this._config = {...this._config, entities:ne};
        this._fire();
      });
    });
    this.querySelectorAll(".eb").forEach(btn => {
      btn.addEventListener("click", e => {
        const idx = parseInt(e.target.dataset.idx);
        const ne = [...(this._config.entities||[])];
        ne.splice(idx,1);
        this._config = {...this._config, entities:ne};
        this._render(); this._fire();
      });
    });
  }

  _fire() {
    this.dispatchEvent(new CustomEvent("config-changed",
      {detail:{config:this._config}, bubbles:true, composed:true}));
  }
}

if (!customElements.get("carburanti-economici-card")) {
  customElements.define("carburanti-economici-card", CarburantiEconomiciCard);
}
if (!customElements.get("carburanti-economici-card-editor")) {
  customElements.define("carburanti-economici-card-editor", CarburantiEconomiciCardEditor);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "carburanti-economici-card",
  name: "Carburanti Economici Italia",
  description: "Mappa + lista distributori più economici",
  preview: false,
});
