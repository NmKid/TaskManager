import sys
from pathlib import Path

# Add src to path if needed (though usually running from root works)
sys.path.append(str(Path(__file__).resolve().parent))

from config.config import BASE_DIR

def main():
    print(f"Starting TaskManager from {BASE_DIR}")
    print("TODO: Implement Sync Logic")

if __name__ == "__main__":
    main()
