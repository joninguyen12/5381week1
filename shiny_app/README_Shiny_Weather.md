# Weather Dashboard — Shiny for Python

**SYSEN 5381 — Homework 1: AI-Powered Reporter Software**

The Weather Dashboard is an AI-powered reporter application that queries current weather conditions from up to ten U.S. cities and evaluates conditions by use case (e.g., athlete training, road trip). Data is provided by the free Weatherstack API; reports are produced by OpenAI or Ollama. The app features a dark-themed UI, real-time weather on demand, optional sample data when the API rate limit is reached, and AI-generated condition summaries and advisories tailored to the user’s use case.

---

## System Definition

| Component | Description |
|-----------|-------------|
| **Tool Name** | Weather Dashboard — An AI-powered reporter that queries and displays current weather for multiple US cities in user-selected units and generates use-case-specific AI advisories. |
| **Stakeholders & Needs** | **User/Student** — Needs quick access to current weather data and tailored advice (e.g., for training or travel) in preferred units (Fahrenheit, Metric, or Scientific).<br><br>**Instructor/Developer** — Needs a demonstration of API integration, reactive web app development, on-demand data fetching, and AI reporting (OpenAI/Ollama). |
| **System Goals** | 1. **SUMMARIZE** — Display weather in a table (City, Temperature, Humidity (%), Wind (mph), Pressure (mb), Conditions) and optionally generate an AI condition summary and advisory per city for the user’s use case.<br><br>2. **FORMAT** — Present weather in user-selected units (Fahrenheit, Metric, or Scientific).<br><br>3. **INTERPRET** — Show weather descriptions and AI-generated advisories (training, travel, or custom use case) for each selected city. |
| **Goal-Stakeholder Mapping** | **SUMMARIZE** → Weather table plus optional AI report.<br><br>**FORMAT** → Sidebar unit selection.<br><br>**INTERPRET** → Weather conditions and use-case-specific advisories per city. |

---

## Table of Contents

- [Overview](#overview)
- [✨ Features](#-features)
- [📦 Installation](#-installation)
- [🔑 API Requirements](#-api-requirements)
- [🚀 How to Run](#-how-to-run)
- [💻 Usage Instructions](#-usage-instructions)
- [📁 Project Structure](#-project-structure)
- [📊 Data Summary](#-data-summary)
- [🔧 Technical Details](#-technical-details)
- [⚠️ Troubleshooting](#️-troubleshooting)
- [📚 Additional Resources](#-additional-resources)

---

## Overview

The Weather Dashboard is a Shiny for Python web application that allows users to:

- **Select multiple US cities** from a predefined list of 10 major cities (default selection: New York, Los Angeles, Chicago). At least one city must be selected; otherwise the app notifies the user that the weather table could not be generated.
- **Choose temperature units** (Fahrenheit, Metric, or Scientific) for the data.
- **Use sample data** — A checkbox lets the user use sample data stored in the app for each city instead of querying the API when the free Weatherstack API rate limit has been reached.
- **Query current weather data** on-demand via the Weatherstack API when not using sample data.
- **View the weather table** with attributes per city: City, Temperature, Humidity (%), Wind (mph), Pressure (mb), Conditions.
- **Enter a use case** (e.g., athlete training, road trip). Default use case is training. The use case is used to tailor the AI report.
- **Generate an AI report** — After loading weather, the user can click **"Generate AI Insights"** to get an AI-generated condition summary and an advisory for each selected city pertaining to their use case (via OpenAI or Ollama).

The app uses a reactive model: **Get Weather** triggers `weather_api.py` to query the Weatherstack API and render the table; **Generate AI Insights** passes the use case and weather data to the AI module (`ai_weather.py`), which builds a tailored prompt, calls the AI, parses the response, and renders the report.

---

## ✨ Features

- ✅ **On-demand API queries** — Weather data is fetched only when **Get Weather** is clicked
- ✅ **Sample data option** — Checkbox to use sample data (skip API) when the free API rate limit is reached
- ✅ **Multi-city selection** — Up to 10 predefined US cities; at least one required
- ✅ **Unit conversion** — Fahrenheit (°F), Metric (°C), and Scientific units
- ✅ **Weather table** — City, Temperature, Humidity (%), Wind (mph), Pressure (mb), Conditions
- ✅ **Use-case input** — Optional text (e.g., training, road trip) to tailor the AI report; default is training
- ✅ **AI reporting** — Condition summary and advisory per city for the use case (OpenAI or Ollama)
- ✅ **Error handling** — Clear messages for missing API key, no cities selected, API errors, and AI errors
- ✅ **Rate limiting** — 1-second delay between city queries for Weatherstack
- ✅ **Modern UI** — Dark-themed sidebar with text boxes, radio buttons, and action buttons

---

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Install Dependencies

From the repository root, navigate to the **app3** directory and install the required Python packages:

```bash
cd 03_query_ai/app3
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
   - In the **app3** directory, create a file named `.env`
   - Add the following line (replace `your_weatherstack_api_key` with your actual key):

   ```env
   WEATHER_API_KEY=your_weatherstack_api_key
   ```

3. **Security Note:**
   - The `.env` file should be in `.gitignore` (if using git)
   - **Never commit your API key to version control**
   - Keep your API key private and secure

### API Endpoint

The application uses the Weatherstack Current Weather API to retrieve real-time weather for specified locations:
- **API Key:** `WEATHER_API_KEY` (in `.env`)
- **Endpoint:** `http://api.weatherstack.com/current`
- **Authentication:** API key passed as `access_key` parameter
- **Rate Limits:** Free tier typically allows 1,000 requests/month

**Request a free API key:** [https://weatherstack.com/signup/free](https://weatherstack.com/signup/free)

### Optional: AI (OpenAI or Ollama)

For **Generate AI Insights**, use either OpenAI (`OPENAI_API_KEY` in `.env`) or Ollama (local or cloud with `OLLAMA_API_KEY`). See [Technical Details → API Keys](#api-keys). Without an AI key, the app still runs; the AI button will show an error until configured or when using sample data.

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
   - Click the **"Get Weather"** button (or check **Use sample data (skip API)** to use built-in sample data when the API rate limit is reached)
   - The app queries the Weatherstack API for each selected city (or loads sample data)
   - A status message indicates success or any errors

4. **View Results:**
   - Weather data is displayed in an interactive table with:
     - **City** — Location name as queried
     - **Temperature** — Current temperature (units match selection: °F, °C, or Kelvin)
     - **Humidity (%)** — Relative humidity (0–100)
     - **Wind (mph)** — Wind speed (mph or km/h by selection)
     - **Pressure (mb)** — Atmospheric pressure in millibars
     - **Conditions** — Short weather description (e.g., Clear, Partly cloudy)

5. **Generate AI Report (optional):**
   - Enter a **Use Case** (e.g., training, road trip); default is training.
   - Click **"Generate AI Insights"** after weather is loaded.
   - The AI module builds a tailored prompt and calls OpenAI or Ollama; the response is parsed and displayed as a condition summary and an advisory for each selected city.

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

The app handles:

- **Missing API Key:** "API key not found. Add WEATHER_API_KEY to a .env file..." (use sample data to run without a key)
- **No Cities Selected:** "Please select at least one city." / "Select at least one city."
- **API rate limit / API errors:** Specific message from Weatherstack (e.g., usage limit reached); use **Use sample data (skip API)** to continue
- **AI report errors:** "Error: …" when AI key is missing or the AI call fails
- **Network issues:** Connection error messages

---

## 📁 Project Structure

```
app3/
├── app.py                    # Main Shiny app: UI (make_ui), server, reactive state, weather table + AI insights
├── weather_api.py            # Weatherstack: get_api_key(), fetch_weather(); returns DataFrame per city
├── ai_weather.py             # AI module: get_ai_insights(); builds prompt, calls OpenAI/Ollama, parses response
├── data_pipeline.py          # Standalone script: fetch → clean → write weather_for_ai.json/.csv/.txt (not used by app)
├── requirements.txt          # Dependencies (includes numpy)
├── requirements-shiny.txt    # Minimal dependencies (no numpy)
├── .env                      # WEATHER_API_KEY, optional OPENAI_API_KEY / OLLAMA_API_KEY (create locally)
├── README_Shiny_Weather.md   # This file
├── weather_for_ai.json       # Output of data_pipeline.py (optional)
├── weather_for_ai.csv        # Output of data_pipeline.py (optional)
└── weather_for_ai.txt        # Output of data_pipeline.py (optional)
```

**Entry point:** Run from the **app3** directory: `shiny run app.py`.

### File Descriptions

| File | Role |
|------|------|
| [`app.py`](app.py) | Main Shiny app. Defines the UI (`make_ui()`), server logic (fetch weather, generate AI insights), reactive state, and how the weather table and AI cards are rendered. |
| [`weather_api.py`](weather_api.py) | Weather data. Exposes `get_api_key()` and `fetch_weather(cities, units)`. Calls the Weatherstack API and returns a pandas DataFrame (one row per city) or an error. |
| [`ai_weather.py`](ai_weather.py) | AI report. Exposes `get_ai_insights(df, use_case)`. Turns the weather DataFrame and optional use-case text into a prompt, calls OpenAI or Ollama, and returns a dict with summary and advisories (or an error). |
| `.env` | Config (not in git). Holds `WEATHER_API_KEY` and optionally `OPENAI_API_KEY` and `OLLAMA_API_KEY`. Loaded by `weather_api` and `ai_weather`. |
| [`requirements.txt`](requirements.txt) | Full dependency list (shiny, pandas, requests, python-dotenv, numpy). Use: `pip install -r requirements.txt`. |
| `README_Shiny_Weather.md` | Project README: setup, API keys, run instructions, technical details, troubleshooting. |

---

## 📊 Data Summary

Table summarizing the columns in the API data returned by `fetch_weather()` (Weatherstack current weather API). One row per city. The app displays these with friendly headers: City, Temperature, Humidity (%), Wind (mph), Pressure (mb), Conditions.

| Column name (display) | Data type | Brief description |
|-----------------------|-----------|-------------------|
| City                  | string    | Location name as queried (e.g., "New York", "Los Angeles"). |
| Temperature           | float     | Current temperature in Fahrenheit °F (or in the units requested: metric °C or scientific Kelvin). |
| Humidity (%)          | int       | Relative humidity, percent (0–100). |
| Wind (mph)            | float     | Wind speed in miles per hour (or in the units requested: kilometers per hour). |
| Pressure (mb)         | int       | Atmospheric pressure in millibars. |
| Conditions            | string    | Short weather description (e.g., "Clear", "Partly cloudy", "Light rain"). |

---

## 🔧 Technical Details

Information needed to understand and run the software (aligned with Homework 1 documentation).

### API Key and Endpoint

- **API Key:** `WEATHER_API_KEY` (stored in `.env` in the app3 directory).
- **Endpoint:** `http://api.weatherstack.com/current` — retrieve real-time weather for specified locations.

Optional for AI: `OPENAI_API_KEY` or `OLLAMA_API_KEY` in `.env`. See [API Requirements → Optional: AI](#optional-ai-openai-or-ollama).

### Packages

| Package         | Version  | Purpose |
|-----------------|----------|---------|
| shiny           | ≥1.0.0   | Web framework: UI, server, reactivity. |
| pandas          | ≥2.0.0   | DataFrames for weather data and table rendering. |
| requests        | ≥2.28.0  | HTTP calls to Weatherstack, OpenAI, and Ollama. |
| python-dotenv   | ≥1.0.0   | Loads `.env` for API keys. |
| numpy           | &lt;2     | Numerical support (in `requirements.txt` only; omitted in `requirements-shiny.txt`). |

**Install dependencies:** `pip install -r requirements.txt`

### File Structure

| File | Role |
|------|------|
| app.py | Main Shiny app. Defines the UI (`make_ui()`), server logic (fetch weather, generate AI insights), reactive state, and how the weather table and AI cards are rendered. |
| weather_api.py | Weather data. Exposes `get_api_key()` and `fetch_weather(cities, units)`. Calls the Weatherstack API and returns a pandas DataFrame (one row per city) or an error. |
| ai_weather.py | AI report. Exposes `get_ai_insights(df, use_case)`. Turns the weather DataFrame and optional use-case text into a prompt, calls OpenAI or Ollama, and returns a dict with summary and advisories (or an error). |
| .env | Config (not in git). Holds `WEATHER_API_KEY` and optionally `OPENAI_API_KEY` and `OLLAMA_API_KEY`. Loaded by weather_api and ai_weather. |
| requirements.txt | Full dependency list. Use: `pip install -r requirements.txt`. |
| README_Shiny_Weather.md | Project README: setup, API keys, run instructions, technical details, troubleshooting. |

### Usage Instructions (quick reference)

- **Install dependencies:** `pip install -r requirements.txt`
- **Entry point:** Run from the **app3** directory with `shiny run app.py`
- **Request free API key:** [https://weatherstack.com/signup/free](https://weatherstack.com/signup/free)

### Architecture

- **Framework:** Shiny for Python (core version, not shiny.express). The app is written as a Shiny app using the library’s functions (e.g. `make_ui()`); the interface provides text boxes, radio buttons, sidebars, and action buttons.
- **UI Pattern:** Sidebar layout with main content area.
- **Reactivity Model:** Uses `reactive.value()` and `@reactive.effect` with `@reactive.event()` decorators.
- **Data Flow:** User input → **Get Weather** → `weather_api.py` queries Weatherstack API → return data rendered into table; **Generate AI Insights** → use case and weather data passed to AI module → tailored prompt → AI called (OpenAI/Ollama) → response parsed and rendered as AI report.

### Key Components

1. **UI (`make_ui()`):** Custom CSS dark theme; sidebar (city selector, units, use-case text, sample-data checkbox, Get Weather, Generate AI Insights); main area (status, weather table, AI report cards).
2. **Server (`server()`):** `_fetch_weather()` (calls `weather_api.fetch_weather`, updates `weather_result`); `_generate_ai()` (calls `ai_weather.get_ai_insights`, updates `ai_result`); `status_ui()`, `weather_table()`, `ai_insights_ui()` (render from reactive values).
3. **weather_api.py:** `get_api_key()`, `fetch_weather(cities, units)` → `(DataFrame, error)`.
4. **ai_weather.py:** `get_ai_insights(df, use_case)` → dict with summary, advisories, optional error.

### Rate Limiting

The app uses a 1-second delay between city requests in `weather_api.fetch_weather()` to respect Weatherstack API rate limits. When the free tier limit is reached, use **Use sample data (skip API)** to continue without live API calls.

---

## ⚠️ Troubleshooting

### Common Issues

**Issue:** "API key not found" error
- **Solution:** Ensure `.env` file exists in the **app3** directory with `WEATHER_API_KEY=your_key`, or use **Use sample data (skip API)** to run without the API

**Issue:** App won't start
- **Solution:** Verify all dependencies are installed: `pip install -r requirements.txt`

**Issue:** No data returned / API rate limit reached
- **Solution:** Check your API key is valid and you haven't exceeded rate limits. Use **Use sample data (skip API)** to continue with built-in sample data.

**Issue:** Port already in use
- **Solution:** Shiny will automatically try another port, or stop other Shiny apps running

---

## 📚 Additional Resources

- [Shiny for Python Documentation](https://shiny.posit.co/py/)
- [Weatherstack API Documentation](https://weatherstack.com/documentation)
- [Weatherstack free signup](https://weatherstack.com/signup/free)
- [Python-dotenv Documentation](https://pypi.org/project/python-dotenv/)

---

## 📄 License

This project is part of the SYSEN 5381 course materials.

---

**Last Updated:** February 2026
