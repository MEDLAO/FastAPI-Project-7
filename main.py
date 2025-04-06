from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image
import uuid
import os
import time


app = FastAPI()


# Allow all origins for testing (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create filtered directory if it doesn't exist
os.makedirs("filtered", exist_ok=True)


def get_transparent_bounds(image_path: str):
    """Detect the transparent region in an RGBA image."""
    img = Image.open(image_path).convert("RGBA")
    alpha = img.split()[3]  # Alpha channel
    mask = alpha.point(lambda x: 255 if x == 0 else 0)
    bbox = mask.getbbox()
    if not bbox:
        raise ValueError("No transparent area detected in the filter.")
    return bbox


def apply_filter(uploaded_path: str, filter_path: str, output_path: str):
    """Apply uploaded filter with transparent region to uploaded image."""
    base_img = Image.open(uploaded_path).convert("RGBA")
    filter_img = Image.open(filter_path).convert("RGBA")

    bounds = get_transparent_bounds(filter_path)
    w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    resized = base_img.resize((w, h))

    canvas = Image.new("RGBA", filter_img.size, (0, 0, 0, 0))
    canvas.paste(resized, (bounds[0], bounds[1]))
    result = Image.alpha_composite(canvas, filter_img)
    result.save(output_path)


def delete_file_after_delay(path: str, delay: int = 30):
    time.sleep(delay)
    if os.path.exists(path):
        os.remove(path)


@app.post("/custom-filter")
async def custom_filter(
    uploaded_image: UploadFile = File(...),
    uploaded_filter: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # Save uploaded files
    input_path = f"temp_{uuid.uuid4().hex}.png"
    filter_path = f"filter_{uuid.uuid4().hex}.png"
    output_path = f"filtered/result_{uuid.uuid4().hex[:8]}.png"

    with open(input_path, "wb") as f:
        f.write(await uploaded_image.read())
    with open(filter_path, "wb") as f:
        f.write(await uploaded_filter.read())

    try:
        apply_filter(input_path, filter_path, output_path)
    except ValueError as e:
        return {"error": str(e)}

    # Clean up temp files
    background_tasks.add_task(os.remove, input_path)
    background_tasks.add_task(os.remove, filter_path)
    background_tasks.add_task(delete_file_after_delay, output_path)

    return FileResponse(
        output_path,
        media_type="image/png",
        filename="filtered_image.png"
    )
