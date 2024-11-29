"""
FlashMCP Weather Server Example
"""

import os
import httpx
from pydantic import BaseModel, Field
from FlashMCP.server import FlashMCPServer

# Load env vars
API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    raise ValueError("OPENWEATHER_API_KEY environment variable required")

# API configuration
API_BASE = "http://api.openweathermap.org/data/2.5"
DEFAULT_PARAMS = {"appid": API_KEY, "units": "metric"}


# Pydantic models for parameters
class ForecastParams(BaseModel):
    city: str = Field(..., description="City name")
    days: int = Field(default=5, ge=1, le=10, description="Number of days to forecast")
    units: str = Field(
        default="metric", pattern="^(metric|imperial)$", description="Temperature units"
    )


class AlertParams(BaseModel):
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


# Create server
app = FlashMCPServer("weather-service")


# Tools using Pydantic models
@app.tool(description="Get detailed weather forecast for a city")
async def get_forecast(params: ForecastParams) -> dict:
    """Get a multi-day weather forecast for a city."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/forecast",
            params={
                "q": params.city,
                "cnt": params.days * 8,  # API returns 3-hour intervals
                "units": params.units,
                **DEFAULT_PARAMS,
            },
        )
        response.raise_for_status()
        data = response.json()

    # Process into daily forecasts
    forecasts = []
    for i in range(0, len(data["list"]), 8):  # Every 8th entry is a new day
        day_data = data["list"][i]
        forecasts.append(
            {
                "date": day_data["dt_txt"].split()[0],
                "temperature": {
                    "high": day_data["main"]["temp_max"],
                    "low": day_data["main"]["temp_min"],
                },
                "conditions": day_data["weather"][0]["description"],
                "humidity": day_data["main"]["humidity"],
                "wind_speed": day_data["wind"]["speed"],
            }
        )

    return {
        "city": data["city"]["name"],
        "country": data["city"]["country"],
        "forecasts": forecasts,
    }


# Tools using simple kwargs
@app.tool()
async def get_alerts(lat: float, lon: float) -> list:
    """Get weather alerts and warnings for a location."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/onecall",
            params={
                "lat": lat,
                "lon": lon,
                "exclude": "current,minutely,hourly,daily",
                **DEFAULT_PARAMS,
            },
        )
        response.raise_for_status()
        data = response.json()

    return data.get("alerts", [])


# Add HTTP resources
app.add_http_resource(
    f"{API_BASE}/weather?q=London&units=metric&appid={API_KEY}",
    name="London Weather",
    description="Current weather in London",
    mime_type="application/json",
)

# Add local data resources
app.add_file_resource("weather_stations/*.json", description="Weather station metadata")

app.add_dir_resource(
    "~/Developer/FlashMCP/historical_data",
    pattern="*.csv",
    recursive=True,
    description="Historical weather data",
)


def main():
    import asyncio
    import logging

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the server
    asyncio.run(FlashMCPServer.run_stdio(app))


if __name__ == "__main__":
    main()
