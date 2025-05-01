import os
import sys
import requests
import subprocess
import zipfile
from osrparse import Replay
from datetime import datetime
# star rating a bit scuffed
# ===== Configuration =====
DANSER_CLI_PATH = "PATH TO DANSER"
OUTPUT_DIR = "rendered_replays" # dont even bother changing this, it just outputs in the danser folder i cba to fix
OSU_SONGS_DIR = "USE YOUR BRAIN" 

# ===== Mod Constants =====
MODS = {
    0: "NM",
    1 << 0: "NF",
    1 << 1: "EZ",
    1 << 2: "TD",
    1 << 3: "HD",
    1 << 4: "HR",
    1 << 5: "SD",
    1 << 6: "DT",
    1 << 7: "RX",
    1 << 8: "HT",
    1 << 9: "NC",
    1 << 10: "FL",
    1 << 11: "AT",
    1 << 12: "SO",
    1 << 13: "AP",
    1 << 14: "PF",
    1 << 15: "K4",
    1 << 16: "K5",
    1 << 17: "K6",
    1 << 18: "K7",
    1 << 19: "K8",
    1 << 20: "FI",
    1 << 21: "RD",
    1 << 22: "CN",
    1 << 23: "TP",
    1 << 24: "K9",
    1 << 25: "CO",
    1 << 26: "K1",
    1 << 27: "K3",
    1 << 28: "K2",
    1 << 29: "V2",
    1 << 30: "MI"
}

# ===== Helper Functions =====
def query_md5_api(hash):
    """Get beatmap info from catboy.best API"""
    api_url = f"https://catboy.best/api/v2/md5/{hash}"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {str(e)}")
        return None

def sanitize_filename(name):
    """Remove invalid characters from folder names"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.strip()

def parse_mods(mod_value):
    """Convert mod bitmask to string representation"""
    if mod_value == 0:
        return "NM"
    
    active_mods = []
    for bit_flag, mod_name in MODS.items():
        if bit_flag != 0 and (mod_value & bit_flag):
            active_mods.append(mod_name)
    
    # Special case for NC (always comes with DT)
    if "NC" in active_mods and "DT" in active_mods:
        active_mods.remove("DT")
    
    return "".join(active_mods)

def format_accuracy(replay):
    """Calculate and format accuracy percentage"""
    total_hits = replay.count_300 + replay.count_100 + replay.count_50 + replay.count_miss
    if total_hits == 0:
        return "0.00%"
    accuracy = (replay.count_300 * 300 + replay.count_100 * 100 + replay.count_50 * 50) / (total_hits * 300) * 100
    return f"{accuracy:.2f}%"

def generate_output_name(replay, api_data):
    """Generate formatted output filename"""
    beatmap = api_data or {}
    beatmapset = beatmap.get('set', {})
    
    stars = beatmap.get('difficulty_rating', 0)
    player = replay.username
    artist = beatmapset.get('artist', 'Unknown Artist')
    title = beatmapset.get('title', 'Unknown Title')
    version = beatmap.get('version', 'Unknown Difficulty')
    mods = parse_mods(replay.mods.value if replay.mods else 0)
    accuracy = format_accuracy(replay)
    
    # Sanitize and format the final filename
    filename = f"[{stars:.2f}⭐] {player} - {artist} - {title} [{version}] +{mods} {accuracy}"
    return sanitize_filename(filename) + ".mp4"

def extract_osz(osz_file, api_data):
    """Extract .osz to properly named subfolder in Songs directory"""
    beatmapset_id = str(api_data.get('beatmapset_id'))
    artist = sanitize_filename(api_data.get('set', {}).get('artist', 'Unknown Artist'))
    title = sanitize_filename(api_data.get('set', {}).get('title', 'Unknown Title'))
    
    folder_name = f"{beatmapset_id} {artist} - {title}"
    extract_path = os.path.join(OSU_SONGS_DIR, folder_name)
    
    try:
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(osz_file, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        print(f"Extracted to: {extract_path}")
        return True
    except Exception as e:
        print(f"Extraction failed: {str(e)}")
        return False

def download_and_extract(api_data):
    """Download and extract beatmap with proper folder structure"""
    beatmapset_id = api_data.get('beatmapset_id')
    if not beatmapset_id:
        print("No beatmapset ID found in API data")
        return False
    
    download_url = f"https://catboy.best/d/{beatmapset_id}"
    osz_file = f"{beatmapset_id}.osz"
    
    try:
        print(f"Downloading beatmapset {beatmapset_id}...")
        response = requests.get(download_url, stream=True, timeout=15)
        response.raise_for_status()
        
        with open(osz_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        success = extract_osz(osz_file, api_data)
        os.remove(osz_file)
        return success
        
    except Exception as e:
        print(f"Download failed: {str(e)}")
        if os.path.exists(osz_file):
            os.remove(osz_file)
        return False

def render_with_danser(replay_path, output_name=None):
    """Render replay using danser-cli"""
    if not output_name:
        output_name = os.path.splitext(os.path.basename(replay_path))[0] + ".mp4"
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    output_path = os.path.join(OUTPUT_DIR, output_name)
    
    cmd = [
        DANSER_CLI_PATH,
        "-replay", replay_path,
        "-out", output_path,
    ]
    
    print(f"\nRendering replay with danser-cli...")
    try:
        subprocess.run(cmd, check=True)
        print(f"Success! Video saved to: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Rendering failed: {str(e)}")
        return False

def print_beatmap_info(api_data):
    """Display beatmap information"""
    if not api_data:
        return

    beatmap = api_data
    beatmapset = beatmap.get('set', {})
    
    print("\n=== Beatmap Information ===")
    print(f"\n[Basic Info]")
    print(f"Artist:       {beatmapset.get('artist', 'N/A')}")
    print(f"Title:        {beatmapset.get('title', 'N/A')}")
    print(f"Version:      {beatmap.get('version', 'N/A')} ({beatmap.get('difficulty_rating', 0):.2f}★)")
    print(f"Mapper:       {beatmapset.get('creator', 'N/A')}")
    print(f"Status:       {beatmap.get('status', 'N/A').capitalize()}")
    print(f"BPM:          {beatmap.get('bpm', 'N/A')}")

# ===== Main Workflow =====
def process_replay(replay_path):
    """Full pipeline: Parse → Download (if needed) → Render"""
    try:
        replay = Replay.from_path(replay_path)
        print(f"\nProcessing replay by {replay.username} (Score: {replay.score:,})")
        
        md5_hash = replay.beatmap_hash
        api_data = query_md5_api(md5_hash)
        
        if not api_data:
            print("Could not fetch beatmap info. Skipping download.")
            output_name = f"rendered_{os.path.splitext(os.path.basename(replay_path))[0]}.mp4"
        else:
            print_beatmap_info(api_data)
            
            beatmapset_id = str(api_data.get('beatmapset_id'))
            artist = sanitize_filename(api_data.get('set', {}).get('artist', 'Unknown Artist'))
            title = sanitize_filename(api_data.get('set', {}).get('title', 'Unknown Title'))
            expected_folder = f"{beatmapset_id} {artist} - {title}"
            
            if not os.path.exists(os.path.join(OSU_SONGS_DIR, expected_folder)):
                if not download_and_extract(api_data):
                    print("Proceeding with rendering anyway...")
            else:
                print(f"Beatmap already exists: {expected_folder}")
            
            output_name = generate_output_name(replay, api_data)
        
        render_with_danser(replay_path, output_name)
        
    except Exception as e:
        print(f"Error processing replay: {str(e)}")

if len(sys.argv) < 2:
    print("Usage: python replay_processor.py <replay.osr>")
    print("(or drag/drop .osr file onto the script)")
    input("Press Enter to exit...")
    sys.exit(1)
    
replay_file = sys.argv[1]
if not os.path.exists(replay_file):
    print(f"Error: File not found - {replay_file}")
    sys.exit(1)
    
process_replay(replay_file)