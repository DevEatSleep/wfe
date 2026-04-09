# Deploy Your PWA to Render (Free & Simple)

**Time:** 5 minutes | **Cost:** $0 | **Difficulty:** ⭐ Easy

## **Step 1: Prepare Your GitHub Repository**

```bash
# From your project folder
cd wfe

# Initialize git if not already done
git init
git add .
git commit -m "Ready for Render deployment"

# Add your GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

> **Don't have GitHub?** Create free account at [github.com](https://github.com)

---

## **Step 2: Create Render Account**

1. Go to **[render.com](https://render.com)**
2. Click **"Sign Up"** 
3. Use GitHub credentials to sign in (recommended)
4. Authorize Render to access your GitHub

---

## **Step 3: Create New Web Service**

1. Dashboard → **"New +"** → **"Web Service"**
2. Connect your GitHub repository:
   - Click **"Connect Account"**
   - Select your repo: `wfe`
   - Click **"Connect"**

3. Configure deployment:

| Setting | Value |
|---------|-------|
| **Name** | `wfe` |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | `Free` |

4. Click **"Create Web Service"** ✨

---

## **Step 4: Create PostgreSQL Database**

1. Dashboard → **"New +"** → **"PostgreSQL"**
2. Fill in:
   - **Name:** `wfe`
   - **Database:** `wfe`
3. Click **"Create Database"**
4. Wait 2-3 minutes
5. **Copy the DATABASE_URL** from the database page

---

## **Step 5: Connect Database to Web Service**

1. Go to your Web Service (`wfe`)
2. Click **"Settings"**
3. Scroll to **"Environment"**
4. Add new variable:
   - **Key:** `DATABASE_URL`
   - **Value:** Paste the DATABASE_URL from your PostgreSQL
5. Click **"Save"**
6. Render auto-redeploys (~2 minutes)

---

## **Step 6: Wait for Deployment**

- Watch the logs scroll in real-time
- ✅ When you see **"Service is live"** → Done!

**Your app is now live at:** `https://wfe.onrender.com`

---

## **Step 7: Test Your PWA**

1. Open `https://wfe.onrender.com` in browser
2. Verify it works (may take ~48s on first load)
3. Install as PWA:
   - Click install icon (⬇️) in address bar
   - App appears on your home screen

---

## **Common Issues & Fixes**

### **"Build failed"**
```
❌ Error: ModuleNotFoundError
✅ Fix: Check requirements.txt has all dependencies
pip freeze > requirements.txt
git push origin main
```

### **"Service crashed"**
```
✅ Check logs: Dashboard → Your Service → Logs
✅ Common cause: SQLite database path
✅ Solution: Already using PostgreSQL (data persists!)
```

### **Slow startup (~48s)**
```
✅ Normal on free tier (service spins down after 15 min inactivity)
✅ Upgrade to paid tier for faster performance
```

### **Data lost after restart**
```
✅ Already solved! Using PostgreSQL (free tier persists data)
```

---

## **PostgreSQL Setup (Already Configured)**

Your app has been migrated to PostgreSQL! Here's how to use it:

### **Local Development**
```bash
# 1. Install PostgreSQL from postgresql.org
# 2. Create a new database
psql -U postgres -c "CREATE DATABASE wfe"

# 3. Create .env file with:
DATABASE_URL=postgresql://localhost/wfe

# 4. Install packages
pip install -r requirements.txt

# 5. Run your app
python app.py
```

### **Render Deployment**
```bash
# 1. Dashboard → New + → PostgreSQL
# 2. Name: "wfe", Database: "wfe" (free tier)
# 3. Wait for creation (2-3 minutes)
# 4. Copy the DATABASE_URL
# 5. Go to Web Service (wfe) → Settings → Environment Variables
# 6. Add: DATABASE_URL = (paste the copied URL)
# 7. Render auto-redeploys your service
```

**Your data will now persist forever!** ✨

---

## **Auto-Deploy from GitHub**

Every time you push to GitHub, Render auto-deploys:

```bash
# Make changes locally
nano app.py

# Commit and push
git add .
git commit -m "Add new feature"
git push origin main

# ✨ Render automatically deploys within 1 minute!
```

---

## **Monitor Your App**

**Render Dashboard:**
- **Logs** → See real-time activity
- **Metrics** → CPU, Memory, Network usage
- **Events** → Deployment history
- **Settings** → Configure environment

---

## **Upgrade to Paid (Optional)**

When you're ready for production:

| Feature | Free | Paid ($7/mo) |
|---------|------|-------------|
| **CPU** | 0.1 | Up to 16 |
| **RAM** | 512 MB | Up to 32 GB |
| **Startup** | 48s | Instant |
| **Disk** | Ephemeral | Persistent |
| **Uptime** | 99% | 99.95% |

**Upgrade:** Settings → Instance Type → Select Paid Tier

---

## **Your App Features on Render**

✅ **Automatic HTTPS** (PWA requirement)  
✅ **Auto-deploy from GitHub**  
✅ **512MB RAM** (enough for your app)  
✅ **Free tier forever**  
✅ **Custom domain** (optional, paid)  
✅ **Environment variables** (/static secrets management)

---

## **Support**

- **Render Docs:** [render.com/docs](https://render.com/docs)
- **Community Forum:** [render.com/community](https://render.com/community)
- **Email Support:** support@render.com

---

## **Next Steps**

1. ✅ Deploy your app
2. 📱 Install as PWA
3. 🎉 Share with beta testers
4. 📊 Monitor usage on Render dashboard
5. 🚀 Upgrade to paid when ready (optional)

**Happy deploying!** 🚀
