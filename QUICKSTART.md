# 🚀 Quick Start Guide

## Option 1: Automatic Setup (Easiest)

### On Mac/Linux:
```bash
./start.sh
```

### On Windows:
```cmd
start.bat
```

This will automatically:
- Install all dependencies
- Start both backend and frontend servers
- Open in your browser

---

## Option 2: Manual Setup

### Step 1: Install Backend
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Install Frontend
```bash
cd frontend
npm install
```

### Step 3: Start Backend (Terminal 1)
```bash
cd backend
python main.py
```
✅ Backend running on http://localhost:5002

### Step 4: Start Frontend (Terminal 2)
```bash
cd frontend
npm run dev
```
✅ Frontend running on http://localhost:3100

---

## 🎯 Using the App

1. **Open** http://localhost:3000 in your browser
2. **Paste** a YouTube channel URL
   - Example: `https://www.youtube.com/@MrBeast`
   - Example: `https://www.youtube.com/c/veritasium`
3. **Set** how many videos (default: 20)
4. **Click** "Start Extraction"
5. **Wait** for the progress to complete
6. **Download** the viral_dna.txt file
7. **Upload** to NotebookLM for analysis

---

## 💡 Pro Tips

- Start with 10-20 videos for faster results
- The script automatically gets the MOST POPULAR videos
- Some videos may not have transcripts (will be skipped)
- Processing takes ~1-2 seconds per video
- The output file is saved in the backend folder

---

## ❓ Common Issues

**"Module not found" error:**
```bash
cd backend
pip install -r requirements.txt
```

**"Port already in use":**
- Backend: Kill process on port 5000
- Frontend: Kill process on port 3000

**"No transcripts found":**
- Some videos don't have captions
- Try a different channel
- Increase the video limit

---

## 🎉 You're Ready!

The app should now be running. Enjoy extracting viral DNA!
