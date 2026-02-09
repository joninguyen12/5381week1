# Weather Dashboard — Shiny for Python

A modern, interactive web application built with Shiny for Python that queries the Weatherstack API to display current weather conditions for selected US cities. The app features a dark-themed UI and provides real-time weather data on demand.

![Weather Dashboard Screenshot](Screenshot%202026-02-01%20at%208.16.07%20PM.png)

---

## Table of Contents

- [Overview](#overview)
- [✨ Features](#-features)
- [📦 Installation](#-installation)
- [🔑 API Requirements](#-api-requirements)
- [🚀 How to Run](#-how-to-run)
- [💻 Usage Instructions](#-usage-instructions)
- [📁 Project Structure](#-project-structure)
- [🔧 Technical Details](#-technical-details)
- [📸 Screenshots](#-screenshots)
- [⚠️ Troubleshooting](#️-troubleshooting)
- [📚 Additional Resources](#-additional-resources)

---

## Overview

The Weather Dashboard is a Shiny for Python web application that allows users to:

- **Select multiple US cities** from a predefined list of 10 major cities
- **Choose temperature units** (Fahrenheit, Metric, or Scientific)
- **Query current weather data** on-demand via the Weatherstack API
- **View formatted results** in an interactive data table with temperature, humidity, wind speed, pressure, and weather descriptions

The application uses a reactive programming model where API calls are made only when the user clicks the **"Get Weather"** button, ensuring efficient API usage.

---

## ✨ Features

- ✅ **On-demand API queries** — Weather data is fetched only when requested
- ✅ **Multi-city selection** — Query weather for multiple cities simultaneously
- ✅ **Unit conversion** — Support for Fahrenheit (°F), Metric (°C), and Scientific units
- ✅ **Error handling** — Clear error messages for missing API keys, network issues, and API failures
- ✅ **Rate limiting** — Built-in 1-second delay between city queries to respect API rate limits
- ✅ **Modern UI** — Dark-themed interface with custom styling
- ✅ **Responsive design** — Clean sidebar layout with intuitive controls

---

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Install Dependencies

Navigate to the `01_query_api` directory and install the required Python packages:

```bash
cd 01_query_api
pip install -r requirements.txt
```

**Required packages:**
- `shiny>=1.0.0` — Shiny for Python web framework
- `pandas>=2.0.0` — Data manipulation and DataFrame handling
- `requests>=2.28.0` — HTTP library for API calls
- `python-dotenv>=1.0.0` — Environment variable management
- `numpy<2` — Numerical computing support

**Alternative:** Use [`requirements-shiny.txt`](requirements-shiny.txt) (which excludes numpy):

```bash
pip install -r requirements-shiny.txt
```

---

## 🔑 API Requirements

### Weatherstack API Key Setup

The application requires a Weatherstack API key to function. Follow these steps:

1. **Get a free API key:**
   - Visit [weatherstack.com](https://weatherstack.com/)
   - Sign up for a free account
   - Navigate to your dashboard to retrieve your API key

2. **Create a `.env` file:**
   - In the `01_query_api` directory, create a file named `.env`
   - Add the following line (replace `your_weatherstack_api_key` with your actual key):

   ```env
   WEATHER_API_KEY=your_weatherstack_api_key
   ```

3. **Security Note:**
   - The `.env` file should be in `.gitignore` (if using git)
   - **Never commit your API key to version control**
   - Keep your API key private and secure

### API Endpoint

The application uses the Weatherstack Current Weather API:
- **Base URL:** `http://api.weatherstack.com/current`
- **Authentication:** API key passed as `access_key` parameter
- **Rate Limits:** Free tier typically allows 1,000 requests/month

---

## 🚀 How to Run

1. **Ensure dependencies are installed** (see [Installation](#-installation))

2. **Verify your `.env` file exists** with a valid `WEATHER_API_KEY` (see [API Requirements](#-api-requirements))

3. **Start the Shiny application:**

   ```bash
   shiny run app.py
   ```

4. **Open your browser:**
   - The terminal will display a URL (typically `http://127.0.0.1:8000`)
   - Open this URL in your web browser
   - The Weather Dashboard will load

5. **To stop the app:**
   - Press `Ctrl+C` in the terminal where the app is running

---

## 💻 Usage Instructions

### Basic Workflow

1. **Select Cities:**
   - In the sidebar, use the **"Cities"** dropdown to select one or more cities
   - You can select multiple cities by clicking on additional options
   - Default selection includes: New York, Los Angeles, and Chicago

2. **Choose Units:**
   - Select your preferred temperature unit:
     - **Fahrenheit (°F, mph)** — US standard units
     - **Metric (°C, km/h)** — Celsius and kilometers per hour
     - **Scientific** — Scientific notation

3. **Fetch Weather Data:**
   - Click the **"Get Weather"** button
   - The app will query the Weatherstack API for each selected city
   - A status message will appear indicating success or any errors

4. **View Results:**
   - Weather data is displayed in an interactive table showing:
     - **City** — Name of the city
     - **Temperature_F** — Temperature in the selected unit
     - **Humidity** — Relative humidity percentage
     - **Wind_mph** — Wind speed (units vary by selection)
     - **Pressure** — Atmospheric pressure
     - **Weather** — Current weather description

### Available Cities

The app includes 10 predefined US cities:
- New York
- Los Angeles
- Chicago
- Houston
- Phoenix
- Philadelphia
- Seattle
- San Diego
- Boston
- San Jose

### Error Handling

The app handles various error scenarios:

- **Missing API Key:** Displays "API key not found. Add WEATHER_API_KEY to a .env file..."
- **No Cities Selected:** Shows "Please select at least one city."
- **API Errors:** Displays specific error messages from the Weatherstack API
- **Network Issues:** Shows connection error messages

---

## 📁 Project Structure

```
01_query_api/
├── app.py                    # Main Shiny application (UI + server logic)
├── weather_api.py            # Weatherstack API helper module
├── requirements.txt          # Python dependencies (includes numpy)
├── requirements-shiny.txt    # Python dependencies (minimal)
├── .env                      # API key configuration (create this file)
├── README.md                 # General query_api directory README
├── README_Shiny_Weather.md  # This file
└── Screenshot*.png           # Application screenshots
```

### File Descriptions

| File | Purpose |
|------|---------|
| [`app.py`](app.py) | Main Shiny application containing UI definition (`make_ui()`), server logic (`server()`), and reactive event handlers |
| [`weather_api.py`](weather_api.py) | Helper module that handles API key loading, weather data fetching (`fetch_weather()`), and error handling |
| [`requirements.txt`](requirements.txt) | Complete list of Python package dependencies |
| `.env` | Environment file containing the `WEATHER_API_KEY` (not included in repo) |

---

## 🔧 Technical Details

### Architecture

- **Framework:** Shiny for Python (core version, not shiny.express)
- **UI Pattern:** Sidebar layout with main content area
- **Reactivity Model:** Uses `reactive.value()` and `@reactive.effect` with `@reactive.event()` decorators
- **Data Flow:** User input → Button click → API call → Reactive value update → UI re-render

### Key Components

1. **UI (`make_ui()`):**
   - Custom CSS styling with dark theme
   - Sidebar with city selector, unit radio buttons, and action button
   - Main area with status messages and data table

2. **Server (`server()`):**
   - `_fetch_weather()` — Triggered by button click, calls API and updates reactive value
   - `status_ui()` — Renders status messages (initial state, success, or errors)
   - `weather_table()` — Renders the weather data DataFrame

3. **API Module (`weather_api.py`):**
   - `get_api_key()` — Loads API key from environment
   - `fetch_weather()` — Makes API requests, handles errors, returns DataFrame

### Rate Limiting

The app includes a 1-second delay between city queries to respect Weatherstack API rate limits and prevent request throttling.

---

## 📸 Screenshots

### Main Dashboard View
![Weather Dashboard - Main View](Screenshot%202026-02-01%20at%208.16.07%20PM.png)

### Weather Results Display
![Weather Dashboard - Results](Screenshot%202026-02-01%20at%208.32.32%20PM.png)

### Multiple Cities Selected
![Weather Dashboard - Multiple Cities](Screenshot%202026-02-01%20at%208.33.01%20PM.png)

---

## ⚠️ Troubleshooting

### Common Issues

**Issue:** "API key not found" error
- **Solution:** Ensure `.env` file exists in the `01_query_api` directory with `WEATHER_API_KEY=your_key`

**Issue:** App won't start
- **Solution:** Verify all dependencies are installed: `pip install -r requirements.txt`

**Issue:** No data returned
- **Solution:** Check your API key is valid and you haven't exceeded rate limits

**Issue:** Port already in use
- **Solution:** Shiny will automatically try another port, or stop other Shiny apps running

---

## 📚 Additional Resources

- [Shiny for Python Documentation](https://shiny.posit.co/py/)
- [Weatherstack API Documentation](https://weatherstack.com/documentation)
- [Python-dotenv Documentation](https://pypi.org/project/python-dotenv/)

---

## 📄 License

This project is part of the SYSEN 5381 course materials.

---

**Last Updated:** February 2026
