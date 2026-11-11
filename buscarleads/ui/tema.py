"""Tema escuro do app."""

CSS_TEMA = """
<style>
:root {
    color-scheme: dark;
}
.stApp {
    background: #111827;
    color: #F3F4F6;
}
[data-testid="stHeader"] {
    background: rgba(17, 24, 39, 0.92);
}
[data-testid="stSidebar"] {
    background: #17212f;
    border-right: 1px solid #374151;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.2rem;
}
h1, h2, h3 {
    color: #F3F4F6;
    letter-spacing: -0.025em;
}
h1 {
    font-size: 2rem !important;
}
h2 {
    font-size: 1.35rem !important;
}
h3 {
    font-size: 1.05rem !important;
}
p, label, [data-testid="stCaptionContainer"] {
    color: #D1D5DB;
}
[data-testid="stMetric"] {
    background: #1F2937;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 0.85rem 1rem;
}
[data-testid="stMetricValue"] {
    color: #F3F4F6;
}
[data-testid="stMetricLabel"] {
    color: #9CA3AF;
}
[data-testid="stExpander"] {
    border: 1px solid #374151;
    border-radius: 10px;
    background: #17212f;
}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div {
    background: #1F2937;
    border-color: #4B5563;
}
input, textarea {
    color: #F3F4F6 !important;
}
button[kind="primary"] {
    background: #059669;
    border-color: #059669;
}
button[kind="primary"]:hover {
    background: #047857;
    border-color: #047857;
}
button:focus-visible, a:focus-visible, input:focus-visible {
    outline: 2px solid #34D399 !important;
    outline-offset: 2px;
}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border: 1px solid #374151;
    border-radius: 10px;
}
hr {
    border-color: #374151;
}
</style>
"""
