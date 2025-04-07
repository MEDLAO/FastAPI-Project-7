from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image
import uuid
import os
import time


app = FastAPI()


# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production: restrict to known origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure filtered directory exists
os.makedirs("filtered", exist_ok=True)


# === Helper functions ===
def get_transparent_bounds(filter_path):
    """Detect the bounding box of the transparent region in the filter image."""
    img = Image.open(filter_path).convert("RGBA")
    alpha = img.split()[3]  # Alpha channel
    mask = alpha.point(lambda x: 255 if x == 0 else 0)  # Make transparent fully white
    bbox = mask.getbbox()

    if not bbox:
        raise ValueError("No transparent area detected in the filter.")
    return bbox


def apply_filter(uploaded_path, filter_path, output_path):
    """Paste the uploaded image into the transparent part of the filter image."""
    uploaded_img = Image.open(uploaded_path).convert("RGBA")
    filter_img = Image.open(filter_path).convert("RGBA")

    # Get transparent area
    bbox = get_transparent_bounds(filter_path)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Resize user image to fit transparent hole
    resized_img = uploaded_img.resize((w, h))

    # Create transparent canvas and paste images
    canvas = Image.new("RGBA", filter_img.size, (0, 0, 0, 0))
    canvas.paste(resized_img, (bbox[0], bbox[1]))
    final = Image.alpha_composite(canvas, filter_img)

    # Save result
    final.save(output_path)


def delete_file_after_delay(path, delay=30):
    """Delete a file after a short delay."""
    time.sleep(delay)
    if os.path.exists(path):
        os.remove(path)


# === API Endpoint ===
@app.post("/custom-filter")
async def custom_filter(
    uploaded_image: UploadFile = File(...),
    uploaded_filter: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # Save files
    image_path = f"temp_{uuid.uuid4().hex}.png"
    filter_path = f"filter_{uuid.uuid4().hex}.png"
    output_path = f"filtered/filtered_{uuid.uuid4().hex[:8]}.png"

    with open(image_path, "wb") as f:
        f.write(await uploaded_image.read())

    with open(filter_path, "wb") as f:
        f.write(await uploaded_filter.read())

    try:
        apply_filter(image_path, filter_path, output_path)
    except ValueError as e:
        return {"error": str(e)}

    # Clean up temp files
    background_tasks.add_task(os.remove, image_path)
    background_tasks.add_task(os.remove, filter_path)
    background_tasks.add_task(delete_file_after_delay, output_path)

    # Return result
    return FileResponse(
        output_path,
        media_type="image/png",
        filename="filtered_image.png"
    )
