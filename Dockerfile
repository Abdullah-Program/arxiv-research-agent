# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile  —  FastAPI Backend
#
# Ye file batata hai Docker ko:
#   "Is box mein kya andar daalna hai aur kaise chalana hai"
# ─────────────────────────────────────────────────────────────────────────────

# Step 1: Base image — Python 3.12 ka ek clean Linux environment
#   "slim" matlab minimum size, sirf zaruri cheezein
FROM python:3.12-slim

# Step 2: Ye environment variables set karo
#   PYTHONDONTWRITEBYTECODE = .pyc files mat banao (space bachao)
#   PYTHONUNBUFFERED = logs turant dikhao (buffering mat karo)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Step 3: Container ke andar /app folder banao aur wahan jao
WORKDIR /app

# Step 4: Pehle sirf requirements copy karo (layer caching trick)
#   Agar code change karo lekin requirements nahi, toh pip install dobara nahi chalega
COPY requirements.txt .

# Step 5: Dependencies install karo
#   --no-cache-dir = cache mat rakh (image size kam karo)
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Pura project copy karo container mein
COPY . .

# Step 7: Port 8000 expose karo (FastAPI yahan listen karega)
EXPOSE 8000

# Step 8: Container start hone par ye command chalao
#   host=0.0.0.0 = container ke bahar se bhi accessible ho
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
