from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import uuid
import os
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to RapidAPI domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create and serve output folder
os.makedirs("filtered", exist_ok=True)
app.mount("/filtered", StaticFiles(directory="filtered"), name="filtered")

# === Utility Functions ===

def get_transparent_circle_bounds(filter_path):
    filter_img = Image.open(filter_path).convert("RGBA")
    alpha = filter_img.split()[3]
    transparent_mask = alpha.point(lambda x: 255 if x == 0 else 0)
    return transparent_mask.getbbox()

def apply_filter_with_circle(uploaded_path, filter_path, output_path):
    uploaded_img = Image.open(uploaded_path).convert("RGBA")
    filter_img = Image.open(filter_path).convert("RGBA")

    circle_bounds = get_transparent_circle_bounds(filter_path)
    circle_width = circle_bounds[2] - circle_bounds[0]
    circle_height = circle_bounds[3] - circle_bounds[1]

    uploaded_resized = uploaded_img.resize((circle_width, circle_height))
    background = Image.new("RGBA", filter_img.size, (0, 0, 0, 0))
    background.paste(uploaded_resized, (circle_bounds[0], circle_bounds[1]))
    final_image = Image.alpha_composite(background, filter_img)
    final_image.save(output_path)

def delete_after_delay(path, delay=60):
    time.sleep(delay)
    if os.path.exists(path):
        os.remove(path)

# === Main API Endpoint ===

@app.post("/custom-filter")
async def custom_filter_api(
    background_tasks: BackgroundTasks,
    uploaded_file: UploadFile = File(...),
    filter_file: UploadFile = File(...)
):
    try:
        # Generate unique file names
        input_path = f"temp_input_{uuid.uuid4().hex[:8]}.png"
        filter_path = f"temp_filter_{uuid.uuid4().hex[:8]}.png"
        output_filename = f"filtered_{uuid.uuid4().hex[:8]}.png"
        output_path = os.path.join("filtered", output_filename)

        # Save uploaded files
        with open(input_path, "wb") as f:
            f.write(await uploaded_file.read())

        with open(filter_path, "wb") as f:
            f.write(await filter_file.read())

        # Process the image
        apply_filter_with_circle(input_path, filter_path, output_path)

        # Cleanup
        background_tasks.add_task(os.remove, input_path)
        background_tasks.add_task(os.remove, filter_path)
        background_tasks.add_task(delete_after_delay, output_path, 60)

        # Return filtered image URL (change to full domain in production)
        return JSONResponse({
            "success": True,
            "url": f"/filtered/{output_filename}"
        })

    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )
