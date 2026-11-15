// Carburanti Economici Italia — Lovelace Card v6.3

const ITALIAN_FLAG_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3 2" width="20" height="14" style="border-radius:2px;vertical-align:middle;margin:0 4px;flex-shrink:0">
  <rect width="1" height="2" fill="#009246"/>
  <rect x="1" width="1" height="2" fill="#fff"/>
  <rect x="2" width="1" height="2" fill="#CE2B37"/>
</svg>`;

const FUEL_LABELS = { benzina: "Benzina", diesel: "Diesel", gpl: "GPL" };

function slugFromPriceEntity(entityId) {
  const m = entityId.match(/^sensor\.distributore_(\d+)deg_(benzina|diesel|gpl)_(.+)_prezzo$/);
  if (!m) return null;
  return { rank: parseInt(m[1]), fuel: m[2], zone: m[3] };
}

function friendlyZoneName(hass, zoneSlug) {
  const state = hass.states[`zone.${zoneSlug}`];
  if (state) return state.attributes.friendly_name || zoneSlug;
  // lo slug è l'object_id esatto della zona/tracker scelto in configurazione
  const tr = hass.states[`device_tracker.${zoneSlug}`];
  if (tr) return tr.attributes.friendly_name || zoneSlug;
  return zoneSlug.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function formatDateTime(iso) {
  if (!iso || iso === "unavailable" || iso === "unknown") return null;
  try {
    return new Date(iso).toLocaleString("it-IT", {
      day:"2-digit", month:"2-digit", year:"numeric",
      hour:"2-digit", minute:"2-digit"
    });
  } catch { return null; }
}

class CarburantiEconomiciCard extends HTMLElement {

  static getConfigElement() {
    return document.createElement("carburanti-economici-card-editor");
  }
  static getStubConfig() { return { entities: [] }; }

  setConfig(config) {
    if (!Array.isArray(config.entities)) throw new Error("entities must be an array");
    this.config = config;
    this._rendered = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) {
      this._render();
    } else {
      this._refreshView(hass);
    }
  }

  // Aggiorna lista, intestazione, footer e (se serve) rimonta la mappa
  _refreshView(hass) {
    const stations = this._buildStations(hass);
    this._updateList();
    this._updateFooter();
    this._updateHeader(stations);

    // Firma della mappa: entita' + coordinate. Se cambia, la mappa va rimontata
    const mapSig = JSON.stringify(
      stations.filter(s => s.lat && s.lng).map(s => [s.entityId, s.lat, s.lng])
    );
    if (mapSig !== this._mapSig) {
      this._remountMap(stations);
    } else {
      const mapCard = this.querySelector("#ce-map-col")?.firstElementChild;
      if (mapCard && mapCard.hass !== undefined) mapCard.hass = hass;
    }
  }

  _updateHeader(stations) {
    const titleEl = this.querySelector(".ce-title");
    const chipEl = this.querySelector(".ce-fuel-chip");
    if (!titleEl || !chipEl || !stations.length) return;
    const zoneName = friendlyZoneName(this._hass, stations[0].zone);
    titleEl.textContent = `Carburanti Economici — ${zoneName}`;
    chipEl.textContent = FUEL_LABELS[stations[0].fuel] || stations[0].fuel;
  }

  _remountMap(stations) {
    const col = this.querySelector("#ce-map-col");
    if (!col) return;
    const withCoords = stations.filter(s => s.lat && s.lng);
    this._mapSig = JSON.stringify(withCoords.map(s => [s.entityId, s.lat, s.lng]));
    col._mapMounted = false;
    col.innerHTML = "";
    if (withCoords.length) {
      this._mountMap(stations, stations[0]?.zone || "");
    } else {
      col.innerHTML = `<div class="ce-no-map">📍 Coordinate non disponibili</div>`;
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
        lastApiCall: meta.rank === 1 ? priceState.attributes?.last_api_call : null,
        lat: addrState?.attributes?.latitude,
        lng: addrState?.attributes?.longitude,
        entityId: `${base}_indirizzo`,
      });
    }
    return stations.sort((a, b) => a.rank - b.rank);
  }

  _getLastApiCall() {
    return this._buildStations().find(s => s.rank === 1)?.lastApiCall || null;
  }

  _stationRowHTML(s) {
    const isUnavailable = !s.price || s.price === "unavailable" || s.price === "unknown";
    const priceText = isUnavailable ? "—" : `${s.price} €/L`;
    const brandText = (!s.brand || s.brand === "unavailable") ? "—" : s.brand;
    const addrText = (!s.address || s.address === "unavailable") ? "—" : s.address;
    return `
      <div class="ce-row">
        <div class="ce-icon"><ha-icon icon="mdi:numeric-${s.rank}-circle"></ha-icon></div>
        <div class="ce-content">
          <div class="ce-primary">
            <span class="ce-brand">${brandText}</span>
            <span class="ce-price ${isUnavailable ? "ce-unavail" : ""}">${priceText}</span>
          </div>
          <div class="ce-secondary">${addrText}</div>
        </div>
      </div>`;
  }

  _updateList() {
    const el = this.querySelector(".ce-list");
    if (!el) return;
    const stations = this._buildStations();
    el.innerHTML = stations.length
      ? stations.map(s => this._stationRowHTML(s)).join("")
      : `<div class="ce-empty">Nessun dato disponibile</div>`;
  }

  _updateFooter() {
    const el = this.querySelector(".ce-footer-text");
    if (!el) return;
    const ts = this._getLastApiCall();
    el.textContent = ts ? `Aggiornato: ${formatDateTime(ts)}` : "";
  }

  async _handleRefresh() {
    const btn = this.querySelector("#ce-refresh-btn");
    if (btn) btn.classList.add("ce-spinning");
    // pulsante dell'istanza mostrata (entity_id prevedibile), con ripiego sul primo trovato
    const zoneSlug = this._buildStations?.()[0]?.zone;
    let buttonEntity = zoneSlug && this._hass.states[`button.aggiorna_carburanti_${zoneSlug}`]
      ? `button.aggiorna_carburanti_${zoneSlug}` : null;
    if (!buttonEntity) {
      buttonEntity = Object.keys(this._hass.states).find(eid => {
        if (!eid.startsWith("button.")) return false;
        const name = (this._hass.states[eid].attributes?.friendly_name || "").toLowerCase();
        return name.includes("aggiorna") && name.includes("carburant");
      });
    }
    if (buttonEntity) {
      try {
        await this._hass.callService("button", "press", { entity_id: buttonEntity });
      } catch (e) {
        console.error("Carburanti Economici: refresh failed", e);
      }
    }
    setTimeout(() => { if (btn) btn.classList.remove("ce-spinning"); }, 1500);
  }

  _render() {
    if (!this._hass || !this.config) return;
    this._rendered = true;

    const stations = this._buildStations();
    const fuel = stations[0]?.fuel || "benzina";
    const fuelLabel = FUEL_LABELS[fuel] || fuel;
    const zoneName = stations[0] ? friendlyZoneName(this._hass, stations[0].zone) : "—";
    const hasCoords = stations.some(s => s.lat && s.lng);
    const zoneSlug = stations[0]?.zone || "";
    const lastApiCall = this._getLastApiCall();
    const lastUpdate = lastApiCall ? formatDateTime(lastApiCall) : null;
    const stationRows = stations.length
      ? stations.map(s => this._stationRowHTML(s)).join("")
      : `<div class="ce-empty">Nessun dato disponibile</div>`;

    this.innerHTML = `
      <ha-card>
        <style>
          ha-card { overflow:hidden; font-family:var(--primary-font-family,sans-serif); border-radius:var(--ha-card-border-radius,12px); }
          .ce-header { display:flex; align-items:center; gap:8px; padding:14px 16px 10px; }
          .ce-title { font-size:14px; font-weight:500; color:var(--primary-text-color); flex:1; }
          .ce-fuel-chip { font-size:11px; font-weight:600; color:var(--secondary-text-color); background:var(--secondary-background-color); border-radius:99px; padding:2px 10px; letter-spacing:0.5px; }
          .ce-divider { height:1px; background:var(--divider-color); margin:0 16px; }
          .ce-body { display:grid; grid-template-columns:1fr 1fr; }
          @media (max-width:500px) {
            .ce-body { grid-template-columns:1fr; }
            .ce-map-col { border-top:1px solid var(--divider-color); }
          }
          .ce-list { padding:8px; display:flex; flex-direction:column; gap:4px; overflow-y:auto; max-height:320px; }
          .ce-row { display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:10px; background:var(--secondary-background-color); }
          .ce-icon { display:flex; align-items:center; justify-content:center; flex-shrink:0; }
          .ce-icon ha-icon { --mdi-icon-size:28px; }
          .ce-content { flex:1; min-width:0; }
          .ce-primary { display:flex; align-items:baseline; justify-content:space-between; gap:6px; }
          .ce-brand { font-size:13px; font-weight:500; color:var(--primary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .ce-price { font-size:14px; font-weight:700; color:var(--primary-text-color); white-space:nowrap; flex-shrink:0; }
          .ce-unavail { color:var(--secondary-text-color); font-weight:400; }
          .ce-secondary { font-size:11px; color:var(--secondary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; }
          .ce-empty { padding:20px; text-align:center; color:var(--secondary-text-color); font-size:13px; }
          .ce-map-col { overflow:hidden; }
          .ce-no-map { height:320px; display:flex; align-items:center; justify-content:center; color:var(--secondary-text-color); font-size:12px; background:var(--secondary-background-color); }
          .ce-footer { padding:6px 16px 10px; font-size:11px; color:var(--secondary-text-color); display:flex; align-items:center; gap:4px; }
          .ce-footer > ha-icon { --mdi-icon-size:14px; }
          .ce-footer-spacer { flex:1; }
          .ce-refresh-btn { background:none; border:none; cursor:pointer; color:var(--secondary-text-color); display:flex; align-items:center; justify-content:center; padding:4px; border-radius:50%; transition:background 0.2s, color 0.2s; }
          .ce-refresh-btn:hover { background:var(--secondary-background-color); color:var(--primary-color); }
          .ce-refresh-btn ha-icon { --mdi-icon-size:16px; }
          @keyframes ce-spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
          .ce-refresh-btn.ce-spinning ha-icon { animation:ce-spin 1s linear infinite; }
        </style>

        <div class="ce-header">
          ${ITALIAN_FLAG_SVG}
          <span class="ce-title">Carburanti Economici — ${zoneName}</span>
          <span class="ce-fuel-chip">${fuelLabel}</span>
        </div>
        <div class="ce-divider"></div>
        <div class="ce-body">
          <div class="ce-list">${stationRows}</div>
          <div class="ce-map-col" id="ce-map-col">
            ${!hasCoords ? `<div class="ce-no-map">📍 Coordinate non disponibili</div>` : ""}
          </div>
        </div>
        <div class="ce-divider"></div>
        <div class="ce-footer">
          <ha-icon icon="mdi:update"></ha-icon>
          <span class="ce-footer-text">${lastUpdate ? `Aggiornato: ${lastUpdate}` : ""}</span>
          <span class="ce-footer-spacer"></span>
          <button class="ce-refresh-btn" id="ce-refresh-btn" title="Aggiorna dati">
            <ha-icon icon="mdi:refresh"></ha-icon>
          </button>
        </div>
      </ha-card>`;

    this.querySelector("#ce-refresh-btn")?.addEventListener("click", () => this._handleRefresh());

    this._mapSig = JSON.stringify(
      stations.filter(s => s.lat && s.lng).map(s => [s.entityId, s.lat, s.lng])
    );
    if (hasCoords) {
      requestAnimationFrame(() => this._mountMap(stations, zoneSlug));
    }
  }

  async _mountMap(stations, zoneSlug) {
    const col = this.querySelector("#ce-map-col");
    if (!col || col._mapMounted) return;
    col._mapMounted = true;

    const entities = [];
    if (this._hass.states[`zone.${zoneSlug}`]) {
      entities.push({ entity: `zone.${zoneSlug}` });
    }
    if (this._hass.states[`device_tracker.${zoneSlug}`]) {
      entities.push({ entity: `device_tracker.${zoneSlug}` });
    }
    stations.filter(s => s.lat && s.lng).forEach(s => {
      entities.push({ entity: s.entityId });
    });

    try {
      const helpers = await window.loadCardHelpers();
      const card = await helpers.createCardElement({
        type: "map",
        entities,
        default_zoom: 13,
        hours_to_show: 0,
      });
      card.hass = this._hass;
      card.style.cssText = "height:320px;display:block;--ha-card-border-radius:0;--ha-card-box-shadow:none;";
      col.appendChild(card);
    } catch (e) {
      console.error("Carburanti Economici: map failed", e);
      col._mapMounted = false;
      col.innerHTML = `<div class="ce-no-map">📍 Mappa non disponibile</div>`;
    }
  }
}

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
      .filter(e => /^sensor\.distributore_\d+deg_(benzina|diesel|gpl)_.+_prezzo$/.test(e))
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
        .es{flex:1;padding:6px 8px;border-radius:8px;font-size:12px;background:var(--secondary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color)}
        .eb{background:none;border:none;cursor:pointer;color:var(--error-color,#f44336);font-size:14px;padding:4px 6px}
        .ea{align-self:flex-start;padding:6px 16px;border-radius:8px;background:var(--primary-color);color:#fff;border:none;cursor:pointer;font-size:13px}
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
if (!window.customCards.find(c => c.type === "carburanti-economici-card")) {
  window.customCards.push({
    type: "carburanti-economici-card",
    name: "Carburanti Economici Italia",
    description: "Mappa + lista distributori più economici",
    preview: false,
  });
}
