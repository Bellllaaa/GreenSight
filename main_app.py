import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

#used for prediction - clustering
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import haversine_distances
import folium
from streamlit_folium import st_folium
import os

from streamlit_geolocation import streamlit_geolocation
from streamlit_option_menu import option_menu



DATA_FILE = "waste_reports.csv"
date = datetime.now().strftime("%Y%m%d")
df = pd.read_csv(DATA_FILE)

# def generate_popup(row):
#     date_str = str(row['date'])
#     popup_html = (
#         f"<strong>Date:</strong> {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}<br>"
#         f"<strong>Description:</strong> {row['description']}<br>"
#         f"<strong>Coordinates:</strong> ({row['lat']}, {row['lon']})<br>"
#     )
#     if "image" in row and pd.notna(row["image"]) and row["image"] != "" and os.path.exists(row["image"]):
#         with open(row["image"], "rb") as img_file:
#             img_base64 = base64.b64encode(img_file.read()).decode("utf-8")
#             popup_html += f'<img src="data:image/jpeg;base64,{img_base64}" width="200"><br>'
#     return popup_html


st.set_page_config(
    page_title=None,
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto",
    menu_items=None,
)


with st.sidebar:
    selected = option_menu(
        menu_title="Navigation",
        options=["Report Incident", "Hotspot", "Graphic Analysis","Organize Cleanup", "Community"],
    )


if selected == "Report Incident":
    location = streamlit_geolocation()#current location
    # st.write(f"{location}")
    if location is not None:
        current_lat = location['latitude']
        # st.write(current_lat)
        current_lon = location['longitude']
        # st.write(current_lon)


    st.header("Report Illegal Waste Location")

    with st.form("report_form"): #(manual input)
        lat = st.number_input("Latitude", value=current_lat)
        lon = st.number_input("Longitude", value=current_lon)
        description = st.text_area("Describe the incident (optional)", placeholder="e.g., Piles of garbage near the park bench...")
        uploaded_image = st.file_uploader("Upload an image (optional)", type=["jpg", "jpeg", "png"])

        submitted = st.form_submit_button("Submit Report")
        
        if submitted:
            new_report = pd.DataFrame([[lat, lon, date]], columns=["lat", "lon", "date"])
            new_report.to_csv(DATA_FILE, mode="a", header=False, index=False)
            st.success("Report submitted!")


elif selected == "Hotspot":
    
    st.header("Waste Pollution Hotspot Analysis")
    # st.write(current_lat)
    # st.write(current_lon)

    if len(df) < 5:
        st.warning("Need at least 10 reports to analyze")
        st.stop()

    #algorithm -- cluster
    coords = np.radians(df[["lat", "lon"]])
    dbscan = DBSCAN(eps=0.0005, min_samples=5, metric="haversine").fit(coords)
    
    #map
    m = folium.Map(location=[43.6532, -79.3832], zoom_start=25)
    
    #reports
    for _, row in df.iterrows():
        # popup_html = generate_popup(row)    
        folium.CircleMarker(
            location=[row.lat, row.lon],
            radius=3,
            color="blue"
            # opacity=0.2
        ).add_to(m)
    
    # predicted hotspots
    for label in set(dbscan.labels_):
        if label != -1:  # -1 is noise
            cluster_points = df.loc[dbscan.labels_ == label, ["lat", "lon"]]
            centroid = cluster_points.mean().values
            
            # cluster radius
            distances = haversine_distances(
                np.radians(cluster_points),
                np.radians([centroid])
            ) * 6371
            
            folium.Circle(
                location=centroid,
                radius=np.max(distances) * 1000,  #convert to meters
                color="red",
                fill=True,
                fill_opacity=0.2
            ).add_to(m)
    
    st_folium(m, width=700)

elif selected == "Graphic Analysis": 
    st.header("Data Analytics")

    if df.empty:
        st.warning("No data available.")
        st.stop()
    counts = df['date'].value_counts()
    st.line_chart(counts)

    st.write(df.describe())



elif selected == "Organize Cleanup":
    st.header("Organize Cleanup Event")
    
    # Let the user choose which target to use for organizing cleanup
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

        # Additional check in case the keys are missing or None
        if user_lat is None or user_lon is None:
            st.error("Geolocation data is incomplete. Please check your location settings.")
            st.stop()

        # Calculate distances from the user to each waste report using the haversine formula
        user_coord = np.radians([user_lat, user_lon])
        all_coords = np.radians(df[['lat', 'lon']])
        distances = haversine_distances([user_coord], all_coords)[0] * 6371  # in kilometers
        min_idx = np.argmin(distances)
        closest_report = df.iloc[min_idx]

        st.subheader("Closest Dump Location")
        st.write(f"**Latitude:** {closest_report['lat']}  |  **Longitude:** {closest_report['lon']}")
        st.write(f"**Reported on:** {closest_report['date']}")
        st.write(f"**Distance from you:** {distances[min_idx]:.2f} km")

        # Display a map with markers for the user's location and the closest dump
        m = folium.Map(location=[user_lat, user_lon], zoom_start=12)
        folium.Marker(
            location=[user_lat, user_lon],
            popup="Your Location",
            icon=folium.Icon(color="blue")
        ).add_to(m)
        folium.Marker(
            location=[closest_report['lat'], closest_report['lon']],
            popup="Closest Dump",
            icon=folium.Icon(color="red")
        ).add_to(m)
        st_folium(m, width=700)

        # Save the chosen location for the cleanup event
        target_lat = closest_report['lat']
        target_lon = closest_report['lon']

    elif target_option == "Biggest Dump":
        st.subheader("Biggest Dump Cluster")
        if len(df) < 5:
            st.warning("Not enough reports to identify clusters.")
            st.stop()
        # Cluster reports using DBSCAN (ignoring noise points labeled as -1)
        coords = np.radians(df[["lat", "lon"]])
        dbscan = DBSCAN(eps=0.0005, min_samples=5, metric="haversine").fit(coords)
        df['cluster'] = dbscan.labels_

        # Only consider clusters (ignore noise)
        clusters = df[df['cluster'] != -1]
        if clusters.empty:
            st.error("No clusters detected in the current data.")
            st.stop()

        # Identify the cluster with the most reports
        cluster_counts = clusters['cluster'].value_counts()
        biggest_cluster_label = cluster_counts.idxmax()
        cluster_points = df[df['cluster'] == biggest_cluster_label][['lat', 'lon']]
        centroid = cluster_points.mean().values

        st.write(f"**Cluster Label:** {biggest_cluster_label}")
        st.write(f"**Number of Reports:** {cluster_counts.max()}")
        st.write(f"**Centroid Location:** {centroid[0]:.5f}, {centroid[1]:.5f}")

        # Display the cluster on a map
        m = folium.Map(location=centroid, zoom_start=12)
        for _, row in cluster_points.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=3,
                color="blue"
            ).add_to(m)
        folium.Marker(
            location=centroid,
            popup="Cluster Centroid",
            icon=folium.Icon(color="green")
        ).add_to(m)
        st_folium(m, width=700)

        # Save the chosen location (centroid) for the cleanup event
        target_lat = centroid[0]
        target_lon = centroid[1]

    # Section to schedule the cleanup event
    st.subheader("Schedule Cleanup Event")
    event_date = st.date_input("Select cleanup event date", datetime.now())
    event_description = st.text_area("Event Description (optional)", placeholder="Describe the cleanup event...")

    if st.button("Organize Cleanup Event"):
        # Save the event details to a CSV file (appending to existing records if any)
        event_df = pd.DataFrame(
            [[event_date, target_lat, target_lon, event_description]],
            columns=["date", "lat", "lon", "description"]
        )
        EVENTS_FILE = "cleanup_events.csv"
        if os.path.exists(EVENTS_FILE):
            event_df.to_csv(EVENTS_FILE, mode="a", header=False, index=False)
        else:
            event_df.to_csv(EVENTS_FILE, index=False)
        st.success("Cleanup event organized successfully!")


elif selected == "Community":
    st.header("🌍 Community Waste Reports")

    if df.empty:
        st.info("No reports submitted yet.")
        st.stop()

    # Get user location (for closest)
    user_location = streamlit_geolocation()
    user_lat = user_location['latitude'] if user_location else None
    user_lon = user_location['longitude'] if user_location else None

    # Filters
    sort_option = st.selectbox("Sort by:", ["Most Recent", "Closest to Me"])

    # Add description column fallback
    if "description" not in df.columns:
        df["description"] = "No description provided."

    # Sorting logic
    if sort_option == "Most Recent":
        df_sorted = df.sort_values(by="date", ascending=False)
    elif sort_option == "Closest to Me" and user_lat is not None:
        df["distance"] = np.sqrt((df["lat"] - user_lat)**2 + (df["lon"] - user_lon)**2)
        df_sorted = df.sort_values(by="distance")
    else:
        st.warning("Cannot sort by distance without location access.")
        df_sorted = df

    # Display reports
    for idx, row in df_sorted.iterrows():
        bg_color = "#f0f8ff" if idx % 2 == 0 else "#ffe4e1"  # light blue / pink
        with st.container():
            st.markdown(
                f"""
                <div style="background-color:{bg_color}; padding:15px; border-radius:12px; margin-bottom:10px;">
                    <h4>📍 Location: ({row['lat']:.4f}, {row['lon']:.4f})</h4>
                    <p><strong>🗓 Date:</strong> {row['date']}</p>
                    <p><strong>📝 Description:</strong> {row['description']}</p>
                """,
                unsafe_allow_html=True
            )

            # Try to load corresponding image
            img_filename = f"img_{row['date']}_{row['lat']}_{row['lon']}.jpg"
            img_path = os.path.join("uploaded_images", img_filename)
            if os.path.exists(img_path):
                st.image(img_path, width=400, caption="Attached image")

            st.markdown("</div>", unsafe_allow_html=True)
