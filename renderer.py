import sys
import asyncio
import json
import os
from jinja2 import Template
from playwright.sync_api import sync_playwright

# FORCE PROACTOR LOOP FOR PLAYWRIGHT ON WINDOWS
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def run_render():
    with open("render_data.json", "r") as f:
        data = json.load(f)
    
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            :root { --bg-color: #f8fafc; --card-bg: #ffffff; font-family: 'Outfit', sans-serif; }
            body { background-color: var(--bg-color); margin: 0; padding: 0; display: flex; justify-content: center; overflow: hidden; }
            #capture-wrapper { padding: 40px; background-color: #f8fafc; display: inline-block; }
            .dashboard-container { width: 1280px; height: 720px; display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: auto 1fr auto; gap: 1.25rem; }
            .card { background: var(--card-bg); border-radius: 1.25rem; padding: 1.25rem; border: 1px solid rgba(0,0,0,0.05); display: flex; flex-direction: column; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.04); }
            .top-row { grid-column: span 2; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.25rem; }
            .bottom-row { grid-column: span 2; display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.25rem; }
            .mini-box { background: var(--card-bg); border-radius: 1rem; padding: 1rem 1.25rem; border: 1px solid rgba(0,0,0,0.05); }
            .accent-label { color: #0d9488; font-weight: 700; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.05em; }
            #leaflet-map { width: 100%; height: 100%; border-radius: 0.75rem; z-index: 1; }
        </style>
    </head>
    <body>
        <div id="capture-wrapper">
            <div class="dashboard-container">
                <div class="top-row">
                    <div class="mini-box"><span class="accent-label">Pollutant</span><div class="text-lg font-semibold">{{ pollutant }}</div></div>
                    <div class="mini-box"><span class="accent-label">Total Released</span><div class="text-lg font-semibold">{{ display_total }} {{ display_unit }}</div></div>
                    <div class="mini-box"><span class="accent-label">Location</span><div class="text-lg font-semibold text-indigo-600">{{ location }}</div></div>
                    <div class="mini-box"><span class="accent-label">Period</span><div class="text-lg font-semibold">{{ year_range }}</div></div>
                </div>

                <div class="card">
                    <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider">Release Trends Over Time</h2>
                    <div class="flex-grow flex items-center justify-center mt-2">
                        <img src="data:image/png;base64,{{ graph_img }}" class="max-h-full">
                    </div>
                </div>

                <div class="card">
                    <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider">Geographic Concentration</h2>
                    <div class="flex-grow mt-2 relative">
                        <div id="leaflet-map"></div>
                    </div>
                </div>

                <div class="bottom-row">
                    <div class="card !flex-row items-center gap-4" style="background-color: #fef08a; border: 2px solid #eab308;">
                        <div class="w-10 h-10 rounded-full bg-white flex items-center justify-center text-amber-600">📍</div>
                        <div><span class="accent-label" style="color:#854d0e">Location</span><div class="text-xl font-bold">{{ location }}</div></div>
                    </div>
                    <div class="card !flex-row items-center gap-4" style="background-color: #bfdbfe; border: 2px solid #3b82f6;">
                        <div class="w-10 h-10 rounded-full bg-white flex items-center justify-center text-blue-600">🕒</div>
                        <div><span class="accent-label" style="color:#1e40af">Time Frame</span><div class="text-xl font-bold">{{ year_range }}</div></div>
                    </div>
                    <div class="card !flex-row items-center gap-4" style="background-color: #e2e8f0; border: 2px solid #94a3b8;">
                        <div class="w-10 h-10 rounded-full bg-white flex items-center justify-center text-slate-600">☁️</div>
                        <div><span class="accent-label" style="color:#475569">Pollutant</span><div class="text-xl font-bold">{{ pollutant[:20] }}</div></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Initialize map without a fixed view
            var map = L.map('leaflet-map', { zoomControl: false, attributionControl: false });
            L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png').addTo(map);

            // Plot all data points
            var points = [];
            {% for pt in map_points %}
            L.circleMarker([{{ pt.Lat }}, {{ pt.Lon }}], {
                radius: {{ pt.Size }},
                fillColor: "#ef4444",
                color: "#ffffff",
                weight: 1,
                fillOpacity: 0.6
            }).addTo(map);
            {% endfor %}

            // DYNAMIC ZOOM: Focus the map on the data bounds
            var dataBounds = {{ bounds | tojson }};
            if (dataBounds.length > 0) {
                map.fitBounds(dataBounds, { padding: [30, 30] });
            } else {
                map.setView([56.1304, -106.3468], 3); // Fallback to Canada view
            }
        </script>
    </body>
    </html>
    """

    template = Template(html_template)
    rendered_content = template.render(**data)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.set_content(rendered_content)
        
        # Wait for tiles to load and fitBounds to finish animating
        page.wait_for_timeout(4000) 
        
        element = page.query_selector("#capture-wrapper")
        if element:
            element.screenshot(path="temp_report.jpg", type='jpeg', quality=95)
        browser.close()

if __name__ == "__main__":
    run_render()