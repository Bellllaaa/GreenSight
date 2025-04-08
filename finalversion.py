import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import folium
from streamlit_folium import st_folium
import os
import base64
from streamlit_option_menu import option_menu
from streamlit_geolocation import streamlit_geolocation
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import haversine_distances
from geopy.geocoders import Nominatim
from PIL import Image
from fpdf import FPDF

DATA_FILE = "waste_reports.csv"
date = datetime.now().strftime("%Y%m%d")
LANDFILL_DATA_FILE = "large_landfills.csv"


# Function to reverse geocode a latitude and longitude to an address.
@st.cache_data
def get_address(lat, lon):
    geolocator = Nominatim(user_agent="waste_app")
    try:
        location = geolocator.reverse((lat, lon), language="en")
        return location.address if location else "Address not found"
    except Exception as e:
        return "Error fetching address"

# Generate popups for map (used only for the Report Incident and View Analysis pages)
def generate_popup(row):
    date_str = str(row['date'])
    popup_html = (
        f"<strong>Date:</strong> {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}<br>"
        f"<strong>Description:</strong> {row['description']}<br>"
        f"<strong>Coordinates:</strong> ({row['lat']}, {row['lon']})<br>"
    )
    if "image" in row and pd.notna(row["image"]) and row["image"] != "" and os.path.exists(row["image"]):
        with open(row["image"], "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode("utf-8")
            popup_html += f'<img src="data:image/jpeg;base64,{img_base64}" width="200"><br>'
    return popup_html

    
# Sidebar navigation
with st.sidebar:
    selected = option_menu(
        menu_title="Navigation",
        options=["Report Incident", "View Analysis", "Graphic Analysis", "Community", "Organize Cleanup","Hazardous Waste"],
    )

    logo = Image.open("GreenSight.png")
    st.image(logo, use_container_width=True)

# --- REPORT INCIDENT ---
if selected == "Report Incident":
    st.header("Report Illegal Waste Location")

    location = streamlit_geolocation()
    if (location and 'latitude' in location and 'longitude' in location and
            location['latitude'] is not None and location['longitude'] is not None):
        current_lat = location['latitude']
        current_lon = location['longitude']  # Store as positive for input box
    else:
        current_lat = 34.0
        current_lon = 79.0

    with st.form("report_form"):
        lat = st.number_input("Latitude", value=current_lat)
        lon = st.number_input("Longitude", value=current_lon)
        description = st.text_input("Description of Waste")
        image_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])
        submitted = st.form_submit_button("Submit Report")

        if submitted:
            stored_lon = -lon  # Negate longitude when storing in the file
            if image_file:
                os.makedirs("images", exist_ok=True)
                image_path = f"images/{date}_{lat}_{stored_lon}.jpg"
                with open(image_path, "wb") as f:
                    f.write(image_file.getbuffer())
            else:
                image_path = ""

            new_report = pd.DataFrame([[lat, stored_lon, date, description, image_path]],
                                      columns=["lat", "lon", "date", "description", "image"])
            new_report.to_csv(DATA_FILE, mode="a", header=not os.path.exists(DATA_FILE), index=False)
            st.success("Report submitted!")

    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        m = folium.Map(location=[43.6532, -79.3832], zoom_start=12)

        # Plot the markers using the correct longitude (negating stored value for display)
        for _, row in df.iterrows():
            popup_html = generate_popup(row)
            folium.CircleMarker(
                location=[row['lat'], -row['lon']],  # correct longitude
                radius=10,
                color="red",
                fill=True,
                fill_color="red",
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(m)
        st_folium(m, width=700)

# --- VIEW ANALYSIS ---
elif selected == "View Analysis":
    st.header("Waste Pollution Hotspot Analysis")

    st.markdown("""
        This map visualizes different types of waste pollution hotspots using color-coded markers:

        - 🟦 **Blue**: Detected *illegal garbage dumps* — reported or suspected based on analysis.
        - 🔴 **Red**: *Pollution-prone zones* — areas showing signs of concentrated waste accumulation or likely risk zones.
        - 🟩 **Green**: *Registered dump locations* — verified data from the official government waste management database.

        Use this tool to explore problem areas and compare community reports with government-registered sites. Data-driven insights can help target clean-up efforts and improve waste management strategies.
        """)
    if not os.path.exists(DATA_FILE):
        st.warning("No data to analyze yet.")
        st.stop()

    df = pd.read_csv(DATA_FILE)
    dumps = pd.read_csv(LANDFILL_DATA_FILE)
    location = streamlit_geolocation()
    if location is None:
        st.error("Unable to retrieve your geolocation. Please ensure location access is enabled and try again.")
        st.stop()

    user_lat = location.get('latitude')
    user_lon = location.get('longitude')
    coords_rad = np.radians(df[["lat", "lon"]])
    dbscan = DBSCAN(eps=0.0005, min_samples=5, metric="haversine").fit(coords_rad)

    m = folium.Map(location=[43.6532, -79.3832], zoom_start=12)

    # Plot individual markers with correct longitude
    for _, row in df.iterrows():
        popup_html = generate_popup(row)
        folium.CircleMarker(
            location=[row['lat'], -row['lon']],  # correct longitude
            radius=3,
            color="blue",
            fill=True,
            fill_opacity=0.4,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)

    for _, row in dumps.iterrows():
        #popup_html = generate_popup(row)
        latitude = row['LATITUDE']
        longitude = row['LONGITUDE']
        folium.CircleMarker(
        location=[latitude,longitude],  # correct longitude
        radius=3,
        color="green",
        fill=True,
        fill_opacity=0.4,
        #popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)


    # Plot hotspots based on clustering
    for label in set(dbscan.labels_):
        if label != -1:  # Exclude noise
            cluster_points = df.loc[dbscan.labels_ == label, ["lat", "lon"]]
            centroid_lat = cluster_points["lat"].mean()
            centroid_lon = -cluster_points["lon"].mean()  # convert stored lon to actual value
            centroid_coords = np.radians([centroid_lat, centroid_lon])
            cluster_coords = np.radians(cluster_points[["lat", "lon"]])
            distances = haversine_distances(cluster_coords, centroid_coords.reshape(1, -1)) * 6371
            max_distance = np.max(distances)
            max_radius = min(max_distance * 1000, 5000)  # limit radius to 5km
            folium.Circle(
                location=[centroid_lat, centroid_lon],
                radius=max_radius,
                color="red",
                fill=True,
                fill_opacity=0.2
            ).add_to(m)
    st_folium(m, width=700)

    analyze_pins_button = st.button("Analyze Pins")
    if analyze_pins_button:
        st.subheader("Pin Information")
        for _, row in df.iterrows():
            # Get the actual coordinates (convert stored longitude)
            actual_lat = row['lat']
            actual_lon = row['lon']
            address = get_address(actual_lat, actual_lon)
            st.write(f"**Date:** {str(row['date'])[:4]}-{str(row['date'])[4:6]}-{str(row['date'])[6:]}")
            st.write(f"**Description:** {row['description']}")
            st.write(f"**Coordinates:** ({actual_lat}, {actual_lon})")
            st.write(f"**Address:** {address}")
            if "image" in row and pd.notna(row["image"]) and row["image"] != "" and os.path.exists(row["image"]):
                st.image(row["image"], width=200)
            st.write("---")

# --- GRAPHIC ANALYSIS ---
elif selected == "Graphic Analysis":
    st.header("Data Analytics")

    if not os.path.exists(DATA_FILE):
        st.warning("No data available.")
        st.stop()

    df = pd.read_csv(DATA_FILE)
    if df.empty:
        st.warning("No reports to analyze.")
        st.stop()

    counts = df['date'].value_counts().sort_index()
    st.subheader("Reports Over Time")
    st.line_chart(counts)

    st.subheader("Statistical Summary")
    st.write(df.describe())

    with st.form("report_form"):
       export = st.form_submit_button("export")
       if export:
            pdf = FPDF(orientation='P', unit='mm', format=(297, 420))  # A3 portrait size
            pdf.add_page()
            pdf.set_font("Arial", size=15)
            df = pd.read_csv(DATA_FILE)
        #    dateOrganizer = DateSeperator.SeperateDate()


            selected_headers = ["lat","lon","date","description"]
            for header in selected_headers:
                if(header == "description"):
                    pdf.cell(120, 10, header, border=1)
                else:
                    pdf.cell(40, 10, header, border=1)


            pdf.ln()


            # Rows
            for idx, e in df.iterrows():
                latitude = e["lat"]
                longitude = e["lon"]
                date = e["date"]
                description = e["description"]
                date_str = str(date)
                pdf.cell(40, 10, str(latitude), border=1)
                pdf.cell(40, 10, str(longitude), border=1)
                pdf.cell(40, 10, f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}", border=1)
                pdf.cell(120, 10, str(description), border=1)
                pdf.ln()

            pdf.output("output.pdf")




# --- ORGANIZE CLEANUP ---
elif selected == "Organize Cleanup":
    st.header("Organize Cleanup Event")
    target_option = st.radio("Select target location", ("Closest Dump", "Biggest Dump"))
    st.write("Please share your location")

    if target_option == "Closest Dump":
        # Get the user's current location
        location = streamlit_geolocation()
        if location is None:
            st.error("Unable to retrieve your geolocation. Please ensure location access is enabled and try again.")
            st.stop()

        user_lat = location.get('latitude')
        user_lon = location.get('longitude')
        if user_lat is None or user_lon is None:
            st.error("Geolocation data is incomplete. Please check your location settings.")
            st.stop()

        user_coord = np.radians([user_lat, user_lon])
        df = pd.read_csv(DATA_FILE)
        all_coords = np.radians(df[['lat', 'lon']])
        distances = haversine_distances([user_coord], all_coords)[0] * 6371  # in km
        min_idx = np.argmin(distances)
        closest_report = df.iloc[min_idx]

        st.subheader("Closest Dump Location")
        st.write(f"**Latitude:** {closest_report['lat']}  |  **Longitude:** {closest_report['lon']}")
        st.write(f"**Reported on:** {closest_report['date']}")
        st.write(f"**Distance from you:** {distances[min_idx]:.2f} km")

        # Display a map with simple markers (no popups)
        m = folium.Map(location=[user_lat, user_lon], zoom_start=12)
        folium.Marker(
            location=[user_lat, user_lon],
            icon=folium.Icon(color="blue")
        ).add_to(m)
        folium.Marker(
            location=[closest_report['lat'], closest_report['lon']],
            icon=folium.Icon(color="red")
        ).add_to(m)
        st_folium(m, width=700)

        # Convert stored longitude to actual coordinate (assumed stored as negative value)
        actual_lat = float(closest_report['lat'])
        try:
            actual_lon = -float(closest_report['lon'])
        except Exception as e:
            st.error("Invalid longitude data in the selected report.")
            st.stop()

        # Get the actual address from the dump location
        address = get_address(actual_lat, actual_lon)
        # st.write(f"**Dump Address:** {address}")

        target_lat = actual_lat
        target_lon = float(closest_report['lon'])  # Keep stored value if needed

    elif target_option == "Biggest Dump":
        st.subheader("Biggest Dump Cluster")
        df = pd.read_csv(DATA_FILE)
        if len(df) < 5:
            st.warning("Not enough reports to identify clusters.")
            st.stop()
        coords = np.radians(df[["lat", "lon"]])
        dbscan = DBSCAN(eps=0.0005, min_samples=5, metric="haversine").fit(coords)
        df['cluster'] = dbscan.labels_

        clusters = df[df['cluster'] != -1]
        if clusters.empty:
            st.error("No clusters detected in the current data.")
            st.stop()

        cluster_counts = clusters['cluster'].value_counts()
        biggest_cluster_label = cluster_counts.idxmax()
        cluster_points = df[df['cluster'] == biggest_cluster_label][['lat', 'lon']]
        centroid = cluster_points.mean().values

        st.write(f"**Cluster Label:** {biggest_cluster_label}")
        st.write(f"**Number of Reports:** {cluster_counts.max()}")
        st.write(f"**Centroid Location:** {centroid[0]:.5f}, {centroid[1]:.5f}")

        m = folium.Map(location=centroid, zoom_start=12)
        for _, row in cluster_points.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=3,
                color="blue"
            ).add_to(m)
        folium.Marker(
            location=centroid,
            icon=folium.Icon(color="green")
        ).add_to(m)
        st_folium(m, width=700)

        # Convert centroid coordinates if necessary (adjust sign for longitude)
        try:
            centroid_lat = float(centroid[0])
            centroid_lon = -float(centroid[1])
        except Exception as e:
            st.error("Invalid centroid coordinates.")
            st.stop()

        address = get_address(centroid_lat, centroid_lon)
        st.write(f"**Cluster Address (Centroid):** {address}")

        target_lat = centroid_lat
        target_lon = float(centroid[1])  # stored value

    # Section to schedule the cleanup event
    st.subheader("Schedule Cleanup Event")
    event_date = st.date_input("Select cleanup event date", datetime.now())
    event_time = st.time_input("Select cleanup event time", datetime.now().time())
    event_description = st.text_area("Event Description (optional)", placeholder="Describe the cleanup event...")

    st.subheader("Accessibility Features")
    col1, col2 = st.columns(2)
    with col1:
        wheelchair_access = st.checkbox("♿ Wheelchair accessible routes")
        interpreter = st.checkbox("👐 Sign language interpreter requested")
    with col2:
        child_friendly = st.checkbox("🧒 Child-friendly facilities")
        transport = st.checkbox("🚌 Senior-friendly transportation available")
    
    other_needs = st.text_input("Special requirements (e.g., religious accommodations, dietary needs)")

    if st.button("Organize Cleanup Event"):
        # Convert checkboxes to comma-separated string
        access_features = []
        if wheelchair_access: access_features.append("wheelchair")
        if interpreter: access_features.append("interpreter")
        if child_friendly: access_features.append("child_friendly")
        if transport: access_features.append("senior_transport")
        
        event_df = pd.DataFrame(
            [[event_date, event_time, target_lat, target_lon, event_description,
             ",".join(access_features), other_needs]],
            columns=["date", "time", "lat", "lon", "description", 
                    "access_features", "special_requirements"]
        )
        
        EVENTS_FILE = "cleanup_events.csv"
        if os.path.exists(EVENTS_FILE):
            event_df.to_csv(EVENTS_FILE, mode="a", header=False, index=False)
        else:
            event_df.to_csv(EVENTS_FILE, index=False)
        st.success("Cleanup event organized successfully!")
        


# --- COMMUNITY ---
elif selected == "Community":
    st.header("🌍 Community Waste Reports")
    df = pd.read_csv("cleanup_events.csv")
    if df.empty:
        st.info("No reports submitted yet.")
        st.stop()

    # Add accessibility icons processing
    def get_access_icons(access_str):
        icons = []
        if isinstance(access_str, str):
            if "wheelchair" in access_str: icons.append("♿")
            if "interpreter" in access_str: icons.append("👐")
            if "child_friendly" in access_str: icons.append("🧒")
            if "senior_transport" in access_str: icons.append("🚌")
        return " ".join(icons)
    
    df["access_icons"] = df["access_features"].apply(get_access_icons)

    # Rest of your existing community code...
    user_location = streamlit_geolocation()
    user_lat = user_location['latitude'] if user_location else None
    user_lon = user_location['longitude'] if user_location else None

    sort_option = st.selectbox("Sort by:", ["Most Recent", "Closest to Me"])

    if "description" not in df.columns:
        df["description"] = "No description provided."

    if sort_option == "Most Recent":
        df_sorted = df.sort_values(by="date", ascending=True)
    elif sort_option == "Closest to Me" and user_lat is not None:
        df["distance"] = np.sqrt((df["lat"] - user_lat)**2 + (df["lon"] - user_lon)**2)
        df_sorted = df.sort_values(by="distance")
    else:
        st.warning("Cannot sort by distance without location access.")
        df_sorted = df

    for idx, row in df_sorted.iterrows():
        try:
            actual_lat = float(row['lat'])
            actual_lon = float(row['lon'])
        except Exception as e:
            st.error("Invalid coordinate data in a report.")
            continue

        address = get_address(actual_lat, actual_lon)
        bg_color = "#f0f8ff" if idx % 2 == 0 else "#ffe4e1"
        with st.container():
            st.markdown(
    f"""
    <div style="background-color:{bg_color}; padding:15px; border-radius:12px; margin-bottom:10px;">
        <h4>📍 Location: ({address})</h4>
        <p><strong>🗓 Date:</strong> {row['date']}</p>
        <p><strong>⏰ Time:</strong> {row['time']}</p>
        <p><strong>📝 Description:</strong> {row['description']}</p>
        <p><strong>🏠 Coordinates:</strong> {actual_lat:.4f}, {actual_lon:.4f}</p>
        <p><strong>♿️ Accessibility:</strong> {row['access_features']}</p>
        <p><strong>‼️ Special Requirements:</strong> {row['special_requirements']}</p>
        <a href="https://x.com/intent/tweet?text=Check%20out%20this%20illegal%20waste%20report!%20{row['description']}%20{address}" target="_blank">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/b/b7/X_logo.jpg" alt="Share on X" width="30" style="margin-right:10px;">
                    </a>
                    <a href="https://www.instagram.com/?url=https://example.com/{row['lat']},{row['lon']}" target="_blank">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/9/95/Instagram_logo_2022.svg" alt="Share on Instagram" width="30" style="margin-right:10px;">
                    </a>
                    <a href="https://www.youtube.com/results?search_query={row['description']}" target="_blank">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/4/42/YouTube_icon_%282013-2017%29.png" alt="Share on YouTube" width="30">
                    </a>
    </div>
    """,
    unsafe_allow_html=True
)

elif selected == "Hazardous Waste":
    st.header("WHMIS Instruction")
    image = Image.open("pictogram_names.gif")


   # Display the image
    st.image(image, caption='WHMIS Labels!', use_container_width=True)

    st.markdown("""
    **WHMIS** stands for **Workplace Hazardous Materials Information System**.  
    It's a system designed to ensure safe use of hazardous materials in Canadian workplaces.

    The image below shows **WHMIS pictograms**, which are used on labels to indicate the type of hazard a product presents.
    Learn to recognize these symbols to protect yourself and others from potential harm!
    """)

    st.markdown("""
    ### Key WHMIS Symbols Explained:
    - 🔥 **Flame**: Flammable materials or substances that can ignite easily.
    - ☣️ **Biohazardous Infectious Materials**: Organisms or toxins that can cause diseases.
    - ☠️ **Skull and Crossbones**: Toxic materials that may cause immediate and serious health effects or death.
    - 🧪 **Corrosion**: Materials that can cause skin burns, eye damage, or corrode metals.
    - ⚠️ **Exclamation Mark**: May cause less serious health effects like skin irritation or dizziness.
    - 🌱 **Environment**: Harmful to aquatic life (note: not mandatory in Canada but often included).
    - 💥 **Exploding Bomb**: Explosive or self-reactive substances.
    - 🔬 **Health Hazard**: Materials that may cause serious long-term health effects like cancer.
    - 🔄 **Gas Cylinder**: Gases under pressure, which can explode if heated.

    Always read the labels and **follow proper disposal procedures** for hazardous waste to protect yourself and the environment.
    """)

