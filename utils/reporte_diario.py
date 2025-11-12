# utils/reporte_diario.py
"""
Archivo seguro para generar Reporte Diario en PNG y debug de fechas.
Reemplazá completamente el archivo por este contenido.
"""

import io
from datetime import datetime
from typing import Tuple

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

from utils.date_utils import ahora_argentina, format_fecha


def _to_datetime_clean(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    s = s.replace({"": None, "nan": None, "NaN": None, "NONE": None, "None": None})
    out = pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
    if pd.api.types.is_datetime64tz_dtype(out):
        out = out.dt.tz_convert(None).dt.tz_localize(None)
    return out


def _prep_df(df_reclamos: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    df = df_reclamos.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in ("Fecha y hora", "Fecha_formateada", "Estado", "Técnico", "Tipo de reclamo"):
        if col not in df.columns:
            df[col] = pd.NA
    df["Fecha y hora"] = _to_datetime_clean(df["Fecha y hora"])
    df["Fecha_formateada"] = _to_datetime_clean(df["Fecha_formateada"])
    df["Estado"] = df["Estado"].astype(str).str.strip().str.lower()
    df["Técnico"] = df["Técnico"].fillna("Sin técnico").astype(str).str.strip()
    df["Tipo de reclamo"] = df["Tipo de reclamo"].fillna("Sin tipo").astype(str).str.strip()
    ahora_ts = pd.Timestamp(ahora_argentina()).tz_localize(None)
    hace_24h = ahora_ts - pd.Timedelta(hours=24)
    return df, ahora_ts, hace_24h


def generar_reporte_diario_imagen(df_reclamos: pd.DataFrame) -> io.BytesIO:
    df, ahora_ts, hace_24h = _prep_df(df_reclamos)
    mask_ing_24h = df["Fecha y hora"].notna() & (df["Fecha y hora"] >= hace_24h)
    total_ingresados_24h = int(mask_ing_24h.sum())
    mask_res_24h = (
        (df["Estado"] == "resuelto")
        & df["Fecha_formateada"].notna()
        & (df["Fecha_formateada"] >= hace_24h)
    )
    resueltos_24h = df.loc[mask_res_24h, ["Técnico", "Estado", "Fecha_formateada"]]
    tecnicos_resueltos = (
        resueltos_24h.groupby("Técnico")["Estado"]
        .count()
        .reset_index()
        .rename(columns={"Estado": "Cantidad"})
        .sort_values("Cantidad", ascending=False)
    )
    pendientes = df[df["Estado"] == "pendiente"]
    total_pendientes = int(len(pendientes))
    pendientes_tipo = (
        pendientes.groupby("Tipo de reclamo")["Estado"]
        .count()
        .reset_index()
        .rename(columns={"Estado": "Cantidad", "Tipo de reclamo": "Tipo"})
        .sort_values("Cantidad", ascending=False)
    )

    WIDTH, HEIGHT = 1200, 1600
    BG_COLOR = (39, 40, 34)
    TEXT_COLOR = (248, 248, 242)
    HIGHLIGHT_COLOR = (249, 38, 114)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
        font_sub = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
        font_txt = ImageFont.truetype("DejaVuSans.ttf", 24)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_txt = ImageFont.load_default()

    y = 50
    line_h = 40

    def _line(text, font, color, dy):
        nonlocal y
        draw.text((50, y), str(text), font=font, fill=color)
        y += dy

    fecha_str = ahora_ts.strftime("%d/%m/%Y")
    hora_str = ahora_ts.strftime("%H:%M")

    _line(f"■ Reporte Diario - {fecha_str}", font_title, HIGHLIGHT_COLOR, line_h)
    _line(f"Generado a las {hora_str}", font_sub, TEXT_COLOR, line_h)
    _line("", font_txt, TEXT_COLOR, line_h // 2)

    _line(f"■ Reclamos ingresados (24h): {total_ingresados_24h}", font_sub, HIGHLIGHT_COLOR, line_h)
    _line("", font_txt, TEXT_COLOR, line_h // 2)

    _line("■ Reporte técnico/grupo (24h):", font_sub, HIGHLIGHT_COLOR, line_h)
    if tecnicos_resueltos.empty:
        _line("No hay reclamos resueltos en las últimas 24h", font_txt, TEXT_COLOR, line_h)
    else:
        for _, r in tecnicos_resueltos.iterrows():
            _line(f"{r['Técnico']}: {int(r['Cantidad'])} resueltos (24h)", font_txt, TEXT_COLOR, line_h)

    _line("", font_txt, TEXT_COLOR, line_h // 2)
    _line(f"■ Quedan pendientes: {total_pendientes}", font_sub, HIGHLIGHT_COLOR, line_h)
    if pendientes_tipo.empty:
        _line("Sin pendientes", font_txt, TEXT_COLOR, line_h)
    else:
        for _, r in pendientes_tipo.iterrows():
            _line(f"{r['Tipo']}: {int(r['Cantidad'])}", font_txt, TEXT_COLOR, line_h)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
