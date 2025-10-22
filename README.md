# 🎮 R6 Siege Match Dashboard

Real-time opponent analysis dashboard for Rainbow Six Siege competitive matches.

## 📖 About

Automatically scrape and display statistics for all 10 players in your Rainbow Six Siege match. Get instant insights about enemies' K/D, Win Rate, Rank, and favorite operators to gain a competitive advantage.

---

## ✨ Features

- ⚡ **Fast Setup**: 1-click auto-installer
- 📊 **Comprehensive Stats**: K/D, Win Rate, Rank, Top Operators
- 📱 **Mobile-Friendly**: Enter enemies from phone
- 🧠 **Smart Loading**: Only loads changed players
- 🚀 **2-Phase Loading**: Main stats in 20s, operators in 50s
- 💾 **Player Cache**: Instant loading for repeated matches

---

## 🛠️ Installation

### Windows (Recommended)

1. Clone repository:
```bashgit clone https://github.com/JuriCerretani/R6MatchStatsTracker.git
cd R6MatchStatsTracker

2. Run launcher:
```bashSTART_R6_TRACKER.bat

Done! Browser opens automatically.

### Manual (All Platforms)
```bashClone
git clone https://github.com/JuriCerretani/R6MatchStatsTracker.git
cd R6MatchStatsTracker
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txtRun
python app.py

---

## ⚙️ Configuration

Create `config.txt`:
```ini[main]
platform: psn
username: YourUsername[ally1]
platform: psn
username: Friend1[ally2]
platform: xbox
username: Friend2

**Platforms**: `psn`, `xbox`, `ubisoft`

---

## 🚀 Usage

1. **Start server** → `R6TRACKER.bat`
2. **Open on mobile** → `http://192.168.X.X:5000/`
3. **Enter 5 enemies** → Click SAVE
4. **View stats** → 20s for overview, 50s total
5. **Next match** → Change only new players (cached!)

---

## 📁 StructureR6-Siege-Dashboard/
├── START_R6_TRACKER.bat    # Launcher
├── app.py                   # Backend
├── config.txt               # Config
├── requirements.txt         # Dependencies
└── templates/
  └── index.html          # Frontend

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Python not found | Install from python.org, check "Add to PATH" |
| 404 Player Not Found | Check username spelling |
| Cloudflare blocked | Wait 30s and retry |
| Timeout errors | App limits to 3 browsers automatically |

---

## 📊 Performance

| Scenario | Time |
|----------|------|
| 10 players (first load) | ~50s |
| Change 2 enemies | ~18s |
| No changes | Instant |

---

## ⚠️ Disclaimer

Educational purposes only. Scrapes public data from R6 Tracker. Not affiliated with Ubisoft.

---

---

**Made with ❤️ for R6 Siege players**Claude non ha ancora la capacità di eseguire il codice che genera.Claude può commettere errori. Verifica sempre le risposte con attenzione. Sonnet 4.5
