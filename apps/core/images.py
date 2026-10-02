"""Compressione delle immagini caricate.

Le foto arrivano dai telefoni dei collaboratori: 3–5 MB l'una, spesso ruotate.
Prima di salvarle si raddrizzano (EXIF), si ridimensionano e si ricomprimono in
JPEG: una foto da 4 MB scende sotto i 300 KB restando leggibile a schermo.
Se la compressione non conviene (file già piccolo o formato non gestito) il file
originale resta intatto.
"""
from io import BytesIO

from django.core.files.base import ContentFile

MAX_LATO = 1600
QUALITA = 80
ESTENSIONI = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")


def comprimi_immagine(campo_file, max_lato=MAX_LATO, qualita=QUALITA):
    """Ridimensiona e ricomprime l'immagine sul posto.

    Restituisce una tupla ``(byte_prima, byte_dopo)`` oppure ``None`` se il file
    non è un'immagine gestibile o se comprimerlo non porta vantaggio.
    """
    nome = (getattr(campo_file, "name", "") or "").lower()
    if not nome.endswith(ESTENSIONI):
        return None

    try:
        from PIL import Image, ImageOps
    except ImportError:  # Pillow non installato: si tiene l'originale
        return None

    try:
        campo_file.seek(0)
        prima = campo_file.size
        with Image.open(campo_file) as immagine:
            immagine.load()
            immagine = ImageOps.exif_transpose(immagine)

            if max(immagine.size) > max_lato:
                immagine.thumbnail((max_lato, max_lato), Image.LANCZOS)

            # il JPEG non ha trasparenza: la si appiattisce su sfondo bianco
            if immagine.mode != "RGB":
                sfondo = Image.new("RGB", immagine.size, (255, 255, 255))
                if immagine.mode in ("RGBA", "LA", "P"):
                    con_alpha = immagine.convert("RGBA")
                    sfondo.paste(con_alpha, mask=con_alpha.split()[-1])
                else:
                    sfondo.paste(immagine.convert("RGB"))
                immagine = sfondo

            buffer = BytesIO()
            immagine.save(buffer, format="JPEG", quality=qualita, optimize=True, progressive=True)
        dati = buffer.getvalue()
    except Exception:
        # file corrotto o formato non supportato: si tiene l'originale
        return None

    if len(dati) >= prima:
        return None

    nuovo_nome = nome.rsplit("/", 1)[-1].rsplit(".", 1)[0] + ".jpg"
    campo_file.save(nuovo_nome, ContentFile(dati), save=False)
    return prima, len(dati)
