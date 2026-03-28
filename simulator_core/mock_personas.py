"""Mock persona configurations for demo and testing. Use with POST /api/sim/devices."""

from __future__ import annotations

MOCK_PERSONAS: list[dict] = [
    {"label": "young_healthy", "name": "Young Healthy (25F)", "age": 25, "weight_kg": 58.0,  "height_cm": 165.0, "seed": 11},
    {"label": "middle_aged",   "name": "Middle-Aged (50M)",   "age": 50, "weight_kg": 80.0,  "height_cm": 175.0, "seed": 22},
    {"label": "elderly",       "name": "Elderly (72M)",       "age": 72, "weight_kg": 68.0,  "height_cm": 168.0, "seed": 33},
    {"label": "obese",         "name": "Obese (45M)",         "age": 45, "weight_kg": 105.0, "height_cm": 170.0, "seed": 44},
    {"label": "underweight",   "name": "Underweight (22F)",   "age": 22, "weight_kg": 46.0,  "height_cm": 165.0, "seed": 55},
]
