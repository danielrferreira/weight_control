import streamlit.components.v1 as components
import os

_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "frontend")
log_form = components.declare_component("log_form", path=_COMPONENT_DIR)
