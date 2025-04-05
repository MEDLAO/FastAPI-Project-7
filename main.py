from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import uuid
import os
import time

app = FastAPI()

# Allow all origins (adjust for production if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure filtered folder exists
os.makedirs("filtered", exist_ok=True)


# === Helper Functions ===

# Get the bounding box of the transparent area in the filter image
def get_transparent_bounds(filter_path):
    filter_img = Image.open(filter_path).convert("RGBA")
    alpha = filter_img.split()[3]  # Alpha channel
    transparent_mask = alpha.point(lambda x: 255 if x == 0 else 0)
    return transparent_mask.getbbox()  # Returns (left, upper, right, lower)


# Apply the uploaded image into the transparent part of the filter
def apply_filter_with_transparency(uploaded_path, filter_path, output_path):
    uploaded_img = Image.open(uploaded_path).convert("RGBA")
    filter_img = Image.open(filter_path).convert("RGBA")

    bounds = get_transparent_bounds(filter_path)
    if not bounds:
        raise ValueError("No transparent area detected in the filter.")

    left, upper, right, lower = bounds
    width, height = right - left, lower - upper

    uploaded_resized = uploaded_img.resize((width, height))
    canvas = Image.new("RGBA", filter_img.size, (0, 0, 0, 0))
    canvas.paste(uploaded_resized, (left, upper))
    final = Image.alpha_composite(canvas, filter_img)
    final.save(output_path)


# Delete a file after a delay (in seconds)
def delete_after_delay(path, delay=60):
    time.sleep(delay)
    if os.path.exists(path):
        os.remove(path)


# === Endpoint ===

# Apply a custom uploaded filter with a transparent area
@app.post("/apply-custom-filter")
async def apply_custom_filter(
    uploaded_file: UploadFile = File(...),
    filter_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # Generate unique filenames
    input_path = f"temp_{uuid.uuid4().hex}.png"
    filter_path = f"filter_{uuid.uuid4().hex}.png"
    output_filename = f"filtered_image_{uuid.uuid4().hex[:8]}.png"
    output_path = os.path.join("filtered", output_filename)

    # Save uploaded files to disk
    with open(input_path, "wb") as f:
        f.write(await uploaded_file.read())

    with open(filter_path, "wb") as f:
        f.write(await filter_file.read())

    # Apply the filter to the uploaded image
    try:
        apply_filter_with_transparency(input_path, filter_path, output_path)
    except Exception as e:
        return {"error": str(e)}

    # Schedule file cleanup
    background_tasks.add_task(os.remove, input_path)
    background_tasks.add_task(os.remove, filter_path)
    background_tasks.add_task(delete_after_delay, output_path, 30)

    # Return the final image
    return FileResponse(
        output_path,
        media_type="image/png",
        filename="filtered_image.png"
    )
