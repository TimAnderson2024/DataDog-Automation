#!/usr/bin/env python

import pandas as pd
import numpy as np
import plotly.io as pio
import plotly.graph_objects as go

from utils import json_helpers

pio.renderers.default = "browser"


def generate_heatmap_comparative(current: np.ndarray, historical_avg, log_scaled_deviation):
    config = json_helpers.load_json_from_file('config/figures.json')
    
    # Text annotation
    text = np.empty(current.shape, dtype=object)
    for i in range(current.shape[0]):
        for j in range(current.shape[1]):
            text[i, j] = (
                f"{current[i, j]}<br><span style='font-size:11px'>({historical_avg[i][j]}, {log_scaled_deviation[i, j]:+.2f})</span>"
            )

    fig = go.Figure(
        data=go.Heatmap(
            z=log_scaled_deviation,                     
            x=config["error_types"],
            y=config["environments"],
            colorscale="RdYlGn_r",
            zmid=0,                         
            text=text,
            texttemplate="%{text}",
            textfont={"size": 14},
            xgap=1,
            ygap=1,
        )
    )

    fig.update_layout(
        title="Error Counts vs Historical Baseline",
        xaxis_title="Error Type",
        yaxis_title="Service",
        margin=dict(l=80, r=40, t=60, b=40)
    )
    
    m = 1.0
    z_for_color = np.clip(log_scaled_deviation, -m, m)
    fig.update_traces(
        colorbar=dict(
            title="Deviation",
            tickformat="+.2f",
            dtick="outside",
        ),
        z=z_for_color,
        zmin=-m,
        zmax=m,
        zmid=0
    )
    
    return fig

def generate_heatmap_baseline(
    current: np.ndarray,
    historical_avg: np.ndarray,
    log_scaled_deviation: np.ndarray,
) -> go.Figure:
    """
    Heatmap where:
    - 0 is the expected value
    - 0 is shown explicitly and colored light green
    - Higher deviations increase color intensity
    """
    config = json_helpers.load_json_from_file("config/figures.json")

    current = np.asarray(current)
    historical_avg = np.asarray(historical_avg)
    log_scaled_deviation = np.asarray(log_scaled_deviation)

    if not (
        current.shape == historical_avg.shape == log_scaled_deviation.shape
    ):
        raise ValueError("All inputs must have the same shape")

    # Cell text: always show count, with baseline + deviation below
    text = np.empty(current.shape, dtype=object)
    for i in range(current.shape[0]):
        for j in range(current.shape[1]):
            text[i, j] = (
                f"{current[i, j]}"
                f"<br><span style='font-size:11px'>"
                f"({historical_avg[i, j]}, {log_scaled_deviation[i, j]:+.2f})"
                f"</span>"
            )

    customdata = np.dstack([current, historical_avg, log_scaled_deviation])

    fig = go.Figure(
        data=go.Heatmap(
            z=log_scaled_deviation,
            x=config["error_types"],
            y=config["environments"],
            zmin=0,
            colorscale=[
                [0.00, "#a1d99b"],  # was 0.45 → now 0 (expected)
                [0.36, "#fec44f"],  # (0.65 - 0.45) / (1.00 - 0.45)
                [0.73, "#fb6a4a"],  # (0.85 - 0.45) / (1.00 - 0.45)
                [1.00, "#cb181d"],  # same red endpoint
            ],
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=14),
            customdata=customdata,
            hovertemplate=(
                "Service: %{y}<br>"
                "Error Type: %{x}<br>"
                "Current: %{customdata[0]}<br>"
                "Baseline: %{customdata[1]}<br>"
                "Deviation: %{customdata[2]:+.2f}"
                "<extra></extra>"
            ),
            colorbar=dict(
                title="Deviation",
                tickformat="+.2f",
            ),
            xgap=1,
            ygap=1,
        )
    )

    fig.update_layout(
        title="Error Counts vs Historical Baseline",
        xaxis_title="Error Type",
        yaxis_title="Service",
        margin=dict(l=80, r=40, t=60, b=40),
        template="plotly_white",
        plot_bgcolor="white"
    )

    return fig

def main():
    pass

if __name__ == "__main__":
    main()