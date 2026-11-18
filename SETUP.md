# Setup Guide (MacBook + VS Code)

This is a friendly, step-by-step guide to run the **Face-Recognition Performance Lab**
on a Mac. No prior experience needed — just follow each step in order and copy–paste the
commands. It takes about 15–20 minutes, and most of that is waiting for things to install.

**What you'll end up with:** a small website running on your own laptop where you can
create test "participants", run a seeded demo, and look at charts of how a
face-verification system performs (FAR, FRR, EER). Nothing you do leaves your computer.

> Lines that look `like this` are commands. Copy the whole line, paste it into the
> Terminal (explained below), and press **Enter**. Wait for each one to finish before the
> next.

---

## Step 1 — Check you have Python (and install it if not)

The project needs **Python 3.11 or newer**.

1. Open the **Terminal** app on your Mac (press `Cmd + Space`, type "Terminal", hit Enter),
   or just use the Terminal inside VS Code in Step 4.
2. Type this and press Enter:

   ```
   python3 --version
   ```

3. If it prints `Python 3.11.something` or higher (e.g. 3.12), you're good — skip to Step 2.
   If it says a lower number or "command not found", download the latest Python from
   <https://www.python.org/downloads/macos/>, open the installer, and click through it.
   Then run `python3 --version` again to confirm.

---

## Step 2 — Get the project onto your computer

You need the code. The easiest way is with Git (Macs usually already have it).

1. In Terminal, go to where you want the project (your Desktop is fine):

   ```
   cd ~/Desktop
   ```

2. Download the project:

   ```
   git clone https://github.com/oyeshaurya/biometric-system.git
   ```

   > If it says `git: command not found`, a popup will offer to install the developer
   > tools — click **Install**, wait, then run the `git clone` line again.

3. Go into the project folder:

   ```
   cd biometric-system
   ```

---

## Step 3 — Open the project in VS Code

1. Open **VS Code**.
2. Menu: **File → Open Folder…**, then choose the `biometric-system` folder on your Desktop.
3. If VS Code suggests installing the **Python extension**, click **Install** — it makes
   life easier (optional but recommended).

---

## Step 4 — Open the Terminal inside VS Code

In VS Code, menu: **Terminal → New Terminal**. A command box opens at the bottom.
**Run all the remaining commands in this box** — it's already pointed at the project folder.

---

## Step 5 — Create a clean workspace for the project

This makes a private "virtual environment" so the project's pieces don't clash with
anything else on your Mac.

```
python3 -m venv .venv
```

```
source .venv/bin/activate
```

After the second command, your Terminal line should start with `(.venv)`. That means it
worked. **You'll need this active every time you run the app** (see "Running it again
later" at the bottom).

---

## Step 6 — Install the project

```
pip install -e ".[dev]"
```

This downloads everything the app needs. It can take a few minutes and print lots of
text — that's normal. Wait until the prompt comes back.

---

## Step 7 — One-time setup (key, database, login, demo data)

Run these four commands one at a time. Each prints a short confirmation.

1. Create the secret key that encrypts stored face data:

   ```
   python -m biometric_lab.scripts.make_key
   ```

2. Create the database:

   ```
   alembic upgrade head
   ```

3. Create your login (username **admin**, password **labpass123**):

   ```
   python -m biometric_lab.scripts.create_admin --username admin --password labpass123
   ```

4. Add a ready-made demo so the charts have data to show:

   ```
   python -m biometric_lab.scripts.make_synthetic_run
   ```

---

## Step 8 — Start the app

```
uvicorn biometric_lab.main:app --port 8000
```

When you see a line like `Uvicorn running on http://127.0.0.1:8000`, it's ready.
**Leave this Terminal running** — closing it stops the app.

---

## Step 9 — Open it and log in

1. Open your web browser (Safari or Chrome).
2. Go to: **http://127.0.0.1:8000**
3. Sign in with:
   - Username: **admin**
   - Password: **labpass123**

### What to try
- **Participants** tab: see the demo subjects (S001–S010).
- **Analysis** tab: pick the run **demo-run**, click **Compute**. You'll see FAR, FRR, GAR
  and an EER curve — this is the heart of the project.
- **Admin** tab: view settings and click **Verify chain** to confirm the tamper-proof
  activity log is intact.

> **About the camera:** the "Verify" and live "Enrolment" pages ask for your webcam. They
> only do real face matching if the optional real model is installed (see the last
> section). Without it, captures will say "no face" — that's expected. The Analysis side,
> which is the point of the project, works fully without a camera.

---

## Step 10 — Stop the app

Click the VS Code Terminal that's running the app and press **`Ctrl + C`** (hold Control,
press C). That shuts it down cleanly. To turn your workspace off too, type `deactivate`.

---

## Running it again later

You don't repeat the whole setup. Next time, just:

```
cd ~/Desktop/biometric-system
```

```
source .venv/bin/activate
```

```
uvicorn biometric_lab.main:app --port 8000
```

Then open **http://127.0.0.1:8000** again.

---

## If something goes wrong

- **`command not found: python`** → use `python3` instead, or make sure the Terminal line
  starts with `(.venv)` (re-run `source .venv/bin/activate`).
- **`pip` errors about "externally managed environment"** → you skipped the virtual
  environment. Re-do Step 5, then Step 6.
- **"Address already in use" when starting the app** → it's already running in another
  Terminal, or the port is busy. Use a different port: `uvicorn biometric_lab.main:app --port 8001`
  and open `http://127.0.0.1:8001`.
- **The page won't load** → make sure the Terminal from Step 8 is still running and shows
  no errors.
- **Login fails** → re-run the Step 7 command #3 to (re)create the admin account.

---

## Optional: turn on real face matching

By default the app uses a stand-in ("fake") engine so it runs anywhere with no big
downloads. To make the webcam pages do **real** face verification:

```
pip install -e ".[engine]"
```

Then start the app with the real engine turned on:

```
BIOMETRIC_LAB_ENGINE=insightface uvicorn biometric_lab.main:app --port 8000
```

The first run downloads a face model (a few hundred MB). Note: the face-model weights are
licensed for **non-commercial research use** — fine for a class project, not for selling.
See `docs/model_licences.md`.

---

## A few honest notes

- This is a **learning and measurement tool**, not a security product. The demo data is
  artificial, so its error rates are unrealistically perfect.
- Everything runs on `127.0.0.1` (your own laptop only). It makes no internet calls while
  running, and stored face templates are encrypted.
- Curious about the design? It's all written up in the [`docs/`](docs/) folder
  (requirements, architecture, system design).

Enjoy exploring it!
