#!/usr/bin/env python

import numpy as np
import plotly.io as pio
import plotly.graph_objects as go

from utils import json_helpers

pio.renderers.default = "browser"


def generate_heatmap():
    config = json_helpers.load_json_from_file('config/figures.json')
    print(config)

    current = np.array([
        [7, 7, 1],
        [1, 1, 1],
        [19, 28, 8]
    ])

    historical_avg = np.array([
        [2, 2, 1],
        [1, 1, 1],
        [5, 5, 1],
    ])

    # Percent difference
    pct_diff = (current - historical_avg) / historical_avg * 100

    # Text annotation (two lines)
    text = [
        [
            f"{current[i][j]}<br><span style='font-size:11px'>({pct_diff[i][j]:+.0f}%)</span>"
            for j in range(current.shape[1])
        ]
        for i in range(current.shape[0])
    ]

    fig = go.Figure(
        data=go.Heatmap(
            z=pct_diff,                     # color is driven by deviation
            x=config["error_types"],
            y=config["environments"],
            colorscale="RdYlGn_r",
            zmid=0,                         # center colors at 0%
            text=text,
            texttemplate="%{text}",
            textfont={"size": 14},
            hovertemplate=(
                "Service: %{y}<br>"
                "Error: %{x}<br>"
                "Count: %{customdata[0]}<br>"
                "Δ vs avg: %{z:.1f}%<extra></extra>"
            ),
            customdata=np.dstack((current, historical_avg))
        )
    )

    fig.update_layout(
        title="Error Counts vs Historical Baseline",
        xaxis_title="Error Type",
        yaxis_title="Service",
        margin=dict(l=80, r=40, t=60, b=40)
    )

    return fig

def generate_figures():
    heatmap = generate_heatmap()
    heatmap.show()

def main():
    generate_figures()

if __name__ == "__main__":
    main()