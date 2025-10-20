# R6 Siege Tracker Dashboard 🎮

A real-time web dashboard that scrapes player statistics from [R6 Tracker](https://r6.tracker.network) and displays them in a beautiful, interactive interface. Built with Python (Flask + Selenium) and vanilla JavaScript.

## ✨ Features

- **⚡ Ultra-Fast Parallel Scraping**: 20 simultaneous browser sessions (10 for overview + 10 for operators)
- **🎨 Modern UI**: Rainbow Six Siege themed design with smooth animations
- **📊 Comprehensive Stats**: 
  - Current Rank & RP
  - Season K/D, Win Rate, Matches
  - Best Rank achieved
  - Top 4 Most Played Operators (with detailed stats)
  - Last 4 Matches history
- **🎯 Smart Color Coding**: 
  - 🟢 Green for good performance (K/D ≥ 1, Win% ≥ 50%)
  - 🔴 Red for underperformance
- **🔄 Live Updates**: Edit players directly from the web interface without restarting
- **💾 Persistent Configuration**: Save your squad in `config.txt` for quick access
- **🌐 Multi-Platform Support**: PSN, Xbox, Ubisoft (PC)

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Google Chrome browser
- Internet connection

### Installation

1. **Clone the repository or Download ZIP file**
```bash
git clone https://github.com/JuriCerretani/R6MatchStatsTracker
```
then move to directory
```bash
cd R6MatchStatsTracker-main
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```
or
```bash
python -m pip install -r requirements.txt
```

3. **Create configuration file**

Create a `config.txt` file in the project root:
```ini
# Main player (required)
[main]
platform: psn
username: YourUsername

# Fixed allies (optional - up to 4)
[ally1]
platform: xbox
username: Friend1

[ally2]
platform: ubisoft
username: Friend2
```

Valid platforms: `psn`, `xbox`, `ubisoft`

4. **Run the application**
```bash
python app.py
```

5. **Access the dashboard**

The browser will automatically open at `http://127.0.0.1:5000/`

## 📖 Usage

### Terminal Configuration

When you start the application, you'll be prompted to:
1. Confirm or modify saved allies
2. Add enemy players for the current match

**Platform Selection:**
- Press `1` for PSN (PlayStation)
- Press `2` for Xbox
- Press `3` for Ubisoft (PC)

Press `ENTER` to skip any player slot.

### Web Interface

Once the dashboard loads:
1. **View Stats**: All player cards update automatically with scraped data
2. **Edit Players**: Click the "✏️ EDIT PLAYERS" button in the header
3. **Quick Update**: Modify allies/enemies and click "💾 SAVE & UPDATE DATA"
4. **Live Rescraping**: Data refreshes automatically without restarting Python

## 🏗️ Project Structure
```
r6-siege-tracker/
├── app.py                 # Main Flask application & scraping logic
├── config.txt             # User configuration (gitignored)
├── templates/
│   └── index.html        # Web dashboard frontend
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── .gitignore           # Git ignore rules
```

## 🛠️ Technical Details

### Backend (Python)
- **Flask**: Web server and API endpoints
- **Selenium**: Headless Chrome for dynamic content scraping
- **ThreadPoolExecutor**: Parallel processing for fast data collection
- **WebDriver Manager**: Automatic ChromeDriver management

### Frontend (JavaScript + HTML/CSS)
- **Vanilla JavaScript**: No frameworks, pure performance
- **Bootstrap 5**: Responsive grid system
- **Custom CSS**: R6 Siege themed styling
- **Fetch API**: Asynchronous data updates

### Scraping Strategy
1. **Parallel Sessions**: Opens 20 Chrome instances simultaneously
2. **Dual Page Scraping**: 
   - `/overview` page for general stats
   - `/operators` page for operator-specific data
3. **Cloudflare Bypass**: First requests bypass anti-bot protection
4. **Data Consolidation**: Merges overview + operators data per player

## 📊 Data Extracted

### Overview Page (`/overview`)
- Rank Points & Rank Badge
- Current Season Stats (K/D, Win Rate, Matches)
- Lifetime Stats (Level, Total Matches, Time Played)
- Best Rank (Season Peaks)
- Last 4 Matches (Result, Map, Score, K/D, KDA)

### Operators Page (`/operators`)
- Top 4 Most Played Operators
- Per-Operator Stats:
  - Rounds Played
  - K/D Ratio
  - Win Percentage
  - Headshot Percentage

## 🔧 Configuration Reference

### config.txt Format
```ini
# Comments start with #
# Valid platforms: psn, xbox, ubisoft

[main]
platform: psn
username: MainPlayer

[ally1]
platform: xbox
username: Friend1

[ally2]
platform: ubisoft
username: Friend2

[ally3]
platform: psn
username: Friend3

[ally4]
platform: xbox
username: Friend4
```

**Notes:**
- `[main]` section is **required**
- Ally sections (`[ally1]` - `[ally4]`) are **optional**
- Enemy players are always entered manually (they change each match)

## 🐛 Troubleshooting

### "Cloudflare blocked" error
- **Cause**: R6 Tracker is detecting automated traffic
- **Solution**: The app automatically bypasses this by using parallel sessions. If it persists, wait a few minutes between runs.

### "Profile not found" error
- **Cause**: Username doesn't exist or platform is incorrect
- **Solution**: Double-check username spelling and platform selection

### Chrome driver issues
- **Cause**: ChromeDriver version mismatch
- **Solution**: The app auto-updates drivers via `webdriver-manager`. Ensure Chrome browser is up to date.

### Slow scraping
- **Cause**: Too many players configured
- **Expected**: 10 players = ~30-40 seconds (parallel processing)
- **Tip**: Use fewer players for faster results

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This tool is for **educational purposes only**. It scrapes publicly available data from R6 Tracker. Please use responsibly and respect R6 Tracker's terms of service. The authors are not responsible for any misuse of this tool.

**Not affiliated with Ubisoft or R6 Tracker.**

## 🙏 Acknowledgments

- [R6 Tracker](https://r6.tracker.network) for providing the data
- [Ubisoft](https://www.ubisoft.com) for Rainbow Six Siege
- Flask, Selenium, and Bootstrap communities

---

Made with ❤️ for the R6 Siege community
