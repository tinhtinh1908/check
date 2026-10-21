"""Design tokens, theme builders and responsive breakpoints.

Components reference Material ``ColorScheme`` roles (``ft.Colors.SURFACE``…), so switching
``page.theme_mode`` re-themes the whole UI instantly without rebuilding controls. Status colours,
gradients and the console palette are fixed values readable on both themes.
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

# -- typography (one family per weight: Flet maps a family name to a single font file) ---------------
FONTS = {
    "BVP": "fonts/BeVietnamPro-Regular.ttf",
    "BVP Medium": "fonts/BeVietnamPro-Medium.ttf",
    "BVP SemiBold": "fonts/BeVietnamPro-SemiBold.ttf",
    "BVP Bold": "fonts/BeVietnamPro-Bold.ttf",
    "BVP ExtraBold": "fonts/BeVietnamPro-ExtraBold.ttf",
    "JBM": "fonts/JetBrainsMono-Regular.ttf",
    "JBM SemiBold": "fonts/JetBrainsMono-SemiBold.ttf",
}
FONT = "BVP"
FONT_MEDIUM = "BVP Medium"
FONT_SEMIBOLD = "BVP SemiBold"
FONT_BOLD = "BVP Bold"
FONT_EXTRABOLD = "BVP ExtraBold"
MONO = "JBM"
MONO_BOLD = "JBM SemiBold"
FALLBACK = ["Segoe UI", "Arial"]

# -- fixed colours ------------------------------------------------------------------------------------
ACCENT = "#EE3B2E"
ACCENT_2 = "#FF6A3D"
SUCCESS = "#22C55E"
WARNING = "#F5A524"
DANGER = "#EF4444"
INFO = "#3B82F6"
CMD = "#22D3EE"
CLOSE_HOVER = "#E81123"
WHITE = "#FFFFFF"

CONSOLE_BG = "#07080B"
CONSOLE_HEADER = "#0C0E13"
CONSOLE_BORDER = "#1C1F27"
CONSOLE_TEXT = "#D7DBE2"
CONSOLE_DIM = "#6B7383"
CONSOLE_TIME = "#4B5263"

# -- theme roles ----------------------------------------------------------------------------------------
BG = ft.Colors.SURFACE
CARD = ft.Colors.SURFACE_CONTAINER_LOW
CARD_HOVER = ft.Colors.SURFACE_CONTAINER
CARD_ACTIVE = ft.Colors.SURFACE_CONTAINER_HIGH
CARD_DEEP = ft.Colors.SURFACE_CONTAINER_HIGHEST
BORDER = ft.Colors.OUTLINE_VARIANT
TEXT = ft.Colors.ON_SURFACE
TEXT_MUTED = ft.Colors.ON_SURFACE_VARIANT
PRIMARY = ft.Colors.PRIMARY

RADIUS_SM = 8
RADIUS = 12
RADIUS_LG = 16
DURATION_FAST = 140
DURATION = 220
EASE = ft.AnimationCurve.EASE_OUT_CUBIC

_DARK = {
    "primary": ACCENT,
    "on_primary": WHITE,
    "primary_container": "#3A1512",
    "on_primary_container": "#FFD9D5",
    "secondary": ACCENT_2,
    "on_secondary": WHITE,
    "error": DANGER,
    "on_error": WHITE,
    "surface": "#0B0C10",
    "on_surface": "#ECEEF2",
    "on_surface_variant": "#A2A9B6",
    "outline": "#353B4A",
    "outline_variant": "#262A35",
    "surface_container_lowest": "#08090C",
    "surface_container_low": "#13151B",
    "surface_container": "#1A1D25",
    "surface_container_high": "#222631",
    "surface_container_highest": "#2B303C",
    "inverse_surface": "#ECEEF2",
    "on_inverse_surface": "#13151B",
    "shadow": "#000000",
    "scrim": "#000000",
    "surface_tint": "#0B0C10",
}
_LIGHT = {
    "primary": "#E3342A",
    "on_primary": WHITE,
    "primary_container": "#FFE4E1",
    "on_primary_container": "#5A0F0A",
    "secondary": ACCENT_2,
    "on_secondary": WHITE,
    "error": "#DC2626",
    "on_error": WHITE,
    "surface": "#F3F4F7",
    "on_surface": "#12141A",
    "on_surface_variant": "#545C6B",
    "outline": "#CDD2DC",
    "outline_variant": "#E3E6EC",
    "surface_container_lowest": "#FFFFFF",
    "surface_container_low": "#FFFFFF",
    "surface_container": "#F6F7F9",
    "surface_container_high": "#EEF0F4",
    "surface_container_highest": "#E5E8EE",
    "inverse_surface": "#1A1D25",
    "on_inverse_surface": "#ECEEF2",
    "shadow": "#101828",
    "scrim": "#000000",
    "surface_tint": "#FFFFFF",
}


def soft(color: str, opacity: float = 0.14) -> str:
    """Translucent version of a colour (works with theme role names too)."""
    return ft.Colors.with_opacity(opacity, color)


def build_theme(dark: bool) -> ft.Theme:
    return ft.Theme(
        color_scheme=ft.ColorScheme(**(_DARK if dark else _LIGHT)),
        font_family=FONT,
        visual_density=ft.VisualDensity.COMPACT,
        scrollbar_theme=ft.ScrollbarTheme(
            thickness=6, radius=6, thumb_color=soft(TEXT_MUTED, 0.35), track_visibility=False
        ),
        tooltip_theme=ft.TooltipTheme(
            text_style=ft.TextStyle(size=12, color=WHITE, font_family=FONT_MEDIUM),
            decoration=ft.BoxDecoration(bgcolor="#1F2330", border_radius=RADIUS_SM),
        ),
    )


def shadow(strength: float = 1.0) -> ft.BoxShadow:
    return ft.BoxShadow(
        blur_radius=24 * strength, spread_radius=-6, color=soft("#000000", 0.28), offset=ft.Offset(0, 8 * strength)
    )


def glow(color: str = ACCENT, opacity: float = 0.35) -> ft.BoxShadow:
    return ft.BoxShadow(blur_radius=22, spread_radius=-4, color=soft(color, opacity), offset=ft.Offset(0, 6))


ACCENT_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT, colors=[ACCENT, ACCENT_2]
)
DANGER_GRADIENT = ft.LinearGradient(
    begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT, colors=["#B91C1C", DANGER]
)


# -- responsive layout ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class Layout:
    width: float
    height: float
    sidebar: int  # sidebar width
    gap: int  # gap between cards and outer padding
    density: str  # profile cards: "full" | "compact" | "chip"
    short: bool  # short window: compact progress panel / title bar
    console_size: float

    @property
    def main_width(self) -> float:
        return self.width - self.sidebar - 3 * self.gap


def compute_layout(width: float, height: float) -> Layout:
    if width >= 1600:
        sidebar, gap = 340, 16
    elif width >= 1280:
        sidebar, gap = 316, 16
    elif width >= 1024:
        sidebar, gap = 288, 14
    else:
        sidebar, gap = 260, 12
    short = height < 700
    main = width - sidebar - 3 * gap
    # five cards in one row need ~170 px each to show name + counts; narrower windows use chips (3 + 2)
    if main >= 900:
        density = "full" if height >= 760 else "compact"
    else:
        density = "chip"
    return Layout(width, height, sidebar, gap, density, short, 13.0 if width >= 1600 else 12.5)
