import os
import shutil
import subprocess
import tempfile
import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from ansi2html import Ansi2HTMLConverter

app = FastAPI(title="Oikonomia DriftLint Web Portal")

templates = Jinja2Templates(directory="templates")
ansi_converter = Ansi2HTMLConverter(dark_bg=True, inline=True)

def convert_csv_to_npy(csv_path, npy_path):
    """Parses a standard multi-row comma-separated matrix into an audit-ready binary array."""
    data = np.genfromtxt(csv_path, delimiter=',')
    if len(data.shape) == 2 and data.shape[0] > 2 and data.shape[1] == 2:
        data = data.T
    np.save(npy_path, data)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "output": None})

@app.post("/scan", response_class=HTMLResponse)
async def scan_matrix(
    request: Request,
    mode: str = Form(...),
    file: UploadFile = File(...)
):
    with tempfile.TemporaryDirectory() as tmpdir:
        input_filename = file.filename
        uploaded_path = os.path.join(tmpdir, input_filename)
        target_npy_path = os.path.join(tmpdir, "target_matrix.npy")

        with open(uploaded_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            if input_filename.lower().endswith('.csv'):
                convert_csv_to_npy(uploaded_path, target_npy_path)
            else:
                shutil.move(uploaded_path, target_npy_path)

            # CLOUD OPTIMIZATION: Call main.py directly via the native Python environment
            cmd = [
                "python", "main.py",
                "--target", target_npy_path,
                "--mode", mode
            ]

            # Execute the script and capture the UTF-8 ANSI stream
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
            raw_output = result.stdout

        except subprocess.CalledProcessError as e:
            raw_output = f"ENGINE EXECUTION ERROR:\n{e.stderr if e.stderr else e.stdout}"
        except Exception as e:
            raw_output = f"INGESTION FAILURE: {str(e)}\nVerify your layout contains uniform numerical dimensions."

        html_output = ansi_converter.convert(raw_output, full=False)

        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "output": html_output, "mode": mode, "filename": input_filename}
        )

if __name__ == "__main__":
    import uvicorn
    # Configure port to use Render's dynamic environment routing variable
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)