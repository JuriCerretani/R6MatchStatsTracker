"""
R6 Siege Tracker - Web Scraper & Dashboard
=============================================
A Flask-based web application that scrapes player statistics from R6 Tracker
and displays them in a real-time dashboard with parallel processing.

Author: Your Name
License: MIT
"""

import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from flask import Flask, jsonify, render_template, request
from threading import Timer
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def read_parameters(file_name):
    """
    Reads the configuration file with sections [main], [ally1], [ally2], etc.
    Returns a dictionary with the sections found.
    """
    if not os.path.exists(file_name):
        print(f"Error: Configuration file '{file_name}' not found.")
        return None

    config = {
        'main': None,
        'allies': []
    }
    
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_section = None
        current_data = {}
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            if not line or line.startswith('#'):
                continue
            
            if line.startswith('[') and line.endswith(']'):
                if current_section and 'platform' in current_data and 'username' in current_data:
                    if current_section == 'main':
                        config['main'] = current_data.copy()
                    elif current_section.startswith('ally'):
                        config['allies'].append(current_data.copy())
                
                current_section = line[1:-1].strip().lower()
                current_data = {}
                continue
            
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    value = parts[1].strip()
                    current_data[key] = value
        
        if current_section and 'platform' in current_data and 'username' in current_data:
            if current_section == 'main':
                config['main'] = current_data.copy()
            elif current_section.startswith('ally'):
                config['allies'].append(current_data.copy())
        
        if not config['main']:
            print("Error: [main] section not found or incomplete in config.txt")
            return None
        
        if config['main']['platform'].lower() not in ['psn', 'xbox', 'ubisoft']:
            print(f"Error: Platform '{config['main']['platform']}' not valid for [main]")
            print("Valid platforms: psn, xbox, ubisoft")
            return None
        
        return config
        
    except Exception as e:
        print(f"Error reading file: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_config(file_name, players_config):
    """
    Saves the current configuration to the config.txt file
    """
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write("[main]\n")
            f.write(f"platform: {players_config['main']['platform']}\n")
            f.write(f"username: {players_config['main']['username']}\n")
            f.write("\n")
            
            for idx, ally in enumerate(players_config['allies'], 1):
                f.write(f"[ally{idx}]\n")
                f.write(f"platform: {ally['platform']}\n")
                f.write(f"username: {ally['username']}\n")
                f.write("\n")
        
        print(f"✓ Configuration saved to {file_name}")
        return True
    except Exception as e:
        print(f"⚠ Error saving configuration: {e}")
        return False


def build_url(parameters):
    """
    Constructs the full R6 Tracker URL with proper platform mapping.
    Platform mapping: psn → psn, xbox → xbl, ubisoft → ubi
    """
    platform = parameters['platform'].lower()
    username = parameters['username']
    
    platform_map = {
        'psn': 'psn',
        'xbox': 'xbl',
        'ubisoft': 'ubi'
    }
    
    if platform not in platform_map:
        print(f"Error: Platform '{platform}' not valid. Use: psn, xbox, or ubisoft.")
        return None
    
    url_platform = platform_map[platform]
    
    base_url = "https://r6.tracker.network/r6siege/profile/{platform}/{username}/overview"
    final_url = base_url.format(platform=url_platform, username=username)
    final_url += "?lang=en"
    return final_url


# ============================================================================
# HELPER FUNCTIONS FOR DATA EXTRACTION
# ============================================================================

def find_stat_value(driver, base_selector, stat_name):
    """
    Finds a specific stat value within a context element.
    """
    try:
        if isinstance(base_selector, str) and (base_selector.strip().startswith('/') or 
                                                base_selector.strip().startswith('.//') or 
                                                base_selector.strip().startswith('//')):
            context = driver.find_element(By.XPATH, base_selector)
        else:
            context = driver.find_element(By.CSS_SELECTOR, base_selector)
    except Exception:
        return "N/A"

    try:
        try:
            label_elem = context.find_element(By.XPATH, f".//*[contains(normalize-space(string(.)), '{stat_name}')]")
        except Exception:
            label_elem = driver.find_element(By.XPATH, f"//*[contains(normalize-space(string(.)), '{stat_name}')]")

        parent = label_elem.find_element(By.XPATH, "./ancestor::div[1]")

        try:
            value_elem = parent.find_element(By.XPATH, ".//div[contains(@class,'stat-value') or contains(@class,'value') or contains(@class,'text-') or .//span[contains(@class,'stat-value')]]")
            val = value_elem.text.strip()
            return val if val else "N/A"
        except Exception:
            full = parent.text.strip().replace(label_elem.text.strip(), '').strip()
            return full if full else "N/A"
    except Exception:
        return "N/A"


def extract_section_stats(driver, section_keyword):
    """
    Searches for a section based on header title and returns stats.
    """
    section_keyword = section_keyword.lower()
    stats = {}

    blocks = driver.find_elements(By.CSS_SELECTOR, 
                                  "div.stat-group, div.stat-card, div.name-value, div.tracker-card, div.trn-card__content")
    
    for block in blocks:
        try:
            try:
                title_elem = block.find_element(By.XPATH, "preceding::h2[1]")
            except Exception:
                try:
                    title_elem = block.find_element(By.XPATH, "preceding::h3[1]")
                except Exception:
                    title_elem = None

            title_text = title_elem.text.strip().lower() if title_elem is not None else ""
            if section_keyword in title_text:
                stats = extract_stats_from_context(driver, block)
                if stats:
                    return stats
        except Exception:
            continue

    try:
        header = driver.find_element(By.XPATH, 
                                     f"//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{section_keyword}')] | "
                                     f"//h3[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{section_keyword}')]")
        block_after = header.find_element(By.XPATH, "following-sibling::div[1]")
        stats = extract_stats_from_context(driver, block_after)
    except Exception:
        pass

    return stats


def extract_stats_from_context(driver, context=None):
    """
    Returns a dict {stat_name: stat_value} by searching stat blocks.
    """
    stats = {}
    try:
        if context is None:
            ctx_elem = driver
        elif isinstance(context, str):
            try:
                ctx_elem = driver.find_element(By.XPATH, context)
            except Exception:
                try:
                    ctx_elem = driver.find_element(By.CSS_SELECTOR, context)
                except Exception:
                    ctx_elem = driver
        else:
            ctx_elem = context

        blocks = ctx_elem.find_elements(By.XPATH, 
                                       ".//div[contains(@class,'text-center') or contains(@class,'name-value')]")
        if not blocks:
            blocks = ctx_elem.find_elements(By.XPATH, 
                                           ".//div[.//div[contains(@class,'stat-label')] and .//div[contains(@class,'stat-value')]]")

        for b in blocks:
            try:
                try:
                    label_elem = b.find_element(By.XPATH, 
                                               ".//div[contains(@class,'stat-label')] | .//span[contains(@class,'stat-name')]")
                    label = label_elem.text.strip()
                except Exception:
                    label = ""

                if not label:
                    continue

                try:
                    val_elem = b.find_element(By.XPATH, 
                                             ".//div[contains(@class,'stat-value')] | .//span[contains(@class,'stat-value')]")
                    value = val_elem.text.strip()
                except Exception:
                    value = ""

                if not value:
                    text_all = b.text.strip().replace(label, '').strip()
                    value = text_all if text_all else "N/A"

                parts = [p.strip() for p in value.split('/') if p.strip()]
                parts = list(dict.fromkeys(parts))
                clean_value = ' / '.join(parts)

                stats[label] = clean_value
            except Exception:
                continue

    except Exception as e:
        print(f"[DEBUG] extract_stats_from_context error: {e}")

    return stats

def get_optimized_chrome_options():
    """
    Returns optimized Chrome options to reduce resource usage
    """
    options = webdriver.ChromeOptions()
    
    # Headless mode
    options.add_argument('--headless=new')
    
    # Performance optimizations
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-software-rasterizer')
    
    # Reduce memory usage
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-breakpad')
    options.add_argument('--disable-component-extensions-with-background-pages')
    options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--disable-renderer-backgrounding')
    
    # Disable images for faster loading (optional)
    options.add_argument('--blink-settings=imagesEnabled=false')
    
    # Language and user agent
    options.add_argument("--lang=en")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Logging
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    return options

# ============================================================================
# SCRAPING FUNCTIONS - OVERVIEW PAGE
# ============================================================================

def scrape_overview_only(url):
    """
    Performs scraping ONLY on the /overview page
    OPTIMIZED: Uses shared Chrome options
    """
    print(f"[OVERVIEW] Starting scraping: {url}")
    
    extracted_data = {}
    
    options = get_optimized_chrome_options()

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.set_page_load_timeout(20)
        
        driver.get(url)
        
        time.sleep(2)
        
        # SMART 404 CHECK
        try:
            error_div = driver.find_element(By.CSS_SELECTOR, "div.content.content--error")
            error_text = error_div.text.lower()
            
            if 'player not found' in error_text or '404' in error_text or 'missing in action' in error_text:
                print("[OVERVIEW] ❌ Player not found (404)")
                return {"error": "Player not found", "error_type": "404"}
        except:
            pass
        
        wait = WebDriverWait(driver, 12)
        
        # Extract RP
        try:
            rp_selector = ".text-24.text-20, .trn-defstat__value, .stat-value"
            rp_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, rp_selector)))
            extracted_data['Rank Points'] = rp_element.text.strip()
            
        except Exception as e:
            try:
                error_div = driver.find_element(By.CSS_SELECTOR, "div.content.content--error")
                if error_div:
                    print("[OVERVIEW] ❌ Player not found (404)")
                    return {"error": "Player not found", "error_type": "404"}
            except:
                pass
            
            extracted_data['Rank Points'] = "N/A"

        try:
            image_selector = "img.size-14, img.trn-defstat__icon, img[alt*='Rank']"
            image_element = driver.find_element(By.CSS_SELECTOR, image_selector)
            extracted_data['Rank Image URL'] = image_element.get_attribute('src')
        except Exception:
            extracted_data['Rank Image URL'] = ""

        if extracted_data.get('Rank Points', "N/A") == "N/A":
            return {"error": "Profile not found or tracker structure changed"}

        # Lifetime Stats
        lifetime_stats = extract_section_stats(driver, "lifetime overall")
        if not lifetime_stats:
            lifetime_stats = extract_section_stats(driver, "lifetime")
        if not lifetime_stats:
            lifetime_stats = extract_section_stats(driver, "overall")

        extracted_data["Level"] = lifetime_stats.get("Level", "N/A")
        extracted_data["Lifetime Matches"] = lifetime_stats.get("Matches", "N/A")
        extracted_data["Time Played"] = lifetime_stats.get("Time Played", "N/A")

        # Season Stats
        try:
            season_section = driver.find_element(By.CSS_SELECTOR, "section.season-overview.v3-card")
            current_season_stats = {}
            stat_blocks = season_section.find_elements(By.CSS_SELECTOR, "div.name-value")
            
            for block in stat_blocks:
                try:
                    stat_name_elem = block.find_element(By.CSS_SELECTOR, "span.stat-name span.truncate")
                    stat_name = stat_name_elem.text.strip()
                    stat_value_elem = block.find_element(By.CSS_SELECTOR, "span.stat-value span.truncate")
                    stat_value = stat_value_elem.text.strip()
                    if stat_name and stat_value:
                        current_season_stats[stat_name] = stat_value
                except:
                    continue
            
            kd_value = "N/A"
            for key, value in current_season_stats.items():
                if 'kd' in key.lower() or 'k/d' in key.lower():
                    kd_value = value
                    break
            extracted_data['Season K/D'] = kd_value
            
            winrate_value = "N/A"
            for key, value in current_season_stats.items():
                if 'win' in key.lower() and 'rate' in key.lower():
                    winrate_value = value
                    break
            extracted_data['Season Win Rate'] = winrate_value
            
            matches_value = "N/A"
            for key, value in current_season_stats.items():
                if 'match' in key.lower() and 'es' in key.lower():
                    matches_value = value
                    break
            extracted_data['Season Matches'] = matches_value
            
        except Exception:
            extracted_data['Season K/D'] = "N/A"
            extracted_data['Season Win Rate'] = "N/A"
            extracted_data['Season Matches'] = "N/A"

        # Best Rank
        try:
            season_peaks_section = driver.find_element(By.CSS_SELECTOR, "div.v3-card.season-peaks")
            first_rank_img = season_peaks_section.find_element(By.CSS_SELECTOR, "tbody tr:first-child img.size-10")
            extracted_data['Best Rank Image URL'] = first_rank_img.get_attribute('src')
            extracted_data['Best Rank Name'] = first_rank_img.get_attribute('alt')
            
            try:
                first_row = season_peaks_section.find_element(By.CSS_SELECTOR, "tbody tr:first-child")
                rp_element = first_row.find_element(By.XPATH, ".//span[contains(text(), 'RP')]/..")
                extracted_data['Best Rank RP'] = rp_element.text.strip()
            except:
                extracted_data['Best Rank RP'] = "N/A"
        except Exception:
            extracted_data['Best Rank Image URL'] = ""
            extracted_data['Best Rank Name'] = "N/A"
            extracted_data['Best Rank RP'] = "N/A"

        # Last Matches - SKIP for speed (optional)
        extracted_data['Last Matches'] = []

        print(f"[OVERVIEW] ✓ Data extracted")
        return extracted_data

    except Exception as e:
        try:
            if driver:
                error_div = driver.find_element(By.CSS_SELECTOR, "div.content.content--error")
                if error_div:
                    print("[OVERVIEW] ❌ Player not found (404)")
                    return {"error": "Player not found", "error_type": "404"}
        except:
            pass
            
        return {"error": f"Scraping error: {str(e)[:100]}"}
    finally:
        if driver:
            driver.quit()

# ============================================================================
# SCRAPING FUNCTIONS - OPERATORS PAGE
# ============================================================================

def scrape_operators_only(url):
    """
    Performs scraping ONLY on the /operators page
    OPTIMIZED: Faster with optimized options
    """
    operators_url = url.replace('/overview', '/operators')
    print(f"[OPERATORS] Starting scraping: {operators_url}")
    
    options = get_optimized_chrome_options()

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(15)
        
        driver.get(operators_url)
        
        time.sleep(5)
        
        if "Just a moment" in driver.title:
            print("[OPERATORS] Cloudflare blocked")
            return []
        
        try:
            error_div = driver.find_element(By.CSS_SELECTOR, "div.content.content--error")
            if error_div:
                print("[OPERATORS] Player not found (404)")
                return []
        except:
            pass
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        operator_rows = driver.find_elements(By.XPATH, "//tr[.//img[contains(@src, 'operators/badges')]]")
        
        if not operator_rows:
            operator_rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr[data-key]")
        
        operator_rows = operator_rows[:4]
        
        top_operators = []
        
        for operator_row in operator_rows:
            try:
                operator_data = {}
                
                try:
                    name_elem = operator_row.find_element(By.XPATH, 
                                                         ".//span[contains(@class, 'stat-value')]//span[contains(@class, 'truncate')]")
                    operator_data['Name'] = name_elem.text.strip()
                except:
                    operator_data['Name'] = "N/A"
                
                try:
                    img_elem = operator_row.find_element(By.TAG_NAME, "img")
                    operator_data['Image URL'] = img_elem.get_attribute('src')
                except:
                    operator_data['Image URL'] = ""
                
                try:
                    all_text = operator_row.text
                    import re
                    
                    numbers = re.findall(r'\d+(?:\.\d+)?%?', all_text)
                    
                    rounds_candidates = [n for n in numbers if '%' not in n and len(n) >= 3 and '.' not in n]
                    operator_data['Rounds Played'] = rounds_candidates[0] if rounds_candidates else "N/A"
                    
                    percentages = [n for n in numbers if '%' in n]
                    operator_data['Win %'] = percentages[0] if len(percentages) >= 1 else "N/A"
                    operator_data['HS %'] = percentages[1] if len(percentages) >= 2 else "N/A"
                    
                    kd_candidates = [n for n in numbers if '.' in n and '%' not in n]
                    operator_data['K/D'] = kd_candidates[0] if kd_candidates else "N/A"
                except:
                    operator_data.setdefault('Rounds Played', 'N/A')
                    operator_data.setdefault('Win %', 'N/A')
                    operator_data.setdefault('K/D', 'N/A')
                    operator_data.setdefault('HS %', 'N/A')
                
                top_operators.append(operator_data)
            except:
                continue
        
        print(f"[OPERATORS] Extracted {len(top_operators)} operators")
        return top_operators

    except Exception as e:
        print(f"[OPERATORS] Error: {str(e)[:50]}")
        return []
    finally:
        if driver:
            driver.quit()


# ============================================================================
# PLAYER INPUT COLLECTION
# ============================================================================

players_config = {
    'main': None,
    'allies': [],
    'enemies': []
}


def select_platform(username):
    """
    Shows platform selection menu and returns the choice.
    """
    print(f"  Platform for '{username}':")
    print("    1 → PSN (PlayStation)")
    print("    2 → Xbox")
    print("    3 → Ubisoft (PC)")
    
    while True:
        choice = input("  Choose (1/2/3): ").strip()
        
        if choice == '1':
            return 'psn'
        elif choice == '2':
            return 'xbox'
        elif choice == '3':
            return 'ubisoft'
        else:
            print("  ⚠ Invalid choice. Try again.")


def collect_players_input():
    """
    Loads configuration from config.txt only.
    NO terminal input required - everything is done via web interface.
    """
    print("\n" + "="*60)
    print("LOADING PLAYER CONFIGURATION")
    print("="*60)
    
    config_data = read_parameters('config.txt')
    
    if not config_data or 'main' not in config_data or not config_data['main']:
        print("=" * 60)
        print("⚠ ERROR: config.txt file not valid or missing!")
        print("=" * 60)
        print("\nThe config.txt file must contain at least:")
        print("""
[main]
platform: psn
username: YourNickname
        """)
        print("\nValid platforms: psn, xbox, ubisoft")
        print("=" * 60)
        
        print("\nDo you want to create a new config.txt now?")
        create = input("Type 'y' to create, any other key to exit: ").strip().lower()
        
        if create == 'y' or create == 's':
            print("\n--- CREATING CONFIG.TXT ---")
            username = input("Main username: ").strip()
            if not username:
                print("⚠ Username required!")
                return False
            
            platform = select_platform(username)
            
            try:
                with open('config.txt', 'w', encoding='utf-8') as f:
                    f.write("# R6 Siege Tracker Configuration\n")
                    f.write("# Main player (required)\n\n")
                    f.write("[main]\n")
                    f.write(f"platform: {platform}\n")
                    f.write(f"username: {username}\n")
                    f.write("\n# Fixed allies (optional - up to 4)\n")
                    f.write("# Uncomment and fill to save your squad\n\n")
                    f.write("#[ally1]\n")
                    f.write("#platform: psn\n")
                    f.write("#username: FriendName\n")
                
                print("\n✓ config.txt file created successfully!")
                print(f"✓ Main player: {username} ({platform.upper()})\n")
                
                config_data = read_parameters('config.txt')
                if not config_data or 'main' not in config_data:
                    print("⚠ Error rereading config.txt")
                    return False
            except Exception as e:
                print(f"⚠ Error creating file: {e}")
                return False
        else:
            print("\nExiting program.")
            return False
    
    players_config['main'] = config_data['main'].copy()
    main_platform_display = config_data['main']['platform'].upper()
    print(f"✓ MAIN PLAYER: {config_data['main']['username']} ({main_platform_display})")
    
    config_allies = config_data.get('allies', [])
    if config_allies:
        players_config['allies'] = config_allies
        print(f"✓ FIXED ALLIES: {len(config_allies)}")
        for idx, ally in enumerate(config_allies, 1):
            print(f"  {idx}. {ally['username']} ({ally['platform'].upper()})")
    else:
        print(f"⊘ No fixed allies configured")
    
    players_config['enemies'] = []
    
    print("\n" + "="*60)
    print("✓ Configuration loaded successfully!")
    print("💡 Add enemies via web interface when match starts")
    print("="*60 + "\n")
    
    return True


# ============================================================================
# PARALLEL SCRAPING HELPERS
# ============================================================================

def scrape_player_overview(player_data, player_type, player_index):
    """
    Scrapes /overview for a single player
    """
    username = player_data['username']
    print(f"\n[OVERVIEW {player_type.upper()} #{player_index}] {username}")
    
    tracker_url = build_url(player_data)
    if not tracker_url:
        return {
            'error': 'Invalid URL',
            'username': username,
            'platform': player_data['platform'],
            'player_type': player_type,
            'player_index': player_index
        }
    
    result = scrape_overview_only(tracker_url)
    result['username'] = username
    result['platform'] = player_data['platform']
    result['tracker_url'] = tracker_url
    result['player_type'] = player_type
    result['player_index'] = player_index
    
    if 'error' not in result:
        print(f"[✓ OVERVIEW {player_type.upper()} #{player_index}] {username}")
    else:
        print(f"[✗ OVERVIEW {player_type.upper()} #{player_index}] {username}: {result['error']}")
    
    return result


def scrape_player_operators(player_data, player_type, player_index):
    """
    Scrapes /operators for a single player
    """
    username = player_data['username']
    print(f"\n[OPERATORS {player_type.upper()} #{player_index}] {username}")
    
    tracker_url = build_url(player_data)
    if not tracker_url:
        return {
            'operators': [],
            'username': username,
            'player_type': player_type,
            'player_index': player_index
        }
    
    operators = scrape_operators_only(tracker_url)
    
    print(f"[✓ OPERATORS {player_type.upper()} #{player_index}] {username} - {len(operators)} ops")
    
    return {
        'operators': operators,
        'username': username,
        'player_type': player_type,
        'player_index': player_index
    }


# ============================================================================
# FLASK API ENDPOINTS
# ============================================================================

@app.route('/api/get_initial_config', methods=['GET'])
def get_initial_config():
    """
    Returns the initial configuration (main + allies) loaded from config.txt
    """
    return jsonify({
        'main': players_config['main'],
        'allies': players_config['allies'],
        'enemies': players_config['enemies']
    })


@app.route('/api/scrape_player/<player_type>/<int:player_index>', methods=['GET'])
def scrape_single_player_endpoint(player_type, player_index):
    """
    Scrapes data for a single player with controlled parallelism
    """
    try:
        print(f"\n[API] Single player request: {player_type} #{player_index}")
        
        if player_type == 'main':
            if not players_config['main']:
                return jsonify({'error': 'Main player not configured'}), 400
            player_data = players_config['main']
        elif player_type == 'ally':
            if player_index < 1 or player_index > len(players_config['allies']):
                return jsonify({'error': f'Ally {player_index} not configured'}), 400
            player_data = players_config['allies'][player_index - 1]
        elif player_type == 'enemy':
            if player_index < 1 or player_index > len(players_config['enemies']):
                return jsonify({'error': f'Enemy {player_index} not configured'}), 400
            player_data = players_config['enemies'][player_index - 1]
        else:
            return jsonify({'error': 'Invalid player type'}), 400
        
        # CONTROLLED PARALLELISM: Max 2 workers instead of unlimited
        with ThreadPoolExecutor(max_workers=2) as executor:
            overview_future = executor.submit(scrape_player_overview, player_data, player_type, player_index)
            operators_future = executor.submit(scrape_player_operators, player_data, player_type, player_index)
            
            overview_result = overview_future.result()
            operators_result = operators_future.result()
        
        overview_result['Top Operators'] = operators_result.get('operators', [])
        
        return jsonify(overview_result), 200
        
    except Exception as e:
        print(f"[ERROR] Single player scraping: {e}")
        return jsonify({'error': str(e)}), 500
        
        
@app.route('/api/scrape_overview/<player_type>/<int:player_index>', methods=['GET'])
def scrape_overview_endpoint(player_type, player_index):
    """
    Scrapes ONLY overview data for a single player (fast)
    """
    try:
        print(f"\n[API OVERVIEW] Request: {player_type} #{player_index}")
        
        if player_type == 'main':
            if not players_config['main']:
                return jsonify({'error': 'Main player not configured'}), 400
            player_data = players_config['main']
        elif player_type == 'ally':
            if player_index < 1 or player_index > len(players_config['allies']):
                return jsonify({'error': f'Ally {player_index} not configured'}), 400
            player_data = players_config['allies'][player_index - 1]
        elif player_type == 'enemy':
            if player_index < 1 or player_index > len(players_config['enemies']):
                return jsonify({'error': f'Enemy {player_index} not configured'}), 400
            player_data = players_config['enemies'][player_index - 1]
        else:
            return jsonify({'error': 'Invalid player type'}), 400
        
        # Only scrape overview
        overview_result = scrape_player_overview(player_data, player_type, player_index)
        
        return jsonify(overview_result), 200
        
    except Exception as e:
        print(f"[ERROR] Overview scraping: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/scrape_operators/<player_type>/<int:player_index>', methods=['GET'])
def scrape_operators_endpoint(player_type, player_index):
    """
    Scrapes ONLY operators data for a single player (slow)
    """
    try:
        print(f"\n[API OPERATORS] Request: {player_type} #{player_index}")
        
        if player_type == 'main':
            if not players_config['main']:
                return jsonify({'error': 'Main player not configured'}), 400
            player_data = players_config['main']
        elif player_type == 'ally':
            if player_index < 1 or player_index > len(players_config['allies']):
                return jsonify({'error': f'Ally {player_index} not configured'}), 400
            player_data = players_config['allies'][player_index - 1]
        elif player_type == 'enemy':
            if player_index < 1 or player_index > len(players_config['enemies']):
                return jsonify({'error': f'Enemy {player_index} not configured'}), 400
            player_data = players_config['enemies'][player_index - 1]
        else:
            return jsonify({'error': 'Invalid player type'}), 400
        
        # Only scrape operators
        operators_result = scrape_player_operators(player_data, player_type, player_index)
        
        return jsonify(operators_result), 200
        
    except Exception as e:
        print(f"[ERROR] Operators scraping: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/update_players', methods=['POST'])
def update_players():
    """
    Updates player configuration without restarting the server.
    """
    try:
        if not request.is_json:
            print("[ERROR] Request is not JSON")
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json'
            }), 400
        
        data = request.get_json()
        
        print("\n" + "="*60)
        print("UPDATING PLAYER CONFIGURATION")
        print("="*60)
        
        new_allies = data.get('allies', [])
        players_config['allies'] = []
        
        for idx, ally in enumerate(new_allies, 1):
            if ally.get('username') and ally.get('platform'):
                username = ally['username'].strip()
                platform = ally['platform'].lower()
                
                if platform not in ['psn', 'xbox', 'ubisoft']:
                    print(f"[WARN] Invalid platform for ally {idx}: {platform}")
                    continue
                
                players_config['allies'].append({
                    'username': username,
                    'platform': platform
                })
                print(f"✓ Ally {idx}: {username} ({platform.upper()})")
        
        new_enemies = data.get('enemies', [])
        players_config['enemies'] = []
        
        for idx, enemy in enumerate(new_enemies, 1):
            if enemy.get('username') and enemy.get('platform'):
                username = enemy['username'].strip()
                platform = enemy['platform'].lower()
                
                if platform not in ['psn', 'xbox', 'ubisoft']:
                    print(f"[WARN] Invalid platform for enemy {idx}: {platform}")
                    continue
                
                players_config['enemies'].append({
                    'username': username,
                    'platform': platform
                })
                print(f"✓ Enemy {idx}: {username} ({platform.upper()})")
        
        print(f"\n✓ Configuration updated!")
        print(f"  Allies: {len(players_config['allies'])}/4")
        print(f"  Enemies: {len(players_config['enemies'])}/5")
        print("="*60 + "\n")
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully',
            'allies_count': len(players_config['allies']),
            'enemies_count': len(players_config['enemies'])
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Configuration update: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/')
def index():
    """Renders the main HTML page"""
    return render_template('index.html')


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    import socket
    
    print("\n" + "="*60)
    print("R6 SIEGE TRACKER - SCRAPER & DASHBOARD")
    print("="*60)
    
    if not collect_players_input():
        print("\nERROR: Configuration failed. Exiting.")
        input("Press ENTER to exit...")
        exit(1)
    
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "Unable to detect"
    
    print("\n" + "="*60)
    print("🚀 STARTING FLASK SERVER")
    print("="*60)
    print(f"🖥️  PC Access:      http://127.0.0.1:5000/")
    print(f"📱 Mobile Access:  http://{local_ip}:5000/")
    print("="*60)
    print("\n💡 The web interface will open automatically in 2 seconds")
    print("💡 Add enemies from mobile when your match starts!")
    print("💡 Press CTRL+C to stop the server")
    print("="*60 + "\n")
    
    # Auto-open browser after 2 seconds
    Timer(2, lambda: webbrowser.open('http://127.0.0.1:5000/')).start()
    
    # Start server WITHOUT asking for input
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("🛑 SERVER STOPPED BY USER")
        print("="*60)
    except Exception as e:
        print(f"\n\n❌ SERVER ERROR: {e}")
        input("Press ENTER to exit...")
