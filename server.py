import os
from datetime import datetime

import requests
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from mcp.server.fastmcp import FastMCP, Image
from dotenv import load_dotenv

mcp = FastMCP("Prometheus MCP")


def query_prometheus(endpoint, params):
    prometheus_url = os.environ.get("PROMETHEUS_URL")
    endpoint = f"{prometheus_url}{endpoint}"
    headers = {}

    if "GOOGLE_AUTH_JSON_FILE" in os.environ:
        key_path = os.environ.get('GOOGLE_AUTH_JSON_FILE')
        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        if credentials.expired or not credentials.valid:
            credentials.refresh(Request())
        access_token = credentials.token
        headers['Authorization'] = f"Bearer {access_token}"
    response = requests.get(endpoint, params=params, headers=headers)
    return response


@mcp.tool()
def prometheus_query_range(
    query: str, start_time: str, end_time: str, step: str
) -> int:
    """
    Query Prometheus /query_range API endpoint and return
    an image of a plot of the time series monitoring data.
    Use this tool whenever the user asks about the status
    of their compute infrastructure.
    """

    response = query_prometheus(
        "/api/v1/query_range",
        {
            "query": query,
            "start": start_time,
            "end": end_time,
            "step": step,
        },
    )

    if response.status_code != 200:
        return f"Query failed: {response.status_code} - {response.text}"
    data = response.json()
    if data["status"] != "success" or "result" not in data["data"]:
        return f"No data returned: {data}"
    plt.figure(figsize=(12, 6))
    # Process each timeseries in the result
    for series in data["data"]["result"]:
        # Extract metric information for the legend
        metric = series["metric"]
        if metric:
            if "__name__" in metric:
                name = metric["__name__"]
            else:
                # Create a label from metric labels
                name = ", ".join([f"{k}={v}" for k, v in metric.items()])
        else:
            name = "Unknown metric"

        # Convert timestamp to datetime
        times = [datetime.fromtimestamp(float(point[0])) for point in series["values"]]
        values = [float(point[1]) for point in series["values"]]

        # Plot the data
        plt.plot(times, values, label=name, marker=".")

    plt.grid(True, alpha=0.3)
    plt.title(query)
    plt.xlabel("Time")
    plt.gcf().autofmt_xdate()
    date_format = mdates.DateFormatter("%Y-%m-%d %H:%M:%S")
    plt.gca().xaxis.set_major_formatter(date_format)
    plt.legend(loc="best")
    plt.tight_layout()
    image_path = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3] + ".png"
    plt.savefig(image_path)

    return Image(path=image_path)


@mcp.tool()
def prometheus_alert_rules() -> dict[str, any]:
    """
    Query the Prometheus /rules API.
    Returns a list of alerting and recording rules that are currently loaded.
    In addition it returns the currently active alerts fired by the Prometheus
    instance of each alerting rule.
    """
    response = query_prometheus("/api/v1/rules", None)
    if response.status_code != 200:
        return f"Query failed: {response.status_code} - {response.text}"
    data = response.json()
    return data


if __name__ == "__main__":
    print("Initialize and run the Prometheus MCP server")
    load_dotenv()
    mcp.run(transport="stdio")
