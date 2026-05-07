import json
import pandas as pd
from jinja2 import Template

def create_html_report(df, total_qty, units, pollutant, location_name, year_range, lang="EN"):
    """
    Generates a bilingual standalone HTML report with unit normalization 
    and automatic scaling (kg if < 1 tonne).
    """
    # 1. NORMALIZE DATA (Handles mixed kg, g, and tonnes)
    df = df.copy()
    def to_tonnes(row):
        u = str(row.get('Units', 'tonnes')).lower().strip()
        q = float(row.get('Quantity', 0))
        if 'kg' in u: return q / 1000
        if 'gram' in u or u == 'g': return q / 1000000
        return q
    
    df['Qty_T'] = df.apply(to_tonnes, axis=1)
    grand_total_tonnes = df['Qty_T'].sum()

    # 2. DYNAMIC UNIT SWITCHING (If < 1 Tonne, use KG)
    if grand_total_tonnes < 1.0:
        display_unit = "kg"
        multiplier = 1000
    else:
        display_unit = "tonnes" if lang == "EN" else "tonnes métriques"
        multiplier = 1
        
    display_total = f"{grand_total_tonnes * multiplier:,.2f}"
    df['Display_Qty'] = df['Qty_T'] * multiplier

    # 3. PREPARE TREND DATA
    trend = df.groupby("Year")["Display_Qty"].sum().sort_index()
    trend_labels = [str(int(y)) for y in trend.index.tolist()]
    trend_values = [float(v) for v in trend.values.tolist()]

    # 4. PREPARE FACILITY RANKINGS
    top_facs_df = df.groupby(["Facility", "Display_Company"])["Display_Qty"].sum().nlargest(10).reset_index()
    top_facs = []
    for _, row in top_facs_df.iterrows():
        display_name = f"{row['Facility']} - {row['Display_Company']}"
        top_facs.append({
            "DisplayName": display_name.replace("'", "\\'"),
            "Quantity": float(row['Display_Qty'])
        })

    # 5. PREPARE MAP DATA
    geo = df.dropna(subset=["Lat", "Lon"]).copy()
    map_points = []
    bounds = []
    if not geo.empty:
        max_q = geo["Display_Qty"].max()
        for _, r in geo.iterrows():
            lat, lon = float(r["Lat"]), float(r["Lon"])
            size = (float(r["Display_Qty"]) / max_q * 18) if max_q > 0 else 6
            full_name = f"{r['Facility']} - {r['Display_Company']}"
            map_points.append({
                "Lat": lat, "Lon": lon, "Size": max(4, size),
                "Facility": full_name.replace("'", "\\'")
            })
            bounds.append([lat, lon])

    # 6. DEFINE BILINGUAL LABELS
    labels = {
        "title": "Environmental Dashboard" if lang == "EN" else "Tableau de Bord Environnemental",
        "sync": "Synchronizing Node" if lang == "EN" else "Synchronisation du Nœud",
        "agent": "Agent" if lang == "EN" else "Substance",
        "volume": "Volume" if lang == "EN" else "Volume",
        "focus": "Focus" if lang == "EN" else "Zone",
        "cycle": "Cycle" if lang == "EN" else "Période",
        "pattern": "Historical Pattern" if lang == "EN" else "Tendance Historique",
        "density": "Spatial Density" if lang == "EN" else "Densité Spatiale",
        "location": "Location" if lang == "EN" else "Emplacement",
        "timeframe": "Time Frame" if lang == "EN" else "Période",
        "pollutant": "Pollutant" if lang == "EN" else "Polluant"
    }

    # 7. HTML TEMPLATE
    html_template = """
    <!DOCTYPE html>
    <html lang="{{ lang_code }}">
    <head>
        <meta charset="UTF-8">
        <title>{{ labels.title }}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            :root { --bg-color: #f8fafc; font-family: 'Outfit', sans-serif; }
            html, body { height: 100%; margin: 0; padding: 0; overflow: hidden; background-color: var(--bg-color); }
            body { display: flex; flex-direction: column; padding: 1.5rem; box-sizing: border-box; }
            
            .dashboard-container { 
                display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: auto 1fr auto; 
                gap: 1.5rem; height: 100%; width: 100%; max-width: 1850px; margin: 0 auto;
            }
            .card { background: #ffffff; border-radius: 1.5rem; padding: 1.75rem; border: 1px solid rgba(0,0,0,0.05); display: flex; flex-direction: column; min-height: 0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
            .header-row { grid-column: span 2; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; }
            .footer-row { grid-column: span 2; display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
            .mini-box { background: white; border-radius: 1.25rem; padding: 1.25rem; border: 1px solid rgba(0,0,0,0.05); }
            .chart-wrapper { flex: 1; min-height: 0; position: relative; margin-top: 1rem; }
            #map-container { flex: 1; min-height: 300px; border-radius: 1rem; margin-top: 1rem; z-index: 1; }
            .ranking-item { line-height: 1.2; padding: 0.5rem 0; }
            .accent-label { font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; }
            .box-yellow { background-color: #fef08a; border: 2px solid #eab308; }
            .box-blue { background-color: #bfdbfe; border: 2px solid #3b82f6; }
            .box-grey { background-color: #e2e8f0; border: 2px solid #94a3b8; }
        </style>
    </head>
    <body>
        <div class="dashboard-container">
            <div class="header-row">
                <div class="mini-box"><span class="accent-label">{{ labels.agent }}</span><div class="text-2xl font-bold mt-1">{{ pollutant }}</div></div>
                <div class="mini-box"><span class="accent-label">{{ labels.volume }}</span><div class="text-2xl font-bold mt-1">{{ display_total }} {{ display_unit }}</div></div>
                <div class="mini-box"><span class="accent-label">{{ labels.focus }}</span><div class="text-2xl font-bold mt-1 text-indigo-600">{{ location }}</div></div>
                <div class="mini-box"><span class="accent-label">{{ labels.cycle }}</span><div class="text-2xl font-bold mt-1">{{ year_range }}</div></div>
            </div>

            <div class="card">
                <h2 class="text-xs font-bold text-slate-400 uppercase tracking-widest">{{ labels.pattern }}</h2>
                <div class="chart-wrapper"><canvas id="trendChart"></canvas></div>
            </div>

            <div class="card">
                <div class="flex justify-between items-start">
                    <h2 class="text-xs font-bold text-slate-400 uppercase tracking-widest">{{ labels.density }}</h2>
                    <span class="text-[0.65rem] font-bold text-slate-500 uppercase">({{ display_unit }})</span>
                </div>
                <div id="map-container"></div>
                <div class="mt-4 border-t pt-4 h-48 overflow-y-auto">
                    {% for f in top_facilities %}
                    <div class="flex justify-between text-[0.7rem] border-b border-slate-50 last:border-0 ranking-item">
                        <span class="font-medium text-slate-700 pr-4">{{ f.DisplayName }}</span>
                        <span class="font-bold text-slate-900 whitespace-nowrap">{{ "{:,.2f}".format(f.Quantity) }} {{ display_unit }}</span>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <div class="footer-row">
                <div class="card box-yellow !flex-row items-center gap-4 !py-4">
                    <div class="text-2xl">📍</div>
                    <div><span class="accent-label">{{ labels.location }}</span><div class="text-xl font-bold">{{ location }}</div></div>
                </div>
                <div class="card box-blue !flex-row items-center gap-4 !py-4">
                    <div class="text-2xl">🕒</div>
                    <div><span class="accent-label">{{ labels.timeframe }}</span><div class="text-xl font-bold">{{ year_range }}</div></div>
                </div>
                <div class="card box-grey !flex-row items-center gap-4 !py-4">
                    <div class="text-2xl">☁️</div>
                    <div><span class="accent-label">{{ labels.pollutant }}</span><div class="text-xl font-bold">{{ pollutant[:25] }}</div></div>
                </div>
            </div>
        </div>

        <script>
            try {
                const ctx = document.getElementById('trendChart').getContext('2d');
                const gradient = ctx.createLinearGradient(0, 0, 0, 400);
                gradient.addColorStop(0, 'rgba(99, 102, 241, 0.2)');
                gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: {{ trend_labels | tojson }},
                        datasets: [{
                            data: {{ trend_values | tojson }},
                            borderColor: '#6366f1',
                            backgroundColor: gradient,
                            borderWidth: 5,
                            fill: true,
                            tension: 0.4,
                            pointRadius: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: { duration: 4000, easing: 'easeInOutQuart', delay: 1000 },
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.03)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });

                const map = L.map('map-container', { zoomControl: false, attributionControl: false });
                L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(map);
                const points = {{ map_points | tojson }};
                const bounds = {{ bounds | tojson }};
                points.forEach(p => { 
                    L.circleMarker([p.Lat, p.Lon], { radius: p.Size, color: '#ef4444', weight: 2, fillOpacity: 0.6 })
                     .addTo(map).bindTooltip("<b>"+p.Facility+"</b>"); 
                });
                if (bounds.length > 0) map.fitBounds(bounds, { padding: [40, 40] });

            } catch (err) {
                console.error(err);
            }
        </script>
    </body>
    </html>
    """
    return Template(html_template).render(
        pollutant=pollutant, display_total=display_total, display_unit=display_unit,
        location=location_name, year_range=year_range, trend_labels=trend_labels,
        trend_values=trend_values, map_points=map_points, bounds=bounds, 
        top_facilities=top_facs, labels=labels, lang_code=lang.lower()
    )