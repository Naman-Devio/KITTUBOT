# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
KITTUBOT Multimodal Media & Sticker Perception Processor
Extracts visual frames from Photos, WebP Stickers, Lottie Animations,
and WebM Video Stickers (via FFmpeg) for Vision AI comprehension.
"""

import os
import io
import base64
import tempfile
import asyncio
from dataclasses import dataclass
from PIL import Image
from telegram import Message, PhotoSize, Sticker
from KITTUBOT import log


@dataclass
class ProcessedMedia:
    base64_data_url: str
    media_type: str
    emoji: str
    caption: str


async def process_message_media(message: Message) -> ProcessedMedia | None:
    """
    Downloads and prepares photo or sticker media as a base64 JPEG data URL
    compatible with OpenAI/Groq/Gemini Vision APIs.
    """
    if not message:
        return None

    caption = message.caption or message.text or ""
    caption = caption.strip()

    # 1. Standard Photo
    if message.photo:
        try:
            # Pick the highest resolution photo
            photo: PhotoSize = message.photo[-1]
            tg_file = await photo.get_file()
            buf = bytearray()
            await tg_file.download_as_bytearray(buf)

            # Convert/verify with Pillow to ensure clean JPEG
            img = Image.open(io.BytesIO(buf))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(out_buf.getvalue()).decode("utf-8")

            return ProcessedMedia(
                base64_data_url=f"data:image/jpeg;base64,{b64_str}",
                media_type="photo",
                emoji="",
                caption=caption,
            )
        except Exception as e:
            log.warning(f"[MediaProcessor] Failed to process photo: {e}")
            return None

    # 2. Telegram Sticker
    if message.sticker:
        sticker: Sticker = message.sticker
        emoji = sticker.emoji or ""

        # A. Video Sticker (WebM)
        if sticker.is_video:
            try:
                tg_file = await sticker.get_file()
                with tempfile.TemporaryDirectory() as tmpdir:
                    in_webm = os.path.join(tmpdir, "sticker.webm")
                    out_jpg = os.path.join(tmpdir, "frame.jpg")

                    await tg_file.download_to_drive(custom_path=in_webm)

                    # Extract frame at 0.5s via FFmpeg
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", "00:00:00.5",
                        "-i", in_webm,
                        "-vframes", "1",
                        out_jpg,
                    ]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await proc.communicate()

                    # Fallback to start if 0.5s failed (very short sticker)
                    if not os.path.exists(out_jpg) or os.path.getsize(out_jpg) == 0:
                        cmd_fallback = [
                            "ffmpeg", "-y",
                            "-i", in_webm,
                            "-vframes", "1",
                            out_jpg,
                        ]
                        proc_fb = await asyncio.create_subprocess_exec(
                            *cmd_fallback,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await proc_fb.communicate()

                    if os.path.exists(out_jpg) and os.path.getsize(out_jpg) > 0:
                        with open(out_jpg, "rb") as f:
                            b64_str = base64.b64encode(f.read()).decode("utf-8")
                        return ProcessedMedia(
                            base64_data_url=f"data:image/jpeg;base64,{b64_str}",
                            media_type="sticker_video",
                            emoji=emoji,
                            caption=caption,
                        )
            except Exception as e:
                log.warning(f"[MediaProcessor] Video sticker ffmpeg failed: {e}")

        # B. Animated Sticker (TGS / Lottie)
        if sticker.is_animated:
            try:
                # Use sticker thumbnail if available
                if sticker.thumbnail:
                    tg_file = await sticker.thumbnail.get_file()
                    buf = bytearray()
                    await tg_file.download_as_bytearray(buf)
                    img = Image.open(io.BytesIO(buf))
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    out_buf = io.BytesIO()
                    img.save(out_buf, format="JPEG", quality=85)
                    b64_str = base64.b64encode(out_buf.getvalue()).decode("utf-8")
                    return ProcessedMedia(
                        base64_data_url=f"data:image/jpeg;base64,{b64_str}",
                        media_type="sticker_animated",
                        emoji=emoji,
                        caption=caption,
                    )
            except Exception as e:
                log.warning(f"[MediaProcessor] Animated sticker thumbnail failed: {e}")

        # C. Static Sticker (WebP)
        try:
            tg_file = await sticker.get_file()
            buf = bytearray()
            await tg_file.download_as_bytearray(buf)

            img = Image.open(io.BytesIO(buf))
            if img.mode in ("RGBA", "P"):
                # Composite over white background to avoid transparent black artifacts
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img)
                img = bg
            else:
                img = img.convert("RGB")

            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(out_buf.getvalue()).decode("utf-8")

            return ProcessedMedia(
                base64_data_url=f"data:image/jpeg;base64,{b64_str}",
                media_type="sticker_static",
                emoji=emoji,
                caption=caption,
            )
        except Exception as e:
            log.warning(f"[MediaProcessor] Static sticker processing failed: {e}")

    return None
