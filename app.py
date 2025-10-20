"""
R6 Siege Tracker - Web Scraper & Dashboard
=============================================
A Flask-based web application that scrapes player statistics from R6 Tracker
and displays them in a real-time dashboard with parallel processing.

Author: JuriCerretani
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
    
    Args:
        file_name (str): Path to the configuration file
        
    Returns:
        dict: Configuration data with 'main' and 'allies' keys, or None if error
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
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # New section [name]
            if line.startswith('[') and line.endswith(']'):
                # Save previous section if complete
                if current_section and 'platform' in current_data and 'username' in current_data:
                    if current_section == 'main':
                        config['main'] = current_data.copy()
                    elif current_section.startswith('ally'):
                        config['allies'].append(current_data.copy())
                
                # Start new section
                current_section = line[1:-1].strip().lower()
                current_data = {}
                continue
            
            # Read key:value parameters
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    value = parts[1].strip()
                    current_data[key] = value
        
        # Save last section (important!)
        if current_section and 'platform' in current_data and 'username' in current_data:
            if current_section == 'main':
                config['main'] = current_data.copy()
            elif current_section.startswith('ally'):
                config['allies'].append(current_data.copy())
        
        # Validate main player exists
        if not config['main']:
            print("Error: [main] section not found or incomplete in config.txt")
            return None
        
        # Validate main platform
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
    
    Args:
        file_name (str): Path to the configuration file
        players_config (dict): Player configuration data
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(file_name, 'w', encoding='utf-8') as f:
            # Main player
            f.write("[main]\n")
            f.write(f"platform: {players_config['main']['platform']}\n")
            f.write(f"username: {players_config['main']['username']}\n")
            f.write("\n")
            
            # Allies
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
    Platform mapping:
    - psn → psn
    - xbox → xbl
    - ubisoft → ubi
    
    Args:
        parameters (dict): Dictionary with 'platform' and 'username' keys
        
    Returns:
        str: Full tracker URL, or None if invalid platform
    """
    platform = parameters['platform'].lower()
    username = parameters['username']
    
    # Platform mapping for URL paths
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
    Compatible with both CSS and XPath selectors.
    
    Args:
        driver: Selenium WebDriver instance
        base_selector (str): CSS or XPath selector for the context
        stat_name (str): Name of the stat to find
        
    Returns:
        str: Stat value or "N/A"
    """
    try:
        # Determine if selector is XPath or CSS
        if isinstance(base_selector, str) and (base_selector.strip().startswith('/') or 
                                                base_selector.strip().startswith('.//') or 
                                                base_selector.strip().startswith('//')):
            context = driver.find_element(By.XPATH, base_selector)
        else:
            context = driver.find_element(By.CSS_SELECTOR, base_selector)
    except Exception:
        return "N/A"

    try:
        # Find element containing the label text
        try:
            label_elem = context.find_element(By.XPATH, f".//*[contains(normalize-space(string(.)), '{stat_name}')]")
        except Exception:
            label_elem = driver.find_element(By.XPATH, f"//*[contains(normalize-space(string(.)), '{stat_name}')]")

        # Get parent element containing both label and value
        parent = label_elem.find_element(By.XPATH, "./ancestor::div[1]")

        # Try to find value within parent
        try:
            value_elem = parent.find_element(By.XPATH, ".//div[contains(@class,'stat-value') or contains(@class,'value') or contains(@class,'text-') or .//span[contains(@class,'stat-value')]]")
            val = value_elem.text.strip()
            return val if val else "N/A"
        except Exception:
            # Fallback: get parent text without label
            full = parent.text.strip().replace(label_elem.text.strip(), '').strip()
            return full if full else "N/A"
    except Exception:
        return "N/A"


def extract_section_stats(driver, section_keyword):
    """
    Searches for a section (e.g., 'lifetime overall', 'ranked') based on <h2>/<h3> title
    and returns a dictionary of {label: value}.
    
    Args:
        driver: Selenium WebDriver instance
        section_keyword (str): Keyword to search in section headers
        
    Returns:
        dict: Dictionary of stat labels and values
    """
    section_keyword = section_keyword.lower()
    stats = {}

    # Find potential stat blocks
    blocks = driver.find_elements(By.CSS_SELECTOR, 
                                  "div.stat-group, div.stat-card, div.name-value, div.tracker-card, div.trn-card__content")
    
    for block in blocks:
        try:
            # Try to find preceding header
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

    # Fallback: search for header containing keyword
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
    Returns a dict {stat_name: stat_value} by searching all stat blocks
    within the specified context.
    
    Args:
        driver: Selenium WebDriver instance
        context: WebElement, XPath string, or None for entire page
        
    Returns:
        dict: Dictionary of stat names and values
    """
    stats = {}
    try:
        # Resolve context
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

        # Find stat blocks
        blocks = ctx_elem.find_elements(By.XPATH, 
                                       ".//div[contains(@class,'text-center') or contains(@class,'name-value')]")
        if not blocks:
            blocks = ctx_elem.find_elements(By.XPATH, 
                                           ".//div[.//div[contains(@class,'stat-label')] and .//div[contains(@class,'stat-value')]]")

        # Iterate through each block
        for b in blocks:
            try:
                # Get label
                try:
                    label_elem = b.find_element(By.XPATH, 
                                               ".//div[contains(@class,'stat-label')] | .//span[contains(@class,'stat-name')]")
                    label = label_elem.text.strip()
                except Exception:
                    label = ""

                if not label:
                    continue

                # Get value
                try:
                    val_elem = b.find_element(By.XPATH, 
                                             ".//div[contains(@class,'stat-value')] | .//span[contains(@class,'stat-value')]")
                    value = val_elem.text.strip()
                except Exception:
                    value = ""

                if not value:
                    # Fallback: get text without label
                    text_all = b.text.strip().replace(label, '').strip()
                    value = text_all if text_all else "N/A"

                # Remove duplicates like "1,697h / 1,697h"
                parts = [p.strip() for p in value.split('/') if p.strip()]
                parts = list(dict.fromkeys(parts))
                clean_value = ' / '.join(parts)

                stats[label] = clean_value
            except Exception:
                continue

    except Exception as e:
        print(f"[DEBUG] extract_stats_from_context error: {e}")

    return stats


# ============================================================================
# SCRAPING FUNCTIONS - OVERVIEW PAGE
# ============================================================================

def scrape_overview_only(url):
    """
    Performs scraping ONLY on the /overview page
    
    Args:
        url (str): Full URL to the player's overview page
        
    Returns:
        dict: Extracted player data or error dictionary
    """
    print(f"[OVERVIEW] Starting scraping: {url}")
    
    extracted_data = {}
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument("--lang=en")
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)

        # 1. Extract RP and Rank Image
        try:
            rp_selector = ".text-24.text-20, .trn-defstat__value, .stat-value"
            rp_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, rp_selector)))
            extracted_data['Rank Points'] = rp_element.text.strip()
        except Exception:
            extracted_data['Rank Points'] = "N/A"

        try:
            image_selector = "img.size-14, img.trn-defstat__icon, img[alt*='Rank']"
            image_element = driver.find_element(By.CSS_SELECTOR, image_selector)
            extracted_data['Rank Image URL'] = image_element.get_attribute('src')
        except Exception:
            extracted_data['Rank Image URL'] = ""

        if extracted_data.get('Rank Points', "N/A") == "N/A":
            return {"error": "Profile not found or tracker structure changed"}

        # 2. Lifetime Stats
        lifetime_stats = extract_section_stats(driver, "lifetime overall")
        if not lifetime_stats:
            lifetime_stats = extract_section_stats(driver, "lifetime")
        if not lifetime_stats:
            lifetime_stats = extract_section_stats(driver, "overall")

        extracted_data["Level"] = lifetime_stats.get("Level", "N/A")
        extracted_data["Lifetime Matches"] = lifetime_stats.get("Matches", "N/A")
        extracted_data["Time Played"] = lifetime_stats.get("Time Played", "N/A")

        # 3. Season Stats
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
            
            # Extract K/D
            kd_value = "N/A"
            for key, value in current_season_stats.items():
                if 'kd' in key.lower() or 'k/d' in key.lower():
                    kd_value = value
                    break
            extracted_data['Season K/D'] = kd_value
            
            # Extract Win Rate
            winrate_value = "N/A"
            for key, value in current_season_stats.items():
                if 'win' in key.lower() and 'rate' in key.lower():
                    winrate_value = value
                    break
            extracted_data['Season Win Rate'] = winrate_value
            
            # Extract Matches
            matches_value = "N/A"
            for key, value in current_season_stats.items():
                if 'match' in key.lower() and 'es' in key.lower():
                    matches_value = value
                    break
            extracted_data['Season Matches'] = matches_value
            
        except Exception as e:
            print(f"[DEBUG] Error extracting season stats: {e}")
            extracted_data['Season K/D'] = "N/A"
            extracted_data['Season Win Rate'] = "N/A"
            extracted_data['Season Matches'] = "N/A"

        # 4. Best Rank
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
        except Exception as e:
            print(f"[DEBUG] Error extracting best rank: {e}")
            extracted_data['Best Rank Image URL'] = ""
            extracted_data['Best Rank Name'] = "N/A"
            extracted_data['Best Rank RP'] = "N/A"

        # 5. Last Matches
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='match-row']")
            if not match_rows:
                match_rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'match') and contains(@class, 'row')]")
            
            # Filter duplicates (take every 2nd element)
            match_rows = [match_rows[i] for i in range(0, len(match_rows), 2)]
            match_rows = match_rows[:4]  # Limit to 4 matches
            
            last_matches = []
            
            for idx, match_row in enumerate(match_rows, 1):
                try:
                    match_data = {}
                    match_classes = match_row.get_attribute('class') or ''
                    
                    # Determine win/loss
                    if 'win' in match_classes.lower():
                        match_data['Result'] = 'Win'
                    elif 'loss' in match_classes.lower():
                        match_data['Result'] = 'Loss'
                    else:
                        match_data['Result'] = 'Unknown'
                    
                    # Extract map name
                    try:
                        all_spans = match_row.find_elements(By.TAG_NAME, "span")
                        for span in all_spans:
                            text = span.text.strip()
                            map_keywords = ['Labs', 'Border', 'Bank', 'Kanal', 'Consulate', 'Villa', 'Chalet', 
                                          'Club', 'Kafe', 'Oregon', 'Theme', 'Tower', 'Yacht', 'Fortress',
                                          'Outback', 'Stadium', 'Favela', 'Skyscraper', 'Emerald']
                            if any(keyword in text for keyword in map_keywords) and 'ago' not in text.lower():
                                match_data['Map'] = text
                                break
                        if 'Map' not in match_data:
                            match_data['Map'] = "N/A"
                    except:
                        match_data['Map'] = "N/A"
                    
                    # Extract game mode
                    try:
                        mode_keywords = ['Ranked', 'Unranked', 'Casual', 'Quick Match']
                        all_spans = match_row.find_elements(By.TAG_NAME, "span")
                        for span in all_spans:
                            text = span.text.strip()
                            if text in mode_keywords:
                                match_data['Mode'] = text
                                break
                        if 'Mode' not in match_data:
                            match_data['Mode'] = "N/A"
                    except:
                        match_data['Mode'] = "N/A"
                    
                    # Extract score
                    try:
                        all_text = match_row.text
                        import re
                        score_pattern = r'(\d+)\s*:\s*(\d+)'
                        score_match = re.search(score_pattern, all_text)
                        if score_match:
                            match_data['Score'] = f"{score_match.group(1)} : {score_match.group(2)}"
                        else:
                            match_data['Score'] = "N/A"
                    except:
                        match_data['Score'] = "N/A"
                    
                    # Extract K/D, KDA, HS%
                    try:
                        all_text = match_row.text
                        import re
                        
                        kd_match = re.search(r'K/D[^\d]*(\d+\.\d+)', all_text)
                        if kd_match:
                            match_data['K/D'] = kd_match.group(1)
                        
                        kda_match = re.search(r'K/D/A[^\d]*(\d+)[^\d]+(\d+)[^\d]+(\d+)', all_text)
                        if kda_match:
                            match_data['Kills'] = kda_match.group(1)
                            match_data['Deaths'] = kda_match.group(2)
                            match_data['Assists'] = kda_match.group(3)
                        
                        hs_match = re.search(r'HS\s*%[^\d]*(\d+\.\d+%)', all_text)
                        if hs_match:
                            match_data['HS%'] = hs_match.group(1)
                    except:
                        pass
                    
                    # Set defaults
                    match_data.setdefault('K/D', 'N/A')
                    match_data.setdefault('Kills', 'N/A')
                    match_data.setdefault('Deaths', 'N/A')
                    match_data.setdefault('Assists', 'N/A')
                    match_data.setdefault('HS%', 'N/A')
                    
                    last_matches.append(match_data)
                except:
                    continue
            
            extracted_data['Last Matches'] = last_matches
        except Exception as e:
            print(f"[DEBUG] Error extracting matches: {e}")
            extracted_data['Last Matches'] = []

        return extracted_data

    except Exception as e:
        return {"error": f"Overview scraping error: {e}"}
    finally:
        if driver:
            driver.quit()


# ============================================================================
# SCRAPING FUNCTIONS - OPERATORS PAGE
# ============================================================================

def scrape_operators_only(url):
    """
    Performs scraping ONLY on the /operators page
    
    Args:
        url (str): Full URL to the player's overview page (will be converted to operators)
        
    Returns:
        list: List of operator dictionaries or empty list if error
    """
    operators_url = url.replace('/overview', '/operators')
    print(f"[OPERATORS] Starting scraping: {operators_url}")
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument("--lang=en")
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(operators_url)
        
        time.sleep(8)  # Wait for Cloudflare
        
        if "Just a moment" in driver.title:
            print("[OPERATORS] Cloudflare blocked")
            return []
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Find operator rows
        operator_rows = driver.find_elements(By.XPATH, "//tr[.//img[contains(@src, 'operators/badges')]]")
        
        if not operator_rows:
            operator_rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr[data-key]")
        
        operator_rows = operator_rows[:4]  # Limit to top 4
        
        top_operators = []
        
        for idx, operator_row in enumerate(operator_rows, 1):
            try:
                operator_data = {}
                
                # Extract operator name
                try:
                    name_elem = operator_row.find_element(By.XPATH, 
                                                         ".//span[contains(@class, 'stat-value')]//span[contains(@class, 'truncate')]")
                    operator_data['Name'] = name_elem.text.strip()
                except:
                    operator_data['Name'] = "N/A"
                
                # Extract operator image
                try:
                    img_elem = operator_row.find_element(By.TAG_NAME, "img")
                    operator_data['Image URL'] = img_elem.get_attribute('src')
                except:
                    operator_data['Image URL'] = ""
                
                # Extract statistics
                try:
                    all_text = operator_row.text
                    import re
                    
                    numbers = re.findall(r'\d+(?:\.\d+)?%?', all_text)
                    
                    # Rounds played (large number without %)
                    rounds_candidates = [n for n in numbers if '%' not in n and len(n) >= 3 and '.' not in n]
                    operator_data['Rounds Played'] = rounds_candidates[0] if rounds_candidates else "N/A"
                    
                    # Percentages
                    percentages = [n for n in numbers if '%' in n]
                    operator_data['Win %'] = percentages[0] if len(percentages) >= 1 else "N/A"
                    operator_data['HS %'] = percentages[1] if len(percentages) >= 2 else "N/A"
                    
                    # K/D (decimal number)
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
        print(f"[OPERATORS] Error: {e}")
        return []
    finally:
        if driver:
            driver.quit()


# ============================================================================
# PLAYER INPUT COLLECTION
# ============================================================================

# Global player configuration storage
players_config = {
    'main': None,
    'allies': [],
    'enemies': []
}


def select_platform(username):
    """
    Shows platform selection menu and returns the choice.
    
    Args:
        username (str): Username for display purposes
        
    Returns:
        str: 'psn', 'xbox', or 'ubisoft'
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
    Collects player data from terminal for allies and enemies.
    Allows pressing ENTER to confirm/skip a player.
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*60)
    print("PLAYER CONFIGURATION FOR THE MATCH")
    print("="*60)
    print("Press ENTER to confirm/skip a player\n")
    
    # Load existing configuration
    config_data = read_parameters('config.txt')
    
    # Verify main player exists
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
        
        # Offer to create config.txt
        print("\nDo you want to create a new config.txt now?")
        create = input("Type 's' to create, any other key to exit: ").strip().lower()
        
        if create == 's' or create == 'y':
            print("\n--- CREATING CONFIG.TXT ---")
            username = input("Main username: ").strip()
            if not username:
                print("⚠ Username required!")
                return False
            
            platform = select_platform(username)
            
            # Create config.txt
            try:
                with open('config.txt', 'w', encoding='utf-8') as f:
                    f.write("# R6 Siege Tracker Configuration\n")
                    f.write("# Main player (required)\n\n")
                    f.write("[main]\n")
                    f.write(f"platform: {platform}\n")
                    f.write(f"username: {username}\n")
                    f.write("\n# Fixed allies (optional)\n")
                    f.write("# You can add up to 4 allies\n")
                    f.write("# Valid platforms: psn, xbox, ubisoft\n\n")
                    f.write("#[ally1]\n")
                    f.write("#platform: psn\n")
                    f.write("#username: FriendName\n")
                
                print("\n✓ config.txt file created successfully!")
                print(f"✓ Main player: {username} ({platform.upper()})\n")
                
                # Reload configuration
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
    
    # Main player
    players_config['main'] = config_data['main'].copy()
    main_platform_display = config_data['main']['platform'].upper()
    print(f"✓ MAIN PLAYER: {config_data['main']['username']} ({main_platform_display})")
    print()
    
    # Track if configuration was modified
    config_modified = False
    
    # Collect ALLIES (max 4)
    print("-" * 60)
    print("ALLIES (maximum 4):")
    print("-" * 60)
    
    config_allies = config_data.get('allies', [])
    
    for i in range(1, 5):
        print(f"\n--- Ally {i} ---")
        
        # Check if there's a saved ally in config
        if i <= len(config_allies) and config_allies[i-1].get('username'):
            saved_ally = config_allies[i-1]
            platform_display = saved_ally['platform'].upper()
            print(f"  💾 Saved in config: {saved_ally['username']} ({platform_display})")
            choice = input(f"  Press ENTER to use '{saved_ally['username']}', write new username or 'skip' to skip: ").strip()
            
            if not choice:
                # Use saved ally
                players_config['allies'].append(saved_ally.copy())
                print(f"  ✓ Ally {i} confirmed: {saved_ally['username']} ({platform_display})")
                continue
            elif choice.lower() == 'skip':
                # Skip this ally
                print(f"  ⊘ Ally {i} skipped.")
                config_modified = True
                continue
            else:
                # New username
                username = choice
                config_modified = True
        else:
            # No saved ally at this position - ask manually
            username = input(f"  Username Ally {i} (or ENTER to skip): ").strip()
            if not username:
                print(f"  ⊘ Ally {i} skipped.")
                continue
            config_modified = True
        
        # Ask platform for new username
        platform = select_platform(username)
        
        players_config['allies'].append({
            'username': username,
            'platform': platform
        })
        print(f"  ✓ Ally {i} added: {username} ({platform.upper()})")
    
    # Ask if want to save modifications
    if config_modified and len(players_config['allies']) > 0:
        print("\n" + "-" * 60)
        save_choice = input("💾 Do you want to save these allies to config.txt for next time? (y/n): ").strip().lower()
        if save_choice == 's' or save_choice == 'y':
            save_config('config.txt', players_config)
    
    # Collect ENEMIES (max 5) - always manual
    print("\n" + "-" * 60)
    print("ENEMIES (maximum 5):")
    print("-" * 60)
    for i in range(1, 6):
        print(f"\n--- Enemy {i} ---")
        username = input(f"  Username Enemy {i} (or ENTER to skip): ").strip()
        
        if not username:
            print(f"  ⊘ Enemy {i} skipped.")
            continue
        
        platform = select_platform(username)
        
        players_config['enemies'].append({
            'username': username,
            'platform': platform
        })
        print(f"  ✓ Enemy {i} added: {username} ({platform.upper()})")
    
    # Summary
    print("\n" + "="*60)
    print("CONFIGURED PLAYERS SUMMARY:")
    print("="*60)
    print(f"✓ Main Player: {players_config['main']['username']} ({players_config['main']['platform'].upper()})")
    
    if players_config['allies']:
        print(f"\n✓ Configured allies: {len(players_config['allies'])}/4")
        for idx, ally in enumerate(players_config['allies'], 1):
            print(f"  {idx}. {ally['username']} ({ally['platform'].upper()})")
    else:
        print(f"\n⊘ No allies configured (0/4)")
    
    if players_config['enemies']:
        print(f"\n✓ Configured enemies: {len(players_config['enemies'])}/5")
        for idx, enemy in enumerate(players_config['enemies'], 1):
            print(f"  {idx}. {enemy['username']} ({enemy['platform'].upper()})")
    else:
        print(f"\n⊘ No enemies configured (0/5)")
    
    print("="*60 + "\n")
    
    return True


# ============================================================================
# PARALLEL SCRAPING HELPERS
# ============================================================================

def scrape_player_overview(player_data, player_type, player_index):
    """
    Scrapes /overview for a single player
    
    Args:
        player_data (dict): Player data with username and platform
        player_type (str): 'main', 'ally', or 'enemy'
        player_index (int): Player index for debugging
        
    Returns:
        dict: Scraped data with metadata
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
    
    Args:
        player_data (dict): Player data with username and platform
        player_type (str): 'main', 'ally', or 'enemy'
        player_index (int): Player index for debugging
        
    Returns:
        dict: Operators data with metadata
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

@app.route('/api/scrape_data', methods=['GET'])
def scrape_api():
    """
    Executes 20 simultaneous scrapings:
    - 10 for /overview (all players)
    - 10 for /operators (all players)
    
    Returns:
        JSON: Complete player data organized by main/allies/enemies
    """
    
    print("\n" + "="*60)
    print("STARTING PARALLEL SCRAPING (20 SESSIONS)")
    print("="*60)
    
    # Prepare all tasks (overview + operators)
    all_tasks = []
    
    # Main player
    if players_config['main']:
        all_tasks.append(('overview', 'main', 0, players_config['main']))
        all_tasks.append(('operators', 'main', 0, players_config['main']))
    
    # Allies
    for idx, ally in enumerate(players_config['allies'], 1):
        all_tasks.append(('overview', 'ally', idx, ally))
        all_tasks.append(('operators', 'ally', idx, ally))
    
    # Enemies
    for idx, enemy in enumerate(players_config['enemies'], 1):
        all_tasks.append(('overview', 'enemy', idx, enemy))
        all_tasks.append(('operators', 'enemy', idx, enemy))
    
    print(f"\n[INFO] Total tasks: {len(all_tasks)} (overview + operators)")
    print(f"[INFO] Simultaneous sessions: {min(10, len(all_tasks))}\n")
    
    # Dictionaries to collect results
    overview_results = {}
    operators_results = {}
    
    # Execute everything in parallel
    max_workers = min(10, len(all_tasks))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        
        for task_type, player_type, idx, player_data in all_tasks:
            key = (player_type, idx)
            
            if task_type == 'overview':
                future = executor.submit(scrape_player_overview, player_data, player_type, idx)
                futures[future] = ('overview', key)
            else:  # operators
                future = executor.submit(scrape_player_operators, player_data, player_type, idx)
                futures[future] = ('operators', key)
        
        # Collect results
        for future in as_completed(futures):
            task_type, key = futures[future]
            try:
                result = future.result()
                
                if task_type == 'overview':
                    overview_results[key] = result
                else:  # operators
                    operators_results[key] = result
                    
            except Exception as exc:
                print(f"[EXCEPTION] {task_type} {key}: {exc}")
    
    # Combine overview + operators for each player
    final_data = {
        'main': None,
        'allies': [],
        'enemies': []
    }
    
    # Main player
    main_key = ('main', 0)
    if main_key in overview_results:
        final_data['main'] = overview_results[main_key]
        if main_key in operators_results:
            final_data['main']['Top Operators'] = operators_results[main_key]['operators']
        else:
            final_data['main']['Top Operators'] = []
    
    # Allies
    for idx in range(1, len(players_config['allies']) + 1):
        ally_key = ('ally', idx)
        if ally_key in overview_results:
            ally_data = overview_results[ally_key]
            if ally_key in operators_results:
                ally_data['Top Operators'] = operators_results[ally_key]['operators']
            else:
                ally_data['Top Operators'] = []
            final_data['allies'].append(ally_data)
    
    # Enemies
    for idx in range(1, len(players_config['enemies']) + 1):
        enemy_key = ('enemy', idx)
        if enemy_key in overview_results:
            enemy_data = overview_results[enemy_key]
            if enemy_key in operators_results:
                enemy_data['Top Operators'] = operators_results[enemy_key]['operators']
            else:
                enemy_data['Top Operators'] = []
            final_data['enemies'].append(enemy_data)
    
    print("\n" + "="*60)
    print("SCRAPING COMPLETED!")
    print("="*60)
    
    return jsonify(final_data)


@app.route('/api/update_players', methods=['POST'])
def update_players():
    """
    Updates player configuration without restarting the server.
    Receives JSON with allies and enemies.
    
    Returns:
        JSON: Success status and updated counts
    """
    try:
        # Verify request is JSON
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
        print(f"[DEBUG] Received data: {data}")
        
        # Update allies
        new_allies = data.get('allies', [])
        players_config['allies'] = []
        
        for idx, ally in enumerate(new_allies, 1):
            if ally.get('username') and ally.get('platform'):
                username = ally['username'].strip()
                platform = ally['platform'].lower()
                
                # Validate platform
                if platform not in ['psn', 'xbox', 'ubisoft']:
                    print(f"[WARN] Invalid platform for ally {idx}: {platform}")
                    continue
                
                players_config['allies'].append({
                    'username': username,
                    'platform': platform
                })
                print(f"✓ Ally {idx}: {username} ({platform.upper()})")
        
        # Update enemies
        new_enemies = data.get('enemies', [])
        players_config['enemies'] = []
        
        for idx, enemy in enumerate(new_enemies, 1):
            if enemy.get('username') and enemy.get('platform'):
                username = enemy['username'].strip()
                platform = enemy['platform'].lower()
                
                # Validate platform
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
        
        # Optional: save to config.txt
        save_to_config = data.get('save_to_config', False)
        if save_to_config and len(players_config['allies']) > 0:
            save_config('config.txt', players_config)
        
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


def open_browser():
    """Opens the browser after 2 seconds"""
    time.sleep(2)
    webbrowser.open_new('http://127.0.0.1:5000/')


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("R6 SIEGE TRACKER - SCRAPER & DASHBOARD")
    print("="*60)
    
    # STEP 1: Collect player input
    if not collect_players_input():
        print("\nERROR: Configuration failed. Exiting.")
        exit(1)
    
    input("\nPress ENTER to start Flask server and open browser...")
    
    # STEP 2: Start Flask server
    print("\nStarting Flask server...")
    Timer(1, open_browser).start()
    app.run(debug=False)