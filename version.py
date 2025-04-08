import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import folium
from streamlit_folium import st_folium
import os
import base64
from streamlit_option_menu import option_menu
from streamlit_geolocation import streamlit_geolocation  # Correct way to call the geolocation service

DATA_FILE = "waste_reports.csv"
date = datetime.now().strftime("%Y%m%d")

# Function to generate the popup HTML for markers
def generate_popup(row):
    # Convert the date to a string and format it
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


# Sidebar with cleaner navigation bar
with st.sidebar:
    selected = option_menu(
        menu_title="Navigation",
        options=["Report Incident", "View Analysis", "Graphic Analysis"],
    )

if selected == "Report Incident":
    st.header("Report Illegal Waste Location")

    # Try to get current geolocation
    location = streamlit_geolocation()  # Get current location from geolocation widget

    # Default coordinates if location cannot be fetched
    if location and 'latitude' in location and 'longitude' in location:
        current_lat = location['latitude']
        current_lon = location['longitude']
    else:
        current_lat = 34.0  # Default value if location cannot be obtained
        current_lon = -79.0  # Default value if location cannot be obtained

    # Autofill button outside of the form
    if st.button("Autofill Coordinates"):
        if location and 'latitude' in location and 'longitude' in location:
            current_lat = location['latitude']
            current_lon = location['longitude']
            st.success(f"Coordinates autofilled: ({current_lat}, {current_lon})")
        else:
            st.warning("Unable to fetch your location.")

    with st.form("report_form"):  # Manual input form
        lat = st.number_input("Latitude", value=current_lat)
        lon = st.number_input("Longitude", value=current_lon)
        description = st.text_input("Description of Waste")
        image_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])

        # Submit button inside the form
        submitted = st.form_submit_button("Submit Report")

        if submitted:
            if image_file:
                image_path = f"images/{date}_{lat}_{lon}.jpg"
                with open(image_path, "wb") as f:
                    f.write(image_file.getbuffer())
            else:
                image_path = ""

            # Save data to CSV
            new_report = pd.DataFrame([[lat, lon, date, description, image_path]],
                                      columns=["lat", "lon", "date", "description", "image"])
            new_report.to_csv(DATA_FILE, mode="a", header=False, index=False)
            st.success("Report submitted!")

    # Display map
    df = pd.read_csv(DATA_FILE, header=None, names=["lat", "lon", "date", "description", "image"])

    m = folium.Map(location=[df.lat.mean(), df.lon.mean()], zoom_start=12)

    # Add markers with popups
    for _, row in df.iterrows():
        popup_html = generate_popup(row)
        folium.CircleMarker(
            location=[row['lat'], -row['lon']],  # Ensure the longitude is negative
            radius=10,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.6,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)

    st_folium(m, width=700)

elif selected == "View Analysis":
    st.header("Waste Pollution Hotspot Analysis")

    # Map for analysis
    df = pd.read_csv(DATA_FILE)
    m = folium.Map(location=[df.lat.mean(), df.lon.mean()], zoom_start=12)

    # Add report markers to the map
    for _, row in df.iterrows():
        popup_html = generate_popup(row)
        folium.CircleMarker(
            location=[row['lat'], -row['lon']],  # Ensure the longitude is negative
            radius=2,
            color="blue",
            opacity=0.2,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)

    # Display the map
    st_folium(m, width=700)

    # Button to analyze pins
    analyze_button = st.button("Analyze Pins")

    if analyze_button:
        # Display the information of each pin
        st.subheader("Pin Information")

        for _, row in df.iterrows():
            st.write(f"**Date**: {str(row['date'])[:4]}-{str(row['date'])[4:6]}-{str(row['date'])[6:]}")  # Formatting date
            st.write(f"**Description**: {row['description']}")
            st.write(f"**Coordinates**: ({row['lat']}, {row['lon']})")
            if "image" in row and pd.notna(row["image"]) and row["image"] != "" and os.path.exists(row["image"]):
                st.image(row["image"], width=200)  # Display image if available
            st.write("---")

elif selected == "Graphic Analysis":
    st.header("Data Analytics")

    df = pd.read_csv(DATA_FILE)

    if df.empty:
        st.warning("No data available.")
        st.stop()

    # Display a line chart for date-based counts
    counts = df['date'].value_counts()
    st.line_chart(counts)

    # Show a descriptive statistics summary
    st.write(df.describe())